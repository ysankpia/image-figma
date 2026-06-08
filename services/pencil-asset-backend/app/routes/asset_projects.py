from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from PIL import Image, UnidentifiedImageError

from ..exporter import export_asset_project, write_export_preview
from ..jsonio import read_json, write_json
from ..projects import (
    AssetProjectStorage,
    UploadInput,
    initialize_asset_project,
    project_summary,
    selected_slice_count,
    source_path_for_page,
    validate_manual_slices,
)
from ..state import state
from ..utils import safe_slug
from .pages import REVIEW_HTML, WORKSPACE_HTML


router = APIRouter(prefix="/api/asset-projects")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def storage() -> AssetProjectStorage:
    state.settings.storage_root.mkdir(parents=True, exist_ok=True)
    return AssetProjectStorage(state.settings.storage_root)


@router.post("")
async def create_asset_project(
    request: Request,
    projectName: Annotated[str, Form()] = "Pencil Asset Project",
) -> dict[str, object]:
    if state.settings.yolo_model is None:
        raise HTTPException(status_code=400, detail="YOLO UI model is required: set PENCIL_ASSET_YOLO_MODEL")
    if not state.settings.yolo_model.exists():
        raise HTTPException(status_code=400, detail=f"YOLO UI model not found: {state.settings.yolo_model}")

    form = await request.form()
    files = [item for item in form.getlist("files[]") if hasattr(item, "filename") and hasattr(item, "read")]
    if not files:
        files = [item for item in form.getlist("files") if hasattr(item, "filename") and hasattr(item, "read")]
    if not files:
        raise HTTPException(status_code=400, detail="files[] is required")
    if len(files) > state.settings.max_files:
        raise HTTPException(status_code=413, detail=f"too many files; max is {state.settings.max_files}")

    validated_uploads: list[tuple[str, str, bytes]] = []
    for index, upload in enumerate(files, start=1):
        original = upload.filename or f"page_{index:04d}.png"
        suffix = Path(original).suffix.lower()
        if suffix not in IMAGE_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"unsupported image type: {original}")
        data = await upload.read()
        if len(data) > state.settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail=f"{original} exceeds max upload bytes")
        try:
            with Image.open(BytesIO(data)) as image:
                image.verify()
        except (OSError, UnidentifiedImageError) as error:
            raise HTTPException(status_code=400, detail=f"invalid image: {original}") from error
        validated_uploads.append((original, suffix, data))

    store = storage()
    paths = store.create_project(projectName)
    try:
        inputs: list[UploadInput] = []
        for index, (original, suffix, data) in enumerate(validated_uploads, start=1):
            upload_name = f"page_{index:04d}_{safe_slug(Path(original).stem, 'source')}{suffix}"
            target = paths.uploads / upload_name
            target.write_bytes(data)
            inputs.append(UploadInput(page_id=f"page_{index:04d}", original_name=original, source_path=target))

        project = initialize_asset_project(paths=paths, inputs=inputs, project_name=projectName, settings=state.settings)
        store.patch_project(paths, **project)
        return {"success": True, "data": project_summary(paths)}
    except HTTPException:
        raise
    except Exception as error:
        store.patch_project(paths, status="failed", error=str(error))
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.get("")
def list_asset_projects() -> dict[str, object]:
    return {"success": True, "data": {"projects": storage().list_projects()}}


@router.get("/workspace")
def workspace_page() -> HTMLResponse:
    return HTMLResponse(WORKSPACE_HTML)


@router.get("/{project_id}")
def get_asset_project(project_id: str) -> dict[str, object]:
    paths = existing_paths(project_id)
    return {"success": True, "data": project_summary(paths)}


@router.get("/{project_id}/review")
def review_page(project_id: str) -> HTMLResponse:
    existing_paths(project_id)
    return HTMLResponse(REVIEW_HTML.replace("__PROJECT_ID__", safe_slug(project_id, "asset_project")))


@router.get("/{project_id}/source/{page_id}")
def get_source(project_id: str, page_id: str) -> FileResponse:
    paths = existing_paths(project_id)
    source = source_path_for_page(paths, page_id)
    return FileResponse(source, media_type="image/png", filename=f"{page_id}.png")


@router.get("/{project_id}/evidence")
def get_evidence(project_id: str) -> dict[str, object]:
    paths = existing_paths(project_id)
    project = read_json(paths.project_json)
    pages = []
    for page in project.get("pages") or []:
        page_id = str(page["pageId"])
        evidence_path = paths.evidence / page_id / "evidence.v1.json"
        pages.append(
            {
                "pageId": page_id,
                "evidence": read_json(evidence_path) if evidence_path.exists() else None,
            }
        )
    return {"success": True, "data": {"schema": "pencil_asset.evidence_bundle.v1", "projectId": paths.project_id, "pages": pages}}


@router.get("/{project_id}/candidates")
def get_candidates(project_id: str) -> dict[str, object]:
    paths = existing_paths(project_id)
    return {"success": True, "data": read_json(paths.candidates_json)}


@router.get("/{project_id}/manual-slices")
def get_manual_slices(project_id: str) -> dict[str, object]:
    paths = existing_paths(project_id)
    return {"success": True, "data": read_json(paths.manual_slices_json)}


@router.put("/{project_id}/manual-slices")
async def put_manual_slices(project_id: str, request: Request) -> dict[str, object]:
    paths = existing_paths(project_id)
    payload = await request.json()
    try:
        manual = validate_manual_slices(payload, read_json(paths.candidates_json))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    write_json(paths.manual_slices_json, manual)
    selected = selected_slice_count(manual)
    storage().patch_project(paths, manualSlicesConfirmed=True, selectedSliceCount=selected, selectedAssetCount=selected)
    return {"success": True, "data": {"selectedSliceCount": selected, "manualSlices": manual}}


@router.post("/{project_id}/export-preview")
def create_export_preview(project_id: str) -> dict[str, object]:
    paths = existing_paths(project_id)
    manual = validated_existing_manual(paths)
    if selected_slice_count(manual) == 0:
        raise HTTPException(status_code=409, detail="no selected image/icon slices to preview")
    manifest = write_export_preview(paths=paths, manual_slices=manual)
    storage().patch_project(paths, exportPreviewPath=str(paths.output / "export-preview" / "manifest.json"))
    return {"success": True, "data": manifest}


@router.get("/{project_id}/export-preview/{filename}")
def get_export_preview_file(project_id: str, filename: str) -> FileResponse:
    paths = existing_paths(project_id)
    safe_name = safe_slug(filename, "index_html")
    allowed = {
        "index_html": ("index.html", "text/html"),
        "contact-sheet_png": ("contact-sheet.png", "image/png"),
        "manifest_json": ("manifest.json", "application/json"),
    }
    if safe_name not in allowed:
        raise HTTPException(status_code=404, detail="preview file not found")
    relative, media = allowed[safe_name]
    path = paths.output / "export-preview" / relative
    if not path.exists():
        raise HTTPException(status_code=404, detail="preview file not found")
    return FileResponse(path, media_type=media, filename=relative)


@router.post("/{project_id}/export")
def export_project(project_id: str) -> dict[str, object]:
    paths = existing_paths(project_id)
    manual = validated_existing_manual(paths)
    if selected_slice_count(manual) == 0:
        raise HTTPException(status_code=409, detail="no selected image/icon slices to export")
    try:
        manifest = export_asset_project(paths=paths, manual_slices=manual)
    except Exception as error:
        storage().patch_project(paths, status="failed", error=str(error))
        raise HTTPException(status_code=500, detail=str(error)) from error
    storage().patch_project(
        paths,
        status="exported",
        manifestPath=str(paths.output / "manifest.json"),
        zipPath=str(paths.output / "project.zip"),
        selectedAssetsZipPath=str(paths.output / "selected-assets.zip"),
        downloadUrl=f"/api/asset-projects/{project_id}/download.zip",
        selectedAssetsDownloadUrl=f"/api/asset-projects/{project_id}/selected-assets.zip",
        selectedAssetCount=manifest["selectedAssetCount"],
    )
    return {"success": True, "data": manifest}


@router.get("/{project_id}/download.zip")
def download_project_zip(project_id: str) -> FileResponse:
    paths = existing_paths(project_id)
    zip_path = paths.output / "project.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=409, detail="project has not been exported")
    return FileResponse(zip_path, media_type="application/zip", filename="project.zip")


@router.get("/{project_id}/selected-assets.zip")
def download_selected_assets_zip(project_id: str) -> FileResponse:
    paths = existing_paths(project_id)
    zip_path = paths.output / "selected-assets.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=409, detail="project has not been exported")
    return FileResponse(zip_path, media_type="application/zip", filename="selected-assets.zip")


def existing_paths(project_id: str):
    paths = storage().paths(project_id)
    if not paths.project_json.exists():
        raise HTTPException(status_code=404, detail="asset project not found")
    return paths


def validated_existing_manual(paths) -> dict[str, Any]:
    if not paths.manual_slices_json.exists():
        raise HTTPException(status_code=409, detail="manual_slices.v1.json not found")
    try:
        return validate_manual_slices(read_json(paths.manual_slices_json), read_json(paths.candidates_json))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
