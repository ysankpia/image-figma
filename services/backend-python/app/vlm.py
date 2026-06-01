from __future__ import annotations

import base64
import json
from dataclasses import dataclass

from openai import AsyncOpenAI
from PIL import Image

from .config import VLMConfig

SYSTEM_PROMPT = """You are a precise mobile UI detector.
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
    client = AsyncOpenAI(base_url=config.base_url, api_key=config.api_key)

    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    response = await client.chat.completions.create(
        model=config.model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": "Detect all UI elements."},
            ]},
        ],
        temperature=0,
        timeout=config.timeout,
    )

    text = response.choices[0].message.content or ""
    # Extract JSON from response (may be wrapped in markdown code block)
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
