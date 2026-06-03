from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse

from ..jsonio import read_json
from ..state import state
from ..types import EXPORT_MODES, IMAGE_EXTENSIONS, PageInput
from ..utils import safe_slug


router = APIRouter(prefix="/api/pencil/projects")


@router.post("")
async def create_project(
    request: Request,
    projectName: Annotated[str, Form()] = "Pencil Project",
    mode: Annotated[str, Form()] = "all",
    columns: Annotated[str, Form()] = "auto",
    includeDebug: Annotated[bool, Form()] = True,
    ocrProvider: Annotated[str | None, Form()] = None,
) -> dict[str, object]:
    if mode != "all" and mode not in EXPORT_MODES:
        raise HTTPException(status_code=400, detail=f"unsupported mode: {mode}")
    if columns != "auto":
        try:
            if int(columns) <= 0:
                raise ValueError
        except ValueError as error:
            raise HTTPException(status_code=400, detail="columns must be auto or a positive integer") from error
    form = await request.form()
    files = [item for item in form.getlist("files[]") if hasattr(item, "filename") and hasattr(item, "read")]
    if not files:
        files = [item for item in form.getlist("files") if hasattr(item, "filename") and hasattr(item, "read")]
    if not files:
        raise HTTPException(status_code=400, detail="files[] is required")
    if len(files) > state.settings.max_files:
        raise HTTPException(status_code=413, detail=f"too many files; max is {state.settings.max_files}")

    paths = state.storage.create_task(projectName)
    inputs: list[PageInput] = []
    for index, upload in enumerate(files, start=1):
        original = upload.filename or f"page_{index:04d}.png"
        suffix = Path(original).suffix.lower()
        if suffix not in IMAGE_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"unsupported image type: {original}")
        data = await upload.read()
        if len(data) > state.settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail=f"{original} exceeds max upload bytes")
        filename = f"page_{index:04d}_{safe_slug(Path(original).stem)}{suffix}"
        target = paths.uploads / filename
        target.write_bytes(data)
        inputs.append(PageInput(id=f"page_{index:04d}", path=target, original_name=original))

    state.storage.patch_status(
        paths,
        projectName=projectName,
        mode=mode,
        columns=columns,
        includeDebug=includeDebug,
        inputCount=len(inputs),
    )
    state.tasks.submit(
        paths=paths,
        inputs=inputs,
        project_name=projectName,
        mode=mode,
        columns=columns,
        include_debug=includeDebug,
        ocr_provider=ocrProvider,
    )
    return {"success": True, "data": {"taskId": paths.task_id, "status": "queued"}}


@router.get("/{task_id}")
def get_project(task_id: str) -> dict[str, object]:
    try:
        status = state.storage.read_status(task_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="task not found") from error
    data = public_status(status)
    return {"success": True, "data": data}


@router.get("/{task_id}/manifest")
def get_manifest(task_id: str) -> dict[str, object]:
    try:
        status = state.storage.read_status(task_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="task not found") from error
    if status.get("status") != "completed":
        raise HTTPException(status_code=409, detail="task is not completed")
    manifest_path = Path(str(status.get("manifestPath") or ""))
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="manifest not found")
    return {"success": True, "data": read_json(manifest_path)}


@router.get("/{task_id}/download.zip")
def download_zip(task_id: str) -> FileResponse:
    try:
        status = state.storage.read_status(task_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="task not found") from error
    if status.get("status") != "completed":
        raise HTTPException(status_code=409, detail="task is not completed")
    zip_path = Path(str(status.get("zipPath") or ""))
    if not zip_path.exists():
        raise HTTPException(status_code=404, detail="zip not found")
    return FileResponse(zip_path, media_type="application/zip", filename="project.zip")


def public_status(status: dict[str, object]) -> dict[str, object]:
    keys = [
        "taskId",
        "status",
        "projectName",
        "pageCount",
        "modes",
        "downloadUrl",
        "warnings",
        "error",
        "createdAt",
        "updatedAt",
    ]
    return {key: status[key] for key in keys if key in status}
