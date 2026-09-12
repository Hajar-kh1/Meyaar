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

`agent/tests/test_analysis_retrieval.py` (25 cases, chat/retrieval) and the
"complete feature records feeding the generation path" section of
`agent/tests/test_analysis.py` (6 cases: prompt completeness, template citation,
LLM citation, bounded prompt for complex geometry, light-context fallback,
failure logged not fatal) — see `docs/testing.md`.
