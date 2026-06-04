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
    export_manual_slice_project,
    initialize_slice_project,
    validate_manual_slices,
)
from ..state import state
from ..types import IMAGE_EXTENSIONS, PageInput
from ..utils import safe_slug


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
        },
    }


@router.get("/{project_id}")
def get_slice_project(project_id: str) -> dict[str, object]:
    storage = SliceProjectStorage(state.storage)
    try:
        project = storage.read_project(project_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail="slice project not found") from error
    return {"success": True, "data": public_project(project)}


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
    selected = sum(1 for page in manual_slices.get("pages") or [] for item in page.get("slices") or [] if item.get("selected") is not False)
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
        selectedAssetCount=manifest["selectedAssetCount"],
    )
    return {"success": True, "data": manifest}


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
        "manualSlicesConfirmed",
        "error",
        "warnings",
        "createdAt",
        "updatedAt",
    ]
    return {key: project[key] for key in keys if key in project}


REVIEW_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Pencil Assisted Slice Review</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #111827; color: #e5e7eb; }
    .app { display: grid; grid-template-columns: 180px minmax(0, 1fr) 320px; height: 100vh; }
    aside, .panel { border-color: #263244; border-style: solid; background: #0f172a; }
    aside { border-width: 0 1px 0 0; padding: 12px; overflow: auto; }
    .panel { border-width: 0 0 0 1px; padding: 12px; overflow: auto; }
    main { display: grid; grid-template-rows: auto minmax(0, 1fr); min-width: 0; }
    .toolbar { display: flex; gap: 8px; align-items: center; padding: 10px 12px; border-bottom: 1px solid #263244; background: #111827; }
    button, input, select { border: 1px solid #334155; background: #1f2937; color: #e5e7eb; border-radius: 6px; padding: 7px 9px; }
    button.active { background: #2563eb; border-color: #3b82f6; }
    button.primary { background: #16a34a; border-color: #22c55e; }
    button.warn { background: #7f1d1d; border-color: #ef4444; }
    .page-btn { width: 100%; margin-bottom: 8px; text-align: left; }
    .canvas-wrap { overflow: auto; position: relative; background: #020617; }
    canvas { display: block; margin: 24px auto; background: #fff; }
    .asset { border: 1px solid #334155; border-radius: 8px; padding: 8px; margin-bottom: 8px; background: #111827; }
    .asset.active { border-color: #60a5fa; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 6px; }
    .muted { color: #94a3b8; font-size: 12px; }
    .status { margin-left: auto; color: #94a3b8; font-size: 12px; }
  </style>
</head>
<body>
  <div class="app">
    <aside>
      <h3>Pages</h3>
      <div id="pages"></div>
    </aside>
    <main>
      <div class="toolbar">
        <button id="mode-select" class="active">选择</button>
        <button id="mode-draw">画框</button>
        <button id="delete" class="warn">删除</button>
        <button id="save">保存</button>
        <button id="export" class="primary">导出</button>
        <a id="download" style="display:none;color:#86efac" href="#">下载 ZIP</a>
        <span id="status" class="status">loading</span>
      </div>
      <div class="canvas-wrap"><canvas id="canvas"></canvas></div>
    </main>
    <section class="panel">
      <h3>Selected Slices</h3>
      <div id="assets"></div>
    </section>
  </div>
  <script>
    const projectId = "__PROJECT_ID__";
    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");
    const state = { candidates: null, manual: null, pageIndex: 0, mode: "select", image: null, activeId: null, drag: null };
    const colors = { image: "#22c55e", icon: "#22c55e", text: "#ef4444", shape: "#3b82f6", group: "#f59e0b", unknown: "#eab308" };

    function setStatus(text) { document.getElementById("status").textContent = text; }
    async function api(path, options) {
      const res = await fetch(`/api/pencil/slice-projects/${projectId}${path}`, options);
      if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
      return (await res.json()).data;
    }
    async function load() {
      state.candidates = await api("/candidates");
      state.manual = await api("/manual-slices");
      renderPages();
      await loadPage(0);
      renderAssets();
      setStatus("ready");
    }
    function currentCandidatePage() { return state.candidates.pages[state.pageIndex]; }
    function currentManualPage() { return state.manual.pages[state.pageIndex]; }
    async function loadPage(index) {
      state.pageIndex = index;
      state.activeId = null;
      const page = currentCandidatePage();
      state.image = new Image();
      state.image.onload = () => {
        canvas.width = page.width;
        canvas.height = page.height;
        draw();
      };
      state.image.src = `/api/pencil/slice-projects/${projectId}/source/${page.pageId}`;
      renderPages();
      renderAssets();
    }
    function renderPages() {
      document.getElementById("pages").innerHTML = state.candidates.pages.map((page, i) =>
        `<button class="page-btn ${i === state.pageIndex ? "active" : ""}" onclick="loadPage(${i})">${page.pageId}<br><span class="muted">${page.width}x${page.height}</span></button>`
      ).join("");
    }
    function draw() {
      if (!state.image) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(state.image, 0, 0);
      for (const candidate of currentCandidatePage().candidates) drawBox(candidate.bbox, colors[candidate.kind] || colors.unknown, candidate.id.split("_").pop(), false);
      for (const slice of currentManualPage().slices) if (slice.selected !== false) drawBox(slice.bbox, "#ffffff", slice.name, slice.id === state.activeId);
      if (state.drag?.draft) drawBox(state.drag.draft, "#f97316", "new", true);
    }
    function drawBox(b, color, label, active) {
      ctx.save();
      ctx.strokeStyle = color;
      ctx.lineWidth = active ? 4 : 2;
      ctx.strokeRect(b.x, b.y, b.width, b.height);
      ctx.fillStyle = "rgba(2,6,23,.78)";
      ctx.fillRect(b.x, Math.max(0, b.y - 18), Math.min(140, Math.max(34, String(label).length * 8 + 10)), 18);
      ctx.fillStyle = color;
      ctx.font = "12px sans-serif";
      ctx.fillText(String(label), b.x + 4, Math.max(12, b.y - 5));
      if (active) {
        ctx.fillStyle = "#60a5fa";
        for (const handle of handlesFor(b)) ctx.fillRect(handle.x - 4, handle.y - 4, 8, 8);
      }
      ctx.restore();
    }
    function handlesFor(b) {
      const cx = b.x + b.width / 2, cy = b.y + b.height / 2, r = b.x + b.width, bt = b.y + b.height;
      return [
        { name: "nw", x: b.x, y: b.y }, { name: "n", x: cx, y: b.y }, { name: "ne", x: r, y: b.y },
        { name: "e", x: r, y: cy }, { name: "se", x: r, y: bt }, { name: "s", x: cx, y: bt },
        { name: "sw", x: b.x, y: bt }, { name: "w", x: b.x, y: cy }
      ];
    }
    function hitHandle(slice, point) {
      for (const handle of handlesFor(slice.bbox)) {
        if (Math.abs(point.x - handle.x) <= 8 && Math.abs(point.y - handle.y) <= 8) return handle.name;
      }
      return null;
    }
    function canvasPoint(event) {
      const rect = canvas.getBoundingClientRect();
      return { x: Math.round((event.clientX - rect.left) * canvas.width / rect.width), y: Math.round((event.clientY - rect.top) * canvas.height / rect.height) };
    }
    function clampBox(b) {
      const x = Math.max(0, Math.min(canvas.width - 1, Math.round(b.x)));
      const y = Math.max(0, Math.min(canvas.height - 1, Math.round(b.y)));
      const width = Math.max(1, Math.min(canvas.width - x, Math.round(b.width)));
      const height = Math.max(1, Math.min(canvas.height - y, Math.round(b.height)));
      return { x, y, width, height };
    }
    function resizeBox(original, handle, dx, dy) {
      let x = original.x, y = original.y, right = original.x + original.width, bottom = original.y + original.height;
      if (handle.includes("w")) x += dx;
      if (handle.includes("e")) right += dx;
      if (handle.includes("n")) y += dy;
      if (handle.includes("s")) bottom += dy;
      x = Math.max(0, Math.min(x, right - 1));
      y = Math.max(0, Math.min(y, bottom - 1));
      right = Math.max(x + 1, Math.min(canvas.width, right));
      bottom = Math.max(y + 1, Math.min(canvas.height, bottom));
      return { x: Math.round(x), y: Math.round(y), width: Math.round(right - x), height: Math.round(bottom - y) };
    }
    function hit(items, point) {
      return [...items].reverse().find(item => point.x >= item.bbox.x && point.y >= item.bbox.y && point.x <= item.bbox.x + item.bbox.width && point.y <= item.bbox.y + item.bbox.height);
    }
    canvas.addEventListener("mousedown", event => {
      const p = canvasPoint(event);
      if (state.mode === "draw") {
        state.drag = { start: p, draft: { x: p.x, y: p.y, width: 1, height: 1 } };
        return;
      }
      const slice = hit(currentManualPage().slices, p);
      if (slice) {
        state.activeId = slice.id;
        const handle = hitHandle(slice, p);
        state.drag = { id: slice.id, action: handle ? "resize" : "move", handle, start: p, original: { ...slice.bbox } };
        renderAssets(); draw(); return;
      }
      const candidate = hit(currentCandidatePage().candidates.map(c => ({...c, bbox: c.bbox})), p);
      if (candidate) addSliceFromCandidate(candidate);
    });
    canvas.addEventListener("mousemove", event => {
      if (!state.drag) return;
      const p = canvasPoint(event);
      if (state.drag.draft) {
        const x = Math.min(state.drag.start.x, p.x), y = Math.min(state.drag.start.y, p.y);
        state.drag.draft = clampBox({ x, y, width: Math.abs(p.x - state.drag.start.x), height: Math.abs(p.y - state.drag.start.y) });
      } else {
        const slice = currentManualPage().slices.find(item => item.id === state.drag.id);
        if (slice) {
          const dx = p.x - state.drag.start.x, dy = p.y - state.drag.start.y;
          if (state.drag.action === "resize") {
            slice.bbox = resizeBox(state.drag.original, state.drag.handle, dx, dy);
          } else {
            slice.bbox.x = Math.max(0, Math.min(canvas.width - slice.bbox.width, state.drag.original.x + dx));
            slice.bbox.y = Math.max(0, Math.min(canvas.height - slice.bbox.height, state.drag.original.y + dy));
          }
        }
      }
      draw(); renderAssets();
    });
    window.addEventListener("mouseup", () => {
      if (state.drag?.draft && state.drag.draft.width > 4 && state.drag.draft.height > 4) addManualSlice(state.drag.draft);
      state.drag = null;
      draw(); renderAssets();
    });
    function addSliceFromCandidate(candidate) {
      const page = currentManualPage();
      const id = `${page.pageId}__slice_${String(Date.now()).slice(-8)}`;
      page.slices.push({ id, name: `slice_${page.slices.length + 1}`, kind: candidate.kind, bbox: clampBox({...candidate.bbox}), selected: true, exportMode: "rect", source: "candidate_confirmed", candidateIds: [candidate.id] });
      state.activeId = id; renderAssets(); draw();
    }
    function addManualSlice(bbox) {
      const page = currentManualPage();
      const id = `${page.pageId}__slice_${String(Date.now()).slice(-8)}`;
      page.slices.push({ id, name: `slice_${page.slices.length + 1}`, kind: "image", bbox: clampBox(bbox), selected: true, exportMode: "rect", source: "manual", candidateIds: [] });
      state.activeId = id;
    }
    function renderAssets() {
      const page = currentManualPage();
      document.getElementById("assets").innerHTML = page.slices.map(slice => `
        <div class="asset ${slice.id === state.activeId ? "active" : ""}" onclick="state.activeId='${slice.id}'; renderAssets(); draw();">
          <input value="${slice.name}" onchange="updateSlice('${slice.id}', 'name', this.value)" />
          <div class="row">
            <input type="number" value="${slice.bbox.x}" onchange="updateBBox('${slice.id}', 'x', this.value)" />
            <input type="number" value="${slice.bbox.y}" onchange="updateBBox('${slice.id}', 'y', this.value)" />
            <input type="number" value="${slice.bbox.width}" onchange="updateBBox('${slice.id}', 'width', this.value)" />
            <input type="number" value="${slice.bbox.height}" onchange="updateBBox('${slice.id}', 'height', this.value)" />
          </div>
          <div class="muted">${slice.kind} / ${slice.source}</div>
        </div>`).join("");
    }
    function updateSlice(id, key, value) { const s = currentManualPage().slices.find(x => x.id === id); if (s) s[key] = value; draw(); }
    function updateBBox(id, key, value) { const s = currentManualPage().slices.find(x => x.id === id); if (s) { s.bbox[key] = Math.max(0, Number(value) || 0); s.bbox = clampBox(s.bbox); } draw(); renderAssets(); }
    document.getElementById("mode-select").onclick = () => setMode("select");
    document.getElementById("mode-draw").onclick = () => setMode("draw");
    function setMode(mode) { state.mode = mode; document.getElementById("mode-select").classList.toggle("active", mode === "select"); document.getElementById("mode-draw").classList.toggle("active", mode === "draw"); }
    document.getElementById("delete").onclick = () => { const page = currentManualPage(); page.slices = page.slices.filter(x => x.id !== state.activeId); state.activeId = null; renderAssets(); draw(); };
    document.getElementById("save").onclick = async () => { await api("/manual-slices", { method: "PUT", headers: {"Content-Type":"application/json"}, body: JSON.stringify(state.manual) }); setStatus("saved"); };
    document.getElementById("export").onclick = async () => { await document.getElementById("save").onclick(); await api("/export", { method: "POST" }); const link = document.getElementById("download"); link.href = `/api/pencil/slice-projects/${projectId}/download.zip`; link.style.display = "inline"; setStatus("exported"); };
    window.loadPage = loadPage; window.state = state; window.updateSlice = updateSlice; window.updateBBox = updateBBox;
    load().catch(error => setStatus(error.message));
  </script>
</body>
</html>
"""
