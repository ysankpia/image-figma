from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from .config import Settings
from .ocr import OCRBlock, OCRDocument, OCRWarning, build_failed_ocr_document, validate_ocr_document
from .png_tools import PngMetadata


PROVIDER = "baidu_ppocrv5"


def extract_baidu_ppocrv5(
    *,
    task_id: str,
    image: PngMetadata,
    source_path: Path | None,
    settings: Settings,
) -> OCRDocument:
    if not settings.baidu_paddle_ocr_token:
        return build_failed_ocr_document(
            task_id=task_id,
            image=image,
            provider=PROVIDER,
            model=settings.baidu_paddle_ocr_model,
            code="BAIDU_PADDLE_OCR_TOKEN_MISSING",
            message="BAIDU_PADDLE_OCR_TOKEN is required when OCR_PROVIDER=baidu_ppocrv5.",
        )
    if source_path is None or not source_path.exists():
        return build_failed_ocr_document(
            task_id=task_id,
            image=image,
            provider=PROVIDER,
            model=settings.baidu_paddle_ocr_model,
            code="OCR_SOURCE_FILE_MISSING",
            message="OCR source PNG file is missing.",
        )

    try:
        job_id, submit_seconds = submit_job(source_path, settings)
        job_payload, poll_seconds, poll_count = poll_job(job_id, settings)
        json_url = ((job_payload.get("data") or {}).get("resultUrl") or {}).get("jsonUrl")
        if not isinstance(json_url, str) or not json_url:
            raise ValueError("Baidu PP-OCRv5 response does not contain resultUrl.jsonUrl.")
        rows = download_jsonl(json_url, settings)
        blocks, warnings = parse_ppocrv5_rows(rows, settings.ocr_min_confidence)
    except Exception as error:
        return build_failed_ocr_document(
            task_id=task_id,
            image=image,
            provider=PROVIDER,
            model=settings.baidu_paddle_ocr_model,
            code="OCR_EXTRACTION_FAILED",
            message=f"Baidu PP-OCRv5 extraction failed: {error}",
        )

    document = OCRDocument(
        version="0.1",
        taskId=task_id,
        provider=PROVIDER,
        model=settings.baidu_paddle_ocr_model,
        imageSize={"width": image.width, "height": image.height},
        coordinateSpace="pixel",
        blocks=blocks,
        warnings=warnings,
        meta={
            "notes": "ocr_contract_harness",
            "remoteJobId": job_id,
            "submitSeconds": round(submit_seconds, 3),
            "pollSeconds": round(poll_seconds, 3),
            "pollCount": poll_count,
            "filteredLowConfidenceCount": sum(1 for warning in warnings if warning.code == "OCR_LOW_CONFIDENCE"),
        },
    )
    return validate_ocr_document(document)


def submit_job(source_path: Path, settings: Settings) -> tuple[str, float]:
    headers = {"Authorization": f"bearer {settings.baidu_paddle_ocr_token}"}
    payload = {
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useTextlineOrientation": False,
    }
    data = {
        "model": settings.baidu_paddle_ocr_model,
        "optionalPayload": json.dumps(payload, ensure_ascii=False),
    }

    start = time.perf_counter()
    with source_path.open("rb") as source:
        response = requests.post(
            settings.baidu_paddle_ocr_job_url,
            headers=headers,
            data=data,
            files={"file": source},
            timeout=settings.baidu_paddle_ocr_timeout_seconds,
        )
    elapsed = time.perf_counter() - start
    if response.status_code != 200:
        raise ValueError(f"Baidu PP-OCRv5 submit failed with status {response.status_code}.")
    body = response.json()
    job_id = ((body.get("data") or {}).get("jobId"))
    if not isinstance(job_id, str) or not job_id:
        raise ValueError("Baidu PP-OCRv5 submit response does not contain data.jobId.")
    return job_id, elapsed


def poll_job(job_id: str, settings: Settings) -> tuple[dict[str, Any], float, int]:
    headers = {"Authorization": f"bearer {settings.baidu_paddle_ocr_token}"}
    start = time.perf_counter()
    polls = 0
    while True:
        polls += 1
        response = requests.get(
            f"{settings.baidu_paddle_ocr_job_url}/{job_id}",
            headers=headers,
            timeout=settings.baidu_paddle_ocr_timeout_seconds,
        )
        if response.status_code != 200:
            raise ValueError(f"Baidu PP-OCRv5 poll failed with status {response.status_code}.")
        body = response.json()
        data = body.get("data") or {}
        state = data.get("state")
        if state == "done":
            return body, time.perf_counter() - start, polls
        if state == "failed":
            raise ValueError(f"Baidu PP-OCRv5 job failed: {data.get('errorMsg') or 'unknown error'}.")
        if time.perf_counter() - start >= settings.baidu_paddle_ocr_timeout_seconds:
            raise TimeoutError("Baidu PP-OCRv5 job timed out.")
        time.sleep(settings.baidu_paddle_ocr_poll_interval_seconds)


def download_jsonl(url: str, settings: Settings) -> list[dict[str, Any]]:
    response = requests.get(url, timeout=settings.baidu_paddle_ocr_timeout_seconds)
    if response.status_code != 200:
        raise ValueError(f"Baidu PP-OCRv5 JSONL download failed with status {response.status_code}.")
    rows: list[dict[str, Any]] = []
    for line in response.text.splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    if not rows:
        raise ValueError("Baidu PP-OCRv5 JSONL response is empty.")
    return rows


def parse_ppocrv5_rows(rows: list[dict[str, Any]], min_confidence: float) -> tuple[list[OCRBlock], list[OCRWarning]]:
    blocks: list[OCRBlock] = []
    warnings: list[OCRWarning] = []
    next_index = 1

    for row in rows:
        result = row.get("result")
        if not isinstance(result, dict):
            warnings.append(OCRWarning(code="BAIDU_OCR_RESULT_MISSING", message="JSONL row does not contain result."))
            continue
        ocr_results = result.get("ocrResults")
        if not isinstance(ocr_results, list):
            warnings.append(
                OCRWarning(code="BAIDU_OCR_RESULTS_MISSING", message="result.ocrResults is missing or invalid.")
            )
            continue
        for ocr_result in ocr_results:
            if not isinstance(ocr_result, dict):
                continue
            parsed_blocks, parsed_warnings = parse_ocr_result(
                ocr_result,
                start_index=next_index,
                min_confidence=min_confidence,
            )
            next_index += count_rec_texts(ocr_result)
            blocks.extend(parsed_blocks)
            warnings.extend(parsed_warnings)

    return blocks, warnings


def count_rec_texts(ocr_result: dict[str, Any]) -> int:
    pruned = ocr_result.get("prunedResult")
    if not isinstance(pruned, dict) or not isinstance(pruned.get("rec_texts"), list):
        return 0
    return len(pruned["rec_texts"])


def parse_ocr_result(
    ocr_result: dict[str, Any],
    *,
    start_index: int,
    min_confidence: float,
) -> tuple[list[OCRBlock], list[OCRWarning]]:
    pruned = ocr_result.get("prunedResult")
    if not isinstance(pruned, dict):
        return [], [OCRWarning(code="BAIDU_PRUNED_RESULT_MISSING", message="ocrResults item has no prunedResult.")]

    texts = pruned.get("rec_texts")
    scores = pruned.get("rec_scores")
    boxes = pruned.get("rec_boxes")
    polys = pruned.get("rec_polys")
    if not isinstance(texts, list):
        return [], [OCRWarning(code="BAIDU_REC_TEXTS_MISSING", message="prunedResult.rec_texts is missing.")]
    if not isinstance(scores, list):
        scores = []
    if not isinstance(boxes, list):
        boxes = []
    if not isinstance(polys, list):
        polys = []

    blocks: list[OCRBlock] = []
    warnings: list[OCRWarning] = []
    for index, text_value in enumerate(texts):
        block_number = start_index + index
        block_id = f"ocr_text_{block_number:03d}"
        text = str(text_value).strip()
        if not text:
            warnings.append(OCRWarning(code="OCR_TEXT_EMPTY", message="Empty OCR text was dropped.", blockId=block_id))
            continue

        confidence = parse_score(scores[index] if index < len(scores) else None)
        if confidence < min_confidence:
            warnings.append(
                OCRWarning(
                    code="OCR_LOW_CONFIDENCE",
                    message=f"OCR text was dropped because confidence {confidence:.3f} is below threshold.",
                    blockId=block_id,
                )
            )
            continue

        bbox = None
        if index < len(boxes):
            bbox = rec_box_to_bbox(boxes[index])
        if bbox is None and index < len(polys):
            bbox = polygon_to_bbox(polys[index])
        if bbox is None:
            warnings.append(OCRWarning(code="INVALID_OCR_BBOX", message="OCR bbox is missing.", blockId=block_id))
            continue

        blocks.append(
            OCRBlock(
                id=block_id,
                text=text,
                bbox=bbox,
                confidence=confidence,
                lineId=f"line_{block_number:03d}",
                blockId=f"block_{block_number:03d}",
                source=PROVIDER,
            )
        )

    return blocks, warnings


def parse_score(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0


def rec_box_to_bbox(value: Any) -> list[int] | None:
    if not isinstance(value, list) or len(value) != 4:
        return None
    try:
        x1, y1, x2, y2 = [float(item) for item in value]
    except (TypeError, ValueError):
        return None
    width = x2 - x1
    height = y2 - y1
    if width <= 1 or height <= 1:
        return None
    return [round(x1), round(y1), round(width), round(height)]


def polygon_to_bbox(value: Any) -> list[int] | None:
    if not isinstance(value, list) or not value:
        return None
    points: list[tuple[float, float]] = []
    for point in value:
        if not isinstance(point, list) or len(point) < 2:
            return None
        try:
            points.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError):
            return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    if width <= 1 or height <= 1:
        return None
    return [round(min(xs)), round(min(ys)), round(width), round(height)]
