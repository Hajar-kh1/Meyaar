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
                           analyses: Optional[Sequence[ErrorAnalysis]] = None
                           ) -> dict:
    """Everything Meyaar stored for one analysis, unfiltered.

    Returns ``{run_id, analyses, findings, analysis_records, feature_data,
    available_fields, counts, truncation}``. ``results`` / ``analyses`` may be
    passed in when the caller already fetched them (avoids a second query).
    """
    results = list(results) if results is not None else (
        _safe(repo.fetch_results, run_id) or [])
    analyses = list(analyses) if analyses is not None else (
        _safe(repo.fetch_analyses, run_id) or [])

    raw_records = _safe(repo.fetch_analysis_records, run_id) or []
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
