# Vector upload pipeline: load, classify, store, validate, and explain GIS data.

import json
import os
import re
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from dotenv import load_dotenv
from sqlalchemy import bindparam, create_engine, text

from agent.graph.builder import run_analysis
from src.insertion.insertion import (
    add_feature_id,
    detect_layer_type_fast,
    insert_vector_data,
    load_vector_file,
)
from src.quality import quality_score
from src.validation.validation_tools import run_rules_for_layer

load_dotenv()

SUPPORTED_VECTOR_EXTENSIONS = {
    ".geojson",
    ".json",
    ".gpkg",
    ".csv",
    ".parquet",
    ".zip",
}


class InvalidVectorFileError(ValueError):
    pass


class VectorProcessingError(RuntimeError):
    pass


def _build_layer_geojson(gdf) -> dict:
    layer = add_feature_id(gdf)

    if layer.crs is None:
        layer = layer.set_crs("EPSG:4326")
    elif layer.crs.to_epsg() != 4326:
        layer = layer.to_crs("EPSG:4326")

    return json.loads(
        layer[
            [
                "feature_id",
                "geometry",
            ]
        ].to_json()
    )


def _build_stored_layer_geojson(
    engine,
    layer_name: str,
) -> dict:
    query = text(
        f"""
        SELECT
            feature_id::text AS feature_id,
            ST_AsGeoJSON(
                CASE
                    WHEN ST_SRID(geometry) = 4326
                        THEN geometry
                    WHEN ST_SRID(geometry) = 0
                        THEN ST_SetSRID(
                            geometry,
                            4326
                        )
                    ELSE ST_Transform(
                        geometry,
                        4326
                    )
                END
            )::json AS geometry
        FROM public.{layer_name}
        WHERE geometry IS NOT NULL
        ORDER BY feature_id
        """
    )

    with engine.connect() as connection:
        rows = (
            connection.execute(query)
            .mappings()
            .all()
        )

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "feature_id": row[
                        "feature_id"
                    ]
                },
                "geometry": row["geometry"],
            }
            for row in rows
        ],
    }


def _attach_error_geometries(
    engine,
    layer_name: str,
    errors: list[dict],
) -> None:
    if (
        layer_name
        not in {
            "roads",
            "buildings",
        }
        or not errors
    ):
        return

    feature_ids = sorted(
        {
            str(error["feature_id"])
            for error in errors
            if error.get("feature_id")
            is not None
        }
    )

    if not feature_ids:
        return

    query = text(
        f"""
        SELECT
            feature_id::text AS feature_id,
            ST_AsGeoJSON(
                CASE
                    WHEN ST_SRID(geometry) = 4326
                        THEN geometry
                    WHEN ST_SRID(geometry) = 0
                        THEN ST_SetSRID(
                            geometry,
                            4326
                        )
                    ELSE ST_Transform(
                        geometry,
                        4326
                    )
                END
            ) AS geometry
        FROM public.{layer_name}
        WHERE geometry IS NOT NULL
          AND feature_id::text IN :feature_ids
        """
    ).bindparams(
        bindparam(
            "feature_ids",
            expanding=True,
        )
    )

    with engine.connect() as connection:
        rows = (
            connection.execute(
                query,
                {
                    "feature_ids": feature_ids
                },
            )
            .mappings()
            .all()
        )

    geometries = {
        row["feature_id"]: json.loads(
            row["geometry"]
        )
        for row in rows
        if row["geometry"]
    }

    for error in errors:
        error["geometry"] = geometries.get(
            str(
                error.get(
                    "feature_id"
                )
            )
        )


def _safe_extract_shapefile(
    zip_path: Path,
    destination: Path,
) -> Path:
    try:
        with zipfile.ZipFile(
            zip_path
        ) as archive:
            destination_root = (
                destination.resolve()
            )

            for member in archive.infolist():
                member_path = (
                    destination
                    / member.filename
                ).resolve()

                if (
                    destination_root
                    not in member_path.parents
                    and member_path
                    != destination_root
                ):
                    raise (
                        InvalidVectorFileError(
                            "The ZIP file "
                            "contains an "
                            "unsafe path."
                        )
                    )

            archive.extractall(
                destination
            )

    except zipfile.BadZipFile as error:
        raise InvalidVectorFileError(
            "The uploaded ZIP file "
            "is invalid."
        ) from error

    shapefiles = list(
        destination.rglob("*.shp")
    )

    if len(shapefiles) != 1:
        raise InvalidVectorFileError(
            "The ZIP file must "
            "contain exactly one "
            "Shapefile."
        )

    shapefile = shapefiles[0]

    required_files = {
        ".shp",
        ".shx",
        ".dbf",
    }

    available_files = {
        file.suffix.lower()
        for file
        in shapefile.parent.iterdir()
        if file.stem.lower()
        == shapefile.stem.lower()
    }

    missing_files = (
        required_files
        - available_files
    )

    if missing_files:
        raise InvalidVectorFileError(
            "The Shapefile is missing: "
            + ", ".join(
                sorted(
                    missing_files
                )
            )
        )

    return shapefile


def _resolve_layer_name(
    gdf,
    detection: dict,
    requested_layer: str | None,
) -> str:
    geometry_types = set(
        gdf.geom_type
        .dropna()
        .unique()
    )

    road_types = {
        "LineString",
        "MultiLineString",
    }

    building_types = {
        "Polygon",
        "MultiPolygon",
    }

    if (
        geometry_types
        and geometry_types.issubset(
            road_types
        )
    ):
        return "roads"

    if (
        geometry_types
        and geometry_types.issubset(
            building_types
        )
    ):
        return "buildings"

    if geometry_types:
        raise InvalidVectorFileError(
            "The file contains mixed "
            "or unsupported geometry "
            "types: "
            + ", ".join(
                sorted(
                    geometry_types
                )
            )
            + ". Separate roads and "
            "buildings into different "
            "files."
        )

    if (
        detection.get("status")
        == "success"
        and detection.get(
            "layer_type"
        )
        in {
            "roads",
            "buildings",
        }
    ):
        return detection[
            "layer_type"
        ]

    if requested_layer:
        return requested_layer

    raise InvalidVectorFileError(
        detection.get(
            "message",
            "Could not detect "
            "layer type.",
        )
    )


def _finding_key(
    item: dict,
) -> tuple[str, str] | None:
    feature_id = item.get("feature_id")
    rule_id = item.get("rule_id")

    if (
        feature_id is None
        or rule_id is None
    ):
        return None

    return (
        str(feature_id),
        str(rule_id),
    )


def _build_verified_fixes(
    remediation: list[dict],
    validation_before: dict,
    validation_after: dict | None,
) -> list[dict]:
    before_keys = {
        key
        for item in validation_before.get(
            "errors",
            [],
        )
        if (
            key := _finding_key(item)
        )
        is not None
    }

    after_keys = {
        key
        for item in (
            validation_after
            or {}
        ).get(
            "errors",
            [],
        )
        if (
            key := _finding_key(item)
        )
        is not None
    }

    verified = []

    for item in remediation:
        if item.get("status") != "applied":
            continue

        key = _finding_key(item)

        was_present = (
            key in before_keys
            if key is not None
            else False
        )

        still_present = (
            key in after_keys
            if (
                key is not None
                and validation_after
            )
            else None
        )

        verified.append(
            {
                "result_id": item.get(
                    "result_id"
                ),
                "feature_id": item.get(
                    "feature_id"
                ),
                "rule_id": item.get(
                    "rule_id"
                ),
                "revalidation_available":
                    validation_after
                    is not None,
                "was_present_before":
                    was_present,
                "still_present_after":
                    still_present,
                "resolved": (
                    bool(was_present)
                    and still_present is False
                    if validation_after
                    is not None
                    else None
                ),
            }
        )

    return verified


def _build_revalidation_summary(
    *,
    fixes_applied: bool,
    validation_before: dict,
    validation_after: dict | None,
    quality_before: dict,
    quality_after: dict,
    verified_fixes: list[dict],
) -> dict:
    resolved = sum(
        1
        for item in verified_fixes
        if item.get(
            "resolved"
        )
        is True
    )

    unresolved = sum(
        1
        for item in verified_fixes
        if item.get(
            "resolved"
        )
        is False
    )

    return {
        "attempted": fixes_applied,
        "performed":
            validation_after
            is not None,
        "before_run_id":
            validation_before.get(
                "run_id"
            ),
        "after_run_id": (
            validation_after.get(
                "run_id"
            )
            if validation_after
            else None
        ),
        "quality_before":
            quality_before.get(
                "quality_score"
            ),
        "quality_after":
            quality_after.get(
                "quality_score"
            ),
        "quality_improvement":
            round(
                quality_after.get(
                    "quality_score",
                    0,
                )
                - quality_before.get(
                    "quality_score",
                    0,
                ),
                1,
            ),
        "affected_features_before":
            quality_before.get(
                "affected_features"
            ),
        "affected_features_after":
            quality_after.get(
                "affected_features"
            ),
        "findings_before":
            validation_before.get(
                "total_errors",
                0,
            ),
        "findings_after": (
            validation_after.get(
                "total_errors",
                0,
            )
            if validation_after
            else validation_before.get(
                "total_errors",
                0,
            )
        ),
        "applied_fixes":
            len(verified_fixes),
        "resolved_fixes":
            resolved,
        "unresolved_fixes":
            unresolved,
    }


def process_vector_upload(
    filename: str,
    content: bytes,
    requested_layer: str | None = None,
) -> dict:
    extension = (
        Path(filename)
        .suffix
        .lower()
    )

    if re.search(
        r"\.(png|jpe?g|tiff?|webp)"
        r"\.json$",
        filename,
        re.IGNORECASE,
    ):
        raise InvalidVectorFileError(
            "This JSON file is image "
            "metadata, not vector "
            "geospatial data. Upload "
            "the related image in "
            "Map image mode instead."
        )

    if (
        extension
        not in SUPPORTED_VECTOR_EXTENSIONS
    ):
        raise InvalidVectorFileError(
            "Supported vector formats "
            "are GeoJSON, JSON, "
            "GeoPackage, CSV, "
            "GeoParquet, and zipped "
            "Shapefile."
        )

    if not content:
        raise InvalidVectorFileError(
            "The uploaded file is empty."
        )

    if requested_layer is not None:
        requested_layer = (
            requested_layer
            .lower()
            .strip()
        )

        if requested_layer not in {
            "roads",
            "buildings",
        }:
            raise InvalidVectorFileError(
                "Layer type must be "
                "roads or buildings."
            )

    with TemporaryDirectory() as temporary:
        temporary_path = Path(
            temporary
        )

        uploaded_path = (
            temporary_path
            / Path(filename).name
        )

        uploaded_path.write_bytes(
            content
        )

        if extension == ".zip":
            vector_path = (
                _safe_extract_shapefile(
                    uploaded_path,
                    temporary_path
                    / "shapefile",
                )
            )
        else:
            vector_path = (
                uploaded_path
            )

        detection = (
            detect_layer_type_fast(
                vector_path
            )
        )

        try:
            gdf = load_vector_file(
                vector_path
            )
        except Exception as error:
            raise InvalidVectorFileError(
                str(error)
            ) from error

        layer_geojson = (
            _build_layer_geojson(
                gdf
            )
        )

        layer_name = (
            _resolve_layer_name(
                gdf,
                detection,
                requested_layer,
            )
        )

        database_url = os.getenv(
            "MEYAAR_DATABASE_URL"
        )

        if not database_url:
            raise VectorProcessingError(
                "MEYAAR_DATABASE_URL "
                "is not configured."
            )

        engine = create_engine(
            database_url,
            pool_pre_ping=True,
        )

        try:
            insertion = (
                insert_vector_data(
                    engine=engine,
                    file_path=vector_path,
                    table_name=layer_name,
                )
            )

            if (
                insertion.get("status")
                != "success"
            ):
                raise (
                    VectorProcessingError(
                        insertion.get(
                            "message",
                            "Vector insertion "
                            "failed.",
                        )
                    )
                )

            validation = (
                run_rules_for_layer(
                    engine=engine,
                    layer_name=layer_name,
                )
            )

            if (
                validation.get("status")
                != "success"
            ):
                raise (
                    VectorProcessingError(
                        validation.get(
                            "message",
                            "Vector validation "
                            "failed.",
                        )
                    )
                )

            _attach_error_geometries(
                engine=engine,
                layer_name=layer_name,
                errors=validation.get(
                    "errors",
                    [],
                ),
            )

            run_id = validation[
                "run_id"
            ]

            quality_before = quality_score(
                validation.get(
                    "affected_features",
                    0,
                ),
                insertion.get(
                    "inserted_rows",
                    0,
                ),
            )

            analysis = run_analysis(
                run_id
            )

            fixes_applied = any(
                item.get("status")
                == "applied"
                for item in analysis.get(
                    "remediation",
                    [],
                )
            )

            validation_after = None
            quality_after = quality_before

            if fixes_applied:
                validation_after = (
                    run_rules_for_layer(
                        engine=engine,
                        layer_name=layer_name,
                    )
                )

                if (
                    validation_after.get(
                        "status"
                    )
                    == "success"
                ):
                    _attach_error_geometries(
                        engine=engine,
                        layer_name=layer_name,
                        errors=
                            validation_after.get(
                                "errors",
                                [],
                            ),
                    )

                    quality_after = (
                        quality_score(
                            validation_after.get(
                                "affected_features",
                                0,
                            ),
                            insertion.get(
                                "inserted_rows",
                                0,
                            ),
                        )
                    )
                else:
                    validation_after = None

            verified_fixes = (
                _build_verified_fixes(
                    analysis.get(
                        "remediation",
                        [],
                    ),
                    validation,
                    validation_after,
                )
            )

            revalidation_summary = (
                _build_revalidation_summary(
                    fixes_applied=
                        fixes_applied,
                    validation_before=
                        validation,
                    validation_after=
                        validation_after,
                    quality_before=
                        quality_before,
                    quality_after=
                        quality_after,
                    verified_fixes=
                        verified_fixes,
                )
            )

            fixed_layer_geojson = (
                _build_stored_layer_geojson(
                    engine,
                    layer_name,
                )
            )

            improvement = (
                revalidation_summary[
                    "quality_improvement"
                ]
            )

            return {
                "filename": filename,
                "status": "completed",
                "layer_name": layer_name,
                "run_id": run_id,
                "insertion": insertion,
                "validation": validation,
                "analysis": analysis,
                "total_features":
                    quality_after[
                        "total_features"
                    ],
                "affected_features":
                    quality_after[
                        "affected_features"
                    ],
                "total_findings": (
                    validation_after
                    or validation
                ).get(
                    "total_errors",
                    0,
                ),
                "error_rate":
                    quality_after[
                        "error_rate"
                    ],
                "quality_score":
                    quality_after[
                        "quality_score"
                    ],
                "compliance_score":
                    quality_after[
                        "quality_score"
                    ],
                "quality_before":
                    quality_before,
                "quality_after":
                    quality_after,
                "quality_improvement":
                    improvement,
                "validation_after":
                    validation_after,
                "verified_fixes":
                    verified_fixes,
                "revalidation_summary":
                    revalidation_summary,
                "layer_geojson":
                    layer_geojson,
                "fixed_layer_geojson":
                    fixed_layer_geojson,
            }

        finally:
            engine.dispose()