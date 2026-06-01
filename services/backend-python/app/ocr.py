from __future__ import annotations

import asyncio
import json

import httpx

from .config import OCRConfig
from .schema import BBox, TextBlock


async def run_ocr(image_path: str, config: OCRConfig) -> list[TextBlock]:
    if not config.token:
        return []

    async with httpx.AsyncClient(timeout=config.timeout) as client:
        job_id = await _submit(client, image_path, config)
        result_url = await _poll(client, job_id, config)
        rows = await _download_jsonl(client, result_url, config)

    return _parse_rows(rows, config.min_confidence)


async def _submit(client: httpx.AsyncClient, image_path: str, config: OCRConfig) -> str:
    with open(image_path, "rb") as f:
        file_bytes = f.read()
    payload = json.dumps({
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useTextlineOrientation": False,
    })
    resp = await client.post(
        config.job_url,
        headers={"Authorization": f"bearer {config.token}"},
        files={"file": ("input.png", file_bytes, "image/png")},
        data={"model": config.model, "optionalPayload": payload},
    )
    resp.raise_for_status()
    data = resp.json().get("data", {})
    job_id = data.get("jobId", "")
    if not job_id:
        raise RuntimeError("OCR submit: no jobId in response")
    return job_id


async def _poll(client: httpx.AsyncClient, job_id: str, config: OCRConfig) -> str:
    elapsed = 0.0
    while elapsed < config.timeout:
        resp = await client.get(
            f"{config.job_url}/{job_id}",
            headers={"Authorization": f"bearer {config.token}"},
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        state = data.get("state", "")
        if state == "done":
            result_url = data.get("resultUrl", {}).get("jsonUrl", "")
            if not result_url:
                raise RuntimeError("OCR poll: no jsonUrl in done response")
            return result_url
        if state == "failed":
            raise RuntimeError(f"OCR job failed: {data.get('errorMsg', 'unknown')}")
        await asyncio.sleep(config.poll_interval)
        elapsed += config.poll_interval
    raise TimeoutError("OCR poll timed out")


async def _download_jsonl(client: httpx.AsyncClient, url: str, config: OCRConfig) -> list[dict]:
    resp = await client.get(url)
    resp.raise_for_status()
    rows = []
    for line in resp.text.strip().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _parse_rows(rows: list[dict], min_confidence: float) -> list[TextBlock]:
    blocks: list[TextBlock] = []
    next_id = 1
    for row in rows:
        result = row.get("result", {})
        ocr_results = result.get("ocrResults", [])
        for ocr_result in ocr_results:
            pruned = ocr_result.get("prunedResult", {})
            texts = pruned.get("rec_texts", [])
            scores = pruned.get("rec_scores", [])
            rec_boxes = pruned.get("rec_boxes", [])
            for i, text in enumerate(texts):
                text = str(text).strip()
                if not text:
                    continue
                score = scores[i] if i < len(scores) else 0
                if score < min_confidence:
                    continue
                if i < len(rec_boxes):
                    box = rec_boxes[i]
                    if len(box) == 4:
                        x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
                        width = x2 - x1
                        height = y2 - y1
                        if width <= 1 or height < 6:
                            continue
                        blocks.append(TextBlock(
                            id=f"text_{next_id:04d}",
                            text=text,
                            bbox=BBox(x=x1, y=y1, width=width, height=height),
                            confidence=float(score),
                        ))
                        next_id += 1
    return blocks
