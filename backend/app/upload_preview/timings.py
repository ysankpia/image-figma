from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Literal, TypeVar

from .paths import UploadPreviewPaths
from .types import UploadPreviewPipelineError

T = TypeVar("T")


@dataclass
class StageTiming:
    stage: str
    started_at: str
    completed_at: str | None
    elapsed_seconds: float | None
    status: Literal["running", "completed", "failed"]
    error_code: str | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "startedAt": self.started_at,
            "completedAt": self.completed_at,
            "elapsedSeconds": self.elapsed_seconds,
            "status": self.status,
            "errorCode": self.error_code,
            "message": self.message,
        }


def run_stage(paths: UploadPreviewPaths, timings: list[StageTiming], stage: str, action: Callable[[], T]) -> T:
    started_perf = time.perf_counter()
    timing = StageTiming(
        stage=stage,
        started_at=datetime.now(UTC).isoformat(),
        completed_at=None,
        elapsed_seconds=None,
        status="running",
    )
    timings.append(timing)
    write_stage_timings(paths, timings)
    try:
        result = action()
    except UploadPreviewPipelineError as error:
        finish_stage_timing(timing, started_perf, "failed", error.code, str(error))
        write_stage_timings(paths, timings)
        raise
    except Exception as error:
        finish_stage_timing(timing, started_perf, "failed", error.__class__.__name__, str(error))
        write_stage_timings(paths, timings)
        raise UploadPreviewPipelineError(stage, error.__class__.__name__, str(error)) from error
    finish_stage_timing(timing, started_perf, "completed", None, None)
    write_stage_timings(paths, timings)
    return result


def finish_stage_timing(
    timing: StageTiming,
    started_perf: float,
    status: Literal["completed", "failed"],
    error_code: str | None,
    message: str | None,
) -> None:
    timing.completed_at = datetime.now(UTC).isoformat()
    timing.elapsed_seconds = round(time.perf_counter() - started_perf, 3)
    timing.status = status
    timing.error_code = error_code
    timing.message = message


def write_stage_timings(paths: UploadPreviewPaths, timings: list[StageTiming]) -> None:
    paths.root.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaName": "UploadPreviewStageTimings",
        "schemaVersion": "0.1",
        "stages": [timing.to_dict() for timing in timings],
    }
    (paths.root / "stage_timings.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

