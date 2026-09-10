from pathlib import Path

import geopandas as gpd
import ijson
import pandas as pd
import pyogrio
from shapely import wkt

SUPPORTED_FORMATS = {
    ".geojson",
    ".json",
    ".shp",
    ".gpkg",
    ".parquet",
    ".csv",
}

FEATURE_CATALOG = {
    "roads": {
        "names": [
            "road",
            "roads",
            "street",
            "streets",
            "highway",
        ],
        "geometries": [
            "LineString",
            "MultiLineString",
        ],
        "fields": [
            "class",
            "subclass",
            "road_surface",
            "speed_limits",
            "connectors",
            "width_rules",
        ],
    },
    "buildings": {
        "names": [
            "building",
            "buildings",
        ],
        "geometries": [
            "Polygon",
            "MultiPolygon",
        ],
        "fields": [
            "building",
            "building_type",
            "height",
            "levels",
        ],
    },
}


def load_vector_file(file_path, source_layer=None):
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    extension = file_path.suffix.lower()

    if extension not in SUPPORTED_FORMATS:
        supported = ", ".join(
            sorted(SUPPORTED_FORMATS)
        )

        raise ValueError(
            f"Unsupported file format: "
            f"{extension or 'no extension'}. "
            f"Supported formats are: {supported}"
        )

    if extension in {
        ".geojson",
        ".json",
        ".shp",
    }:
        gdf = gpd.read_file(file_path)

    elif extension == ".gpkg":
        gdf = gpd.read_file(
            file_path,
            layer=source_layer,
        )

    elif extension == ".parquet":
        gdf = gpd.read_parquet(file_path)

    elif extension == ".csv":
        df = pd.read_csv(file_path)

        if "geometry" in df.columns:
            df["geometry"] = df["geometry"].apply(
                lambda value: (
                    wkt.loads(value)
                    if pd.notna(value)
                    else None
                )
            )

            gdf = gpd.GeoDataFrame(
                df,
                geometry="geometry",
                crs="EPSG:4326",
            )

        elif {
            "longitude",
            "latitude",
        }.issubset(df.columns):
            geometry = gpd.points_from_xy(
                df["longitude"],
                df["latitude"],
            )

            gdf = gpd.GeoDataFrame(
                df,
                geometry=geometry,
                crs="EPSG:4326",
            )

        else:
            raise ValueError(
                "CSV must contain either a "
                "'geometry' column or longitude "
                "and latitude columns."
            )

    if "geometry" not in gdf.columns:
        raise ValueError(
            "The file does not contain "
            "a geometry column."
        )

    if gdf.empty:
        raise ValueError(
            "The file contains no features."
        )

    return gdf


def get_gpkg_layers(file_path):
    file_path = Path(file_path)

    if file_path.suffix.lower() != ".gpkg":
        return []

    return [
        str(row[0])
        for row in pyogrio.list_layers(file_path)
    ]


def _inspect_geojson(
    file_path,
    sample_size=10,
):
    geometries = []
    fields = set()

    with open(file_path, "rb") as file:
        for index, feature in enumerate(
            ijson.items(
                file,
                "features.item",
            )
        ):
            geometry = (
                feature.get("geometry") or {}
            ).get("type")

            if geometry:
                geometries.append(geometry)

            fields.update(
                (
                    feature.get("properties")
                    or {}
                ).keys()
            )

            if index + 1 >= sample_size:
                break

    geometry = (
        max(
            set(geometries),
            key=geometries.count,
        )
        if geometries
        else "Unknown"
    )

    return (
        geometry,
        {
            str(field).lower()
            for field in fields
        },
    )


def detect_layer_type_fast(
    file_path,
    source_layer=None,
    sample_size=10,
):
    path = Path(file_path)
    name = (
        source_layer or path.stem
    ).lower()

    for layer_type, config in (
        FEATURE_CATALOG.items()
    ):
        matches = [
            word
            for word in config["names"]
            if word in name
        ]

        if matches:
            return {
                "status": "success",
                "layer_type": layer_type,
                "confidence": 0.9,
                "geometry": "Not read",
                "signals": [
                    f"name:{word}"
                    for word in matches
                ],
            }

    try:
        extension = path.suffix.lower()

        if extension in {
            ".geojson",
            ".json",
        }:
            geometry, fields = (
                _inspect_geojson(
                    path,
                    sample_size,
                )
            )

        elif extension in {
            ".shp",
            ".gpkg",
        }:
            info = pyogrio.read_info(
                path,
                layer=source_layer,
            )

            geometry = (
                info.get("geometry_type")
                or "Unknown"
            )

            fields = {
                str(field).lower()
                for field in info.get(
                    "fields",
                    [],
                )
            }

        else:
            gdf = load_vector_file(
                path,
                source_layer=source_layer,
            ).head(sample_size)

            geometry_types = (
                gdf.geom_type
                .dropna()
                .tolist()
            )

            geometry = (
                geometry_types[0]
                if geometry_types
                else "Unknown"
            )

            fields = {
                str(column).lower()
                for column in gdf.columns
            }

    except Exception as error:
        return {
            "status": "needs_confirmation",
            "layer_type": "unknown",
            "confidence": 0.0,
            "message": (
                "Could not inspect layer: "
                f"{error}"
            ),
        }

    best_type = "unknown"
    best_score = 0
    best_signals = []

    for layer_type, config in (
        FEATURE_CATALOG.items()
    ):
        score = 0
        signals = []

        if geometry in config["geometries"]:
            score += 3
            signals.append(
                f"geometry:{geometry}"
            )

        for field in config["fields"]:
            if field in fields:
                score += 2
                signals.append(
                    f"field:{field}"
                )

        if score > best_score:
            best_type = layer_type
            best_score = score
            best_signals = signals

    if best_score < 3:
        return {
            "status": "needs_confirmation",
            "layer_type": "unknown",
            "confidence": 0.0,
            "geometry": geometry,
            "signals": best_signals,
            "message": (
                "Could not detect layer "
                "type automatically."
            ),
        }

    return {
        "status": "success",
        "layer_type": best_type,
        "confidence": round(
            min(best_score / 8, 1),
            2,
        ),
        "geometry": geometry,
        "signals": best_signals,
    }


def detect_layer_type(gdf):
    geometry_types = set(
        gdf.geom_type
        .dropna()
        .unique()
    )

    columns = [
        column.lower()
        for column in gdf.columns
    ]

    road_types = {
        "LineString",
        "MultiLineString",
    }

    if (
        geometry_types
        and geometry_types.issubset(
            road_types
        )
    ):
        return {
            "status": "success",
            "layer_type": "roads",
        }

    building_types = {
        "Polygon",
        "MultiPolygon",
    }

    if (
        geometry_types
        and geometry_types.issubset(
            building_types
        )
    ):
        building_keywords = {
            "building",
            "building_type",
            "height",
            "levels",
        }

        if any(
            keyword in columns
            for keyword in (
                building_keywords
            )
        ):
            return {
                "status": "success",
                "layer_type": "buildings",
            }

        return {
            "status": "needs_confirmation",
            "layer_type": "unknown",
            "message": (
                "Polygon layer detected. "
                "Please confirm if it is "
                "buildings."
            ),
        }

    return {
        "status": "needs_confirmation",
        "layer_type": "unknown",
        "message": (
            "Could not detect layer "
            "type automatically."
        ),
    }


def add_feature_id(gdf):
    gdf = gdf.copy()

    if "feature_id" in gdf.columns:
        gdf["feature_id"] = (
            gdf["feature_id"].astype(str)
        )

    elif "id" in gdf.columns:
        gdf["feature_id"] = (
            gdf["id"].astype(str)
        )

    elif "ogc_fid" in gdf.columns:
        gdf["feature_id"] = (
            gdf["ogc_fid"].astype(str)
        )

    else:
        gdf["feature_id"] = [
            str(index)
            for index in range(
                1,
                len(gdf) + 1,
            )
        ]

    return gdf


def insert_vector_data(
    engine,
    file_path,
    table_name,
    source_layer=None,
):
    try:
        print("Reading file...")

        gdf = load_vector_file(
            file_path,
            source_layer=source_layer,
        )

        gdf = add_feature_id(gdf)

        print(
            "File loaded successfully"
        )
        print(
            "Rows:",
            len(gdf),
        )
        print(
            "CRS:",
            gdf.crs,
        )
        print(
            "Geometry types:",
            gdf.geom_type
            .dropna()
            .unique(),
        )

        print(
            "Inserting into PostGIS..."
        )

        gdf.to_postgis(
            name=table_name,
            con=engine,
            schema="public",
            if_exists="replace",
            index=False,
        )

        return {
            "status": "success",
            "message": (
                "File inserted into "
                "PostGIS successfully."
            ),
            "table_name": table_name,
            "inserted_rows": len(gdf),
            "crs": (
                str(gdf.crs)
                if gdf.crs
                else None
            ),
            "geometry_types": (
                gdf.geom_type
                .dropna()
                .unique()
                .tolist()
            ),
        }

    except (
        ValueError,
        FileNotFoundError,
    ) as error:
        return {
            "status": "failed",
            "message": str(error),
        }

    except Exception as error:
        return {
            "status": "failed",
            "message": (
                "Error while processing "
                f"file: {error}"
            ),
        }