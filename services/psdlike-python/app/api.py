from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Path as ApiPath, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from .core.pipeline import run_pipeline
from .storage import compile_dir, create_task_dirs, new_task_id, save_upload, task_dir, write_error

router = APIRouter()


@router.post("/api/draft-preview")
async def create_draft_preview(
    image: UploadFile = File(...),
    ocr: UploadFile | None = File(default=None),
    allow_missing_ocr: bool = Query(default=True, alias="allowMissingOcr"),
) -> JSONResponse:
    task_id = new_task_id()
    root = create_task_dirs(task_id)
    image_path = root / "input.png"
    ocr_path: Path | None = None
    try:
        save_upload(image_path, await image.read())
        if ocr is not None:
            ocr_path = root / "input.ocr_blocks.v1.json"
            save_upload(ocr_path, await ocr.read())
        result = run_pipeline(
            image_path=image_path,
            ocr_path=ocr_path,
            out_dir=compile_dir(task_id),
            allow_missing_ocr=allow_missing_ocr,
            task_id=task_id,
        )
    except Exception as exc:  # noqa: BLE001 - API writes error artifact for user visibility.
        write_error(task_id, exc)
        raise HTTPException(status_code=500, detail={"taskId": task_id, "error": str(exc)}) from exc
    return JSONResponse(
        {
            "taskId": task_id,
            "status": "completed",
            "dslUrl": f"/api/draft-preview/{task_id}/dsl",
            "previewUrl": f"/api/draft-preview/{task_id}/preview",
            "diagnostics": result.diagnostics,
        }
    )


@router.get("/api/draft-preview/{taskId}")
def get_task(task_id: str = ApiPath(alias="taskId")) -> JSONResponse:
    root = task_dir(task_id)
    if not root.exists():
        raise HTTPException(status_code=404, detail="task not found")
    error_path = root / "error.json"
    if error_path.exists():
        return JSONResponse({"taskId": task_id, "status": "failed", "errorPath": str(error_path)})
    diagnostics_path = compile_dir(task_id) / "layer_stack.v1.json"
    if not diagnostics_path.exists():
        return JSONResponse({"taskId": task_id, "status": "running"})
    return JSONResponse(
        {
            "taskId": task_id,
            "status": "completed",
            "dslUrl": f"/api/draft-preview/{task_id}/dsl",
            "previewUrl": f"/api/draft-preview/{task_id}/preview",
        }
    )


@router.get("/api/draft-preview/{taskId}/dsl")
def get_dsl(task_id: str = ApiPath(alias="taskId")) -> FileResponse:
    return existing_file(compile_dir(task_id) / "draft_runtime.dsl.v1_0.json", media_type="application/json")


@router.get("/api/draft-preview/{taskId}/assets/{name}")
def get_asset(task_id: str = ApiPath(alias="taskId"), name: str = ApiPath()) -> FileResponse:
    if "/" in name or ".." in name:
        raise HTTPException(status_code=400, detail="invalid asset name")
    return existing_file(compile_dir(task_id) / "assets" / name, media_type="image/png")


@router.get("/api/draft-preview/{taskId}/preview")
def get_preview(task_id: str = ApiPath(alias="taskId")) -> HTMLResponse:
    path = compile_dir(task_id) / "preview.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="preview not found")
    return HTMLResponse(path.read_text(encoding="utf-8"))


def existing_file(path: Path, media_type: str) -> FileResponse:
    if not path.exists():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path, media_type=media_type)
