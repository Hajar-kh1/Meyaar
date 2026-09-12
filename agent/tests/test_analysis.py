"""End-to-end graph tests: heuristic classification, missing context,
batch runs, DB failures, malformed/lying LLM output."""
from __future__ import annotations

import json

import pytest

from agent.graph.builder import run_analysis
from agent.tests.conftest import (
    MISSING_RUN_ID,
    RUN_ID,
    StubLLM,
    build_memory_repo,
)


# ── template path (no LLM configured in CI) ─────────────────────────────────
def test_full_run_all_rules_template_path(repo, sample_analyses_expected):
    out = run_analysis(RUN_ID, repository=repo)
    assert out["results_loaded"] == 14
    assert len(out["analyses"]) == 14
    assert out["errors"] == []

    by_rule = {a["rule_id"]: a for a in out["analyses"]}
    assert set(by_rule) == set(sample_analyses_expected)
    for rule_id, (status, review, related) in sample_analyses_expected.items():
        a = by_rule[rule_id]
        assert a["status"] == status, rule_id
        assert a["human_review_required"] is review, rule_id
        assert a["related_features"] == related, rule_id
        assert a["severity"] != ""          # severity preserved from engine
    # Analyses were persisted
    assert len(repo.fetch_analyses(RUN_ID)) == 14


def test_severity_preserved_from_source(repo):
    out = run_analysis(RUN_ID, repository=repo)
    src = {r.result_id: r.severity for r in repo.fetch_results(RUN_ID)}
    for a in out["analyses"]:
        assert a["severity"] == src[a["result_id"]]


def test_bld001_explanation_is_grounded(repo):
    out = run_analysis(RUN_ID, repository=repo)
    a = next(x for x in out["analyses"] if x["rule_id"] == "BLD001")
    # echoes engine details (area value) but must not invent other numbers
    assert "34.52" in a["explanation"]
    assert "BLD_157" in a["explanation"]
    assert a["feature_id"] == "BLD_102"
    assert a["status"] == "confirmed"
    assert a["human_review_required"] is False


def test_heuristic_rows_are_candidates_and_persisted(repo):
    out = run_analysis(RUN_ID, repository=repo)
    cand = [a for a in out["analyses"] if a["status"] == "candidate"]
    assert {a["rule_id"] for a in cand} == {"RD001", "RD002"}
    for a in cand:
        assert a["human_review_required"] is True
        assert "candidate" in a["explanation"].lower() or "review" in a["explanation"].lower()


def test_missing_feature_context_returns_insufficient(repo):
    # Seed run with results whose features + details are absent.
    repo2 = build_memory_repo(results_file="missing_context_run.json",
                              run_id=MISSING_RUN_ID)
    out = run_analysis(MISSING_RUN_ID, repository=repo2)
    assert len(out["analyses"]) == 2
    by_rule = {a["rule_id"]: a for a in out["analyses"]}
    # Deterministic rule with no info -> insufficient_context
    assert by_rule["BLD002"]["status"] == "insufficient_context"
    assert by_rule["BLD002"]["insufficient_context"] is True
    # Heuristic rule with no info -> still a candidate (must be reviewed),
    # but explicitly flagged as having insufficient context to explain.
    assert by_rule["RD002"]["status"] == "candidate"
    assert by_rule["RD002"]["insufficient_context"] is True
    assert by_rule["RD002"]["human_review_required"] is True
    for a in out["analyses"]:
        assert "no details" in a["explanation"] or "not available" in a["explanation"]


def test_unknown_rule_is_informational(repo):
    from agent.core.models import ValidationResult
    from agent.db.memory import InMemoryRepository
    repo2 = InMemoryRepository(results=[
        ValidationResult(result_id=501, run_id=MISSING_RUN_ID, layer_name="roads",
                         feature_id="R_1", rule_id="ZZZ999", error_type="Mystery",
                         severity="high", details="something happened")])
    out = run_analysis(MISSING_RUN_ID, repository=repo2)
    assert out["analyses"][0]["status"] == "informational"
    assert out["analyses"][0]["human_review_required"] is False


def test_empty_run_summarizes_zero(empty_repo):
    out = run_analysis(RUN_ID, repository=empty_repo)
    assert out["results_loaded"] == 0
    assert out["analyses"] == []
    assert out["summary"]["total_errors"] == 0
    assert out["summary"]["critical_errors"] == 0


def test_summary_counts_and_priority(empty_repo, repo):
    out = run_analysis(RUN_ID, repository=repo)
    s = out["summary"]
    assert s["total_errors"] == 14
    assert s["critical_errors"] == 4   # BLD004, RD005, GIS001, GIS002
    assert s["high_errors"] == 6
    assert s["medium_errors"] == 4
    assert s["most_common_error"] in {  # several rules tied at 1 -> any is fine
        "Building Overlap", "Duplicate Buildings", "Invalid Geometry",
        "Missing Geometry", "Road Overshoot", "Road Undershoot",
        "Duplicate Roads", "Missing/Wrong CRS", "Invalid Coordinates",
        "Missing Required Attributes", "Wrong Data Type",
        "Invalid Attribute Values"}
    assert s["counts_by_rule"]["BLD001"] == 1
    assert s["counts_by_layer"]["roads"] == 5
    assert any("human review" in a.lower() for a in s["priority_actions"])
    assert any("critical" in a.lower() for a in s["priority_actions"])


# ── executive narrative (saved per run at the end of the workflow) ──────────
def test_template_narrative_is_saved_and_grounded(repo):
    out = run_analysis(RUN_ID, repository=repo)
    narrative = out["summary"]["narrative"]
    assert narrative and "14 error" in narrative
    assert "4 critical, 6 high, 4 medium" in narrative   # severity counts correct
    # each error group is enumerated (rule names + layer qualifier)
    assert "Findings: " in narrative
    assert "1 Building Overlap (buildings)" in narrative
    assert "1 Missing Geometry (buildings)" in narrative
    assert "1 Missing Geometry (roads)" in narrative
    assert "1 Road Overshoot (roads)" in narrative
    # remediation outcome is part of the narrative (2 auto-fixed geometry
    # repairs, 7 human-review, 5 no-action on the fixture run)
    assert "2 automatically fixed" in narrative
    assert "7 queued for human review" in narrative
    assert "5 required no action" in narrative
    stored = repo.fetch_run_summary(RUN_ID)
    assert stored is not None
    assert stored["narrative"] == narrative
    assert stored["counts"]["remediation"]["auto_fixed"] == 2
    assert stored["counts"]["errors"]["total_errors"] == 14


def test_clean_run_saves_no_error_narrative(empty_repo):
    out = run_analysis(RUN_ID, repository=empty_repo)
    assert "no errors" in out["summary"]["narrative"]
    stored = empty_repo.fetch_run_summary(RUN_ID)
    assert stored is not None
    assert stored["counts"]["errors"]["total_errors"] == 0


def test_llm_narrative_used_when_returned(repo):
    prose = ("This validation run identified 14 quality issues across "
             "building, road and general layers; two invalid geometries "
             "were repaired automatically and the remaining findings "
             "require human review.")
    out = run_analysis(RUN_ID, repository=repo, llm=StubLLM(prose))
    assert out["summary"]["narrative"] == prose


def test_json_output_rejected_as_narrative(repo):
    # An LLM that answers JSON (as in the analyze step) must NOT become the
    # narrative — the deterministic template takes over.
    payload = json.dumps([{"result_id": 1, "status": "confirmed"}])
    out = run_analysis(RUN_ID, repository=repo, llm=StubLLM(payload))
    assert out["summary"]["narrative"].startswith("Validation run")
    assert "error" in out["summary"]["narrative"]


# ── database failure handling ───────────────────────────────────────────────
class FailingRepo:
    """Repository that blows up on reads (simulated DB outage)."""

    def fetch_results(self, *a, **k):
        raise RuntimeError("connection refused")

    def fetch_related_features(self, *a, **k):
        raise RuntimeError("connection refused")

    def fetch_feature_context(self, *a, **k):
        raise RuntimeError("connection refused")

    def query_readonly(self, *a, **k):
        raise RuntimeError("connection refused")

    def save_analyses(self, analyses):
        return len(analyses)

    def fetch_analyses(self, run_id):
        return []

    def build_summary(self, results, analyses):
        from agent.db.base import Repository
        return Repository.build_summary(self, results, analyses)

    def priority_actions(self, summary):
        from agent.db.base import Repository
        return Repository.priority_actions(self, summary)


def test_db_failure_logged_not_fatal():
    out = run_analysis(RUN_ID, repository=FailingRepo())
    assert out["results_loaded"] == 0
    assert any("fetch_results" in e for e in out["errors"])
    assert out["summary"]["total_errors"] == 0


# ── LLM path robustness ─────────────────────────────────────────────────────
def test_llm_garbage_falls_back_to_template(repo):
    stub = StubLLM("this is not json {{{")
    out = run_analysis(RUN_ID, repository=repo, llm=stub)
    assert stub.calls >= 1
    assert len(out["analyses"]) == 14
    # template fallback still yields valid statuses
    by_rule = {a["rule_id"]: a for a in out["analyses"]}
    assert by_rule["RD001"]["status"] == "candidate"
    assert by_rule["BLD001"]["status"] == "confirmed"


def test_llm_retries_then_falls_back(repo):
    stub = StubLLM("nonsense", fail_attempts=3)
    out = run_analysis(RUN_ID, repository=repo, llm=stub)
    assert out["analyses"]  # non-empty despite persistent LLM failure


def test_llm_invents_result_id_is_dropped(repo):
    # LLM returns an entry for result 999999 that does not exist + valid ones.
    payload = json.dumps([{
        "result_id": 999999, "status": "confirmed",
        "explanation": "invented", "cause": None,
        "recommendation": None, "human_review_required": False,
        "related_features": []}])
    stub = StubLLM(payload)
    out = run_analysis(RUN_ID, repository=repo, llm=stub)
    # inventing a result_id must not crash; per-item template fallback fills gaps
    assert all(a["result_id"] in {r.result_id for r in repo.fetch_results(RUN_ID)}
               for a in out["analyses"])


def test_llm_cannot_downgrade_heuristic_to_confirmed(repo):
    payload = json.dumps([{
        "result_id": 5, "status": "confirmed",  # RD001 must stay candidate
        "explanation": "LLM tried to confirm it",
        "cause": None, "recommendation": None,
        "human_review_required": False, "related_features": []}])
    stub = StubLLM(payload)
    out = run_analysis(RUN_ID, repository=repo, llm=stub)
    a = next(x for x in out["analyses"] if x["rule_id"] == "RD001")
    assert a["status"] == "candidate"
    assert a["human_review_required"] is True


def test_llm_valid_analysis_is_used(repo):
    payload = json.dumps([{
        "result_id": 1, "status": "confirmed",
        "explanation": "BLD_102 and BLD_157 intersect; verified from engine details.",
        "cause": "positive-area intersection",
        "recommendation": "snap boundaries to touch only",
        "human_review_required": False,
        "related_features": ["BLD_157"]}])
    stub = StubLLM(payload)
    out = run_analysis(RUN_ID, repository=repo, llm=stub)
    a = next(x for x in out["analyses"] if x["result_id"] == 1)
    assert a["explanation"].startswith("BLD_102 and BLD_157")
    assert a["cause"] == "positive-area intersection"
    # items the LLM did not cover fall back to templates
    assert len(out["analyses"]) == 14


def test_multiple_errors_one_run_grouped(repo):
    out = run_analysis(RUN_ID, repository=repo)
    analyze_traces = [t for t in out["trace"] if t.startswith("[analyze]")]
    # group = distinct (layer, rule); sample_run has 14 distinct rules
    assert len(analyze_traces) == 14
    assert all("template" in t for t in analyze_traces)


# ── complete feature records feeding the generation path ────────────────────
RICH_BUILDING = {
    "feature_id": "BLD_102", "layer_name": "buildings",
    "geometry_type": "Polygon", "srid": 4326, "is_valid": True, "is_empty": False,
    "area_m2": 248.7, "building_length": 18.2, "building_width": 12.0,
    "building_area": 248.7, "building_coverage": 50.5, "floors": 2,
    "name": "Villa 12", "vertex_count": 32,
    "centroid": "POINT(46.701 24.601)",
    "x_min": 46.700, "y_min": 24.600, "x_max": 46.702, "y_max": 24.602,
}


def _rich_repo():
    """Repo whose flagged building carries dimensions/attributes/measurements."""
    repo = build_memory_repo()
    repo.seed_feature("buildings", "BLD_102", dict(RICH_BUILDING))
    return repo


class _EmptyArrayLLM:
    """Valid JSON that analyses nothing -> per-item template fallback."""

    def __init__(self):
        self.prompts: list[str] = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return type("R", (), {"content": json.dumps([])})()


def test_group_prompt_receives_complete_feature_records():
    repo = _rich_repo()
    llm = _EmptyArrayLLM()
    run_analysis(RUN_ID, repository=repo, llm=llm)

    buildings_prompt = next(p for p in llm.prompts if '"layer":"buildings"' in p
                            or "Layer: buildings" in p)
    # every stored attribute/measurement is in the prompt, not a trimmed set
    for token in ("area_m2", "building_length", "building_width",
                  "building_coverage", "floors", "vertex_count", "bbox",
                  "248.7", "18.2", "50.5", "Villa 12"):
        assert token in buildings_prompt, token
    # the group prompt stays scoped to its own layer
    assert "RD_101" not in buildings_prompt


def test_template_explanation_cites_stored_measurements():
    out = run_analysis(RUN_ID, repository=_rich_repo())   # deterministic path
    bld001 = next(a for a in out["analyses"] if a["rule_id"] == "BLD001")
    explanation = bld001["explanation"]
    assert "Stored feature measurements:" in explanation
    assert "area_m2=248.7" in explanation
    assert "building_length=18.2" in explanation
    assert "building_coverage=50.5" in explanation
    assert "floors=2" in explanation
    assert "bbox=[46.7, 24.6, 46.702, 24.602]" in explanation
    assert "srid=4326" in explanation
    # free-text attributes are NOT echoed as measurements (no noise, no claims)
    assert "Villa 12" not in explanation


def test_llm_generation_uses_the_stored_measurements():
    repo = _rich_repo()
    prompts: list[str] = []

    class MeasuringLLM:
        def invoke(self, prompt):
            prompts.append(prompt)
            return type("R", (), {"content": json.dumps([{
                "result_id": 1, "status": "confirmed",
                "explanation": "BLD_102 overlaps BLD_157; the stored record gives "
                               "building_length = 18.2 m, building_width = 12.0 m "
                               "and area_m2 = 248.7 m².",
                "cause": "positive-area intersection",
                "recommendation": "snap boundaries so they only touch",
                "human_review_required": False,
                "related_features": ["BLD_157"]}])})()

    out = run_analysis(RUN_ID, repository=repo, llm=MeasuringLLM())
    a = next(x for x in out["analyses"] if x["result_id"] == 1)
    assert "building_length = 18.2 m" in a["explanation"]   # the LLM's answer, kept
    assert "248.7" in a["explanation"]
    # the values it cited were genuinely in the prompt it was given
    assert any("building_length" in p and "248.7" in p for p in prompts)


def test_generation_falls_back_when_complete_records_unavailable():
    """Older/custom repositories without complete records still work: the
    light-weight context is used and the run stays error-free."""
    inner = build_memory_repo()

    class LightRepo:
        fetch_feature_records = None            # not available on this repo

        def __init__(self, wrapped):
            self._wrapped = wrapped

        def __getattr__(self, name):
            return getattr(self._wrapped, name)

    out = run_analysis(RUN_ID, repository=LightRepo(inner))
    assert len(out["analyses"]) == 14
    assert out["errors"] == []
    bld001 = next(a for a in out["analyses"] if a["rule_id"] == "BLD001")
    assert bld001["status"] == "confirmed"      # grounded via details + context


def test_generation_prompt_stays_bounded_for_complex_geometry():
    """A feature with a very complex geometry must not blow the group prompt:
    records are bounded, but every field (and its value) survives."""
    repo = build_memory_repo()
    repo.seed_feature("buildings", "BLD_102", {
        **RICH_BUILDING,
        "geometry": {"type": "Polygon",
                     "coordinates": [[[46.60 + i * 0.00001, 24.60] for i in range(6000)]]},
    })
    llm = _EmptyArrayLLM()
    run_analysis(RUN_ID, repository=repo, llm=llm)
    buildings_prompt = next(p for p in llm.prompts if "Layer: buildings" in p)
    assert len(buildings_prompt) < 40_000        # bounded, not 6000 coordinates
    assert "_omitted_items" in buildings_prompt  # the trim is marked, not silent
    assert "building_length" in buildings_prompt  # fields survive
    assert "area_m2=248.7" in buildings_prompt or '"area_m2": 248.7' in buildings_prompt


def test_generation_survives_context_read_failure():
    repo = build_memory_repo()

    def boom(layer_name, feature_ids):
        raise RuntimeError('relation "public.buildings" does not exist')

    repo.fetch_feature_records = boom
    out = run_analysis(RUN_ID, repository=repo)
    assert len(out["analyses"]) == 14           # a failed read is logged, not fatal
    assert any(e.startswith("context.") for e in out["errors"])
    bld001 = next(a for a in out["analyses"] if a["rule_id"] == "BLD001")
    assert bld001["status"] == "confirmed"      # engine details still grounded it
    assert "Stored feature measurements:" not in bld001["explanation"]
