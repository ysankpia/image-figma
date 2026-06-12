#!/usr/bin/env python3
"""Offline LLM layout advisor harness.

This is an experiment runner, not a product runtime. It reads
layout_advisor_input.v1.json, asks an OpenAI-compatible provider for grouping
relationships, and writes layout_advisor_result.v1.json.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import http.client
import urllib.error
import urllib.request
from pathlib import Path


RESULT_VERSION = "layout_advisor_result.v1"
FLOW_ROLES = {"text", "textview", "icon", "image", "imageview"}
TRANSIENT_PROVIDER_STATUS = {408, 409, 425, 429, 500, 502, 503, 504, 520, 522, 524}
MAX_PROVIDER_ATTEMPTS = 3


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the LLM layout advisor experiment.")
    parser.add_argument("--input", required=True, help="layout_advisor_input.v1.json")
    parser.add_argument("--image", required=True, help="source PNG path")
    parser.add_argument("--out", required=True, help="layout_advisor_result.v1.json")
    parser.add_argument("--fallback-out", default="", help="optional provider fallback artifact")
    parser.add_argument("--fixture-response", default="", help="test-only raw provider response fixture")
    args = parser.parse_args()

    input_path = Path(args.input)
    image_path = Path(args.image)
    out_path = Path(args.out)
    fallback_path = Path(args.fallback_out) if args.fallback_out else out_path.with_name("layout_advisor_fallback.v1.json")

    try:
        advisor_input = json.loads(input_path.read_text(encoding="utf-8"))
        if args.fixture_response:
            raw_text = Path(args.fixture_response).read_text(encoding="utf-8")
        else:
            raw_text = call_provider(advisor_input, image_path)
        result = parse_result_text(raw_text)
        validate_result_shape(result)
        write_json(out_path, result)
        return 0
    except Exception as exc:  # noqa: BLE001 - CLI must preserve fallback artifact.
        fallback = {
            "version": "layout_advisor_fallback.v1",
            "stage": "layout_advisor_experiment",
            "reason": str(exc),
            "policy": "continue_with_baseline_layoutcompile",
        }
        write_json(fallback_path, fallback)
        print(f"layout advisor failed: {exc}", file=sys.stderr)
        return 1


def call_provider(advisor_input: dict, image_path: Path) -> str:
    base_url = env("LAYOUT_ADVISOR_BASE_URL", "https://api.openai.com").rstrip("/")
    api_key = env("LAYOUT_ADVISOR_API_KEY", "")
    model = env("LAYOUT_ADVISOR_MODEL", "")
    wire_api = env("LAYOUT_ADVISOR_WIRE_API", "responses").strip().lower()
    timeout = float(env("LAYOUT_ADVISOR_TIMEOUT_SECONDS", "120"))
    temperature = float(env("LAYOUT_ADVISOR_TEMPERATURE", "0") or 0)
    if not api_key:
        raise RuntimeError("missing LAYOUT_ADVISOR_API_KEY")
    if not model:
        raise RuntimeError("missing LAYOUT_ADVISOR_MODEL")
    image_data_url = png_data_url(image_path)
    prompt = advisor_prompt(advisor_input)
    if wire_api in ("responses", "response"):
        payload = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": image_data_url},
                    ],
                }
            ],
        }
        if temperature > 0:
            payload["temperature"] = temperature
        response = post_json(request_url(base_url, "/responses"), payload, api_key, timeout)
        return extract_responses_text(response)
    if wire_api in ("chat.completions", "chat-completions", "chat"):
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                }
            ],
        }
        if temperature > 0:
            payload["temperature"] = temperature
        response = post_json(request_url(base_url, "/chat/completions"), payload, api_key, timeout)
        return response["choices"][0]["message"]["content"]
    raise RuntimeError(f"unsupported LAYOUT_ADVISOR_WIRE_API {wire_api!r}")


def advisor_prompt(advisor_input: dict) -> str:
    compact = compact_advisor_input(advisor_input)
    return "\n".join(
        [
            "You are a layout relationship advisor for a PNG-to-editable-Figma pipeline.",
            "Return ONLY strict JSON. Do not return markdown.",
            "Your output must have version layout_advisor_result.v1.",
            "You may only group existing IDs from flowEvidence.",
            "Only flowEvidence roles are groupable: text, icon, image.",
            "Focus on repairing badRows. Split bad rows into small physical horizontal rows.",
            "Do not invent or modify text, bboxes, assets, colors, coordinates, HTML, CSS, Figma nodes, or SVG.",
            "Prefer small credible horizontal rows with 2-6 items. Do not create mega-rows.",
            "If uncertain, omit the group; the deterministic validator will reject unsafe groups.",
            "Input JSON:",
            json.dumps(compact, ensure_ascii=False, separators=(",", ":")),
        ]
    )


def compact_advisor_input(advisor_input: dict) -> dict:
    return {
        "version": advisor_input.get("version"),
        "sourceImage": advisor_input.get("sourceImage"),
        "flowEvidence": compact_flow_evidence(advisor_input.get("evidence", [])),
        "badRows": compact_bad_rows(advisor_input.get("badRows", [])),
        "outputShape": advisor_input.get("instructions", {}).get("outputShape"),
    }


def compact_flow_evidence(evidence: list[dict]) -> list[dict]:
    out: list[dict] = []
    for item in evidence:
        role = str(item.get("roleHint", "")).strip().lower()
        if role not in FLOW_ROLES:
            continue
        compact = {
            "id": item.get("id"),
            "roleHint": item.get("roleHint"),
            "bbox": item.get("bbox"),
        }
        text = str(item.get("text", "")).strip()
        if text:
            compact["text"] = text
        confidence = item.get("confidence")
        if isinstance(confidence, (int, float)):
            compact["confidence"] = round(float(confidence), 3)
        out.append(compact)
    return out


def compact_bad_rows(rows: list[dict]) -> list[dict]:
    keep = (
        "id",
        "bbox",
        "flowEvidence",
        "flowCount",
        "gap",
        "gapVariance",
        "requiredWidth",
        "fitRatio",
        "ySpread",
        "medianHeight",
        "reason",
    )
    out: list[dict] = []
    for row in rows:
        compact: dict = {}
        for key in keep:
            if key in row:
                value = row[key]
                if key == "fitRatio" and isinstance(value, (int, float)):
                    value = round(float(value), 3)
                compact[key] = value
        out.append(compact)
    return out


def post_json(url: str, payload: dict, api_key: str, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    for attempt in range(MAX_PROVIDER_ATTEMPTS):
        request = urllib.request.Request(
            url,
            data=data,
            headers=provider_headers(api_key),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - user-configured provider.
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code in TRANSIENT_PROVIDER_STATUS and attempt < MAX_PROVIDER_ATTEMPTS - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise RuntimeError(f"provider HTTP {exc.code}: {body[:500]}") from exc
        except (urllib.error.URLError, TimeoutError, http.client.RemoteDisconnected) as exc:
            if attempt < MAX_PROVIDER_ATTEMPTS - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise RuntimeError(f"provider connection error: {exc}") from exc
    raise RuntimeError("provider request failed after retries")


def provider_headers(api_key: str) -> dict[str, str]:
    # Some OpenAI-compatible gateways reject Python's default urllib user-agent.
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "curl/8.7.1",
    }


def request_url(base_url: str, api_path: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    path = "/" + str(api_path or "").strip().lstrip("/")
    if base.endswith("/v1"):
        return base + path
    if base.endswith(path) or "/v1/" in base:
        return base
    return base + "/v1" + path


def extract_responses_text(response: dict) -> str:
    texts: list[str] = []
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in ("output_text", "text") and content.get("text"):
                texts.append(str(content["text"]))
    if not texts and response.get("output_text"):
        texts.append(str(response["output_text"]))
    if not texts:
        raise RuntimeError("provider response did not contain output text")
    return "\n".join(texts)


def parse_result_text(text: str) -> dict:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise
        return json.loads(raw[start : end + 1])


def validate_result_shape(result: dict) -> None:
    if result.get("version") != RESULT_VERSION:
        raise RuntimeError(f"expected {RESULT_VERSION}, got {result.get('version')!r}")
    groups = result.get("groups")
    if not isinstance(groups, list):
        raise RuntimeError("groups must be a list")
    for index, group in enumerate(groups):
        if not isinstance(group, dict):
            raise RuntimeError(f"groups[{index}] must be an object")
        ids = group.get("evidenceIds")
        if not isinstance(ids, list) or not all(isinstance(value, str) for value in ids):
            raise RuntimeError(f"groups[{index}].evidenceIds must be string list")


def png_data_url(path: Path) -> str:
    data = path.read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def env(key: str, default: str) -> str:
    value = os.environ.get(key)
    return default if value is None else value


if __name__ == "__main__":
    raise SystemExit(main())
