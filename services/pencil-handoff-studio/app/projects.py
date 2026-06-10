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
from .utils import bbox_area, clamp_bbox, file_sha256, safe_slug


CANDIDATES_SCHEMA = "pencil_handoff.candidates.v1"
MANUAL_SLICES_SCHEMA = "pencil.manual_slices.v1"
PROJECT_SCHEMA = "pencil_handoff.project.v1"
REVIEW_STATE_SCHEMA = "pencil_handoff.review_state.v1"


@dataclass(frozen=True)
class UploadInput:
    original_name: str
    source_path: Path


@dataclass(frozen=True)
class ProjectPaths:
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


class ProjectStorage:
    def __init__(self, root: Path) -> None:
        self.root = root / "projects"
        self.root.mkdir(parents=True, exist_ok=True)

    def create_project(self, project_name: str) -> ProjectPaths:
        project_id = f"handoff_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}"
        paths = self.paths(project_id)
        paths.uploads.mkdir(parents=True, exist_ok=True)
        paths.pages.mkdir(parents=True, exist_ok=True)
        paths.evidence.mkdir(parents=True, exist_ok=True)
        paths.output.mkdir(parents=True, exist_ok=True)
        write_json(
            paths.project_json,
            {
                "schema": PROJECT_SCHEMA,
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

    def paths(self, project_id: str) -> ProjectPaths:
        safe_id = safe_slug(project_id, "handoff_project")
        root = self.root / safe_id
        return ProjectPaths(
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

    def patch_project(self, paths: ProjectPaths, **updates: Any) -> dict[str, Any]:
        current = read_json(paths.project_json) if paths.project_json.exists() else {"projectId": paths.project_id}
        project = {**current, **updates, "updatedAt": now_iso()}
        write_json(paths.project_json, project)
        return project

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
                    }
                )
        items.sort(key=lambda item: str(item.get("updatedAt") or ""), reverse=True)
        return items

    def delete_project(self, project_id: str) -> None:
        paths = self.paths(project_id)
        if paths.root.exists():
            shutil.rmtree(paths.root)


def initialize_project(
    *,
    paths: ProjectPaths,
    inputs: list[UploadInput],
    project_name: str,
    settings: Settings,
    include_ocr: bool,
    include_basic_elements: bool,
) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    warnings: list[str] = []
    for index, item in enumerate(inputs, start=1):
        page_id = f"page_{index:04d}"
        page_dir = paths.pages / page_id
        page_dir.mkdir(parents=True, exist_ok=True)
        source_path = page_dir / "source.png"
        (page_dir / "original_name.txt").write_text(item.original_name, encoding="utf-8")
        with Image.open(item.source_path) as image:
            source = image.convert("RGBA")
            source.save(source_path)
            width, height = source.size
        result = evidence.collect_page_evidence(
            page_id=page_id,
            source_path=source_path,
            work_dir=paths.evidence / page_id,
            settings=settings,
            include_ocr=include_ocr,
            include_basic_elements=include_basic_elements,
        )
        warnings.extend(result.warnings)
        candidates = evidence.merge_evidence_candidates(
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
        "schema": CANDIDATES_SCHEMA,
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
        "schema": PROJECT_SCHEMA,
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
        "reviewUrl": f"/api/handoff-projects/{paths.project_id}/review",
        "candidatesPath": str(paths.candidates_json),
        "manualSlicesPath": str(paths.manual_slices_json),
        "reviewStatePath": str(paths.review_state_json),
    }


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


def default_review_state(*, project_id: str, candidates: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": REVIEW_STATE_SCHEMA,
        "projectId": project_id,
        "activePageId": (candidates.get("pages") or [{}])[0].get("pageId") if candidates.get("pages") else None,
        "filters": {
            "showHidden": False,
            "showCandidates": True,
            "showBasic": True,
            "colors": {
                "candidate": "#22c55e",
                "selected": "#2563eb",
                "active": "#d946ef",
                "hidden": "#94a3b8",
            },
        },
        "viewport": {"x": 0, "y": 0, "scale": 1},
        "pages": [
            {
                "pageId": page["pageId"],
                "hiddenCandidateIds": [],
                "rejectedCandidateIds": [],
                "lastFilter": None,
            }
            for page in candidates.get("pages") or []
        ],
        "lastSavedAt": now_iso(),
    }


def validate_review_state(value: dict[str, Any], candidates: dict[str, Any]) -> dict[str, Any]:
    if value.get("schema") != REVIEW_STATE_SCHEMA:
        raise ValueError(f"schema must be {REVIEW_STATE_SCHEMA}")
    candidate_ids_by_page = {
        str(page["pageId"]): {str(candidate["id"]) for candidate in page.get("candidates") or []}
        for page in candidates.get("pages") or []
    }
    pages: list[dict[str, Any]] = []
    for page in value.get("pages") or []:
        page_id = str(page.get("pageId") or "")
        known = candidate_ids_by_page.get(page_id)
        if known is None:
            raise ValueError(f"unknown pageId in review_state: {page_id}")
        hidden = [str(item) for item in page.get("hiddenCandidateIds") or []]
        rejected = [str(item) for item in page.get("rejectedCandidateIds") or []]
        for candidate_id in [*hidden, *rejected]:
            if candidate_id not in known:
                raise ValueError(f"unknown candidate id for {page_id}: {candidate_id}")
        pages.append({**page, "pageId": page_id, "hiddenCandidateIds": hidden, "rejectedCandidateIds": rejected})
    return {
        "schema": REVIEW_STATE_SCHEMA,
        "projectId": str(value.get("projectId") or ""),
        "activePageId": value.get("activePageId"),
        "filters": value.get("filters") if isinstance(value.get("filters"), dict) else {},
        "viewport": value.get("viewport") if isinstance(value.get("viewport"), dict) else {"x": 0, "y": 0, "scale": 1},
        "pages": pages,
        "lastSavedAt": now_iso(),
    }


def ensure_review_state(paths: ProjectPaths) -> dict[str, Any]:
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


def validate_manual_slices(value: dict[str, Any], candidates: dict[str, Any]) -> dict[str, Any]:
    if value.get("schema") != MANUAL_SLICES_SCHEMA:
        raise ValueError(f"schema must be {MANUAL_SLICES_SCHEMA}")
    page_info = {str(page["pageId"]): page for page in candidates.get("pages") or []}
    seen_ids: set[str] = set()
    pages: list[dict[str, Any]] = []
    for page in value.get("pages") or []:
        page_id = str(page.get("pageId") or "")
        info = page_info.get(page_id)
        if info is None:
            raise ValueError(f"unknown pageId in manual_slices: {page_id}")
        slices: list[dict[str, Any]] = []
        for item in page.get("slices") or []:
            item_id = str(item.get("id") or "")
            if not item_id:
                raise ValueError("slice id is required")
            if item_id in seen_ids:
                raise ValueError(f"duplicate slice id: {item_id}")
            seen_ids.add(item_id)
            kind = str(item.get("kind") or "")
            if kind not in {"image", "icon", "basic"}:
                raise ValueError(f"unsupported slice kind: {kind}")
            bbox = clamp_bbox(item.get("bbox") or {}, int(info["width"]), int(info["height"]))
            if bbox_area(bbox) <= 0 or bbox != item.get("bbox"):
                raise ValueError(f"invalid bbox for slice {item_id}")
            slices.append(
                {
                    "id": item_id,
                    "pageId": page_id,
                    "name": str(item.get("name") or item_id),
                    "displayName": str(item.get("displayName") or item.get("name") or item_id),
                    "kind": kind,
                    "bbox": bbox,
                    "selected": item.get("selected") is not False,
                    "source": str(item.get("source") or "manual"),
                    "candidateIds": [str(candidate_id) for candidate_id in item.get("candidateIds") or []],
                    "tags": [str(tag) for tag in item.get("tags") or []],
                }
            )
        pages.append(
            {
                "pageId": page_id,
                "sourceImage": str(page.get("sourceImage") or info["sourceImage"]),
                "width": int(info["width"]),
                "height": int(info["height"]),
                "slices": slices,
            }
        )
    return {"schema": MANUAL_SLICES_SCHEMA, "projectName": str(value.get("projectName") or "Pencil Handoff Project"), "pages": pages}


def project_summary(paths: ProjectPaths) -> dict[str, Any]:
    project = read_json(paths.project_json)
    candidates = read_json(paths.candidates_json) if paths.candidates_json.exists() else {"pages": []}
    manual = read_json(paths.manual_slices_json) if paths.manual_slices_json.exists() else {"pages": []}
    review = ensure_review_state(paths) if paths.candidates_json.exists() else {"pages": []}
    selected = selected_slice_count(manual)
    hidden = sum(len(page.get("hiddenCandidateIds") or []) for page in review.get("pages") or [])
    exported = (paths.output / "project.zip").exists() and (paths.output / "assets.zip").exists()
    return {
        **project,
        "pageCount": len(project.get("pages") or []),
        "candidateCount": sum(len(page.get("candidates") or []) for page in candidates.get("pages") or []),
        "selectedSliceCount": selected,
        "hiddenCandidateCount": hidden,
        "exported": exported,
        "reviewUrl": f"/api/handoff-projects/{paths.project_id}/review",
        "projectZipUrl": f"/api/handoff-projects/{paths.project_id}/project.zip" if exported else None,
        "assetsZipUrl": f"/api/handoff-projects/{paths.project_id}/assets.zip" if exported else None,
    }


def selected_slice_count(manual_slices: dict[str, Any]) -> int:
    return sum(1 for page in manual_slices.get("pages") or [] for item in page.get("slices") or [] if item.get("selected") is not False)


def source_path_for_page(paths: ProjectPaths, page_id: str) -> Path:
    page_safe = safe_slug(page_id, "page")
    source = paths.pages / page_safe / "source.png"
    if not source.exists():
        raise FileNotFoundError(page_id)
    return source


def reset_output(paths: ProjectPaths) -> None:
    if paths.output.exists():
        shutil.rmtree(paths.output)
    paths.output.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
