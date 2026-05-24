from __future__ import annotations

import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, File, UploadFile, status

from ..errors import ApiError, success_response
from ..m30_upload_pipeline import run_m30_preview_pipeline
from ..png_tools import is_png, read_png_metadata
from ..state import state

router = APIRouter(prefix="/api")


@router.post("/upload-m30-preview")
async def upload_png_m30_preview(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> dict[str, object]:
    data = await file.read()
    if len(data) > state.settings.max_upload_bytes:
        raise ApiError(
            "FILE_TOO_LARGE",
            "PNG file is too large.",
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            stage="upload_m30_preview",
        )
    if file.content_type != "image/png" or not is_png(data):
        raise ApiError(
            "INVALID_FILE_TYPE",
            "Only PNG uploads are supported.",
            status_code=status.HTTP_400_BAD_REQUEST,
            stage="upload_m30_preview",
        )
    image = read_png_metadata(data)
    if image is None:
        raise ApiError(
            "INVALID_IMAGE_DIMENSIONS",
            "PNG image dimensions could not be read.",
            status_code=status.HTTP_400_BAD_REQUEST,
            stage="upload_m30_preview",
        )

    task_id = f"task_{secrets.token_hex(6)}"
    now = datetime.now(UTC).isoformat()
    upload_path = state.storage.save_upload(task_id, data)
    state.database.insert_task(
        {
            "id": task_id,
            "status": "processing",
            "stage": "m29_queued",
            "progress": 1,
            "message": "M29 plan-driven pipeline queued.",
            "original_filename": file.filename or "upload.png",
            "mime_type": file.content_type or "image/png",
            "file_size": len(data),
            "upload_path": str(upload_path),
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
            "failed_at": None,
        }
    )
    background_tasks.add_task(run_m30_preview_pipeline, task_id)
    return success_response(
        {
            "taskId": task_id,
            "status": "processing",
            "stage": "m29_queued",
            "progress": 1,
            "file": {
                "filename": file.filename or "upload.png",
                "mimeType": file.content_type or "image/png",
                "size": len(data),
                "width": image.width,
                "height": image.height,
            },
        }
    )
