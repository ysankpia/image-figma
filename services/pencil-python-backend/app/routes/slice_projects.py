from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from PIL import Image, UnidentifiedImageError

from ..config import parse_boundary_source
from ..jsonio import read_json, write_json
from ..slice_projects import (
    SliceProjectStorage,
    ensure_review_state,
    export_manual_slice_project,
    initialize_slice_project,
    project_summary,
    selected_slice_count,
    validate_manual_slices,
    validate_review_state,
    write_export_preview,
)
from ..state import state
from ..types import IMAGE_EXTENSIONS, PageInput
from ..utils import safe_slug
from .slice_project_pages import NEW_PROJECT_HTML, REVIEW_HTML, WORKSPACE_HTML


router = APIRouter(prefix="/api/pencil/slice-projects")


@router.post("")
async def create_slice_project(
    request: Request,
    projectName: Annotated[str, Form()] = "Assisted Slice Project",
    includeDebug: Annotated[bool, Form()] = True,
    ocrProvider: Annotated[str | None, Form()] = None,
    boundarySource: Annotated[str | None, Form()] = None,
) -> dict[str, object]:
    try:
        selected_boundary_source = (
            parse_boundary_source(boundarySource) if boundarySource else state.settings.default_boundary_source
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    form = await request.form()
    files = [item for item in form.getlist("files[]") if hasattr(item, "filename") and hasattr(item, "read")]
    if not files:
        files = [item for item in form.getlist("files") if hasattr(item, "filename") and hasattr(item, "read")]
    if not files:
        raise HTTPException(status_code=400, detail="files[] is required")
    if len(files) > state.settings.max_files:
        raise HTTPException(status_code=413, detail=f"too many files; max is {state.settings.max_files}")

    storage = SliceProjectStorage(state.storage)
    paths = storage.create_project(projectName)
    inputs: list[PageInput] = []
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
        filename = f"page_{index:04d}_{safe_slug(Path(original).stem)}{suffix}"
        target = paths.uploads / filename
        target.write_bytes(data)
        inputs.append(PageInput(id=f"page_{index:04d}", path=target, original_name=original))

    try:
        project = initialize_slice_project(
            paths=paths,
            inputs=inputs,
            project_name=projectName,
            boundary_source=selected_boundary_source,
            include_debug=includeDebug,
            ocr_provider=ocrProvider,
            settings=state.settings,
        )
        storage.patch_project(
            paths,
            status="ready",
            boundarySource=selected_boundary_source,
            includeDebug=includeDebug,
            pageCount=len(inputs),
            pages=project["pages"],
            candidatesPath=str(paths.candidates_json),
            manualSlicesPath=str(paths.manual_slices_json),
            manualSlicesConfirmed=False,
            selectedSliceCount=0,
            reviewUrl=f"/api/pencil/slice-projects/{paths.project_id}/review",
        )
    except Exception as error:
        storage.patch_project(paths, status="failed", error=str(error))
        raise HTTPException(status_code=500, detail=str(error)) from error

    return {
        "success": True,
        "data": {
            **public_project(project),
            "status": "ready",
            "boundarySource": selected_boundary_source,
            "manualSlicesConfirmed": False,
            "selectedSliceCount": 0,
            "reviewUrl": f"/api/pencil/slice-projects/{paths.project_id}/review",
        },
    }


@router.get("/new")
def new_slice_project_page() -> HTMLResponse:
    return HTMLResponse(NEW_PROJECT_HTML)


@router.get("/workspace")
def workspace_page() -> HTMLResponse:
    return HTMLResponse(WORKSPACE_HTML)


@router.get("")
def list_slice_projects() -> dict[str, object]:
    storage = SliceProjectStorage(state.storage)
    projects = storage.list_projects()
    return {"success": True, "data": {"projects": projects, "projectCount": len(projects)}}


@router.get("/{project_id}")
def get_slice_project(project_id: str) -> dict[str, object]:
    storage = SliceProjectStorage(state.storage)
    try:
        paths = storage.paths(project_id)
        if not paths.project_json.exists():
            raise FileNotFoundError(project_id)
        project = project_summary(paths)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="slice project not found") from error
    return {"success": True, "data": public_project(project)}


@router.put("/{project_id}")
async def update_slice_project(project_id: str, request: Request) -> dict[str, object]:
    storage = SliceProjectStorage(state.storage)
    try:
        payload = await request.json()
        project_name = str(payload.get("projectName") or "").strip()
        if not project_name:
            raise HTTPException(status_code=400, detail="projectName is required")
        paths = storage.paths(project_id)
        storage.rename_project(project_id, project_name)
        return {"success": True, "data": public_project(project_summary(paths))}
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="slice project not found") from error


@router.post("/{project_id}/clone")
def clone_slice_project(project_id: str) -> dict[str, object]:
    storage = SliceProjectStorage(state.storage)
    try:
        clone_paths = storage.clone_project(project_id)
        return {"success": True, "data": public_project(project_summary(clone_paths))}
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="slice project not found") from error


@router.delete("/{project_id}")
def delete_slice_project(project_id: str) -> dict[str, object]:
    storage = SliceProjectStorage(state.storage)
    try:
        storage.delete_project(project_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="slice project not found") from error
    return {"success": True, "data": {"projectId": safe_slug(project_id, "slice_project"), "deleted": True}}


@router.get("/{project_id}/review")
def review_page(project_id: str) -> HTMLResponse:
    storage = SliceProjectStorage(state.storage)
    try:
        storage.read_project(project_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="slice project not found") from error
    return HTMLResponse(REVIEW_HTML.replace("__PROJECT_ID__", project_id))


@router.get("/{project_id}/candidates")
def get_candidates(project_id: str) -> dict[str, object]:
    paths = SliceProjectStorage(state.storage).paths(project_id)
    if not paths.candidates_json.exists():
        raise HTTPException(status_code=404, detail="candidates not found")
    return {"success": True, "data": read_json(paths.candidates_json)}


@router.get("/{project_id}/source/{page_id}")
def get_source_image(project_id: str, page_id: str) -> FileResponse:
    paths = SliceProjectStorage(state.storage).paths(project_id)
    source = paths.pages / safe_slug(page_id, "page") / "source.png"
    if not source.exists():
        raise HTTPException(status_code=404, detail="source image not found")
    return FileResponse(source, media_type="image/png")


@router.get("/{project_id}/manual-slices")
def get_manual_slices(project_id: str) -> dict[str, object]:
    paths = SliceProjectStorage(state.storage).paths(project_id)
    if not paths.manual_slices_json.exists():
        raise HTTPException(status_code=404, detail="manual slices not found")
    return {"success": True, "data": read_json(paths.manual_slices_json)}


@router.get("/{project_id}/review-state")
def get_review_state(project_id: str) -> dict[str, object]:
    paths = SliceProjectStorage(state.storage).paths(project_id)
    if not paths.project_json.exists():
        raise HTTPException(status_code=404, detail="slice project not found")
    try:
        review_state = ensure_review_state(paths)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"success": True, "data": review_state}


@router.put("/{project_id}/review-state")
async def put_review_state(project_id: str, request: Request) -> dict[str, object]:
    storage = SliceProjectStorage(state.storage)
    paths = storage.paths(project_id)
    if not paths.project_json.exists():
        raise HTTPException(status_code=404, detail="slice project not found")
    try:
        payload = await request.json()
        review_state = validate_review_state(payload, read_json(paths.candidates_json))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    write_json(paths.review_state_json, review_state)
    rejected = sum(len(page.get("rejectedCandidateIds") or []) for page in review_state.get("pages") or [])
    storage.patch_project(paths, reviewStatePath=str(paths.review_state_json), rejectedCandidateCount=rejected)
    return {"success": True, "data": {"projectId": paths.project_id, "rejectedCandidateCount": rejected}}


@router.put("/{project_id}/manual-slices")
async def put_manual_slices(project_id: str, request: Request) -> dict[str, object]:
    storage = SliceProjectStorage(state.storage)
    paths = storage.paths(project_id)
    if not paths.project_json.exists():
        raise HTTPException(status_code=404, detail="slice project not found")
    try:
        payload = await request.json()
        manual_slices = validate_manual_slices(payload, read_json(paths.candidates_json))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    write_json(paths.manual_slices_json, manual_slices)
    selected = selected_slice_count(manual_slices)
    storage.patch_project(paths, status="ready", manualSlicesConfirmed=True, selectedSliceCount=selected)
    return {"success": True, "data": {"projectId": paths.project_id, "selectedSliceCount": selected}}


@router.post("/{project_id}/export")
def export_slice_project(project_id: str) -> dict[str, object]:
    storage = SliceProjectStorage(state.storage)
    paths = storage.paths(project_id)
    if not paths.project_json.exists():
        raise HTTPException(status_code=404, detail="slice project not found")
    project = storage.read_project(project_id)
    if project.get("manualSlicesConfirmed") is not True:
        raise HTTPException(status_code=409, detail="manual slices must be saved before export")
    if not paths.manual_slices_json.exists():
        raise HTTPException(status_code=409, detail="manual slices are required before export")
    try:
        manual_slices = validate_manual_slices(read_json(paths.manual_slices_json), read_json(paths.candidates_json))
        if selected_slice_count(manual_slices) == 0:
            raise HTTPException(status_code=409, detail="no selected slices to export")
        manifest = export_manual_slice_project(
            paths=paths,
            manual_slices=manual_slices,
            include_debug=bool(project.get("includeDebug", True)),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    storage.patch_project(
        paths,
        status="completed",
        manifestPath=str(paths.output / "manifest.json"),
        zipPath=str(paths.output / "project.zip"),
        selectedAssetsZipPath=str(paths.output / "selected-assets.zip"),
        downloadUrl=f"/api/pencil/slice-projects/{paths.project_id}/download.zip",
        selectedAssetsDownloadUrl=f"/api/pencil/slice-projects/{paths.project_id}/selected-assets.zip",
        selectedAssetCount=manifest["selectedAssetCount"],
    )
    return {"success": True, "data": manifest}


@router.post("/{project_id}/export-preview")
def export_preview(project_id: str) -> dict[str, object]:
    storage = SliceProjectStorage(state.storage)
    paths = storage.paths(project_id)
    if not paths.project_json.exists():
        raise HTTPException(status_code=404, detail="slice project not found")
    if not paths.manual_slices_json.exists():
        raise HTTPException(status_code=409, detail="manual slices are required before export preview")
    try:
        manual_slices = validate_manual_slices(read_json(paths.manual_slices_json), read_json(paths.candidates_json))
        if selected_slice_count(manual_slices) == 0:
            raise HTTPException(status_code=409, detail="no selected slices to preview")
        manifest = write_export_preview(paths=paths, manual_slices=manual_slices)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    storage.patch_project(paths, exportPreviewPath=str(paths.output / "export-preview" / "manifest.json"))
    return {"success": True, "data": manifest}


@router.get("/{project_id}/export-preview/{name}")
def get_export_preview_file(project_id: str, name: str) -> FileResponse:
    paths = SliceProjectStorage(state.storage).paths(project_id)
    requested = Path(name).name
    if requested not in {"contact-sheet.png", "index.html"}:
        raise HTTPException(status_code=404, detail="export preview file not found")
    safe_name = requested
    target = paths.output / "export-preview" / safe_name
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="export preview file not found")
    if target.suffix.lower() == ".png":
        return FileResponse(target, media_type="image/png")
    if target.suffix.lower() == ".html":
        return FileResponse(target, media_type="text/html")
    raise HTTPException(status_code=404, detail="export preview file not found")


@router.get("/{project_id}/download.zip")
def download_zip(project_id: str) -> FileResponse:
    storage = SliceProjectStorage(state.storage)
    try:
        project = storage.read_project(project_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="slice project not found") from error
    if project.get("status") != "completed":
        raise HTTPException(status_code=409, detail="slice project is not exported")
    zip_path = Path(str(project.get("zipPath") or ""))
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="zip not found")
    return FileResponse(zip_path, media_type="application/zip", filename="project.zip")


@router.get("/{project_id}/selected-assets.zip")
def download_selected_assets_zip(project_id: str) -> FileResponse:
    storage = SliceProjectStorage(state.storage)
    try:
        project = storage.read_project(project_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="slice project not found") from error
    if project.get("status") != "completed":
        raise HTTPException(status_code=409, detail="slice project is not exported")
    zip_path = Path(str(project.get("selectedAssetsZipPath") or ""))
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="selected assets zip not found")
    return FileResponse(zip_path, media_type="application/zip", filename="selected-assets.zip")


def public_project(project: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "projectId",
        "status",
        "projectName",
        "pageCount",
        "pages",
        "boundarySource",
        "includeDebug",
        "reviewUrl",
        "downloadUrl",
        "selectedSliceCount",
        "selectedAssetCount",
        "candidateCount",
        "rejectedCandidateCount",
        "completedPageCount",
        "exported",
        "manualSlicesConfirmed",
        "thumbnailUrl",
        "workspaceUrl",
        "selectedAssetsDownloadUrl",
        "error",
        "warnings",
        "createdAt",
        "updatedAt",
    ]
    return {key: project[key] for key in keys if key in project}
