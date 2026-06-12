from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

import requests


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8120")
    parser.add_argument("--input", action="append", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--start-server", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    images = collect_images([Path(item).expanduser() for item in args.input])
    report: dict[str, Any] = {
        "schema": "pencil_handoff.acceptance_report.v1",
        "baseUrl": args.base_url,
        "inputs": [str(path) for path in images],
        "missingInputs": [item for item in args.input if not Path(item).expanduser().exists()],
        "checks": {},
    }
    if not images:
        report["ok"] = False
        report["error"] = "no input images found"
        write_reports(out_dir, report)
        return 2

    process: subprocess.Popen[str] | None = None
    if args.start_server:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8120"],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
        )
        wait_ready(args.base_url)

    try:
        project = create_project(args.base_url, images)
        project_id = project["projectId"]
        report["projectId"] = project_id
        report["checks"]["projectCreated"] = True
        report["checks"]["pageCount"] = project["pageCount"]
        report["checks"]["candidateCount"] = project["candidateCount"]

        candidates = get_json(args.base_url, f"/api/handoff-projects/{project_id}/candidates")
        review_state = get_json(args.base_url, f"/api/handoff-projects/{project_id}/review-state")
        if candidates["pages"] and candidates["pages"][0]["candidates"]:
            candidate_id = candidates["pages"][0]["candidates"][0]["id"]
            review_state["pages"][0]["hiddenCandidateIds"] = [candidate_id]
            review_state["pages"][0]["rejectedCandidateIds"] = [candidate_id]
            put_json(args.base_url, f"/api/handoff-projects/{project_id}/review-state", review_state)
        report["checks"]["reviewStateSaved"] = True

        manual = build_manual_slices(candidates)
        put_json(args.base_url, f"/api/handoff-projects/{project_id}/manual-slices", manual)
        selected_count = sum(len(page["slices"]) for page in manual["pages"])
        report["checks"]["manualSliceSaved"] = True
        report["checks"]["selectedSliceCount"] = selected_count

        preview = post_json(args.base_url, f"/api/handoff-projects/{project_id}/export-preview")
        report["checks"]["exportPreviewGenerated"] = preview["assetCount"] == selected_count
        manifest = post_json(args.base_url, f"/api/handoff-projects/{project_id}/export")
        report["checks"]["exported"] = True
        report["manifest"] = manifest

        project_zip = out_dir / "project.zip"
        assets_zip = out_dir / "assets.zip"
        download(args.base_url, f"/api/handoff-projects/{project_id}/project.zip", project_zip)
        download(args.base_url, f"/api/handoff-projects/{project_id}/assets.zip", assets_zip)
        report["checks"]["projectZipExists"] = project_zip.exists()
        report["checks"]["assetsZipExists"] = assets_zip.exists()
        report["checks"].update(check_archives(project_zip, assets_zip, selected_count, len(candidates["pages"])))
        report["ok"] = all_truthy(report["checks"])
        write_reports(out_dir, report)
        return 0 if report["ok"] else 1
    finally:
        if process is not None:
            process.terminate()
            process.wait(timeout=10)


def collect_images(inputs: list[Path]) -> list[Path]:
    images: list[Path] = []
    for item in inputs:
        if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS:
            images.append(item)
        elif item.is_dir():
            images.extend(sorted(path for path in item.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS))
    return images


def wait_ready(base_url: str) -> None:
    for _ in range(60):
        try:
            response = requests.get(f"{base_url}/api/health", timeout=2)
            if response.status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.5)
    raise RuntimeError("server did not become ready")


def create_project(base_url: str, images: list[Path]) -> dict[str, Any]:
    handles = []
    try:
        files = []
        for image in images:
            handle = image.open("rb")
            handles.append(handle)
            files.append(("files[]", (image.name, handle, "image/png")))
        response = requests.post(
            f"{base_url}/api/handoff-projects",
            data={"projectName": "Handoff Acceptance", "includeOcr": "true", "includeBasicElements": "true"},
            files=files,
            timeout=180,
        )
        response.raise_for_status()
        return response.json()["data"]
    finally:
        for handle in handles:
            handle.close()


def get_json(base_url: str, path: str) -> dict[str, Any]:
    response = requests.get(f"{base_url}{path}", timeout=60)
    response.raise_for_status()
    return response.json()["data"]


def put_json(base_url: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.put(f"{base_url}{path}", json=payload, timeout=60)
    response.raise_for_status()
    return response.json()["data"]


def post_json(base_url: str, path: str) -> dict[str, Any]:
    response = requests.post(f"{base_url}{path}", timeout=180)
    response.raise_for_status()
    return response.json()["data"]


def download(base_url: str, path: str, target: Path) -> None:
    response = requests.get(f"{base_url}{path}", timeout=180)
    response.raise_for_status()
    target.write_bytes(response.content)


def build_manual_slices(candidates: dict[str, Any]) -> dict[str, Any]:
    pages = []
    for page in candidates["pages"]:
        slices = []
        usable = [candidate for candidate in page.get("candidates") or [] if candidate["kind"] in {"image", "icon"}][:3]
        if not usable:
            usable = [
                {
                    "id": f"{page['pageId']}__manual_acceptance",
                    "kind": "image",
                    "bbox": {"x": 0, "y": 0, "width": max(1, min(64, page["width"])), "height": max(1, min(64, page["height"]))},
                }
            ]
        for index, candidate in enumerate(usable, start=1):
            kind = candidate["kind"] if candidate["kind"] in {"image", "icon"} else "image"
            slices.append(
                {
                    "id": f"{page['pageId']}__slice_{index:04d}",
                    "pageId": page["pageId"],
                    "name": f"slice_{index:04d}",
                    "displayName": f"slice_{index:04d}",
                    "kind": kind,
                    "bbox": candidate["bbox"],
                    "selected": True,
                    "source": "acceptance",
                    "candidateIds": [candidate["id"]] if "id" in candidate else [],
                    "tags": [],
                }
            )
        pages.append(
            {
                "pageId": page["pageId"],
                "sourceImage": page["sourceImage"],
                "width": page["width"],
                "height": page["height"],
                "slices": slices,
            }
        )
    return {"schema": "pencil.manual_slices.v1", "projectName": "Handoff Acceptance", "pages": pages}


def check_archives(project_zip: Path, assets_zip: Path, selected_count: int, page_count: int) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    with zipfile.ZipFile(project_zip) as archive:
        names = set(archive.namelist())
        checks["projectHasDesignPen"] = "design.pen" in names
        checks["projectHasManifest"] = "manifest.json" in names
        checks["projectOriginalCount"] = len([name for name in names if name.startswith("assets/originals/") and name.endswith(".png")])
        checks["projectSlicePngCount"] = len([name for name in names if name.startswith("assets/slices/") and name.endswith(".png")])
        design = json.loads(archive.read("design.pen"))
        refs: list[str] = []
        collect_refs(design, refs)
        checks["badRefs"] = len([ref for ref in refs if not ref.startswith("./assets/") or ".." in Path(ref).parts or ref.startswith("/")])
        checks["missingRefs"] = len([ref for ref in refs if ref.removeprefix("./") not in names])
    with zipfile.ZipFile(assets_zip) as archive:
        names = set(archive.namelist())
        checks["assetsHasManifest"] = "manifest.json" in names
        checks["assetsOriginalCount"] = len([name for name in names if name.startswith("originals/") and name.endswith(".png")])
        checks["assetsSlicePngCount"] = len([name for name in names if name.startswith("slices/") and name.endswith(".png")])
    checks["selectedPngCountMatches"] = checks["assetsSlicePngCount"] == selected_count
    checks["projectSliceCountMatches"] = checks["projectSlicePngCount"] == selected_count
    checks["originalCountMatches"] = checks["assetsOriginalCount"] == page_count and checks["projectOriginalCount"] == page_count
    return checks


def collect_refs(value: Any, refs: list[str]) -> None:
    if isinstance(value, dict):
        fill = value.get("fill")
        if isinstance(fill, dict) and fill.get("type") == "image":
            refs.append(fill["url"])
        for child in value.values():
            collect_refs(child, refs)
    elif isinstance(value, list):
        for item in value:
            collect_refs(item, refs)


def all_truthy(checks: dict[str, Any]) -> bool:
    for key, value in checks.items():
        if key in {"badRefs", "missingRefs"}:
            if value != 0:
                return False
        elif isinstance(value, bool):
            if not value:
                return False
        elif isinstance(value, int):
            if value < 1:
                return False
    return True


def write_reports(out_dir: Path, report: dict[str, Any]) -> None:
    (out_dir / "acceptance_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Pencil Handoff Acceptance Report",
        "",
        f"- ok: `{report.get('ok')}`",
        f"- projectId: `{report.get('projectId', '')}`",
        "",
        "## Checks",
        "",
    ]
    for key, value in (report.get("checks") or {}).items():
        lines.append(f"- {key}: `{value}`")
    if report.get("missingInputs"):
        lines.extend(["", "## Missing Inputs", ""])
        lines.extend(f"- {item}" for item in report["missingInputs"])
    (out_dir / "acceptance_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
