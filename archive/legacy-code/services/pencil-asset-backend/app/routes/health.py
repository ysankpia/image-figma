from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from ..state import state


router = APIRouter()


@router.get("/api/health")
def health() -> dict[str, object]:
    return {"success": True, "data": {"status": "ok", "service": "pencil-asset-backend"}}


@router.get("/api/ready")
def ready() -> dict[str, object]:
    settings = state.settings
    checks = {
        "storageRoot": str(settings.storage_root),
        "yoloModel": str(settings.yolo_model) if settings.yolo_model else None,
        "yoloModelExists": bool(settings.yolo_model and settings.yolo_model.exists()),
        "m29extract": str(settings.m29extract_path) if settings.m29extract_path else None,
        "m29extractExists": bool(settings.m29extract_path and settings.m29extract_path.exists()),
        "psdlikeRoot": str(settings.psdlike_root),
        "psdlikeRootExists": settings.psdlike_root.exists(),
        "ocrProvider": settings.ocr_provider,
    }
    if not checks["yoloModelExists"]:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "message": "YOLO UI model is required: set PENCIL_ASSET_YOLO_MODEL",
                "checks": checks,
            },
        )
    return {"success": True, "data": {"status": "ready", "checks": checks}}


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)
