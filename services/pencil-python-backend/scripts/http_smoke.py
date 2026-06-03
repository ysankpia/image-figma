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


ALL_MODES = ("clean-editable", "visual-fidelity", "visual-ocr")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test the Pencil Python Backend HTTP export path.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8100")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--project-name", default="Pencil HTTP Smoke")
    parser.add_argument("--mode", default="all", choices=("all", "clean-editable", "visual-fidelity", "visual-ocr"))
    parser.add_argument("--expected-boundary-source", default="psdlike", choices=("m29", "psdlike", "hybrid"))
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    image_path = args.image.expanduser().resolve()
    out_dir = args.out.expanduser().resolve()
    if not image_path.exists():
        print(f"image does not exist: {image_path}", file=sys.stderr)
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    expected_modes = list(ALL_MODES) if args.mode == "all" else [args.mode]
    zip_path = out_dir / "project.zip"
    unzip_dir = out_dir / "unzipped"
    if zip_path.exists():
        zip_path.unlink()
    if unzip_dir.exists():
        shutil.rmtree(unzip_dir)

    health = requests.get(f"{base_url}/api/health", timeout=10)
    health.raise_for_status()
    print(f"health={health.json()['data']['status']}")

    with image_path.open("rb") as handle:
        response = requests.post(
            f"{base_url}/api/pencil/projects",
            data={
                "projectName": args.project_name,
                "mode": args.mode,
                "columns": "1",
                "includeDebug": "true",
            },
            files={"files[]": (image_path.name, handle, content_type_for(image_path))},
            timeout=30,
        )
    response.raise_for_status()
    created = response.json()["data"]
    task_id = created["taskId"]
    created_boundary = created.get("boundarySource")
    print(f"queued taskId={task_id} boundarySource={created_boundary}")
    if created_boundary != args.expected_boundary_source:
        raise AssertionError(f"queued boundarySource={created_boundary}, expected {args.expected_boundary_source}")

    status = wait_for_completion(base_url, task_id, args.timeout_seconds, args.poll_seconds)
    status_boundary = status.get("boundarySource")
    print(f"status={status['status']} boundarySource={status_boundary}")
    if status_boundary != args.expected_boundary_source:
        raise AssertionError(f"status boundarySource={status_boundary}, expected {args.expected_boundary_source}")

    manifest_response = requests.get(f"{base_url}/api/pencil/projects/{task_id}/manifest", timeout=30)
    manifest_response.raise_for_status()
    manifest = manifest_response.json()["data"]
    manifest_boundary = manifest.get("boundarySource")
    print(
        "manifest "
        f"boundarySource={manifest_boundary} "
        f"pageCount={manifest.get('pageCount')} "
        f"modes={','.join(manifest.get('modes', []))}"
    )
    if manifest_boundary != args.expected_boundary_source:
        raise AssertionError(f"manifest boundarySource={manifest_boundary}, expected {args.expected_boundary_source}")

    download = requests.get(f"{base_url}/api/pencil/projects/{task_id}/download.zip", timeout=60)
    download.raise_for_status()
    zip_path.write_bytes(download.content)
    if zip_path.read_bytes()[:2] != b"PK":
        raise AssertionError("downloaded file is not a ZIP")
    print(f"zip={zip_path} bytes={zip_path.stat().st_size}")

    with ZipFile(zip_path) as archive:
        names = set(archive.namelist())
        required = {"manifest.json", "debug/report.md"}
        required.update(f"{mode}/design.pen" for mode in expected_modes)
        missing = sorted(required - names)
        if missing:
            raise AssertionError(f"ZIP missing required files: {missing}")
        archive.extractall(unzip_dir)

    for mode in expected_modes:
        refs, bad_refs, missing_refs = check_design_refs(unzip_dir, mode)
        print(f"{mode} refs={refs} badRefs={bad_refs} missingRefs={missing_refs}")
        if bad_refs or missing_refs:
            raise AssertionError(f"{mode} has badRefs={bad_refs} missingRefs={missing_refs}")

    print("ok")
    return 0


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
        time.sleep(poll_seconds)
    raise TimeoutError(f"task did not complete within {timeout_seconds} seconds: {task_id}")


def check_design_refs(root: Path, mode: str) -> tuple[int, int, int]:
    design_path = root / mode / "design.pen"
    design = json.loads(design_path.read_text(encoding="utf-8"))
    refs: list[str] = []
    for child in design.get("children", []):
        collect_image_refs(child, refs)

    bad_refs = [
        ref
        for ref in refs
        if not ref.startswith("./assets/visible/")
        or "../" in ref
        or "source.png" in ref
        or "debug/" in ref
        or "raw-crops" in ref
        or "masks/" in ref
    ]
    missing_refs = [ref for ref in refs if not (root / mode / ref.removeprefix("./")).exists()]
    return len(refs), len(bad_refs), len(missing_refs)


def collect_image_refs(node: Any, refs: list[str]) -> None:
    if not isinstance(node, dict):
        return
    fill = node.get("fill")
    if isinstance(fill, dict):
        append_image_ref(fill, refs)
    elif isinstance(fill, list):
        for item in fill:
            if isinstance(item, dict):
                append_image_ref(item, refs)
    for child in node.get("children", []) or []:
        collect_image_refs(child, refs)


def append_image_ref(fill: dict[str, Any], refs: list[str]) -> None:
    if fill.get("type") == "image" and isinstance(fill.get("url"), str):
        refs.append(fill["url"])


def content_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


if __name__ == "__main__":
    raise SystemExit(main())
