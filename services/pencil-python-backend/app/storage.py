from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .jsonio import read_json, write_json
from .utils import safe_slug


@dataclass(frozen=True)
class TaskPaths:
    task_id: str
    root: Path
    uploads: Path
    output: Path
    task_json: Path


class TaskStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.tasks_root = root / "tasks"
        self.tasks_root.mkdir(parents=True, exist_ok=True)

    def create_task(self, project_name: str) -> TaskPaths:
        task_id = f"pencil_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}"
        paths = self.paths(task_id)
        paths.uploads.mkdir(parents=True, exist_ok=True)
        paths.output.mkdir(parents=True, exist_ok=True)
        self.write_status(
            paths,
            {
                "taskId": task_id,
                "status": "queued",
                "projectName": project_name,
                "createdAt": datetime.now(UTC).isoformat(),
                "updatedAt": datetime.now(UTC).isoformat(),
                "warnings": [],
            },
        )
        return paths

    def paths(self, task_id: str) -> TaskPaths:
        safe_id = safe_slug(task_id, "task")
        root = self.tasks_root / safe_id
        return TaskPaths(
            task_id=safe_id,
            root=root,
            uploads=root / "uploads",
            output=root / "output",
            task_json=root / "task.json",
        )

    def read_status(self, task_id: str) -> dict[str, Any]:
        paths = self.paths(task_id)
        if not paths.task_json.exists():
            raise FileNotFoundError(task_id)
        return read_json(paths.task_json)

    def write_status(self, paths: TaskPaths, value: dict[str, Any]) -> None:
        write_json(paths.task_json, {**value, "updatedAt": datetime.now(UTC).isoformat()})

    def patch_status(self, paths: TaskPaths, **updates: Any) -> dict[str, Any]:
        current = read_json(paths.task_json) if paths.task_json.exists() else {"taskId": paths.task_id}
        next_status = {**current, **updates}
        self.write_status(paths, next_status)
        return next_status

    def clean_task(self, task_id: str) -> None:
        paths = self.paths(task_id)
        if paths.root.exists():
            shutil.rmtree(paths.root)
