from __future__ import annotations

from fastapi import APIRouter


router = APIRouter()


@router.get("/api/health")
def health() -> dict[str, object]:
    return {"success": True, "data": {"status": "ok"}}
