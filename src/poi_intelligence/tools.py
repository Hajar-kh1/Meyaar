from __future__ import annotations

from collections import Counter
from typing import Any

from src.geosa_rag.service import retrieve


def _properties(feature: dict) -> dict:
    return feature.get("properties") or {}


def _coordinates(feature: dict) -> list | None:
    geometry = feature.get("geometry") or {}

    if geometry.get("type") != "Point":
        return None

    coordinates = geometry.get("coordinates")

    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return None

    return coordinates


def _value(
    properties: dict,
    keys: tuple[str, ...],
) -> Any:
    for key in keys:
        value = properties.get(key)

        if value not in (None, ""):
            return value

    return None


def analyze_poi_quality(geojson: dict) -> dict:
    features = geojson.get("features") or []

    missing_name = []
    missing_category = []
    missing_coordinates = []
    invalid_coordinates = []
    duplicates = []

    categories = Counter()
    seen = {}

    for index, feature in enumerate(features):
        properties = _properties(feature)

        feature_id = str(
            _value(
                properties,
                (
                    "id",
                    "feature_id",
                    "objectid",
                    "OBJECTID",
                ),
            )
            or feature.get("id")
            or index
        )

        name = _value(
            properties,
            (
                "name",
                "name_ar",
                "name_en",
                "poi_name",
            ),
        )

        category = _value(
            properties,
            (
                "category",
                "type",
                "class",
                "subtype",
            ),
        )

        coordinates = _coordinates(feature)

        if not name:
            missing_name.append(feature_id)

        if not category:
            missing_category.append(feature_id)
        else:
            categories[str(category)] += 1

        if coordinates is None:
            missing_coordinates.append(feature_id)
            continue

        try:
            lon = float(coordinates[0])
            lat = float(coordinates[1])
        except (TypeError, ValueError):
            invalid_coordinates.append(feature_id)
            continue

        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            invalid_coordinates.append(feature_id)

        duplicate_key = (
            str(name or "").strip().lower(),
            round(lon, 6),
            round(lat, 6),
        )

        if duplicate_key in seen:
            duplicates.append(feature_id)
        else:
            seen[duplicate_key] = feature_id

    affected = set(
        missing_name
        + missing_category
        + missing_coordinates
        + invalid_coordinates
        + duplicates
    )

    total = len(features)

    quality_score = (
        round((1 - len(affected) / total) * 100, 2)
        if total
        else 100.0
    )

    return {
        "total_pois": total,
        "affected_pois": len(affected),
        "quality_score": quality_score,
        "missing_name_count": len(missing_name),
        "missing_category_count": len(missing_category),
        "missing_coordinates_count": len(missing_coordinates),
        "invalid_coordinates_count": len(invalid_coordinates),
        "duplicate_count": len(duplicates),
        "missing_name": missing_name,
        "missing_category": missing_category,
        "missing_coordinates": missing_coordinates,
        "invalid_coordinates": invalid_coordinates,
        "duplicates": duplicates,
        "category_distribution": dict(categories.most_common()),
    }


def get_poi_summary(geojson: dict) -> dict:
    features = geojson.get("features") or []

    categories = Counter()

    for feature in features:
        properties = _properties(feature)

        category = _value(
            properties,
            (
                "category",
                "type",
                "class",
                "subtype",
            ),
        )

        if category:
            categories[str(category)] += 1

    return {
        "total_pois": len(features),
        "categories": dict(categories.most_common()),
        "category_count": len(categories),
    }


def search_geosa(question: str, top_k: int = 5) -> list[dict]:
    return retrieve(question, top_k=top_k)