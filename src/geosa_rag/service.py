from __future__ import annotations

import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv
import faiss
import numpy as np
from groq import Groq
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
DOCS_DIR = ROOT / "data" / "geosa_docs"
STORE_DIR = ROOT / "vector_store" / "geosa"

INDEX_PATH = STORE_DIR / "index.faiss"
CHUNKS_PATH = STORE_DIR / "chunks.json"

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
LLM_MODEL = os.getenv("GEOSA_RAG_MODEL", "openai/gpt-oss-20b")

_model: SentenceTransformer | None = None
_index = None
_chunks: list[dict] | None = None


def _embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")
    return Groq(api_key=api_key)


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _split_text(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 200,
) -> list[str]:
    if len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]

        if end < len(text):
            best_break = max(
                chunk.rfind("\n"),
                chunk.rfind(". "),
                chunk.rfind("؟"),
            )

            if best_break > chunk_size // 2:
                end = start + best_break + 1
                chunk = text[start:end]

        chunk = chunk.strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = max(end - overlap, start + 1)

    return chunks


def build_index() -> dict:
    pdf_files = sorted(DOCS_DIR.glob("*.pdf"))

    if not pdf_files:
        raise RuntimeError(f"No PDF documents found in {DOCS_DIR}")

    records = []

    for pdf_path in pdf_files:
        reader = PdfReader(str(pdf_path))

        for page_number, page in enumerate(reader.pages, start=1):
            text = _clean_text(page.extract_text() or "")

            if len(text) < 40:
                continue

            page_chunks = _split_text(text)

            for chunk_number, chunk in enumerate(page_chunks, start=1):
                records.append(
                    {
                        "document": pdf_path.name,
                        "page": page_number,
                        "chunk": chunk_number,
                        "text": chunk,
                    }
                )

    if not records:
        raise RuntimeError(
            "No readable text was extracted from GeoSA documents."
        )

    texts = [item["text"] for item in records]

    embeddings = _embedding_model().encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    vectors = np.asarray(embeddings, dtype="float32")

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    STORE_DIR.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(INDEX_PATH))

    CHUNKS_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    global _index, _chunks
    _index = index
    _chunks = records

    return {
        "status": "built",
        "documents": len(pdf_files),
        "chunks": len(records),
        "index": str(INDEX_PATH),
    }


def _load_store():
    global _index, _chunks

    if _index is not None and _chunks is not None:
        return

    if not INDEX_PATH.exists() or not CHUNKS_PATH.exists():
        build_index()
        return

    _index = faiss.read_index(str(INDEX_PATH))
    _chunks = json.loads(
        CHUNKS_PATH.read_text(encoding="utf-8")
    )


def retrieve(question: str, top_k: int = 5) -> list[dict]:
    _load_store()

    query_embedding = _embedding_model().encode(
        [question],
        normalize_embeddings=True,
    )

    query_vector = np.asarray(
        query_embedding,
        dtype="float32",
    )

    scores, indices = _index.search(
        query_vector,
        min(top_k, len(_chunks)),
    )

    results = []

    for score, index_position in zip(scores[0], indices[0]):
        if index_position < 0:
            continue

        item = dict(_chunks[index_position])
        item["score"] = round(float(score), 4)

        results.append(item)

    return results


def _generate_answer(
    question: str,
    sources: list[dict],
) -> str:
    context = "\n\n".join(
        (
            f"[SOURCE {i}]\n"
            f"Document: {item['document']}\n"
            f"Page: {item['page']}\n"
            f"Content:\n{item['text']}"
        )
        for i, item in enumerate(sources, start=1)
    )

    system_prompt = """
أنت GeoSA Intelligence Assistant داخل نظام Meyaar.

مهمتك الإجابة عن أسئلة المستخدم اعتمادًا فقط على المقاطع المسترجعة من مستندات GeoSA.

القواعد:
- لا تستخدم معرفة خارج المصادر المسترجعة.
- لا تخترع أي متطلبات أو أرقام أو أسماء معايير.
- إذا لم تكفِ المصادر للإجابة، قل بوضوح:
  "لا توجد معلومات كافية في المصادر المتاحة."
- أجب بالعربية ما لم يطلب المستخدم لغة أخرى.
- استخدم إجابة واضحة ومباشرة.
- لا تكتب قائمة المصادر في نهاية الإجابة لأن النظام يعرضها بشكل منفصل.
- فرّق بين عناصر جودة البيانات، ومؤشرات تقييم الجودة، ومتطلبات الجودة الخاصة بطبقة معينة.
- لا تعمم نسبة أو حدًا رقميًا يخص طبقة جيومكانية محددة على جميع البيانات.
- إذا كان السؤال عن "عناصر جودة البيانات"، أعط الأولوية للمقطع الذي يعرّف هذه العناصر مباشرة.
- عند وجود اختلاف بين المقاطع، لا تدمجها كأنها تصنيف واحد.
""".strip()

    user_prompt = f"""
السؤال:
{question}

المصادر المسترجعة:
{context}

أجب اعتمادًا على هذه المصادر فقط.
""".strip()

    client = _groq_client()

    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0.1,
        max_tokens=900,
    )

    return response.choices[0].message.content.strip()


def ask(
    question: str,
    top_k: int = 5,
) -> dict:
    question = question.strip()

    if not question:
        raise ValueError("Question cannot be empty.")

    sources = retrieve(
        question,
        top_k=top_k,
    )

    if not sources:
        return {
            "answer": "لم أجد معلومات كافية في مستندات GeoSA للإجابة على هذا السؤال.",
            "sources": [],
        }

    try:
        answer = _generate_answer(
            question,
            sources,
        )
    except Exception as exc:
        answer = (
            "تعذر توليد الإجابة باستخدام النموذج اللغوي حاليًا، "
            "لكن تم العثور على مصادر مرتبطة بالسؤال."
        )
        print("GEOSA RAG LLM ERROR:", exc)

    formatted_sources = [
        {
            "document": item["document"],
            "page": item["page"],
            "excerpt": item["text"][:700],
            "score": item["score"],
        }
        for item in sources
    ]

    return {
        "answer": answer,
        "sources": formatted_sources,
    }
def ask_with_attachment(
    question: str,
    attachment_name: str,
    attachment_context: str,
    top_k: int = 5,
) -> dict:
    question = question.strip()

    if not question:
        raise ValueError(
            "Question cannot be empty."
        )

    sources = retrieve(
        question,
        top_k=top_k,
    )

    if not sources:
        return {
            "answer": (
                "لم أجد معلومات كافية في مستندات GeoSA للإجابة على هذا السؤال."
            ),
            "sources": [],
            "attachment": attachment_name,
        }

    context = "\n\n".join(
        (
            f"[SOURCE {index}]\n"
            f"Document: {item['document']}\n"
            f"Page: {item['page']}\n"
            f"Content:\n{item['text']}"
        )
        for index, item in enumerate(
            sources,
            start=1,
        )
    )

    system_prompt = """
أنت GeoSA Intelligence Assistant داخل نظام Meyaar.

لديك مصدران للمعلومات:
1. مرفق المستخدم: يمثل البيانات أو المستند الذي يريد المستخدم تحليله.
2. مقتطفات GeoSA: تمثل الأدلة الرسمية المستخدمة لشرح المعايير.

القواعد:
- يمكنك وصف ما يظهر فعليًا في مرفق المستخدم.
- لا تنسب أي متطلب إلى GeoSA إلا إذا كان مدعومًا بمقتطفات GeoSA.
- لا تخترع نسبًا أو حدودًا رقمية.
- لا تدّعي أن Dataset متوافقة بالكامل مع GeoSA إلا إذا تم التحقق من جميع المتطلبات اللازمة.
- فرّق بوضوح بين "ما وجدناه في الملف" و"ما تقوله GeoSA".
- إذا لم تكفِ المصادر، قل ذلك.
- أجب بالعربية ما لم يطلب المستخدم غير ذلك.
""".strip()

    user_prompt = f"""
السؤال:
{question}

المرفق:
{attachment_name}

محتوى أو ملخص المرفق:
{attachment_context}

مقتطفات GeoSA:
{context}
""".strip()

    try:
        response = (
            _groq_client()
            .chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                temperature=0.1,
                max_tokens=1100,
            )
        )

        answer = (
            response.choices[0]
            .message.content.strip()
        )

    except Exception as exc:
        print(
            "GEOSA ATTACHMENT LLM ERROR:",
            exc,
        )
        answer = (
            "تعذر توليد الإجابة حاليًا، "
            "لكن تم العثور على مصادر GeoSA مرتبطة بالسؤال."
        )

    return {
        "answer": answer,
        "attachment": attachment_name,
        "sources": [
            {
                "document": item[
                    "document"
                ],
                "page": item["page"],
                "excerpt": item[
                    "text"
                ][:700],
                "score": item[
                    "score"
                ],
            }
            for item in sources
        ],
    }