"""Top-level Meyaar orchestration for one uploaded file.

FastAPI owns HTTP/auth/file-size concerns. This module owns routing to the
existing deterministic vector and vision tools.
"""
from __future__ import annotations

from src.api.routing import detect_input_type
from src.api.vector_pipeline import process_vector_upload
from src.vision.image_loader import inspect_image
from src.vision.vision_pipeline import run_vision_pipeline


def run_meyaar_agent(
    filename: str,
    content: bytes,
    requested_layer: str | None = None,
) -> dict:
    input_type = detect_input_type(filename)

    if input_type == "vector":
        result = process_vector_upload(filename, content, requested_layer)
    elif input_type == "image":
        inspect_image(content)
        result = run_vision_pipeline(filename, content).model_dump(mode="json")
    else:
        raise ValueError("Unsupported file type.")

    return {
        "input_type": input_type,
        "result": result,
    }
