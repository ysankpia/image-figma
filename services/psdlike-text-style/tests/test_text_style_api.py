from __future__ import annotations

import io
import json

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.main import app


def _load_font(size: int) -> ImageFont.ImageFont:
    for path in [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _make_button_image() -> bytes:
    img = Image.new("RGB", (240, 100), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((20, 25, 220, 75), radius=25, fill=(14, 177, 47))
    draw.text((95, 33), "搜索", fill=(255, 255, 255), font=_load_font(32))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_text_style_batch_returns_control_measurement() -> None:
    client = TestClient(app)
    items = [
        {
            "text": "搜索",
            "bbox": {"x": 20, "y": 25, "width": 200, "height": 50},
            "ownerSurface": {
                "bbox": {"x": 20, "y": 25, "width": 200, "height": 50},
                "fill": "#0eb12f",
                "reason": "filled_control_surface",
            },
        }
    ]

    response = client.post(
        "/api/text-style-batch",
        files={"image": ("page.png", _make_button_image(), "image/png")},
        data={"items": json.dumps(items, ensure_ascii=False)},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    result = body["results"][0]
    assert result["source"] == "psdlike"
    assert result["text"] == "搜索"
    assert 24 <= result["fontSize"] <= 34
    assert result["fontWeight"] == 500
    assert result["fontFamily"] == "PingFang SC"
    assert result["textAlign"] == "center"
    assert result["color"].startswith("#")
    assert result["measured"]["width"] > 0
    assert result["measured"]["height"] > 0


def test_text_style_batch_rejects_bad_items_json() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/text-style-batch",
        files={"image": ("page.png", _make_button_image(), "image/png")},
        data={"items": "not-json"},
    )
    assert response.status_code == 400


def test_health() -> None:
    client = TestClient(app)
    assert client.get("/health").json() == {"ok": True}
