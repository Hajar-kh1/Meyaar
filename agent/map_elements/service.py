"""Preview-only suggestions for the map-elements agent capability.

This service is owned by the agent layer. It never modifies uploaded images;
the frontend renders a preview and the user explicitly chooses to export it.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

MapElement = Literal["title", "legend", "scale", "north_arrow"]


def _title_from_filename(filename: str) -> str:
    """Create a readable, non-authoritative title suggestion."""
    stem = Path(filename).stem
    cleaned = re.sub(r"[_-]+", " ", stem)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.title() if cleaned else "Map"


def suggest_missing_map_element(filename: str, element: MapElement) -> dict:
    """Return an editable suggestion without altering image data."""
    if element == "title":
        return {"element": element, "suggestion": {"title": _title_from_filename(filename)},
                "reason": "Suggested from the uploaded filename. Edit it before saving if needed."}
    if element == "legend":
        return {"element": element, "suggestion": {"legend_items": ["Primary features", "Reference features"]},
                "reason": "A neutral editable legend is proposed because feature labels cannot be verified from the filename alone."}
    if element == "scale":
        return {"element": element, "suggestion": {"scale_label": "Scale: verify before publishing"},
                "reason": "A numeric scale is not guessed because an image alone may have been resized or cropped."}
    if element == "north_arrow":
        return {"element": element, "suggestion": {"north_arrow": "N"},
                "reason": "A standard north marker is proposed. Move or rotate it in the preview if the map is rotated."}
    raise ValueError(f"Unsupported map element: {element}")
