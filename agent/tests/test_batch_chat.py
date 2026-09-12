"""Upload-batch chat tests (folder / multi-file selection).

Requirement: a user who uploads a FOLDER of files gets one analysis per file
(that is how the pipeline works), and must still be able to ask the agent about
the whole selection — "which file has the most errors?", "summarise the folder",
"which files are clean?" — not just about one file at a time.

These tests cover the batch scope end to end: the merged context (per-file
summary + all findings/analyses/payloads/feature records), cross-file answers
computed from the stored numbers, per-batch conversation memory, isolation
between batches, honest handling of files without a run, and the API surface
(GET/POST /api/analyses/batch/{batch_id}).
"""
from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest

from agent.chat import (answer_batch_question, answer_question,
                        build_batch_chat_context, build_chat_context)
from agent.db.memory import InMemoryRepository
from agent.graph.builder import run_analysis
from agent.retrieval import build_batch_analysis_dataset
from agent.tests.conftest import MISSING_RUN_ID, RUN_ID, StubLLM
from agent.tools import get_batch_analysis_record

FIXTURES = Path(__file__).parent / "fixtures"
BATCH_ID = "b1a2c3d4-0000-4000-8000-000000000001"
OTHER_BATCH_ID = "c2b3d4e5-0000-4000-8000-000000000002"
FOLDER = "riyadh-batch"

ROADS_PAYLOAD = {
    "run_id": RUN_ID, "filename": f"{FOLDER}/roads_1.geojson", "status": "completed",
    "layer_name": "roads", "compliance_score": 92.5, "total_errors": 14,
    "quality_after": {"quality_score": 92.5, "error_rate": 3.2},
    "measurements": {"street_length": 842.6, "street_width": 7.5},
}
BUILDINGS_PAYLOAD = {
    "run_id": MISSING_RUN_ID, "filename": f"{FOLDER}/buildings_1.geojson",
    "status": "completed", "layer_name": "buildings", "compliance_score": 61.0,
    "total_errors": 2, "measurements": {"building_length": 18.2, "plot_area": 432.0},
}
IMAGE_PAYLOAD = {                       # a map image: no validation run at all
    "filename": f"{FOLDER}/scan.png", "status": "completed", "input_type": "image",
    "compliance_score": 88.0, "issues": [{"error_type": "Missing legend",
                                          "severity": "medium",
                                          "message": "no legend detected"}],
}
OTHER_BATCH_PAYLOAD = {
    "run_id": RUN_ID, "filename": "another-batch/secret.geojson",
    "status": "completed", "layer_name": "roads", "compliance_score": 10.0,
    "total_errors": 99, "measurements": {"street_length": 111.1},
}


def _batch_repo() -> InMemoryRepository:
    from agent.core.models import ValidationResult

    rows = json.loads((FIXTURES / "sample_run.json").read_text(encoding="utf-8"))
    rows += json.loads((FIXTURES / "missing_context_run.json").read_text(encoding="utf-8"))
    repo = InMemoryRepository(results=[ValidationResult(**r) for r in rows])
    repo.seed_feature("roads", "RD_101", {
        "feature_id": "RD_101", "layer_name": "roads", "geometry_type": "LineString",
        "srid": 4326, "length_m": 842.6, "street_width": 7.5, "vertex_count": 214,
        "centroid": "POINT(46.68 24.66)",
        "x_min": 46.60, "y_min": 24.60, "x_max": 46.70, "y_max": 24.70,
    })

    run_analysis(RUN_ID, repository=repo)
    run_analysis(MISSING_RUN_ID, repository=repo)

    # three files from ONE upload selection ...
    repo.seed_analysis_record(RUN_ID, dict(ROADS_PAYLOAD), analysis_id="a1",
                              batch_id=BATCH_ID, filename=ROADS_PAYLOAD["filename"],
                              total_errors=14, compliance_score=92.5)
    repo.seed_analysis_record(MISSING_RUN_ID, dict(BUILDINGS_PAYLOAD), analysis_id="a2",
                              batch_id=BATCH_ID, filename=BUILDINGS_PAYLOAD["filename"],
                              total_errors=2, compliance_score=61.0)
    repo.seed_analysis_record(None, dict(IMAGE_PAYLOAD), analysis_id="a3",
                              batch_id=BATCH_ID, filename=IMAGE_PAYLOAD["filename"],
                              analysis_type="image", total_errors=0)
    # ... and one file from a DIFFERENT upload selection
    repo.seed_analysis_record(RUN_ID, dict(OTHER_BATCH_PAYLOAD), analysis_id="a9",
                              batch_id=OTHER_BATCH_ID,
                              filename=OTHER_BATCH_PAYLOAD["filename"], total_errors=99)
    return repo


@pytest.fixture()
def batch_repo():
    return _batch_repo()


class BatchLLM:
    """Deterministic stand-in for the chat model: it answers from the batch
    context it is handed (the same way the prompt instructs the real model),
    computing cross-file answers from the stored per-file numbers."""

    def __init__(self):
        self.prompts: list[str] = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        context_block = prompt.split("Context (JSON): ", 1)[1]
        # the conversation history (when present) follows the context block
        context_block = context_block.split("\n\nConversation history")[0]
        context = json.loads(context_block.split("\n\nUser question:")[0])
        question = prompt.split("User question: ", 1)[1].split("\n\nReply STRICT JSON")[0].lower()
        files = context["files"]
        analyzed = [f for f in files if f.get("run_id")]
        if "most" in question or "worst" in question:
            worst = max(analyzed, key=lambda f: f.get("total_errors") or 0)
            answer = (f"{worst['filename']} has the most errors "
                      f"({worst['total_errors']}).")
        elif "clean" in question:
            clean = [f["filename"] for f in analyzed
                     if not (f.get("total_errors") or 0)]
            answer = ("No file is clean; every analyzed file has findings."
                      if not clean else "Clean files: " + ", ".join(clean))
        else:
            answer = "; ".join(
                f"{f['filename']}: {f.get('total_errors')} error(s), "
                f"score {f.get('compliance_score')}" for f in files)
        return type("R", (), {"content": json.dumps(
            {"answer": answer, "sources": []}, default=str)})()


# ── the merged batch context ────────────────────────────────────────────────
def test_batch_context_has_every_file_of_the_selection(batch_repo):
    ctx = build_batch_chat_context(batch_repo, BATCH_ID)
    assert ctx["batch_id"] == BATCH_ID
    names = [f["filename"] for f in ctx["files"]]
    assert names == [f"{FOLDER}/roads_1.geojson", f"{FOLDER}/buildings_1.geojson",
                     f"{FOLDER}/scan.png"]
    by_name = {f["filename"]: f for f in ctx["files"]}
    assert by_name[f"{FOLDER}/roads_1.geojson"]["total_errors"] == 14
    assert by_name[f"{FOLDER}/buildings_1.geojson"]["compliance_score"] == 61.0
    # a map image has no validation run and is marked as such
    assert by_name[f"{FOLDER}/scan.png"]["run_id"] is None
    assert ctx["data_counts"]["files"] == 3
    assert ctx["data_counts"]["files_with_a_run"] == 2


def test_batch_context_merges_findings_analyses_and_payloads(batch_repo):
    ctx = build_batch_chat_context(batch_repo, BATCH_ID)
    # 14 findings from the roads run + 2 from the buildings run
    assert len(ctx["findings"]) == 16
    assert all("source_file" in f for f in ctx["findings"])
    assert {f["source_file"] for f in ctx["findings"]} == {
        f"{FOLDER}/roads_1.geojson", f"{FOLDER}/buildings_1.geojson"}
    assert len(ctx["analyses"]) == 16
    # every stored payload is present, whole, per file
    assert len(ctx["analysis_records"]) == 3
    payloads = {r["filename"]: r["result"] for r in ctx["analysis_records"]}
    assert payloads[f"{FOLDER}/roads_1.geojson"]["measurements"]["street_length"] == 842.6
    assert payloads[f"{FOLDER}/scan.png"]["input_type"] == "image"
    # field index is derived from the merged data
    assert "plot_area" in ctx["available_fields"]
    assert "street_width" in ctx["available_fields"]


def test_batch_feature_records_are_namespaced_per_file(batch_repo):
    ctx = build_batch_chat_context(batch_repo, BATCH_ID)
    assert f"{FOLDER}/roads_1.geojson#RD_101" in ctx["feature_data"]
    record = ctx["feature_data"][f"{FOLDER}/roads_1.geojson#RD_101"]
    assert record["street_width"] == 7.5            # complete record, all fields
    assert record["source_file"] == f"{FOLDER}/roads_1.geojson"
    assert record["feature_id"] == "RD_101"


def test_batch_context_notes_the_live_layer_caveat(batch_repo):
    ctx = build_batch_chat_context(batch_repo, BATCH_ID)
    assert ctx["notes"] and "LIVE layer" in ctx["notes"][0]


def test_batch_context_is_isolated_from_other_batches(batch_repo):
    blob = json.dumps(build_batch_chat_context(batch_repo, BATCH_ID), default=str)
    assert "another-batch/secret.geojson" not in blob     # other file not included
    assert '"total_errors": 99' not in blob               # nor its stored numbers
    assert "111.1" not in blob                            # nor its measurements
    other = build_batch_chat_context(batch_repo, OTHER_BATCH_ID)
    assert [f["filename"] for f in other["files"]] == [OTHER_BATCH_PAYLOAD["filename"]]


def test_unknown_batch_raises_value_error(batch_repo):
    with pytest.raises(ValueError, match="No analyses found for upload batch"):
        build_batch_chat_context(batch_repo, "00000000-0000-4000-8000-0000000000ff")


# ── cross-file questions answered from the stored numbers ──────────────────
def test_question_across_the_whole_folder(batch_repo):
    llm = BatchLLM()
    out = answer_batch_question(batch_repo, BATCH_ID,
                                "which file has the most errors?", llm=llm)
    assert f"{FOLDER}/roads_1.geojson" in out["answer"]
    assert "14" in out["answer"]
    # every file of the selection was in the prompt it answered from
    for name in (f"{FOLDER}/roads_1.geojson", f"{FOLDER}/buildings_1.geojson",
                 f"{FOLDER}/scan.png"):
        assert name in llm.prompts[0]
    assert "upload batch of 3 file(s)" in llm.prompts[0]


def test_folder_summary_lists_each_file_with_its_numbers(batch_repo):
    llm = BatchLLM()
    out = answer_batch_question(batch_repo, BATCH_ID, "summarise the folder", llm=llm)
    for name in (f"{FOLDER}/roads_1.geojson", f"{FOLDER}/buildings_1.geojson",
                 f"{FOLDER}/scan.png"):
        assert name in out["answer"]
    assert "92.5" in out["answer"] and "61.0" in out["answer"]


def test_batch_answers_do_not_invent_files_or_values(batch_repo):
    llm = BatchLLM()
    out = answer_batch_question(batch_repo, BATCH_ID, "which files are clean?", llm=llm)
    assert "another-batch" not in out["answer"]
    assert OTHER_BATCH_PAYLOAD["filename"] not in llm.prompts[0]


# ── conversation memory + grounding rules carry over to batch scope ────────
def test_batch_memory_is_scoped_to_the_batch(batch_repo):
    llm = BatchLLM()
    answer_batch_question(batch_repo, BATCH_ID, "summarise the folder",
                          llm=llm, user_key="user-1")
    answer_batch_question(batch_repo, BATCH_ID, "and again?",
                          llm=llm, user_key="user-1")
    assert "Conversation history" not in llm.prompts[0]
    assert "Conversation history" in llm.prompts[1]
    assert "summarise the folder" in llm.prompts[1]
    # stored under the batch id, not under one of its runs
    assert len(batch_repo.fetch_chat_history(BATCH_ID, "user-1")) == 2
    assert batch_repo.fetch_chat_history(RUN_ID, "user-1") == []


def test_single_run_chat_still_works_for_a_batched_file(batch_repo):
    context = build_chat_context(batch_repo, RUN_ID)
    assert context["run_id"] == RUN_ID and "batch_id" not in context
    stub = StubLLM(json.dumps({"answer": "single run answer", "sources": []}))
    out = answer_question(batch_repo, RUN_ID, "what should I fix first?", llm=stub)
    assert out["answer"] == "single run answer"


def test_batch_chat_requires_llm(batch_repo, monkeypatch):
    import agent.chat as chat_mod
    monkeypatch.setattr(chat_mod, "get_llm", lambda: None)
    with pytest.raises(RuntimeError, match="LLM key"):
        answer_batch_question(batch_repo, BATCH_ID, "hi", llm=None)


def test_batch_sources_are_filtered_to_existing_findings(batch_repo):
    stub = StubLLM(json.dumps({"answer": "answer",
                               "sources": ["BLD002", "GHOST@nothing"]}))
    out = answer_batch_question(batch_repo, BATCH_ID, "q", llm=stub)
    assert out["sources"] == ["BLD002"]     # hallucinated source dropped


# ── tools + dataset API ────────────────────────────────────────────────────
def test_get_batch_analysis_record_tool(batch_repo):
    dataset = get_batch_analysis_record(batch_repo, BATCH_ID)
    assert dataset["counts"]["files"] == 3
    assert len(dataset["analysis_records"]) == 3
    assert "plot_area" in dataset["available_fields"]


def test_build_batch_dataset_is_best_effort_without_batch_support():
    repo = InMemoryRepository()             # nothing stored at all
    dataset = build_batch_analysis_dataset(repo, BATCH_ID)
    assert dataset["files"] == [] and dataset["counts"]["files"] == 0


# ── a single uploaded file: a batch of one, no toggle needed ───────────────
def test_a_lone_uploaded_file_is_a_batch_of_one():
    """The UI generates one batch id per selection, so a single-file upload is
    simply a folder with one file — same endpoint, same scope, answered from
    that file's own stored values."""
    from agent.core.models import ValidationResult

    solo_batch = "d3c4e5f6-0000-4000-8000-000000000003"
    rows = json.loads((FIXTURES / "sample_run.json").read_text(encoding="utf-8"))
    repo = InMemoryRepository(results=[ValidationResult(**rows[0])])
    run_analysis(RUN_ID, repository=repo)
    repo.seed_analysis_record(
        RUN_ID, {"run_id": RUN_ID, "filename": "solo.geojson",
                 "layer_name": "roads", "status": "completed",
                 "compliance_score": 77.0, "total_errors": 3,
                 "measurements": {"street_length": 55.5}},
        analysis_id="solo-1", batch_id=solo_batch, filename="solo.geojson",
        total_errors=3, compliance_score=77.0)

    dataset = build_batch_analysis_dataset(repo, solo_batch)
    assert dataset["counts"]["files"] == 1
    assert [f["filename"] for f in dataset["files"]] == ["solo.geojson"]
    assert "55.5" in json.dumps(dataset, default=str)   # its measurements too

    out = answer_batch_question(repo, solo_batch, "which file has the most errors?",
                                llm=BatchLLM(), user_key="solo-user")
    assert "solo.geojson" in out["answer"]
    # and its single-run thread is still available for the same file
    assert build_chat_context(repo, RUN_ID)["run_id"] == RUN_ID


# ── API surface ────────────────────────────────────────────────────────────
@pytest.fixture()
def client(batch_repo, monkeypatch):
    from fastapi.testclient import TestClient

    from agent.api import router as api_router
    from agent.api.app import app

    class _FakeEngine:
        def begin(self):
            return contextlib.nullcontext(None)

    app.dependency_overrides[api_router.get_repository] = lambda: batch_repo
    app.dependency_overrides[api_router.current_user] = lambda: {
        "user_id": "00000000-0000-4000-8000-000000000001", "role": "admin"}
    monkeypatch.setattr(api_router, "database_engine", lambda: _FakeEngine())
    monkeypatch.setattr(api_router, "ensure_app_tables", lambda conn: None)

    def _require_batch(conn, user, batch_id):
        """Mirror the real guard: an unknown batch is a 404, not an empty batch."""
        from fastapi import HTTPException
        if not batch_repo.fetch_analysis_records_by_batch(batch_id):
            raise HTTPException(status_code=404, detail="Analysis batch not found.")
        return []

    monkeypatch.setattr(api_router, "require_batch_access", _require_batch)
    monkeypatch.setattr(api_router, "require_run_access",
                        lambda conn, user, run_id: [])
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_batch_record_endpoint(client):
    resp = client.get(f"/api/analyses/batch/{BATCH_ID}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["batch_id"] == BATCH_ID
    assert body["counts"]["files"] == 3
    assert len(body["files"]) == 3
    assert body["feature_data"][f"{FOLDER}/roads_1.geojson#RD_101"]["street_width"] == 7.5


def test_batch_record_endpoint_404_for_unknown_batch(client):
    resp = client.get("/api/analyses/batch/00000000-0000-4000-8000-0000000000ff")
    assert resp.status_code == 404


def test_batch_record_endpoint_rejects_malformed_id(client):
    assert client.get("/api/analyses/batch/not-a-uuid").status_code == 422


def test_batch_chat_endpoint(client, monkeypatch):
    import agent.chat as chat_mod
    monkeypatch.setattr(chat_mod, "get_llm", lambda: BatchLLM())
    resp = client.post(f"/api/analyses/batch/{BATCH_ID}/chat",
                       json={"question": "which file has the most errors?"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"question", "answer", "sources"}
    assert f"{FOLDER}/roads_1.geojson" in body["answer"]


def test_batch_chat_endpoint_404_for_unknown_batch(client, monkeypatch):
    import agent.chat as chat_mod
    monkeypatch.setattr(chat_mod, "get_llm", lambda: BatchLLM())
    resp = client.post("/api/analyses/batch/00000000-0000-4000-8000-0000000000ff/chat",
                       json={"question": "hi"})
    assert resp.status_code == 404


# ── chat refresh: clearing a conversation, not only the screen ─────────────
# The chat has one refresh button and no scope switch, so the scope is decided
# by the uploaded selection: a folder (batch id) refreshes the whole-folder
# thread, a lone file refreshes its single-run thread.
def test_refresh_clears_this_conversation_so_the_next_answer_starts_clean(batch_repo):
    llm = BatchLLM()
    # a marker token that only exists in the question being asked, so a hit in
    # a later prompt can only come from the stored conversation history
    first = "summarise the folder [MARKER-4471]"
    answer_batch_question(batch_repo, BATCH_ID, first, llm=llm, user_key="user-1")
    assert len(batch_repo.fetch_chat_history(BATCH_ID, "user-1")) == 1

    assert batch_repo.clear_chat_history(BATCH_ID, "user-1") == 1
    assert batch_repo.fetch_chat_history(BATCH_ID, "user-1") == []

    # the cleared turn is not fed back to the model on the next question
    answer_batch_question(batch_repo, BATCH_ID, "and now?", llm=llm, user_key="user-1")
    assert "Conversation history" not in llm.prompts[-1]
    assert "MARKER-4471" not in llm.prompts[-1]


def test_refresh_is_isolated_to_one_user_and_one_scope(batch_repo):
    llm = BatchLLM()
    answer_batch_question(batch_repo, BATCH_ID, "folder question",
                          llm=llm, user_key="user-1")
    answer_batch_question(batch_repo, BATCH_ID, "same batch, other user",
                          llm=llm, user_key="user-2")
    # a lone file keeps its own single-run thread, separate from folder chat
    answer_question(batch_repo, RUN_ID, "single file question",
                    llm=StubLLM(json.dumps({"answer": "single run answer",
                                            "sources": []})), user_key="user-1")

    assert batch_repo.clear_chat_history(BATCH_ID, "user-1") == 1

    # another user's thread and this user's single-file thread are untouched
    assert len(batch_repo.fetch_chat_history(BATCH_ID, "user-2")) == 1
    assert len(batch_repo.fetch_chat_history(RUN_ID, "user-1")) == 1
    # clearing an empty conversation is a no-op, not an error
    assert batch_repo.clear_chat_history(BATCH_ID, "user-1") == 0
    assert batch_repo.clear_chat_history(OTHER_BATCH_ID, "user-1") == 0


def test_reset_batch_chat_endpoint(client, batch_repo, monkeypatch):
    import agent.chat as chat_mod
    monkeypatch.setattr(chat_mod, "get_llm", lambda: BatchLLM())
    user_key = "00000000-0000-4000-8000-000000000001"   # the fixture's user
    assert client.post(f"/api/analyses/batch/{BATCH_ID}/chat",
                       json={"question": "which file has the most errors?"},
                       ).status_code == 200
    assert len(batch_repo.fetch_chat_history(BATCH_ID, user_key)) == 1

    resp = client.delete(f"/api/analyses/batch/{BATCH_ID}/chat")
    assert resp.status_code == 200
    assert resp.json() == {"scope": "batch", "scope_id": BATCH_ID,
                           "cleared": 1, "persisted": True}
    # the memory behind the answer is gone, so the thread cannot leak back
    assert batch_repo.fetch_chat_history(BATCH_ID, user_key) == []

    # refreshing an already clean conversation succeeds and clears nothing
    assert client.delete(f"/api/analyses/batch/{BATCH_ID}/chat").json()["cleared"] == 0


def test_reset_run_chat_endpoint(client, batch_repo, monkeypatch):
    """A single uploaded file has no batch, so its refresh targets the run."""
    import agent.chat as chat_mod
    monkeypatch.setattr(chat_mod, "get_llm", lambda: StubLLM(
        json.dumps({"answer": "single run answer", "sources": []})))
    user_key = "00000000-0000-4000-8000-000000000001"
    assert client.post(f"/api/validation/{RUN_ID}/chat",
                       json={"question": "what should I fix first?"},
                       ).status_code == 200

    resp = client.delete(f"/api/validation/{RUN_ID}/chat")
    assert resp.status_code == 200
    assert resp.json() == {"scope": "run", "scope_id": RUN_ID,
                           "cleared": 1, "persisted": True}
    assert batch_repo.fetch_chat_history(RUN_ID, user_key) == []
    # the batch threads of the same files are untouched by a single-run refresh
    assert batch_repo.fetch_chat_history(BATCH_ID, user_key) == []


def test_reset_endpoint_rejects_unknown_and_malformed_scopes(client):
    assert client.delete("/api/analyses/batch/00000000-0000-4000-8000-0000000000ff/chat"
                         ).status_code == 404
    assert client.delete("/api/analyses/batch/not-a-uuid/chat").status_code == 422
    assert client.delete("/api/validation/not-a-uuid/chat").status_code == 422
