from __future__ import annotations

import base64
import json
from dataclasses import dataclass

import httpx

from .config import VLMConfig

PROMPT = """You are a precise mobile UI detector.
Return ONLY JSON.
Use normalized coordinates relative to the received image.
Coordinates must be [x1,y1,x2,y2], each value from 0 to 1.
Detect concrete visible UI elements, not inferred semantics.
Roles must be one of: ImageView, TextView, Background, Button, EditText, Icon.
Return this shape:
{"elements":[{"role":"ImageView","label":"short label","confidence":0.90,"bbox":[0.10,0.20,0.30,0.40]}]}

Detect all visible UI elements in this mobile screenshot.
Include images, icons, buttons, input fields, background surfaces, and text blocks.
Do not output final hierarchy or invisible containers."""


@dataclass
class VLMElement:
    role: str
    label: str
    x: int
    y: int
    width: int
    height: int
    confidence: float


async def run_vlm(image_path: str, image_size: tuple[int, int], config: VLMConfig) -> list[VLMElement]:
    if not config.api_key:
        return []

    img_w, img_h = image_size

    with open(image_path, "rb") as f:
        data_url = "data:image/png;base64," + base64.b64encode(f.read()).decode()

    # Use Responses API (same as Go backend)
    base_url = config.base_url.rstrip("/")
    payload = {
        "model": config.model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": PROMPT},
                    {"type": "input_image", "image_url": data_url},
                ],
            }
        ],
    }

    async with httpx.AsyncClient(timeout=config.timeout) as client:
        resp = await client.post(
            f"{base_url}/v1/responses",
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()

    body = resp.json()

    # Parse Responses API output
    text = ""
    for output_item in body.get("output", []):
        if output_item.get("type") == "message":
            for content in output_item.get("content", []):
                if content.get("type") == "output_text":
                    text = content.get("text", "")
                    break
            if text:
                break

    if not text:
        return []

    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    elements: list[VLMElement] = []
    for item in data.get("elements", []):
        bbox = item.get("bbox", [])
        if len(bbox) != 4:
            continue
        x1, y1, x2, y2 = bbox
        conf = item.get("confidence", 0)
        if conf < 0.3:
            continue
        px1 = int(x1 * img_w)
        py1 = int(y1 * img_h)
        px2 = int(x2 * img_w)
        py2 = int(y2 * img_h)
        w = px2 - px1
        h = py2 - py1
        if w < 4 or h < 4:
            continue
        elements.append(VLMElement(
            role=item.get("role", "ImageView"),
            label=item.get("label", ""),
            x=px1, y=py1, width=w, height=h,
            confidence=float(conf),
        ))
    return elements
