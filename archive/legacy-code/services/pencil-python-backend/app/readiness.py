from __future__ import annotations

import importlib
import os
import stat
from pathlib import Path
from typing import Any

from .config import Settings


RUNTIME_IMPORTS = ("fastapi", "uvicorn", "multipart", "PIL", "numpy", "pydantic", "requests")


def readiness_report(settings: Settings, *, require_m29: bool = False) -> dict[str, Any]:
    checks = [
        runtime_imports_check(),
        storage_root_check(settings.storage_root),
        psdlike_root_check(settings.psdlike_root),
        default_boundary_source_check(settings),
        m29extract_check(settings, require_m29=require_m29),
        ocr_check(settings),
    ]
    ready = all(check["ok"] for check in checks)
    return {
        "status": "ready" if ready else "not_ready",
        "ready": ready,
        "checks": checks,
    }


def runtime_imports_check() -> dict[str, Any]:
    missing: list[str] = []
    for module_name in RUNTIME_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception as error:
            missing.append(f"{module_name}({error})")
    return {
        "name": "runtimeImports",
        "ok": not missing,
        "detail": ",".join(RUNTIME_IMPORTS) if not missing else ", ".join(missing),
    }


def storage_root_check(path: Path) -> dict[str, Any]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".ready-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as error:
        return {"name": "storageRoot", "ok": False, "detail": f"{path}: {error}"}
    return {"name": "storageRoot", "ok": True, "detail": str(path)}


def psdlike_root_check(path: Path) -> dict[str, Any]:
    script = path / "tools" / "run_one.py"
    if not script.exists():
        return {"name": "psdlikeRunner", "ok": False, "detail": f"missing {script}"}
    pyproject = path / "pyproject.toml"
    if not pyproject.exists():
        return {"name": "psdlikeRunner", "ok": False, "detail": f"missing {pyproject}"}
    return {"name": "psdlikeRunner", "ok": True, "detail": str(script)}


def default_boundary_source_check(settings: Settings) -> dict[str, Any]:
    if settings.default_boundary_source == "psdlike":
        detail = "psdlike"
    elif settings.default_boundary_source == "hybrid":
        detail = "hybrid requires psdlike and m29extract"
    else:
        detail = "m29 explicit legacy default"
    return {"name": "defaultBoundarySource", "ok": True, "detail": detail}


def m29extract_check(settings: Settings, *, require_m29: bool) -> dict[str, Any]:
    needed = require_m29 or settings.default_boundary_source in {"m29", "hybrid"}
    if settings.m29extract_path is None:
        if needed:
            return {
                "name": "m29extract",
                "ok": False,
                "detail": "missing PENCIL_BACKEND_M29EXTRACT or backend-go/bin/m29extract",
            }
        return {"name": "m29extract", "ok": True, "detail": "not configured; ok for default psdlike"}
    path = settings.m29extract_path
    if not path.exists():
        return {"name": "m29extract", "ok": False, "detail": f"missing {path}"}
    if path.is_dir():
        return {"name": "m29extract", "ok": False, "detail": f"is a directory: {path}"}
    if not path.stat().st_mode & stat.S_IXUSR:
        return {"name": "m29extract", "ok": False, "detail": f"not executable: {path}"}
    return {"name": "m29extract", "ok": True, "detail": str(path)}


def ocr_check(settings: Settings, *, require_baidu_token: bool = False) -> dict[str, Any]:
    if settings.ocr_provider != "baidu_ppocrv5":
        return {"name": "ocr", "ok": True, "detail": settings.ocr_provider}
    token = os.getenv("BAIDU_PADDLE_OCR_TOKEN", "").strip()
    if require_baidu_token and not token:
        return {
            "name": "ocr",
            "ok": False,
            "detail": "OCR_PROVIDER=baidu_ppocrv5 but BAIDU_PADDLE_OCR_TOKEN is empty",
        }
    detail = "baidu_ppocrv5 token=set" if token else "baidu_ppocrv5 token=empty"
    return {"name": "ocr", "ok": True, "detail": detail}
