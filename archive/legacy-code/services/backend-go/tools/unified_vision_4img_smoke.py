#!/usr/bin/env python3
"""Unified Vision 4-image smoke test.

Runs the unified vision approach (detection + grouping + style in one call)
on all 4 sample images. Each section is processed independently with its
own cropped image and evidence list. Large sections (>45 items) are split.

Usage:
  source .env.local
  python3 unified_vision_4img_smoke.py
"""

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

ROOT = Path(__file__).resolve().parent.parent.parent.parent
IMG_DIR = ROOT / "docs/reference/codia-samples/images"
BACKEND = ROOT / "services/backend-go"
WORK_DIR = Path("/tmp/unified_vision_4img_smoke")

MAX_ITEMS_PER_CALL = 45

SAMPLES = [
    ("t018", "腾讯动漫_018_1440.png"),
    ("t022", "腾讯动漫_022_1440.png"),
    ("lizhi", "荔枝_011_1440.png"),
    ("xianyu", "闲鱼.png"),
]

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
        print("ERROR: LAYOUT_ADVISOR_API_KEY or MODEL not set", file=sys.stderr)
        return 1

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Unified Vision 4-Image Smoke Test")
    print(f"Provider: {BASE_URL}")
    print(f"Model: {MODEL}")
    print(f"Max items per call: {MAX_ITEMS_PER_CALL}")
    print(f"Output: {WORK_DIR}")
    print()

    results = []
    for case_name, image_file in SAMPLES:
        print(f"{'='*60}")
        print(f"CASE: {case_name} ({image_file})")
        print(f"{'='*60}")
        case_result = run_case(case_name, IMG_DIR / image_file)
        results.append(case_result)
        print()

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"| case | sections | calls | groups | overflow | errors | coverage | time |")
    print(f"| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |")
    for r in results:
        print(f"| {r['case']} | {r['sections']} | {r['calls']} | {r['groups']} | {r['overflow']} | {r['errors']} | {r['grouped']}/{r['total']} ({r['coverage']:.0%}) | {r['time']:.0f}s |")

    # Write report
    report_path = WORK_DIR / "unified_vision_4img_report.json"
    report_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nReport: {report_path}")

    total_errors = sum(r["errors"] for r in results)
    total_overflow = sum(r["overflow"] for r in results)
    if total_errors == 0 and total_overflow == 0:
        print("\n✅ ALL PASS")
    elif total_errors == 0:
        print(f"\n⚠️  PARTIAL: {total_overflow} overflow groups across all cases")
    else:
        print(f"\n❌ FAIL: {total_errors} errors, {total_overflow} overflow")
    return 0 if total_errors == 0 else 1


def run_case(case_name, image_path):
    case_dir = WORK_DIR / case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # Generate layout IR to get evidence + sections
    ir_path = case_dir / "ui_layout_ir.v1.json"
    if not ir_path.exists():
        import subprocess
        subprocess.run(
            ["go", "run", "./cmd/layoutcompile", "-input", str(image_path), "-out", str(case_dir)],
            cwd=str(BACKEND), capture_output=True, check=True,
        )

    doc = json.loads(ir_path.read_text())
    evidence = doc["evidence"]
    sections = extract_sections(doc)

    print(f"  Evidence: {len(evidence)} | Sections: {len(sections)}")

    total_groups = 0
    total_overflow = 0
    error_counts = {
        "unknown_id": 0,
        "duplicate_ownership": 0,
        "single_member": 0,
        "overflow": 0,
        "parse_failure": 0,
        "provider_failure": 0,
    }
    total_grouped = 0
    total_flow = 0
    call_count = 0
    all_results = []

    for section in sections:
        flow_evidence = get_flow_evidence(evidence, section["bbox"])
        total_flow += len(flow_evidence)

        if len(flow_evidence) < 2:
            continue

        # Split large sections
        batches = split_evidence(flow_evidence, section["bbox"], MAX_ITEMS_PER_CALL)

        for batch_idx, (batch_evidence, batch_bbox) in enumerate(batches):
            call_count += 1
            batch_id = f"{section['id']}" if len(batches) == 1 else f"{section['id']}_part{batch_idx+1}"
            print(f"  [{batch_id}] {len(batch_evidence)} items...", end=" ", flush=True)

            try:
                result = call_unified_vision(image_path, batch_evidence, batch_bbox)
                all_results.append(result)

                groups = result.get("groups", [])
                grouped, error_detail, overflow = validate_groups(groups, batch_evidence, batch_bbox)
                total_groups += len(groups)
                total_overflow += overflow
                error_counts["overflow"] += overflow
                for name, count in error_detail.items():
                    error_counts[name] += count
                total_grouped += grouped
                errors = sum(error_detail.values())
                print(f"{len(groups)} groups, {overflow} overflow, {errors} errors ✅" if errors == 0 else f"❌ {errors} errors {error_detail}")
            except Exception as e:
                print(f"FAILED: {e}")
                if isinstance(e, json.JSONDecodeError):
                    error_counts["parse_failure"] += 1
                else:
                    error_counts["provider_failure"] += 1

    elapsed = time.time() - t0

    # Save all results
    (case_dir / "unified_vision_results.json").write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2))

    coverage = total_grouped / total_flow if total_flow > 0 else 0
    return {
        "case": case_name,
        "sections": len(sections),
        "calls": call_count,
        "groups": total_groups,
        "overflow": total_overflow,
        "errors": sum(count for name, count in error_counts.items() if name != "overflow"),
        "errorCounts": error_counts,
        "grouped": total_grouped,
        "total": total_flow,
        "coverage": coverage,
        "time": elapsed,
    }


def extract_sections(doc):
    sections = []
    for child in doc["root"].get("children", []):
        if child["type"] == "section":
            sections.append({"id": child["id"], "bbox": child["bbox"]})
    return sections


def get_flow_evidence(evidence, section_bbox):
    out = []
    for item in evidence:
        role = item.get("roleHint", "").lower()
        if role not in ("text", "icon", "image", "imageview", "textview"):
            continue
        bbox = item["bbox"]
        cx = bbox["x"] + bbox["width"] // 2
        cy = bbox["y"] + bbox["height"] // 2
        if (cx >= section_bbox["x"] and cx <= section_bbox["x"] + section_bbox["width"] and
            cy >= section_bbox["y"] and cy <= section_bbox["y"] + section_bbox["height"]):
            compact = {
                "id": item["id"],
                "role": item["roleHint"],
                "bbox": [bbox["x"], bbox["y"], bbox["width"], bbox["height"]],
            }
            text = item.get("meta", {}).get("text", "").strip()
            if text:
                compact["text"] = text
            out.append(compact)
    return out


def split_evidence(evidence, section_bbox, max_items):
    if len(evidence) <= max_items:
        return [(evidence, [section_bbox["x"], section_bbox["y"], section_bbox["width"], section_bbox["height"]])]

    sorted_ev = sorted(evidence, key=lambda e: e["bbox"][1])
    mid = len(sorted_ev) // 2
    mid_y = sorted_ev[mid]["bbox"][1]

    top = [e for e in sorted_ev if e["bbox"][1] + e["bbox"][3] // 2 < mid_y]
    bottom = [e for e in sorted_ev if e["bbox"][1] + e["bbox"][3] // 2 >= mid_y]

    top_bbox = [section_bbox["x"], section_bbox["y"], section_bbox["width"], mid_y - section_bbox["y"]]
    bottom_bbox = [section_bbox["x"], mid_y, section_bbox["width"], section_bbox["y"] + section_bbox["height"] - mid_y]

    batches = []
    if len(top) <= max_items:
        batches.append((top, top_bbox))
    else:
        batches.extend(split_evidence_list(top, top_bbox, max_items))
    if len(bottom) <= max_items:
        batches.append((bottom, bottom_bbox))
    else:
        batches.extend(split_evidence_list(bottom, bottom_bbox, max_items))
    return batches


def split_evidence_list(evidence, bbox, max_items):
    # Simple split into chunks
    chunks = []
    for i in range(0, len(evidence), max_items):
        chunks.append((evidence[i:i+max_items], bbox))
    return chunks


def validate_groups(groups, evidence, section_bbox):
    all_ids = {item["id"] for item in evidence}
    grouped_ids = set()
    errors = {"unknown_id": 0, "duplicate_ownership": 0, "single_member": 0}
    overflow = 0

    for g in groups:
        members = g.get("members", [])
        if len(members) < 2:
            errors["single_member"] += 1
        for m in members:
            if m not in all_ids:
                errors["unknown_id"] += 1
            if m in grouped_ids:
                errors["duplicate_ownership"] += 1
            grouped_ids.add(m)

        direction = g.get("direction", "horizontal")
        gap = g.get("gap", 0)
        if direction == "horizontal" and len(members) >= 2:
            member_bboxes = [item["bbox"] for item in evidence if item["id"] in members]
            if member_bboxes:
                total_width = sum(b[2] for b in member_bboxes)
                required = total_width + gap * (len(members) - 1)
                container_width = section_bbox[2]
                if container_width > 0 and required / container_width > 1.15:
                    overflow += 1

    return len(grouped_ids), errors, overflow


def call_unified_vision(image_path, evidence, section_bbox):
    evidence_json = json.dumps(evidence, ensure_ascii=False, indent=2)
    prompt = PROMPT_TEMPLATE.format(
        section_bbox=json.dumps(section_bbox),
        evidence=evidence_json,
        item_count=len(evidence),
    )
    image_data_url = crop_section_data_url(image_path, section_bbox)

    response_text = call_provider(prompt, image_data_url)

    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    return json.loads(text)


def crop_section_data_url(image_path, bbox):
    img = Image.open(image_path)
    x, y, w, h = bbox
    pad = 10
    x1, y1 = max(0, x - pad), max(0, y - pad)
    x2, y2 = min(img.width, x + w + pad), min(img.height, y + h + pad)
    cropped = img.crop((x1, y1, x2, y2))
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
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
            if isinstance(e, urllib.error.HTTPError) and e.code < 500:
                body = e.read().decode("utf-8", errors="replace")[:300]
                raise RuntimeError(f"HTTP {e.code}: {body}") from e
            if attempt < 2:
                time.sleep(5 * (attempt + 1))
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
