from __future__ import annotations

from src.poi_intelligence.agent import run_agent


def run_poi_intelligence(
    geojson: dict,
    question: str = "حلل بيانات نقاط الاهتمام.",
) -> dict:
    return run_agent(
        geojson=geojson,
        question=question,
    )