# MEYAAR

MEYAAR is a full-stack geospatial quality workspace for teams. It validates vector GIS data, analyses map images, prioritizes detected issues, and offers safe, reviewable remediation suggestions.

> This is an MVP and research project. It supports quality-review workflows; it is not an official certification tool.

## Features

### Vector data quality

- Upload GeoJSON, GeoPackage, CSV, GeoParquet, or a zipped Shapefile.
- Automatically identify vector versus map-image uploads.
- Detect road and building quality issues using PostGIS rules.
- Prioritize findings from critical/high to low severity.
- Apply only policy-approved geometry repairs and keep before/after audit records.
- Export a separate corrected GeoJSON copy; the uploaded source file is never overwritten.

### Map image quality

- Upload PNG, JPG, JPEG, TIF, or TIFF map images.
- Detect missing map title, legend, scale, and north arrow.
- Add an element manually or ask the map-elements agent for a preview-only suggestion.
- Preview, reposition, remove, and download a new image without changing the original image.

### Team workspace

- Authentication, roles, teams, leaders, and members.
- Team activity summaries and per-member analysis statistics.
- Saved analyses and JSON/PDF reporting.
- Arabic/English interface with light and dark themes.

## Architecture

```text
Next.js frontend
       │
       ▼
FastAPI backend ──────► Agent services
       │                     ├─ validation/remediation agent
       ▼                     └─ map-elements suggestion agent
PostgreSQL + PostGIS
       │
       ▼
Spatial validation rules, saved analyses, and remediation audit records
```

## Project structure

```text
Meyaar/
├── frontend/                 # Next.js user interface
├── src/
│   ├── api/                  # FastAPI routes, auth, and contracts
│   ├── validation/           # PostGIS validation rules
│   ├── insertion/            # Vector ingestion
│   └── vision/               # Map-image analysis pipeline
├── agent/
│   ├── graph/                # Error analysis workflow
│   ├── remediation/          # Safe remediation policy
│   ├── map_elements/         # Preview-only map element suggestions
│   └── api/                  # Agent API routes
├── docker-compose.vector-dev.yml
├── requirements.txt
└── .env.example
```

## Run locally (Windows)

### 1. Configure local environment

Create a local `.env` from `.env.example` and set your own values. Never commit `.env`, credentials, or API keys.

Required database setting:

```env
MEYAAR_DATABASE_URL=postgresql+psycopg2://postgres@127.0.0.1:55432/meyaar_db
```

### 2. Start PostGIS with Docker

Make sure Docker Desktop is running, then from the repository root:

```powershell
docker compose -f docker-compose.vector-dev.yml up -d
docker ps
```

### 3. Start the backend

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn src.api.main:app --reload --port 8000
```

API documentation: `http://127.0.0.1:8000/docs`

### 4. Start the frontend

Open a new terminal:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open `http://localhost:3000`.

### Stop the database

```powershell
docker compose -f docker-compose.vector-dev.yml down
```

## Safe remediation policy

MEYAAR does not silently alter user data:

1. The validation engine detects an issue.
2. The agent classifies it as auto-fixable, review-required, or no-action.
3. Only approved geometry repairs run automatically and are audited.
4. Heuristic topology issues, such as overshoots and undershoots, require human review on the map.
5. Map-image suggestions are previews only; the user may accept, edit, remove, or download a separate copy.

## Security

The repository intentionally ignores secrets and local-only files, including `.env`, key/certificate files, credential files, virtual environments, caches, and `node_modules`. Use `.env.example` files as templates only.

## License

Code is distributed under the repository's MIT License. Third-party datasets, map imagery, standards, and reference documents retain their own licenses.
