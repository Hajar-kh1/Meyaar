"""Complete-analysis retrieval tests.

Requirement under test: when a user asks about an analysis, the agent must use
ALL the information stored for that analysis — not the headline summary and not
a fixed list of fields. So these tests cover:

  1. the whole saved analysis payload (every key) reaching the chat context,
  2. the complete per-feature record (every attribute + PostGIS measurement),
  3. questions about street length/width, building length/width, plot
     dimensions, and several properties at once being answered with the stored
     values,
  4. broad requests ("show me everything about the building") returning a
     structured summary of all meaningful fields,
  5. absent information being reported as unavailable instead of invented,
  6. retrieval staying isolated to the correct run,
  7. the existing chat/analysis contract and the graceful degradation paths.

The language model is exercised through ``QueryLLM``: a deterministic
stand-in that reads the grounded context out of the prompt and resolves the
question against the field names that are actually present — exactly what the
system prompt instructs the real model to do — so the end-to-end answer path
(retrieve -> context -> prompt -> answer) is verified without an LLM key.
"""
from __future__ import annotations

import json
import re

import pytest

from agent.chat import answer_question, build_chat_context
from agent.db.memory import InMemoryRepository
from agent.graph.builder import run_analysis
from agent.retrieval import build_analysis_dataset
from agent.tests.conftest import MISSING_RUN_ID, RUN_ID, StubLLM, build_memory_repo
from agent.tools import get_analysis_record, get_feature_record, list_analysis_fields

# ── realistic stored data (dimension fields a Saudi GIS analysis holds) ──────
STREET_RECORD = {
    "feature_id": "RD_101", "layer_name": "roads",
    "geometry_type": "LineString", "srid": 4326, "is_valid": True, "is_empty": False,
    "length_m": 842.6, "street_length": 842.6, "street_width": 7.5,
    "surface": "asphalt", "lanes": 2, "vertex_count": 214,
    "centroid": "POINT(46.68 24.66)",
    "x_min": 46.60, "y_min": 24.60, "x_max": 46.70, "y_max": 24.70,
}

BUILDING_RECORD = {
    "feature_id": "BLD_102", "layer_name": "buildings",
    "geometry_type": "Polygon", "srid": 4326, "is_valid": True, "is_empty": False,
    "area_m2": 218.4, "building_length": 18.2, "building_width": 12.0,
    "building_area": 218.4, "building_coverage": 50.5,
    "height_m": 7.4, "floors": 2, "name": "Villa 12", "vertex_count": 32,
    "centroid": "POINT(46.701 24.601)",
    "x_min": 46.700, "y_min": 24.600, "x_max": 46.702, "y_max": 24.602,
}

# The saved analysis payload (public.saved_analyses.result_payload). This is
# the complete JSON the vector pipeline stores — the agent must receive all of
# it, so a field added by a later pipeline version needs no code change here.
ANALYSIS_PAYLOAD = {
    "run_id": RUN_ID,
    "filename": "riyadh_plots.geojson",
    "status": "completed",
    "layer_name": "roads",
    "compliance_score": 92.5,
    "total_errors": 14,
    "insertion": {"inserted_rows": 118, "crs": "EPSG:4326",
                  "geometry_types": ["LineString"]},
    "quality_before": {"quality_score": 74.0, "error_rate": 12.5,
                       "total_features": 118},
    "quality_after": {"quality_score": 92.5, "error_rate": 3.2,
                      "total_features": 118},
    "measurements": {
        "street_length": 842.6,
        "street_width": 7.5,
        "building_length": 18.2,
        "building_width": 12.0,
        "building_area": 218.4,
        "plot_length": 24.0,
        "plot_width": 18.0,
        "plot_area": 432.0,
        "building_coverage": 50.5,
        "setbacks": {"front": 3.0, "side": 1.5, "rear": 2.0},
        "distances": {"to_nearest_building": 4.2, "to_road_centreline": 9.8},
        "coordinates": {"centroid": [46.701, 24.601],
                        "bbox": [46.7, 24.6, 46.702, 24.602]},
        "counts": {"buildings": 62, "roads": 56, "vertices": 1840},
    },
    "layer_geojson": {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"feature_id": "RD_101"},
            "geometry": {"type": "LineString",
                         "coordinates": [[46.6, 24.6], [46.7, 24.7]]},
        }],
    },
    # A metric introduced by a LATER pipeline version: it must flow through the
    # dynamic retrieval without touching agent code.
    "future_metric_added_later": {"new_ratio": 0.42,
                                  "note": "added by a later pipeline version"},
}


def _seed_analysis(repo, run_id: str = RUN_ID, payload: dict | None = None) -> None:
    """Run the analysis workflow and store the complete analysis payload."""
    run_analysis(run_id, repository=repo)
    repo.seed_analysis_record(run_id, dict(payload or ANALYSIS_PAYLOAD))


@pytest.fixture()
def rich_repo():
    repo = build_memory_repo()
    repo.seed_feature("roads", "RD_101", dict(STREET_RECORD))
    repo.seed_feature("buildings", "BLD_102", dict(BUILDING_RECORD))
    repo.seed_feature("buildings", "BLD_157", {
        "feature_id": "BLD_157", "layer_name": "buildings",
        "geometry_type": "Polygon", "srid": 4326, "area_m2": 248.7,
        "building_length": 20.0, "building_width": 12.4, "vertex_count": 32,
        "centroid": "POINT(46.701 24.601)",
        "x_min": 46.700, "y_min": 24.600, "x_max": 46.702, "y_max": 24.602,
    })
    _seed_analysis(repo)
    return repo


# ── deterministic stand-in for the chat model ───────────────────────────────
GENERIC_WORDS = {"dimension", "dimensions", "measurement", "measurements",
                 "size", "sizes", "properties", "values"}
BROAD_WORDS = {"all", "everything", "every", "details", "detail", "summary",
               "information", "list", "show"}


def _flatten(value, prefix: str = "", out: dict | None = None) -> dict:
    """{dotted path: scalar value} for every scalar in a JSON-ish structure."""
    out = {} if out is None else out
    if isinstance(value, dict):
        for key, child in value.items():
            _flatten(child, f"{prefix}.{key}" if prefix else str(key), out)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _flatten(child, f"{prefix}[{index}]", out)
    else:
        out[prefix] = value
    return out


def _words(text: str) -> set:
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if w}


def _candidate_names(path: str) -> list[set]:
    """The field name and its container name, from a flattened path
    ("a.result.measurements.plot_width" -> [{plot,width}, {measurements}])."""
    parts = [re.sub(r"\[\d+\]", "", part) for part in path.split(".")]
    names = [parts[-1]]
    if len(parts) > 1:
        names.append(parts[-2])
    return [_words(name) for name in names if name]


def _field_matches(path: str, words: set) -> bool:
    """Map a question's wording onto a stored field name (e.g. 'street length'
    or 'plot dimensions' onto street_length / plot_length, 'coordinates' onto
    the stored coordinate container)."""
    for name_words in _candidate_names(path):
        if not name_words:
            continue
        if name_words <= words:
            return True
        if (name_words & words) and (words & GENERIC_WORDS):
            return True
    return False


class QueryLLM:
    """Reads the grounded context out of the prompt and answers from it.

    Mirrors the instructions given to the real model: resolve the question
    against the field names actually stored, answer with the stored values,
    and say the value is not available when nothing matches.
    """

    def __init__(self):
        self.prompts: list[str] = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        payload = prompt.split("Context (JSON): ", 1)[1]
        context = json.loads(payload.split("\n\nUser question:")[0])
        question = prompt.split("User question: ", 1)[1].split("\n\nReply STRICT JSON")[0]
        flat = _flatten(context)
        words = _words(question)
        broad = bool(words & BROAD_WORDS) and len(words) <= 6

        if broad:
            picks = flat
        else:
            picks = {path: value for path, value in flat.items()
                     if _field_matches(path, words)}

        if not picks:
            answer = ("That information is not available in this analysis.")
        else:
            answer = "; ".join(
                f"{path.split('.')[-1].split('[')[0]} = {value}"
                for path, value in sorted(picks.items()))
        return type("R", (), {"content": json.dumps(
            {"answer": answer, "sources": []}, default=str)})()


def _ask(repo, question: str, run_id: str = RUN_ID) -> tuple[str, str]:
    llm = QueryLLM()
    out = answer_question(repo, run_id, question, llm=llm)
    return out["answer"], llm.prompts[0]


# ── 1. the complete stored analysis reaches the context and the prompt ──────
def test_context_carries_the_whole_stored_payload(rich_repo):
    ctx = build_chat_context(rich_repo, RUN_ID)
    assert len(ctx["analysis_records"]) == 1
    record = ctx["analysis_records"][0]
    stored = record["result"]

    # No whitelist: every stored key is present, nothing was extracted.
    assert set(stored) == set(ANALYSIS_PAYLOAD)
    assert stored["measurements"]["street_length"] == 842.6
    assert stored["measurements"]["plot_width"] == 18.0
    assert stored["measurements"]["setbacks"]["rear"] == 2.0
    assert stored["future_metric_added_later"]["new_ratio"] == 0.42
    # Analysis metadata travels with the payload.
    assert record["filename"] == "riyadh_plots.geojson"
    assert record["total_errors"] == 14
    assert record["analysis_id"]


def test_prompt_contains_every_stored_field(rich_repo):
    _, prompt = _ask(rich_repo, "give me all the analysis information")
    for token in ("street_length", "street_width", "building_length",
                  "building_width", "building_area", "plot_length",
                  "plot_width", "plot_area", "building_coverage", "setbacks",
                  "future_metric_added_later", "842.6", "0.42"):
        assert token in prompt, token


def test_complete_feature_records_include_every_attribute(rich_repo):
    ctx = build_chat_context(rich_repo, RUN_ID)
    road = ctx["feature_data"]["RD_101"]
    assert road["length_m"] == 842.6          # computed measurement
    assert road["street_length"] == 842.6
    assert road["street_width"] == 7.5
    assert road["surface"] == "asphalt"       # ordinary layer attribute
    assert road["lanes"] == 2
    assert road["vertex_count"] == 214
    assert road["bbox"] == [46.60, 24.60, 46.70, 24.70]
    building = ctx["feature_data"]["BLD_102"]
    assert building["building_length"] == 18.2
    assert building["building_width"] == 12.0
    assert building["name"] == "Villa 12"
    assert building["floors"] == 2
    # A feature merely mentioned inside a finding's details is retrieved too.
    assert "BLD_157" in ctx["feature_data"]


def test_available_fields_index_is_built_from_the_data(rich_repo):
    ctx = build_chat_context(rich_repo, RUN_ID)
    index = ctx["available_fields"]
    for name in ("street_length", "plot_area", "setbacks", "front",
                 "future_metric_added_later", "new_ratio", "lanes"):
        assert name in index, name
    assert index["plot_area"]["example"] == 432.0
    assert any(entry.startswith("feature:") or entry.startswith("analysis_record:")
               for entry in index["street_width"]["found_in"])


# ── 2. questions answered from the stored values ────────────────────────────
def test_street_length_question_gets_the_stored_value(rich_repo):
    answer, _ = _ask(rich_repo, "What is the street length?")
    assert "842.6" in answer


def test_street_width_question_gets_the_stored_value(rich_repo):
    answer, _ = _ask(rich_repo, "What is the street width?")
    assert "7.5" in answer


def test_building_length_and_width_question_gets_both(rich_repo):
    answer, _ = _ask(rich_repo, "What are the building length and width?")
    assert "18.2" in answer
    assert "12.0" in answer


def test_plot_dimensions_question_gets_both_dimensions(rich_repo):
    answer, _ = _ask(rich_repo, "What are the plot dimensions?")
    assert "24.0" in answer          # plot_length
    assert "18.0" in answer          # plot_width


def test_multiple_properties_in_one_question(rich_repo):
    answer, _ = _ask(rich_repo,
                     "give me the street length, building area and plot area")
    assert "842.6" in answer
    assert "218.4" in answer
    assert "432.0" in answer


def test_question_about_coordinates_and_counts(rich_repo):
    answer, _ = _ask(rich_repo, "what are the coordinates and counts of the building?")
    assert "46.701" in answer        # stored coordinate value, unchanged
    assert "62" in answer            # buildings count


# ── 3. broad requests summarise every meaningful field ──────────────────────
def test_broad_analysis_summary_covers_every_meaningful_field(rich_repo):
    answer, _ = _ask(rich_repo, "give me all the analysis information")
    payload_fields = _flatten(ANALYSIS_PAYLOAD)
    missing = [path for path, value in payload_fields.items()
               if f"{path.split('.')[-1].split('[')[0]} = {value}" not in answer]
    assert not missing, missing


def test_broad_request_about_the_building_returns_its_measurements(rich_repo):
    answer, _ = _ask(rich_repo, "show me everything about the building")
    for token in ("18.2", "12.0", "218.4", "50.5", "Villa 12"):
        assert token in answer, token


# ── 4. absent information is reported, never invented ──────────────────────
def test_missing_field_is_reported_as_unavailable(rich_repo):
    answer, prompt = _ask(rich_repo, "what is the groundwater depth of the plot?")
    assert "not available" in answer.lower()
    # ...and the retrieved data really has no such field (nothing to invent):
    # only the echoed user question mentions it.
    context_block = prompt.split("\n\nUser question: ")[0]
    assert "groundwater" not in context_block.lower()
    assert not re.search(r"\d", answer)


def test_unavailable_saved_analysis_store_degrades_gracefully(rich_repo):
    def boom(run_id):
        raise RuntimeError("relation public.saved_analyses does not exist")

    rich_repo.fetch_analysis_records = boom
    ctx = build_chat_context(rich_repo, RUN_ID)
    assert ctx["analysis_records"] == []          # reported, not fabricated
    assert ctx["feature_data"]                    # other data still retrieved
    stub = StubLLM(json.dumps({"answer": "still answers", "sources": []}))
    out = answer_question(rich_repo, RUN_ID, "street width?", llm=stub)
    assert out["answer"] == "still answers"


# ── clean runs: features referenced only by the stored payload ──────────────
def test_features_referenced_only_by_the_payload_are_measured():
    """A run with no engine findings still stores its layer geometry in the
    payload; those features' complete records (with measurements) must be
    retrievable, otherwise 'what is the street length?' fails on a clean run."""
    repo = InMemoryRepository()
    repo.seed_feature("roads", "RD_101", dict(STREET_RECORD))
    run_analysis(RUN_ID, repository=repo)            # clean run: summary only
    repo.seed_analysis_record(RUN_ID, {
        "run_id": RUN_ID, "filename": "clean.geojson", "status": "completed",
        "layer_name": "roads", "compliance_score": 100.0,
        "layer_geojson": {
            "type": "FeatureCollection",
            "features": [{"type": "Feature",
                          "properties": {"feature_id": "RD_101"},
                          "geometry": {"type": "LineString",
                                       "coordinates": [[46.6, 24.6], [46.7, 24.7]]}}],
        },
    })
    ctx = build_chat_context(repo, RUN_ID)
    assert ctx["feature_data"]["RD_101"]["street_length"] == 842.6
    assert ctx["feature_data"]["RD_101"]["length_m"] == 842.6
    answer, _ = _ask(repo, "what is the street length?")
    assert "842.6" in answer


# ── 6. retrieval is scoped to the correct run ───────────────────────────────
def _dual_run_repo() -> InMemoryRepository:
    """One repository holding two independent runs with distinct values."""
    from agent.core.models import ValidationResult
    rows_a = json.loads((__import__("pathlib").Path(__file__).parent /
                         "fixtures" / "sample_run.json").read_text(encoding="utf-8"))
    rows_b = json.loads((__import__("pathlib").Path(__file__).parent /
                         "fixtures" / "missing_context_run.json").read_text(encoding="utf-8"))
    results = [ValidationResult(**r) for r in rows_a + rows_b]
    repo = InMemoryRepository(results=results)
    repo.seed_feature("roads", "RD_101", dict(STREET_RECORD))
    repo.seed_feature("roads", "RD_777", {
        "feature_id": "RD_777", "layer_name": "roads",
        "geometry_type": "LineString", "srid": 4326,
        "length_m": 999.9, "street_length": 999.9, "street_width": 3.3,
    })
    run_analysis(RUN_ID, repository=repo)
    run_analysis(MISSING_RUN_ID, repository=repo)
    repo.seed_analysis_record(RUN_ID, dict(ANALYSIS_PAYLOAD),
                              analysis_id="analysis-a")
    repo.seed_analysis_record(MISSING_RUN_ID, {
        "run_id": MISSING_RUN_ID, "filename": "other.geojson",
        "status": "completed", "compliance_score": 61.0,
        "measurements": {"street_length": 111.1, "street_width": 2.2},
    }, analysis_id="analysis-b")
    return repo


def test_each_run_sees_only_its_own_analysis_data():
    repo = _dual_run_repo()
    ctx_a = build_chat_context(repo, RUN_ID)
    ctx_b = build_chat_context(repo, MISSING_RUN_ID)

    blob_a = json.dumps(ctx_a, default=str)
    blob_b = json.dumps(ctx_b, default=str)

    assert ctx_a["analysis_records"][0]["result"]["measurements"]["street_length"] == 842.6
    assert ctx_b["analysis_records"][0]["result"]["measurements"]["street_length"] == 111.1
    assert "111.1" not in blob_a          # run B's value never leaks into A
    assert "842.6" not in blob_b          # ...nor A's into B
    assert "RD_777" not in ctx_a["feature_data"]
    assert "RD_101" not in ctx_b["feature_data"]
    assert ctx_a["total_analyses"] == 14 and ctx_b["total_analyses"] == 2


def test_feature_lookup_is_scoped_by_layer(rich_repo):
    """A missing feature is absent, never borrowed from another layer."""
    assert get_feature_record(rich_repo, "roads", "BLD_102") is None
    assert get_feature_record(rich_repo, "buildings", "BLD_102") is not None


# ── 7. tools expose the same complete data ─────────────────────────────────
def test_get_analysis_record_tool_returns_the_complete_dataset(rich_repo):
    dataset = get_analysis_record(rich_repo, RUN_ID)
    assert set(dataset["analysis_records"][0]["result"]) == set(ANALYSIS_PAYLOAD)
    assert dataset["counts"]["features"] >= 3
    assert dataset["findings"] and dataset["analyses"]
    assert "street_length" in dataset["available_fields"]


def test_get_feature_record_tool_returns_all_attributes(rich_repo):
    road = get_feature_record(rich_repo, "roads", "RD_101")
    assert road["street_width"] == 7.5 and road["lanes"] == 2
    assert road["length_m"] == 842.6


def test_list_analysis_fields_tool_indexes_stored_fields(rich_repo):
    index = list_analysis_fields(rich_repo, RUN_ID)
    assert set(index) >= {"street_length", "plot_area", "building_coverage",
                          "future_metric_added_later"}
    assert index["street_length"]["example"] == 842.6


# ── 8. existing chat behaviour stays intact ────────────────────────────────
def test_existing_context_contract_unchanged(rich_repo):
    ctx = build_chat_context(rich_repo, RUN_ID)
    assert ctx["run_id"] == RUN_ID
    assert ctx["summary"]["total_errors"] == 14
    assert len(ctx["analyses"]) == 14
    assert ctx["rules"]["RD001"]["type"] == "heuristic"
    assert ctx["remediation"]["summary"]["auto_fixed"] == 2
    assert ctx["context_chars"] and isinstance(ctx["context_truncated"], bool)


def test_sources_filtering_still_applies_with_complete_data(rich_repo):
    stub = StubLLM(json.dumps({"answer": "answer",
                               "sources": ["BLD001", "GHOST_9"]}))
    out = answer_question(rich_repo, RUN_ID, "q", llm=stub)
    assert out["sources"] == ["BLD001"]


# ── 9. API surface for the complete record ─────────────────────────────────
@pytest.fixture()
def client(rich_repo, monkeypatch):
    import contextlib

    from fastapi.testclient import TestClient

    from agent.api import router as api_router
    from agent.api.app import app

    class _FakeEngine:
        def begin(self):
            return contextlib.nullcontext(None)

    app.dependency_overrides[api_router.get_repository] = lambda: rich_repo
    app.dependency_overrides[api_router.current_user] = lambda: {
        "user_id": "00000000-0000-4000-8000-000000000001", "role": "admin"}
    monkeypatch.setattr(api_router, "database_engine", lambda: _FakeEngine())
    monkeypatch.setattr(api_router, "ensure_app_tables", lambda conn: None)
    monkeypatch.setattr(api_router, "require_run_access",
                        lambda conn, user, run_id: None)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_record_endpoint_returns_every_stored_field(client):
    resp = client.get(f"/api/validation/{RUN_ID}/record")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == RUN_ID
    assert set(body["analysis_records"][0]["result"]) == set(ANALYSIS_PAYLOAD)
    assert body["feature_data"]["RD_101"]["street_width"] == 7.5
    assert "plot_area" in body["available_fields"]
    assert body["counts"]["findings"] == 14


def test_record_endpoint_404_without_analysis(client, empty_repo):
    from agent.api import router as api_router
    from agent.api.app import app
    app.dependency_overrides[api_router.get_repository] = lambda: empty_repo
    resp = client.get(f"/api/validation/{RUN_ID}/record")
    assert resp.status_code == 404


def test_chat_endpoint_answers_dimension_question(client, monkeypatch):
    import agent.chat as chat_mod
    monkeypatch.setattr(chat_mod, "get_llm", lambda: QueryLLM())
    resp = client.post(f"/api/validation/{RUN_ID}/chat",
                       json={"question": "what is the street width?"})
    assert resp.status_code == 200
    assert "7.5" in resp.json()["answer"]
