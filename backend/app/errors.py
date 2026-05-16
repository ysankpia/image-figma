from __future__ import annotations

from typing import Any

from fastapi import status
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        stage: str,
        task_id: str | None = None,
        detail: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.stage = stage
        self.task_id = task_id
        self.detail = detail


def success_response(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data}


def error_response(error: ApiError) -> JSONResponse:
    payload: dict[str, Any] = {
        "success": False,
        "error": {
            "code": error.code,
            "message": error.message,
            "stage": error.stage,
        },
    }
    if error.detail is not None:
        payload["error"]["detail"] = error.detail
    if error.task_id is not None:
        payload["error"]["taskId"] = error.task_id
    return JSONResponse(status_code=error.status_code, content=payload)
