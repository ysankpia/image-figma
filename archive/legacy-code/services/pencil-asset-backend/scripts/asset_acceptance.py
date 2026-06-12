#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import requests


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class AcceptanceResult:
    name: str
    input_paths: list[str]
    status: str = "pending"
    missing_sample: bool = False
    project_id: str | None = None
    page_count: int = 0
    candidate_count: int = 0
    selected_slice_count: int = 0
    preview_asset_count: int = 0
    exported_asset_count: int = 0
    selected_png_count: int = 0
    selected_manifest_asset_count: int = 0
    reference_count: int = 0
    project_zip_exists: bool = False
    selected_assets_zip_exists: bool = False
    bad_refs: int = 0
    missing_refs: int = 0
    errors: list[str] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Acceptance test the Pencil asset handoff backend.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8110")
    parser.add_argument("--input", action="append", default=[], type=Path, help="Image file or directory. Repeatable.")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--project-name", default="Pencil Asset Acceptance")
    parser.add_argument("--max-files-per-project", type=int, default=6)
    parser.add_argument("--slices-per-page", type=int, default=3)
    parser.add_argument("--skip-ready", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    out_dir = args.out.expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if not args.input:
        print("at least one --input is required", file=sys.stderr)
        return 2

    health = get_json(f"{base_url}/api/health")
    if health.get("data", {}).get("status") != "ok":
        raise AssertionError(json.dumps(health, ensure_ascii=False, indent=2))
    print("health=ok")
    if not args.skip_ready:
        ready = get_json(f"{base_url}/api/ready")
        print(f"ready={ready.get('data', {}).get('status')}")

    results: list[AcceptanceResult] = []
    for index, raw_input in enumerate(args.input, start=1):
        images = discover_images(raw_input)
        sample_name = f"sample_{index:02d}_{safe_name(raw_input.stem or raw_input.name)}"
        sample_out = out_dir / sample_name
        sample_out.mkdir(parents=True, exist_ok=True)
        result = AcceptanceResult(name=sample_name, input_paths=[str(raw_input.expanduser())])
        if not images:
            result.status = "missingSample"
            result.missing_sample = True
            result.errors.append(f"no input images found: {raw_input.expanduser()}")
            results.append(result)
            continue
        try:
            run_sample(
                base_url=base_url,
                images=images[: args.max_files_per_project],
                out_dir=sample_out,
                project_name=f"{args.project_name} {index:02d}",
                slices_per_page=args.slices_per_page,
                result=result,
            )
            result.status = "passed"
        except Exception as error:
            result.status = "failed"
            result.errors.append(str(error))
        results.append(result)

    report = {
        "schema": "pencil_asset.acceptance.v1",
        "createdAt": datetime.now(UTC).isoformat(),
        "baseUrl": base_url,
        "outDir": str(out_dir),
        "sampleCount": len(results),
        "passed": sum(1 for item in results if item.status == "passed"),
        "failed": sum(1 for item in results if item.status == "failed"),
        "missingSample": sum(1 for item in results if item.missing_sample),
        "results": [result_to_dict(item) for item in results],
    }
    (out_dir / "acceptance_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "acceptance_report.md").write_text(render_markdown_report(report), encoding="utf-8")
    print(f"report={out_dir / 'acceptance_report.md'}")
    if report["failed"]:
        raise AssertionError(f"asset acceptance failed: {report['failed']} sample(s)")
    print("assetAcceptance=ok")
    return 0


def run_sample(
    *,
    base_url: str,
    images: list[Path],
    out_dir: Path,
    project_name: str,
    slices_per_page: int,
    result: AcceptanceResult,
) -> None:
    result.input_paths = [str(path) for path in images]
    created = create_project(base_url, images, project_name)
    project_id = str(created["projectId"])
    result.project_id = project_id
    result.page_count = int(created.get("pageCount") or 0)
    result.candidate_count = int(created.get("candidateCount") or 0)
    result.artifacts["reviewUrl"] = f"{base_url}{created.get('reviewUrl')}"
    if result.page_count < 1:
        raise AssertionError("pageCount must be >= 1")
    if result.candidate_count <= 0:
        raise AssertionError("candidateCount must be > 0")

    candidates = get_json(f"{base_url}/api/asset-projects/{project_id}/candidates")["data"]
    manual_slices = build_manual_slices(project_name=project_name, candidates=candidates, slices_per_page=slices_per_page)
    result.selected_slice_count = sum(
        1
        for page in manual_slices.get("pages") or []
        for item in page.get("slices") or []
        if item.get("selected") is not False
    )
    if result.selected_slice_count <= 0:
        raise AssertionError("selectedSliceCount must be > 0")
    saved = put_json(f"{base_url}/api/asset-projects/{project_id}/manual-slices", manual_slices)["data"]
    if int(saved.get("selectedSliceCount") or 0) != result.selected_slice_count:
        raise AssertionError("manualSliceSaved selected count mismatch")

    preview = post_json(f"{base_url}/api/asset-projects/{project_id}/export-preview")["data"]
    result.preview_asset_count = int(preview.get("assetCount") or 0)
    if result.preview_asset_count != result.selected_slice_count:
        raise AssertionError("export preview count does not match selected slices")
    contact_sheet = out_dir / "contact-sheet.png"
    download_binary(f"{base_url}/api/asset-projects/{project_id}/export-preview/contact-sheet.png", contact_sheet)
    result.artifacts["contactSheet"] = str(contact_sheet)

    manifest = post_json(f"{base_url}/api/asset-projects/{project_id}/export")["data"]
    result.exported_asset_count = int(manifest.get("selectedAssetCount") or 0)
    if result.exported_asset_count != result.selected_slice_count:
        raise AssertionError("exported asset count does not match selected slices")

    project_zip = out_dir / "project.zip"
    selected_zip = out_dir / "selected-assets.zip"
    download_zip(f"{base_url}/api/asset-projects/{project_id}/download.zip", project_zip)
    download_zip(f"{base_url}/api/asset-projects/{project_id}/selected-assets.zip", selected_zip)
    result.project_zip_exists = project_zip.exists()
    result.selected_assets_zip_exists = selected_zip.exists()
    result.artifacts["projectZip"] = str(project_zip)
    result.artifacts["selectedAssetsZip"] = str(selected_zip)

    unzipped = out_dir / "project-unzipped"
    if unzipped.exists():
        shutil.rmtree(unzipped)
    with ZipFile(project_zip) as archive:
        names = set(archive.namelist())
        required = {"design.pen", "manifest.json", "manual_slices.v1.json", "export-preview/contact-sheet.png"}
        missing = required - names
        if missing:
            raise AssertionError(f"project.zip missing: {sorted(missing)}")
        if "selected-assets.zip" in names:
            raise AssertionError("project.zip must not embed selected-assets.zip")
        archive.extractall(unzipped)
    ref_result = check_design_refs(unzipped)
    result.bad_refs = ref_result["badRefs"]
    result.missing_refs = ref_result["missingRefs"]
    result.reference_count = ref_result["referenceRefs"]
    if ref_result["visibleRefs"] != result.selected_slice_count:
        raise AssertionError(f"visible ref count {ref_result['visibleRefs']} != selected slices {result.selected_slice_count}")
    if result.reference_count != result.page_count:
        raise AssertionError(f"reference ref count {result.reference_count} != page count {result.page_count}")
    if result.bad_refs or result.missing_refs:
        raise AssertionError(f"badRefs={result.bad_refs} missingRefs={result.missing_refs}")

    with ZipFile(selected_zip) as archive:
        names = set(archive.namelist())
        result.selected_png_count = len([name for name in names if name.endswith(".png")])
        if any(name.endswith("source.png") for name in names):
            raise AssertionError("selected-assets.zip must not contain source reference images")
        selected_manifest = json.loads(archive.read("manifest.json"))
        result.selected_manifest_asset_count = int(selected_manifest.get("assetCount") or 0)
    if result.selected_png_count != result.selected_slice_count:
        raise AssertionError("selected-assets.zip PNG count does not match selected slices")
    if result.selected_manifest_asset_count != result.selected_slice_count:
        raise AssertionError("selected-assets.zip manifest count does not match selected slices")


def create_project(base_url: str, images: list[Path], project_name: str) -> dict[str, Any]:
    handles = []
    try:
        files = []
        for image in images:
            handle = image.open("rb")
            handles.append(handle)
            files.append(("files[]", (image.name, handle, content_type_for(image))))
        response = requests.post(
            f"{base_url}/api/asset-projects",
            data={"projectName": project_name},
            files=files,
            timeout=900,
        )
        return parse_response(response)["data"]
    finally:
        for handle in handles:
            handle.close()


def build_manual_slices(*, project_name: str, candidates: dict[str, Any], slices_per_page: int) -> dict[str, Any]:
    pages = []
    for page in candidates.get("pages") or []:
        selected = select_candidates(page.get("candidates") or [], slices_per_page)
        slices = []
        for index, candidate in enumerate(selected, start=1):
            kind = str(candidate.get("kind") or "image")
            if kind not in {"image", "icon"}:
                kind = "image"
            slices.append(
                {
                    "id": f"{page['pageId']}__slice_{index:04d}",
                    "name": f"slice_{index:04d}",
                    "displayName": f"Asset {index:04d}",
                    "kind": kind,
                    "bbox": candidate["bbox"],
                    "selected": True,
                    "exportMode": "rect",
                    "source": "candidate_confirmed",
                    "candidateIds": [str(candidate["id"])],
                    "tags": ["acceptance"],
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
    return {"schema": "pencil.manual_slices.v1", "projectName": project_name, "pages": pages}


def select_candidates(candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    usable = [
        candidate
        for candidate in candidates
        if str(candidate.get("kind") or "") in {"image", "icon"} and valid_bbox(candidate.get("bbox"))
    ]
    usable.sort(key=lambda item: ({"strong": 0, "normal": 1, "review": 2}.get(str(item.get("level")), 1), -float(item.get("confidence") or 0)))
    selected = usable[: max(1, min(limit, len(usable)))]
    if not selected:
        raise AssertionError("no usable image/icon candidates found")
    return selected


def check_design_refs(root: Path) -> dict[str, int]:
    design = json.loads((root / "design.pen").read_text(encoding="utf-8"))
    refs: list[str] = []
    for child in design.get("children") or []:
        collect_image_refs(child, refs)
    visible_refs = [ref for ref in refs if ref.startswith("./assets/visible/")]
    reference_refs = [ref for ref in refs if ref.startswith("./assets/reference/")]
    bad_refs = [
        ref
        for ref in refs
        if not (ref.startswith("./assets/visible/") or ref.startswith("./assets/reference/"))
        or ("source.png" in ref and not ref.startswith("./assets/reference/"))
        or "../" in ref
        or "debug/" in ref
        or "raw-crops" in ref
        or "masks/" in ref
        or Path(ref).is_absolute()
    ]
    missing_refs = [ref for ref in refs if not (root / ref.removeprefix("./")).exists()]
    return {
        "refs": len(refs),
        "visibleRefs": len(visible_refs),
        "referenceRefs": len(reference_refs),
        "badRefs": len(bad_refs),
        "missingRefs": len(missing_refs),
    }


def collect_image_refs(node: Any, refs: list[str]) -> None:
    if not isinstance(node, dict):
        return
    fill = node.get("fill")
    if isinstance(fill, dict) and fill.get("type") == "image" and isinstance(fill.get("url"), str):
        refs.append(fill["url"])
    for child in node.get("children") or []:
        collect_image_refs(child, refs)


def get_json(url: str) -> dict[str, Any]:
    return parse_response(requests.get(url, timeout=60))


def put_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    return parse_response(requests.put(url, json=payload, timeout=60))


def post_json(url: str) -> dict[str, Any]:
    return parse_response(requests.post(url, timeout=600))


def parse_response(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    if response.status_code >= 400:
        raise AssertionError(json.dumps(data, ensure_ascii=False, indent=2))
    return data


def download_zip(url: str, target: Path) -> None:
    download_binary(url, target)
    if target.read_bytes()[:2] != b"PK":
        raise AssertionError(f"downloaded file is not a ZIP: {target}")


def download_binary(url: str, target: Path) -> None:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    target.write_bytes(response.content)


def discover_images(raw: Path) -> list[Path]:
    path = raw.expanduser().resolve()
    if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
        return [path]
    if path.is_dir():
        return [child.resolve() for child in sorted(path.rglob("*")) if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS]
    return []


def valid_bbox(value: Any) -> bool:
    return isinstance(value, dict) and int(value.get("width") or 0) > 0 and int(value.get("height") or 0) > 0


def content_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def result_to_dict(result: AcceptanceResult) -> dict[str, Any]:
    return {
        "name": result.name,
        "inputPaths": result.input_paths,
        "status": result.status,
        "missingSample": result.missing_sample,
        "projectId": result.project_id,
        "pageCount": result.page_count,
        "candidateCount": result.candidate_count,
        "selectedSliceCount": result.selected_slice_count,
        "previewAssetCount": result.preview_asset_count,
        "exportedAssetCount": result.exported_asset_count,
        "selectedPngCount": result.selected_png_count,
        "selectedManifestAssetCount": result.selected_manifest_asset_count,
        "referenceCount": result.reference_count,
        "projectZipExists": result.project_zip_exists,
        "selectedAssetsZipExists": result.selected_assets_zip_exists,
        "badRefs": result.bad_refs,
        "missingRefs": result.missing_refs,
        "errors": result.errors,
        "artifacts": result.artifacts,
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Pencil Asset Acceptance Report",
        "",
        f"- createdAt: `{report['createdAt']}`",
        f"- baseUrl: `{report['baseUrl']}`",
        f"- passed: `{report['passed']}`",
        f"- failed: `{report['failed']}`",
        f"- missingSample: `{report['missingSample']}`",
        "",
        "| Sample | Status | Pages | Candidates | Selected | Reference | Preview | Exported | PNGs | badRefs | missingRefs |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in report["results"]:
        lines.append(
            "| {name} | {status} | {pageCount} | {candidateCount} | {selectedSliceCount} | "
            "{referenceCount} | {previewAssetCount} | {exportedAssetCount} | {selectedPngCount} | "
            "{badRefs} | {missingRefs} |".format(**item)
        )
    lines.append("")
    for item in report["results"]:
        if item["errors"]:
            lines.append(f"## {item['name']} Errors")
            lines.extend(f"- {error}" for error in item["errors"])
            lines.append("")
    return "\n".join(lines) + "\n"


def safe_name(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip())
    return cleaned.strip("_") or "input"


if __name__ == "__main__":
    raise SystemExit(main())
