#!/usr/bin/env python3
"""Test unified vision with REAL evidence from section_0001 of 018 (86 items — stress test)."""

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
EVIDENCE_FILE = Path("/tmp/unified_vision_test/section_0001_evidence.json")

SECTION_BBOX = [27, 14, 611, 817]

PROMPT_TEMPLATE = """You are a UI layout analyzer. You receive a UI screenshot and a list of detected elements with precise bounding boxes within a specific section region.

Section region: {section_bbox} (x, y, width, height)

Your job (ALL in ONE response):
1. Group elements that visually belong together (same row, same card, same toolbar)
2. For each group: direction (horizontal/vertical), gap in pixels, alignment
3. For each text element: estimate fontSize, fontWeight, color
4. Groups can be nested: a horizontal row of vertical cards is valid

Rules:
- Reference elements ONLY by their ID
- Only group elements from the provided list
- Prefer small groups (2-6 items). Large groups (7+) are acceptable only for clear repeated patterns (e.g., a grid of thumbnails).
- If elements don't clearly belong together, put them in "ungrouped"
- Output ONLY valid JSON, no markdown, no explanation
- For nested groups, use "children" array containing sub-groups

Detected elements in this section ({item_count} items):
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
        print("ERROR: LAYOUT_ADVISOR_API_KEY or MODEL not set", file=sys.stderr)
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
    print(f"Section: section_0001 {SECTION_BBOX}")
    print(f"Evidence items: {len(evidence)}")
    print(f"Prompt length: {len(prompt)} chars (~{len(prompt)//4} tokens)")
    print()

    # Crop section from source image to reduce payload size
    image_data_url = crop_section_data_url(SAMPLE_IMAGE, SECTION_BBOX)
    print(f"Image: section crop (not full image)")
    print("Calling provider (this may take longer due to 86 items)...")
    t0 = time.time()
    try:
        response_text = call_provider(prompt, image_data_url)
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 1
    elapsed = time.time() - t0
    print(f"Response in {elapsed:.1f}s")
    print()

    # Parse
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        result = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"JSON parse failed: {e}")
        print(f"Raw response (first 3000 chars):\n{response_text[:3000]}")
        # Save raw for debugging
        Path("/tmp/unified_vision_test/section_0001_raw_response.txt").write_text(response_text)
        return 1

    # Save result
    out_path = Path("/tmp/unified_vision_test/section_0001_result.json")
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"Result saved to {out_path}")
    print()

    # Validate
    groups = result.get("groups", [])
    styles = result.get("elementStyles", {})
    ungrouped = result.get("ungrouped", [])
    all_ids = {item["id"] for item in evidence}
    grouped_ids = set()

    print(f"=== SUMMARY ===")
    print(f"Groups: {len(groups)}")
    print(f"Element styles: {len(styles)}")
    print(f"Ungrouped: {len(ungrouped)}")
    print()

    print(f"=== GROUPS ===")
    errors = 0
    overflow_count = 0
    for g in groups:
        members = g.get("members", [])
        for m in members:
            if m not in all_ids:
                print(f"  ERROR: {m} not in evidence list!")
                errors += 1
            if m in grouped_ids:
                print(f"  ERROR: {m} duplicate ownership!")
                errors += 1
            grouped_ids.add(m)
        # Check fit for horizontal groups
        direction = g.get("direction", "horizontal")
        gap = g.get("gap", 0)
        if direction == "horizontal" and len(members) >= 2:
            member_bboxes = [item["bbox"] for item in evidence if item["id"] in members]
            if member_bboxes:
                total_width = sum(b[2] for b in member_bboxes)
                required = total_width + gap * (len(members) - 1)
                container_width = SECTION_BBOX[2]
                fit_ratio = required / container_width if container_width > 0 else 0
                status = "✅" if fit_ratio <= 1.15 else "⚠️ OVERFLOW"
                if fit_ratio > 1.15:
                    overflow_count += 1
                print(f"  {g['name']}: H gap={gap} members={len(members)} fit={required}/{container_width}={fit_ratio:.2f} {status}")
            else:
                print(f"  {g['name']}: H gap={gap} members={len(members)} (no bbox match)")
        else:
            print(f"  {g['name']}: {direction[0].upper()} gap={gap} members={len(members)}")

    print()
    print(f"=== VALIDATION ===")
    print(f"Total evidence: {len(all_ids)}")
    print(f"Grouped: {len(grouped_ids)}")
    print(f"Ungrouped: {len(ungrouped)}")
    print(f"Unaccounted: {len(all_ids - grouped_ids - set(ungrouped))}")
    print(f"Errors: {errors}")
    print(f"Overflow groups: {overflow_count}/{len([g for g in groups if g.get('direction') == 'horizontal'])}")
    print()

    if errors == 0 and overflow_count == 0:
        print("✅ PASS: All groups valid, no overflow, no duplicate ownership")
    elif errors == 0:
        print(f"⚠️  PARTIAL: No errors but {overflow_count} overflow groups")
    else:
        print(f"❌ FAIL: {errors} validation errors, {overflow_count} overflow groups")

    return 0


def call_provider(prompt, image_data_url):
    if WIRE_API in ("responses", "response"):
        payload = {
            "model": MODEL,
            "input": [{"role": "user", "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": image_data_url},
            ]}],
            "temperature": 0,
        }
        url = request_url(BASE_URL, "/responses")
        response = post_json(url, payload)
        return extract_responses_text(response)
    else:
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ]}],
            "temperature": 0,
        }
        url = request_url(BASE_URL, "/chat/completions")
        response = post_json(url, payload)
        return response["choices"][0]["message"]["content"]


def request_url(base, path):
    if base.endswith("/v1"):
        return base + path
    return base + "/v1" + path


def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json",
        "User-Agent": "curl/8.7.1",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {e.code}: {body}") from e


def extract_responses_text(response):
    for item in response.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return content.get("text", "")
    raise RuntimeError(f"no output_text: {json.dumps(response)[:300]}")


def crop_section_data_url(image_path: Path, section_bbox: list) -> str:
    img = Image.open(image_path)
    x, y, w, h = section_bbox
    pad = 20
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(img.width, x + w + pad)
    y2 = min(img.height, y + h + pad)
    cropped = img.crop((x1, y1, x2, y2))
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    print(f"  Section crop: {cropped.width}x{cropped.height} ({len(buf.getvalue())//1024}KB)")
    return f"data:image/png;base64,{b64}"


if __name__ == "__main__":
    sys.exit(main())
