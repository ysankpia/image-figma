#!/usr/bin/env python3
"""Test unified vision with REAL evidence from section_0003 of 018."""

import base64
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE_URL = os.environ.get("LAYOUT_ADVISOR_BASE_URL", "").rstrip("/")
API_KEY = os.environ.get("LAYOUT_ADVISOR_API_KEY", "")
MODEL = os.environ.get("LAYOUT_ADVISOR_MODEL", "")
WIRE_API = os.environ.get("LAYOUT_ADVISOR_WIRE_API", "responses").strip().lower()

SAMPLE_IMAGE = Path(__file__).resolve().parent.parent.parent.parent / "docs/reference/codia-samples/images/腾讯动漫_018_1440.png"
EVIDENCE_FILE = Path("/tmp/unified_vision_test/section_0003_evidence.json")

SECTION_BBOX = [41, 860, 577, 198]

PROMPT_TEMPLATE = """You are a UI layout analyzer. You receive a UI screenshot and a list of detected elements with precise bounding boxes within a specific section region.

Section region: {section_bbox} (x, y, width, height)

Your job (ALL in ONE response):
1. Group elements that visually belong together (same row, same card, same toolbar)
2. For each group: direction (horizontal/vertical), gap in pixels, alignment
3. For each text element: estimate fontSize, fontWeight, color
4. For groups: estimate borderRadius, background color, shadow if visible

Rules:
- Reference elements ONLY by their ID
- Only group elements from the provided list
- Prefer small groups (2-6 items). Do NOT create one mega-group with all items.
- If elements don't clearly belong together, put them in "ungrouped"
- Output ONLY valid JSON, no markdown, no explanation

Detected elements in this section:
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
      "style": {{"background": "#FFF", "borderRadius": 8, "shadow": "none"}}
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
        evidence=evidence_json
    )

    print(f"Provider: {BASE_URL}")
    print(f"Model: {MODEL}")
    print(f"Section: {SECTION_BBOX}")
    print(f"Evidence items: {len(evidence)}")
    print(f"Prompt length: {len(prompt)} chars")
    print()

    image_bytes = SAMPLE_IMAGE.read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    image_data_url = f"data:image/png;base64,{image_b64}"

    print("Calling provider...")
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
        print(f"Raw response:\n{response_text[:2000]}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print()

    # Validate
    groups = result.get("groups", [])
    styles = result.get("elementStyles", {})
    ungrouped = result.get("ungrouped", [])
    all_ids = {item["id"] for item in evidence}
    grouped_ids = set()

    print(f"=== VALIDATION ===")
    print(f"Groups: {len(groups)}")
    errors = 0
    for g in groups:
        members = g.get("members", [])
        for m in members:
            if m not in all_ids:
                print(f"  ERROR: {m} not in evidence list!")
                errors += 1
            if m in grouped_ids:
                print(f"  ERROR: {m} appears in multiple groups!")
                errors += 1
            grouped_ids.add(m)
        # Check fit
        if g.get("direction") == "horizontal" and len(members) >= 2:
            member_bboxes = [item["bbox"] for item in evidence if item["id"] in members]
            total_width = sum(b[2] for b in member_bboxes)
            gap = g.get("gap", 0)
            required = total_width + gap * (len(members) - 1)
            section_width = SECTION_BBOX[2]
            fit_ratio = required / section_width if section_width > 0 else 0
            status = "✅" if fit_ratio <= 1.15 else "⚠️ OVERFLOW"
            print(f"  {g['name']}: {g['direction']} gap={gap} members={len(members)} required={required}/{section_width} {status}")
        else:
            print(f"  {g['name']}: {g.get('direction', '?')} gap={g.get('gap', '?')} members={len(members)}")

    print(f"\nElement styles: {len(styles)}")
    for eid, s in list(styles.items())[:6]:
        print(f"  {eid}: {s}")

    print(f"\nUngrouped: {ungrouped}")
    print(f"Coverage: {len(grouped_ids)}/{len(all_ids)} evidence items grouped")
    print(f"Errors: {errors}")

    if errors == 0:
        print("\n✅ PASS: All groups valid, no overflow, no duplicate ownership")
    else:
        print(f"\n❌ FAIL: {errors} validation errors")

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
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_responses_text(response):
    for item in response.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return content.get("text", "")
    raise RuntimeError(f"no output_text: {json.dumps(response)[:300]}")


if __name__ == "__main__":
    sys.exit(main())
