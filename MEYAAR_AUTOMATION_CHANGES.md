# Meyaar automation changes

This build keeps the existing API, PostGIS, Vision, Agent, frontend, and report code intact while moving inspection routing behind one Meyaar orchestration entry point.

Implemented:
- `agent/orchestrator.py` routes one uploaded file to the existing Vector or Vision pipeline.
- `/inspect` calls the orchestrator instead of owning Vector/Image execution branches.
- Vector quality now exposes feature-based `error_rate` and `quality_score` using unique affected features.
- Validation counts unique affected feature IDs from the full validation run, not the limited findings list.
- Existing `compliance_score` is preserved as an alias to `quality_score` for frontend compatibility.
- After an applied safe auto-fix, vector validation runs again and returns `validation_after`, `quality_before`, `quality_after`, and `quality_improvement`.
- Multi-file `/inspect` returns vector-folder average quality plus aggregate feature/finding counts.

No new API endpoint was added. Image quality logic was not changed.
