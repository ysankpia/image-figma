from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import requests

from http_smoke import ALL_MODES, assert_ready, check_design_refs, content_type_for


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload images to Pencil Python Backend and download project.zip.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8100")
    parser.add_argument("--input", action="append", default=[], type=Path, help="Image file or directory. Repeatable.")
    parser.add_argument("--out", required=True, type=Path, help="Output directory for project.zip and unzipped verification.")
    parser.add_argument("--project-name", default="Pencil HTTP Project")
    parser.add_argument("--mode", default="all", choices=("all", "clean-editable", "visual-fidelity", "visual-ocr"))
    parser.add_argument("--columns", default="auto")
    parser.add_argument("--include-debug", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--ocr-provider", default=None)
    parser.add_argument("--boundary-source", choices=("m29", "psdlike", "hybrid"), default=None)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--keep-unzipped", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    images = discover_images(args.input)
    if not images:
        print("no input images found", file=sys.stderr)
        return 2

    base_url = args.base_url.rstrip("/")
    out_dir = args.out.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / "project.zip"
    unzip_dir = out_dir / "unzipped"
    if zip_path.exists():
        zip_path.unlink()
    if unzip_dir.exists():
        shutil.rmtree(unzip_dir)

    health = requests.get(f"{base_url}/api/health", timeout=10)
    health.raise_for_status()
    print(f"health={health.json()['data']['status']}")
    assert_ready(base_url)

    files = []
    handles = []
    try:
        for image in images:
            handle = image.open("rb")
            handles.append(handle)
            files.append(("files[]", (image.name, handle, content_type_for(image))))
        data: dict[str, str] = {
            "projectName": args.project_name,
            "mode": args.mode,
            "columns": args.columns,
            "includeDebug": str(args.include_debug).lower(),
        }
        if args.ocr_provider:
            data["ocrProvider"] = args.ocr_provider
        if args.boundary_source:
            data["boundarySource"] = args.boundary_source
        response = requests.post(f"{base_url}/api/pencil/projects", data=data, files=files, timeout=60)
    finally:
        for handle in handles:
            handle.close()

    response.raise_for_status()
    created = response.json()["data"]
    task_id = created["taskId"]
    boundary_source = created.get("boundarySource")
    print(f"queued taskId={task_id} boundarySource={boundary_source} inputCount={len(images)}")

    status = wait_for_completion(base_url, task_id, args.timeout_seconds, args.poll_seconds)
    print(
        "completed "
        f"taskId={task_id} "
        f"boundarySource={status.get('boundarySource')} "
        f"pageCount={status.get('pageCount')} "
        f"modes={','.join(status.get('modes', []))}"
    )

    manifest_response = requests.get(f"{base_url}/api/pencil/projects/{task_id}/manifest", timeout=30)
    manifest_response.raise_for_status()
    manifest = manifest_response.json()["data"]
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"manifest={out_dir / 'manifest.json'}")

    download = requests.get(f"{base_url}/api/pencil/projects/{task_id}/download.zip", timeout=120)
    download.raise_for_status()
    zip_path.write_bytes(download.content)
    if zip_path.read_bytes()[:2] != b"PK":
        raise AssertionError("downloaded file is not a ZIP")
    print(f"zip={zip_path} bytes={zip_path.stat().st_size}")

    verify_zip(zip_path, unzip_dir, args.mode)
    if not args.keep_unzipped:
        shutil.rmtree(unzip_dir)
    print("ok")
    return 0


def discover_images(inputs: list[Path]) -> list[Path]:
    images: list[Path] = []
    for raw in inputs:
        path = raw.expanduser().resolve()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            images.append(path)
        elif path.is_dir():
            for child in sorted(path.iterdir()):
                if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS:
                    images.append(child.resolve())
        elif path.exists():
            raise ValueError(f"unsupported input path: {path}")
        else:
            raise FileNotFoundError(path)
    return images


def wait_for_completion(base_url: str, task_id: str, timeout_seconds: float, poll_seconds: float) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = requests.get(f"{base_url}/api/pencil/projects/{task_id}", timeout=10)
        response.raise_for_status()
        data = response.json()["data"]
        state = data.get("status")
        if state == "completed":
            return data
        if state == "failed":
            raise AssertionError(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"status={state} boundarySource={data.get('boundarySource')}")
        time.sleep(poll_seconds)
    raise TimeoutError(f"task did not complete within {timeout_seconds} seconds: {task_id}")


def verify_zip(zip_path: Path, unzip_dir: Path, mode: str) -> None:
    expected_modes = list(ALL_MODES) if mode == "all" else [mode]
    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        required = {"manifest.json", "debug/report.md"}
        required.update(f"{item}/design.pen" for item in expected_modes)
        missing = sorted(required - names)
        if missing:
            raise AssertionError(f"ZIP missing required files: {missing}")
        archive.extractall(unzip_dir)

    for item in expected_modes:
        refs, bad_refs, missing_refs = check_design_refs(unzip_dir, item)
        print(f"{item} refs={refs} badRefs={bad_refs} missingRefs={missing_refs}")
        if bad_refs or missing_refs:
            raise AssertionError(f"{item} has badRefs={bad_refs} missingRefs={missing_refs}")


if __name__ == "__main__":
    raise SystemExit(main())
