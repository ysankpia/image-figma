from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw

from .jsonio import read_json, write_json
from .project_builder import build_boundary_artifact, validate_project_pen_contract
from .storage import TaskStorage
from .types import ExportRequest, PageInput
from .utils import safe_slug


SLICE_CANDIDATES_SCHEMA = "pencil.slice_candidates.v1"
MANUAL_SLICES_SCHEMA = "pencil.manual_slices.v1"
REVIEW_STATE_SCHEMA = "pencil.slice_review_state.v1"


@dataclass(frozen=True)
class SliceProjectPaths:
    project_id: str
    root: Path
    uploads: Path
    pages: Path
    output: Path
    project_json: Path
    candidates_json: Path
    manual_slices_json: Path
    review_state_json: Path


class SliceProjectStorage:
    def __init__(self, task_storage: TaskStorage) -> None:
        self.root = task_storage.root / "slice-projects"
        self.root.mkdir(parents=True, exist_ok=True)

    def create_project(self, project_name: str) -> SliceProjectPaths:
        project_id = f"slice_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}"
        paths = self.paths(project_id)
        paths.uploads.mkdir(parents=True, exist_ok=True)
        paths.pages.mkdir(parents=True, exist_ok=True)
        paths.output.mkdir(parents=True, exist_ok=True)
        write_json(
            paths.project_json,
            {
                "projectId": paths.project_id,
                "status": "created",
                "projectName": project_name,
                "createdAt": datetime.now(UTC).isoformat(),
                "updatedAt": datetime.now(UTC).isoformat(),
                "warnings": [],
            },
        )
        return paths

    def paths(self, project_id: str) -> SliceProjectPaths:
        safe_id = safe_slug(project_id, "slice_project")
        root = self.root / safe_id
        return SliceProjectPaths(
            project_id=safe_id,
            root=root,
            uploads=root / "uploads",
            pages=root / "pages",
            output=root / "output",
            project_json=root / "project.json",
            candidates_json=root / "candidates.v1.json",
            manual_slices_json=root / "manual_slices.v1.json",
            review_state_json=root / "review_state.v1.json",
        )

    def read_project(self, project_id: str) -> dict[str, Any]:
        paths = self.paths(project_id)
        if not paths.project_json.exists():
            raise FileNotFoundError(project_id)
        return read_json(paths.project_json)

    def patch_project(self, paths: SliceProjectPaths, **updates: Any) -> dict[str, Any]:
        current = read_json(paths.project_json) if paths.project_json.exists() else {"projectId": paths.project_id}
        next_project = {**current, **updates, "updatedAt": datetime.now(UTC).isoformat()}
        write_json(paths.project_json, next_project)
        return next_project

    def list_projects(self) -> list[dict[str, Any]]:
        projects: list[dict[str, Any]] = []
        for root in sorted(self.root.iterdir() if self.root.exists() else [], reverse=True):
            if not root.is_dir():
                continue
            paths = self.paths(root.name)
            if not paths.project_json.exists():
                projects.append(broken_project_summary(paths, "missing project.json"))
                continue
            try:
                projects.append(project_summary(paths))
            except Exception as error:
                projects.append(broken_project_summary(paths, str(error)))
        projects.sort(key=lambda item: str(item.get("updatedAt") or ""), reverse=True)
        return projects

    def rename_project(self, project_id: str, project_name: str) -> dict[str, Any]:
        paths = self.paths(project_id)
        if not paths.project_json.exists():
            raise FileNotFoundError(project_id)
        project = self.patch_project(paths, projectName=project_name)
        if paths.manual_slices_json.exists():
            manual_slices = read_json(paths.manual_slices_json)
            manual_slices["projectName"] = project_name
            write_json(paths.manual_slices_json, manual_slices)
        return project

    def clone_project(self, project_id: str) -> SliceProjectPaths:
        source_paths = self.paths(project_id)
        if not source_paths.project_json.exists():
            raise FileNotFoundError(project_id)
        source_project = read_json(source_paths.project_json)
        clone_name = f"{source_project.get('projectName') or 'Assisted Slice Project'} Copy"
        clone_paths = self.create_project(clone_name)
        if clone_paths.root.exists():
            shutil.rmtree(clone_paths.root)
        shutil.copytree(source_paths.root, clone_paths.root)
        if clone_paths.output.exists():
            shutil.rmtree(clone_paths.output)
        clone_paths.output.mkdir(parents=True, exist_ok=True)
        now = datetime.now(UTC).isoformat()
        project = read_json(clone_paths.project_json)
        project.update(
            {
                "projectId": clone_paths.project_id,
                "projectName": clone_name,
                "status": "ready",
                "createdAt": now,
                "updatedAt": now,
                "reviewUrl": f"/api/pencil/slice-projects/{clone_paths.project_id}/review",
                "downloadUrl": None,
                "selectedAssetsDownloadUrl": None,
                "zipPath": None,
                "selectedAssetsZipPath": None,
                "manifestPath": None,
                "exportPreviewPath": None,
                "candidatesPath": str(clone_paths.candidates_json),
                "manualSlicesPath": str(clone_paths.manual_slices_json),
                "reviewStatePath": str(clone_paths.review_state_json),
                "selectedAssetCount": None,
            }
        )
        write_json(clone_paths.project_json, {key: value for key, value in project.items() if value is not None})
        if clone_paths.candidates_json.exists():
            candidates = read_json(clone_paths.candidates_json)
            candidates["projectId"] = clone_paths.project_id
            write_json(clone_paths.candidates_json, candidates)
        if clone_paths.review_state_json.exists():
            review_state = read_json(clone_paths.review_state_json)
            review_state["projectId"] = clone_paths.project_id
            write_json(clone_paths.review_state_json, review_state)
        if clone_paths.manual_slices_json.exists():
            manual_slices = read_json(clone_paths.manual_slices_json)
            manual_slices["projectName"] = clone_name
            write_json(clone_paths.manual_slices_json, manual_slices)
        return clone_paths

    def delete_project(self, project_id: str) -> None:
        paths = self.paths(project_id)
        if not paths.project_json.exists():
            raise FileNotFoundError(project_id)
        shutil.rmtree(paths.root)


def initialize_slice_project(
    *,
    paths: SliceProjectPaths,
    inputs: list[PageInput],
    project_name: str,
    boundary_source: str,
    include_debug: bool,
    ocr_provider: str | None,
    settings: Any,
) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    for index, page_input in enumerate(inputs, start=1):
        page_id = f"page_{index:04d}"
        page_dir = paths.pages / page_id
        page_dir.mkdir(parents=True, exist_ok=True)
        source_path = page_dir / "source.png"
        with Image.open(page_input.path) as image:
            source = image.convert("RGBA")
            source.save(source_path)
            width, height = source.size
        pages.append(
            {
                "pageId": page_id,
                "originalName": page_input.original_name,
                "sourceImage": f"pages/{page_id}/source.png",
                "width": width,
                "height": height,
            }
        )

    evidence_request = ExportRequest(
        inputs=inputs,
        out_dir=paths.output,
        project_name=project_name,
        mode="visual-fidelity",
        columns="auto",
        include_debug=include_debug,
        ocr_provider=ocr_provider,
        boundary_source=boundary_source,  # type: ignore[arg-type]
    )
    for page, page_input in zip(pages, inputs, strict=True):
        artifact_dir = build_boundary_artifact(
            page_input=page_input,
            page_work=paths.root / "work" / str(page["pageId"]),
            request=evidence_request,
            settings=settings,
        )
        page["artifactDir"] = str(artifact_dir)
        if include_debug:
            debug_dir = paths.root / "debug" / "pages" / str(page["pageId"])
            debug_dir.mkdir(parents=True, exist_ok=True)
            copy_slice_debug(artifact_dir, debug_dir)

    candidates = build_slice_candidates(project_id=paths.project_id, pages=pages)
    public_pages = [{key: value for key, value in page.items() if key != "artifactDir"} for page in pages]
    write_json(paths.candidates_json, candidates)
    write_json(paths.manual_slices_json, default_manual_slices(project_name=project_name, pages=public_pages))
    write_json(paths.review_state_json, default_review_state(project_id=paths.project_id, candidates=candidates))
    return {
        "projectId": paths.project_id,
        "projectName": project_name,
        "pageCount": len(public_pages),
        "pages": public_pages,
    }


def build_slice_candidates(*, project_id: str, pages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": SLICE_CANDIDATES_SCHEMA,
        "projectId": project_id,
        "pages": [
            {
                "pageId": page["pageId"],
                "sourceImage": page["sourceImage"],
                "width": page["width"],
                "height": page["height"],
                "candidates": default_page_candidates(page),
            }
            for page in pages
        ],
    }


def default_review_state(*, project_id: str, candidates: dict[str, Any]) -> dict[str, Any]:
    pages = []
    for page in candidates.get("pages") or []:
        pages.append(
            {
                "pageId": page["pageId"],
                "rejectedCandidateIds": [],
                "hiddenCandidateIds": [],
                "lastFilter": {},
            }
        )
    return {
        "schema": REVIEW_STATE_SCHEMA,
        "projectId": project_id,
        "lastActivePageId": pages[0]["pageId"] if pages else "",
        "filters": {},
        "pages": pages,
        "updatedAt": datetime.now(UTC).isoformat(),
    }


def validate_review_state(value: dict[str, Any], candidates: dict[str, Any]) -> dict[str, Any]:
    if value.get("schema") != REVIEW_STATE_SCHEMA:
        raise ValueError(f"review state schema must be {REVIEW_STATE_SCHEMA}")
    candidate_pages = {str(page["pageId"]): page for page in candidates.get("pages") or []}
    candidate_ids_by_page = {
        page_id: {str(candidate["id"]) for candidate in page.get("candidates") or []}
        for page_id, page in candidate_pages.items()
    }
    pages_value = value.get("pages")
    if not isinstance(pages_value, list):
        raise ValueError("review state pages must be a list")
    pages: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in pages_value:
        page_id = str(page.get("pageId") or "")
        if page_id not in candidate_pages:
            raise ValueError(f"unknown pageId: {page_id}")
        if page_id in seen:
            raise ValueError(f"duplicate pageId: {page_id}")
        seen.add(page_id)
        valid_ids = candidate_ids_by_page[page_id]
        rejected = [str(item) for item in page.get("rejectedCandidateIds") or [] if str(item) in valid_ids]
        hidden = [str(item) for item in page.get("hiddenCandidateIds") or [] if str(item) in valid_ids]
        last_filter = page.get("lastFilter") if isinstance(page.get("lastFilter"), dict) else {}
        pages.append(
            {
                "pageId": page_id,
                "rejectedCandidateIds": sorted(set(rejected)),
                "hiddenCandidateIds": sorted(set(hidden)),
                "lastFilter": last_filter,
            }
        )
    for page_id in sorted(set(candidate_pages) - seen):
        pages.append({"pageId": page_id, "rejectedCandidateIds": [], "hiddenCandidateIds": [], "lastFilter": {}})
    last_active = str(value.get("lastActivePageId") or "")
    if last_active not in candidate_pages and candidate_pages:
        last_active = next(iter(candidate_pages))
    filters = value.get("filters") if isinstance(value.get("filters"), dict) else {}
    return {
        "schema": REVIEW_STATE_SCHEMA,
        "projectId": str(value.get("projectId") or candidates.get("projectId") or ""),
        "lastActivePageId": last_active,
        "filters": filters,
        "pages": pages,
        "updatedAt": datetime.now(UTC).isoformat(),
    }


def ensure_review_state(paths: SliceProjectPaths) -> dict[str, Any]:
    if not paths.candidates_json.exists():
        raise FileNotFoundError("candidates not found")
    candidates = read_json(paths.candidates_json)
    if paths.review_state_json.exists():
        try:
            review_state = validate_review_state(read_json(paths.review_state_json), candidates)
            write_json(paths.review_state_json, review_state)
            return review_state
        except ValueError:
            pass
    review_state = default_review_state(project_id=paths.project_id, candidates=candidates)
    write_json(paths.review_state_json, review_state)
    return review_state


def project_summary(paths: SliceProjectPaths) -> dict[str, Any]:
    project = read_json(paths.project_json)
    candidates = read_json(paths.candidates_json) if paths.candidates_json.exists() else {"pages": []}
    manual_slices = read_json(paths.manual_slices_json) if paths.manual_slices_json.exists() else {"pages": []}
    review_state = ensure_review_state(paths) if paths.candidates_json.exists() else {"pages": []}
    rejected_by_page = {
        str(page.get("pageId")): len(page.get("rejectedCandidateIds") or [])
        for page in review_state.get("pages") or []
    }
    selected_by_page = {
        str(page.get("pageId")): sum(1 for item in page.get("slices") or [] if item.get("selected") is not False)
        for page in manual_slices.get("pages") or []
    }
    pages = []
    for page in candidates.get("pages") or project.get("pages") or []:
        page_id = str(page["pageId"])
        selected_count = selected_by_page.get(page_id, 0)
        candidate_count = len(page.get("candidates") or [])
        pages.append(
            {
                "pageId": page_id,
                "sourceImage": page.get("sourceImage") or f"pages/{page_id}/source.png",
                "width": int(page.get("width") or 0),
                "height": int(page.get("height") or 0),
                "candidateCount": candidate_count,
                "selectedSliceCount": selected_count,
                "rejectedCandidateCount": rejected_by_page.get(page_id, 0),
                "status": "ready" if selected_count > 0 else "untouched",
                "thumbnailUrl": f"/api/pencil/slice-projects/{paths.project_id}/source/{page_id}",
            }
        )
    selected_count_total = sum(page["selectedSliceCount"] for page in pages)
    candidate_count_total = sum(page["candidateCount"] for page in pages)
    rejected_count_total = sum(page["rejectedCandidateCount"] for page in pages)
    completed_pages = sum(1 for page in pages if page["selectedSliceCount"] > 0)
    exported = (paths.output / "project.zip").exists() and (paths.output / "selected-assets.zip").exists()
    return {
        "projectId": paths.project_id,
        "status": project.get("status") or "unknown",
        "projectName": project.get("projectName") or "Assisted Slice Project",
        "pageCount": len(pages),
        "candidateCount": candidate_count_total,
        "selectedSliceCount": selected_count_total,
        "selectedAssetCount": project.get("selectedAssetCount", selected_count_total),
        "rejectedCandidateCount": rejected_count_total,
        "completedPageCount": completed_pages,
        "exported": exported,
        "manualSlicesConfirmed": project.get("manualSlicesConfirmed") is True,
        "reviewUrl": f"/api/pencil/slice-projects/{paths.project_id}/review",
        "workspaceUrl": "/api/pencil/slice-projects/workspace",
        "downloadUrl": f"/api/pencil/slice-projects/{paths.project_id}/download.zip" if exported else project.get("downloadUrl"),
        "selectedAssetsDownloadUrl": f"/api/pencil/slice-projects/{paths.project_id}/selected-assets.zip" if exported else None,
        "thumbnailUrl": pages[0]["thumbnailUrl"] if pages else None,
        "pages": pages,
        "createdAt": project.get("createdAt"),
        "updatedAt": project.get("updatedAt"),
        "error": project.get("error"),
        "warnings": project.get("warnings") or [],
    }


def broken_project_summary(paths: SliceProjectPaths, error: str) -> dict[str, Any]:
    return {
        "projectId": paths.project_id,
        "status": "broken",
        "projectName": paths.project_id,
        "pageCount": 0,
        "candidateCount": 0,
        "selectedSliceCount": 0,
        "selectedAssetCount": 0,
        "rejectedCandidateCount": 0,
        "completedPageCount": 0,
        "exported": False,
        "reviewUrl": None,
        "thumbnailUrl": None,
        "pages": [],
        "updatedAt": None,
        "error": error,
        "warnings": [error],
    }


def default_page_candidates(page: dict[str, Any]) -> list[dict[str, Any]]:
    width = int(page["width"])
    height = int(page["height"])
    candidates = evidence_candidates(page)
    if candidates:
        return candidates

    boxes = [
        ("full_screen", {"x": 0, "y": 0, "width": width, "height": height}, 0.15, "source_image"),
        (
            "upper_region",
            {"x": 0, "y": 0, "width": width, "height": max(1, round(height * 0.33))},
            0.25,
            "layout_region",
        ),
        (
            "middle_region",
            {"x": 0, "y": round(height * 0.33), "width": width, "height": max(1, round(height * 0.34))},
            0.25,
            "layout_region",
        ),
        (
            "lower_region",
            {"x": 0, "y": round(height * 0.67), "width": width, "height": max(1, height - round(height * 0.67))},
            0.25,
            "layout_region",
        ),
    ]
    candidates = []
    for index, (kind, bbox, confidence, reason) in enumerate(boxes, start=1):
        candidates.append(
            {
                "id": f"{page['pageId']}__candidate_{index:04d}",
                "kind": kind,
                "bbox": clamp_bbox(bbox, width, height),
                "source": "source",
                "confidence": confidence,
                "reason": reason,
                "selectedDefault": False,
            }
        )
    return candidates


def evidence_candidates(page: dict[str, Any]) -> list[dict[str, Any]]:
    artifact_raw = page.get("artifactDir")
    if not isinstance(artifact_raw, str):
        return []
    artifact_dir = Path(artifact_raw)
    width = int(page["width"])
    height = int(page["height"])
    candidates: list[dict[str, Any]] = []
    seen: list[dict[str, int]] = []

    evidence_path = artifact_dir / "m29_physical_evidence.v1.json"
    if evidence_path.exists():
        evidence = read_json(evidence_path)
        for primitive in evidence.get("primitives") or []:
            bbox = clamp_bbox(normalize_bbox(primitive.get("bbox") or {}), width, height)
            if bbox["width"] < 6 or bbox["height"] < 6:
                continue
            kind = candidate_kind(str(primitive.get("primitiveType") or primitive.get("role") or "unknown"))
            reason = "foreground_object_release" if (primitive.get("compileHints") or {}).get("foregroundObjectRelease") else "primitive_candidate"
            add_candidate(
                candidates=candidates,
                seen=seen,
                page_id=str(page["pageId"]),
                kind=kind,
                bbox=bbox,
                source="m29",
                confidence=0.65,
                reason=reason,
                source_ids=[str(primitive.get("id") or "")],
            )

    replay_path = artifact_dir / "m29-pencil-replay.v1.json"
    if replay_path.exists():
        replay = read_json(replay_path)
        for layer in replay.get("layers") or []:
            role = str(layer.get("role") or "")
            if role not in {"image_region", "symbol_region", "text_region"}:
                continue
            bbox = clamp_bbox(normalize_bbox(layer.get("bbox") or {}), width, height)
            add_candidate(
                candidates=candidates,
                seen=seen,
                page_id=str(page["pageId"]),
                kind=candidate_kind(role),
                bbox=bbox,
                source="psdlike",
                confidence=0.72,
                reason=str(layer.get("reason") or "replay_layer_candidate"),
                source_ids=[str(layer.get("id") or "")],
            )

    audit_path = artifact_dir / "container_foreground_audit.v1.json"
    if audit_path.exists():
        audit = read_json(audit_path)
        for block in audit.get("missingOcrBlocks") or []:
            add_candidate(
                candidates=candidates,
                seen=seen,
                page_id=str(page["pageId"]),
                kind="text",
                bbox=clamp_bbox(normalize_bbox(block.get("bbox") or {}), width, height),
                source="foreground_audit",
                confidence=0.78,
                reason="missing_ocr_foreground",
                source_ids=[str(block.get("id") or "")],
            )
        for conflict in audit.get("conflicts") or []:
            for group in conflict.get("repeatedLocalGroups") or []:
                add_candidate(
                    candidates=candidates,
                    seen=seen,
                    page_id=str(page["pageId"]),
                    kind="group",
                    bbox=clamp_bbox(normalize_bbox(group.get("bbox") or {}), width, height),
                    source="foreground_audit",
                    confidence=0.82,
                    reason="repeated_local_foreground_group",
                    source_ids=[str(member.get("ocrId") or "") for member in group.get("members") or []],
                )
    return candidates


def add_candidate(
    *,
    candidates: list[dict[str, Any]],
    seen: list[dict[str, int]],
    page_id: str,
    kind: str,
    bbox: dict[str, int],
    source: str,
    confidence: float,
    reason: str,
    source_ids: list[str],
) -> None:
    if bbox["width"] <= 0 or bbox["height"] <= 0:
        return
    if any(bbox_iou(bbox, item) >= 0.92 for item in seen):
        return
    seen.append(bbox)
    candidates.append(
        {
            "id": f"{page_id}__candidate_{len(candidates) + 1:04d}",
            "kind": kind,
            "bbox": bbox,
            "source": source,
            "confidence": round(confidence, 4),
            "reason": reason,
            "selectedDefault": False,
            "sourceIds": [item for item in source_ids if item],
        }
    )


def candidate_kind(raw: str) -> str:
    if "text" in raw:
        return "text"
    if "symbol" in raw or "icon" in raw:
        return "icon"
    if "image" in raw or "raster" in raw:
        return "image"
    if "surface" in raw or "shape" in raw or "rect" in raw:
        return "shape"
    return "unknown"


def default_manual_slices(*, project_name: str, pages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": MANUAL_SLICES_SCHEMA,
        "projectName": project_name,
        "pages": [
            {
                "pageId": page["pageId"],
                "sourceImage": page["sourceImage"],
                "width": page["width"],
                "height": page["height"],
                "slices": [],
            }
            for page in pages
        ],
    }


def validate_manual_slices(value: dict[str, Any], candidates: dict[str, Any]) -> dict[str, Any]:
    if value.get("schema") != MANUAL_SLICES_SCHEMA:
        raise ValueError(f"manual slices schema must be {MANUAL_SLICES_SCHEMA}")
    candidate_pages = {page["pageId"]: page for page in candidates.get("pages") or []}
    pages_value = value.get("pages")
    if not isinstance(pages_value, list):
        raise ValueError("manual slices pages must be a list")
    normalized_pages: list[dict[str, Any]] = []
    seen_pages: set[str] = set()
    seen_ids: set[str] = set()
    for page in pages_value:
        page_id = str(page.get("pageId") or "")
        candidate_page = candidate_pages.get(page_id)
        if candidate_page is None:
            raise ValueError(f"unknown pageId: {page_id}")
        if page_id in seen_pages:
            raise ValueError(f"duplicate pageId: {page_id}")
        seen_pages.add(page_id)
        width = int(candidate_page["width"])
        height = int(candidate_page["height"])
        slices_value = page.get("slices")
        if not isinstance(slices_value, list):
            raise ValueError(f"page {page_id} slices must be a list")
        normalized_slices: list[dict[str, Any]] = []
        for item in slices_value:
            slice_id = str(item.get("id") or "")
            if not slice_id:
                raise ValueError("slice id is required")
            if slice_id in seen_ids:
                raise ValueError(f"duplicate slice id: {slice_id}")
            seen_ids.add(slice_id)
            export_mode = str(item.get("exportMode") or "rect")
            if export_mode != "rect":
                raise ValueError(f"unsupported exportMode: {export_mode}")
            bbox = normalize_bbox(item.get("bbox") or {})
            if bbox["width"] <= 0 or bbox["height"] <= 0:
                raise ValueError(f"slice {slice_id} has invalid bbox")
            if bbox["x"] < 0 or bbox["y"] < 0 or bbox["x"] + bbox["width"] > width or bbox["y"] + bbox["height"] > height:
                raise ValueError(f"slice {slice_id} bbox is out of bounds")
            item["bbox"] = bbox
            item["name"] = safe_slug(str(item.get("name") or slice_id), slice_id)
            item["displayName"] = str(item.get("displayName") or item["name"])
            item["kind"] = str(item.get("kind") or "image")
            item["selected"] = item.get("selected") is not False
            item["exportMode"] = export_mode
            item["reviewState"] = str(item.get("reviewState") or "confirmed")
            if not isinstance(item.get("tags"), list):
                item["tags"] = []
            item["tags"] = [safe_slug(str(tag), "tag") for tag in item.get("tags") or [] if str(tag).strip()]
            if not isinstance(item.get("candidateIds"), list):
                item["candidateIds"] = []
            normalized_slices.append(item)
        normalized_pages.append(
            {
                "pageId": page_id,
                "sourceImage": candidate_page["sourceImage"],
                "width": width,
                "height": height,
                "slices": normalized_slices,
            }
        )
    missing_pages = sorted(set(candidate_pages) - seen_pages)
    if missing_pages:
        raise ValueError(f"manual slices missing pageId: {missing_pages[0]}")
    value["projectName"] = str(value.get("projectName") or "Assisted Slice Project")
    value["pages"] = normalized_pages
    return value


def selected_slice_count(manual_slices: dict[str, Any]) -> int:
    return sum(
        1
        for page in manual_slices.get("pages") or []
        for item in page.get("slices") or []
        if item.get("selected") is not False
    )


def export_manual_slice_project(
    *,
    paths: SliceProjectPaths,
    manual_slices: dict[str, Any],
    include_debug: bool,
) -> dict[str, Any]:
    if paths.output.exists():
        shutil.rmtree(paths.output)
    paths.output.mkdir(parents=True, exist_ok=True)
    selected_assets_manifest = write_selected_assets(paths=paths, manual_slices=manual_slices)
    mode_results = {}
    for mode in ("clean-editable", "visual-fidelity", "visual-ocr"):
        mode_results[mode] = write_manual_mode_project(
            paths=paths,
            manual_slices=manual_slices,
            mode=mode,
            selected_assets_manifest=selected_assets_manifest,
        )
    resource_dir = paths.output / "resource-kit"
    resource_dir.mkdir(parents=True, exist_ok=True)
    write_json(resource_dir / "manifest.json", selected_assets_manifest)
    contact_sheet = write_contact_sheet(
        paths=paths,
        manual_slices=manual_slices,
        output_dir=resource_dir,
        filename="contact-sheet.png",
    )
    selected_assets_manifest["contactSheet"] = "contact-sheet.png"
    write_json(resource_dir / "manifest.json", selected_assets_manifest)
    selected_zip = create_selected_assets_zip(paths.output, selected_assets_manifest)
    if include_debug:
        write_manual_debug(paths=paths, manual_slices=manual_slices)
    manifest = {
        "schema": "pencil.assisted_slice_project_manifest.v1",
        "projectName": manual_slices.get("projectName") or "Assisted Slice Project",
        "createdAt": datetime.now(UTC).isoformat(),
        "pageCount": len(manual_slices.get("pages") or []),
        "modes": ["clean-editable", "visual-fidelity", "visual-ocr"],
        "manualSlices": "manual_slices.v1.json",
        "selectedAssetsZip": "selected-assets.zip",
        "contactSheet": "resource-kit/contact-sheet.png",
        "selectedAssetCount": len(selected_assets_manifest["assets"]),
        "modeResults": mode_results,
        "warnings": [],
    }
    write_json(paths.output / "manual_slices.v1.json", manual_slices)
    write_json(paths.output / "manifest.json", manifest)
    create_manual_project_zip(paths.output)
    manifest["zip"] = "project.zip"
    manifest["zipPath"] = str(paths.output / "project.zip")
    manifest["selectedAssetsZipPath"] = str(selected_zip)
    manifest["projectZipUrl"] = f"/api/pencil/slice-projects/{paths.project_id}/download.zip"
    manifest["selectedAssetsZipUrl"] = f"/api/pencil/slice-projects/{paths.project_id}/selected-assets.zip"
    write_json(paths.output / "manifest.json", manifest)
    return manifest


def write_export_preview(*, paths: SliceProjectPaths, manual_slices: dict[str, Any]) -> dict[str, Any]:
    preview_dir = paths.output / "export-preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    contact_sheet = write_contact_sheet(
        paths=paths,
        manual_slices=manual_slices,
        output_dir=preview_dir,
        filename="contact-sheet.png",
    )
    preview_html = preview_dir / "index.html"
    assets = contact_sheet["assets"]
    preview_html.write_text(
        "<!doctype html><html><head><meta charset='utf-8'><title>Export Preview</title>"
        "<style>body{margin:0;background:#0f172a;color:#e5e7eb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:24px}"
        "img{max-width:100%;border:1px solid #334155;border-radius:8px;background:#020617} table{border-collapse:collapse;margin-top:18px;width:100%}"
        "td,th{border-bottom:1px solid #263244;padding:8px;text-align:left;font-size:13px}</style></head><body>"
        f"<h1>Export Preview</h1><p>{len(assets)} selected assets</p><img src='contact-sheet.png' alt='contact sheet'>"
        "<table><thead><tr><th>Page</th><th>Name</th><th>Size</th><th>File</th></tr></thead><tbody>"
        + "".join(
            f"<tr><td>{escape(str(asset['pageId']))}</td><td>{escape(str(asset['displayName']))}</td><td>{asset['bbox']['width']}x{asset['bbox']['height']}</td><td>{escape(str(asset['file']))}</td></tr>"
            for asset in assets
        )
        + "</tbody></table></body></html>",
        encoding="utf-8",
    )
    manifest = {
        "schema": "pencil.export_preview.v1",
        "createdAt": datetime.now(UTC).isoformat(),
        "assetCount": len(assets),
        "contactSheet": str(contact_sheet["path"]),
        "contactSheetUrl": f"/api/pencil/slice-projects/{paths.project_id}/export-preview/contact-sheet.png",
        "previewHtml": str(preview_html),
        "previewHtmlUrl": f"/api/pencil/slice-projects/{paths.project_id}/export-preview/index.html",
        "assets": assets,
    }
    write_json(preview_dir / "manifest.json", manifest)
    return manifest


def write_contact_sheet(
    *,
    paths: SliceProjectPaths,
    manual_slices: dict[str, Any],
    output_dir: Path,
    filename: str,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    selected: list[dict[str, Any]] = []
    for page in manual_slices.get("pages") or []:
        page_id = str(page["pageId"])
        for index, item in enumerate([entry for entry in page.get("slices") or [] if entry.get("selected") is not False], start=1):
            selected.append(
                {
                    "id": item["id"],
                    "pageId": page_id,
                    "name": item["name"],
                    "displayName": item.get("displayName") or item["name"],
                    "kind": item["kind"],
                    "tags": item.get("tags") or [],
                    "bbox": item["bbox"],
                    "file": f"{page_id}/slice_{index:04d}.png",
                    "sourceImage": str(page["sourceImage"]),
                }
            )
    thumb_w = 160
    thumb_h = 120
    label_h = 54
    gap = 16
    columns = 4 if len(selected) > 1 else 1
    rows = max(1, (len(selected) + columns - 1) // columns)
    sheet_w = columns * thumb_w + (columns + 1) * gap
    sheet_h = rows * (thumb_h + label_h) + (rows + 1) * gap
    sheet = Image.new("RGB", (sheet_w, sheet_h), "#0f172a")
    draw = ImageDraw.Draw(sheet)
    for index, asset in enumerate(selected):
        row = index // columns
        col = index % columns
        left = gap + col * (thumb_w + gap)
        top = gap + row * (thumb_h + label_h + gap)
        bbox = asset["bbox"]
        source_path = paths.root / asset["sourceImage"]
        with Image.open(source_path) as image:
            crop = image.convert("RGBA").crop((bbox["x"], bbox["y"], bbox["x"] + bbox["width"], bbox["y"] + bbox["height"]))
        crop.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        draw.rectangle((left, top, left + thumb_w, top + thumb_h), fill="#020617", outline="#334155")
        paste_x = left + (thumb_w - crop.width) // 2
        paste_y = top + (thumb_h - crop.height) // 2
        sheet.paste(crop.convert("RGB"), (paste_x, paste_y))
        label_top = top + thumb_h + 6
        draw.text((left, label_top), f"{index + 1}. {asset['pageId']}", fill="#e5e7eb")
        draw.text((left, label_top + 16), str(asset["displayName"])[:22], fill="#cbd5e1")
        draw.text((left, label_top + 32), f"{bbox['width']}x{bbox['height']}  {asset['file']}", fill="#94a3b8")
    if not selected:
        draw.text((gap, gap), "No selected assets", fill="#e5e7eb")
    path = output_dir / filename
    sheet.save(path)
    return {"path": path, "assets": selected}


def write_selected_assets(*, paths: SliceProjectPaths, manual_slices: dict[str, Any]) -> dict[str, Any]:
    assets_root = paths.output / "selected-assets"
    assets: list[dict[str, Any]] = []
    for page in manual_slices.get("pages") or []:
        page_id = str(page["pageId"])
        source_path = paths.root / str(page["sourceImage"])
        page_asset_dir = assets_root / page_id
        page_asset_dir.mkdir(parents=True, exist_ok=True)
        with Image.open(source_path) as image:
            source = image.convert("RGBA")
            for index, item in enumerate([entry for entry in page.get("slices") or [] if entry.get("selected") is not False], start=1):
                bbox = item["bbox"]
                filename = f"slice_{index:04d}.png"
                relative = f"{page_id}/{filename}"
                crop = source.crop((bbox["x"], bbox["y"], bbox["x"] + bbox["width"], bbox["y"] + bbox["height"]))
                crop.save(page_asset_dir / filename)
                assets.append(
                    {
                        "id": item["id"],
                        "pageId": page_id,
                        "name": item["name"],
                        "displayName": item.get("displayName") or item["name"],
                        "kind": item["kind"],
                        "tags": item.get("tags") or [],
                        "reviewState": item.get("reviewState") or "confirmed",
                        "bbox": bbox,
                        "file": relative,
                        "exportMode": item["exportMode"],
                        "source": item.get("source") or "manual",
                        "candidateIds": item.get("candidateIds") or [],
                    }
                )
    manifest = {
        "schema": "pencil.selected_assets.v1",
        "createdAt": datetime.now(UTC).isoformat(),
        "assetCount": len(assets),
        "assets": assets,
    }
    write_json(assets_root / "manifest.json", manifest)
    return manifest


def write_manual_mode_project(
    *,
    paths: SliceProjectPaths,
    manual_slices: dict[str, Any],
    mode: str,
    selected_assets_manifest: dict[str, Any],
) -> dict[str, Any]:
    mode_root = paths.output / mode
    visible_root = mode_root / "assets" / "visible"
    frames = []
    assets_by_id = {asset["id"]: asset for asset in selected_assets_manifest["assets"]}
    mode_assets = []
    for page_index, page in enumerate(manual_slices.get("pages") or [], start=1):
        page_id = str(page["pageId"])
        frame = {
            "id": f"{page_id}__frame",
            "type": "frame",
            "name": f"{manual_slices.get('projectName') or 'Assisted Slice Project'} {page_id}",
            "x": (page_index - 1) * (int(page["width"]) + 120),
            "y": 0,
            "width": int(page["width"]),
            "height": int(page["height"]),
            "layout": "none",
            "fill": "#FFFFFF",
            "metadata": {
                "type": "manual_slice_page",
                "pageId": page_id,
                "exportMode": mode,
            },
            "children": [],
        }
        for item in page.get("slices") or []:
            if item.get("selected") is False:
                continue
            asset = assets_by_id[item["id"]]
            visible_dir = visible_root / page_id
            visible_dir.mkdir(parents=True, exist_ok=True)
            source_asset = paths.output / "selected-assets" / asset["file"]
            target_name = f"{safe_slug(mode, 'mode')}__{page_id}__{Path(asset['file']).name}"
            target = visible_dir / target_name
            shutil.copy2(source_asset, target)
            url = f"./assets/visible/{page_id}/{target_name}"
            bbox = item["bbox"]
            frame["children"].append(
                {
                    "id": f"{page_id}__node_{safe_slug(item['id'], 'slice')}",
                    "type": "rectangle",
                    "name": item["name"],
                    "x": bbox["x"],
                    "y": bbox["y"],
                    "width": bbox["width"],
                    "height": bbox["height"],
                    "fill": {"type": "image", "enabled": True, "url": url, "mode": "stretch"},
                    "metadata": {
                        "type": "manual_slice_asset",
                        "pageId": page_id,
                        "sliceId": item["id"],
                        "kind": item["kind"],
                        "bbox": bbox,
                        "exportMode": item["exportMode"],
                    },
                }
            )
            mode_assets.append({**asset, "url": url})
        frames.append(frame)

    document = {"version": "2.11", "children": frames}
    validate_project_pen_contract(document, mode_root)
    write_json(mode_root / "design.pen", document)
    write_json(mode_root / "manifest.json", {"mode": mode, "assets": mode_assets, "assetCount": len(mode_assets)})
    return {
        "mode": mode,
        "designPen": f"{mode}/design.pen",
        "manifest": f"{mode}/manifest.json",
        "frameCount": len(frames),
        "assetCount": len(mode_assets),
    }


def create_selected_assets_zip(out_dir: Path, manifest: dict[str, Any]) -> Path:
    zip_path = out_dir / "selected-assets.zip"
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        assets_root = out_dir / "selected-assets"
        for asset in manifest["assets"]:
            asset_path = assets_root / asset["file"]
            archive.write(asset_path, asset_path.relative_to(assets_root))
        archive.write(assets_root / "manifest.json", "manifest.json")
    return zip_path


def create_manual_project_zip(out_dir: Path) -> Path:
    zip_path = out_dir / "project.zip"
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted(out_dir.rglob("*")):
            if path == zip_path or path.is_dir():
                continue
            relative = path.relative_to(out_dir)
            if relative.parts and relative.parts[0] == "selected-assets":
                continue
            archive.write(path, relative)
    return zip_path


def write_manual_debug(*, paths: SliceProjectPaths, manual_slices: dict[str, Any]) -> None:
    debug_root = paths.output / "debug" / "pages"
    candidates_by_page: dict[str, dict[str, Any]] = {}
    if paths.candidates_json.exists():
        candidates = read_json(paths.candidates_json)
        candidates_by_page = {str(page["pageId"]): page for page in candidates.get("pages") or []}
    for page in manual_slices.get("pages") or []:
        page_id = str(page["pageId"])
        page_debug = debug_root / page_id
        page_debug.mkdir(parents=True, exist_ok=True)
        write_json(page_debug / "manual_slices.v1.json", {"schema": MANUAL_SLICES_SCHEMA, "pages": [page]})
        source_path = paths.root / str(page["sourceImage"])
        shutil.copy2(source_path, page_debug / "source.png")
        draw_overlay(source_path, page.get("slices") or [], page_debug / "overlay.png")
        candidate_page = candidates_by_page.get(page_id)
        if candidate_page is not None:
            write_json(page_debug / "candidates.v1.json", {"schema": SLICE_CANDIDATES_SCHEMA, "pages": [candidate_page]})
            draw_overlay(
                source_path,
                [
                    {"name": str(index), "bbox": candidate["bbox"], "selected": True}
                    for index, candidate in enumerate(candidate_page.get("candidates") or [], start=1)
                ],
                page_debug / "candidates_overlay.png",
                outline="#f59e0b",
            )


def copy_slice_debug(artifact_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "m29_physical_evidence.v1.json",
        "m29-pencil-replay.v1.json",
        "container_foreground_audit.v1.json",
        "source.png",
    ):
        source = artifact_dir / name
        if source.exists():
            shutil.copy2(source, target_dir / name)
    psdlike_debug = artifact_dir / "psdlike_debug"
    if psdlike_debug.exists():
        shutil.copytree(psdlike_debug, target_dir / "psdlike_debug", dirs_exist_ok=True)


def draw_overlay(source_path: Path, slices: list[dict[str, Any]], output_path: Path, *, outline: str = "#22c55e") -> None:
    with Image.open(source_path) as image:
        overlay = image.convert("RGB")
    draw = ImageDraw.Draw(overlay)
    for index, item in enumerate(slices, start=1):
        if item.get("selected") is False:
            continue
        bbox = item["bbox"]
        x = bbox["x"]
        y = bbox["y"]
        w = bbox["width"]
        h = bbox["height"]
        draw.rectangle((x, y, x + w, y + h), outline=outline, width=4)
        draw.rectangle((x, max(0, y - 18), x + 90, max(18, y)), fill="#111827")
        draw.text((x + 4, max(0, y - 17)), f"{index}. {item['name'][:12]}", fill="#ffffff")
    overlay.save(output_path)


def normalize_bbox(value: dict[str, Any]) -> dict[str, int]:
    return {
        "x": int(round(float(value.get("x") or 0))),
        "y": int(round(float(value.get("y") or 0))),
        "width": int(round(float(value.get("width") or 0))),
        "height": int(round(float(value.get("height") or 0))),
    }


def clamp_bbox(value: dict[str, int], width: int, height: int) -> dict[str, int]:
    x = max(0, min(width, int(value["x"])))
    y = max(0, min(height, int(value["y"])))
    right = max(x + 1, min(width, int(value["x"]) + int(value["width"])))
    bottom = max(y + 1, min(height, int(value["y"]) + int(value["height"])))
    return {"x": x, "y": y, "width": right - x, "height": bottom - y}


def bbox_iou(a: dict[str, int], b: dict[str, int]) -> float:
    left = max(a["x"], b["x"])
    top = max(a["y"], b["y"])
    right = min(a["x"] + a["width"], b["x"] + b["width"])
    bottom = min(a["y"] + a["height"], b["y"] + b["height"])
    if right <= left or bottom <= top:
        return 0.0
    intersection = (right - left) * (bottom - top)
    union = a["width"] * a["height"] + b["width"] * b["height"] - intersection
    return intersection / union if union > 0 else 0.0
