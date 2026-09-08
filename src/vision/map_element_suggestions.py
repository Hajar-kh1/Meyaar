"""Safe, deterministic suggestions for missing cartographic map elements.

The suggestions in this module are intentionally previews only.  They never
open, alter, save, or replace the uploaded image; the client decides whether
to render, edit, or discard a suggestion.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal


MapElement = Literal["title", "legend", "scale", "north_arrow"]


def _title_from_filename(filename: str) -> str:
    """Turn a filename into a readable, non-authoritative title suggestion."""
    stem = Path(filename).stem
    cleaned = re.sub(r"[_-]+", " ", stem)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.title() if cleaned else "Map"


def suggest_missing_map_element(filename: str, element: MapElement) -> dict:
    """Return a preview payload for one missing element without changing data.

    This is deliberately deterministic so a user sees the same proposal for
    the same file.  It does not infer geography or invent a map legend from
    pixels: generic labels are provided for the user to edit in the preview.
    """
    if element == "title":
        return {
            "element": element,
            "suggestion": {"title": _title_from_filename(filename)},
            "reason": "Suggested from the uploaded filename. Edit it before saving if needed.",
        }

    if element == "legend":
        return {
            "element": element,
            "suggestion": {"legend_items": ["Primary features", "Reference features"]},
            "reason": "A neutral editable legend is proposed because feature labels cannot be verified from the filename alone.",
        }

    if element == "scale":
        return {
            "element": element,
            "suggestion": {"scale_label": "Scale: verify before publishing"},
            "reason": "A numeric scale is not guessed because an image alone may have been resized or cropped.",
        }

    if element == "north_arrow":
        return {
            "element": element,
            "suggestion": {"north_arrow": "N"},
            "reason": "A standard north marker is proposed. Move or rotate it in the preview if the map is rotated.",
        }

    # Pydantic validates API input, but retain this guard for direct callers.
    raise ValueError(f"Unsupported map element: {element}")
