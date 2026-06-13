from __future__ import annotations

import io
import json

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.main import app


def _make_button_image() -> bytes:
    img = Image.new("RGB", (240, 100), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((20, 25, 220, 75), radius=25, fill=(14, 177, 47))
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 32)
    except OSError:
        font = ImageFont.load_default()
    draw.text((95, 33), "搜索", fill=(255, 255, 255), font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_text_style_batch_returns_measurement() -> None:
    client = TestClient(app)
    image_bytes = _make_button_image()
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
        files={"image": ("page.png", image_bytes, "image/png")},
        data={"items": json.dumps(items)},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["imageWidth"] == 240
    assert body["imageHeight"] == 100
    results = body["results"]
    assert len(results) == 1
    r = results[0]
    assert r["text"] == "搜索"
    assert r["source"] == "psdlike"
    assert 8 <= r["fontSize"] <= 55
    assert r["fontWeight"] in (400, 500, 600)
    assert r["color"].startswith("#")
    assert r["measured"]["width"] > 0
    assert r["measured"]["height"] > 0


def test_text_style_batch_rejects_bad_items() -> None:
    client = TestClient(app)
    image_bytes = _make_button_image()
    response = client.post(
        "/api/text-style-batch",
        files={"image": ("page.png", image_bytes, "image/png")},
        data={"items": "not-json"},
    )
    assert response.status_code == 400
