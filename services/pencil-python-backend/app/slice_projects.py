from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
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
            item["kind"] = str(item.get("kind") or "image")
            item["selected"] = item.get("selected") is not False
            item["exportMode"] = export_mode
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
    write_json(paths.output / "manifest.json", manifest)
    return manifest


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
                name = safe_slug(str(item.get("name") or item["id"]), f"slice_{index:04d}")
                filename = f"{index:04d}_{name}.png"
                relative = f"{page_id}/{filename}"
                crop = source.crop((bbox["x"], bbox["y"], bbox["x"] + bbox["width"], bbox["y"] + bbox["height"]))
                crop.save(page_asset_dir / filename)
                assets.append(
                    {
                        "id": item["id"],
                        "pageId": page_id,
                        "name": item["name"],
                        "kind": item["kind"],
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
