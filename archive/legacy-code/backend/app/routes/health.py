from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from ..errors import success_response
from ..state import state

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, object]:
    return success_response(
        {
            "status": "ok",
            "version": state.settings.version,
            "time": datetime.now(UTC).isoformat(),
        }
    )
