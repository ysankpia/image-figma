from __future__ import annotations

import asyncio
import base64
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from .config import VLMConfig
from .schema import BBox, CandidateBatch, CandidateClassification, ObjectCandidate, TextBlock

ALLOWED_ROLES = {
    "icon",
    "avatar",
    "thumbnail",
    "photo",
    "logo",
    "illustration",
    "card_bg",
    "button_bg",
    "bar_bg",
    "divider",
    "noise",
    "text",
    "unknown",
}
ALLOWED_KINDS = {"image", "shape", "suppress"}
MAX_SIDE = 1280


@dataclass
class ClassificationResult:
    classifications: list[CandidateClassification] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    raw_responses: dict[str, str] = field(default_factory=dict)


async def classify_candidates(
    image: Image.Image,
    candidates: list[ObjectCandidate],
    batches: list[CandidateBatch],
    texts: list[TextBlock],
    config: VLMConfig,
    raw_dir: Path | None = None,
) -> ClassificationResult:
    if not candidates or not batches:
        return ClassificationResult()
    if not config.api_key:
        return ClassificationResult(errors=["vlm_api_key_missing"])

    candidate_by_id = {candidate.id: candidate for candidate in candidates}
    tasks = [
        _classify_batch(image, batch, candidate_by_id, texts, config, raw_dir)
        for batch in batches
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    merged = ClassificationResult()
    by_candidate: dict[str, CandidateClassification] = {}
    for result in results:
        if isinstance(result, Exception):
            merged.errors.append(str(result))
            continue
        merged.warnings.extend(result.warnings)
        merged.errors.extend(result.errors)
        merged.raw_responses.update(result.raw_responses)
        for item in result.classifications:
            existing = by_candidate.get(item.candidate_id)
            if existing is None or item.confidence > existing.confidence:
                by_candidate[item.candidate_id] = item

    merged.classifications = [
        by_candidate[key] for key in sorted(by_candidate)
    ]
    return merged


async def _classify_batch(
    image: Image.Image,
    batch: CandidateBatch,
    candidate_by_id: dict[str, ObjectCandidate],
    texts: list[TextBlock],
    config: VLMConfig,
    raw_dir: Path | None,
) -> ClassificationResult:
    crop = image.crop((batch.bbox.x, batch.bbox.y, batch.bbox.x2, batch.bbox.y2))
    sent_w, sent_h = crop.size
    if max(sent_w, sent_h) > MAX_SIDE:
        scale = MAX_SIDE / max(sent_w, sent_h)
        crop = crop.resize((max(1, int(sent_w * scale)), max(1, int(sent_h * scale))), Image.LANCZOS)

    buf = io.BytesIO()
    crop.save(buf, format="PNG")
    data_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    prompt = build_prompt(batch, candidate_by_id, texts)
    raw_text = await _call_api(data_url, prompt, config)

    result = ClassificationResult()
    result.raw_responses[batch.id] = raw_text
    if raw_dir is not None:
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"{batch.id}.txt").write_text(raw_text, encoding="utf-8")

    if not raw_text:
        result.errors.append(f"{batch.id}:empty_response")
        return result

    payload, parse_error = parse_json_response(raw_text)
    if parse_error:
        result.errors.append(f"{batch.id}:{parse_error}")
        return result

    allowed_ids = set(batch.candidate_ids)
    for item in payload.get("warnings", []) if isinstance(payload.get("warnings", []), list) else []:
        result.warnings.append(f"{batch.id}:{item}")

    for raw in payload.get("classifications", []):
        if not isinstance(raw, dict):
            result.warnings.append(f"{batch.id}:classification_not_object")
            continue
        candidate_id = str(raw.get("candidateId", "")).strip()
        if candidate_id not in allowed_ids:
            result.warnings.append(f"{batch.id}:unknown_candidate_id:{candidate_id}")
            continue
        role = normalize_role(raw.get("role"))
        kind = normalize_kind(raw.get("kind"))
        decision = str(raw.get("decision", "")).strip().lower()
        confidence = parse_float(raw.get("confidence"))
        reason = str(raw.get("reason", "")).strip()[:240]
        if confidence < config.min_confidence:
            kind = "suppress"
            decision = "suppress"
            reason = reason or "low_confidence"
        if decision not in {"emit", "suppress"}:
            decision = "emit" if kind in {"image", "shape"} else "suppress"
        result.classifications.append(
            CandidateClassification(
                candidate_id=candidate_id,
                role=role,
                kind=kind,
                decision=decision,
                confidence=confidence,
                reason=reason,
            )
        )
    return result


def build_prompt(
    batch: CandidateBatch,
    candidate_by_id: dict[str, ObjectCandidate],
    texts: list[TextBlock],
) -> str:
    candidates_payload: list[dict[str, Any]] = []
    for candidate_id in batch.candidate_ids:
        candidate = candidate_by_id[candidate_id]
        local = BBox(
            x=candidate.bbox.x - batch.bbox.x,
            y=candidate.bbox.y - batch.bbox.y,
            width=candidate.bbox.width,
            height=candidate.bbox.height,
        )
        candidates_payload.append(
            {
                "candidateId": candidate.id,
                "globalBBox": candidate.bbox.to_dict(),
                "localBBox": local.to_dict(),
                "textOverlapRatio": candidate.text_overlap_ratio,
                "textBlockCount": candidate.text_block_count,
            }
        )
    text_payload = [
        {
            "id": text.id,
            "localBBox": BBox(
                x=text.bbox.x - batch.bbox.x,
                y=text.bbox.y - batch.bbox.y,
                width=text.bbox.width,
                height=text.bbox.height,
            ).to_dict(),
        }
        for text in texts
        if text.bbox.x2 >= batch.bbox.x
        and text.bbox.x <= batch.bbox.x2
        and text.bbox.y2 >= batch.bbox.y
        and text.bbox.y <= batch.bbox.y2
    ]
    return (
        "You classify existing UI object candidates in a cropped mobile screenshot.\n"
        "Return ONLY strict JSON. Do not use markdown.\n"
        "You must classify only the provided candidateId values. Do not add candidates.\n"
        "Do not output bbox, OCR text, HTML, CSS, Figma, or assets.\n"
        "If uncertain, use role unknown, kind suppress, decision suppress.\n"
        "Allowed roles: icon, avatar, thumbnail, photo, logo, illustration, "
        "card_bg, button_bg, bar_bg, divider, noise, text, unknown.\n"
        "Allowed kind: image, shape, suppress.\n"
        "Shape means editable geometric surface, not a cropped bitmap.\n"
        "Image means a visible raster object worth selecting/replacing.\n"
        "Return shape: {\"classifications\":[{\"candidateId\":\"cand_0001\","
        "\"role\":\"icon\",\"kind\":\"image\",\"decision\":\"emit\","
        "\"confidence\":0.82,\"reason\":\"short reason\"}],\"warnings\":[]}.\n"
        f"Candidate crop origin global bbox: {batch.bbox.to_dict()}\n"
        f"OCR text bboxes in crop, for avoidance only: {json.dumps(text_payload, ensure_ascii=False)}\n"
        f"Candidates: {json.dumps(candidates_payload, ensure_ascii=False)}"
    )


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
        "temperature": 0,
    }

    async with httpx.AsyncClient(timeout=config.timeout) as client:
        for attempt in range(max(1, config.transport_retries)):
            try:
                resp = await client.post(
                    f"{base_url}/v1/responses",
                    headers={
                        "Authorization": f"Bearer {config.api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "User-Agent": "curl/8.7.1",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                body = resp.json()
                return extract_output_text(body)
            except (httpx.HTTPError, json.JSONDecodeError):
                if attempt + 1 >= max(1, config.transport_retries):
                    return ""
                await asyncio.sleep(1.5)
    return ""


def extract_output_text(body: dict[str, Any]) -> str:
    for output_item in body.get("output", []):
        if output_item.get("type") == "message":
            for content in output_item.get("content", []):
                if content.get("type") == "output_text":
                    return str(content.get("text", ""))
    return ""


def parse_json_response(text: str) -> tuple[dict[str, Any], str]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return {}, f"json_parse_error:{exc.msg}"
    if not isinstance(data, dict):
        return {}, "json_root_not_object"
    if "classifications" not in data or not isinstance(data["classifications"], list):
        return {}, "classifications_missing"
    return data, ""


def normalize_role(value: Any) -> str:
    role = str(value or "unknown").strip().lower()
    return role if role in ALLOWED_ROLES else "unknown"


def normalize_kind(value: Any) -> str:
    kind = str(value or "suppress").strip().lower()
    return kind if kind in ALLOWED_KINDS else "suppress"


def parse_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
