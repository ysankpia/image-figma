from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from .config import Settings

PROVIDER_BAIDU_PPOCRV5 = "baidu_ppocrv5"
PROVIDER_NONE = "none"
TRANSIENT_HTTP_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
HTTP_MAX_ATTEMPTS = 3
HTTP_RETRY_BASE_SECONDS = 0.5


@dataclass(frozen=True)
class OCRProviderError(Exception):
    stage: str
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True)
class OCRRunResult:
    artifact: dict[str, Any]
    diagnostics: dict[str, Any]


def run_ocr_provider(image_path: Path, settings: Settings) -> OCRRunResult:
    provider = settings.ocr_provider
    started = time.perf_counter()
    try:
        if provider == PROVIDER_BAIDU_PPOCRV5:
            result = run_baidu_ppocrv5(image_path, settings)
        elif provider == PROVIDER_NONE:
            raise OCRProviderError(
                stage="ocr",
                code="OCR_PROVIDER_NONE",
                message="OCR_PROVIDER=none cannot produce OCR. Provide an OCR artifact or set a real provider.",
            )
        else:
            raise OCRProviderError(
                stage="ocr",
                code="UNSUPPORTED_OCR_PROVIDER",
                message=f"Unsupported OCR_PROVIDER={provider!r}.",
            )
    except OCRProviderError:
        raise
    except Exception as exc:  # noqa: BLE001 - provider boundary converts transport/parser errors to one contract.
        raise OCRProviderError(
            stage="ocr",
            code="OCR_PROVIDER_ERROR",
            message=f"OCR provider failed: {type(exc).__name__}: {exc}",
        ) from exc

    elapsed = time.perf_counter() - started
    diagnostics = dict(result.diagnostics)
    diagnostics.update(
        {
            "ocrProvider": provider,
            "ocrPresent": True,
            "ocrTextCount": len(result.artifact.get("blocks", [])),
            "ocrElapsedSeconds": round(elapsed, 3),
            "ocrError": "",
        }
    )
    return OCRRunResult(artifact=result.artifact, diagnostics=diagnostics)


def run_baidu_ppocrv5(image_path: Path, settings: Settings) -> OCRRunResult:
    if not settings.baidu_paddle_ocr_token:
        raise OCRProviderError(
            stage="ocr",
            code="BAIDU_PADDLE_OCR_TOKEN_MISSING",
            message="BAIDU_PADDLE_OCR_TOKEN is required when OCR_PROVIDER=baidu_ppocrv5.",
        )
    if not image_path.exists():
        raise OCRProviderError(
            stage="ocr",
            code="OCR_SOURCE_FILE_MISSING",
            message=f"OCR source PNG file does not exist: {image_path}",
        )

    with httpx.Client(timeout=settings.baidu_paddle_ocr_timeout_seconds) as client:
        job_id, submit_seconds = submit_baidu_job(client, image_path, settings)
        result_url, poll_seconds, poll_count = poll_baidu_job(client, job_id, settings)
        rows = download_baidu_jsonl(client, result_url, settings)

    artifact = ocr_blocks_artifact(
        rows,
        provider=PROVIDER_BAIDU_PPOCRV5,
        model=settings.baidu_paddle_ocr_model,
        min_confidence=settings.ocr_min_confidence,
        remote_job_id=job_id,
        submit_seconds=submit_seconds,
        poll_seconds=poll_seconds,
        poll_count=poll_count,
    )
    return OCRRunResult(
        artifact=artifact,
        diagnostics={
            "ocrRemoteJobId": job_id,
            "ocrSubmitSeconds": round(submit_seconds, 3),
            "ocrPollSeconds": round(poll_seconds, 3),
            "ocrPollCount": poll_count,
            "ocrFilteredLowConfidenceCount": artifact.get("meta", {}).get("filteredLowConfidenceCount", 0),
            "ocrWarningCount": len(artifact.get("warnings", [])),
        },
    )


def submit_baidu_job(client: httpx.Client, image_path: Path, settings: Settings) -> tuple[str, float]:
    payload = {
        "useDocOrientationClassify": False,
        "useDocUnwarping": False,
        "useTextlineOrientation": False,
    }
    started = time.perf_counter()
    file_bytes = image_path.read_bytes()
    response = request_with_transient_retry(
        client,
        "post",
        settings.baidu_paddle_ocr_job_url,
        headers={"Authorization": f"bearer {settings.baidu_paddle_ocr_token}"},
        files={"file": ("input.png", file_bytes, "image/png")},
        data={
            "model": settings.baidu_paddle_ocr_model,
            "optionalPayload": json.dumps(payload, ensure_ascii=False),
        },
    )
    elapsed = time.perf_counter() - started
    if response.status_code != 200:
        raise OCRProviderError(
            stage="ocr",
            code="BAIDU_OCR_SUBMIT_FAILED",
            message=f"Baidu PP-OCRv5 submit failed with HTTP {response.status_code}.",
        )
    job_id = ((response.json().get("data") or {}).get("jobId"))
    if not isinstance(job_id, str) or not job_id:
        raise OCRProviderError(
            stage="ocr",
            code="BAIDU_OCR_JOB_ID_MISSING",
            message="Baidu PP-OCRv5 submit response does not contain data.jobId.",
        )
    return job_id, elapsed


def poll_baidu_job(client: httpx.Client, job_id: str, settings: Settings) -> tuple[str, float, int]:
    started = time.perf_counter()
    polls = 0
    while True:
        polls += 1
        response = request_with_transient_retry(
            client,
            "get",
            f"{settings.baidu_paddle_ocr_job_url.rstrip('/')}/{job_id}",
            headers={"Authorization": f"bearer {settings.baidu_paddle_ocr_token}"},
        )
        if response.status_code != 200:
            raise OCRProviderError(
                stage="ocr",
                code="BAIDU_OCR_POLL_FAILED",
                message=f"Baidu PP-OCRv5 poll failed with HTTP {response.status_code}.",
            )
        data = response.json().get("data") or {}
        state = data.get("state")
        if state == "done":
            result_url = (data.get("resultUrl") or {}).get("jsonUrl")
            if not isinstance(result_url, str) or not result_url:
                raise OCRProviderError(
                    stage="ocr",
                    code="BAIDU_OCR_JSON_URL_MISSING",
                    message="Baidu PP-OCRv5 done response does not contain resultUrl.jsonUrl.",
                )
            return result_url, time.perf_counter() - started, polls
        if state == "failed":
            raise OCRProviderError(
                stage="ocr",
                code="BAIDU_OCR_JOB_FAILED",
                message=f"Baidu PP-OCRv5 job failed: {data.get('errorMsg') or 'unknown error'}.",
            )
        if time.perf_counter() - started >= settings.baidu_paddle_ocr_timeout_seconds:
            raise OCRProviderError(
                stage="ocr",
                code="BAIDU_OCR_TIMEOUT",
                message="Baidu PP-OCRv5 job timed out.",
            )
        time.sleep(settings.baidu_paddle_ocr_poll_interval_seconds)


def download_baidu_jsonl(client: httpx.Client, url: str, settings: Settings) -> list[dict[str, Any]]:
    response = request_with_transient_retry(client, "get", url)
    if response.status_code != 200:
        raise OCRProviderError(
            stage="ocr",
            code="BAIDU_OCR_DOWNLOAD_FAILED",
            message=f"Baidu PP-OCRv5 JSONL download failed with HTTP {response.status_code}.",
        )
    rows: list[dict[str, Any]] = []
    for line in response.text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise OCRProviderError(
                stage="ocr",
                code="BAIDU_OCR_JSONL_PARSE_FAILED",
                message=f"Baidu PP-OCRv5 JSONL contains invalid JSON: {exc}",
            ) from exc
    if not rows:
        raise OCRProviderError(
            stage="ocr",
            code="BAIDU_OCR_JSONL_EMPTY",
            message="Baidu PP-OCRv5 JSONL response is empty.",
        )
    return rows


def request_with_transient_retry(
    client: httpx.Client,
    method: str,
    url: str,
    **kwargs: Any,
) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(1, HTTP_MAX_ATTEMPTS + 1):
        try:
            response = client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt >= HTTP_MAX_ATTEMPTS:
                raise
            time.sleep(HTTP_RETRY_BASE_SECONDS * (2 ** (attempt - 1)))
            continue
        if response.status_code in TRANSIENT_HTTP_STATUS_CODES and attempt < HTTP_MAX_ATTEMPTS:
            time.sleep(HTTP_RETRY_BASE_SECONDS * (2 ** (attempt - 1)))
            continue
        return response
    assert last_error is not None
    raise last_error


def ocr_blocks_artifact(
    rows: list[dict[str, Any]],
    *,
    provider: str,
    model: str,
    min_confidence: float,
    remote_job_id: str | None = None,
    submit_seconds: float | None = None,
    poll_seconds: float | None = None,
    poll_count: int | None = None,
) -> dict[str, Any]:
    blocks, warnings, counters = parse_baidu_ppocrv5_rows(rows, min_confidence)
    meta: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "minConfidence": min_confidence,
        "rawTextCount": counters["rawTextCount"],
        "filteredLowConfidenceCount": counters["filteredLowConfidenceCount"],
        "droppedEmptyTextCount": counters["droppedEmptyTextCount"],
        "droppedInvalidBoxCount": counters["droppedInvalidBoxCount"],
    }
    if remote_job_id:
        meta["remoteJobId"] = remote_job_id
    if submit_seconds is not None:
        meta["submitSeconds"] = round(submit_seconds, 3)
    if poll_seconds is not None:
        meta["pollSeconds"] = round(poll_seconds, 3)
    if poll_count is not None:
        meta["pollCount"] = poll_count
    return {
        "version": "ocr_blocks.v1",
        "provider": provider,
        "model": model,
        "blocks": blocks,
        "warnings": warnings,
        "meta": meta,
    }


def parse_baidu_ppocrv5_rows(
    rows: list[dict[str, Any]],
    min_confidence: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    blocks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    counters = {
        "rawTextCount": 0,
        "filteredLowConfidenceCount": 0,
        "droppedEmptyTextCount": 0,
        "droppedInvalidBoxCount": 0,
    }

    next_id = 1
    for row_index, row in enumerate(rows, start=1):
        result = row.get("result")
        if not isinstance(result, dict):
            warnings.append({"code": "BAIDU_OCR_RESULT_MISSING", "message": "JSONL row has no result.", "row": row_index})
            continue
        ocr_results = result.get("ocrResults")
        if not isinstance(ocr_results, list):
            warnings.append(
                {"code": "BAIDU_OCR_RESULTS_MISSING", "message": "result.ocrResults is missing.", "row": row_index}
            )
            continue
        for ocr_result in ocr_results:
            parsed, parsed_warnings, parsed_counters = parse_baidu_ocr_result(
                ocr_result,
                start_index=next_id,
                min_confidence=min_confidence,
            )
            next_id += parsed_counters["rawTextCount"]
            blocks.extend(parsed)
            warnings.extend(parsed_warnings)
            for key, value in parsed_counters.items():
                counters[key] += value
    return blocks, warnings, counters


def parse_baidu_ocr_result(
    ocr_result: Any,
    *,
    start_index: int,
    min_confidence: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    counters = {
        "rawTextCount": 0,
        "filteredLowConfidenceCount": 0,
        "droppedEmptyTextCount": 0,
        "droppedInvalidBoxCount": 0,
    }
    if not isinstance(ocr_result, dict):
        return [], [{"code": "BAIDU_OCR_RESULT_INVALID", "message": "ocrResults item is not an object."}], counters
    pruned = ocr_result.get("prunedResult")
    if not isinstance(pruned, dict):
        return [], [{"code": "BAIDU_PRUNED_RESULT_MISSING", "message": "ocrResults item has no prunedResult."}], counters

    texts = pruned.get("rec_texts")
    if not isinstance(texts, list):
        return [], [{"code": "BAIDU_REC_TEXTS_MISSING", "message": "prunedResult.rec_texts is missing."}], counters
    scores = pruned.get("rec_scores")
    boxes = pruned.get("rec_boxes")
    polys = pruned.get("rec_polys")
    if not isinstance(scores, list):
        scores = []
    if not isinstance(boxes, list):
        boxes = []
    if not isinstance(polys, list):
        polys = []

    blocks: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    counters["rawTextCount"] = len(texts)
    for index, value in enumerate(texts):
        block_id = f"text_{start_index + index:04d}"
        text = str(value).strip()
        if not text:
            counters["droppedEmptyTextCount"] += 1
            warnings.append({"code": "OCR_TEXT_EMPTY", "message": "Empty OCR text was dropped.", "blockId": block_id})
            continue
        confidence = parse_score(scores[index] if index < len(scores) else None)
        if confidence < min_confidence:
            counters["filteredLowConfidenceCount"] += 1
            warnings.append(
                {
                    "code": "OCR_LOW_CONFIDENCE",
                    "message": f"OCR text was dropped because confidence {confidence:.3f} is below threshold.",
                    "blockId": block_id,
                }
            )
            continue
        bbox = rec_box_to_bbox(boxes[index] if index < len(boxes) else None)
        if bbox is None:
            bbox = polygon_to_bbox(polys[index] if index < len(polys) else None)
        if bbox is None:
            counters["droppedInvalidBoxCount"] += 1
            warnings.append({"code": "INVALID_OCR_BBOX", "message": "OCR bbox is missing or invalid.", "blockId": block_id})
            continue
        blocks.append(
            {
                "id": block_id,
                "text": text,
                "bbox": bbox,
                "confidence": confidence,
                "source": PROVIDER_BAIDU_PPOCRV5,
            }
        )
    return blocks, warnings, counters


def parse_score(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def rec_box_to_bbox(value: Any) -> dict[str, int] | None:
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
    return {"x": round(x1), "y": round(y1), "width": round(width), "height": round(height)}


def polygon_to_bbox(value: Any) -> dict[str, int] | None:
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
    return {"x": round(min(xs)), "y": round(min(ys)), "width": round(width), "height": round(height)}
