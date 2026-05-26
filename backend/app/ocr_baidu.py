from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

import requests

from .config import Settings
from .ocr import OCRBlock, OCRDocument, OCRWarning, build_failed_ocr_document, validate_ocr_document
from .png_tools import PngMetadata


PROVIDER = "baidu_ppocrv5"
TRANSIENT_HTTP_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
HTTP_MAX_ATTEMPTS = 3
HTTP_RETRY_BASE_SECONDS = 0.5


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
        response = request_with_transient_retry(
            "post",
            settings.baidu_paddle_ocr_job_url,
            settings=settings,
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
        response = request_with_transient_retry(
            "get",
            f"{settings.baidu_paddle_ocr_job_url}/{job_id}",
            settings=settings,
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
    response = request_with_transient_retry(
        "get",
        url,
        settings=settings,
        timeout=settings.baidu_paddle_ocr_timeout_seconds,
    )
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


def request_with_transient_retry(method: str, url: str, *, settings: Settings, **kwargs: Any) -> requests.Response:
    request_fn = getattr(requests, method)
    last_error: requests.RequestException | None = None
    for attempt in range(1, HTTP_MAX_ATTEMPTS + 1):
        rewind_request_files(kwargs)
        try:
            response = request_fn(url, **kwargs)
        except requests.RequestException as error:
            last_error = error
            if attempt >= HTTP_MAX_ATTEMPTS:
                raise
            sleep_before_retry(attempt, settings)
            continue
        if response.status_code in TRANSIENT_HTTP_STATUS_CODES and attempt < HTTP_MAX_ATTEMPTS:
            sleep_before_retry(attempt, settings)
            continue
        return response
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Baidu PP-OCRv5 {method.upper()} request failed before a response was returned.")


def rewind_request_files(kwargs: dict[str, Any]) -> None:
    files = kwargs.get("files")
    if not isinstance(files, dict):
        return
    for value in files.values():
        file_obj = value
        if isinstance(value, tuple) and value:
            file_obj = value[1]
        seek = getattr(file_obj, "seek", None)
        if callable(seek):
            seek(0)


def sleep_before_retry(attempt: int, settings: Settings) -> None:
    delay = min(settings.baidu_paddle_ocr_poll_interval_seconds, HTTP_RETRY_BASE_SECONDS * (2 ** (attempt - 1)))
    if delay > 0:
        time.sleep(delay)


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
        poly_raw = polys[index] if index < len(polys) else None
        if bbox is None and poly_raw is not None:
            bbox = polygon_to_bbox(poly_raw)
        if bbox is None:
            warnings.append(OCRWarning(code="INVALID_OCR_BBOX", message="OCR bbox is missing.", blockId=block_id))
            continue

        block_meta: dict[str, Any] = {}
        if poly_raw is not None:
            angle = estimate_polygon_rotation(poly_raw)
            if angle is not None:
                block_meta["angle"] = round(angle, 3)
            parsed_poly = parse_polygon_points(poly_raw)
            if parsed_poly is not None:
                block_meta["polygon"] = [[round(p[0], 1), round(p[1], 1)] for p in parsed_poly]

        blocks.append(
            OCRBlock(
                id=block_id,
                text=text,
                bbox=bbox,
                confidence=confidence,
                lineId=f"line_{block_number:03d}",
                blockId=f"block_{block_number:03d}",
                source=PROVIDER,
                meta=block_meta,
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


def parse_polygon_points(value: Any) -> list[tuple[float, float]] | None:
    """Parse a polygon value into a list of (x, y) points. Returns None on invalid input."""
    if not isinstance(value, list) or len(value) < 3:
        return None
    points: list[tuple[float, float]] = []
    for point in value:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return None
        try:
            points.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError):
            return None
    return points


def estimate_polygon_rotation(value: Any) -> float | None:
    """Estimate the rotation angle (in degrees) of a text polygon relative to
    horizontal/vertical alignment.

    For a 4-point polygon (typical OCR quad), we compute the angle of each
    consecutive edge, snap it to the nearest 90-degree grid line, and return
    the mean absolute deviation from that grid.  This gives ~0 for perfectly
    horizontal text and a larger value for rotated / artistic text.

    Returns None if the polygon is too small or cannot be parsed.
    """
    points = parse_polygon_points(value)
    if points is None or len(points) < 3:
        return None

    deviations: list[float] = []
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        dx = x2 - x1
        dy = y2 - y1
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            continue  # degenerate edge
        angle_deg = math.degrees(math.atan2(dy, dx))
        # Snap to nearest 90-degree axis (0, 90, 180, 270)
        remainder = angle_deg % 90
        deviation = min(abs(remainder), abs(remainder - 90))
        deviations.append(deviation)

    if not deviations:
        return None
    return sum(deviations) / len(deviations)
