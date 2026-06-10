from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from ..state import state


router = APIRouter()


@router.get("/api/health")
def health() -> dict[str, object]:
    return {"success": True, "data": {"status": "ok", "service": "pencil-handoff-studio"}}


@router.get("/api/ready")
def ready() -> JSONResponse:
    checks = [
        {"name": "storage", "ok": writable_storage(), "detail": str(state.settings.storage_root)},
        {
            "name": "yolo",
            "ok": state.settings.yolo_model is not None and state.settings.yolo_model.exists(),
            "detail": str(state.settings.yolo_model or "not configured; project creation will warn and continue"),
        },
        {
            "name": "m29extract",
            "ok": state.settings.m29extract_path is not None and state.settings.m29extract_path.exists(),
            "detail": str(state.settings.m29extract_path or "not configured; M29 evidence skipped"),
        },
        {
            "name": "psdlike",
            "ok": (state.settings.psdlike_root / "tools" / "run_one.py").exists(),
            "detail": str(state.settings.psdlike_root),
        },
    ]
    ok = checks[0]["ok"]
    status = 200 if ok else 503
    return JSONResponse(status_code=status, content={"success": ok, "data": {"checks": checks}})


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)


def writable_storage() -> bool:
    try:
        state.settings.storage_root.mkdir(parents=True, exist_ok=True)
        probe = state.settings.storage_root / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False
