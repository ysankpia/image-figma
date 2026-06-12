from __future__ import annotations

from datetime import UTC, datetime

from ..state import state


def update_task(task_id: str, stage: str, progress: int, message: str) -> None:
    state.database.update_task(
        task_id,
        status="processing",
        stage=stage,
        progress=progress,
        message=message,
        updated_at=datetime.now(UTC).isoformat(),
    )


def complete_task(task_id: str) -> None:
    now = datetime.now(UTC).isoformat()
    state.database.update_task(
        task_id,
        status="completed",
        stage="m29_completed",
        progress=100,
        message="M29 plan-driven DSL is ready.",
        updated_at=now,
        completed_at=now,
    )


def fail_task(task_id: str, stage: str, code: str, message: str) -> None:
    now = datetime.now(UTC).isoformat()
    state.database.insert_error(
        task_id=task_id,
        stage=stage,
        error_code=code,
        message=message,
    )
    state.database.update_task(
        task_id,
        status="failed",
        stage=stage,
        progress=100,
        message=message,
        updated_at=now,
        failed_at=now,
    )

