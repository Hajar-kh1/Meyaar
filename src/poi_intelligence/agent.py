from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from src.poi_intelligence.tools import (
    analyze_poi_quality,
    get_poi_summary,
    search_geosa,
)


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

MODEL = os.getenv(
    "POI_INTELLIGENCE_MODEL",
    "openai/gpt-oss-20b",
)


def _client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    return Groq(api_key=api_key)


def _choose_tools(question: str) -> list[str]:
    prompt = f"""
أنت Router Agent داخل POI Intelligence في نظام Meyaar.

السؤال:
{question}

الأدوات المتاحة:

1. poi_quality
تفحص جودة بيانات POI:
- missing names
- missing categories
- missing coordinates
- invalid coordinates
- duplicates
- quality score

2. poi_summary
تعطي ملخصًا عن:
- عدد POIs
- الفئات
- توزيع الفئات

3. geosa_rag
تبحث في مستندات GeoSA عن المعايير والمتطلبات.

اختر فقط الأدوات اللازمة للإجابة.

أعد JSON فقط بهذا الشكل:
{{"tools":["poi_quality","geosa_rag"]}}

القيم المسموحة:
poi_quality
poi_summary
geosa_rag
""".strip()

    response = _client().chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0,
        max_tokens=150,
    )

    text = response.choices[0].message.content.strip()

    try:
        result = json.loads(text)
        tools = result.get("tools", [])
    except Exception:
        tools = ["poi_quality", "geosa_rag"]

    allowed = {
        "poi_quality",
        "poi_summary",
        "geosa_rag",
    }

    return [
        tool
        for tool in tools
        if tool in allowed
    ]


def _run_tools(
    geojson: dict,
    question: str,
    tools: list[str],
) -> dict:
    results = {}

    if "poi_quality" in tools:
        results["poi_quality"] = analyze_poi_quality(
            geojson
        )

    if "poi_summary" in tools:
        results["poi_summary"] = get_poi_summary(
            geojson
        )

    if "geosa_rag" in tools:
        results["geosa_rag"] = search_geosa(
            question,
            top_k=5,
        )

    return results


def _final_answer(
    question: str,
    tool_results: dict,
) -> str:
    prompt = f"""
أنت POI Intelligence Agent داخل نظام Meyaar.

السؤال:
{question}

نتائج الأدوات:
{json.dumps(tool_results, ensure_ascii=False)}

أجب اعتمادًا فقط على نتائج الأدوات.

القواعد:
- لا تخترع أرقامًا أو أخطاء.
- نتائج poi_quality وpoi_summary هي نتائج النظام الفعلية.
- geosa_rag يمثل الأدلة المسترجعة من مستندات GeoSA.
- لا تنسب متطلبًا إلى GeoSA إذا لم يظهر في نتائج geosa_rag.
- فرّق بوضوح بين نتيجة تحليل البيانات وبين متطلبات GeoSA.
- إذا لم تكف الأدلة، قل ذلك بوضوح.
- أجب بالعربية.
- اجعل الإجابة مختصرة ومباشرة.
""".strip()

    response = _client().chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0.1,
        max_tokens=900,
    )

    return response.choices[0].message.content.strip()


def run_agent(
    geojson: dict,
    question: str,
) -> dict:
    selected_tools = _choose_tools(question)

    if not selected_tools:
        selected_tools = ["poi_summary"]

    tool_results = _run_tools(
        geojson,
        question,
        selected_tools,
    )

    answer = _final_answer(
        question,
        tool_results,
    )

    return {
        "question": question,
        "selected_tools": selected_tools,
        "tool_results": tool_results,
        "answer": answer,
    }