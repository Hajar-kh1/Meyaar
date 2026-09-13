from __future__ import annotations

import json
import os
from pathlib import Path
import truststore
from dotenv import load_dotenv
from groq import Groq

from src.geosa_rag.service import retrieve


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
truststore.inject_into_ssl()
LLM_MODEL = os.getenv("GEORFP_MODEL", "openai/gpt-oss-20b")


def _client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")
    return Groq(api_key=api_key)


def _retrieve_requirements(
    project_description: str,
    top_k: int = 8,
) -> list[dict]:
    query = (
        "متطلبات البيانات الجيومكانية "
        "الجودة البيانات الوصفية المرجع المكاني "
        "التسليم القبول "
        + project_description
    )

    return retrieve(
        query,
        top_k=top_k,
    )


def _generate_rfp(
    project_description: str,
    sources: list[dict],
) -> str:
    context = "\n\n".join(
        (
            f"[S{index}]\n"
            f"Document: {item['document']}\n"
            f"Page: {item['page']}\n"
            f"Content:\n{item['text']}"
        )
        for index, item in enumerate(
            sources,
            start=1,
        )
    )

    prompt = f"""
أنت GeoRFP Assistant داخل نظام Meyaar.

مهمتك صياغة الجزء الجيومكاني/GIS فقط من وثيقة RFP.

وصف المشروع:
{project_description}

مقتطفات GeoSA:
{context}

أنشئ المتطلبات تحت الأقسام التالية:

1. نطاق العمل الجيومكاني
2. متطلبات البيانات الجيومكانية
3. نظام الإسناد والمرجع المكاني
4. متطلبات جودة البيانات
5. البيانات الوصفية Metadata
6. صيغ وطرق تسليم البيانات
7. التحقق وضمان الجودة
8. معايير القبول Acceptance Criteria
9. إعادة التسليم ومعالجة الأخطاء
10. الامتثال للمعايير

القواعد:
- استخدم فقط المعلومات التي تدعمها المصادر.
- لا تخترع نسب دقة أو حدود رقمية.
- لا تعمم متطلبات طبقة محددة على كل أنواع البيانات.
- إذا لم يدعم أي مصدر متطلبًا لقسم معين، اكتب:
  "لا يوجد متطلب صريح مسترجع من المصادر المتاحة لهذا القسم."
- لا تضف صيغ تسليم أو مدد زمنية أو نسبًا أو أدوات أو بروتوكولات لم تظهر في المصادر.
- ضع بعد كل متطلب مدعوم رقم المصدر بالشكل [S1] أو [S2].
- لا تحول توصية عامة إلى شرط إلزامي.- اجعل المتطلبات قابلة للاستخدام داخل RFP حقيقي.
- لا تنشئ متطلبات مالية أو قانونية أو إدارية.
- ركز فقط على GIS والبيانات الجيومكانية.
- أجب بالعربية.
""".strip()

    response = _client().chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0.1,
        max_tokens=1800,
    )

    return response.choices[0].message.content.strip()


def generate_geospatial_rfp(
    project_description: str,
    top_k: int = 8,
) -> dict:
    project_description = project_description.strip()

    if not project_description:
        raise ValueError(
            "Project description cannot be empty."
        )

    sources = _retrieve_requirements(
        project_description,
        top_k=top_k,
    )

    if not sources:
        return {
            "rfp": None,
            "sources": [],
            "status": "insufficient_sources",
        }

    try:
        rfp = _generate_rfp(
            project_description,
            sources,
        )
        status = "completed"
    except Exception as exc:
        print("GEORFP LLM ERROR:", exc)
        rfp = None
        status = "llm_failed"

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
        "rfp": rfp,
        "sources": formatted_sources,
        "status": status,
    }