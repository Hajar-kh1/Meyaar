"""Complete, field-agnostic retrieval of everything Meyaar stored for an analysis.

Why this module exists
----------------------
The grounded chat used to answer from a hand-picked slice of a run: the
agent's per-error explanations, the severity counts, the rule registry and the
remediation audit. Real questions ("what is the street length and width?",
"what are the plot dimensions?", "what is the building footprint?", "what are
the distances / percentages / coordinates?") need the *whole* stored analysis:

  * ``analysis_records``  — the saved analysis payload (public.saved_analyses
    .result_payload, JSONB) returned WHOLE: every key the pipeline stored —
    insertion, validation (findings + geometry), analysis, quality metrics,
    layer/fixed GeoJSON — with no extraction of a predefined key set.
  * ``feature_data``      — for every feature the run touches: the COMPLETE
    record (every attribute column the layer table holds, discovered at query
    time) merged with the PostGIS measurements (length_m, area_m2,
    distance_m, overlap_area_m2, vertex_count, bbox, centroid) and the
    geometry.
  * ``findings``          — the raw rule-engine rows, including their
    ``details`` text (the numbers the engine computed: areas, distances,
    coordinates, counts, tolerances).
  * ``available_fields``  — a dynamically derived index of every field name
    present in the above, with an example value and where it was found, so a
    question can be mapped onto the project's real field names.

NOTHING here enumerates analysis fields. Whatever the pipeline stores today —
or after a new column/JSON key is added tomorrow — flows through
automatically. Only *generic* size guards are applied (list length, string
length, total prompt budget) and they record what they trimmed, they never
select which analysis fields are "important" or hard-code a schema.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional, Sequence

from agent.core.models import ErrorAnalysis, ValidationResult
from agent.db.base import Repository
from agent.rules.registry import get_rule

logger = logging.getLogger(__name__)

# ── generic collection caps (NOT field lists) ───────────────────────────────
MAX_ANALYSIS_RECORDS = 20          # stored payloads per run (normally 1)
MAX_FEATURE_RECORDS = 200          # distinct features described per run
MAX_RELATED_IDS_PER_LAYER = 40     # ids parsed out of finding details
MAX_PAYLOAD_FEATURE_IDS_PER_LAYER = 50   # ids referenced by the saved payload
MAX_FIELD_ENTRIES = 500            # entries in the field index
MAX_FIELD_CONTEXTS = 3             # "found in" examples per field name

# Escalating (list_cap, str_cap) steps for the size guard: the first step whose
# serialized size fits the budget is used. Large GeoJSON strings / feature
# lists are what normally trigger a smaller step.
_SHRINK_STEPS: tuple[tuple[int, int], ...] = (
    (500, 4000), (200, 2000), (60, 800), (20, 300), (5, 120), (1, 60),
)
MAX_CONTEXT_CHARS = 400_000

# Identifier-like tokens inside a finding's details text ("overlaps BLD_157",
# "junction at 46.68 24.66"): same shape the analysis nodes use.
_ID_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])([A-Za-z]+_[A-Za-z0-9_]+|[A-Za-z]+[0-9][A-Za-z0-9_]*)")


# ── generic size guard ──────────────────────────────────────────────────────
def _shrink(value: Any, list_cap: int, str_cap: int) -> Any:
    """Recursively shorten a JSON-ish structure *without* dropping keys.

    Dicts keep every key (keys are the analysis fields — that is exactly what
    must survive); long lists keep their first ``list_cap`` items and record
    the omitted count; long strings are head-truncated with a marker.
    """
    if isinstance(value, dict):
        return {k: _shrink(v, list_cap, str_cap) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        items = [_shrink(v, list_cap, str_cap) for v in list(value)[:list_cap]]
        omitted = len(value) - len(items)
        if omitted > 0:
            items.append({"_omitted_items": omitted})
        return items
    if isinstance(value, str) and len(value) > str_cap:
        return value[:str_cap] + f"…[+{len(value) - str_cap} chars omitted]"
    return value


def _serialize(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return json.dumps({"unserializable": str(value)}, ensure_ascii=False)


def fit_context(context: dict) -> dict:
    """Fit a chat context inside the prompt budget.

    Applies the escalating generic size guard and annotates the result with
    ``context_chars`` / ``context_truncated`` so the caller (and the model)
    knows whether anything was shortened. Keys are never removed by the guard
    itself.
    """
    for list_cap, str_cap in _SHRINK_STEPS:
        candidate = _shrink(context, list_cap, str_cap)
        size = len(_serialize(candidate))
        if size <= MAX_CONTEXT_CHARS:
            candidate["context_chars"] = size
            candidate["context_truncated"] = (list_cap, str_cap) != _SHRINK_STEPS[0]
            return candidate
    candidate = _shrink(context, *_SHRINK_STEPS[-1])
    candidate["context_chars"] = len(_serialize(candidate))
    candidate["context_truncated"] = True
    return candidate


# ── retrieval ───────────────────────────────────────────────────────────────
def _safe(call, *args, **kwargs) -> Any:
    """Best-effort repository call: an absent table/column (older DB) or a
    driver error degrades to "not available" instead of breaking the answer."""
    try:
        return call(*args, **kwargs)
    except Exception:
        logger.warning("analysis retrieval failed for %r", getattr(call, "__name__", call),
                       exc_info=True)
        return None


def fetch_analysis_records(repo: Repository, run_id: str) -> list[dict]:
    """The COMPLETE stored analysis payload(s) for a run.

    Each entry carries the analysis metadata (id, filename, type, status,
    compliance score, error count, created_at) plus ``result``: the entire
    ``result_payload`` JSON object exactly as the pipeline stored it —
    unfiltered, every key. Repositories that cannot expose it return nothing
    and the caller reports the data as unavailable rather than inventing it.
    """
    records = _safe(repo.fetch_analysis_records, run_id)
    out: list[dict] = []
    for rec in (records or [])[:MAX_ANALYSIS_RECORDS]:
        if isinstance(rec, dict):
            out.append(dict(rec))
    return out


def fetch_feature_records(repo: Repository, layer_name: str,
                          feature_ids: Sequence[Optional[str]]) -> dict[str, dict]:
    """Complete record per feature for one layer.

    Primary path: ``repo.fetch_feature_records`` — every attribute column the
    layer holds (discovered at query time) plus the computed geometry
    measurements. Fallback (older repositories): the structured
    ``fetch_spatial_measurements`` shape. Missing ids are simply absent.
    """
    ids = [str(fid) for fid in feature_ids if fid]
    if not ids:
        return {}
    fn = getattr(repo, "fetch_feature_records", None)
    if callable(fn):
        recs = _safe(fn, layer_name, ids)
        if recs:
            return {str(k): dict(v if isinstance(v, dict) else {"value": v})
                    for k, v in recs.items()}
    fn = getattr(repo, "fetch_spatial_measurements", None)
    if callable(fn):
        recs = _safe(fn, layer_name, ids)
        if recs:
            return {str(k): dict(v if isinstance(v, dict) else {"value": v})
                    for k, v in recs.items()}
    return {}


def _related_ids_from_details(results: Sequence[ValidationResult],
                              layer_name: str) -> list[str]:
    """Feature ids merely *mentioned* in a finding's details text (e.g. the
    other building in an overlap) — so their complete record is retrieved
    too. Rule ids are skipped (they are not features)."""
    out: list[str] = []
    for r in results:
        if r.layer_name != layer_name or not r.details:
            continue
        for token in _ID_TOKEN_RE.findall(r.details):
            if token in out or token == r.feature_id:
                continue
            if get_rule(token) is not None:      # rule id, not a feature
                continue
            out.append(token)
    return out[:MAX_RELATED_IDS_PER_LAYER]


def _iter_payload_ids(value: Any, layer: str, depth: int = 0):
    """Yield (layer, feature_id) for every feature the stored payload mentions
    — validation error rows, report rows and layer-GeoJSON features alike."""
    if depth > 8:
        return
    if isinstance(value, dict):
        own_layer = value.get("layer_name") or layer
        fid = value.get("feature_id")
        if isinstance(fid, (str, int)) and str(fid):
            yield own_layer, str(fid)
        for child in value.values():
            yield from _iter_payload_ids(child, own_layer, depth + 1)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _iter_payload_ids(child, layer, depth + 1)


def _payload_feature_ids(records: Sequence[dict]) -> dict[str, list[str]]:
    """Feature ids referenced by the stored analysis payload(s), grouped by
    layer. A run with no engine findings (a clean analysis) still stores its
    layer geometry in the payload, so those features' full records — and their
    measurements — are retrievable instead of missing.
    """
    found: dict[str, list[str]] = {}
    for rec in records or []:
        payload = rec.get("result") if isinstance(rec, dict) else None
        if not isinstance(payload, dict):
            continue
        default_layer = str(payload.get("layer_name") or "")
        for layer, fid in _iter_payload_ids(payload, default_layer):
            ids = found.setdefault(layer, [])
            if fid not in ids and len(ids) < MAX_PAYLOAD_FEATURE_IDS_PER_LAYER:
                ids.append(fid)
    return {layer: ids for layer, ids in found.items() if layer}


def _collect_feature_data(repo: Repository, results: Sequence[ValidationResult],
                          analyses: Sequence[ErrorAnalysis],
                          analysis_records: Sequence[dict] = ()
                          ) -> tuple[dict, int]:
    """Complete data for every feature this run touches, grouped by id.

    Ids come from the validation results, the related features recorded by the
    agent, the ids mentioned inside finding details, and the features stored in
    the analysis payload itself — so a question about "the other building" or
    about a clean run's street reaches that feature's full record as well.
    """
    wanted: dict[str, list[str]] = {}
    for r in results:
        if r.feature_id:
            wanted.setdefault(r.layer_name, []).append(str(r.feature_id))
    for a in analyses:
        for fid in (a.related_features or []):
            wanted.setdefault(a.layer_name, []).append(str(fid))
    for layer in list(wanted):
        wanted[layer].extend(_related_ids_from_details(results, layer))
    for layer, ids in _payload_feature_ids(analysis_records).items():
        wanted.setdefault(layer, []).extend(ids)

    feature_data: dict[str, dict] = {}
    omitted = 0
    for layer, ids in wanted.items():
        unique = list(dict.fromkeys(ids))
        recs = fetch_feature_records(repo, layer, unique)
        for fid, rec in recs.items():
            if len(feature_data) >= MAX_FEATURE_RECORDS:
                omitted += 1
                continue
            rec = dict(rec)
            rec.setdefault("feature_id", fid)
            rec.setdefault("layer_name", layer)
            feature_data[fid] = rec
    return feature_data, omitted


# ── dynamic field index ─────────────────────────────────────────────────────
RECORD_SOFT_LIMIT_CHARS = 8_000


def compact_record(record: dict,
                   soft_limit: int = RECORD_SOFT_LIMIT_CHARS) -> dict:
    """Bound ONE feature record for a prompt without dropping any field.

    A per-group generation prompt carries up to 25 records; a feature with a
    very complex geometry could otherwise dominate (or blow) the prompt. Keys
    always survive (they are the analysis fields) — only oversized lists (long
    coordinate rings) and strings are shortened, with an explicit marker.
    Records under the limit pass through untouched.
    """
    if not isinstance(record, dict) or len(_serialize(record)) <= soft_limit:
        return record
    for list_cap, str_cap in ((200, 2000), (60, 600), (10, 200), (1, 80)):
        candidate = _shrink(record, list_cap, str_cap)
        if len(_serialize(candidate)) <= soft_limit:
            return candidate
    return _shrink(record, 1, 80)


def _walk_fields(value: Any, context: str, out: dict[str, dict],
                 depth: int = 0) -> None:
    """Record every leaf/object key found in the data with an example value
    and where it was seen. Names are discovered, never declared."""
    if depth > 8 or len(out) > MAX_FIELD_ENTRIES * 4:
        return
    if isinstance(value, dict):
        for key, child in value.items():
            name = str(key)
            entry = out.setdefault(name, {"example": None, "type": "", "found_in": []})
            if context not in entry["found_in"] and len(entry["found_in"]) < MAX_FIELD_CONTEXTS:
                entry["found_in"].append(context)
            if isinstance(child, (dict, list, tuple)):
                if not entry["type"]:
                    entry["type"] = ("object" if isinstance(child, dict) else "array")
            else:
                if not entry["type"]:
                    entry["type"] = type(child).__name__
                if entry["example"] is None and child is not None:
                    entry["example"] = child
            _walk_fields(child, context, out, depth + 1)
    elif isinstance(value, (list, tuple)):
        for child in list(value)[:3]:
            _walk_fields(child, context, out, depth + 1)


def available_fields(dataset: dict) -> dict[str, dict]:
    """Index of every field name present in the analysis data.

    ``{"street_length": {"example": 120.5, "type": "float",
    "found_in": ["feature:RD_101", "analysis_record:0"]}, ...}``

    This is what lets the agent map a user's wording onto the project's real
    field names dynamically — a synonym is resolved from the data that is
    actually stored, not from a hard-coded map.
    """
    out: dict[str, dict] = {}
    for fid, rec in (dataset.get("feature_data") or {}).items():
        _walk_fields(rec, f"feature:{fid}", out)
    for i, rec in enumerate(dataset.get("analysis_records") or []):
        _walk_fields(rec, f"analysis_record:{i}", out)
    for i, finding in enumerate(dataset.get("findings") or []):
        _walk_fields(finding, f"finding:{i}", out)
    for i, analysis in enumerate(dataset.get("analyses") or []):
        _walk_fields(analysis, f"analysis:{i}", out)
    if len(out) > MAX_FIELD_ENTRIES:
        keep = sorted(out)[:MAX_FIELD_ENTRIES]
        out = {k: out[k] for k in keep}
    return {k: out[k] for k in sorted(out)}


def build_analysis_dataset(repo: Repository, run_id: str,
                           results: Optional[Sequence[ValidationResult]] = None,
                           analyses: Optional[Sequence[ErrorAnalysis]] = None,
                           records: Optional[Sequence[dict]] = None
                           ) -> dict:
    """Everything Meyaar stored for one analysis, unfiltered.

    Returns ``{run_id, analyses, findings, analysis_records, feature_data,
    available_fields, counts, truncation}``. ``results`` / ``analyses`` /
    ``records`` may be passed in when the caller already fetched them (avoids
    duplicate queries — used by the batch builder).
    """
    results = list(results) if results is not None else (
        _safe(repo.fetch_results, run_id) or [])
    analyses = list(analyses) if analyses is not None else (
        _safe(repo.fetch_analyses, run_id) or [])

    raw_records = ([dict(r) for r in records if isinstance(r, dict)]
                   if records is not None
                   else (_safe(repo.fetch_analysis_records, run_id) or []))
    records = [dict(r) for r in raw_records[:MAX_ANALYSIS_RECORDS]
               if isinstance(r, dict)]
    feature_data, omitted_features = _collect_feature_data(repo, results, analyses,
                                                          records)

    dataset: dict = {
        "run_id": run_id,
        "analyses": [a.model_dump() for a in analyses],
        "findings": [r.model_dump() for r in results],
        "analysis_records": records,
        "feature_data": feature_data,
        "counts": {
            "analyses": len(analyses),
            "findings": len(results),
            "analysis_records": len(records),
            "features": len(feature_data),
        },
    }
    truncation = {}
    if omitted_features:
        truncation["feature_data_omitted"] = omitted_features
    if len(raw_records) > len(records):
        truncation["analysis_records_omitted"] = len(raw_records) - len(records)
    if truncation:
        dataset["truncation"] = truncation
    dataset["available_fields"] = available_fields(dataset)
    return dataset


# ── upload BATCH (folder / multi-file selection) ────────────────────────────
MAX_BATCH_RUNS = 25

LIVE_LAYER_NOTE = (
    "Per-file analysis_records, findings and analyses are that run's immutable "
    "stored record. feature_data records are read from the LIVE layer tables, "
    "which hold only the most recently uploaded file's features, so a feature "
    "record describes the current layer state rather than a historical snapshot.")


def build_batch_analysis_dataset(repo: Repository, batch_id: str) -> dict:
    """Everything Meyaar stored for an upload BATCH (a folder / multi-file pick).

    Merges the per-file complete datasets into one record the chat can answer
    from: a ``files`` summary (one entry per file: stored errors, compliance
    score, layer and run), every finding, every agent analysis, every stored
    payload, and every feature record — namespaced ``"<filename>#<feature_id>"``
    so two files with the same feature id can never collide — plus a
    dynamically derived field index. Nothing is whitelisted.
    """
    fetcher = getattr(repo, "fetch_analysis_records_by_batch", None)
    raw = (_safe(fetcher, batch_id) or []) if callable(fetcher) else []
    records = [dict(r) for r in raw[:MAX_ANALYSIS_RECORDS] if isinstance(r, dict)]

    files: list[dict] = []
    analyses: list[dict] = []
    findings: list[dict] = []
    merged_records: list[dict] = []
    feature_data: dict[str, dict] = {}
    without_run = 0

    for record in records[:MAX_BATCH_RUNS]:
        payload = record.get("result") if isinstance(record.get("result"), dict) else {}
        run_id = record.get("run_id") or payload.get("run_id")
        filename = record.get("filename") or payload.get("filename")
        entry = {
            "filename": filename,
            "analysis_id": record.get("analysis_id"),
            "run_id": str(run_id) if run_id else None,
            "layer_name": payload.get("layer_name"),
            "status": record.get("status") or payload.get("status"),
            "compliance_score": record.get("compliance_score",
                                           payload.get("compliance_score")),
            "total_errors": record.get("total_errors", payload.get("total_errors")),
            "created_at": record.get("created_at"),
            "analyzed": 0,
            "findings": 0,
        }
        merged_records.append({**record, "batch_id": batch_id})
        if not run_id:
            without_run += 1          # e.g. a map image: no validation run
            files.append(entry)
            continue

        dataset = build_analysis_dataset(repo, str(run_id), records=[record])
        entry["analyzed"] = len(dataset["analyses"])
        entry["findings"] = len(dataset["findings"])
        for analysis in dataset["analyses"]:
            analyses.append({**analysis, "source_file": filename,
                             "source_run_id": str(run_id)})
        for finding in dataset["findings"]:
            findings.append({**finding, "source_file": filename,
                             "source_run_id": str(run_id)})
        for fid, feature in dataset["feature_data"].items():
            if len(feature_data) >= MAX_FEATURE_RECORDS:
                break
            feature_data[f"{filename}#{fid}"] = {
                **feature, "feature_id": fid, "source_file": filename,
                "source_run_id": str(run_id)}
        files.append(entry)

    dataset = {
        "batch_id": batch_id,
        "files": files,
        "analyses": analyses,
        "findings": findings,
        "analysis_records": merged_records,
        "feature_data": feature_data,
        "counts": {
            "files": len(files),
            "files_with_a_run": len(files) - without_run,
            "analyses": len(analyses),
            "findings": len(findings),
            "features": len(feature_data),
        },
        "notes": [LIVE_LAYER_NOTE],
    }
    if len(raw) > len(records):
        dataset["truncation"] = {"files_omitted": len(raw) - len(records)}
    dataset["available_fields"] = available_fields(dataset)
    return dataset


# ── the caller's other uploads (cross-upload questions) ─────────────────────
MAX_RECENT_UPLOADS = 10        # uploads listed in the chat context
MAX_RECENT_FILENAMES = 12      # file names kept per upload (the count stays exact)

RECENT_UPLOADS_NOTE = (
    "These are the caller's own recent uploads, newest first; 'files' is how "
    "many files that one upload selection contained and 'filenames' lists them "
    "(truncated names still have the exact count in 'files'). The upload being "
    "discussed now is marked \"is_current\": \"the previous batch\", \"my last "
    "upload\" and 'the one before' mean the entry listed AFTER it in this list. "
    "Use these entries for questions about other uploads ('how many files was "
    "the previous batch?', 'compare this batch with the last one', 'which of my "
    "uploads had the most errors?') and state their numbers exactly as listed. "
    "Uploads not listed here — including other users' uploads, which are never "
    "listed — are not available; say so instead of guessing. "
    "'unbatched_analyses' counts older analyses saved before uploads were "
    "grouped; they are individual files, not batches.")


def recent_uploads_summary(repo: Repository, viewer: Optional[dict] = None,
                           current_scope_id: Optional[str] = None,
                           limit: int = MAX_RECENT_UPLOADS) -> dict:
    """The caller's recent uploads, shaped for the chat prompt.

    Only the caller's own uploads (or their team's, if they manage/lead it) are
    ever included — see Repository.fetch_recent_upload_batches. Bounded by
    ``limit`` uploads and ``MAX_RECENT_FILENAMES`` names each, because a chat
    prompt must stay affordable; the per-upload file COUNT is always exact, so
    "how many files was the previous batch?" is answered from the real number.
    Returns {"available": False, ...} when there is no upload history to show.
    """
    data = _safe(repo.fetch_recent_upload_batches, viewer, limit) or {}
    raw_uploads = data.get("uploads")
    uploads: list[dict] = []
    for row in (raw_uploads or [])[:limit]:
        if not isinstance(row, dict):
            continue
        names = [str(n) for n in (row.get("filenames") or []) if n]
        entry = {
            "batch_id": str(row.get("batch_id")),
            "uploaded_at": row.get("uploaded_at"),
            "files": int(row.get("files") or len(names)),
            "filenames": names[:MAX_RECENT_FILENAMES],
            "total_errors": row.get("total_errors"),
        }
        if len(names) > MAX_RECENT_FILENAMES:
            entry["filenames_truncated"] = len(names) - MAX_RECENT_FILENAMES
        layers = [str(l) for l in (row.get("layers") or []) if l]
        if layers:
            entry["layers"] = layers
        if current_scope_id and entry["batch_id"] == str(current_scope_id):
            entry["is_current"] = True
        uploads.append(entry)

    unbatched = int(data.get("unbatched_analyses") or 0)
    summary = {
        "available": bool(uploads or unbatched or data.get("total_uploads")),
        "uploads": uploads,
        "unbatched_analyses": unbatched,
        "total_uploads": int(data.get("total_uploads") or len(uploads)),
        "note": RECENT_UPLOADS_NOTE,
    }
    if not uploads:
        summary["uploads_note"] = (
            "No earlier uploads are stored for this caller: nothing can be said "
            "about a previous batch beyond what the current context holds.")
    return summary
