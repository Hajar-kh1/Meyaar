from pathlib import Path

VECTOR_EXTENSIONS = {
    ".geojson",
    ".json",
    ".gpkg",
    ".csv",
    ".parquet",
    ".zip",
}

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
}


def detect_input_type(filename: str) -> str:
    extension = Path(filename).suffix.lower()

    if extension in VECTOR_EXTENSIONS:
        return "vector"

    if extension in IMAGE_EXTENSIONS:
        return "image"

    return "unsupported"