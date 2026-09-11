"""FastAPI router for the Error Analysis Agent.

Routes follow the team's FastAPI conventions (backend/ on origin/backend).
The backend teammate can mount this router:

    from agent.api.router import router as analysis_router
    app.include_router(analysis_router, prefix="/api")

or run the standalone app (agent.api.app:app) during development.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, UUID4

from agent.chat import answer_question
from agent.core.models import (
    AnalyzeResponse,
    AnalysisListResponse,
    RemediationListResponse,
    RunSummary,
)
from agent.db.base import Repository
from agent.graph.builder import build_summary_model, run_analysis
from agent.map_elements.service import suggest_missing_map_element
from agent.retrieval import build_analysis_dataset
from src.api.auth import current_user, database_engine, ensure_app_tables, require_run_access
from src.api.schemas import MapElementSuggestionRequest, MapElementSuggestionResponse

router = APIRouter(tags=["validation-analysis"])


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: list[str] = Field(default_factory=list)


def get_repository() -> Repository:
    """FastAPI dependency: production repository (override in tests)."""
    from agent.db.postgres import PostgresRepository
    return PostgresRepository()


@router.post("/map-elements/suggest", response_model=MapElementSuggestionResponse,
             summary="Suggest a missing map element without editing the image")
def suggest_map_element(body: MapElementSuggestionRequest,
                        user: dict = Depends(current_user)):
    """Agent-owned, preview-only cartographic suggestion endpoint."""
    return suggest_missing_map_element(body.filename, body.element)


@router.post("/validation/{run_id}/analyze",
             response_model=AnalyzeResponse,
             summary="Trigger Error Analysis for a validation run")
def trigger_analysis(run_id: UUID4, repo: Repository = Depends(get_repository), user: dict = Depends(current_user)):
    with database_engine().begin() as connection:
        ensure_app_tables(connection)
        require_run_access(connection, user, str(run_id))
    out = run_analysis(str(run_id), repository=repo)
    n = len(out.get("analyses", []))
    if out.get("errors"):
        # DB/context problems are logged and surfaced, not silently dropped.
        return AnalyzeResponse(
            run_id=str(run_id), status="completed_with_warnings",
            total_errors_analyzed=n,
            message="; ".join(out["errors"][:5]))
    return AnalyzeResponse(run_id=str(run_id), status="completed",
                           total_errors_analyzed=n,
                           message=f"Analyzed {n} validation error(s)")


@router.get("/validation/{run_id}/analysis",
            response_model=AnalysisListResponse,
            summary="Retrieve Error Analyses for a validation run")
def get_analysis(run_id: UUID4, repo: Repository = Depends(get_repository), user: dict = Depends(current_user)):
    with database_engine().begin() as connection:
        ensure_app_tables(connection)
        require_run_access(connection, user, str(run_id))
    try:
        analyses = repo.fetch_analyses(str(run_id))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"analysis fetch failed: {exc}")
    results = repo.fetch_results(str(run_id))
    stored = None
    if not analyses:
        # A run with no engine findings is still a completed analysis: the
        # analyze step persists a zero-error summary. Return that as a valid
        # empty result instead of a 404 that loops ("run analyze first")
        # even after analyze already ran.
        try:
            stored = repo.fetch_run_summary(str(run_id))
        except Exception:
            stored = None
        if results or not stored:
            raise HTTPException(
                status_code=404,
                detail="No agent analysis found for this run. "
                       "Call POST /api/validation/{run_id}/analyze first.")
    summary = repo.build_summary(results, analyses)
    summary["priority_actions"] = repo.priority_actions(summary)
    # Attach the persisted executive narrative (written by the summarize node).
    if stored is None:
        try:
            stored = repo.fetch_run_summary(str(run_id))
        except Exception:
            stored = None   # table may be absent on older DBs — summary still works
    if stored and stored.get("narrative"):
        summary["narrative"] = stored.get("narrative")
    return AnalysisListResponse(
        run_id=str(run_id),
        summary=build_summary_model(str(run_id), summary),
        analyses=analyses,
    )


@router.get("/validation/{run_id}/remediation",
            response_model=RemediationListResponse,
            summary="Retrieve remediation/audit records for a validation run")
def get_remediation(run_id: UUID4, repo: Repository = Depends(get_repository), user: dict = Depends(current_user)):
    """Remediation decisions + audit for a run. The dashboard can
    distinguish: action=auto_fix/status=applied (automatically fixed),
    action=human_review/status=pending_review (needs a reviewer),
    action=no_action/status=none (nothing to do), status=failed (rolled back).
    Records are created by POST /api/validation/{run_id}/analyze."""
    with database_engine().begin() as connection:
        ensure_app_tables(connection)
        require_run_access(connection, user, str(run_id))
    try:
        records = repo.fetch_remediation_records(str(run_id))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"remediation fetch failed: {exc}")
    return RemediationListResponse(run_id=str(run_id), remediation=records)


@router.get("/validation/{run_id}/record",
            summary="Retrieve the COMPLETE analysis data for a run (every stored field)")
def get_analysis_data(run_id: UUID4, repo: Repository = Depends(get_repository),
                      user: dict = Depends(current_user)):
    """The unfiltered analysis dataset behind the grounded chat.

    Returns the whole stored analysis payload(s) (every JSON key the pipeline
    persisted), the complete record of every feature the run touches (all
    layer attributes + PostGIS measurements), the raw rule-engine findings
    including their details text, and the index of every available field name
    with an example value. Nothing is whitelisted, so a field added to the
    pipeline or a layer later is returned with no code change.
    """
    with database_engine().begin() as connection:
        ensure_app_tables(connection)
        require_run_access(connection, user, str(run_id))
    dataset = build_analysis_dataset(repo, str(run_id))
    counts = dataset["counts"]
    if not any(counts.get(key) for key in ("analyses", "findings",
                                           "analysis_records")):
        raise HTTPException(
            status_code=404,
            detail="No analysis found for this run. "
                   "Call POST /api/validation/{run_id}/analyze first.")
    return {"run_id": str(run_id), **dataset}


@router.post("/validation/{run_id}/chat",
             response_model=ChatResponse,
             summary="Ask a grounded question about a run's engine results")
def chat_about_run(run_id: UUID4, body: ChatRequest,
                   repo: Repository = Depends(get_repository), user: dict = Depends(current_user)):
    """Chat endpoint: answers from the run's stored analyses + summary only.

    Requires an LLM key (MEYAAR_LLM_API_KEY) — analysis endpoints work
    without one, chat does not.
    """
    with database_engine().begin() as connection:
        ensure_app_tables(connection)
        require_run_access(connection, user, str(run_id))
    try:
        # Conversation memory is scoped to the authenticated user so each
        # user's thread about this run stays private (CLI uses user_key="cli").
        out = answer_question(repo, str(run_id), body.question,
                              user_key=str(user.get("user_id") or "anonymous"))
    except ValueError as exc:      # no analyses yet for this run
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        msg = str(exc)
        if "LLM key" in msg:
            raise HTTPException(status_code=503, detail=msg)
        raise HTTPException(status_code=502, detail=msg)
    return ChatResponse(**out)
