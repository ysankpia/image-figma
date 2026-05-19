from __future__ import annotations

from typing import Literal


TaskStatus = Literal["processing", "completed", "failed"]
TaskStage = Literal["completed", "failed", "upload", "task_lookup", "dsl_lookup", "asset_lookup"]
