from agent.map_elements.service import suggest_missing_map_element


def test_title_suggestion_is_readable_and_deterministic():
    result = suggest_missing_map_element("riyadh_roads-2026.png", "title")

    assert result["element"] == "title"
    assert result["suggestion"] == {"title": "Riyadh Roads 2026"}


def test_scale_does_not_invent_an_unverified_numeric_value():
    result = suggest_missing_map_element("map.png", "scale")

    assert result["suggestion"]["scale_label"] == "Scale: verify before publishing"


def test_north_arrow_is_a_preview_not_an_image_mutation():
    result = suggest_missing_map_element("map.png", "north_arrow")

    assert result["suggestion"] == {"north_arrow": "N"}
    assert "preview" in result["reason"].lower() or "Move" in result["reason"]
