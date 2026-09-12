# Complete analysis retrieval (grounded chat + per-finding generation)

## The problem this solves

Grounded chat used to answer from a hand-picked slice of a run: the agent's
per-error explanations, the severity counts, the rule registry and the
remediation audit. Questions about the analysis *itself* — street length and
width, building length/width, plot dimensions, building footprint/area,
distances, percentages, counts, coordinates — could not be answered, because
those values were never retrieved, and any attempt to "add a few more fields"
would have hard-coded a schema that goes stale as soon as the pipeline stores
something new.

## The rule now: retrieve the record, not a field list

`agent/retrieval.py` builds an **unfiltered** dataset for a run:

| Part | Source | What it carries |
|---|---|---|
| `analysis_records` | `public.saved_analyses.result_payload` (JSONB), matched on `result_payload->>'run_id'` | the **whole saved payload object** — every key the pipeline wrote (insertion, validation findings + geometry, quality metrics, layer/`fixed_layer_geojson`, analysis output, and anything added later) plus the analysis metadata (id, filename, type, status, compliance score, error count) |
| `feature_data` | one query per layer: `to_jsonb(t) - 'geometry'` + PostGIS measurement columns | the **complete feature record**: every attribute column the layer table has, discovered at query time, merged with `geometry_type, srid, is_valid, is_empty, length_m, area_m2, vertex_count, centroid, bbox` and the geometry (GeoJSON coordinates) |
| `findings` | `public.validation_results` | the raw engine rows including `details` — the numbers the engine computed (areas, distances, coordinates, tolerances, group sizes) |
| `available_fields` | derived from all of the above | an index of **every field name present**, with an example value, its type and where it was found — this is what maps a user's wording ("street length", "plot dimensions") onto the project's real field names |
| `analyses` / `summary` / `rules` / `remediation` | agent tables + registry | the existing grounded context (explanations, counts, policy, audit) |

Which features are described:

1. every `feature_id` in the run's validation results,
2. every `related_features` id the agent recorded,
3. every feature id *mentioned* in a finding's `details` ("overlaps BLD_157"),
4. every feature id referenced by the stored payload itself (`layer_geojson`,
   `validation.errors`, report rows) — so a **clean run with zero findings**
   still has its layer features measured.

Nothing is scoped by a whitelist of keys or columns anywhere in this path.

## Where it is used

* **Per-finding generation** (`agent/graph/nodes.py`): `prepare_groups` fetches
  the COMPLETE record per referenced feature through `_complete_contexts`
  (primary `fetch_feature_records`, fallback `fetch_related_features` on older
  repositories, and a failed read is logged into the run's `errors` instead of
  silently dropping context). So the group prompt carries every layer
  attribute plus the measurements, the prompt tells the model to cite stored
  values with units, and the deterministic template path appends
  `_measurement_clause` — a grounded echo of the numeric facts stored for the
  feature (measurements and numeric attributes + bbox; free-text labels are
  skipped, absent values contribute nothing).
* `agent/chat.py::build_chat_context` adds `analysis_records`, `feature_data`,
  `findings`, `available_fields` and `data_counts` to the prompt context, then
  passes the result through `retrieval.fit_context` (generic size guard).
* The system prompt (rules 8-12) instructs the model to answer from those
  actual stored values, map wording to real field names, preserve units
  exactly as stored, say plainly when a value is not available, and answer
  broad requests with a structured summary of every meaningful field.
* `agent/tools/__init__.py` exposes the same data as tools:
  `get_analysis_record(run_id)`, `get_feature_record(layer_name, feature_id)`,
  `list_analysis_fields(run_id)`.
* `GET /api/validation/{run_id}/record` returns the same dataset (whole
  payloads + feature records + field index) for the UI/reporting layer.

## Size handling (generic, never field-based)

`fit_context` applies escalating caps on **list length and string length**
only: dictionaries always keep every key (keys are the analysis fields), long
lists keep their first N items plus an `{"_omitted_items": n}` marker, and long
strings (large GeoJSON) are head-truncated with a marker. The result carries
`context_chars` and `context_truncated` so the truncation is visible rather
than silent. Retrieval itself caps records per part
(`MAX_ANALYSIS_RECORDS`, `MAX_FEATURE_RECORDS`, …) and reports omissions in
`data_truncation`.

## Failure behaviour

Every retrieval call is best-effort, like chat memory: a database without
`public.saved_analyses`, an unreachable layer table or a driver error yields
an empty section, and the model is told the data is unavailable — the chat
still answers the rest of the question instead of erroring, and never invents
the missing value.

## Live check (real PostGIS dev DB)

```
fetch_analysis_records -> 1 record for run 0a551062-…, 19 top-level payload keys
roads fetch_feature_records -> fields: area_m2, bbox, centroid, city, feature_id,
  geometry, geometry_type, highway, is_empty, is_valid, length_m, name, name_ar,
  srid, test_expected_error_type, test_expected_rule_id, vertex_count
available_fields: 74 field names, context fits in ~11k chars (untruncated)
```

Real chat answers (deepseek-chat, run `43a44b94-…`, roads layer):
* "What is the street length and width?" →
  *"…Length is stored as `length_m` … Olaya Street … 10010.707593624815 m …
  Al Nakheel Street … 996.7751294876401 m. This analysis does not store a width
  value for any road feature, so street width is not available in this run."*
* "Give me all the analysis information." → full structured summary: quality
  score/error rate percentages, severity split, each finding group with counts
  and recommendations, remediation audit, per-feature measurements, insertion
  metadata.
* "What are the plot dimensions and setbacks?" → *"…There is no plot layer, no
  plot area or frontage field, and no setback field … anywhere in the stored
  data, so plot dimensions and setbacks are not available in this analysis."*

## Upload batches (a folder / multi-file selection): chat across all files

An upload selection of several files produces one analysis per file (the
pipeline runs per file and each gets its own run id). Chat used to be bound to
a single run, so a folder of 7 files meant 7 separate conversations and no
"summarise the folder".

**Design (Option A — explicit batch):** every upload selection sends one
`batch_id` (a UUID the UI generates per selection) and
`public.saved_analyses.batch_id` stores it, so a batch is an explicit,
persistent group — re-openable later, not inferred from filenames.

| Piece | What it does |
|---|---|
| `POST /vectors/process`, `POST /images/analyze`, `POST /inspect` | accept an optional `batch_id` form field (validated by `normalize_batch_id`; malformed → 422) and echo it back in the response |
| `GET /analyses` | now returns `batch_id`, so the UI can group saved analyses |
| `require_batch_access` (`src/api/auth.py`) | all-or-nothing authorisation: if any analysis in the batch is not visible to the caller (owner, or manager/leader of the owning team) the whole batch is reported as not found |
| `fetch_analysis_records_by_batch` (Postgres + in-memory) | complete payloads for the batch, oldest first |
| `build_batch_analysis_dataset` / `build_batch_chat_context` | merges the per-file datasets: a `files` summary (name, layer, stored error count, compliance score, run), all findings, all agent analyses, every stored payload, every feature record namespaced `"<filename>#<feature_id>"` (two files can legitimately reuse feature ids), per-file remediation counts, and a dynamic field index |
| `POST /api/analyses/batch/{batch_id}/chat` · `GET /api/analyses/batch/{batch_id}` | chat + full merged dataset for a batch |
| `get_batch_analysis_record(batch_id)` tool | the same dataset for agent-side use |
| Conversation memory | keyed on the batch id (the `agent_chat_messages.run_id` column stores the *chat scope*: a run id or a batch id), so batch follow-ups keep their own thread |
| Frontend | `UploadPanel` generates one batch id per selection and sends it with every file. `AgentChat` has **no scope switch**: the scope is implied by the upload, so a folder (batch id) gets the whole-folder thread and a lone file (no batch) gets its single-run thread. Its one **Refresh chat** button clears the messages *and* calls `DELETE` on the matching chat endpoint, so the cleared conversation cannot leak back into later answers |

**Cross-upload questions ("how many files was the previous batch?").** A
conversation is scoped to ONE upload, so questions about an *earlier* upload
used to be unanswerable. The fix widens the DATA, not the scope: the context
also carries `recent_uploads` — the caller's own recent upload selections,
newest first, one entry each (`batch_id`, `uploaded_at`, exact `files` count,
`filenames`, `total_errors`, `layers`), with the upload being discussed marked
`is_current`. "The previous batch" therefore means the entry listed
immediately after the current one, and the numbers are read, never estimated.

| Piece | What it does |
|---|---|
| `fetch_recent_upload_batches(viewer, limit)` (Postgres + in-memory) | one row per upload selection: file count, names, upload time, error total; newest first. Visibility matches `require_batch_access` — own uploads, plus team uploads only for a manager/leader of that team; a viewer with no identity gets `{}` |
| `recent_uploads_summary(repo, viewer, current_scope_id)` (`agent/retrieval.py`) | shapes it for the prompt: bounded to `MAX_RECENT_UPLOADS` uploads and `MAX_RECENT_FILENAMES` names each (the file COUNT stays exact, so "how many files" is never a guess), marks `is_current`, and states the `unbatched_analyses` caveat (older analyses predate upload grouping — individual files, not batches) |
| `build_chat_context` / `build_batch_chat_context` | include `recent_uploads` only when an identified caller is supplied, so the anonymous/CLI path is unchanged. Single-run chat marks the batch the run came from, so the question resolves from per-file chat too |
| System prompt rule 14 | how to read the list: use it only for other uploads, resolve "the previous batch" from the `is_current` marker, quote the listed numbers exactly, and say plainly that an upload outside the list (or another user's) is not available |
| `get_recent_uploads(user_id, …)` tool | the same list for agent-side use |
| `GET /api/uploads/recent` | the caller's own uploads as JSON (verifiable without the model) |

Live check (real dev DB + real `deepseek-chat`, caller = the account with 37
stored analyses; chat scope = the newest upload `e62ede1a`, 3 files):

```
listed uploads: e62ede1a 3 files / a5f81f2e 4 files / 44be75ab 7 files / b7c1d2e3 3 files
                unbatched_analyses: 20

Q: how many files was the previous batch?
A: "The previous batch contained 4 files (streets/4.geojson, streets/5.geojson,
   streets/6.geojson, streets/7.geojson), all in the roads layer, with a total
   of 4 errors."

Q: which of my uploads had the most errors?
A: "...the batch of 7 files (Riyadh-street/1.geojson through
   Riyadh-street/7.geojson), which had 5 errors. The others, from newest to
   oldest: the current batch of 3 files has 1 error; the previous batch of 4
   files has 4 errors; and the oldest listed batch of 3 files has 3 errors."
```

**Honesty guard:** `notes` tells the model that per-file payloads/findings/
analyses are that run's immutable record, while `feature_data` comes from the
**live layer tables** — which hold only the most recently uploaded file's
features (each upload replaces the layer table). So a feature record describes
the current layer state, and a file without a run (e.g. a map image) is reported
as having no validation run rather than given invented findings.

**Chat refresh (`DELETE …/chat`).** The chat has a single refresh button and no
scope switch, so the scope is decided by what was uploaded: a folder (batch id)
refreshes the whole-folder thread, a lone file (no batch) refreshes its
single-run thread. Refresh clears the messages the user sees *and* the stored
turns behind them (`clear_chat_history(scope_id, user_key)` on the
`Repository`); without the second half a "cleared" conversation would keep
steering the next answer through the model's memory. Responses report what
happened (`{"scope", "scope_id", "cleared", "persisted"}`), an unknown batch is
a 404, and a database without the chat table reports `persisted: false` instead
of failing.

Live batch check (real dev DB + real model — three files of one folder):

```
counts: {'files': 3, 'files_with_a_run': 3, 'analyses': 3, 'findings': 3, 'features': 6}
files: Riyadh-street/5.geojson  (layer roads, 0 errors, score 100.0)
       Riyadh-street/6.geojson  (layer roads, 2 errors, score 0.0)
       Riyadh-street/7.geojson  (layer roads, 1 error,  score 50.0)
feature keys: 'Riyadh-street/5.geojson#1', '…/6.geojson#1', '…/7.geojson#2'  (namespaced per file)
context: 46,833 chars, truncated: false

Q: Which file has the most errors?
A: "…Riyadh-street/6.geojson, with 2 errors (both medium-severity Duplicate Roads
   findings). The other two files: Riyadh-street/7.geojson has 1 error (a critical
   Missing Geometry finding), and Riyadh-street/5.geojson has 0 errors (compliance
   score 100.0)."

Q: Summarise the whole folder.
A: per-file breakdown with measurements (e.g. "length 14734.058284410537 m",
   "geometry_type, srid, vertex_count, centroid, bbox, length_m and area_m2 are all
   null"), per-file remediation (3 pending human review, 0 auto-fixed) and a priority
   order for the folder.

Q: Are there any files with no errors at all?
A: "Yes — one file in this batch is clean: Riyadh-street/5.geojson, with 0 errors and
   a compliance score of 100.0 (2 features analyzed, no findings)."
```

Real per-finding generation (same DB/run, group `(roads, RD002)`, feature 2):

```
context keys: area_m2, bbox, centroid, city, feature_id, geometry, geometry_type,
  highway, is_empty, is_valid, length_m, name, name_ar, srid,
  test_expected_error_type, test_expected_rule_id, vertex_count
measurements: length_m=996.7751294876401, area_m2=0.0, vertex_count=2,
  bbox=[46.66615, 24.698, 46.676, 24.698], centroid=POINT(46.671075 24.698)
layer attributes: city=Riyadh, name="Al Nakheel Street", highway=residential,
  name_ar="شارع النخيل"
group prompt: 3136 chars, contains length_m: True, contains layer attributes: True

LLM explanation: "Road Undershoot candidate (RD002, heuristic, 5 m tolerance).
  Feature 2 ('Al Nakheel Street', highway=residential, Riyadh) is a 2-vertex
  LINESTRING with length_m = 996.7751294876401 m, running along latitude 24.698
  from longitude 46.676 to 46.66615 (bbox […]).
  The rule engine reports that one of its endpoints stops 2.87 m short of nearby
  road 1, which is within the 5 m heuristic tolerance. No
  related_features_context was stored, so the counterpart road's attributes …"
```

Findings whose feature row no longer exists in the layer (ids 7/4/6 after the
roads table was reloaded) get an empty context and the model says exactly that
— no invented geometry or dimensions.

## Tests

`agent/tests/test_analysis_retrieval.py` (25 cases, chat/retrieval),
`agent/tests/test_batch_chat.py` (26 cases, folder/batch scope + chat refresh) and the
"complete feature records feeding the generation path" section of
`agent/tests/test_analysis.py` (6 cases: prompt completeness, template citation,
LLM citation, bounded prompt for complex geometry, light-context fallback,
failure logged not fatal) — see `docs/testing.md`.
