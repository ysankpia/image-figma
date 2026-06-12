from __future__ import annotations

from fastapi import APIRouter, status

from ..errors import ApiError, success_response
from ..state import state

router = APIRouter(prefix="/api")


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str) -> dict[str, object]:
    asset = state.database.get_latest_asset(asset_id)
    if asset is None:
        raise ApiError(
            "ASSET_NOT_FOUND",
            "Asset not found.",
            status_code=status.HTTP_404_NOT_FOUND,
            stage="asset_lookup",
        )

    return success_response(
        {
            "assetId": asset["asset_id"],
            "taskId": asset["task_id"],
            "role": asset["role"],
            "url": asset["url"],
            "mimeType": asset["mime_type"],
        }
    )
