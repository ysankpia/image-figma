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

from http_smoke import ALL_MODES, assert_ready, check_design_refs, content_type_for


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class SampleResult:
    name: str
    input_paths: list[str]
    status: str = "pending"
    missing_sample: bool = False
    project_id: str | None = None
    page_count: int = 0
    candidate_count: int = 0
    selected_slice_count: int = 0
    rejected_candidate_count: int = 0
    preview_asset_count: int = 0
    exported_asset_count: int = 0
    selected_png_count: int = 0
    selected_manifest_asset_count: int = 0
    project_zip_exists: bool = False
    selected_assets_zip_exists: bool = False
    bad_refs: int = 0
    missing_refs: int = 0
    errors: list[str] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Acceptance test the assisted slice workspace HTTP path.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8100")
    parser.add_argument("--input", action="append", default=[], type=Path, help="Image file or directory. Repeatable.")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--project-name", default="Slice Workspace Acceptance")
    parser.add_argument("--boundary-source", choices=("m29", "psdlike", "hybrid"), default="psdlike")
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
        assert_ready(base_url)

    results = []
    for index, raw_input in enumerate(args.input, start=1):
        images = discover_images(raw_input)
        sample_name = f"sample_{index:02d}_{safe_name(raw_input.stem or raw_input.name)}"
        sample_out = out_dir / sample_name
        sample_out.mkdir(parents=True, exist_ok=True)
        result = SampleResult(name=sample_name, input_paths=[str(raw_input.expanduser())])
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
                boundary_source=args.boundary_source,
                slices_per_page=args.slices_per_page,
                result=result,
            )
            result.status = "passed"
        except Exception as error:
            result.status = "failed"
            result.errors.append(str(error))
        results.append(result)

    report = {
        "schema": "pencil.slice_workspace_acceptance.v1",
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
        raise AssertionError(f"slice workspace acceptance failed: {report['failed']} sample(s)")
    print("sliceWorkspaceAcceptance=ok")
    return 0


def run_sample(
    *,
    base_url: str,
    images: list[Path],
    out_dir: Path,
    project_name: str,
    boundary_source: str,
    slices_per_page: int,
    result: SampleResult,
) -> None:
    result.input_paths = [str(path) for path in images]
    created = create_project(base_url, images, project_name, boundary_source)
    project_id = str(created["projectId"])
    result.project_id = project_id
    result.page_count = int(created.get("pageCount") or 0)
    result.artifacts["reviewUrl"] = f"{base_url}{created.get('reviewUrl')}"

    project = get_json(f"{base_url}/api/pencil/slice-projects/{project_id}")["data"]
    if int(project.get("pageCount") or 0) < 1:
        raise AssertionError("pageCount must be >= 1")

    candidates = get_json(f"{base_url}/api/pencil/slice-projects/{project_id}/candidates")["data"]
    candidate_pages = candidates.get("pages") or []
    result.candidate_count = sum(len(page.get("candidates") or []) for page in candidate_pages)
    if result.candidate_count <= 0:
        raise AssertionError("candidateCount must be > 0")

    manual_slices = build_manual_slices(project_name=project_name, candidates=candidates, slices_per_page=slices_per_page)
    result.selected_slice_count = sum(
        len([item for item in page.get("slices") or [] if item.get("selected") is not False])
        for page in manual_slices.get("pages") or []
    )
    if result.selected_slice_count <= 0:
        raise AssertionError("selectedSliceCount must be > 0")

    put_manual = put_json(f"{base_url}/api/pencil/slice-projects/{project_id}/manual-slices", manual_slices)["data"]
    if int(put_manual.get("selectedSliceCount") or 0) != result.selected_slice_count:
        raise AssertionError("manualSliceSaved selected count mismatch")

    review_state = get_json(f"{base_url}/api/pencil/slice-projects/{project_id}/review-state")["data"]
    rejected_id = first_unselected_candidate_id(candidates, manual_slices)
    if rejected_id:
        for page in review_state.get("pages") or []:
            valid_ids = {str(candidate["id"]) for candidate in candidate_page_by_id(candidates, str(page.get("pageId"))).get("candidates") or []}
            if rejected_id in valid_ids:
                page["rejectedCandidateIds"] = sorted(set([*(page.get("rejectedCandidateIds") or []), rejected_id]))
                break
    put_review = put_json(f"{base_url}/api/pencil/slice-projects/{project_id}/review-state", review_state)["data"]
    result.rejected_candidate_count = int(put_review.get("rejectedCandidateCount") or 0)
    refreshed_review = get_json(f"{base_url}/api/pencil/slice-projects/{project_id}/review-state")["data"]
    refreshed_rejected = {
        rejected
        for page in refreshed_review.get("pages") or []
        for rejected in page.get("rejectedCandidateIds") or []
    }
    if rejected_id and rejected_id not in refreshed_rejected:
        raise AssertionError("reviewStateSaved rejected candidate was not persisted")
    if rejected_id and rejected_id in selected_candidate_ids(manual_slices):
        raise AssertionError("rejected candidate must not be selected")

    preview = post_json(f"{base_url}/api/pencil/slice-projects/{project_id}/export-preview", {})["data"]
    result.preview_asset_count = int(preview.get("assetCount") or 0)
    if result.preview_asset_count != result.selected_slice_count:
        raise AssertionError("export preview asset count does not match selected slices")
    preview_png = requests.get(f"{base_url}/api/pencil/slice-projects/{project_id}/export-preview/contact-sheet.png", timeout=60)
    preview_png.raise_for_status()
    (out_dir / "contact-sheet.png").write_bytes(preview_png.content)
    result.artifacts["contactSheet"] = str(out_dir / "contact-sheet.png")

    manifest = post_json(f"{base_url}/api/pencil/slice-projects/{project_id}/export", {})["data"]
    result.exported_asset_count = int(manifest.get("selectedAssetCount") or 0)
    if result.exported_asset_count != result.selected_slice_count:
        raise AssertionError("exported asset count does not match selected slices")

    project_zip = out_dir / "project.zip"
    selected_zip = out_dir / "selected-assets.zip"
    download_file(f"{base_url}/api/pencil/slice-projects/{project_id}/download.zip", project_zip)
    download_file(f"{base_url}/api/pencil/slice-projects/{project_id}/selected-assets.zip", selected_zip)
    result.project_zip_exists = project_zip.exists()
    result.selected_assets_zip_exists = selected_zip.exists()
    result.artifacts["projectZip"] = str(project_zip)
    result.artifacts["selectedAssetsZip"] = str(selected_zip)

    unzipped = out_dir / "project-unzipped"
    if unzipped.exists():
        shutil.rmtree(unzipped)
    with ZipFile(project_zip) as archive:
        names = set(archive.namelist())
        if "selected-assets.zip" not in names:
            raise AssertionError("project.zip missing selected-assets.zip")
        if "resource-kit/contact-sheet.png" not in names:
            raise AssertionError("project.zip missing resource-kit/contact-sheet.png")
        archive.extractall(unzipped)
    for mode in ALL_MODES:
        refs, bad_refs, missing_refs = check_design_refs(unzipped, mode)
        result.bad_refs += bad_refs
        result.missing_refs += missing_refs
        if refs != result.selected_slice_count:
            raise AssertionError(f"{mode} ref count {refs} != selected slices {result.selected_slice_count}")
    if result.bad_refs or result.missing_refs:
        raise AssertionError(f"badRefs={result.bad_refs} missingRefs={result.missing_refs}")

    with ZipFile(selected_zip) as archive:
        names = set(archive.namelist())
        result.selected_png_count = len([name for name in names if name.endswith(".png")])
        selected_manifest = json.loads(archive.read("manifest.json"))
        result.selected_manifest_asset_count = int(selected_manifest.get("assetCount") or 0)
    if result.selected_png_count != result.selected_slice_count:
        raise AssertionError("selected-assets.zip PNG count does not match selected slices")
    if result.selected_manifest_asset_count != result.selected_slice_count:
        raise AssertionError("selected-assets.zip manifest count does not match selected slices")
    if result.selected_manifest_asset_count != result.exported_asset_count:
        raise AssertionError("selected manifest count does not match export manifest count")


def create_project(base_url: str, images: list[Path], project_name: str, boundary_source: str) -> dict[str, Any]:
    files = []
    handles = []
    try:
        for image in images:
            handle = image.open("rb")
            handles.append(handle)
            files.append(("files[]", (image.name, handle, content_type_for(image))))
        response = requests.post(
            f"{base_url}/api/pencil/slice-projects",
            data={"projectName": project_name, "boundarySource": boundary_source, "includeDebug": "true"},
            files=files,
            timeout=300,
        )
        response.raise_for_status()
        return response.json()["data"]
    finally:
        for handle in handles:
            handle.close()


def build_manual_slices(*, project_name: str, candidates: dict[str, Any], slices_per_page: int) -> dict[str, Any]:
    pages = []
    for page in candidates.get("pages") or []:
        selected = select_candidates(page.get("candidates") or [], slices_per_page)
        slices = []
        for index, candidate in enumerate(selected, start=1):
            candidate_id = str(candidate["id"])
            slices.append(
                {
                    "id": f"{page['pageId']}__slice_{index:04d}",
                    "name": f"slice_{index:04d}",
                    "displayName": f"Acceptance Slice {index:04d}",
                    "kind": str(candidate.get("kind") or "image"),
                    "tags": ["acceptance"],
                    "reviewState": "confirmed",
                    "bbox": candidate["bbox"],
                    "selected": True,
                    "exportMode": "rect",
                    "source": "candidate_confirmed",
                    "candidateIds": [candidate_id],
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
    usable = [candidate for candidate in candidates if valid_bbox(candidate.get("bbox"))]
    preferred = [
        candidate
        for candidate in usable
        if str(candidate.get("kind") or "") not in {"full_screen"}
        and str(candidate.get("reason") or "") != "source_image"
    ]
    pool = preferred or usable
    selection_limit = max(1, min(limit, len(pool) - 1)) if len(pool) > 1 else 1
    selected = pool[:selection_limit]
    if not selected:
        raise AssertionError("no usable candidates found")
    return selected


def valid_bbox(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return int(value.get("width") or 0) > 0 and int(value.get("height") or 0) > 0


def first_unselected_candidate_id(candidates: dict[str, Any], manual_slices: dict[str, Any]) -> str | None:
    selected = selected_candidate_ids(manual_slices)
    for page in candidates.get("pages") or []:
        for candidate in page.get("candidates") or []:
            candidate_id = str(candidate.get("id") or "")
            if candidate_id and candidate_id not in selected:
                return candidate_id
    return None


def selected_candidate_ids(manual_slices: dict[str, Any]) -> set[str]:
    return {
        str(candidate_id)
        for page in manual_slices.get("pages") or []
        for item in page.get("slices") or []
        for candidate_id in item.get("candidateIds") or []
    }


def first_candidate_id(candidates: dict[str, Any]) -> str | None:
    for page in candidates.get("pages") or []:
        for candidate in page.get("candidates") or []:
            candidate_id = str(candidate.get("id") or "")
            if candidate_id:
                return candidate_id
    return None


def candidate_page_by_id(candidates: dict[str, Any], page_id: str) -> dict[str, Any]:
    for page in candidates.get("pages") or []:
        if str(page.get("pageId")) == page_id:
            return page
    return {}


def get_json(url: str) -> dict[str, Any]:
    response = requests.get(url, timeout=60)
    return parse_response(response)


def put_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.put(url, json=payload, timeout=60)
    return parse_response(response)


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(url, json=payload, timeout=300)
    return parse_response(response)


def parse_response(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    if response.status_code >= 400:
        raise AssertionError(json.dumps(data, ensure_ascii=False, indent=2))
    return data


def download_file(url: str, target: Path) -> None:
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    target.write_bytes(response.content)
    if target.read_bytes()[:2] != b"PK":
        raise AssertionError(f"downloaded file is not a ZIP: {target}")


def discover_images(raw: Path) -> list[Path]:
    path = raw.expanduser().resolve()
    if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
        return [path]
    if path.is_dir():
        return [child.resolve() for child in sorted(path.rglob("*")) if child.is_file() and child.suffix.lower() in IMAGE_EXTENSIONS]
    return []


def result_to_dict(result: SampleResult) -> dict[str, Any]:
    return {
        "name": result.name,
        "inputPaths": result.input_paths,
        "status": result.status,
        "missingSample": result.missing_sample,
        "projectId": result.project_id,
        "pageCount": result.page_count,
        "candidateCount": result.candidate_count,
        "selectedSliceCount": result.selected_slice_count,
        "rejectedCandidateCount": result.rejected_candidate_count,
        "previewAssetCount": result.preview_asset_count,
        "exportedAssetCount": result.exported_asset_count,
        "selectedPngCount": result.selected_png_count,
        "selectedManifestAssetCount": result.selected_manifest_asset_count,
        "projectZipExists": result.project_zip_exists,
        "selectedAssetsZipExists": result.selected_assets_zip_exists,
        "badRefs": result.bad_refs,
        "missingRefs": result.missing_refs,
        "errors": result.errors,
        "artifacts": result.artifacts,
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Slice Workspace Acceptance Report",
        "",
        f"- createdAt: `{report['createdAt']}`",
        f"- baseUrl: `{report['baseUrl']}`",
        f"- passed: `{report['passed']}`",
        f"- failed: `{report['failed']}`",
        f"- missingSample: `{report['missingSample']}`",
        "",
        "| Sample | Status | Pages | Candidates | Selected | Rejected | Preview | Exported | PNGs | badRefs | missingRefs |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in report["results"]:
        lines.append(
            "| {name} | {status} | {pageCount} | {candidateCount} | {selectedSliceCount} | "
            "{rejectedCandidateCount} | {previewAssetCount} | {exportedAssetCount} | "
            "{selectedPngCount} | {badRefs} | {missingRefs} |".format(**item)
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
