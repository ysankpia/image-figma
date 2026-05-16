from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ApiSuccess(BaseModel):
    success: Literal[True]
    data: dict[str, Any]


class ApiErrorBody(BaseModel):
    code: str
    message: str
    stage: str
    detail: str | None = None
    taskId: str | None = None


class ApiFailure(BaseModel):
    success: Literal[False]
    error: ApiErrorBody
