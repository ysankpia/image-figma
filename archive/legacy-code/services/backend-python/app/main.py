from __future__ import annotations

import os
import secrets
import time
from pathlib import Path
from typing import Any

import orjson
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .config import load_config, load_dotenv_local
from .pipeline import Pipeline

load_dotenv_local()
config = load_config()
pipeline = Pipeline(config)

app = FastAPI(title="Pipeline Backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

tasks: dict[str, dict[str, Any]] = {}


def _new_task_id() -> str:
    return f"task_{secrets.token_hex(6)}"


@app.get("/api/health")
async def health():
    return {"success": True, "data": {"status": "ok", "version": "pipeline-v0.1"}}


@app.post("/api/draft-preview")
async def upload_preview(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".png"):
        raise HTTPException(400, "Only PNG files are supported")
    data = await file.read()
    if len(data) > config.server.max_upload_bytes:
        raise HTTPException(400, "File too large")
    if not data[:8] == b"\x89PNG\r\n\x1a\n":
        raise HTTPException(400, "Invalid PNG file")

    task_id = _new_task_id()
    storage = Path(config.server.storage_root) / task_id
    storage.mkdir(parents=True, exist_ok=True)
    input_path = storage / "input.png"
    input_path.write_bytes(data)

    task_record = {
        "taskId": task_id,
        "status": "queued",
        "progress": 1,
        "message": "Pipeline queued.",
        "outputDir": str(storage / "compile"),
        "dslPath": None,
    }
    tasks[task_id] = task_record

    import asyncio
    asyncio.create_task(_run_pipeline(task_id, str(input_path), str(storage / "compile")))

    return {"success": True, "data": {"taskId": task_id, "status": "queued"}}


@app.post("/api/draft-preview/batch")
async def upload_batch(files: list[UploadFile] = File(...)):
    if len(files) > 20:
        raise HTTPException(400, "Maximum 20 files per batch")
    results = []
    for file in files:
        if not file.filename or not file.filename.lower().endswith(".png"):
            results.append({"filename": file.filename, "status": "rejected", "error": "not PNG"})
            continue
        data = await file.read()
        if len(data) > config.server.max_upload_bytes:
            results.append({"filename": file.filename, "status": "rejected", "error": "too large"})
            continue
        if not data[:8] == b"\x89PNG\r\n\x1a\n":
            results.append({"filename": file.filename, "status": "rejected", "error": "invalid PNG"})
            continue

        task_id = _new_task_id()
        storage = Path(config.server.storage_root) / task_id
        storage.mkdir(parents=True, exist_ok=True)
        input_path = storage / "input.png"
        input_path.write_bytes(data)

        task_record = {
            "taskId": task_id,
            "status": "queued",
            "progress": 1,
            "message": "Pipeline queued.",
            "outputDir": str(storage / "compile"),
            "dslPath": None,
        }
        tasks[task_id] = task_record

        import asyncio
        asyncio.create_task(_run_pipeline(task_id, str(input_path), str(storage / "compile")))
        results.append({"taskId": task_id, "filename": file.filename, "status": "queued"})

    return {"success": True, "data": {"total": len(results), "tasks": results}}


@app.get("/api/draft-preview/{task_id}")
async def get_task(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return {"success": True, "data": task}


@app.get("/api/draft-preview/{task_id}/dsl")
async def get_dsl(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] != "completed":
        raise HTTPException(409, "DSL not ready")
    dsl_path = task.get("dslPath")
    if not dsl_path or not Path(dsl_path).exists():
        raise HTTPException(404, "DSL file not found")
    dsl = orjson.loads(Path(dsl_path).read_bytes())
    return {"success": True, "data": {"dsl": dsl}}


@app.get("/api/draft-preview/{task_id}/assets/{asset_name}")
async def get_asset(task_id: str, asset_name: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    asset_path = Path(task["outputDir"]) / "assets" / asset_name
    if not asset_path.exists() or not asset_name.endswith(".png"):
        raise HTTPException(404, "Asset not found")
    return FileResponse(asset_path, media_type="image/png")


async def _run_pipeline(task_id: str, input_path: str, output_dir: str):
    task = tasks[task_id]
    try:
        task["status"] = "running"
        task["progress"] = 20
        task["message"] = "Running pipeline..."
        dsl = await pipeline.run(input_path, output_dir, task_id)
        dsl_path = str(Path(output_dir) / "draft" / "draft_runtime.dsl.v1_0.json")
        task["status"] = "completed"
        task["progress"] = 100
        task["message"] = "Pipeline completed."
        task["dslPath"] = dsl_path
    except Exception as e:
        task["status"] = "failed"
        task["progress"] = 100
        task["message"] = str(e)
