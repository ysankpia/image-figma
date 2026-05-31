#!/usr/bin/env python3
"""Quick test: can one VLM call do detection + grouping + style simultaneously?

Uses the same provider config as the layout advisor experiment.
Sends a section crop + OCR evidence, asks for groups + style in one shot.
"""

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

# Use same env vars as advisor experiment
BASE_URL = os.environ.get("LAYOUT_ADVISOR_BASE_URL", "https://api.openai.com").rstrip("/")
API_KEY = os.environ.get("LAYOUT_ADVISOR_API_KEY", "")
MODEL = os.environ.get("LAYOUT_ADVISOR_MODEL", "")
WIRE_API = os.environ.get("LAYOUT_ADVISOR_WIRE_API", "responses").strip().lower()

SAMPLE_IMAGE = Path(__file__).resolve().parent.parent.parent.parent / "docs/reference/codia-samples/images/腾讯动漫_018_1440.png"

# Simulated evidence for section_0002 of 018 (small, 8 items — good for quick test)
MOCK_EVIDENCE = [
    {"id": "ev_001", "role": "text", "bbox": [55, 695, 138, 27], "text": "热门推荐"},
    {"id": "ev_002", "role": "icon", "bbox": [200, 700, 24, 24]},
    {"id": "ev_003", "role": "text", "bbox": [420, 698, 80, 22], "text": "查看更多"},
    {"id": "ev_004", "role": "icon", "bbox": [505, 700, 20, 20]},
    {"id": "ev_005", "role": "text", "bbox": [55, 734, 31, 27], "text": "玄幻"},
    {"id": "ev_006", "role": "text", "bbox": [157, 777, 120, 25], "text": "斗破苍穹"},
    {"id": "ev_007", "role": "text", "bbox": [300, 777, 100, 25], "text": "斗罗大陆"},
    {"id": "ev_008", "role": "text", "bbox": [440, 777, 100, 25], "text": "完美世界"},
]

UNIFIED_PROMPT = """You are a UI layout analyzer. You receive a UI screenshot and a list of detected elements with precise bounding boxes.

Your job (do ALL of these in ONE response):
1. Group elements that visually belong together (same row, same card, same toolbar)
2. For each group, determine layout direction (horizontal/vertical) and gap
3. For each text element, estimate fontSize, fontWeight, color

Rules:
- Reference elements by their ID (ev_001, ev_002, etc.)
- Only group elements from the provided list
- If unsure about a group, leave elements in "ungrouped"
- Output ONLY valid JSON, no markdown

Input evidence:
{evidence}

Return this JSON shape:
{{
  "version": "unified_vision_result.v1",
  "groups": [
    {{
      "name": "descriptive_name",
      "direction": "horizontal",
      "gap": 12,
      "members": ["ev_001", "ev_002"],
      "style": {{"background": "#FFFFFF", "borderRadius": 0}}
    }}
  ],
  "elementStyles": {{
    "ev_001": {{"fontSize": 16, "fontWeight": 600, "color": "#1A1A1A"}}
  }},
  "ungrouped": ["ev_010"]
}}"""


def main():
    if not API_KEY:
        print("ERROR: LAYOUT_ADVISOR_API_KEY not set", file=sys.stderr)
        return 1
    if not MODEL:
        print("ERROR: LAYOUT_ADVISOR_MODEL not set", file=sys.stderr)
        return 1

    print(f"Provider: {BASE_URL}")
    print(f"Model: {MODEL}")
    print(f"Wire API: {WIRE_API}")
    print(f"Image: {SAMPLE_IMAGE.name}")
    print(f"Evidence items: {len(MOCK_EVIDENCE)}")
    print()

    # Build prompt
    evidence_json = json.dumps(MOCK_EVIDENCE, ensure_ascii=False, indent=2)
    prompt = UNIFIED_PROMPT.format(evidence=evidence_json)

    # Encode image
    image_bytes = SAMPLE_IMAGE.read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    image_data_url = f"data:image/png;base64,{image_b64}"

    # Call provider
    print("Calling provider...")
    try:
        response_text = call_provider(prompt, image_data_url)
    except Exception as e:
        print(f"Provider call failed: {e}", file=sys.stderr)
        return 1

    print(f"\n{'='*60}")
    print("RAW RESPONSE:")
    print(f"{'='*60}")
    print(response_text[:3000])
    print()

    # Try to parse JSON
    try:
        # Strip markdown code fences if present
        text = response_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        result = json.loads(text)
        print(f"{'='*60}")
        print("PARSED RESULT:")
        print(f"{'='*60}")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print()
        # Quick validation
        groups = result.get("groups", [])
        styles = result.get("elementStyles", {})
        ungrouped = result.get("ungrouped", [])
        print(f"Groups: {len(groups)}")
        for g in groups:
            print(f"  {g.get('name', '?')}: {g.get('direction', '?')} gap={g.get('gap', '?')} members={g.get('members', [])}")
        print(f"Element styles: {len(styles)}")
        for eid, s in list(styles.items())[:5]:
            print(f"  {eid}: {s}")
        print(f"Ungrouped: {ungrouped}")
        print()
        print("SUCCESS: Unified vision call works!")
        return 0
    except json.JSONDecodeError as e:
        print(f"JSON parse failed: {e}", file=sys.stderr)
        print("Response was not valid JSON — model may need prompt tuning")
        return 1


def call_provider(prompt: str, image_data_url: str) -> str:
    if WIRE_API in ("responses", "response"):
        payload = {
            "model": MODEL,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": image_data_url},
                    ],
                }
            ],
            "temperature": 0,
        }
        url = request_url(BASE_URL, "/responses")
        response = post_json(url, payload)
        return extract_responses_text(response)
    else:
        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                }
            ],
            "temperature": 0,
        }
        url = request_url(BASE_URL, "/chat/completions")
        response = post_json(url, payload)
        return response["choices"][0]["message"]["content"]


def request_url(base: str, path: str) -> str:
    if base.endswith("/v1"):
        return base + path
    return base + "/v1" + path


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
            "Accept": "application/json",
            "User-Agent": "curl/8.7.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {e.code}: {body}") from e


def extract_responses_text(response: dict) -> str:
    output = response.get("output", [])
    for item in output:
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return content.get("text", "")
    raise RuntimeError(f"no output_text in response: {json.dumps(response)[:300]}")


if __name__ == "__main__":
    sys.exit(main())
