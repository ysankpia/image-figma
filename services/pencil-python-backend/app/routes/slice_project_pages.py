from __future__ import annotations


NEW_PROJECT_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Pencil Slice Review</title>
  <link rel="icon" href="data:," />
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0f172a; color: #e5e7eb; display: grid; place-items: center; }
    main { width: min(720px, calc(100vw - 32px)); border: 1px solid #263244; background: #111827; padding: 24px; border-radius: 8px; }
    h1 { margin: 0 0 18px; font-size: 22px; font-weight: 650; }
    label { display: block; margin: 14px 0 6px; color: #cbd5e1; font-size: 13px; }
    input, select, button { width: 100%; border: 1px solid #334155; background: #1f2937; color: #e5e7eb; border-radius: 6px; padding: 10px 12px; font: inherit; }
    input[type="checkbox"] { width: auto; margin-right: 8px; }
    button { margin-top: 18px; background: #16a34a; border-color: #22c55e; cursor: pointer; }
    button:disabled { opacity: .6; cursor: progress; }
    .row { display: grid; grid-template-columns: 1fr 180px; gap: 12px; }
    .check { display: flex; align-items: center; margin-top: 12px; color: #cbd5e1; }
    .muted { color: #94a3b8; font-size: 12px; line-height: 1.5; margin-top: 12px; }
    .status { min-height: 20px; margin-top: 14px; color: #93c5fd; font-size: 13px; white-space: pre-wrap; }
    .error { color: #fca5a5; }
  </style>
</head>
<body>
  <main>
    <h1>Pencil Slice Review</h1>
    <form id="form">
      <label for="files">Images</label>
      <input id="files" name="files[]" type="file" accept="image/png,image/jpeg,image/webp" multiple required />
      <div class="row">
        <div>
          <label for="projectName">Project name</label>
          <input id="projectName" name="projectName" value="Assisted Slice Project" />
        </div>
        <div>
          <label for="boundarySource">Boundary source</label>
          <select id="boundarySource" name="boundarySource">
            <option value="psdlike" selected>psdlike</option>
            <option value="m29">m29</option>
            <option value="hybrid">hybrid</option>
          </select>
        </div>
      </div>
      <label class="check"><input id="includeDebug" name="includeDebug" type="checkbox" checked /> include debug artifacts</label>
      <button id="submit" type="submit">Create review project</button>
    </form>
    <div class="muted">Upload one or more screenshots, then confirm slices in the review workbench. Manual slices are the final export contract.</div>
    <div id="status" class="status"></div>
  </main>
  <script>
    const form = document.getElementById("form");
    const submit = document.getElementById("submit");
    const statusEl = document.getElementById("status");
    function status(text, error=false) {
      statusEl.textContent = text;
      statusEl.classList.toggle("error", error);
    }
    form.addEventListener("submit", async event => {
      event.preventDefault();
      const files = document.getElementById("files").files;
      if (!files.length) { status("Select at least one image.", true); return; }
      const body = new FormData();
      for (const file of files) body.append("files[]", file);
      body.append("projectName", document.getElementById("projectName").value || "Assisted Slice Project");
      body.append("boundarySource", document.getElementById("boundarySource").value);
      body.append("includeDebug", document.getElementById("includeDebug").checked ? "true" : "false");
      submit.disabled = true;
      status("Creating project...");
      try {
        const response = await fetch("/api/pencil/slice-projects", { method: "POST", body });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
        const url = payload.data.reviewUrl || `/api/pencil/slice-projects/${payload.data.projectId}/review`;
        status(`Created ${payload.data.projectId}. Opening review...`);
        window.location.href = url;
      } catch (error) {
        status(error.message || String(error), true);
        submit.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


REVIEW_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Pencil Assisted Slice Workbench</title>
  <link rel="icon" href="data:," />
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #0b1120; color: #e5e7eb; overflow: hidden; }
    .app { display: grid; grid-template-columns: 210px minmax(0, 1fr) 350px; height: 100vh; }
    aside, .panel { border-color: #263244; border-style: solid; background: #0f172a; min-height: 0; overflow: auto; }
    aside { border-width: 0 1px 0 0; padding: 12px; }
    .panel { border-width: 0 0 0 1px; padding: 12px; }
    main { display: grid; grid-template-rows: auto minmax(0, 1fr); min-width: 0; min-height: 0; }
    h3 { margin: 0 0 10px; font-size: 14px; font-weight: 650; }
    button, input, select { border: 1px solid #334155; background: #1f2937; color: #e5e7eb; border-radius: 6px; padding: 7px 9px; font: inherit; }
    button { cursor: pointer; white-space: nowrap; }
    button.active { background: #2563eb; border-color: #3b82f6; }
    button.primary { background: #16a34a; border-color: #22c55e; }
    button.warn { background: #7f1d1d; border-color: #ef4444; }
    label { font-size: 12px; color: #cbd5e1; }
    .toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 10px 12px; border-bottom: 1px solid #263244; background: #111827; }
    .canvas-wrap { overflow: hidden; position: relative; background: #020617; min-height: 0; }
    canvas { display: block; width: 100%; height: 100%; }
    .page-btn { width: 100%; margin-bottom: 8px; text-align: left; }
    .page-btn .count { float: right; color: #86efac; }
    .filters { display: grid; gap: 8px; margin-bottom: 14px; border-bottom: 1px solid #263244; padding-bottom: 12px; }
    .filter-row { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
    .filter-row label { display: inline-flex; gap: 4px; align-items: center; }
    .filter-row input[type="checkbox"] { width: auto; }
    .filter-row input[type="range"] { width: 130px; }
    .asset { border: 1px solid #334155; border-radius: 8px; padding: 8px; margin-bottom: 8px; background: #111827; }
    .asset.active { border-color: #60a5fa; }
    .asset input, .asset select { width: 100%; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 6px; }
    .muted { color: #94a3b8; font-size: 12px; }
    .status { margin-left: auto; color: #94a3b8; font-size: 12px; }
    .hud { position: absolute; left: 12px; bottom: 12px; background: rgba(15, 23, 42, .86); border: 1px solid #334155; border-radius: 6px; padding: 6px 8px; color: #cbd5e1; font-size: 12px; pointer-events: none; }
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
        <button id="pan">平移</button>
        <button id="fit">适屏</button>
        <button id="zoom100">100%</button>
        <button id="zoomOut">-</button>
        <button id="zoomIn">+</button>
        <button id="delete" class="warn">删除</button>
        <button id="save">保存</button>
        <button id="export" class="primary">导出</button>
        <a id="download" style="display:none;color:#86efac" href="#">下载 ZIP</a>
        <span id="status" class="status">loading</span>
      </div>
      <div class="canvas-wrap" id="viewport">
        <canvas id="canvas"></canvas>
        <div id="hud" class="hud">loading</div>
      </div>
    </main>
    <section class="panel">
      <div class="filters">
        <h3>Filters</h3>
        <div class="filter-row">
          <label><input id="showCandidates" type="checkbox" checked /> candidates</label>
          <label><input id="showSelected" type="checkbox" checked /> selected</label>
          <label><input id="showLabels" type="checkbox" checked /> labels</label>
        </div>
        <div class="filter-row" id="kindFilters"></div>
        <div class="filter-row" id="sourceFilters"></div>
        <div class="filter-row">
          <label>conf <input id="minConfidence" type="number" min="0" max="1" step="0.05" value="0" style="width:72px" /></label>
          <label>opacity <input id="candidateOpacity" type="range" min="0.1" max="1" step="0.05" value="0.75" /></label>
        </div>
      </div>
      <h3>Selected Slices <span id="selectedCount" class="muted"></span></h3>
      <div id="assets"></div>
    </section>
  </div>
  <script>
    const projectId = "__PROJECT_ID__";
    const canvas = document.getElementById("canvas");
    const viewport = document.getElementById("viewport");
    const ctx = canvas.getContext("2d");
    const hud = document.getElementById("hud");
    const kindOptions = ["image", "icon", "text", "shape", "group", "unknown"];
    const sourceOptions = ["psdlike", "m29", "foreground_audit", "source", "manual"];
    const colors = { image: "#22c55e", icon: "#22c55e", text: "#ef4444", shape: "#3b82f6", group: "#f59e0b", unknown: "#eab308", full_screen: "#64748b", upper_region: "#64748b", middle_region: "#64748b", lower_region: "#64748b" };
    const state = {
      candidates: null, manual: null, pageIndex: 0, mode: "select", image: null, activeId: null, drag: null,
      view: { scale: 1, offsetX: 40, offsetY: 40 }, spaceDown: false,
      filters: {
        showCandidates: true, showSelected: true, showLabels: true, minConfidence: 0, candidateOpacity: 0.75,
        kinds: { image: true, icon: true, text: false, shape: true, group: true, unknown: true },
        sources: { psdlike: true, m29: true, foreground_audit: true, source: true, manual: true }
      }
    };

    function setStatus(text, error=false) {
      const el = document.getElementById("status");
      el.textContent = text;
      el.style.color = error ? "#fca5a5" : "#94a3b8";
    }
    async function api(path, options) {
      const res = await fetch(`/api/pencil/slice-projects/${projectId}${path}`, options);
      let payload = null;
      try { payload = await res.json(); } catch (_) {}
      if (!res.ok) throw new Error((payload && payload.detail) || res.statusText);
      return payload.data;
    }
    async function load() {
      state.candidates = await api("/candidates");
      state.manual = await api("/manual-slices");
      renderFilterControls();
      renderPages();
      await loadPage(0);
      setStatus("ready");
    }
    function currentCandidatePage() { return state.candidates.pages[state.pageIndex]; }
    function currentManualPage() { return state.manual.pages[state.pageIndex]; }
    async function loadPage(index) {
      state.pageIndex = index;
      state.activeId = null;
      const page = currentCandidatePage();
      state.image = new Image();
      state.image.onload = () => { resizeCanvas(); fitToScreen(); renderAll(); };
      state.image.src = `/api/pencil/slice-projects/${projectId}/source/${page.pageId}`;
      renderPages();
      renderAssets();
    }
    function resizeCanvas() {
      const rect = viewport.getBoundingClientRect();
      canvas.width = Math.max(1, Math.round(rect.width * devicePixelRatio));
      canvas.height = Math.max(1, Math.round(rect.height * devicePixelRatio));
      ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
    }
    window.addEventListener("resize", () => { resizeCanvas(); renderAll(); });

    function imageToScreen(point) {
      return { x: point.x * state.view.scale + state.view.offsetX, y: point.y * state.view.scale + state.view.offsetY };
    }
    function screenToImage(point) {
      return { x: (point.x - state.view.offsetX) / state.view.scale, y: (point.y - state.view.offsetY) / state.view.scale };
    }
    function eventScreenPoint(event) {
      const rect = canvas.getBoundingClientRect();
      return { x: event.clientX - rect.left, y: event.clientY - rect.top };
    }
    function eventImagePoint(event) {
      const p = screenToImage(eventScreenPoint(event));
      return { x: Math.round(p.x), y: Math.round(p.y) };
    }
    function clampBox(b) {
      const page = currentCandidatePage();
      const x = Math.max(0, Math.min(page.width - 1, Math.round(b.x)));
      const y = Math.max(0, Math.min(page.height - 1, Math.round(b.y)));
      const width = Math.max(1, Math.min(page.width - x, Math.round(b.width)));
      const height = Math.max(1, Math.min(page.height - y, Math.round(b.height)));
      return { x, y, width, height };
    }
    function renderAll() {
      draw();
      renderPages();
      renderAssets();
      updateHud();
    }
    function draw() {
      const rect = canvas.getBoundingClientRect();
      ctx.clearRect(0, 0, rect.width, rect.height);
      ctx.save();
      ctx.translate(state.view.offsetX, state.view.offsetY);
      ctx.scale(state.view.scale, state.view.scale);
      if (state.image) ctx.drawImage(state.image, 0, 0);
      if (state.filters.showCandidates) {
        for (const candidate of filteredCandidates()) {
          drawBox(candidate.bbox, colors[candidate.kind] || colors.unknown, candidate.id.split("_").pop(), false, state.filters.candidateOpacity);
        }
      }
      if (state.filters.showSelected) {
        for (const slice of currentManualPage().slices) if (slice.selected !== false) drawBox(slice.bbox, "#ffffff", slice.name, slice.id === state.activeId, 1);
      }
      if (state.drag?.draft) drawBox(state.drag.draft, "#f97316", "new", true, 1);
      ctx.restore();
    }
    function drawBox(b, color, label, active, alpha) {
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.strokeStyle = color;
      ctx.lineWidth = (active ? 3 : 2) / state.view.scale;
      ctx.strokeRect(b.x, b.y, b.width, b.height);
      if (state.filters.showLabels) {
        ctx.fillStyle = "rgba(2,6,23,.78)";
        const labelWidth = Math.min(160, Math.max(34, String(label).length * 8 + 10)) / state.view.scale;
        const labelHeight = 18 / state.view.scale;
        ctx.fillRect(b.x, Math.max(0, b.y - labelHeight), labelWidth, labelHeight);
        ctx.fillStyle = color;
        ctx.font = `${12 / state.view.scale}px sans-serif`;
        ctx.fillText(String(label), b.x + 4 / state.view.scale, Math.max(12 / state.view.scale, b.y - 5 / state.view.scale));
      }
      if (active) {
        ctx.fillStyle = "#60a5fa";
        const size = 8 / state.view.scale;
        for (const handle of handlesFor(b)) ctx.fillRect(handle.x - size / 2, handle.y - size / 2, size, size);
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
      const threshold = 9 / state.view.scale;
      for (const handle of handlesFor(slice.bbox)) {
        if (Math.abs(point.x - handle.x) <= threshold && Math.abs(point.y - handle.y) <= threshold) return handle.name;
      }
      return null;
    }
    function hit(items, point) {
      return [...items].reverse().find(item => point.x >= item.bbox.x && point.y >= item.bbox.y && point.x <= item.bbox.x + item.bbox.width && point.y <= item.bbox.y + item.bbox.height);
    }
    function filteredCandidates() {
      return currentCandidatePage().candidates.filter(candidate => {
        const kind = state.filters.kinds[candidate.kind] !== undefined ? candidate.kind : "unknown";
        const source = state.filters.sources[candidate.source] !== undefined ? candidate.source : "manual";
        return state.filters.kinds[kind] && state.filters.sources[source] && Number(candidate.confidence || 0) >= state.filters.minConfidence;
      });
    }

    function fitToScreen() {
      const rect = canvas.getBoundingClientRect();
      const page = currentCandidatePage();
      const scale = Math.min((rect.width - 48) / page.width, (rect.height - 48) / page.height);
      state.view.scale = Math.max(0.05, Math.min(4, scale || 1));
      state.view.offsetX = (rect.width - page.width * state.view.scale) / 2;
      state.view.offsetY = (rect.height - page.height * state.view.scale) / 2;
      renderAll();
    }
    function setZoom(scale, center) {
      const before = screenToImage(center);
      state.view.scale = Math.max(0.05, Math.min(8, scale));
      state.view.offsetX = center.x - before.x * state.view.scale;
      state.view.offsetY = center.y - before.y * state.view.scale;
      renderAll();
    }
    function zoomBy(factor, center=null) {
      const rect = canvas.getBoundingClientRect();
      setZoom(state.view.scale * factor, center || { x: rect.width / 2, y: rect.height / 2 });
    }

    canvas.addEventListener("mousedown", event => {
      const screen = eventScreenPoint(event);
      const p = eventImagePoint(event);
      if (state.mode === "pan" || state.spaceDown) {
        state.drag = { action: "pan", startScreen: screen, originalView: { ...state.view } };
        return;
      }
      if (state.mode === "draw") {
        state.drag = { action: "draw", start: p, draft: clampBox({ x: p.x, y: p.y, width: 1, height: 1 }) };
        return;
      }
      const slice = hit(currentManualPage().slices.filter(item => item.selected !== false), p);
      if (slice) {
        state.activeId = slice.id;
        const handle = hitHandle(slice, screenToImage(screen));
        state.drag = { id: slice.id, action: handle ? "resize" : "move", handle, start: p, original: { ...slice.bbox } };
        renderAll(); return;
      }
      const candidate = hit(filteredCandidates(), p);
      if (candidate) {
        state.activeId = null;
        renderAll();
      }
    });
    canvas.addEventListener("dblclick", event => {
      const candidate = hit(filteredCandidates(), eventImagePoint(event));
      if (candidate) addSliceFromCandidate(candidate);
    });
    canvas.addEventListener("mousemove", event => {
      const screen = eventScreenPoint(event);
      const p = eventImagePoint(event);
      if (state.drag) {
        if (state.drag.action === "pan") {
          state.view.offsetX = state.drag.originalView.offsetX + screen.x - state.drag.startScreen.x;
          state.view.offsetY = state.drag.originalView.offsetY + screen.y - state.drag.startScreen.y;
        } else if (state.drag.action === "draw") {
          const x = Math.min(state.drag.start.x, p.x), y = Math.min(state.drag.start.y, p.y);
          state.drag.draft = clampBox({ x, y, width: Math.abs(p.x - state.drag.start.x), height: Math.abs(p.y - state.drag.start.y) });
        } else {
          const slice = currentManualPage().slices.find(item => item.id === state.drag.id);
          if (slice) {
            const dx = p.x - state.drag.start.x, dy = p.y - state.drag.start.y;
            if (state.drag.action === "resize") slice.bbox = resizeBox(state.drag.original, state.drag.handle, dx, dy);
            else slice.bbox = moveBox(state.drag.original, dx, dy);
          }
        }
        renderAll();
      } else {
        updateHud(p);
      }
    });
    window.addEventListener("mouseup", () => {
      if (state.drag?.action === "draw" && state.drag.draft.width > 4 && state.drag.draft.height > 4) addManualSlice(state.drag.draft);
      state.drag = null;
      renderAll();
    });
    canvas.addEventListener("wheel", event => {
      event.preventDefault();
      zoomBy(event.deltaY < 0 ? 1.12 : 0.89, eventScreenPoint(event));
    }, { passive: false });
    function resizeBox(original, handle, dx, dy) {
      let x = original.x, y = original.y, right = original.x + original.width, bottom = original.y + original.height;
      if (handle.includes("w")) x += dx;
      if (handle.includes("e")) right += dx;
      if (handle.includes("n")) y += dy;
      if (handle.includes("s")) bottom += dy;
      x = Math.max(0, Math.min(x, right - 1));
      y = Math.max(0, Math.min(y, bottom - 1));
      right = Math.max(x + 1, Math.min(currentCandidatePage().width, right));
      bottom = Math.max(y + 1, Math.min(currentCandidatePage().height, bottom));
      return { x: Math.round(x), y: Math.round(y), width: Math.round(right - x), height: Math.round(bottom - y) };
    }
    function moveBox(original, dx, dy) {
      const page = currentCandidatePage();
      return {
        x: Math.round(Math.max(0, Math.min(page.width - original.width, original.x + dx))),
        y: Math.round(Math.max(0, Math.min(page.height - original.height, original.y + dy))),
        width: original.width,
        height: original.height
      };
    }
    function addSliceFromCandidate(candidate) {
      const page = currentManualPage();
      const id = `${page.pageId}__slice_${Date.now()}_${Math.floor(Math.random()*1000)}`;
      page.slices.push({ id, name: `slice_${page.slices.length + 1}`, kind: normalizeKind(candidate.kind), bbox: clampBox({...candidate.bbox}), selected: true, exportMode: "rect", source: "candidate_confirmed", candidateIds: [candidate.id] });
      state.activeId = id; renderAll();
    }
    function addManualSlice(bbox) {
      const page = currentManualPage();
      const id = `${page.pageId}__slice_${Date.now()}_${Math.floor(Math.random()*1000)}`;
      page.slices.push({ id, name: `slice_${page.slices.length + 1}`, kind: "image", bbox: clampBox(bbox), selected: true, exportMode: "rect", source: "manual", candidateIds: [] });
      state.activeId = id;
    }
    function duplicateActive() {
      const page = currentManualPage();
      const slice = activeSlice();
      if (!slice) return;
      const id = `${page.pageId}__slice_${Date.now()}_${Math.floor(Math.random()*1000)}`;
      page.slices.push({ ...slice, id, name: `${slice.name}_copy`, bbox: clampBox({ ...slice.bbox, x: slice.bbox.x + 12, y: slice.bbox.y + 12 }) });
      state.activeId = id; renderAll();
    }
    function activeSlice() { return currentManualPage().slices.find(item => item.id === state.activeId); }
    function deleteActive() {
      const page = currentManualPage();
      page.slices = page.slices.filter(item => item.id !== state.activeId);
      state.activeId = null; renderAll();
    }
    function moveActive(dx, dy) {
      const slice = activeSlice();
      if (!slice) return;
      slice.bbox = moveBox(slice.bbox, dx, dy);
      renderAll();
    }
    function normalizeKind(kind) { return kindOptions.includes(kind) ? kind : "unknown"; }

    function renderPages() {
      document.getElementById("pages").innerHTML = state.candidates.pages.map((page, i) => {
        const manualPage = state.manual.pages.find(item => item.pageId === page.pageId);
        const count = (manualPage?.slices || []).filter(item => item.selected !== false).length;
        return `<button class="page-btn ${i === state.pageIndex ? "active" : ""}" onclick="loadPage(${i})">${page.pageId}<span class="count">${count}</span><br><span class="muted">${page.width}x${page.height}</span></button>`;
      }).join("");
    }
    function renderAssets() {
      const page = currentManualPage();
      const selectedCount = page.slices.filter(item => item.selected !== false).length;
      document.getElementById("selectedCount").textContent = `(${selectedCount})`;
      document.getElementById("assets").innerHTML = page.slices.map(slice => `
        <div class="asset ${slice.id === state.activeId ? "active" : ""}" onclick="focusSlice('${slice.id}')">
          <input name="${slice.id}__name" value="${escapeHtml(slice.name)}" onchange="updateSlice('${slice.id}', 'name', this.value)" />
          <div class="row">
            <select name="${slice.id}__kind" onchange="updateSlice('${slice.id}', 'kind', this.value)">${kindOptions.map(kind => `<option value="${kind}" ${normalizeKind(slice.kind) === kind ? "selected" : ""}>${kind}</option>`).join("")}</select>
            <label><input name="${slice.id}__selected" type="checkbox" ${slice.selected !== false ? "checked" : ""} onchange="updateSlice('${slice.id}', 'selected', this.checked)" /> selected</label>
          </div>
          <div class="row">
            <input name="${slice.id}__x" type="number" value="${slice.bbox.x}" onchange="updateBBox('${slice.id}', 'x', this.value)" />
            <input name="${slice.id}__y" type="number" value="${slice.bbox.y}" onchange="updateBBox('${slice.id}', 'y', this.value)" />
            <input name="${slice.id}__width" type="number" value="${slice.bbox.width}" onchange="updateBBox('${slice.id}', 'width', this.value)" />
            <input name="${slice.id}__height" type="number" value="${slice.bbox.height}" onchange="updateBBox('${slice.id}', 'height', this.value)" />
          </div>
          <div class="muted">${slice.source || "manual"} ${slice.candidateIds?.length ? "/ candidate" : ""}</div>
        </div>`).join("");
    }
    function focusSlice(id) {
      state.activeId = id;
      const slice = activeSlice();
      if (slice) {
        const rect = canvas.getBoundingClientRect();
        state.view.offsetX = rect.width / 2 - (slice.bbox.x + slice.bbox.width / 2) * state.view.scale;
        state.view.offsetY = rect.height / 2 - (slice.bbox.y + slice.bbox.height / 2) * state.view.scale;
      }
      renderAll();
    }
    function renderFilterControls() {
      document.getElementById("kindFilters").innerHTML = kindOptions.map(kind => `<label><input name="filter_kind_${kind}" type="checkbox" data-kind="${kind}" ${state.filters.kinds[kind] ? "checked" : ""} /> ${kind}</label>`).join("");
      document.getElementById("sourceFilters").innerHTML = sourceOptions.map(source => `<label><input name="filter_source_${source}" type="checkbox" data-source="${source}" ${state.filters.sources[source] ? "checked" : ""} /> ${source}</label>`).join("");
      for (const input of document.querySelectorAll("[data-kind]")) input.onchange = () => { state.filters.kinds[input.dataset.kind] = input.checked; renderAll(); };
      for (const input of document.querySelectorAll("[data-source]")) input.onchange = () => { state.filters.sources[input.dataset.source] = input.checked; renderAll(); };
      for (const id of ["showCandidates", "showSelected", "showLabels"]) document.getElementById(id).onchange = event => { state.filters[id] = event.target.checked; renderAll(); };
      document.getElementById("minConfidence").onchange = event => { state.filters.minConfidence = Number(event.target.value) || 0; renderAll(); };
      document.getElementById("candidateOpacity").oninput = event => { state.filters.candidateOpacity = Number(event.target.value) || 0.75; renderAll(); };
    }
    function updateSlice(id, key, value) {
      const s = currentManualPage().slices.find(x => x.id === id);
      if (s) s[key] = value;
      renderAll();
    }
    function updateBBox(id, key, value) {
      const s = currentManualPage().slices.find(x => x.id === id);
      if (s) { s.bbox[key] = Math.max(0, Number(value) || 0); s.bbox = clampBox(s.bbox); }
      renderAll();
    }
    function updateHud(point=null) {
      const slice = activeSlice();
      const zoom = `${Math.round(state.view.scale * 100)}%`;
      if (state.drag?.draft) hud.textContent = `draw x:${state.drag.draft.x} y:${state.drag.draft.y} w:${state.drag.draft.width} h:${state.drag.draft.height} zoom:${zoom}`;
      else if (slice) hud.textContent = `${slice.name} x:${slice.bbox.x} y:${slice.bbox.y} w:${slice.bbox.width} h:${slice.bbox.height} zoom:${zoom}`;
      else if (point) hud.textContent = `x:${point.x} y:${point.y} zoom:${zoom}`;
      else hud.textContent = `zoom:${zoom}`;
    }
    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
    }
    async function saveManual() {
      setStatus("saving...");
      await api("/manual-slices", { method: "PUT", headers: {"Content-Type":"application/json"}, body: JSON.stringify(state.manual) });
      setStatus("saved");
    }
    async function exportProject() {
      try {
        await saveManual();
        setStatus("exporting...");
        await api("/export", { method: "POST" });
        const link = document.getElementById("download");
        link.href = `/api/pencil/slice-projects/${projectId}/download.zip`;
        link.style.display = "inline";
        setStatus("exported");
      } catch (error) {
        setStatus(error.message || String(error), true);
      }
    }
    document.getElementById("mode-select").onclick = () => setMode("select");
    document.getElementById("mode-draw").onclick = () => setMode("draw");
    document.getElementById("pan").onclick = () => setMode("pan");
    document.getElementById("fit").onclick = fitToScreen;
    document.getElementById("zoom100").onclick = () => { const rect = canvas.getBoundingClientRect(); setZoom(1, { x: rect.width / 2, y: rect.height / 2 }); };
    document.getElementById("zoomOut").onclick = () => zoomBy(0.8);
    document.getElementById("zoomIn").onclick = () => zoomBy(1.25);
    document.getElementById("delete").onclick = deleteActive;
    document.getElementById("save").onclick = () => saveManual().catch(error => setStatus(error.message || String(error), true));
    document.getElementById("export").onclick = exportProject;
    function setMode(mode) {
      state.mode = mode;
      for (const id of ["mode-select", "mode-draw", "pan"]) document.getElementById(id).classList.remove("active");
      if (mode === "select") document.getElementById("mode-select").classList.add("active");
      if (mode === "draw") document.getElementById("mode-draw").classList.add("active");
      if (mode === "pan") document.getElementById("pan").classList.add("active");
    }
    window.addEventListener("keydown", event => {
      if (event.target && ["INPUT", "SELECT", "TEXTAREA"].includes(event.target.tagName)) return;
      if (event.code === "Space") { state.spaceDown = true; event.preventDefault(); }
      if (event.key === "Delete" || event.key === "Backspace") { deleteActive(); event.preventDefault(); }
      if (event.key === "Escape") { state.drag = null; state.activeId = null; renderAll(); event.preventDefault(); }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") { saveManual().catch(error => setStatus(error.message || String(error), true)); event.preventDefault(); }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "d") { duplicateActive(); event.preventDefault(); }
      const step = event.shiftKey ? 10 : 1;
      if (event.key === "ArrowLeft") { moveActive(-step, 0); event.preventDefault(); }
      if (event.key === "ArrowRight") { moveActive(step, 0); event.preventDefault(); }
      if (event.key === "ArrowUp") { moveActive(0, -step); event.preventDefault(); }
      if (event.key === "ArrowDown") { moveActive(0, step); event.preventDefault(); }
    });
    window.addEventListener("keyup", event => { if (event.code === "Space") state.spaceDown = false; });
    window.loadPage = loadPage; window.focusSlice = focusSlice; window.updateSlice = updateSlice; window.updateBBox = updateBBox;
    load().catch(error => setStatus(error.message || String(error), true));
  </script>
</body>
</html>
"""
