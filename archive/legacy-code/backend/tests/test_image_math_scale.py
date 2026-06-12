from __future__ import annotations

from app.image_math import build_scale_profile


def test_scale_profile_uses_regular_ocr_height_and_records_basis() -> None:
    profile = build_scale_profile(
        image_size={"width": 390, "height": 844},
        ocr_blocks=[
            {"bbox": [20, 20, 80, 14], "confidence": 0.98},
            {"bbox": [20, 50, 90, 16], "confidence": 0.96},
        ],
        source_objects=[],
    )

    assert profile.text_sample_count == 2
    assert profile.source == "ocr_text_height_plus_image_fallback"
    assert 0.8 <= profile.factor <= 1.3


def test_scale_profile_fallback_ignores_large_media_region_as_text_unit() -> None:
    profile = build_scale_profile(
        image_size={"width": 900, "height": 1200},
        ocr_blocks=[],
        source_objects=[{"bbox": [0, 80, 850, 1050]}],
    )

    assert profile.source == "image_fallback"
    assert profile.scale_basis_px <= 32
    assert profile.factor <= 2.5
