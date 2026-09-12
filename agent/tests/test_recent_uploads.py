"""Cross-upload questions: "how many files was the previous batch?".

A chat conversation is scoped to ONE upload selection (its batch id). This is
fine until the user asks about an EARLIER upload ("how many files was the
previous batch?", "compare this with my last one"), which used to be
unanswerable — the model had no way to know.

The fix is not to widen the scope: it is to list the CALLER'S OWN recent
uploads in the context (batch id, upload time, file count, file names, stored
error total), with the upload being discussed marked is_current. So the agent
can answer about other uploads from real stored numbers while one user's
uploads stay invisible to every other user.

These tests cover: the list contents and ordering, the is_current marker,
answering the "previous batch" question from single-run AND folder chat, the
exactness of the file count when the name list is truncated, per-user and
per-team isolation, the "not available" path (no history, no identity, an
upload outside the list), the unbatched-analyses caveat, the agent tool and the
API surface.
"""
from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest

from agent.chat import answer_batch_question, answer_question, build_chat_context
from agent.db.memory import InMemoryRepository
from agent.graph.builder import run_analysis
from agent.retrieval import (MAX_RECENT_FILENAMES, recent_uploads_summary)
from agent.tests.conftest import RUN_ID, StubLLM
from agent.tools import get_recent_uploads

FIXTURES = Path(__file__).parent / "fixtures"

ALICE = "11111111-1111-4111-8111-111111111111"
BOB = "22222222-2222-4222-8222-222222222222"
TEAMMATE = "33333333-3333-4333-8333-333333333333"
TEAM = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"

BATCH_OLD = "b0000000-0000-4000-8000-000000000001"     # 2 files, uploaded first
BATCH_CURRENT = "b0000000-0000-4000-8000-000000000002"  # 3 files, the one in discussion
BATCH_BOB = "b0000000-0000-4000-8000-000000000003"      # someone else's
BATCH_TEAM = "b0000000-0000-4000-8000-000000000004"     # a teammate's upload

RUN_CURRENT = RUN_ID


def _payload(run_id=None, filename="layer.geojson", layer="roads",
             errors=0, score=100.0, **extra):
    payload = {"run_id": run_id, "filename": filename, "status": "completed",
               "layer_name": layer, "total_errors": errors,
               "compliance_score": score}
    payload.update(extra)
    return payload


def _repo() -> InMemoryRepository:
    """Alice owns two uploads (one older, one current) plus one unbatched
    analysis; Bob and a teammate own uploads Alice must never see."""
    from agent.core.models import ValidationResult

    rows = json.loads((FIXTURES / "sample_run.json").read_text(encoding="utf-8"))
    repo = InMemoryRepository(results=[ValidationResult(**rows[0])])
    run_analysis(RUN_CURRENT, repository=repo)

    def seed(batch_id, filename, user_id, created_at, team_id=None, errors=0,
             score=100.0, run_id=None):
        repo.seed_analysis_record(
            run_id, _payload(run_id=run_id, filename=filename, errors=errors,
                             score=score),
            analysis_id=f"{batch_id}:{filename}", batch_id=batch_id,
            filename=filename, user_id=user_id, team_id=team_id,
            created_at=created_at, total_errors=errors,
            compliance_score=score)

    # Alice: an older 2-file upload, then the current 3-file upload
    seed(BATCH_OLD, "old/1.geojson", ALICE, "2026-09-10T09:00:00", errors=1)
    seed(BATCH_OLD, "old/2.geojson", ALICE, "2026-09-10T09:00:05", errors=2)
    seed(BATCH_CURRENT, "current/1.geojson", ALICE, "2026-09-12T11:00:00",
         run_id=RUN_CURRENT)
    seed(BATCH_CURRENT, "current/2.geojson", ALICE, "2026-09-12T11:00:05", errors=1)
    seed(BATCH_CURRENT, "current/3.geojson", ALICE, "2026-09-12T11:00:09", errors=1)
    # an analysis saved before uploads were grouped
    seed(None, "loose.geojson", ALICE, "2026-09-01T08:00:00", errors=0)
    # other people's uploads
    seed(BATCH_BOB, "bob/1.geojson", BOB, "2026-09-12T12:00:00", errors=99)
    seed(BATCH_TEAM, "team/1.geojson", TEAMMATE, "2026-09-12T13:00:00",
         team_id=TEAM, errors=7)
    return repo


@pytest.fixture()
def repo():
    return _repo()


def _viewer(user_id=ALICE, team_id=None, role="user"):
    return {"user_id": user_id, "team_id": team_id, "role": role}


class RecentLLM:
    """Stands in for the chat model following prompt rule 14: it reads
    'recent_uploads' from the context and answers about OTHER uploads, using the
    is_current marker to resolve "the previous batch"."""

    def __init__(self):
        self.prompts: list[str] = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        block = prompt.split("Context (JSON): ", 1)[1]
        block = block.split("\n\nConversation history")[0]
        context = json.loads(block.split("\n\nUser question: ")[0])
        question = prompt.split("User question: ", 1)[1].lower()
        uploads = (context.get("recent_uploads") or {}).get("uploads") or []
        index = next((i for i, u in enumerate(uploads) if u.get("is_current")), None)
        answer = "I could not find that upload."
        if "previous" in question:
            previous = (uploads[index + 1]
                        if index is not None and index + 1 < len(uploads) else None)
            answer = (f"The previous upload contained {previous['files']} file(s): "
                      + ", ".join(previous["filenames"])
                      if previous else
                      "There is no earlier upload available for your account.")
        elif "how many" in question and "upload" in question:
            answer = f"You have {len(uploads)} uploads listed."
        elif "most errors" in question and uploads:
            worst = max(uploads, key=lambda u: u.get("total_errors") or 0)
            answer = (f"{worst['batch_id']} had the most errors "
                      f"({worst['total_errors']}).")
        return type("R", (), {"content": json.dumps({"answer": answer,
                                                    "sources": []})})()


# ── the list itself ────────────────────────────────────────────────────────
def test_recent_uploads_lists_the_callers_uploads_newest_first(repo):
    summary = recent_uploads_summary(repo, _viewer(), current_scope_id=BATCH_CURRENT)
    assert summary["available"] is True
    assert [u["batch_id"] for u in summary["uploads"]] == [BATCH_CURRENT, BATCH_OLD]
    current, older = summary["uploads"]
    assert current["files"] == 3 and current["is_current"] is True
    assert older["files"] == 2 and "is_current" not in older
    assert older["filenames"] == ["old/1.geojson", "old/2.geojson"]
    assert older["total_errors"] == 3          # stored per-file totals, summed
    assert older["uploaded_at"].startswith("2026-09-10T09:00")
    # the caveat about pre-grouping analyses is stated, not silently dropped
    assert summary["unbatched_analyses"] == 1


def test_upload_list_is_bounded_but_the_file_count_stays_exact():
    from agent.core.models import ValidationResult

    repo = _repo()
    long_batch = "b0000000-0000-4000-8000-00000000000f"
    total = MAX_RECENT_FILENAMES + 4
    for i in range(total):
        repo.seed_analysis_record(
            None, _payload(filename=f"many/{i}.geojson"),
            analysis_id=f"many-{i}", batch_id=long_batch, filename=f"many/{i}.geojson",
            user_id=ALICE, created_at=f"2026-09-12T14:{i:02d}:00", total_errors=0)
    entry = next(u for u in recent_uploads_summary(repo, _viewer())["uploads"]
                 if u["batch_id"] == long_batch)
    assert entry["files"] == total                      # exact count
    assert len(entry["filenames"]) == MAX_RECENT_FILENAMES
    assert entry["filenames_truncated"] == 4


def test_the_list_is_limited_to_the_newest_uploads(repo):
    summary = recent_uploads_summary(repo, _viewer(), limit=1)
    assert [u["batch_id"] for u in summary["uploads"]] == [BATCH_CURRENT]


# ── isolation ──────────────────────────────────────────────────────────────
def test_another_users_uploads_are_never_listed(repo):
    alice = recent_uploads_summary(repo, _viewer(), current_scope_id=BATCH_CURRENT)
    listed = {u["batch_id"] for u in alice["uploads"]}
    assert BATCH_BOB not in listed and BATCH_TEAM not in listed
    assert all(BATCH_BOB not in json.dumps(u) for u in alice["uploads"])

    bob = recent_uploads_summary(repo, _viewer(user_id=BOB))
    assert [u["batch_id"] for u in bob["uploads"]] == [BATCH_BOB]
    assert BATCH_CURRENT not in {u["batch_id"] for u in bob["uploads"]}
    # Bob's own pre-grouping analysis count, not Alice's
    assert bob["unbatched_analyses"] == 0


def test_a_manager_sees_team_uploads_and_a_member_does_not(repo):
    manager = recent_uploads_summary(
        repo, _viewer(user_id=ALICE, team_id=TEAM, role="manager"))
    assert BATCH_TEAM in {u["batch_id"] for u in manager["uploads"]}

    member = recent_uploads_summary(
        repo, _viewer(user_id=ALICE, team_id=TEAM, role="member"))
    assert BATCH_TEAM not in {u["batch_id"] for u in member["uploads"]}
    assert BATCH_CURRENT in {u["batch_id"] for u in member["uploads"]}


def test_without_an_identity_nothing_is_listed(repo):
    net = recent_uploads_summary(repo, {})
    assert net["available"] is False and net["uploads"] == []
    assert "No earlier uploads" in net["uploads_note"]
    assert recent_uploads_summary(repo, None)["available"] is False


def test_a_repository_without_upload_history_degrades_gracefully():
    class NoHistory(InMemoryRepository):
        def fetch_recent_upload_batches(self, viewer=None, limit=20):
            return {}

    summary = recent_uploads_summary(NoHistory(), _viewer())
    assert summary["available"] is False and summary["uploads"] == []


# ── answering the question ─────────────────────────────────────────────────
def test_previous_batch_is_answered_from_stored_numbers(repo):
    llm = RecentLLM()
    out = answer_batch_question(repo, BATCH_CURRENT,
                                "how many files was the previous batch?",
                                llm=llm, user_key=ALICE, viewer=_viewer())
    assert "2 file(s)" in out["answer"]
    assert "old/1.geojson" in out["answer"] and "old/2.geojson" in out["answer"]
    context = json.loads(
        llm.prompts[0].split("Context (JSON): ", 1)[1]
        .split("\n\nUser question: ")[0])
    assert context["recent_uploads"]["uploads"][0]["is_current"] is True
    assert context["batch_id"] == BATCH_CURRENT


def test_previous_batch_also_works_from_a_single_file_chat(repo):
    """A lone uploaded file has its own run thread; the run's batch is marked
    is_current there too, so 'the previous batch' still resolves."""
    llm = RecentLLM()
    out = answer_question(repo, RUN_CURRENT, "how many files was the previous batch?",
                          llm=llm, user_key=ALICE, viewer=_viewer())
    assert "2 file(s)" in out["answer"]
    context = json.loads(
        llm.prompts[0].split("Context (JSON): ", 1)[1]
        .split("\n\nUser question: ")[0])
    marks = [u for u in context["recent_uploads"]["uploads"] if u.get("is_current")]
    assert [u["batch_id"] for u in marks] == [BATCH_CURRENT]


def test_a_question_about_an_unlisted_upload_is_reported_not_invented(repo):
    """The very first upload has nothing before it — the model must say so."""
    llm = RecentLLM()
    out = answer_batch_question(repo, BATCH_OLD, "how many files was the previous batch?",
                                llm=llm, user_key=ALICE, viewer=_viewer())
    assert "no earlier upload" in out["answer"].lower()
    assert "9" not in out["answer"] and "99" not in out["answer"]


def test_anonymous_chat_has_no_upload_list(repo):
    """No caller identity (CLI/tests without auth) → no recent uploads at all,
    and the previous behaviour is unchanged."""
    context = build_chat_context(repo, RUN_CURRENT)
    assert "recent_uploads" not in context
    summary = recent_uploads_summary(repo, _viewer(user_id=ALICE))
    assert summary["available"] is True


def test_upload_history_reaches_the_prompt_and_stays_scoped(repo):
    """End-to-end through the prompt: the model sees the caller's list and Bob's
    upload is nowhere in it."""
    llm = RecentLLM()
    answer_batch_question(repo, BATCH_CURRENT, "which of my uploads had the most errors?",
                          llm=llm, user_key=ALICE, viewer=_viewer())
    prompt = llm.prompts[0]
    assert "recent_uploads" in prompt
    assert BATCH_OLD in prompt
    assert BATCH_BOB not in prompt and "bob/1.geojson" not in prompt
    assert "99" not in prompt


def test_upload_history_never_leaks_across_users_in_the_prompt(repo):
    llm = RecentLLM()
    answer_batch_question(repo, BATCH_BOB, "how many files was the previous batch?",
                          llm=llm, user_key=BOB, viewer=_viewer(user_id=BOB))
    prompt = llm.prompts[0]
    assert BATCH_BOB in prompt
    assert BATCH_CURRENT not in prompt and "current/1.geojson" not in prompt


# ── the agent tool ─────────────────────────────────────────────────────────
def test_get_recent_uploads_tool(repo):
    out = get_recent_uploads(repo, ALICE, current_scope_id=BATCH_CURRENT)
    assert [u["batch_id"] for u in out["uploads"]] == [BATCH_CURRENT, BATCH_OLD]
    assert out["uploads"][1]["files"] == 2
    assert get_recent_uploads(repo, "", current_scope_id=BATCH_CURRENT)["available"] is False


# ── API surface ────────────────────────────────────────────────────────────
@pytest.fixture()
def client(repo, monkeypatch):
    from fastapi.testclient import TestClient

    from agent.api import router as api_router
    from agent.api.app import app

    class _FakeEngine:
        def begin(self):
            return contextlib.nullcontext(None)

    app.dependency_overrides[api_router.get_repository] = lambda: repo
    app.dependency_overrides[api_router.current_user] = lambda: {
        "user_id": ALICE, "team_id": None, "role": "user"}
    monkeypatch.setattr(api_router, "database_engine", lambda: _FakeEngine())
    monkeypatch.setattr(api_router, "ensure_app_tables", lambda conn: None)
    monkeypatch.setattr(api_router, "require_batch_access",
                        lambda conn, user, batch_id: [])
    monkeypatch.setattr(api_router, "require_run_access",
                        lambda conn, user, run_id: [])
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_recent_uploads_endpoint(client):
    resp = client.get("/api/uploads/recent")
    assert resp.status_code == 200
    body = resp.json()
    assert body["available"] is True
    assert [u["batch_id"] for u in body["uploads"]] == [BATCH_CURRENT, BATCH_OLD]
    assert body["uploads"][1]["files"] == 2
    assert body["unbatched_analyses"] == 1
    assert BATCH_BOB not in json.dumps(body)


def test_batch_chat_endpoint_answers_about_the_previous_batch(client, monkeypatch):
    import agent.chat as chat_mod
    monkeypatch.setattr(chat_mod, "get_llm", lambda: RecentLLM())
    resp = client.post(f"/api/analyses/batch/{BATCH_CURRENT}/chat",
                       json={"question": "how many files was the previous batch?"})
    assert resp.status_code == 200
    assert "2 file(s)" in resp.json()["answer"]


def test_single_run_chat_endpoint_answers_about_the_previous_batch(client, monkeypatch):
    import agent.chat as chat_mod
    monkeypatch.setattr(chat_mod, "get_llm", lambda: RecentLLM())
    resp = client.post(f"/api/validation/{RUN_CURRENT}/chat",
                       json={"question": "how many files was the previous batch?"})
    assert resp.status_code == 200
    assert "2 file(s)" in resp.json()["answer"]


# ── CLI ────────────────────────────────────────────────────────────────────
def test_cli_chat_passes_the_viewer_only_when_a_user_id_is_given(repo, monkeypatch):
    """`agent.cli chat <run> --user-id <uuid>` unlocks that user's uploads; without
    the flag the CLI stays run-scoped exactly as before."""
    import agent.chat as chat_mod
    import agent.db.postgres as pg
    from agent.cli import main

    seen: list[dict] = []

    def fake_answer(repo_, run_id, question, **kwargs):
        seen.append(kwargs)
        return {"answer": "ok", "sources": []}

    monkeypatch.setattr(chat_mod, "answer_question", fake_answer)
    # the CLI imports get_llm from agent.core.llm inside the command, so patch there
    monkeypatch.setattr("agent.core.llm.get_llm", lambda: RecentLLM())
    monkeypatch.setattr(pg, "PostgresRepository", lambda: repo)

    assert main(["chat", RUN_CURRENT, "--ask", "hi", "--user-id", ALICE]) == 0
    assert seen[-1]["viewer"] == {"user_id": ALICE, "role": "user"}
    assert seen[-1]["user_key"] == "cli"

    assert main(["chat", RUN_CURRENT, "--ask", "hi"]) == 0
    assert seen[-1]["viewer"] is None
