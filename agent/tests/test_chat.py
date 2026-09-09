"""Chat-layer tests: grounding, source filtering, no-LLM behaviour."""
from __future__ import annotations

import json

import pytest

from agent.chat import answer_question, build_chat_context
from agent.graph.builder import run_analysis
from agent.tests.conftest import RUN_ID, StubLLM, build_memory_repo


def _seed(repo) -> None:
    # Chat reads STORED analyses, so analyze the run first (template path).
    run_analysis(RUN_ID, repository=repo)


def test_context_contains_summary_and_analyses(repo):
    _seed(repo)
    ctx = build_chat_context(repo, RUN_ID)
    assert ctx["run_id"] == RUN_ID
    assert ctx["summary"]["total_errors"] == 14
    assert len(ctx["analyses"]) == 14
    assert ctx["rules"]["RD001"]["type"] == "heuristic"


def test_context_contains_remediation_audit(repo):
    _seed(repo)   # run_analysis also persists remediation records
    ctx = build_chat_context(repo, RUN_ID)
    rem = ctx["remediation"]
    assert rem["available"] is True
    # 14 records: BLD003+RD004 applied, RD001/RD002+others pending_review,
    # GIS001-005 no_action (layer-level), none failed in the fixture run.
    assert rem["summary"]["total"] == 14
    assert rem["summary"]["auto_fixed"] == 2
    assert rem["summary"]["failed"] == 0
    assert rem["summary"]["pending_review"] == 7
    assert rem["summary"]["no_action"] == 5
    assert len(rem["items"]) == 14
    item = rem["items"][0]
    assert {"rule_id", "feature_id", "action", "status",
            "remediation_type"} <= set(item)


def test_chat_prompt_includes_remediation_audit(repo):
    _seed(repo)
    prompts: list[str] = []

    class RecordingLLM:
        def invoke(self, prompt):
            prompts.append(prompt)
            return type("R", (), {"content": json.dumps({
                "answer": "Two invalid geometries were repaired automatically; "
                          "the rest are queued for human review.",
                "sources": []})})()

    out = answer_question(repo, RUN_ID, "what was fixed automatically?", llm=RecordingLLM())
    assert "remediated automatically" in out["answer"] or "repaired automatically" in out["answer"]
    joined = prompts[0]
    assert '"remediation"' in joined
    assert '"auto_fixed": 2' in joined
    assert '"pending_review": 7' in joined


def test_chat_works_when_remediation_table_missing(repo):
    _seed(repo)
    original = repo.fetch_remediation_records

    def boom(run_id):
        raise RuntimeError("relation agent_remediation_actions does not exist")

    repo.fetch_remediation_records = boom
    try:
        ctx = build_chat_context(repo, RUN_ID)
        assert ctx["remediation"]["available"] is False
        assert ctx["remediation"]["items"] == []
        # And answering still works (analysis grounding unaffected).
        stub = StubLLM(json.dumps({"answer": "ok", "sources": ["RD005"]}))
        out = answer_question(repo, RUN_ID, "hi", llm=stub)
        assert out["answer"] == "ok"
    finally:
        repo.fetch_remediation_records = original


def test_answer_returns_question_answer_sources(repo):
    _seed(repo)
    stub = StubLLM(json.dumps({
        "answer": "Fix critical missing geometry first (RD005, BLD004).",
        "sources": ["RD005", "BLD004", "FAKE@nothing"]}))   # fake must be dropped
    out = answer_question(repo, RUN_ID, "what should I fix first?", llm=stub)
    assert out["question"] == "what should I fix first?"
    assert out["answer"].startswith("Fix critical")
    assert set(out["sources"]) == {"RD005", "BLD004"}   # FAKE@nothing filtered out


def test_sources_are_only_known_ids(repo):
    _seed(repo)
    stub = StubLLM(json.dumps({
        "answer": "answer",
        "sources": ["BLD001@BLD_102", "BLD_102", "GHOST_9", "BLD001"]}))
    out = answer_question(repo, RUN_ID, "q", llm=stub)
    assert "BLD001@BLD_102" in out["sources"]
    assert "BLD_102" in out["sources"]
    assert "BLD001" in out["sources"]
    assert "GHOST_9" not in out["sources"]   # hallucinated id dropped


def test_chat_without_analyses_raises(empty_repo):
    with pytest.raises(ValueError, match="No agent analysis"):
        build_chat_context(empty_repo, RUN_ID)


def test_chat_requires_llm(repo, monkeypatch):
    _seed(repo)
    import agent.chat as chat_mod
    monkeypatch.setattr(chat_mod, "get_llm", lambda: None)
    with pytest.raises(RuntimeError, match="LLM key"):
        answer_question(repo, RUN_ID, "hi", llm=None)


def test_malformed_llm_answer_raises(repo):
    _seed(repo)
    stub = StubLLM("not json at all")
    with pytest.raises(RuntimeError, match="did not return a valid answer"):
        answer_question(repo, RUN_ID, "hi", llm=stub)


# ── conversation memory ─────────────────────────────────────────────────

def _recording_llm(prompts: list[str], answers: list[str]):
    """LLM fake that records every prompt and cycles canned answers."""
    class RecordingLLM:
        def __init__(self):
            self._i = 0

        def invoke(self, prompt):
            prompts.append(prompt)
            answer = answers[self._i % len(answers)]
            self._i += 1
            return type("R", (), {"content": json.dumps({
                "answer": answer, "sources": []})})()

    return RecordingLLM()


def test_chat_memory_replays_prior_turns_and_persists(repo):
    _seed(repo)
    prompts: list[str] = []
    llm = _recording_llm(prompts, ["Critical errors first.", "As I said, start with critical errors."])
    first = answer_question(repo, RUN_ID, "which errors are critical?", llm=llm, user_key="user-1")
    second = answer_question(repo, RUN_ID, "and the first one you mentioned?", llm=llm, user_key="user-1")

    # First prompt has no history yet; the second replays the first turn.
    # (The system prompt mentions 'Conversation so far'; the injected block
    # uses the distinct marker 'Conversation history'.)
    assert "Conversation history" not in prompts[0]
    assert "Conversation history" in prompts[1]
    assert "which errors are critical?" in prompts[1]
    assert "Critical errors first." in prompts[1]

    # The new turn was persisted, oldest first, in conversation order.
    history = repo.fetch_chat_history(RUN_ID, "user-1")
    assert len(history) == 2
    assert history[0]["question"] == "which errors are critical?"
    assert history[0]["answer"] == "Critical errors first."
    assert history[1]["question"] == "and the first one you mentioned?"
    assert history[1]["answer"] == "As I said, start with critical errors."
    assert second["answer"] == "As I said, start with critical errors."


def test_chat_memory_is_scoped_per_user(repo):
    _seed(repo)
    prompts: list[str] = []
    llm = _recording_llm(prompts, ["For user one.", "For user two."])
    answer_question(repo, RUN_ID, "question from user one", llm=llm, user_key="user-1")
    answer_question(repo, RUN_ID, "question from user two", llm=llm, user_key="user-2")

    # Each user sees only their own thread...
    assert len(repo.fetch_chat_history(RUN_ID, "user-1")) == 1
    assert len(repo.fetch_chat_history(RUN_ID, "user-2")) == 1
    # ...and user-2's second prompt does not leak user-1's turn.
    assert "question from user one" not in prompts[1]
    assert "question from user two" in prompts[1]


def test_chat_memory_best_effort_when_table_missing(repo):
    _seed(repo)
    original_save = repo.save_chat_turn
    original_fetch = repo.fetch_chat_history

    def missing(*args, **kwargs):
        raise RuntimeError("relation agent_chat_messages does not exist")

    repo.save_chat_turn = missing
    repo.fetch_chat_history = missing
    try:
        stub = StubLLM(json.dumps({"answer": "still answers", "sources": []}))
        out = answer_question(repo, RUN_ID, "hi", llm=stub, user_key="user-1")
        assert out["answer"] == "still answers"   # stateless fallback
    finally:
        repo.save_chat_turn = original_save
        repo.fetch_chat_history = original_fetch


def test_chat_memory_keeps_only_recent_turns(repo):
    _seed(repo)
    prompts: list[str] = []
    llm = _recording_llm(prompts, ["ok"])
    for i in range(1, 9):                          # q1..q8 stored
        answer_question(repo, RUN_ID, f"question number {i}", llm=llm, user_key="user-1")
    # Everything is stored; the default read window is the last 6.
    assert len(repo.fetch_chat_history(RUN_ID, "user-1", limit=100)) == 8
    assert len(repo.fetch_chat_history(RUN_ID, "user-1")) == 6
    answer_question(repo, RUN_ID, "question number 9", llm=llm, user_key="user-1")

    last_prompt = prompts[-1]
    assert "Conversation history" in last_prompt
    assert "question number 8" in last_prompt       # recent turn present
    assert "question number 1" not in last_prompt   # trimmed beyond the window
    assert "question number 2" not in last_prompt


def test_failed_answer_is_not_persisted(repo):
    _seed(repo)
    stub = StubLLM("not json at all")
    with pytest.raises(RuntimeError):
        answer_question(repo, RUN_ID, "hi", llm=stub, user_key="user-1")
    assert repo.fetch_chat_history(RUN_ID, "user-1") == []
