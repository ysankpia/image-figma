#!/usr/bin/env python3
"""Test unified vision with section_0001 TOP HALF (39 items) — split to avoid provider timeout."""

import base64
import io
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from PIL import Image

BASE_URL = os.environ.get("LAYOUT_ADVISOR_BASE_URL", "").rstrip("/")
API_KEY = os.environ.get("LAYOUT_ADVISOR_API_KEY", "")
MODEL = os.environ.get("LAYOUT_ADVISOR_MODEL", "")
WIRE_API = os.environ.get("LAYOUT_ADVISOR_WIRE_API", "responses").strip().lower()

SAMPLE_IMAGE = Path(__file__).resolve().parent.parent.parent.parent / "docs/reference/codia-samples/images/腾讯动漫_018_1440.png"
EVIDENCE_FILE = Path("/tmp/unified_vision_test/section_0001_top_evidence.json")

# Top half of section_0001
SECTION_BBOX = [27, 14, 611, 408]

PROMPT_TEMPLATE = """You are a UI layout analyzer. You receive a cropped section of a UI screenshot and a list of detected elements with precise bounding boxes.

Section region: {section_bbox} (x, y, width, height)

Your job (ALL in ONE response):
1. Group elements that visually belong together (same row, same card, same toolbar)
2. For each group: direction (horizontal/vertical), gap in pixels
3. For each text element: estimate fontSize, fontWeight, color

Rules:
- Reference elements ONLY by their ID
- Only group elements from the provided list
- Prefer small groups (2-6 items)
- If elements don't clearly belong together, put them in "ungrouped"
- Output ONLY valid JSON, no markdown

Detected elements ({item_count} items):
{evidence}

Return JSON:
{{
  "version": "unified_vision_result.v1",
  "groups": [
    {{
      "name": "descriptive_name",
      "direction": "horizontal|vertical",
      "gap": 12,
      "members": ["id1", "id2"],
      "style": {{"background": "#FFF", "borderRadius": 8}}
    }}
  ],
  "elementStyles": {{
    "id1": {{"fontSize": 16, "fontWeight": 600, "color": "#1A1A1A"}}
  }},
  "ungrouped": ["id_x"]
}}"""


def main():
    if not API_KEY or not MODEL:
        print("ERROR: env not set", file=sys.stderr)
        return 1

    evidence = json.loads(EVIDENCE_FILE.read_text())
    evidence_json = json.dumps(evidence, ensure_ascii=False, indent=2)
    prompt = PROMPT_TEMPLATE.format(
        section_bbox=json.dumps(SECTION_BBOX),
        evidence=evidence_json,
        item_count=len(evidence),
    )

    print(f"Provider: {BASE_URL}")
    print(f"Model: {MODEL}")
    print(f"Section: section_0001 TOP HALF {SECTION_BBOX}")
    print(f"Evidence items: {len(evidence)}")
    print(f"Prompt length: {len(prompt)} chars (~{len(prompt)//4} tokens)")

    image_data_url = crop_section_data_url(SAMPLE_IMAGE, SECTION_BBOX)
    print()
    print("Calling provider...")
    t0 = time.time()
    try:
        response_text = call_provider(prompt, image_data_url)
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 1
    elapsed = time.time() - t0
    print(f"Response in {elapsed:.1f}s\n")

    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        result = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"JSON parse failed: {e}")
        print(f"Raw:\n{response_text[:2000]}")
        Path("/tmp/unified_vision_test/section_0001_top_raw.txt").write_text(response_text)
        return 1

    Path("/tmp/unified_vision_test/section_0001_top_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2))

    groups = result.get("groups", [])
    styles = result.get("elementStyles", {})
    ungrouped = result.get("ungrouped", [])
    all_ids = {item["id"] for item in evidence}
    grouped_ids = set()
    errors = 0
    overflow_count = 0

    print(f"Groups: {len(groups)} | Styles: {len(styles)} | Ungrouped: {len(ungrouped)}")
    print()
    for g in groups:
        members = g.get("members", [])
        for m in members:
            if m not in all_ids:
                errors += 1
            if m in grouped_ids:
                errors += 1
            grouped_ids.add(m)
        direction = g.get("direction", "horizontal")
        gap = g.get("gap", 0)
        if direction == "horizontal" and len(members) >= 2:
            member_bboxes = [item["bbox"] for item in evidence if item["id"] in members]
            if member_bboxes:
                total_width = sum(b[2] for b in member_bboxes)
                required = total_width + gap * (len(members) - 1)
                fit = required / SECTION_BBOX[2] if SECTION_BBOX[2] > 0 else 0
                status = "✅" if fit <= 1.15 else "⚠️"
                if fit > 1.15:
                    overflow_count += 1
                print(f"  {g['name']}: H gap={gap} n={len(members)} fit={fit:.2f} {status}")
            else:
                print(f"  {g['name']}: H gap={gap} n={len(members)}")
        else:
            print(f"  {g['name']}: {direction[0].upper()} gap={gap} n={len(members)}")

    print(f"\nCoverage: {len(grouped_ids)}/{len(all_ids)} grouped")
    print(f"Errors: {errors} | Overflow: {overflow_count}")
    if errors == 0 and overflow_count == 0:
        print("✅ PASS")
    elif errors == 0:
        print(f"⚠️  PARTIAL ({overflow_count} overflow)")
    else:
        print(f"❌ FAIL ({errors} errors)")
    return 0


def crop_section_data_url(image_path, bbox):
    img = Image.open(image_path)
    x, y, w, h = bbox
    pad = 10
    x1, y1 = max(0, x - pad), max(0, y - pad)
    x2, y2 = min(img.width, x + w + pad), min(img.height, y + h + pad)
    cropped = img.crop((x1, y1, x2, y2))
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    print(f"  Crop: {cropped.width}x{cropped.height} ({len(buf.getvalue())//1024}KB)")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"


def call_provider(prompt, image_data_url):
    if WIRE_API in ("responses", "response"):
        payload = {"model": MODEL, "temperature": 0, "input": [{"role": "user", "content": [
            {"type": "input_text", "text": prompt},
            {"type": "input_image", "image_url": image_data_url},
        ]}]}
        resp = post_json(request_url(BASE_URL, "/responses"), payload)
        return extract_responses_text(resp)
    payload = {"model": MODEL, "temperature": 0, "messages": [{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_data_url}},
    ]}]}
    resp = post_json(request_url(BASE_URL, "/chat/completions"), payload)
    return resp["choices"][0]["message"]["content"]


def request_url(base, path):
    return base + path if base.endswith("/v1") else base + "/v1" + path


def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json",
        "User-Agent": "curl/8.7.1",
    }, method="POST")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            if attempt < 2:
                print(f"  Retry {attempt+1}: {e}")
                time.sleep(3)
            else:
                raise RuntimeError(f"Provider failed after 3 attempts: {e}") from e
    raise RuntimeError("unreachable")


def extract_responses_text(response):
    for item in response.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return content.get("text", "")
    raise RuntimeError(f"no output_text: {json.dumps(response)[:300]}")


if __name__ == "__main__":
    sys.exit(main())
