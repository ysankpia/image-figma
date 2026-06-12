from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from PIL import Image, UnidentifiedImageError

from ..exporter import export_handoff_project, write_export_preview
from ..jsonio import read_json, write_json
from ..projects import (
    ProjectStorage,
    UploadInput,
    ensure_review_state,
    initialize_project,
    project_summary,
    selected_slice_count,
    source_path_for_page,
    validate_manual_slices,
    validate_review_state,
)
from ..state import state
from ..utils import safe_slug


router = APIRouter(prefix="/api/handoff-projects")
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def storage() -> ProjectStorage:
    state.settings.storage_root.mkdir(parents=True, exist_ok=True)
    return ProjectStorage(state.settings.storage_root)


@router.post("")
async def create_handoff_project(
    request: Request,
    projectName: Annotated[str, Form()] = "Pencil Handoff Project",
    includeOcr: Annotated[bool, Form()] = True,
    includeBasicElements: Annotated[bool, Form()] = True,
) -> dict[str, object]:
    form = await request.form()
    files = [item for item in form.getlist("files[]") if hasattr(item, "filename") and hasattr(item, "read")]
    if not files:
        files = [item for item in form.getlist("files") if hasattr(item, "filename") and hasattr(item, "read")]
    if not files:
        raise HTTPException(status_code=400, detail="files[] is required")
    if state.settings.max_files > 0 and len(files) > state.settings.max_files:
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
            inputs.append(UploadInput(original_name=original, source_path=target))
        project = initialize_project(
            paths=paths,
            inputs=inputs,
            project_name=projectName,
            settings=state.settings,
            include_ocr=includeOcr,
            include_basic_elements=includeBasicElements,
        )
        store.patch_project(paths, **project)
        return {"success": True, "data": project_summary(paths)}
    except HTTPException:
        raise
    except Exception as error:
        store.patch_project(paths, status="failed", error=str(error))
        raise HTTPException(status_code=500, detail=str(error)) from error


@router.get("")
def list_handoff_projects() -> dict[str, object]:
    return {"success": True, "data": {"projects": storage().list_projects()}}


@router.get("/workspace")
def workspace_page():
    if (Path(__file__).resolve().parents[2] / "web" / "dist" / "index.html").exists():
        return RedirectResponse("/studio/")
    return HTMLResponse(FALLBACK_WORKSPACE_HTML)


@router.get("/{project_id}")
def get_handoff_project(project_id: str) -> dict[str, object]:
    return {"success": True, "data": project_summary(existing_paths(project_id))}


@router.delete("/{project_id}")
def delete_handoff_project(project_id: str) -> dict[str, object]:
    existing_paths(project_id)
    storage().delete_project(project_id)
    return {"success": True, "data": {"projectId": safe_slug(project_id, "handoff_project"), "deleted": True}}


@router.get("/{project_id}/review")
def review_page(project_id: str):
    existing_paths(project_id)
    if (Path(__file__).resolve().parents[2] / "web" / "dist" / "index.html").exists():
        return RedirectResponse(f"/studio/?projectId={safe_slug(project_id, 'handoff_project')}")
    return HTMLResponse(FALLBACK_WORKSPACE_HTML.replace("__PROJECT_ID__", safe_slug(project_id, "handoff_project")))


@router.get("/{project_id}/source/{page_id}")
def get_source(project_id: str, page_id: str) -> FileResponse:
    try:
        source = source_path_for_page(existing_paths(project_id), page_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="source page not found") from error
    return FileResponse(source, media_type="image/png", filename=f"{page_id}.png")


@router.get("/{project_id}/candidates")
def get_candidates(project_id: str) -> dict[str, object]:
    return {"success": True, "data": read_json(existing_paths(project_id).candidates_json)}


@router.get("/{project_id}/review-state")
def get_review_state(project_id: str) -> dict[str, object]:
    return {"success": True, "data": ensure_review_state(existing_paths(project_id))}


@router.put("/{project_id}/review-state")
async def put_review_state(project_id: str, request: Request) -> dict[str, object]:
    paths = existing_paths(project_id)
    payload = await request.json()
    try:
        review_state = validate_review_state(payload, read_json(paths.candidates_json))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    write_json(paths.review_state_json, review_state)
    hidden = sum(len(page.get("hiddenCandidateIds") or []) for page in review_state.get("pages") or [])
    storage().patch_project(paths, reviewStatePath=str(paths.review_state_json), hiddenCandidateCount=hidden)
    return {"success": True, "data": {"projectId": paths.project_id, "hiddenCandidateCount": hidden, "reviewState": review_state}}


@router.get("/{project_id}/manual-slices")
def get_manual_slices(project_id: str) -> dict[str, object]:
    return {"success": True, "data": read_json(existing_paths(project_id).manual_slices_json)}


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
    storage().patch_project(paths, manualSlicesConfirmed=True, selectedSliceCount=selected)
    return {"success": True, "data": {"selectedSliceCount": selected, "manualSlices": manual}}


@router.post("/{project_id}/export-preview")
def create_export_preview(project_id: str) -> dict[str, object]:
    paths = existing_paths(project_id)
    manual = validated_existing_manual(paths)
    if selected_slice_count(manual) == 0:
        raise HTTPException(status_code=409, detail="no selected slices to preview")
    manifest = write_export_preview(paths=paths, manual_slices=manual)
    storage().patch_project(paths, exportPreviewPath=str(paths.output / "export-preview" / "manifest.json"))
    return {"success": True, "data": manifest}


@router.get("/{project_id}/export-preview/{filename}")
def get_export_preview_file(project_id: str, filename: str) -> FileResponse:
    paths = existing_paths(project_id)
    allowed = {
        "index.html": ("index.html", "text/html"),
        "contact-sheet.png": ("contact-sheet.png", "image/png"),
        "manifest.json": ("manifest.json", "application/json"),
    }
    if filename not in allowed:
        raise HTTPException(status_code=404, detail="preview file not found")
    relative, media = allowed[filename]
    path = paths.output / "export-preview" / relative
    if not path.exists():
        raise HTTPException(status_code=404, detail="preview file not found")
    return FileResponse(path, media_type=media, filename=relative)


@router.post("/{project_id}/export")
def export_project(project_id: str) -> dict[str, object]:
    paths = existing_paths(project_id)
    manual = validated_existing_manual(paths)
    if selected_slice_count(manual) == 0:
        raise HTTPException(status_code=409, detail="no selected slices to export")
    try:
        manifest = export_handoff_project(paths=paths, manual_slices=manual, review_state=ensure_review_state(paths))
    except Exception as error:
        storage().patch_project(paths, status="failed", error=str(error))
        raise HTTPException(status_code=500, detail=str(error)) from error
    storage().patch_project(
        paths,
        status="exported",
        manifestPath=str(paths.output / "manifest.json"),
        projectZipPath=str(paths.output / "project.zip"),
        assetsZipPath=str(paths.output / "assets.zip"),
        projectZipUrl=f"/api/handoff-projects/{paths.project_id}/project.zip",
        assetsZipUrl=f"/api/handoff-projects/{paths.project_id}/assets.zip",
        selectedSliceCount=manifest["assetCount"],
    )
    return {"success": True, "data": manifest}


@router.get("/{project_id}/project.zip")
def download_project_zip(project_id: str) -> FileResponse:
    zip_path = existing_paths(project_id).output / "project.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=409, detail="project has not been exported")
    return FileResponse(zip_path, media_type="application/zip", filename="project.zip")


@router.get("/{project_id}/assets.zip")
def download_assets_zip(project_id: str) -> FileResponse:
    zip_path = existing_paths(project_id).output / "assets.zip"
    if not zip_path.exists():
        raise HTTPException(status_code=409, detail="project has not been exported")
    return FileResponse(zip_path, media_type="application/zip", filename="assets.zip")


def existing_paths(project_id: str):
    paths = storage().paths(project_id)
    if not paths.project_json.exists():
        raise HTTPException(status_code=404, detail="handoff project not found")
    return paths


def validated_existing_manual(paths) -> dict[str, Any]:
    try:
        return validate_manual_slices(read_json(paths.manual_slices_json), read_json(paths.candidates_json))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


FALLBACK_WORKSPACE_HTML = """<!doctype html>
<html>
  <head><meta charset="utf-8"><title>Pencil Handoff Studio</title></head>
  <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:24px">
    <h1>Pencil Handoff Studio</h1>
    <p>Frontend is not built yet. Run <code>pnpm --filter @image-figma/pencil-handoff-studio-web run build</code>.</p>
    <p>Project: __PROJECT_ID__</p>
  </body>
</html>"""
