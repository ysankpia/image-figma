from __future__ import annotations

import argparse
import importlib
import os
import stat
import sys
from pathlib import Path
from typing import NamedTuple

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import Settings, get_settings


class CheckResult(NamedTuple):
    name: str
    ok: bool
    detail: str


RUNTIME_IMPORTS = ("fastapi", "uvicorn", "multipart", "PIL", "numpy", "pydantic", "requests")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight check for Pencil Python Backend deployment config.")
    parser.add_argument(
        "--require-m29",
        action="store_true",
        help="Require a valid m29extract executable even when the default boundary source is psdlike.",
    )
    parser.add_argument(
        "--require-baidu-token",
        action="store_true",
        help="Fail when OCR_PROVIDER=baidu_ppocrv5 and BAIDU_PADDLE_OCR_TOKEN is empty.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        settings = get_settings()
    except Exception as error:
        print(f"settings=fail {error}", file=sys.stderr)
        return 1

    print_settings(settings)
    checks = [
        check_runtime_imports(),
        check_storage_root(settings.storage_root),
        check_psdlike_root(settings.psdlike_root),
        check_default_boundary_source(settings),
        check_m29extract(settings, require_m29=args.require_m29),
        check_ocr(settings, require_baidu_token=args.require_baidu_token),
    ]

    failed = False
    for result in checks:
        status = "ok" if result.ok else "fail"
        print(f"{result.name}={status} {result.detail}")
        failed = failed or not result.ok

    if failed:
        print("preflight=fail", file=sys.stderr)
        return 1
    print("preflight=ok")
    return 0


def print_settings(settings: Settings) -> None:
    print(f"addr={settings.addr}")
    print(f"storageRoot={settings.storage_root}")
    print(f"defaultBoundarySource={settings.default_boundary_source}")
    print(f"psdlikeRoot={settings.psdlike_root}")
    print(f"m29extract={settings.m29extract_path or ''}")
    print(f"maxFiles={settings.max_files}")
    print(f"maxUploadBytes={settings.max_upload_bytes}")
    print(f"maxWorkers={settings.max_workers}")
    print(f"ocrProvider={settings.ocr_provider}")


def check_runtime_imports() -> CheckResult:
    missing: list[str] = []
    for module_name in RUNTIME_IMPORTS:
        try:
            importlib.import_module(module_name)
        except Exception as error:
            missing.append(f"{module_name}({error})")
    if missing:
        return CheckResult("runtimeImports", False, ", ".join(missing))
    return CheckResult("runtimeImports", True, ",".join(RUNTIME_IMPORTS))


def check_storage_root(path: Path) -> CheckResult:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".preflight-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except Exception as error:
        return CheckResult("storageRoot", False, f"{path}: {error}")
    return CheckResult("storageRoot", True, str(path))


def check_psdlike_root(path: Path) -> CheckResult:
    script = path / "tools" / "run_one.py"
    if not script.exists():
        return CheckResult("psdlikeRunner", False, f"missing {script}")
    pyproject = path / "pyproject.toml"
    if not pyproject.exists():
        return CheckResult("psdlikeRunner", False, f"missing {pyproject}")
    return CheckResult("psdlikeRunner", True, str(script))


def check_default_boundary_source(settings: Settings) -> CheckResult:
    if settings.default_boundary_source == "psdlike":
        return CheckResult("defaultBoundarySource", True, "psdlike")
    if settings.default_boundary_source == "hybrid":
        return CheckResult("defaultBoundarySource", True, "hybrid requires psdlike and m29extract")
    return CheckResult("defaultBoundarySource", True, "m29 explicit legacy default")


def check_m29extract(settings: Settings, *, require_m29: bool) -> CheckResult:
    needed = require_m29 or settings.default_boundary_source in {"m29", "hybrid"}
    if settings.m29extract_path is None:
        if needed:
            return CheckResult("m29extract", False, "missing PENCIL_BACKEND_M29EXTRACT or backend-go/bin/m29extract")
        return CheckResult("m29extract", True, "not configured; ok for default psdlike")
    path = settings.m29extract_path
    if not path.exists():
        return CheckResult("m29extract", False, f"missing {path}")
    if path.is_dir():
        return CheckResult("m29extract", False, f"is a directory: {path}")
    mode = path.stat().st_mode
    if not mode & stat.S_IXUSR:
        return CheckResult("m29extract", False, f"not executable: {path}")
    return CheckResult("m29extract", True, str(path))


def check_ocr(settings: Settings, *, require_baidu_token: bool) -> CheckResult:
    if settings.ocr_provider != "baidu_ppocrv5":
        return CheckResult("ocr", True, settings.ocr_provider)
    token = os.getenv("BAIDU_PADDLE_OCR_TOKEN", "").strip()
    if require_baidu_token and not token:
        return CheckResult("ocr", False, "OCR_PROVIDER=baidu_ppocrv5 but BAIDU_PADDLE_OCR_TOKEN is empty")
    detail = "baidu_ppocrv5 token=set" if token else "baidu_ppocrv5 token=empty"
    return CheckResult("ocr", True, detail)


if __name__ == "__main__":
    raise SystemExit(main())
