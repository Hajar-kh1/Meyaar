from __future__ import annotations

import json
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from dotenv import load_dotenv
from groq import Groq
from shapely.geometry import shape
from shapely.strtree import STRtree


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

LLM_MODEL = os.getenv(
    "DATASET_COMPARE_MODEL",
    "openai/gpt-oss-20b",
)


def _client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    return Groq(api_key=api_key)


def _feature_id(
    feature: dict,
    index: int,
) -> str:
    properties = feature.get("properties") or {}

    for key in (
        "id",
        "feature_id",
        "objectid",
        "OBJECTID",
        "fid",
        "FID",
        "ogc_fid",
    ):
        value = properties.get(key)

        if value not in (None, ""):
            return str(value)

    if feature.get("id") is not None:
        return str(feature["id"])

    return f"row_{index}"


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _geometry_family(
    geometry_type: str | None,
) -> str | None:
    if not geometry_type:
        return None

    value = geometry_type.lower()

    if "point" in value:
        return "point"

    if "line" in value:
        return "line"

    if "polygon" in value:
        return "polygon"

    return value


def _dataset_geometry_family(
    geojson: dict,
) -> str | None:
    values = []

    for feature in (
        geojson.get("features") or []
    )[:500]:
        geometry = feature.get("geometry") or {}
        family = _geometry_family(
            geometry.get("type")
        )

        if family:
            values.append(family)

    if not values:
        return None

    return Counter(values).most_common(1)[0][0]


def _schema(
    geojson: dict,
) -> dict[str, str]:
    result: dict[str, str] = {}

    for feature in (
        geojson.get("features") or []
    )[:1000]:
        properties = feature.get("properties") or {}

        for key, value in properties.items():
            if value is None:
                continue

            value_type = type(value).__name__

            if key not in result:
                result[key] = value_type

            elif result[key] != value_type:
                result[key] = "mixed"

    return result


def _bbox(
    geojson: dict,
) -> list[float] | None:
    bounds = []

    for feature in geojson.get("features") or []:
        geometry = feature.get("geometry")

        if not geometry:
            continue

        try:
            bounds.append(
                shape(geometry).bounds
            )
        except Exception:
            continue

    if not bounds:
        return None

    return [
        min(item[0] for item in bounds),
        min(item[1] for item in bounds),
        max(item[2] for item in bounds),
        max(item[3] for item in bounds),
    ]


def _bbox_intersection_ratio(
    first: list[float] | None,
    second: list[float] | None,
) -> float:
    if not first or not second:
        return 0.0

    left = max(first[0], second[0])
    bottom = max(first[1], second[1])
    right = min(first[2], second[2])
    top = min(first[3], second[3])

    if right <= left or top <= bottom:
        return 0.0

    intersection = (
        (right - left)
        * (top - bottom)
    )

    area_a = max(
        (first[2] - first[0])
        * (first[3] - first[1]),
        1e-12,
    )

    area_b = max(
        (second[2] - second[0])
        * (second[3] - second[1]),
        1e-12,
    )

    return round(
        intersection / min(area_a, area_b),
        4,
    )


def compatibility_check(
    dataset_a: dict,
    dataset_b: dict,
) -> dict:
    geometry_a = _dataset_geometry_family(
        dataset_a
    )
    geometry_b = _dataset_geometry_family(
        dataset_b
    )

    schema_a = _schema(dataset_a)
    schema_b = _schema(dataset_b)

    fields_a = set(schema_a)
    fields_b = set(schema_b)

    common_fields = sorted(
        fields_a & fields_b
    )

    union = fields_a | fields_b

    schema_similarity = (
        len(common_fields) / len(union)
        if union
        else 1.0
    )

    bbox_a = _bbox(dataset_a)
    bbox_b = _bbox(dataset_b)

    spatial_overlap = _bbox_intersection_ratio(
        bbox_a,
        bbox_b,
    )

    same_geometry = (
        geometry_a == geometry_b
        and geometry_a is not None
    )

    score = 0.0

    if same_geometry:
        score += 60

    score += schema_similarity * 20
    score += min(spatial_overlap, 1) * 20

    compatible = same_geometry

    level = (
        "high"
        if score >= 75
        else "medium"
        if score >= 50
        else "low"
    )

    return {
        "compatible": compatible,
        "level": level,
        "score": round(score, 2),
        "geometry_family_a": geometry_a,
        "geometry_family_b": geometry_b,
        "schema_similarity": round(
            schema_similarity * 100,
            2,
        ),
        "spatial_overlap": round(
            spatial_overlap * 100,
            2,
        ),
        "bbox_a": bbox_a,
        "bbox_b": bbox_b,
        "reason": (
            "Datasets have compatible geometry types."
            if compatible
            else "Datasets use different geometry families and should not be directly compared."
        ),
    }


def compare_schema(
    dataset_a: dict,
    dataset_b: dict,
) -> dict:
    schema_a = _schema(dataset_a)
    schema_b = _schema(dataset_b)

    fields_a = set(schema_a)
    fields_b = set(schema_b)

    common = sorted(
        fields_a & fields_b
    )

    type_changes = []

    for field in common:
        if schema_a[field] != schema_b[field]:
            type_changes.append(
                {
                    "field": field,
                    "dataset_a": schema_a[field],
                    "dataset_b": schema_b[field],
                }
            )

    return {
        "dataset_a_fields": len(schema_a),
        "dataset_b_fields": len(schema_b),
        "common_fields_count": len(common),
        "only_a_count": len(
            fields_a - fields_b
        ),
        "only_b_count": len(
            fields_b - fields_a
        ),
        "common_fields": common,
        "only_a": sorted(
            fields_a - fields_b
        ),
        "only_b": sorted(
            fields_b - fields_a
        ),
        "type_changes": type_changes,
    }


def _quality(
    geojson: dict,
) -> dict:
    features = geojson.get("features") or []

    affected = set()
    invalid_geometry = []
    missing_geometry = []
    duplicate_geometry = []
    missing_attributes = []

    seen_geometry = set()

    all_fields = set()

    for feature in features[:2000]:
        all_fields.update(
            (feature.get("properties") or {}).keys()
        )

    for index, feature in enumerate(features):
        feature_id = _feature_id(
            feature,
            index,
        )

        geometry = feature.get("geometry")

        if not geometry:
            missing_geometry.append(feature_id)
            affected.add(feature_id)
        else:
            try:
                geom = shape(geometry)

                if geom.is_empty or not geom.is_valid:
                    invalid_geometry.append(feature_id)
                    affected.add(feature_id)

                key = geom.wkb_hex

                if key in seen_geometry:
                    duplicate_geometry.append(feature_id)
                    affected.add(feature_id)
                else:
                    seen_geometry.add(key)

            except Exception:
                invalid_geometry.append(feature_id)
                affected.add(feature_id)

        properties = feature.get(
            "properties"
        ) or {}

        if any(
            properties.get(field) in (
                None,
                "",
            )
            for field in all_fields
        ):
            missing_attributes.append(
                feature_id
            )
            affected.add(feature_id)

    total = len(features)

    score = (
        round(
            (
                1
                - len(affected)
                / total
            )
            * 100,
            2,
        )
        if total
        else 100.0
    )

    return {
        "total_features": total,
        "affected_features": len(affected),
        "quality_score": score,
        "issues": {
            "missing_geometry": len(
                missing_geometry
            ),
            "invalid_geometry": len(
                invalid_geometry
            ),
            "duplicate_geometry": len(
                duplicate_geometry
            ),
            "missing_attributes": len(
                missing_attributes
            ),
        },
    }


def _distance_meters(
    first,
    second,
) -> float:
    first_point = first.centroid
    second_point = second.centroid

    lat = math.radians(
        (
            first_point.y
            + second_point.y
        )
        / 2
    )

    dx = (
        first_point.x
        - second_point.x
    ) * 111320 * math.cos(lat)

    dy = (
        first_point.y
        - second_point.y
    ) * 110540

    return math.sqrt(
        dx * dx + dy * dy
    )


def _spatial_similarity(
    first,
    second,
    family: str,
) -> tuple[bool, float]:
    if family == "point":
        distance = _distance_meters(
            first,
            second,
        )

        similarity = max(
            0.0,
            1 - distance / 100,
        )

        return (
            distance <= 50,
            similarity,
        )

    if family == "polygon":
        try:
            union = first.union(second).area

            if not union:
                return False, 0.0

            score = (
                first.intersection(
                    second
                ).area
                / union
            )

            return score >= 0.5, score

        except Exception:
            return False, 0.0

    distance = _distance_meters(
        first,
        second,
    )

    try:
        hausdorff = first.hausdorff_distance(
            second
        ) * 111320
    except Exception:
        hausdorff = distance

    similarity = max(
        0.0,
        1 - hausdorff / 150,
    )

    return (
        hausdorff <= 60,
        similarity,
    )


def _tree_index(
    value,
    geometries: list,
    object_lookup: dict[int, int],
) -> int | None:
    if isinstance(
        value,
        (
            int,
            np.integer,
        ),
    ):
        return int(value)

    return object_lookup.get(
        id(value)
    )


def compare_spatial(
    dataset_a: dict,
    dataset_b: dict,
) -> dict:
    features_a = (
        dataset_a.get("features") or []
    )
    features_b = (
        dataset_b.get("features") or []
    )

    family = _dataset_geometry_family(
        dataset_a
    )

    valid_b = []

    for index, feature in enumerate(
        features_b
    ):
        geometry = feature.get("geometry")

        if not geometry:
            continue

        try:
            valid_b.append(
                (
                    index,
                    shape(geometry),
                )
            )
        except Exception:
            continue

    geometries_b = [
        item[1]
        for item in valid_b
    ]

    if not geometries_b:
        return {
            "matching_strategy": "spatial",
            "matched_count": 0,
            "only_a_count": len(
                features_a
            ),
            "only_b_count": len(
                features_b
            ),
            "geometry_different_count": 0,
            "matches": [],
            "only_a_indexes": list(
                range(len(features_a))
            ),
            "only_b_indexes": list(
                range(len(features_b))
            ),
        }

    tree = STRtree(
        geometries_b
    )

    object_lookup = {
        id(geometry): index
        for index, geometry in enumerate(
            geometries_b
        )
    }

    used_b = set()
    matches = []
    only_a = []
    geometry_different = []

    for index_a, feature_a in enumerate(
        features_a
    ):
        geometry = feature_a.get(
            "geometry"
        )

        if not geometry:
            only_a.append(index_a)
            continue

        try:
            geom_a = shape(geometry)
            nearest = tree.nearest(
                geom_a
            )
            nearest_index = _tree_index(
                nearest,
                geometries_b,
                object_lookup,
            )

            if nearest_index is None:
                only_a.append(index_a)
                continue

            source_b_index = valid_b[
                nearest_index
            ][0]

            if source_b_index in used_b:
                only_a.append(index_a)
                continue

            geom_b = valid_b[
                nearest_index
            ][1]

            is_match, similarity = (
                _spatial_similarity(
                    geom_a,
                    geom_b,
                    family or "",
                )
            )

            if not is_match:
                only_a.append(index_a)
                continue

            used_b.add(
                source_b_index
            )

            id_a = _feature_id(
                feature_a,
                index_a,
            )

            id_b = _feature_id(
                features_b[
                    source_b_index
                ],
                source_b_index,
            )

            geometry_same = (
                _canonical(
                    feature_a.get(
                        "geometry"
                    )
                )
                == _canonical(
                    features_b[
                        source_b_index
                    ].get("geometry")
                )
            )

            if not geometry_same:
                geometry_different.append(
                    {
                        "dataset_a": id_a,
                        "dataset_b": id_b,
                        "similarity": round(
                            similarity
                            * 100,
                            2,
                        ),
                    }
                )

            matches.append(
                {
                    "dataset_a": id_a,
                    "dataset_b": id_b,
                    "dataset_a_index": index_a,
                    "dataset_b_index": source_b_index,
                    "similarity": round(
                        similarity
                        * 100,
                        2,
                    ),
                }
            )

        except Exception:
            only_a.append(index_a)

    only_b = [
        index
        for index in range(
            len(features_b)
        )
        if index not in used_b
    ]

    return {
        "matching_strategy": "spatial",
        "matched_count": len(matches),
        "only_a_count": len(only_a),
        "only_b_count": len(only_b),
        "geometry_different_count": len(
            geometry_different
        ),
        "matches": matches[:1000],
        "geometry_different": (
            geometry_different[:1000]
        ),
        "only_a_indexes": only_a,
        "only_b_indexes": only_b,
    }


def _collection(
    features: list[dict],
) -> dict:
    return {
        "type": "FeatureCollection",
        "features": features,
    }


def _map_layers(
    dataset_a: dict,
    dataset_b: dict,
    spatial: dict,
    limit: int = 700,
) -> dict:
    features_a = (
        dataset_a.get("features") or []
    )
    features_b = (
        dataset_b.get("features") or []
    )

    only_a = [
        features_a[index]
        for index in spatial.get(
            "only_a_indexes",
            [],
        )[:limit]
        if index < len(features_a)
    ]

    only_b = [
        features_b[index]
        for index in spatial.get(
            "only_b_indexes",
            [],
        )[:limit]
        if index < len(features_b)
    ]

    matched = []

    for match in spatial.get(
        "matches",
        [],
    )[:limit]:
        index = match[
            "dataset_b_index"
        ]

        if index < len(features_b):
            matched.append(
                features_b[index]
            )

    return {
        "only_a": _collection(
            only_a
        ),
        "only_b": _collection(
            only_b
        ),
        "matched": _collection(
            matched
        ),
    }


def _interpret(
    result: dict,
) -> str:
    reduced = {
        "compatibility": (
            result["compatibility"]
        ),
        "schema": result["schema"],
        "spatial": {
            key: value
            for key, value in (
                result["spatial"].items()
            )
            if key
            not in {
                "matches",
                "only_a_indexes",
                "only_b_indexes",
                "geometry_different",
            }
        },
        "quality": result["quality"],
    }

    prompt = f"""
أنت Dataset Comparison Analyst داخل نظام Meyaar.

حلل المقارنة التالية فقط:

{json.dumps(reduced, ensure_ascii=False)}

القواعد:
- Dataset A وDataset B قد يكونان من مصدرين مختلفين.
- لا تفترض أنهما نسختان قديمة وجديدة.
- الفرق بين البيانات لا يعني وجود خطأ.
- لا تعتبر العناصر الموجودة في Dataset واحدة فقط أخطاء بشكل تلقائي.
- اشرح الفروق في البنية والمحتوى المكاني والجودة.
- إذا كانت المقارنة غير متوافقة، وضح ذلك.
- لا تخترع سببًا للاختلافات.
- لا تدّعي الامتثال لـ GeoSA اعتمادًا على هذه المقارنة فقط.
- أجب بالعربية وباختصار.
""".strip()

    response = (
        _client()
        .chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.1,
            max_tokens=800,
        )
    )

    return (
        response.choices[0]
        .message.content.strip()
    )


def compare_datasets(
    dataset_a: dict,
    dataset_b: dict,
    dataset_a_name: str = "Dataset A",
    dataset_b_name: str = "Dataset B",
) -> dict:
    compatibility = compatibility_check(
        dataset_a,
        dataset_b,
    )

    schema = compare_schema(
        dataset_a,
        dataset_b,
    )

    quality_a = _quality(
        dataset_a
    )

    quality_b = _quality(
        dataset_b
    )

    spatial = (
        compare_spatial(
            dataset_a,
            dataset_b,
        )
        if compatibility["compatible"]
        else {
            "matching_strategy": None,
            "matched_count": 0,
            "only_a_count": len(
                dataset_a.get(
                    "features"
                ) or []
            ),
            "only_b_count": len(
                dataset_b.get(
                    "features"
                ) or []
            ),
            "geometry_different_count": 0,
            "matches": [],
            "only_a_indexes": [],
            "only_b_indexes": [],
        }
    )

    result = {
        "dataset_a": {
            "name": dataset_a_name,
            "feature_count": len(
                dataset_a.get(
                    "features"
                ) or []
            ),
        },
        "dataset_b": {
            "name": dataset_b_name,
            "feature_count": len(
                dataset_b.get(
                    "features"
                ) or []
            ),
        },
        "compatibility": compatibility,
        "schema": schema,
        "spatial": spatial,
        "quality": {
            "dataset_a": quality_a,
            "dataset_b": quality_b,
            "change": round(
                quality_b[
                    "quality_score"
                ]
                - quality_a[
                    "quality_score"
                ],
                2,
            ),
        },
        "compliance": {
            "status": "not_assessed",
            "message": (
                "Dataset differences do not prove GeoSA compliance. "
                "Compliance must be based on validation rules and standards evidence."
            ),
        },
    }

    result["map_layers"] = (
        _map_layers(
            dataset_a,
            dataset_b,
            spatial,
        )
    )

    try:
        result["interpretation"] = (
            _interpret(result)
        )
    except Exception as exc:
        print(
            "DATASET COMPARE LLM ERROR:",
            exc,
        )
        result["interpretation"] = None

    spatial.pop(
        "only_a_indexes",
        None,
    )
    spatial.pop(
        "only_b_indexes",
        None,
    )

    return result