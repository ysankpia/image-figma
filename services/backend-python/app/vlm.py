from __future__ import annotations

import asyncio
import base64
import io
import json
from dataclasses import dataclass

import httpx
from PIL import Image

from .config import VLMConfig

MAX_SIDE = 1280

ROLE_PROMPT_PREFIX = """You are a precise mobile UI detector.
Return ONLY JSON.
Use normalized coordinates relative to the received image.
Coordinates must be [x1,y1,x2,y2], each value from 0 to 1.
Detect concrete visible UI elements, not inferred semantics.
Roles must be one of: ImageView, TextView, Background, StatusBar, ActionBar, BottomNavigation, ListView, ViewGroup, Button, EditText.
Return this shape:
{"elements":[{"role":"ImageView","label":"short label","confidence":0.90,"bbox":[0.10,0.20,0.30,0.40]}]}

"""

PASSES: list[dict] = [
    {
        "id": "layout",
        "crop": None,  # full image
        "prompt": ROLE_PROMPT_PREFIX + """Detect the major layout regions and large interactive elements.
Include cards, list items, large buttons, tab bars, and major content sections.
Do not output individual icons or small text labels.
Do not output final hierarchy.""",
        "roles": {"Background", "Button", "EditText", "ListView", "ViewGroup", "ActionBar", "StatusBar"},
    },
    {
        "id": "imageview",
        "crop": None,
        "prompt": ROLE_PROMPT_PREFIX + """Detect only concrete visible image/icon elements.
Include thumbnails, cover images, avatars, badges, arrows, status glyphs, navigation icons, small UI icons, and image-like decorative glyphs.
Do not output text labels as TextView.
Do not output containers, buttons, backgrounds, or final hierarchy.
Prefer tight visible bboxes for the image/icon itself.""",
        "roles": {"ImageView"},
    },
    {
        "id": "background",
        "crop": None,
        "prompt": ROLE_PROMPT_PREFIX + """Detect only visible background and surface regions.
Include cards, bars, pills, panels, selected tab surfaces, obvious large background blocks, and visible control backplates.
Do not output text, icons, buttons, or final hierarchy.
Do not infer invisible containers.""",
        "roles": {"Background"},
    },
    {
        "id": "bottom_nav",
        "crop": (0.0, 0.82, 1.0, 0.18),  # (x_ratio, y_ratio, w_ratio, h_ratio)
        "prompt": ROLE_PROMPT_PREFIX + """Detect the bottom navigation area in this cropped mobile UI.
Include the BottomNavigation container and concrete tab icons.
Do not output every text label unless it is needed as a sparse tab label hint.
Do not create Button candidates for each tab.""",
        "roles": {"BottomNavigation", "ImageView", "TextView", "Background", "ViewGroup"},
    },
]


@dataclass
class VLMElement:
    role: str
    label: str
    x: int
    y: int
    width: int
    height: int
    confidence: float
    pass_id: str = ""


async def run_vlm(image_path: str, image_size: tuple[int, int], config: VLMConfig) -> list[VLMElement]:
    if not config.api_key:
        return []

    img_w, img_h = image_size
    img = Image.open(image_path).convert("RGB")

    tasks = [
        _run_pass(p, img, img_w, img_h, config)
        for p in PASSES
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    elements: list[VLMElement] = []
    for result in results:
        if isinstance(result, list):
            elements.extend(result)
    return elements


async def _run_pass(
    pass_def: dict,
    img: Image.Image,
    orig_w: int,
    orig_h: int,
    config: VLMConfig,
) -> list[VLMElement]:
    pass_id = pass_def["id"]
    crop = pass_def["crop"]

    # Crop region if specified
    if crop:
        cx, cy, cw, ch = crop
        x1 = int(cx * orig_w)
        y1 = int(cy * orig_h)
        x2 = int((cx + cw) * orig_w)
        y2 = int((cy + ch) * orig_h)
        region = img.crop((x1, y1, x2, y2))
        region_w, region_h = region.size
    else:
        region = img
        region_w, region_h = orig_w, orig_h
        x1, y1 = 0, 0

    # Resize to max side
    if max(region_w, region_h) > MAX_SIDE:
        scale = MAX_SIDE / max(region_w, region_h)
        new_w, new_h = int(region_w * scale), int(region_h * scale)
        region = region.resize((new_w, new_h), Image.LANCZOS)

    buf = io.BytesIO()
    region.save(buf, format="PNG")
    data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

    text = await _call_api(data_url, pass_def["prompt"], config)
    if not text:
        return []

    # Parse JSON
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    allowed_roles = pass_def.get("roles")
    elements: list[VLMElement] = []
    for item in data.get("elements", []):
        bbox = item.get("bbox", [])
        if len(bbox) != 4:
            continue
        role = item.get("role", "ImageView")
        if allowed_roles and role not in allowed_roles:
            continue
        conf = item.get("confidence", 0)
        if conf < 0.3:
            continue
        bx1, by1, bx2, by2 = bbox
        # Coordinates are normalized to the sent image (region)
        px1 = int(bx1 * region_w) + x1
        py1 = int(by1 * region_h) + y1
        px2 = int(bx2 * region_w) + x1
        py2 = int(by2 * region_h) + y1
        w = px2 - px1
        h = py2 - py1
        if w < 4 or h < 4:
            continue
        elements.append(VLMElement(
            role=role,
            label=item.get("label", ""),
            x=px1, y=py1, width=w, height=h,
            confidence=float(conf),
            pass_id=pass_id,
        ))
    return elements


async def _call_api(data_url: str, prompt: str, config: VLMConfig) -> str:
    base_url = config.base_url.rstrip("/")
    payload = {
        "model": config.model,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url},
                ],
            }
        ],
    }

    async with httpx.AsyncClient(timeout=config.timeout) as client:
        last_err = None
        for attempt in range(3):
            try:
                resp = await client.post(
                    f"{base_url}/v1/responses",
                    headers={
                        "Authorization": f"Bearer {config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                break
            except (httpx.ConnectError, httpx.ReadError, httpx.WriteError) as e:
                last_err = e
                if attempt < 2:
                    await asyncio.sleep(2)
        else:
            return ""

    body = resp.json()
    for output_item in body.get("output", []):
        if output_item.get("type") == "message":
            for content in output_item.get("content", []):
                if content.get("type") == "output_text":
                    return content.get("text", "")
    return ""
