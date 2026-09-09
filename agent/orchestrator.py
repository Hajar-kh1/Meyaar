"""Top-level Meyaar orchestration for one uploaded file (agent-owned).

FastAPI owns HTTP/auth/file-size concerns (src/api/main.py). This module
owns routing: it decides whether an uploaded file is VECTOR data or a MAP
IMAGE and forwards it to the existing deterministic teammate pipelines:

    vector  -> src.api.vector_pipeline.process_vector_upload(...)
    image   -> src.vision.image_loader.inspect_image(...) +
               src.vision.vision_pipeline.run_vision_pipeline(...)

Deterministic by design — NO LLM in the routing decision. File-type routing
is extension/content logic; an LLM would be slower, cost tokens and could
misroute. The agentic layer interprets AFTER routing (error analysis for
vector runs, map-element suggestions for images); it never replaces the
deterministic detection (same principle as the rule engine vs. the agent).

Expected wiring (backend role): a single upload endpoint calls
run_meyaar_agent(filename, content, requested_layer?) and returns
{"input_type": "vector"|"image", "result": <pipeline result>}. Exceptions
from the downstream pipelines (InvalidVectorFileError,
InvalidImageError, VisionModelNotConfiguredError, ...) propagate untouched
so the API layer keeps its existing error mapping.
"""
from __future__ import annotations

import re
from pathlib import Path

# Extension sets mirror the backend pipelines (src/api/vector_pipeline.py +
# src/api/main.py image endpoints). Update together if a format is added.
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

# Strong content signatures (magic bytes) used as a second opinion so a
# mislabelled image is still routed to the image path.
_IMAGE_MAGIC = (
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"II*\x00", "tiff"),   # little-endian TIFF
    (b"MM\x00*", "tiff"),   # big-endian TIFF
)

_JSON_TEXT_RE = re.compile(rb"^\s*[{\[]")


def _sniffs_as_image(content: bytes) -> bool:
    """True when the file header is a known image signature."""
    return any(content.startswith(magic) for magic, _ in _IMAGE_MAGIC)


def _sniffs_as_vector_text(content: bytes) -> bool:
    """True when the file looks like JSON text (GeoJSON/JSON convention)."""
    return bool(_JSON_TEXT_RE.match(content[:64]))


def detect_input_type(filename: str, content: bytes = b"") -> str:
    """Deterministic routing decision: 'vector' | 'image' | 'unsupported'.

    Priority: strong image signature wins (a real PNG misnamed .geojson is
    still an image); then the filename extension; then JSON-looking text
    (the app treats .json/.geojson as vector data). No LLM involved.
    """
    extension = Path(filename or "").suffix.lower()

    if _sniffs_as_image(content):
        return "image"

    if extension in IMAGE_EXTENSIONS:
        return "image"

    if extension in VECTOR_EXTENSIONS:
        return "vector"

    # Unknown/extensionless file that is clearly JSON text -> vector data
    # by the app convention (the vector pipeline validates the contents and
    # raises a friendly error for non-geospatial JSON).
    if _sniffs_as_vector_text(content):
        return "vector"

    return "unsupported"


def run_meyaar_agent(
    filename: str,
    content: bytes,
    requested_layer: str | None = None,
) -> dict:
    """Route one uploaded file to the vector or image pipeline.

    Returns {"input_type": ..., "result": ...}. Raises ValueError for
    unsupported file types; downstream pipeline errors propagate as-is.
    """
    input_type = detect_input_type(filename, content)

    if input_type == "vector":
        # Lazy import: keeps this module importable without the backend deps
        # and lets tests stub the pipeline.
        from src.api.vector_pipeline import process_vector_upload

        result = process_vector_upload(filename, content, requested_layer)

    elif input_type == "image":
        from src.vision.image_loader import inspect_image
        from src.vision.vision_pipeline import run_vision_pipeline

        # Validate/parse first (raises InvalidImageError on bad images),
        # then run the full vision pipeline and return plain JSON.
        inspect_image(content)
        result = run_vision_pipeline(filename, content).model_dump(mode="json")

    else:
        raise ValueError(
            f"Unsupported file type for {filename!r}. Supported: vector "
            f"({sorted(VECTOR_EXTENSIONS)}) or image "
            f"({sorted(IMAGE_EXTENSIONS)}).")

    return {
        "input_type": input_type,
        "result": result,
    }
