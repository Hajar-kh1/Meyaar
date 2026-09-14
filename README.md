# MEYAAR

MEYAAR is an intelligent geospatial data quality and standards workspace for inspecting, validating, comparing, and improving geospatial datasets and map products.

It combines deterministic spatial validation, agentic analysis, GeoSA-grounded RAG, safe remediation, dataset comparison, and AI-assisted geospatial workflows in one platform.

> MEYAAR is an MVP and research project. It supports geospatial quality and standards-review workflows; it is not an official GeoSA certification tool.

## Project Status

MEYAAR is delivered as a complete full-stack MVP for local deployment and demonstration. The repository includes the web application, REST API, PostGIS development environment, deterministic validation pipelines, AI-assisted workflows, automated tests, and local setup documentation.

| Item | Details |
| --- | --- |
| Delivery type | Full-stack academic MVP |
| User interface | Arabic and English with RTL/LTR support |
| Backend API | FastAPI with interactive OpenAPI documentation |
| Spatial database | PostgreSQL 16 + PostGIS 3.5 via Docker Compose |
| Supported environment | Windows development environment |
| Source license | MIT; third-party assets retain their own terms |

## Contents

- [Features](#features)
- [Intelligence Workspace](#intelligence-workspace)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Technology Stack](#technology-stack)
- [Local Setup](#local-setup-windows)
- [Verification and Tests](#verification-and-tests)
- [Design and Security](#important-design-principles)

## Features

### Vector Data Quality

- Upload GeoJSON, GeoPackage, CSV, GeoParquet, or a zipped Shapefile.
- Automatically detect supported vector inputs and identify the relevant layer type.
- Use lightweight metadata-based layer detection to avoid unnecessary full-file inspection during classification.
- Validate road and building datasets using deterministic PostGIS rules.
- Detect issues such as overlaps, duplicates, invalid geometries, missing geometries, overshoots, undershoots, and general GIS data-quality problems.
- Prioritize findings by severity.
- Calculate Quality Score using affected features rather than total findings.
- Display detected issues spatially on the map.

### Safe Remediation & Revalidation

- Classify findings as auto-fixable, review-required, or no-action.
- Apply only policy-approved geometry repairs automatically.
- Preserve before/after remediation audit records.
- Automatically re-run deterministic validation after applied fixes.
- Verify whether each applied fix was actually resolved.
- Compare quality before and after remediation.
- Export a separate corrected GeoJSON copy without overwriting the uploaded source file.

### Map Image Quality

- Upload PNG, JPG, JPEG, TIF, or TIFF map images.
- Analyze map images using the vision pipeline.
- Detect missing map elements such as:
  - Title
  - Legend
  - Scale
  - North arrow
- Add an element manually or request a preview-only suggestion.
- Preview, reposition, remove, and download a new image without modifying the original.

## Intelligence Workspace

MEYAAR includes additional AI-assisted geospatial workflows built on top of the core quality engine.

### GeoSA Intelligence

A conversational RAG assistant grounded in official GeoSA reference documents.

- Ask questions about Saudi geospatial standards and guidelines.
- Retrieve relevant evidence using a FAISS vector index and multilingual embeddings.
- Generate answers grounded in retrieved GeoSA passages.
- Display document and page sources with the answer.
- Support file attachments for contextual analysis.
- Support Arabic voice input and text-to-speech interaction.
- Keep uploaded-document content separate from official GeoSA evidence.
- Avoid treating unsupported recommendations or thresholds as official GeoSA requirements.

GeoSA Intelligence uses:

```text
Question / Attachment
        ↓
Multilingual Embeddings
        ↓
FAISS Retrieval
        ↓
Relevant GeoSA Evidence
        ↓
LLM
        ↓
Grounded Answer + Sources
```

### POI Intelligence

An agentic workflow for analyzing Points of Interest datasets.

The POI agent dynamically selects the tools needed for the user's question.

Available capabilities include:

- POI quality analysis.
- Missing-name detection.
- Missing-category detection.
- Invalid-coordinate detection.
- Duplicate POI detection.
- Category distribution analysis.
- POI dataset summaries.
- GeoSA RAG retrieval when standards evidence is required.

```text
POI Dataset + Question
        ↓
POI Agent
        ↓
Dynamic Tool Selection
        ↓
POI Quality | POI Summary | GeoSA RAG
        ↓
Tool Results
        ↓
AI Interpretation
```

Deterministic quality findings remain separate from GeoSA interpretation so that retrieved standards evidence is not treated as a validation result by itself.

### Dataset Compare

Compare any two compatible geospatial datasets, even when they come from different sources and use different feature IDs.

The comparison includes:

- Dataset compatibility.
- Geometry type compatibility.
- Schema and field differences.
- Feature counts.
- Spatial matching.
- Matched features.
- Features only in Dataset A.
- Features only in Dataset B.
- Geometry differences.
- Dataset quality comparison.
- AI interpretation of the comparison results.

Spatial matching can compare features based on their geographic relationship rather than requiring identical IDs.

> Difference does not automatically mean error. Dataset Compare reports differences first and leaves compliance decisions to explicit validation rules and standards evidence.

Typical use cases include comparing government and vendor datasets, evaluating alternative data sources, reviewing contractor deliveries, and comparing dataset versions.

### GeoRFP Assistant

An AI-assisted workspace for preparing geospatial technical requirements for RFPs.

- Enter a project or procurement description.
- Retrieve relevant GeoSA evidence.
- Generate GIS-focused technical requirements.
- Generate geospatial data deliverable requirements and acceptance considerations.
- Show supporting GeoSA sources.
- Avoid inventing unsupported numeric thresholds, formats, timelines, or requirements.
- Copy generated requirements for use in procurement documents.

```text
Project Description
        ↓
GeoSA Retrieval
        ↓
Relevant Standards Evidence
        ↓
GeoRFP Assistant
        ↓
GIS Requirements + Sources
```

## Reporting & Delivery

MEYAAR can generate analysis outputs for both individual datasets and batch workflows.

- Structured analysis results.
- Quality Score and affected-feature statistics.
- Detailed findings.
- Before/after remediation information.
- Revalidation results.
- PDF quality reports.
- Arabic audio summaries.
- Email delivery.
- Batch analysis reporting for multiple uploaded files.

Delivery stages are handled independently so a PDF, audio, or email failure does not invalidate the core analysis result.

## Quality Score

MEYAAR calculates quality based on unique affected features rather than the total number of findings.

```text
Error Rate = Affected Features / Total Features

Quality Score = 1 - Error Rate
```

A feature is counted only once even if multiple findings are detected on it.

Example:

```text
Total Features:     100
Affected Features:   20
Total Findings:      27

Error Rate:          20%
Quality Score:       80%
```

## Architecture

```text
                         Next.js Frontend
                                │
                                ▼
                         FastAPI Backend
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
        Vector Pipeline    Vision Pipeline   Intelligence
              │                                   │
              ▼                    ┌──────────────┼──────────────┐
      PostgreSQL + PostGIS         │              │              │
              │                    ▼              ▼              ▼
              ▼               GeoSA RAG       POI Agent     Dataset Compare
      Validation Rules              │
              │                     ▼
              ▼                GeoRFP Assistant
       Analysis Agent
              │
              ▼
        Safe Remediation
              │
              ▼
         Revalidation
              │
              ▼
     PDF + Arabic Audio + Email
```

## Vector Processing Flow

```text
Upload
  ↓
Input Detection
  ↓
Fast Layer Detection
  ↓
Vector Loading
  ↓
PostGIS Insertion
  ↓
Deterministic Validation
  ↓
Error Analysis Agent
  ↓
Safe Remediation
  ↓
Deterministic Revalidation
  ↓
Quality Before / After
  ↓
Map + Report + Audio + Delivery
```

## Project Structure

```text
Meyaar/
├── frontend/                    # Next.js user interface
├── src/
│   ├── api/                     # FastAPI routes, auth, delivery, contracts
│   ├── insertion/               # Vector ingestion and layer detection
│   ├── validation/              # PostGIS validation rules
│   ├── vision/                  # Map-image analysis pipeline
│   ├── reporting/               # Report generation
│   ├── voice/                   # Arabic audio summaries
│   ├── geosa_rag/               # GeoSA retrieval and grounded Q&A
│   ├── poi_intelligence/        # Agentic POI analysis
│   ├── dataset_compare/         # Geospatial dataset comparison
│   ├── georfp/                  # GeoRFP generation
│   └── intelligence/            # Intelligence API integration
├── agent/
│   ├── graph/                   # Error-analysis workflow
│   ├── remediation/             # Safe remediation policy
│   ├── map_elements/            # Map-element suggestions
│   └── api/                     # Agent API routes
├── data/
│   └── geosa_docs/              # GeoSA reference documents
├── vector_store/
│   └── geosa/                   # Local FAISS GeoSA index
├── docker-compose.vector-dev.yml
├── pyproject.toml
├── uv.lock
├── .env.example
├── README.md
└── LICENSE
```

## Technology Stack

### Backend

- Python
- FastAPI
- PostgreSQL
- PostGIS
- GeoPandas
- Pyogrio
- Shapely
- SQLAlchemy
- LangGraph

### AI & Retrieval

- Groq
- FAISS
- Sentence Transformers
- Multilingual MiniLM embeddings
- RAG
- Agentic tool selection

### Frontend

- Next.js
- React
- TypeScript

## Local Setup (Windows)

### Prerequisites

Install the following before starting the project:

- [Git](https://git-scm.com/)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Node.js](https://nodejs.org/) 20 or later
- [uv](https://docs.astral.sh/uv/) for Python environment and dependency management
- Python 3.12 or later, managed automatically by `uv` when available

Install `uv` once, then run Python commands from the repository root.

`uv sync` creates and maintains `.venv` automatically from `uv.lock`; manual activation is not required.

### 1. Configure Local Environment

Create `.env` from `.env.example` and provide your local credentials.

Never commit `.env`, credentials, or API keys.

Required database configuration:

```env
MEYAAR_DATABASE_URL=postgresql+psycopg2://postgres@127.0.0.1:55432/meyaar_db
```

AI-powered features also require the corresponding API credentials configured in `.env`.

| Variable | Required | Purpose |
| --- | --- | --- |
| `MEYAAR_DATABASE_URL` | Yes | PostgreSQL/PostGIS connection string |
| `MOONDREAM_API_KEY` | For vision AI | Map-image analysis provider credential |
| `MOONDREAM_MODEL_ID` | For vision AI | Vision model identifier |
| `BREVO_API_KEY` | For Brevo delivery | Transactional report email delivery |
| `BREVO_SENDER_EMAIL` | For Brevo delivery | Verified sender address |
| `MEYAAR_SMTP_*` | For SMTP delivery | Alternative outgoing email configuration |

### 2. Start PostGIS

Make sure Docker Desktop is running.

From the repository root:

```powershell
docker compose -f docker-compose.vector-dev.yml up -d
docker ps
```

### 3. Start the Backend

```powershell
uv sync
uv run uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --reload
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

### 4. Start the Frontend

Open another PowerShell terminal:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open:

```text
http://localhost:3000
```

### Local Service Endpoints

| Service | URL |
| --- | --- |
| MEYAAR web application | [http://localhost:3000](http://localhost:3000) |
| Backend API | [http://127.0.0.1:8000](http://127.0.0.1:8000) |
| Interactive API documentation | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| PostGIS | `127.0.0.1:55432` |

### 5. Stop the Database

```powershell
docker compose -f docker-compose.vector-dev.yml down
```

## Verification and Tests

Run backend tests from the repository root:

```powershell
uv run pytest
```

Run frontend quality checks from the `frontend` directory:

```powershell
npm.cmd run lint
npm.cmd run build
```

For a quick delivery check, confirm that Docker reports `meyaar-postgis-dev` as healthy, the API documentation opens successfully, and the web application can register or sign in a user.

## Troubleshooting

### Login displays `Failed to fetch`

The frontend cannot reach the API. Keep the backend terminal running and verify that [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) opens in the browser.

### Database connection fails

Start Docker Desktop, run the PostGIS Compose command again, and check the container state:

```powershell
docker compose -f docker-compose.vector-dev.yml up -d
docker ps
```

### Port already in use

Stop the older development process using port `3000`, `8000`, or `55432`, then start the affected service again.

## GeoSA RAG Index

Official GeoSA reference documents are stored locally under:

```text
data/geosa_docs/
```

The generated retrieval index is stored under:

```text
vector_store/geosa/
```

The index only needs to be rebuilt when the GeoSA document collection changes.

## Safe Remediation Policy

MEYAAR does not silently alter uploaded source data.

1. The deterministic validation engine detects an issue.
2. The analysis agent interprets the detected finding.
3. The remediation policy determines whether the issue is auto-fixable, review-required, or no-action.
4. Only policy-approved repairs may be applied automatically.
5. Applied repairs are recorded for auditing.
6. PostGIS validation runs again after remediation.
7. MEYAAR verifies whether the original finding was actually resolved.
8. The corrected dataset is provided separately from the original upload.
9. Heuristic topology issues such as overshoots and undershoots can remain review-required.
10. Map-image changes remain preview-based and do not modify the original image.

## Important Design Principles

MEYAAR separates deterministic geospatial validation from AI interpretation.

- PostGIS rules detect vector quality issues.
- AI explains and prioritizes already detected findings.
- Revalidation verifies fixes deterministically.
- GeoSA RAG provides standards evidence but does not independently certify compliance.
- Dataset differences are not automatically classified as errors.
- Generated recommendations must not be presented as official GeoSA requirements unless supported by retrieved evidence.

## Security

The repository intentionally ignores secrets and local-only files, including:

- `.env`
- API keys
- credentials
- certificates and private keys
- virtual environments
- caches
- `node_modules`

Use `.env.example` only as a configuration template.

## Disclaimer

MEYAAR is an academic MVP and research prototype designed to support geospatial quality assurance and standards-review workflows.

Quality Scores and AI-generated interpretations are MEYAAR system indicators and should not be interpreted as official GeoSA certification or regulatory approval.

## License

Code is distributed under the repository's MIT License.

Third-party datasets, map imagery, standards, models, and reference documents retain their respective licenses and usage conditions.
