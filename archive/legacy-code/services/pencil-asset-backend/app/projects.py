from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PIL import Image

from . import evidence
from .config import Settings
from .jsonio import read_json, write_json
from .utils import bbox_area, bbox_iou, clamp_bbox, file_sha256, normalize_bbox, safe_slug


ASSET_CANDIDATES_SCHEMA = "pencil_asset.candidates.v1"
MANUAL_SLICES_SCHEMA = "pencil.manual_slices.v1"
PROJECT_MANIFEST_SCHEMA = "pencil_asset.project.v1"
REVIEW_STATE_SCHEMA = "pencil_asset.review_state.v1"


@dataclass(frozen=True)
class UploadInput:
    page_id: str
    original_name: str
    source_path: Path


@dataclass(frozen=True)
class AssetProjectPaths:
    project_id: str
    root: Path
    uploads: Path
    pages: Path
    evidence: Path
    output: Path
    project_json: Path
    candidates_json: Path
    manual_slices_json: Path
    review_state_json: Path


class AssetProjectStorage:
    def __init__(self, root: Path) -> None:
        self.root = root / "asset-projects"
        self.root.mkdir(parents=True, exist_ok=True)

    def create_project(self, project_name: str) -> AssetProjectPaths:
        project_id = f"asset_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}"
        paths = self.paths(project_id)
        paths.uploads.mkdir(parents=True, exist_ok=True)
        paths.pages.mkdir(parents=True, exist_ok=True)
        paths.evidence.mkdir(parents=True, exist_ok=True)
        paths.output.mkdir(parents=True, exist_ok=True)
        write_json(
            paths.project_json,
            {
                "schema": PROJECT_MANIFEST_SCHEMA,
                "projectId": project_id,
                "projectName": project_name,
                "status": "created",
                "createdAt": now_iso(),
                "updatedAt": now_iso(),
                "pages": [],
                "warnings": [],
            },
        )
        return paths

    def paths(self, project_id: str) -> AssetProjectPaths:
        safe_id = safe_slug(project_id, "asset_project")
        root = self.root / safe_id
        return AssetProjectPaths(
            project_id=safe_id,
            root=root,
            uploads=root / "uploads",
            pages=root / "pages",
            evidence=root / "evidence",
            output=root / "output",
            project_json=root / "project.json",
            candidates_json=root / "candidates.v1.json",
            manual_slices_json=root / "manual_slices.v1.json",
            review_state_json=root / "review_state.v1.json",
        )

    def patch_project(self, paths: AssetProjectPaths, **updates: Any) -> dict[str, Any]:
        current = read_json(paths.project_json) if paths.project_json.exists() else {"projectId": paths.project_id}
        project = {**current, **updates, "updatedAt": now_iso()}
        write_json(paths.project_json, project)
        return project

    def read_project(self, project_id: str) -> dict[str, Any]:
        paths = self.paths(project_id)
        if not paths.project_json.exists():
            raise FileNotFoundError(project_id)
        return read_json(paths.project_json)

    def list_projects(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for root in sorted(self.root.iterdir() if self.root.exists() else [], reverse=True):
            if not root.is_dir():
                continue
            paths = self.paths(root.name)
            try:
                items.append(project_summary(paths))
            except Exception as error:
                items.append(
                    {
                        "projectId": root.name,
                        "projectName": root.name,
                        "status": "broken",
                        "pageCount": 0,
                        "candidateCount": 0,
                        "selectedSliceCount": 0,
                        "exported": False,
                        "error": str(error),
                        "warnings": [str(error)],
                    }
                )
        items.sort(key=lambda item: str(item.get("updatedAt") or ""), reverse=True)
        return items


def initialize_asset_project(
    *,
    paths: AssetProjectPaths,
    inputs: list[UploadInput],
    project_name: str,
    settings: Settings,
) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, item in enumerate(inputs, start=1):
        page_id = f"page_{index:04d}"
        page_dir = paths.pages / page_id
        page_dir.mkdir(parents=True, exist_ok=True)
        source_path = page_dir / "source.png"
        with Image.open(item.source_path) as image:
            source = image.convert("RGBA")
            source.save(source_path)
            width, height = source.size
        page_evidence_dir = paths.evidence / page_id
        result = evidence.collect_page_evidence(
            page_id=page_id,
            source_path=source_path,
            work_dir=page_evidence_dir,
            settings=settings,
        )
        warnings.extend(result.warnings)
        candidates = evidence.merge_evidence_candidates(
            page_id=page_id,
            width=width,
            height=height,
            evidence_items=result.evidence.get("items") or [],
        )
        if not candidates and result.evidence.get("items"):
            candidates = review_candidates_from_evidence(
                page_id=page_id,
                width=width,
                height=height,
                evidence_items=result.evidence.get("items") or [],
            )
        pages.append(
            {
                "pageId": page_id,
                "originalName": item.original_name,
                "sourceImage": f"pages/{page_id}/source.png",
                "width": width,
                "height": height,
                "sha256": file_sha256(source_path),
                "evidencePath": f"evidence/{page_id}/evidence.v1.json",
                "candidateCount": len(candidates),
                "candidates": candidates,
            }
        )

    if not any(page["candidateCount"] > 0 for page in pages):
        raise RuntimeError("no image/icon candidate evidence generated")

    public_pages = [
        {
            "pageId": page["pageId"],
            "originalName": page["originalName"],
            "sourceImage": page["sourceImage"],
            "width": page["width"],
            "height": page["height"],
            "sha256": page["sha256"],
            "evidencePath": page["evidencePath"],
        }
        for page in pages
    ]
    candidates_doc = {
        "schema": ASSET_CANDIDATES_SCHEMA,
        "projectId": paths.project_id,
        "projectName": project_name,
        "pages": [
            {
                "pageId": page["pageId"],
                "sourceImage": page["sourceImage"],
                "width": page["width"],
                "height": page["height"],
                "candidates": page["candidates"],
            }
            for page in pages
        ],
    }
    manual_doc = default_manual_slices(project_name=project_name, pages=public_pages)
    review_state = default_review_state(project_id=paths.project_id, candidates=candidates_doc)
    write_json(paths.candidates_json, candidates_doc)
    write_json(paths.manual_slices_json, manual_doc)
    write_json(paths.review_state_json, review_state)
    return {
        "schema": PROJECT_MANIFEST_SCHEMA,
        "projectId": paths.project_id,
        "projectName": project_name,
        "status": "ready",
        "createdAt": read_json(paths.project_json).get("createdAt") if paths.project_json.exists() else now_iso(),
        "updatedAt": now_iso(),
        "pageCount": len(public_pages),
        "pages": public_pages,
        "candidateCount": sum(len(page["candidates"]) for page in candidates_doc["pages"]),
        "selectedSliceCount": 0,
        "warnings": sorted(set(warnings)),
        "reviewUrl": f"/api/asset-projects/{paths.project_id}/review",
        "candidatesPath": str(paths.candidates_json),
        "manualSlicesPath": str(paths.manual_slices_json),
        "reviewStatePath": str(paths.review_state_json),
    }


def review_candidates_from_evidence(
    *, page_id: str, width: int, height: int, evidence_items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: list[dict[str, int]] = []
    ranked = sorted(
        evidence_items,
        key=lambda item: (
            item.get("kind") not in {"image", "icon", "ignore", "control"},
            -float(item.get("confidence") or 0.0),
            -bbox_area(item.get("bbox") or {"x": 0, "y": 0, "width": 0, "height": 0}),
        ),
    )
    for item in ranked:
        bbox = clamp_bbox(item.get("bbox") or {}, width, height)
        if bbox_area(bbox) < 256:
            continue
        if bbox["width"] > width * 0.95 and bbox["height"] > height * 0.85:
            continue
        raw_kind = str(item.get("rawKind") or "").lower()
        if item.get("kind") not in {"image", "icon", "ignore"}:
            continue
        if item.get("kind") == "ignore" and not any(word in raw_kind for word in ("image", "icon", "symbol", "raster", "media", "bitmap")):
            continue
        if any(bbox_iou(bbox, existing) > 0.82 for existing in seen):
            continue
        seen.append(bbox)
        candidates.append(
            {
                "id": f"{page_id}__candidate_{len(candidates) + 1:04d}",
                "kind": "image",
                "bbox": bbox,
                "sources": [str(item.get("source") or "evidence")],
                "confidence": round(float(item.get("confidence") or 0.3), 4),
                "reason": "review_only_physical_candidate",
                "level": "review",
                "selectedDefault": False,
                "sourceIds": [str(item.get("id") or "")],
            }
        )
        if len(candidates) >= 12:
            break
    return candidates


def default_manual_slices(*, project_name: str, pages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": MANUAL_SLICES_SCHEMA,
        "projectName": project_name,
        "pages": [
            {
                "pageId": page["pageId"],
                "sourceImage": page["sourceImage"],
                "width": int(page["width"]),
                "height": int(page["height"]),
                "slices": [],
            }
            for page in pages
        ],
    }


def default_review_state(*, project_id: str, candidates: dict[str, Any]) -> dict[str, Any]:
    pages = [
        {
            "pageId": str(page["pageId"]),
            "rejectedCandidateIds": [],
            "hiddenCandidateIds": [],
            "lastFilter": {},
        }
        for page in candidates.get("pages") or []
    ]
    return {
        "schema": REVIEW_STATE_SCHEMA,
        "projectId": project_id,
        "lastActivePageId": pages[0]["pageId"] if pages else "",
        "filters": {},
        "pages": pages,
        "updatedAt": now_iso(),
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
    seen_pages: set[str] = set()
    for page in pages_value:
        page_id = str(page.get("pageId") or "")
        if page_id not in candidate_pages:
            raise ValueError(f"unknown pageId: {page_id}")
        if page_id in seen_pages:
            raise ValueError(f"duplicate pageId: {page_id}")
        seen_pages.add(page_id)
        valid_ids = candidate_ids_by_page[page_id]
        rejected = normalize_candidate_id_list(page.get("rejectedCandidateIds"), valid_ids, page_id, "rejectedCandidateIds")
        hidden = normalize_candidate_id_list(page.get("hiddenCandidateIds"), valid_ids, page_id, "hiddenCandidateIds")
        last_filter = page.get("lastFilter") if isinstance(page.get("lastFilter"), dict) else {}
        pages.append(
            {
                "pageId": page_id,
                "rejectedCandidateIds": rejected,
                "hiddenCandidateIds": hidden,
                "lastFilter": last_filter,
            }
        )

    for page_id in sorted(set(candidate_pages) - seen_pages):
        pages.append({"pageId": page_id, "rejectedCandidateIds": [], "hiddenCandidateIds": [], "lastFilter": {}})

    last_active = str(value.get("lastActivePageId") or "")
    if last_active not in candidate_pages and candidate_pages:
        last_active = sorted(candidate_pages)[0]
    filters = value.get("filters") if isinstance(value.get("filters"), dict) else {}
    return {
        "schema": REVIEW_STATE_SCHEMA,
        "projectId": str(value.get("projectId") or candidates.get("projectId") or ""),
        "lastActivePageId": last_active,
        "filters": filters,
        "pages": pages,
        "updatedAt": now_iso(),
    }


def normalize_candidate_id_list(value: object, valid_ids: set[str], page_id: str, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"page {page_id} {field} must be a list")
    normalized: list[str] = []
    for raw in value:
        candidate_id = str(raw)
        if candidate_id not in valid_ids:
            raise ValueError(f"unknown candidate id for {page_id}: {candidate_id}")
        normalized.append(candidate_id)
    return sorted(set(normalized))


def ensure_review_state(paths: AssetProjectPaths) -> dict[str, Any]:
    if not paths.candidates_json.exists():
        raise FileNotFoundError("candidates.v1.json not found")
    candidates = read_json(paths.candidates_json)
    if paths.review_state_json.exists():
        review_state = validate_review_state(read_json(paths.review_state_json), candidates)
    else:
        review_state = default_review_state(project_id=paths.project_id, candidates=candidates)
    write_json(paths.review_state_json, review_state)
    return review_state


def validate_manual_slices(value: dict[str, Any], candidates: dict[str, Any]) -> dict[str, Any]:
    if value.get("schema") != MANUAL_SLICES_SCHEMA:
        raise ValueError(f"manual slices schema must be {MANUAL_SLICES_SCHEMA}")
    candidate_pages = {str(page["pageId"]): page for page in candidates.get("pages") or []}
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
        for raw in slices_value:
            item = dict(raw)
            slice_id = str(item.get("id") or "")
            if not slice_id:
                raise ValueError("slice id is required")
            if slice_id in seen_ids:
                raise ValueError(f"duplicate slice id: {slice_id}")
            seen_ids.add(slice_id)
            kind = str(item.get("kind") or "image").lower()
            if kind not in {"image", "icon"}:
                raise ValueError(f"unsupported slice kind: {kind}")
            export_mode = str(item.get("exportMode") or "rect")
            if export_mode != "rect":
                raise ValueError(f"unsupported exportMode: {export_mode}")
            bbox = normalize_bbox(item.get("bbox") or {})
            if bbox["width"] <= 0 or bbox["height"] <= 0:
                raise ValueError(f"slice {slice_id} has invalid bbox")
            if bbox["x"] < 0 or bbox["y"] < 0 or bbox["x"] + bbox["width"] > width or bbox["y"] + bbox["height"] > height:
                raise ValueError(f"slice {slice_id} bbox is out of bounds")
            item.update(
                {
                    "id": slice_id,
                    "kind": kind,
                    "bbox": bbox,
                    "selected": item.get("selected") is not False,
                    "exportMode": export_mode,
                    "name": safe_slug(str(item.get("name") or slice_id), slice_id),
                    "displayName": str(item.get("displayName") or item.get("name") or slice_id),
                    "source": str(item.get("source") or "manual"),
                }
            )
            if not isinstance(item.get("candidateIds"), list):
                item["candidateIds"] = []
            item["candidateIds"] = [str(candidate_id) for candidate_id in item["candidateIds"] if str(candidate_id).strip()]
            if not isinstance(item.get("tags"), list):
                item["tags"] = []
            item["tags"] = [safe_slug(str(tag), "tag") for tag in item["tags"] if str(tag).strip()]
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
    return {
        "schema": MANUAL_SLICES_SCHEMA,
        "projectName": str(value.get("projectName") or "Pencil Asset Project"),
        "pages": normalized_pages,
    }


def selected_slice_count(manual_slices: dict[str, Any]) -> int:
    return sum(
        1
        for page in manual_slices.get("pages") or []
        for item in page.get("slices") or []
        if item.get("selected") is not False and item.get("kind") in {"image", "icon"}
    )


def project_summary(paths: AssetProjectPaths) -> dict[str, Any]:
    project = read_json(paths.project_json)
    candidates = read_json(paths.candidates_json) if paths.candidates_json.exists() else {"pages": []}
    manual = read_json(paths.manual_slices_json) if paths.manual_slices_json.exists() else {"pages": []}
    review_state = ensure_review_state(paths) if paths.candidates_json.exists() else {"pages": []}
    selected_by_page = {
        str(page.get("pageId")): sum(
            1
            for item in page.get("slices") or []
            if item.get("selected") is not False and item.get("kind") in {"image", "icon"}
        )
        for page in manual.get("pages") or []
    }
    rejected_by_page = {
        str(page.get("pageId")): len(page.get("rejectedCandidateIds") or [])
        for page in review_state.get("pages") or []
    }
    pages: list[dict[str, Any]] = []
    for page in candidates.get("pages") or project.get("pages") or []:
        page_id = str(page["pageId"])
        candidate_count = len(page.get("candidates") or [])
        selected_count = selected_by_page.get(page_id, 0)
        rejected_count = rejected_by_page.get(page_id, 0)
        pages.append(
            {
                "pageId": page_id,
                "sourceImage": page.get("sourceImage") or f"pages/{page_id}/source.png",
                "width": int(page.get("width") or 0),
                "height": int(page.get("height") or 0),
                "candidateCount": candidate_count,
                "selectedSliceCount": selected_count,
                "rejectedCandidateCount": rejected_count,
                "thumbnailUrl": f"/api/asset-projects/{paths.project_id}/source/{page_id}",
                "status": "ready" if selected_count > 0 else "untouched",
            }
        )
    exported = (paths.output / "project.zip").exists() and (paths.output / "selected-assets.zip").exists()
    selected_count_total = sum(page["selectedSliceCount"] for page in pages)
    rejected_count_total = sum(page["rejectedCandidateCount"] for page in pages)
    return {
        "projectId": paths.project_id,
        "projectName": project.get("projectName") or "Pencil Asset Project",
        "status": project.get("status") or "unknown",
        "pageCount": len(pages),
        "candidateCount": sum(page["candidateCount"] for page in pages),
        "selectedSliceCount": selected_count_total,
        "rejectedCandidateCount": rejected_count_total,
        "selectedAssetCount": project.get("selectedAssetCount", selected_count_total),
        "exported": exported,
        "reviewUrl": f"/api/asset-projects/{paths.project_id}/review",
        "downloadUrl": f"/api/asset-projects/{paths.project_id}/download.zip" if exported else None,
        "selectedAssetsDownloadUrl": f"/api/asset-projects/{paths.project_id}/selected-assets.zip" if exported else None,
        "thumbnailUrl": pages[0]["thumbnailUrl"] if pages else None,
        "pages": pages,
        "createdAt": project.get("createdAt"),
        "updatedAt": project.get("updatedAt"),
        "warnings": project.get("warnings") or [],
        "error": project.get("error"),
    }


def source_path_for_page(paths: AssetProjectPaths, page_id: str) -> Path:
    page_id = safe_slug(page_id, "page")
    source = paths.pages / page_id / "source.png"
    if not source.exists():
        raise FileNotFoundError(page_id)
    return source


def reset_output(paths: AssetProjectPaths) -> None:
    if paths.output.exists():
        shutil.rmtree(paths.output)
    paths.output.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
