-- ============================================================
-- MEYAAR — AGENT CHAT MEMORY (conversation history per run/user)
-- Owned by: Agentic AI role (agent/)
--
-- One row per chat turn (question -> answer) about a validation run,
-- scoped to the authenticated user (user_key) so each user's thread is
-- private and the UI needs no session plumbing: the backend keys on
-- (run_id, user_key) automatically.
--
-- The chat service (agent/chat.py) reads the last N turns for a
-- (run_id, user_key) before answering and injects them into the prompt
-- as "Conversation so far", then stores the new turn — so follow-ups
-- ("and the first error I asked about?") keep their context without
-- re-explaining, and each answer stays grounded in the run's stored
-- analyses/summary (the two sources of truth together).
--
-- Sources JSONB mirrors the ChatResponse sources (rule_id@feature_id)
-- filtered to ids that exist in the run context.
-- ============================================================

CREATE TABLE IF NOT EXISTS public.agent_chat_messages (
    chat_id    BIGSERIAL PRIMARY KEY,
    run_id     UUID NOT NULL,
    user_key   TEXT NOT NULL,
    question   TEXT NOT NULL,
    answer     TEXT NOT NULL,
    sources    JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_chat_messages_run_user
    ON public.agent_chat_messages (run_id, user_key, chat_id);
