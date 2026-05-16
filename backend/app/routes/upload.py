from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, File, UploadFile, status

from ..database import json_dumps
from ..dsl_factory import build_deterministic_dsl
from ..errors import ApiError, success_response
from ..state import state
from ..storage import is_png, read_png_metadata

router = APIRouter(prefix="/api")


@router.post("/upload")
async def upload_png(file: UploadFile = File(...)) -> dict[str, object]:
    task_id: str | None = None
    try:
        data = await file.read()
        if len(data) > state.settings.max_upload_bytes:
            raise ApiError(
                "FILE_TOO_LARGE",
                "PNG file is too large.",
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                stage="upload",
            )

        if file.content_type != "image/png" or not is_png(data):
            raise ApiError(
                "INVALID_FILE_TYPE",
                "Only PNG uploads are supported.",
                status_code=status.HTTP_400_BAD_REQUEST,
                stage="upload",
            )

        image = read_png_metadata(data)
        if image is None:
            raise ApiError(
                "INVALID_IMAGE_DIMENSIONS",
                "PNG image dimensions could not be read.",
                status_code=status.HTTP_400_BAD_REQUEST,
                stage="upload",
            )

        task_id = f"task_{secrets.token_hex(6)}"
        now = datetime.now(UTC).isoformat()
        upload_path = state.storage.save_upload(task_id, data)
        banner_path = state.storage.create_banner_asset(task_id, upload_path)
        dsl = build_deterministic_dsl(
            task_id=task_id,
            original_url=state.storage.original_url(task_id),
            fallback_url=state.storage.banner_url(task_id),
            image=image,
        )
        dsl_path = state.storage.dsl_path(task_id)
        dsl_path.write_text(json.dumps(dsl, ensure_ascii=False, indent=2), encoding="utf-8")

        state.database.insert_task(
            {
                "id": task_id,
                "status": "completed",
                "stage": "completed",
                "progress": 100,
                "message": "Deterministic DSL is ready.",
                "original_filename": file.filename or "upload.png",
                "mime_type": file.content_type or "image/png",
                "file_size": len(data),
                "upload_path": str(upload_path),
                "created_at": now,
                "updated_at": now,
                "completed_at": now,
                "failed_at": None,
            }
        )
        state.database.insert_asset(
            {
                "asset_id": "asset_original",
                "task_id": task_id,
                "role": "original",
                "path": str(upload_path),
                "url": state.storage.original_url(task_id),
                "mime_type": "image/png",
                "width": image.width,
                "height": image.height,
                "created_at": now,
            }
        )
        state.database.insert_asset(
            {
                "asset_id": "asset_banner",
                "task_id": task_id,
                "role": "fallback_region",
                "path": str(banner_path),
                "url": state.storage.banner_url(task_id),
                "mime_type": "image/png",
                "width": image.width,
                "height": image.height,
                "created_at": now,
            }
        )
        state.database.insert_dsl_result(
            {
                "task_id": task_id,
                "dsl_path": str(dsl_path),
                "version": "0.1",
                "validation_status": "valid",
                "validation_errors": json_dumps([]),
                "created_at": now,
            }
        )

        return success_response(
            {
                "taskId": task_id,
                "status": "completed",
                "stage": "completed",
                "progress": 100,
                "file": {
                    "filename": file.filename or "upload.png",
                    "mimeType": file.content_type or "image/png",
                    "size": len(data),
                },
            }
        )
    except ApiError:
        raise
    except Exception as error:
        state.database.insert_error(
            task_id=task_id,
            stage="upload",
            error_code="UPLOAD_FAILED",
            message="Upload failed.",
            detail=str(error),
        )
        raise ApiError(
            "UPLOAD_FAILED",
            "Upload failed.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            stage="upload",
            task_id=task_id,
            detail=str(error),
        ) from error
