from __future__ import annotations

from fastapi import APIRouter, Response, status

from ..readiness import readiness_report
from ..state import state


router = APIRouter()


@router.get("/api/health")
def health() -> dict[str, object]:
    return {"success": True, "data": {"status": "ok"}}


@router.get("/api/ready")
def ready(response: Response) -> dict[str, object]:
    report = readiness_report(state.settings)
    if not report["ready"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"success": report["ready"], "data": report}
