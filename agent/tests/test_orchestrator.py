"""Orchestrator tests: deterministic file routing + delegation.

Detection tests need nothing (pure logic). Delegation tests stub the
downstream teammate modules in sys.modules so nothing heavy (PIL models,
the DB, the vision model) is imported.
"""
from __future__ import annotations

import sys
import types

import pytest

from agent.orchestrator import (
    IMAGE_EXTENSIONS,
    VECTOR_EXTENSIONS,
    detect_input_type,
    run_meyaar_agent,
)

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 24
TIFF_LE_BYTES = b"II*\x00" + b"\x00" * 24
TIFF_BE_BYTES = b"MM\x00*" + b"\x00" * 24
GEOJSON_TEXT = b'{"type": "FeatureCollection", "features": []}'


# ── deterministic detection ──────────────────────────────────────────────

@pytest.mark.parametrize("name", [f"data{ext}" for ext in sorted(VECTOR_EXTENSIONS)])
def test_vector_extensions_route_to_vector(name):
    assert detect_input_type(name, b"") == "vector"


@pytest.mark.parametrize("name", [f"map{ext}" for ext in sorted(IMAGE_EXTENSIONS)])
def test_image_extensions_route_to_image(name):
    assert detect_input_type(name, b"") == "image"


def test_extension_matching_is_case_insensitive():
    assert detect_input_type("DATA.GeoJSON", b"") == "vector"
    assert detect_input_type("MAP.PNG", b"") == "image"


@pytest.mark.parametrize("name", ["notes.pdf", "readme.txt", "data", "archive.rar", "file.exe"])
def test_unsupported_extensions(name):
    assert detect_input_type(name, b"") == "unsupported"


def test_image_magic_bytes_win_over_mislabelled_extension():
    # A real PNG misnamed as vector data must still go to the image path.
    assert detect_input_type("roads.geojson", PNG_BYTES) == "image"
    assert detect_input_type("layer.json", JPEG_BYTES) == "image"


@pytest.mark.parametrize("content", [TIFF_LE_BYTES, TIFF_BE_BYTES])
def test_tiff_magic_bytes_both_endianness(content):
    assert detect_input_type("whatever.bin", content) == "image"


def test_json_text_with_unknown_extension_routes_to_vector():
    # The app convention treats JSON text as vector data; the vector
    # pipeline validates the actual contents afterwards.
    assert detect_input_type("payload.bin", GEOJSON_TEXT) == "vector"
    assert detect_input_type("payload", GEOJSON_TEXT) == "vector"


def test_known_image_extension_still_image_when_content_empty():
    assert detect_input_type("map.png", b"") == "image"
    assert detect_input_type("roads.geojson", b"") == "vector"


# ── delegation to the existing pipelines ─────────────────────────────────

def _stub_module(name: str, **attrs):
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod
    return mod


def _clear_stubs(monkeypatch, names):
    for name in names:
        monkeypatch.delitem(sys.modules, name, raising=False)


@pytest.fixture()
def vector_stub(monkeypatch):
    calls = {}

    def process_vector_upload(filename, content, requested_layer=None):
        calls["filename"] = filename
        calls["requested_layer"] = requested_layer
        return {"layer": "buildings", "findings": 3}

    _stub_module("src.api.vector_pipeline",
                 process_vector_upload=process_vector_upload)
    yield calls
    _clear_stubs(monkeypatch, ["src.api.vector_pipeline"])


def test_vector_upload_is_forwarded_to_vector_pipeline(vector_stub):
    out = run_meyaar_agent("roads.geojson", b'{"type": "FeatureCollection"}', "roads")
    assert out["input_type"] == "vector"
    assert out["result"] == {"layer": "buildings", "findings": 3}
    assert vector_stub["filename"] == "roads.geojson"
    assert vector_stub["requested_layer"] == "roads"


@pytest.fixture()
def image_stubs(monkeypatch):
    calls = []

    def inspect_image(content):
        calls.append("inspect")
        return {"width": 10, "height": 10}

    class _VisionResult:
        def model_dump(self, mode="python"):
            return {"elements": ["title", "legend"]}

    def run_vision_pipeline(filename, content):
        calls.append("vision")
        return _VisionResult()

    _stub_module("src.vision.image_loader", inspect_image=inspect_image)
    _stub_module("src.vision.vision_pipeline",
                 run_vision_pipeline=run_vision_pipeline)
    yield calls
    _clear_stubs(monkeypatch,
                 ["src.vision.image_loader", "src.vision.vision_pipeline"])


def test_image_upload_is_forwarded_to_vision_pipeline(image_stubs):
    out = run_meyaar_agent("map.png", PNG_BYTES)
    assert out["input_type"] == "image"
    assert out["result"] == {"elements": ["title", "legend"]}
    # inspect_image runs first (validation), then the vision pipeline.
    assert image_stubs == ["inspect", "vision"]


def test_image_magic_routes_mislabelled_file_to_vision(image_stubs):
    # Misnamed PNG -> sniffed as image -> vision pipeline, not vector.
    out = run_meyaar_agent("roads.geojson", PNG_BYTES)
    assert out["input_type"] == "image"
    assert image_stubs == ["inspect", "vision"]


def test_unsupported_file_raises_value_error():
    with pytest.raises(ValueError, match="Unsupported file type"):
        run_meyaar_agent("notes.pdf", b"%PDF-1.4", None)


def test_pipeline_errors_propagate_untouched(vector_stub, monkeypatch):
    def raise_invalid(filename, content, requested_layer=None):
        raise ValueError("not a real vector file")

    sys.modules["src.api.vector_pipeline"].process_vector_upload = raise_invalid
    with pytest.raises(ValueError, match="not a real vector file"):
        run_meyaar_agent("roads.geojson", b"{}")
