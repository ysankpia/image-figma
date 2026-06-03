from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image

from .config import Settings
from .exporter.single_page import SinglePageExportOptions, export_single_page
from .hybrid_boundary import build_hybrid_boundary_artifact
from .jsonio import read_json, write_json
from .m29_runner import run_m29extract
from .psdlike_adapter import adapt_psdlike_to_pencil_evidence
from .psdlike_runner import run_psdlike
from .types import EXPORT_MODES, ExportRequest, PageInput
from .utils import mode_dir_name, safe_slug


@dataclass(frozen=True)
class PageExportResult:
    page_index: int
    page_namespace: str
    input: PageInput
    source_size: tuple[int, int]
    artifact_dir: Path
    single_export_dir: Path
    mode_manifests: dict[str, dict[str, Any]]
    boundary_source: str


def export_project(request: ExportRequest, settings: Settings) -> dict[str, Any]:
    if request.out_dir.exists():
        shutil.rmtree(request.out_dir)
    request.out_dir.mkdir(parents=True, exist_ok=True)

    modes = selected_modes(request.mode)
    work_dir = request.out_dir / "work"
    debug_pages_dir = request.out_dir / "debug" / "pages"
    page_results: list[PageExportResult] = []
    for index, page_input in enumerate(request.inputs, start=1):
        namespace = f"page_{index:04d}"
        page_work = work_dir / namespace
        artifact_dir = build_boundary_artifact(
            page_input=page_input,
            page_work=page_work,
            request=request,
            settings=settings,
        )
        single_export_dir = page_work / "single_page_export"
        export_single_page(
            SinglePageExportOptions(
                input_dir=artifact_dir,
                out=single_export_dir,
                name=f"{request.project_name} {namespace}",
                mode=request.mode,
                include_debug_pen=request.include_debug,
            )
        )
        mode_manifests = {
            mode: read_json(single_export_dir / mode_dir_name(mode) / "manifest.json")
            for mode in modes
        }
        with Image.open(page_input.path) as image:
            source_size = (image.width, image.height)
        if request.include_debug:
            copy_page_debug(artifact_dir, debug_pages_dir / namespace)
        page_results.append(
            PageExportResult(
                page_index=index,
                page_namespace=namespace,
                input=page_input,
                source_size=source_size,
                artifact_dir=artifact_dir,
                single_export_dir=single_export_dir,
                mode_manifests=mode_manifests,
                boundary_source=request.boundary_source,
            )
        )

    layout = compute_layout(page_results, request.columns)
    mode_results: dict[str, Any] = {}
    for mode in modes:
        mode_results[mode] = build_mode_project(
            mode=mode,
            request=request,
            page_results=page_results,
            layout=layout,
        )

    manifest = build_project_manifest(request, page_results, modes, layout, mode_results)
    manifest["zip"] = "project.zip"
    write_json(request.out_dir / "manifest.json", manifest)
    write_debug_report(request.out_dir / "debug" / "report.md", manifest)
    zip_path = create_project_zip(request.out_dir)
    manifest["zipPath"] = str(zip_path)
    write_json(request.out_dir / "manifest.json", manifest)
    return manifest


def build_boundary_artifact(
    *,
    page_input: PageInput,
    page_work: Path,
    request: ExportRequest,
    settings: Settings,
) -> Path:
    provider = request.ocr_provider if request.ocr_provider is not None else settings.ocr_provider
    if request.boundary_source == "m29":
        m29_dir = page_work / "m29"
        run_m29extract(
            image_path=page_input.path,
            output_dir=m29_dir,
            m29extract_path=settings.m29extract_path,
            ocr_provider=provider,
        )
        return m29_dir
    if request.boundary_source == "psdlike":
        psdlike_dir = page_work / "psdlike"
        cached_psdlike_dir = find_psdlike_artifact(request.psdlike_artifacts_root, page_input)
        if cached_psdlike_dir is not None:
            shutil.copytree(cached_psdlike_dir, psdlike_dir, dirs_exist_ok=True)
        else:
            run_psdlike(
                image_path=page_input.path,
                output_dir=psdlike_dir,
                ocr_provider=provider,
                psdlike_root=settings.psdlike_root,
                tile_size=settings.psdlike_tile_size,
            )
        artifact_dir = page_work / "psdlike_pencil_evidence"
        adapt_psdlike_to_pencil_evidence(psdlike_dir, artifact_dir)
        return artifact_dir
    if request.boundary_source == "hybrid":
        psdlike_dir = page_work / "psdlike"
        cached_psdlike_dir = find_psdlike_artifact(request.psdlike_artifacts_root, page_input)
        if cached_psdlike_dir is not None:
            shutil.copytree(cached_psdlike_dir, psdlike_dir, dirs_exist_ok=True)
        else:
            run_psdlike(
                image_path=page_input.path,
                output_dir=psdlike_dir,
                ocr_provider=provider,
                psdlike_root=settings.psdlike_root,
                tile_size=settings.psdlike_tile_size,
            )
        m29_dir = page_work / "m29_fallback"
        run_m29extract(
            image_path=page_input.path,
            output_dir=m29_dir,
            m29extract_path=settings.m29extract_path,
            ocr_provider="none",
        )
        hybrid_dir = page_work / "hybrid_boundary"
        build_hybrid_boundary_artifact(
            psdlike_dir=psdlike_dir,
            m29_dir=m29_dir,
            output_dir=hybrid_dir,
        )
        artifact_dir = page_work / "hybrid_pencil_evidence"
        adapt_psdlike_to_pencil_evidence(hybrid_dir, artifact_dir)
        return artifact_dir
    raise ValueError(f"unsupported boundary source: {request.boundary_source}")


def find_psdlike_artifact(root: Path | None, page_input: PageInput) -> Path | None:
    if root is None:
        return None
    root = root.expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"PSD-like artifacts root not found: {root}")

    candidates: list[Path] = []
    manifest_path = root / "input_manifest.v1.json"
    if manifest_path.exists():
        data = read_json(manifest_path)
        input_sha = file_sha256(page_input.path)
        input_path = page_input.path.expanduser().resolve()
        for item in data.get("cases") or []:
            case_id = item.get("caseId")
            if not isinstance(case_id, str) or not case_id:
                continue
            source_path = item.get("sourcePath")
            duplicate_paths = item.get("duplicatePaths") if isinstance(item.get("duplicatePaths"), list) else []
            manifest_paths = [source_path, *duplicate_paths]
            path_match = any(
                isinstance(value, str) and Path(value).expanduser().resolve() == input_path
                for value in manifest_paths
            )
            sha_match = item.get("sha256") == input_sha
            if path_match or sha_match:
                candidates.append(root / case_id)

    direct = root / page_input.id
    if direct.exists():
        candidates.append(direct)
    for child in sorted(root.iterdir()):
        if child.is_dir() and child.name.endswith(page_input.path.stem):
            candidates.append(child)

    for candidate in candidates:
        if (candidate / "layer_stack.v1.json").exists():
            return candidate
    if candidates:
        raise FileNotFoundError(f"Matched PSD-like artifact has no layer_stack.v1.json: {candidates[0]}")
    raise FileNotFoundError(f"No PSD-like artifact found for {page_input.path} in {root}")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_modes(mode: str) -> list[str]:
    if mode == "all":
        return list(EXPORT_MODES)
    if mode not in EXPORT_MODES:
        raise ValueError(f"unsupported mode: {mode}")
    return [mode]


def compute_layout(page_results: list[PageExportResult], columns: str) -> dict[str, Any]:
    if columns != "auto":
        parsed = max(1, int(columns))
    else:
        web_like = any(width / max(1, height) >= 0.85 for width, height in (item.source_size for item in page_results))
        parsed = 2 if web_like else 5
    gap = 120
    positions: dict[str, dict[str, int]] = {}
    col_widths = [0] * parsed
    row_heights: list[int] = []
    for index, result in enumerate(page_results):
        col = index % parsed
        row = index // parsed
        width, height = result.source_size
        if row >= len(row_heights):
            row_heights.append(0)
        col_widths[col] = max(col_widths[col], width)
        row_heights[row] = max(row_heights[row], height)
    x_offsets: list[int] = []
    current_x = 0
    for width in col_widths:
        x_offsets.append(current_x)
        current_x += width + gap
    y_offsets: list[int] = []
    current_y = 0
    for height in row_heights:
        y_offsets.append(current_y)
        current_y += height + gap
    for index, result in enumerate(page_results):
        col = index % parsed
        row = index // parsed
        positions[result.page_namespace] = {"x": x_offsets[col], "y": y_offsets[row]}
    return {"columns": parsed, "gap": gap, "positions": positions}


def build_mode_project(
    *,
    mode: str,
    request: ExportRequest,
    page_results: list[PageExportResult],
    layout: dict[str, Any],
) -> dict[str, Any]:
    mode_root = request.out_dir / mode
    assets_root = mode_root / "assets" / "visible"
    frames: list[dict[str, Any]] = []
    mode_assets: list[dict[str, Any]] = []
    for result in page_results:
        single_mode_dir = result.single_export_dir / mode_dir_name(mode)
        single_doc = read_json(single_mode_dir / "design.pen")
        frame = dict(single_doc["children"][0])
        namespace = result.page_namespace
        position = layout["positions"][namespace]
        frame["id"] = f"{namespace}__frame"
        frame["name"] = f"{request.project_name} {namespace}"
        frame["x"] = position["x"]
        frame["y"] = position["y"]
        frame["metadata"] = {
            **(frame.get("metadata") or {}),
            "pageNamespace": namespace,
            "originalName": result.input.original_name,
            "exportMode": mode,
        }
        page_asset_dir = assets_root / namespace
        asset_prefix = f"{safe_slug(mode, 'mode')}__{namespace}"
        rewritten_assets = rewrite_children(frame.get("children") or [], namespace, asset_prefix, single_mode_dir, page_asset_dir)
        frames.append(frame)
        rewritten_asset_by_original_url = {
            item["originalUrl"]: item["url"]
            for item in rewritten_assets
        }
        for asset in result.mode_manifests[mode].get("assets", []):
            updated_asset = {"page": namespace, **asset}
            original_url = asset.get("url")
            if isinstance(original_url, str) and original_url in rewritten_asset_by_original_url:
                updated_asset["url"] = rewritten_asset_by_original_url[original_url]
            mode_assets.append(updated_asset)

    document = {
        "version": "2.11",
        "children": frames,
    }
    validate_project_pen_contract(document, mode_root)
    write_json(mode_root / "design.pen", document)
    write_json(mode_root / "manifest.json", {"mode": mode, "pageCount": len(frames), "assets": mode_assets})
    return {
        "mode": mode,
        "designPen": f"{mode}/design.pen",
        "manifest": f"{mode}/manifest.json",
        "frameCount": len(frames),
        "assetCount": len(mode_assets),
    }


def validate_project_pen_contract(document: dict[str, Any], mode_root: Path) -> None:
    ids: set[str] = set()
    image_urls_by_basename: dict[str, str] = {}

    def visit(node: dict[str, Any]) -> None:
        node_id = node.get("id")
        if isinstance(node_id, str):
            if node_id in ids:
                raise ValueError(f"duplicate .pen node id: {node_id}")
            ids.add(node_id)

        if "strokeWidth" in node:
            raise ValueError(f"Pencil contract violation: strokeWidth on node {node_id}")
        stroke = node.get("stroke")
        if stroke is not None and not is_valid_pencil_stroke(stroke):
            raise ValueError(f"Pencil contract violation: invalid stroke on node {node_id}")

        fill = node.get("fill")
        if isinstance(fill, dict) and fill.get("type") == "image":
            validate_project_image_fill(fill, mode_root, image_urls_by_basename, node_id)

        for child in node.get("children") or []:
            if isinstance(child, dict):
                visit(child)

    for child in document.get("children") or []:
        if isinstance(child, dict):
            visit(child)


def is_valid_pencil_stroke(stroke: Any) -> bool:
    if not isinstance(stroke, dict):
        return False
    if "fill" not in stroke or "thickness" not in stroke:
        return False
    thickness = stroke.get("thickness")
    if isinstance(thickness, dict):
        return all(isinstance(value, int | float) for value in thickness.values())
    return isinstance(thickness, int | float)


def validate_project_image_fill(
    fill: dict[str, Any],
    mode_root: Path,
    image_urls_by_basename: dict[str, str],
    node_id: Any,
) -> None:
    url = fill.get("url")
    if fill.get("enabled") is not True:
        raise ValueError(f"Pencil contract violation: image fill must set enabled=true on node {node_id}")
    if not isinstance(url, str) or not url:
        raise ValueError(f"Pencil contract violation: missing image url on node {node_id}")
    if "://" in url or url.startswith("/"):
        raise ValueError(f"Pencil contract violation: non-portable image url {url!r} on node {node_id}")
    if url.startswith("../") or "/../" in url:
        raise ValueError(f"Pencil contract violation: escaping image url {url!r} on node {node_id}")
    forbidden_fragments = ("source.png", "raw-crops", "masks/", "debug/")
    if any(fragment in url for fragment in forbidden_fragments):
        raise ValueError(f"Pencil contract violation: debug/raw image url {url!r} on node {node_id}")
    if not url.startswith("./assets/visible/"):
        raise ValueError(f"Pencil contract violation: image url outside visible assets {url!r} on node {node_id}")

    basename = Path(url).name
    previous_url = image_urls_by_basename.get(basename)
    if previous_url is not None and previous_url != url:
        raise ValueError(f"Pencil contract violation: duplicate visible asset basename {basename!r}")
    image_urls_by_basename[basename] = url

    image_path = mode_root / url.removeprefix("./")
    if not image_path.exists():
        raise ValueError(f"Pencil contract violation: missing visible asset {url!r} on node {node_id}")


def rewrite_children(
    children: list[dict[str, Any]],
    namespace: str,
    asset_prefix: str,
    single_mode_dir: Path,
    page_asset_dir: Path,
) -> list[dict[str, str]]:
    rewritten_assets: list[dict[str, str]] = []
    for child in children:
        child["id"] = f"{namespace}__{child['id']}"
        metadata = child.get("metadata") or {}
        child["metadata"] = namespace_metadata(metadata, namespace)
        fill = child.get("fill")
        if isinstance(fill, dict) and fill.get("type") == "image" and isinstance(fill.get("url"), str):
            source_rel = fill["url"].removeprefix("./")
            source_path = single_mode_dir / source_rel
            if source_path.exists():
                page_asset_dir.mkdir(parents=True, exist_ok=True)
                target_name = f"{asset_prefix}__{source_path.name}"
                target_path = page_asset_dir / target_name
                shutil.copy2(source_path, target_path)
                original_url = fill["url"]
                fill["url"] = f"./assets/visible/{namespace}/{target_name}"
                fill["enabled"] = True
                rewritten_assets.append({"originalUrl": original_url, "url": fill["url"]})
        if isinstance(child.get("children"), list):
            rewritten_assets.extend(rewrite_children(child["children"], namespace, asset_prefix, single_mode_dir, page_asset_dir))
    return rewritten_assets


def namespace_metadata(metadata: dict[str, Any], namespace: str) -> dict[str, Any]:
    updated = {**metadata, "pageNamespace": namespace}
    for key in ("primitiveId", "sourcePrimitiveId"):
        value = updated.get(key)
        if isinstance(value, str) and value:
            updated[f"page{key[0].upper()}{key[1:]}"] = f"{namespace}__{value}"
    return updated


def copy_page_debug(m29_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "m29_physical_evidence.v1.json",
        "m29-pencil-replay.v1.json",
        "ocr.json",
        "debug_overlay.png",
        "preview_sheet.png",
        "m29extract.stdout.txt",
        "m29extract.stderr.txt",
        "source.png",
    ):
        source = m29_dir / name
        if source.exists():
            shutil.copy2(source, target_dir / name)
    for dirname in ("crops", "masks"):
        source_dir = m29_dir / dirname
        if source_dir.exists():
            shutil.copytree(source_dir, target_dir / dirname, dirs_exist_ok=True)
    psdlike_debug = m29_dir / "psdlike_debug"
    if psdlike_debug.exists():
        shutil.copytree(psdlike_debug, target_dir / "psdlike_debug", dirs_exist_ok=True)


def build_project_manifest(
    request: ExportRequest,
    page_results: list[PageExportResult],
    modes: list[str],
    layout: dict[str, Any],
    mode_results: dict[str, Any],
) -> dict[str, Any]:
    pages = []
    for result in page_results:
        pages.append(
            {
                "namespace": result.page_namespace,
                "id": result.input.id,
                "originalName": result.input.original_name,
                "width": result.source_size[0],
                "height": result.source_size[1],
                "boundarySource": result.boundary_source,
                "modes": {
                    mode: {
                        "textNodes": result.mode_manifests[mode].get("textNodes", 0),
                        "cropNodes": result.mode_manifests[mode].get("cropNodes", 0),
                        "cropTextNodes": result.mode_manifests[mode].get("cropTextNodes", 0),
                        "visualTextCropNodes": result.mode_manifests[mode].get("visualTextCropNodes", 0),
                        "textKnockoutCropNodes": result.mode_manifests[mode].get("textKnockoutCropNodes", 0),
                        "suppressedInternalCropNodes": result.mode_manifests[mode].get("suppressedInternalCropNodes", 0),
                        "sourceFallbackNodes": result.mode_manifests[mode].get("sourceFallbackNodes", 0),
                    }
                    for mode in modes
                },
            }
        )
    return {
        "schema": "pencil.python.project_manifest.v1",
        "projectName": request.project_name,
        "createdAt": datetime.now(UTC).isoformat(),
        "pageCount": len(page_results),
        "modes": modes,
        "boundarySource": request.boundary_source,
        "psdlikeArtifactsRoot": str(request.psdlike_artifacts_root) if request.psdlike_artifacts_root else None,
        "columns": layout["columns"],
        "includeDebug": request.include_debug,
        "pages": pages,
        "modeResults": mode_results,
        "warnings": [],
    }


def write_debug_report(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Pencil Python Backend Export Report",
        "",
        f"- project: {manifest['projectName']}",
        f"- pages: {manifest['pageCount']}",
        f"- modes: {', '.join(manifest['modes'])}",
        f"- boundary source: {manifest.get('boundarySource', 'm29')}",
        f"- columns: {manifest['columns']}",
        "",
        "## Pages",
        "",
        "| page | original | size | mode | text | text crops | visual text crops | crops | knockout | suppressed | source fallback |",
        "|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for page in manifest["pages"]:
        size = f"{page['width']}x{page['height']}"
        for mode, stats in page["modes"].items():
            lines.append(
                f"| {page['namespace']} | {page['originalName']} | {size} | {mode} | "
                f"{stats['textNodes']} | {stats['cropTextNodes']} | {stats.get('visualTextCropNodes', 0)} | {stats['cropNodes']} | "
                f"{stats['textKnockoutCropNodes']} | {stats['suppressedInternalCropNodes']} | "
                f"{stats.get('sourceFallbackNodes', 0)} |"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def create_project_zip(out_dir: Path) -> Path:
    zip_path = out_dir / "project.zip"
    if zip_path.exists():
        zip_path.unlink()
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for path in sorted(out_dir.rglob("*")):
            if path == zip_path or path.is_dir() or "work" in path.relative_to(out_dir).parts:
                continue
            archive.write(path, path.relative_to(out_dir))
    return zip_path


def discover_inputs(raw_inputs: list[Path], manifest_paths: list[Path]) -> list[PageInput]:
    paths: list[Path] = []
    for manifest_path in manifest_paths:
        data = read_json(manifest_path.expanduser().resolve())
        items = data.get("pages") or data.get("cases") or []
        for item in items:
            raw_path = item.get("path") or item.get("sourcePath")
            if raw_path:
                paths.append(Path(raw_path).expanduser().resolve())
    for raw_input in raw_inputs:
        path = raw_input.expanduser().resolve()
        if path.is_dir():
            paths.extend(sorted(item for item in path.rglob("*") if item.is_file() and item.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}))
        else:
            paths.append(path)
    inputs: list[PageInput] = []
    seen: set[Path] = set()
    for index, path in enumerate(paths, start=1):
        if path in seen:
            continue
        seen.add(path)
        inputs.append(PageInput(id=f"page_{index:04d}_{safe_slug(path.stem)}", path=path, original_name=path.name))
    return inputs
