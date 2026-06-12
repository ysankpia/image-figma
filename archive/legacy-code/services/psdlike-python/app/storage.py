from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from .config import get_settings


def new_task_id() -> str:
    return uuid.uuid4().hex


def task_dir(task_id: str) -> Path:
    return get_settings().storage_dir / task_id


def compile_dir(task_id: str) -> Path:
    return task_dir(task_id) / "compile"


def create_task_dirs(task_id: str) -> Path:
    root = task_dir(task_id)
    (root / "compile").mkdir(parents=True, exist_ok=True)
    return root


def save_upload(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def copy_input(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def write_error(task_id: str, exc: Exception) -> None:
    write_error_payload(
        task_id,
        {
            "taskId": task_id,
            "status": "failed",
            "errorType": type(exc).__name__,
            "message": str(exc),
        },
    )


def write_error_payload(task_id: str, payload: dict[str, Any]) -> None:
    root = task_dir(task_id)
    root.mkdir(parents=True, exist_ok=True)
    (root / "error.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
