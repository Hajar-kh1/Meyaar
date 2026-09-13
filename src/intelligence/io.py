from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

import geopandas as gpd
from pypdf import PdfReader


VECTOR_EXTENSIONS = {
    ".geojson",
    ".json",
    ".gpkg",
    ".zip",
}


def _normalize_geojson(data: dict) -> dict:
    if data.get("type") != "FeatureCollection":
        raise ValueError("The uploaded file must contain a FeatureCollection.")

    return {
        "type": "FeatureCollection",
        "features": data.get("features") or [],
    }


def load_vector_upload(
    filename: str,
    content: bytes,
) -> dict:
    suffix = Path(filename).suffix.lower()

    if suffix in {".geojson", ".json"}:
        try:
            return _normalize_geojson(
                json.loads(
                    content.decode("utf-8-sig")
                )
            )
        except Exception as exc:
            raise ValueError(
                "Invalid GeoJSON file."
            ) from exc

    if suffix not in VECTOR_EXTENSIONS:
        raise ValueError(
            "Supported comparison formats are GeoJSON, JSON, GPKG and zipped Shapefile."
        )

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / filename
        path.write_bytes(content)

        try:
            if suffix == ".zip":
                gdf = gpd.read_file(
                    f"zip://{path}"
                )
            else:
                gdf = gpd.read_file(path)
        except Exception as exc:
            raise ValueError(
                f"Could not read vector file: {filename}"
            ) from exc

        if gdf.empty:
            return {
                "type": "FeatureCollection",
                "features": [],
            }

        if gdf.crs:
            try:
                gdf = gdf.to_crs(4326)
            except Exception:
                pass

        return json.loads(
            gdf.to_json()
        )


def preview_geojson(
    geojson: dict,
    limit: int = 800,
) -> dict:
    return {
        "type": "FeatureCollection",
        "features": (
            geojson.get("features") or []
        )[:limit],
    }


def extract_attachment_context(
    filename: str,
    content: bytes,
) -> str:
    suffix = Path(filename).suffix.lower()

    if suffix in {".geojson", ".json"}:
        data = load_vector_upload(
            filename,
            content,
        )

        features = data.get("features") or []
        fields = set()

        for feature in features[:200]:
            fields.update(
                (feature.get("properties") or {}).keys()
            )

        sample = [
            feature.get("properties") or {}
            for feature in features[:5]
        ]

        return json.dumps(
            {
                "filename": filename,
                "type": "geospatial_dataset",
                "feature_count": len(features),
                "fields": sorted(fields),
                "sample_properties": sample,
            },
            ensure_ascii=False,
            indent=2,
        )

    if suffix == ".pdf":
        reader = PdfReader(
            io.BytesIO(content)
        )

        text = "\n".join(
            page.extract_text() or ""
            for page in reader.pages[:20]
        )

        return text[:20000]

    if suffix in {
        ".txt",
        ".md",
        ".csv",
    }:
        return content.decode(
            "utf-8",
            errors="ignore",
        )[:20000]

    if suffix in {".gpkg", ".zip"}:
        data = load_vector_upload(
            filename,
            content,
        )

        features = data.get("features") or []
        fields = set()

        for feature in features[:200]:
            fields.update(
                (feature.get("properties") or {}).keys()
            )

        return json.dumps(
            {
                "filename": filename,
                "type": "geospatial_dataset",
                "feature_count": len(features),
                "fields": sorted(fields),
            },
            ensure_ascii=False,
            indent=2,
        )

    raise ValueError(
        "Unsupported attachment. Use PDF, TXT, CSV, GeoJSON, GPKG or zipped Shapefile."
    )