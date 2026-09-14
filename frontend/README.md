# MEYAAR frontend

The MEYAAR web interface is a Next.js application for uploading geospatial
data, reviewing vector and map-image quality results, managing teams, and
exporting reports. It supports Arabic and English, RTL/LTR layouts, and light
and dark themes.

## Run locally

Start the FastAPI backend from the repository root first. Then run:

```powershell
npm.cmd install
npm.cmd run dev
```

Open [http://localhost:3000](http://localhost:3000). API requests are proxied
to `http://127.0.0.1:8000` by `next.config.ts`.

## Delivery checks

```powershell
npm.cmd run lint
npm.cmd run build
```

Runtime configuration and complete project setup are documented in the root
`README.md`.
