from __future__ import annotations

from pathlib import Path
from typing import Any

import orjson

from .schema import dataclass_to_dict


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = dataclass_to_dict(payload)
    path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))


def error_payload(stage: str, error: Exception | str) -> dict[str, Any]:
    message = str(error)
    return {
        "version": "pipeline_stage_error.v1",
        "stage": stage,
        "error": message,
        "policy": "continue_with_degraded_output",
    }
