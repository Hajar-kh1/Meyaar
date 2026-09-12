"""Grounded chat over a run's validation results, agent analyses and the
remediation audit, WITH conversation memory.

The chat answers questions about ONE engine run using ONLY:
  - the run summary (counts, most common error, priority actions)
  - the stored agent analyses (explanations, causes, recommendations)
  - the rule registry (rule meaning, heuristic vs deterministic)
  - the COMPLETE stored analysis data (agent/retrieval.py): the whole saved
    analysis payload with every key the pipeline persisted, the full record of
    every feature the run touches (all layer attributes + PostGIS
    measurements: lengths, areas, distances, coordinates, counts), the raw
    rule-engine findings with their details text, and a dynamically derived
    index of every field name present. No field whitelist is involved, so a
    question about any stored value — including a field added after this code
    was written — is answered from real data.
  - the remediation audit (what was auto-fixed, what is queued for a human,
    what failed) — so "what did the agent fix?" is answered truthfully.
  - the conversation so far for this (run_id, user_key) — persisted chat
    turns from agent_chat_messages — so follow-ups ("and the first error I
    asked about?", "as you said earlier") keep their context instead of
    re-explaining, and repeated questions don't re-derive the same answer.

It never answers from general knowledge about features that are not in the
run, and it never invents numbers. Sources returned are filtered to ids that
actually exist in the provided context (no hallucinated citations).

Memory is best-effort by design: if the chat-memory table does not exist on
an older DB, fetching/saving is skipped with a warning and the chat still
works exactly as before (stateless, grounded on the run only).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from agent.core.config import settings
from agent.core.llm import get_llm
from agent.db.base import Repository
from agent.retrieval import (build_analysis_dataset, build_batch_analysis_dataset,
                             fit_context, recent_uploads_summary)
from agent.rules.registry import get_rule

logger = logging.getLogger(__name__)

# How many past turns (question/answer pairs) are replayed into the prompt.
# Bounded on purpose: memory is for continuity, not for unbounded token burn.
CHAT_HISTORY_LIMIT = 6

SYSTEM_PROMPT = (
    "You are Meyaar's chat assistant for a Saudi geospatial compliance run. "
    "Answer questions about THIS validation run using ONLY the context provided "
    "(run summary + per-error analyses + remediation audit). Rules: "
    "1) Never invent feature ids, counts, areas, or distances. "
    "2) If the question is about something not present in the context, say so "
    "   explicitly (e.g. 'that feature is not among this run's findings'). "
    "3) Be concise and practical. Group findings by error type and severity, "
    "and state the count in each group. Present individual findings as "
    "'the first error', 'the second error', and so on. Do not include file "
    "names, UUIDs, feature IDs, result IDs, or rule IDs in the visible answer "
    "unless the user explicitly asks for technical identifiers or exact details. "
    "4) Heuristic rules (RD001/RD002) are candidates, NOT confirmed errors — "
    "   mention they need human review when relevant. "
    "5) Answer in the same language as the user's question. If the question "
    "   is Arabic, use clear Modern Standard Arabic while preserving rule IDs "
    "   and feature IDs exactly. If it is English, answer in English. "
    "6) The context contains a 'remediation' audit of what the agent did about "
    "   each error: action=auto_fix with status=applied means it was repaired "
    "   automatically (only invalid-geometry fixes BLD003/RD004 are ever "
    "   automatic); action=human_review with status=pending_review means it is "
    "   queued for a human reviewer; action=auto_fix with status=failed means "
    "   the automatic repair was attempted, rolled back and logged; "
    "   action=no_action with status=none means nothing was done (layer-level "
    "   guidance only). When the user asks what was fixed automatically or "
    "   what still needs a human, answer from the remediation summary/items — "
    "   do NOT claim something was auto-fixed unless the audit says applied, "
    "   and do NOT claim something needs a human if it was already applied. "
    "7) A 'Conversation so far' block lists your earlier questions and answers "
    "   about THIS run. Use it for follow-ups: when the user refers back "
    "   ('the first error', 'as you said', 'what about the roads then?'), "
    "   honour the reference from the conversation + run context instead of "
    "   asking again or guessing. Stay consistent with your earlier answers — "
    "   never contradict a fact you already stated unless the run context "
    "   clearly supports the correction. Do not repeat whole earlier answers "
    "   verbatim; reference them briefly and build on them. "
    # ── complete analysis data (no field whitelist) ───────────────────────
    "8) The context carries the COMPLETE analysis data, not a sample: "
    "   'analysis_records' holds the stored analysis payload(s) with EVERY "
    "   field the system saved (whole JSON objects: insertion, validation, "
    "   quality metrics, geometry, and any other key the pipeline stored), "
    "   'feature_data' is the complete stored record of each feature (every "
    "   attribute the layer holds plus the computed measurements — length, "
    "   area, distance, overlap, vertex count, bbox, centroid, and the "
    "   geometry/coordinates), 'findings' are the raw rule-engine rows with "
    "   their 'details' text (the numbers the engine computed), and "
    "   'available_fields' indexes every field name present with an example "
    "   value and where it was found. Answer from these actual stored values; "
    "   never work from a fixed short list of fields. "
    "9) Field names may differ from the user's wording. Map by meaning using "
    "   'available_fields', 'feature_data' and 'analysis_records' (for example "
    "   a question about a street's length, a building's dimensions, a plot's "
    "   measurements or a feature's coordinates maps onto the dimension/"
    "   measurement fields actually stored for that layer and feature). State "
    "   which stored field you used and give its stored value. "
    "10) Preserve units exactly as stored (m, m², degrees, %, counts). Never "
    "   convert, re-round, or drop a unit. "
    "11) If a requested value is genuinely absent from the context, say "
    "   plainly that it is not available in this analysis. Never invent, "
    "   estimate, or borrow a value from another feature or analysis. "
    "12) For broad requests ('give me all the analysis information', 'the "
    "   details of this analysis', 'show me everything about the building') "
    "   return a structured summary of ALL meaningful available fields — "
    "   grouped by layer/feature and covering dimensions, areas, distances, "
    "   percentages/scores, counts, coordinates and the analysis metadata — "
    "   not just the headline counts. "
    # ── upload batch scope (a folder / multi-file selection) ──────────────
    "13) When the context has a 'batch_id' and a 'files' list, the question is "
    "   about ONE UPLOAD BATCH: several files analyzed together. Answer across "
    "   the whole selection: use 'files' for per-file numbers (each entry has "
    "   the file's name, layer, stored error count, compliance score and run) "
    "   and use 'source_file' on findings/analyses/feature records to say which "
    "   file a detail came from. Comparisons ('which file has the most "
    "   errors?', 'summarise the folder', 'which files are clean?') are expected "
    "   — compute them from the stored numbers, never from memory. Totals must "
    "   be stated as coming from the listed files. If a file has no run "
    "   (e.g. a map image), say it has no validation run instead of inventing "
    "   findings for it. Never let one file's values stand in for another's. "
    # ── the caller's OTHER uploads ────────────────────────────────────────
    "14) The context may carry 'recent_uploads': the caller's own earlier "
    "   uploads, newest first, one entry per upload selection (batch_id, "
    "   uploaded_at, files, filenames, total_errors, layers). Use it ONLY to "
    "   answer questions about other uploads ('how many files was the previous "
    "   batch?', 'what was my last upload?', 'compare this batch with the "
    "   previous one', 'which upload had the most errors?'). The upload being "
    "   discussed now is the entry marked is_current; 'the previous batch' means "
    "   the entry listed immediately AFTER it. Read the numbers (file counts, "
    "   error totals, names) exactly as listed — never estimate them, and never "
    "   reuse them as if they were this upload's values. If the asked-about "
    "   upload is not in the list (or the list is absent), say plainly that it "
    "   is not available; never invent an upload, a file count or a score. "
    "   Other users' uploads are never listed, so a question about someone "
    "   else's upload is not answerable from here."
)

MAX_CHAT_ANALYSES = 100


def _question_language(question: str) -> str:
    """Choose the response language from the user's actual question."""
    return "Arabic" if any("\u0600" <= char <= "\u06ff" for char in question) else "English"


def build_chat_context(repo: Repository, run_id: str,
                       viewer: Optional[dict] = None) -> dict:
    """Assemble the grounded context for one run.

    Includes the COMPLETE analysis dataset (see agent/retrieval.py): the whole
    stored analysis payload(s), the full record of every feature the run
    touches, the raw findings and a dynamic index of every available field
    name — so questions about any stored value (dimensions, areas, distances,
    percentages, counts, coordinates, or a field added later) are answered
    from real data instead of a hard-coded field list.

    ``viewer`` (the authenticated caller) additionally brings in that caller's
    own recent uploads, so questions about OTHER uploads ("how many files was
    the previous batch?") are answerable — see recent_uploads_summary.
    """
    analyses = repo.fetch_analyses(run_id)
    results = repo.fetch_results(run_id)
    stored = None
    if not analyses:
        # A run with no engine findings is still a completed analysis: the
        # analyze step persisted a zero-error summary. Chat on it must work
        # (\"is my data clean?\") instead of dead-ending in the \"run analyze
        # first\" error even though analyze already ran.
        try:
            stored = repo.fetch_run_summary(run_id)
        except Exception:
            stored = None
        if results or not stored:
            raise ValueError(
                f"No agent analysis found for run {run_id}. "
                "Run POST /api/validation/{run_id}/analyze (or the CLI analyze) first.")
    summary = repo.build_summary(results, analyses)
    summary["priority_actions"] = repo.priority_actions(summary)
    if stored and stored.get("narrative"):
        summary["narrative"] = stored.get("narrative")
    rules: dict[str, dict] = {}
    for a in analyses:
        rd = get_rule(a.rule_id)
        if rd is not None:
            rules[a.rule_id] = {"type": rd.type,
                                "requires_human_review": rd.requires_human_review,
                                "recommendation": rd.recommendation}
    # Complete, unfiltered analysis data — every stored key, every column.
    dataset = build_analysis_dataset(repo, run_id, results=results,
                                    analyses=analyses)
    context = {
        "run_id": run_id,
        "summary": summary,
        "analyses": dataset["analyses"][:MAX_CHAT_ANALYSES],
        "analyses_in_context": min(
            len(analyses),
            MAX_CHAT_ANALYSES,
        ),
        "total_analyses": len(analyses),
        "rules": rules,
        "remediation": _remediation_context(repo, run_id),
        # ── complete analysis data (no field whitelist) ───────────────────
        # analysis_records = whole stored payload(s); feature_data = every
        # attribute + measurement per feature; findings = raw engine rows with
        # their details; available_fields = dynamic index of field names.
        "analysis_records": dataset["analysis_records"],
        "feature_data": dataset["feature_data"],
        "findings": dataset["findings"],
        "available_fields": dataset["available_fields"],
        "data_counts": dataset["counts"],
    }
    # The caller's OTHER uploads: included only for an identified caller (so the
    # anonymous/CLI path stays unchanged and small). The entry for the upload
    # this run came from is marked is_current, which is how "the previous batch"
    # resolves even in single-run chat.
    if viewer:
        current_batch = next(
            (str(r.get("batch_id")) for r in dataset["analysis_records"]
             if isinstance(r, dict) and r.get("batch_id")), None)
        context["recent_uploads"] = recent_uploads_summary(
            repo, viewer, current_scope_id=current_batch)
    if dataset.get("truncation"):
        context["data_truncation"] = dataset["truncation"]
    return fit_context(context)


def build_batch_chat_context(repo: Repository, batch_id: str,
                             viewer: Optional[dict] = None) -> dict:
    """Complete context for ONE UPLOAD BATCH (a folder / multi-file selection).

    Same completeness rules as ``build_chat_context``, but merged across every
    analysis that shares the batch id: a per-file summary (name, layer, stored
    error count, compliance score, run), all findings, all agent analyses, every
    stored payload and every feature record (namespaced by file), plus the
    per-file remediation audit summary so "what did the agent fix in this
    batch?" is answerable truthfully.

    ``viewer`` (the authenticated caller) additionally brings in that caller's
    own recent uploads — with THIS batch marked is_current — so "how many files
    was the previous batch?" is answerable without ever exposing another user's
    uploads.
    """
    dataset = build_batch_analysis_dataset(repo, batch_id)
    if not dataset["files"]:
        raise ValueError(
            f"No analyses found for upload batch {batch_id}. "
            "Upload the folder again (each upload selection gets its own batch).")

    remediation = {"available": False, "by_file": {}, "items": []}
    for entry in dataset["files"]:
        run_id = entry.get("run_id")
        if not run_id:
            continue        # a map image has no validation run / audit
        try:
            per_run = _remediation_context(repo, run_id)
        except Exception:
            per_run = {"available": False, "summary": {}, "items": []}
        remediation["by_file"][entry["filename"]] = per_run.get("summary", {})
        remediation["available"] = remediation["available"] or per_run.get("available", False)
        for item in per_run.get("items", []):
            if len(remediation["items"]) >= MAX_CHAT_ANALYSES:
                break
            remediation["items"].append({**item, "source_file": entry["filename"]})

    context = {
        "batch_id": batch_id,
        "scope": "upload batch (all files of one upload selection)",
        "files": dataset["files"],
        "analyses": dataset["analyses"][:MAX_CHAT_ANALYSES],
        "analyses_in_context": min(len(dataset["analyses"]), MAX_CHAT_ANALYSES),
        "total_analyses": len(dataset["analyses"]),
        "findings": dataset["findings"],
        "analysis_records": dataset["analysis_records"],
        "feature_data": dataset["feature_data"],
        "available_fields": dataset["available_fields"],
        "remediation": remediation,
        "notes": dataset.get("notes", []),
        "data_counts": dataset["counts"],
    }
    if viewer:
        context["recent_uploads"] = recent_uploads_summary(
            repo, viewer, current_scope_id=batch_id)
    if dataset.get("truncation"):
        context["data_truncation"] = dataset["truncation"]
    return fit_context(context)


def _remediation_context(repo: Repository, run_id: str) -> dict:
    """Compact remediation audit for the chat prompt.

    Kept small on purpose: counts + one short item per record so the model
    can truthfully say what was auto-fixed / queued / failed without burning
    tokens on full before/after GeoJSON.
    """
    try:
        records = repo.fetch_remediation_records(run_id) or []
    except Exception:
        # The audit table may not exist on older DBs — chat must not break.
        return {"available": False, "summary": {}, "items": []}
    applied = sum(1 for r in records
                  if r.get("action") == "auto_fix" and r.get("status") == "applied")
    failed = sum(1 for r in records if r.get("status") == "failed")
    pending = sum(1 for r in records
                  if r.get("action") == "human_review"
                  and r.get("status") == "pending_review")
    no_action = sum(1 for r in records
                    if r.get("action") == "no_action")
    summary = {
        "total": len(records),
        "auto_fixed": applied,
        "failed": failed,
        "pending_review": pending,
        "no_action": no_action,
    }
    items = []
    for r in records[:MAX_CHAT_ANALYSES]:
        reason = str(r.get("reason") or "")[:180]
        items.append({
            "rule_id": r.get("rule_id"),
            "feature_id": r.get("feature_id"),
            "action": r.get("action"),
            "status": r.get("status"),
            "remediation_type": r.get("remediation_type"),
            "issue": str(r.get("issue") or "")[:140],
            "reason": reason,
            "human_review_required": bool(r.get("human_review_required")),
        })
    return {"available": True, "summary": summary, "items": items}


def _code_fence_strip(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        t = t.rsplit("\n", 1)[0] if t.endswith("```") else t
        if t.endswith("```"):
            t = t[:-3].strip()
    return t.strip()


def _load_history(repo: Repository, run_id: str, user_key: str,
                  history_limit: int) -> list[dict]:
    """Most recent turns for the (run_id, user_key) conversation, oldest
    first. Best-effort: an absent memory table or failing repository returns
    [] and the chat continues stateless (never breaks answering)."""
    if history_limit <= 0 or not user_key:
        return []
    try:
        turns = repo.fetch_chat_history(run_id, user_key, limit=history_limit)
    except Exception:
        logger.warning(
            "chat memory read failed for run %s (table absent or DB error); "
            "answering stateless", run_id, exc_info=True)
        return []
    return turns or []


def _conversation_block(history: list[dict]) -> str:
    """Render past turns as a compact numbered transcript for the prompt."""
    if not history:
        return ""
    lines: list[str] = []
    for i, turn in enumerate(history, 1):
        question = str(turn.get("question") or "").strip()
        answer = str(turn.get("answer") or "").strip()
        if not question:
            continue
        lines.append(f"{i}. user: {question}")
        lines.append(f"   assistant: {answer}")
    return "\n".join(lines)


def answer_question(repo: Repository, run_id: str, question: str,
                    llm: Optional[Any] = None,
                    user_key: str = "anonymous",
                    history_limit: int = CHAT_HISTORY_LIMIT,
                    context: Optional[dict] = None,
                    scope_label: Optional[str] = None,
                    viewer: Optional[dict] = None) -> dict:
    """Answer a question about a run. Returns {question, answer, sources}.

    ``run_id`` doubles as the conversation-memory scope, so batch chat (which
    passes the batch id as the scope) keeps its own separate thread. ``context``
    and ``scope_label`` let a caller supply a pre-built context — see
    ``answer_batch_question`` / ``build_batch_chat_context``. ``viewer`` is the
    authenticated caller: it unlocks that caller's own recent uploads in the
    context (never another user's) so questions about other uploads work.

    Conversation memory: prior turns for this (run_id, user_key) are replayed
    into the prompt (continuity for follow-ups) and the new turn is persisted
    to agent_chat_messages — both best-effort, so the chat stays usable and
    stateless-safe when the memory table is absent.
    """
    llm = llm or get_llm()
    if llm is None:
        raise RuntimeError(
            "Chat requires an LLM key (MEYAAR_LLM_API_KEY in agent/.env). "
            "The analysis endpoints work without one; chat does not.")

    context = context if context is not None else build_chat_context(
        repo, run_id, viewer=viewer)
    payload = json.dumps(context, ensure_ascii=False, default=str)
    history = _load_history(repo, run_id, user_key, history_limit)
    conversation = _conversation_block(history)
    response_language = _question_language(question)
    prompt = (
        "System instructions:\n" + SYSTEM_PROMPT +
        "\n\nRequired response language: " + response_language + ". "
        "The answer field MUST be written in that language. "
        "Keep technical IDs unchanged internally, but omit them from the visible "
        "answer unless the user explicitly requests them. Summarize repeated "
        "findings by category instead of listing long identifiers.\n\n"
        "Scope of this conversation: "
        + (scope_label or ("single analysis run " + str(run_id))) +
        ".\n\nContext (JSON): " + payload +
        (("\n\nConversation history (your earlier turns about this run):\n" + conversation)
         if conversation else "") +
        "\n\nUser question: " + question +
        "\n\nReply STRICT JSON only: "
        '{"answer": "your answer", "sources": ["RULE@feature", "..."]} '
        "where each source is a finding present in the context (rule_id@feature_id)."
    )
    attempts = max(1, settings.llm_retries)
    answer = ""
    sources_raw: list = []
    for _ in range(attempts):
        try:
            resp = llm.invoke(prompt)
            parsed = json.loads(_code_fence_strip(str(resp.content)))
            answer = str(parsed.get("answer", "")).strip()
            if answer:
                sources_raw = parsed.get("sources") or []
                break
        except Exception:
            continue
    if not answer:
        raise RuntimeError("The model did not return a valid answer; try again.")

    # Filter sources to ids that genuinely exist in the context.
    known = set()
    for a in context["analyses"]:
        known.add(f"{a['rule_id']}@{a.get('feature_id') or ''}".rstrip("@"))
        known.add(a["rule_id"])
        if a.get("feature_id"):
            known.add(a["feature_id"])
    sources = []
    for s in sources_raw:
        s = str(s).strip()
        if s in known and s not in sources:
            sources.append(s)

    # Persist the turn (best-effort — memory must never break chat).
    if user_key:
        try:
            repo.save_chat_turn(run_id, user_key, question, answer, sources)
        except Exception:
            logger.warning(
                "chat memory write failed for run %s (table absent or DB "
                "error); answer still returned", run_id, exc_info=True)
    return {"question": question, "answer": answer, "sources": sources}


def answer_batch_question(repo: Repository, batch_id: str, question: str,
                          llm: Optional[Any] = None,
                          user_key: str = "anonymous",
                          history_limit: int = CHAT_HISTORY_LIMIT,
                          viewer: Optional[dict] = None) -> dict:
    """Answer a question about an upload BATCH (a folder / multi-file selection).

    Same grounding, unit and memory rules as single-run chat: the context is
    merged across every analysis stored with this batch id (per-file summary +
    all findings, analyses, payloads and feature records), the conversation is
    keyed on the batch id so follow-ups ("and the second file?") keep their
    context, and cited sources stay filtered to findings that exist in the
    merged context. Raises ValueError when the batch has no stored analyses.

    ``viewer`` is the authenticated caller; it unlocks that caller's own recent
    uploads (this batch marked is_current) so "how many files was the previous
    batch?" is answered from the real numbers — never from another user's data.
    """
    context = build_batch_chat_context(repo, batch_id, viewer=viewer)
    files = context["data_counts"]["files"]
    return answer_question(
        repo, batch_id, question, llm=llm, user_key=user_key,
        history_limit=history_limit, context=context,
        scope_label=(f"an upload batch of {files} file(s) — see 'files' for the "
                     "per-file numbers, and 'source_file' to attribute a detail "
                     "to the file it came from"))
