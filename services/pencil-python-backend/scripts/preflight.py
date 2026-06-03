from __future__ import annotations

import argparse
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.config import Settings, get_settings
from app.readiness import (
    default_boundary_source_check,
    m29extract_check,
    ocr_check,
    psdlike_root_check,
    runtime_imports_check,
    storage_root_check,
)


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
        runtime_imports_check(),
        storage_root_check(settings.storage_root),
        psdlike_root_check(settings.psdlike_root),
        default_boundary_source_check(settings),
        m29extract_check(settings, require_m29=args.require_m29),
        ocr_check(settings, require_baidu_token=args.require_baidu_token),
    ]

    failed = False
    for result in checks:
        status = "ok" if result["ok"] else "fail"
        print(f"{result['name']}={status} {result['detail']}")
        failed = failed or not result["ok"]

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


if __name__ == "__main__":
    raise SystemExit(main())
