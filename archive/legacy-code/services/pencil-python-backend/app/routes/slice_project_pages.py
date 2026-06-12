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


WORKSPACE_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Pencil Slice Workspace</title>
  <link rel="icon" href="data:," />
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #070b14; color: #e5e7eb; }
    .shell { display: grid; grid-template-columns: 340px minmax(0, 1fr); min-height: 100vh; }
    aside { border-right: 1px solid #263244; background: #0f172a; padding: 20px; }
    main { padding: 22px; min-width: 0; }
    h1, h2, h3 { margin: 0; }
    h1 { font-size: 22px; margin-bottom: 8px; }
    h2 { font-size: 16px; margin: 22px 0 12px; }
    h3 { font-size: 15px; margin-bottom: 8px; }
    .muted { color: #94a3b8; font-size: 12px; line-height: 1.5; }
    label { display: block; margin: 12px 0 6px; color: #cbd5e1; font-size: 13px; }
    input, select, button { border: 1px solid #334155; background: #111827; color: #e5e7eb; border-radius: 6px; padding: 9px 10px; font: inherit; }
    input, select { width: 100%; }
    input[type="checkbox"] { width: auto; margin-right: 8px; }
    button { cursor: pointer; }
    button.primary { background: #16a34a; border-color: #22c55e; }
    button.warn { background: #7f1d1d; border-color: #ef4444; }
    button.secondary { background: #1f2937; }
    button:disabled { opacity: .55; cursor: progress; }
    .row { display: grid; grid-template-columns: minmax(0, 1fr) 130px; gap: 10px; }
    .check { display: flex; align-items: center; margin-top: 12px; }
    .status { min-height: 20px; margin-top: 12px; color: #93c5fd; font-size: 13px; white-space: pre-wrap; }
    .topbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
    .topbar-actions { display: flex; align-items: center; gap: 10px; }
    .projects { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 14px; }
    .card { border: 1px solid #263244; background: #0f172a; border-radius: 8px; overflow: hidden; }
    .card-body { display: grid; grid-template-columns: 92px minmax(0, 1fr); gap: 12px; padding: 12px; }
    .thumb { width: 92px; height: 120px; object-fit: cover; background: #020617; border: 1px solid #334155; border-radius: 6px; }
    .card-title { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
    .card-title strong { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .badge { display: inline-flex; align-items: center; border: 1px solid #334155; border-radius: 999px; color: #cbd5e1; font-size: 11px; padding: 2px 7px; white-space: nowrap; }
    .badge.done { border-color: #16a34a; color: #86efac; }
    .badge.broken { border-color: #ef4444; color: #fca5a5; }
    .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin: 10px 0; }
    .stat { background: #111827; border: 1px solid #263244; border-radius: 6px; padding: 7px; }
    .stat span { display: block; color: #94a3b8; font-size: 11px; }
    .stat strong { display: block; margin-top: 3px; font-size: 15px; }
    .actions { display: flex; flex-wrap: wrap; gap: 8px; padding: 0 12px 12px; }
    .actions a, .actions button { text-decoration: none; color: #e5e7eb; font-size: 13px; }
    .actions a { border: 1px solid #334155; background: #1f2937; border-radius: 6px; padding: 8px 10px; }
    .empty { border: 1px dashed #334155; border-radius: 8px; padding: 40px; text-align: center; color: #94a3b8; }
  </style>
</head>
<body>
  <div class="shell">
    <aside>
      <h1>Pencil Slice Workspace</h1>
      <p class="muted">自动候选只负责提示，用户确认的 manual_slices 才是最终交付真相源。</p>
      <h2>新建项目</h2>
      <form id="createForm">
        <label for="files">Images</label>
        <input id="files" name="files[]" type="file" accept="image/png,image/jpeg,image/webp" multiple required />
        <div class="row">
          <div>
            <label for="projectName">Project name</label>
            <input id="projectName" name="projectName" value="Assisted Slice Project" />
          </div>
          <div>
            <label for="boundarySource">Source</label>
            <select id="boundarySource" name="boundarySource">
              <option value="psdlike" selected>psdlike</option>
              <option value="m29">m29</option>
              <option value="hybrid">hybrid</option>
            </select>
          </div>
        </div>
        <label class="check"><input id="includeDebug" name="includeDebug" type="checkbox" checked /> include debug</label>
        <button id="createButton" class="primary" type="submit" style="width:100%;margin-top:14px">创建并打开</button>
      </form>
      <div id="createStatus" class="status"></div>
    </aside>
    <main>
      <div class="topbar">
        <div>
          <h1>项目</h1>
          <div id="summary" class="muted">loading</div>
        </div>
        <div class="topbar-actions">
          <button class="secondary" onclick="loadProjects()">刷新</button>
          <a class="muted" href="/api/pencil/slice-projects/new">旧上传页</a>
        </div>
      </div>
      <div id="projects" class="projects"></div>
    </main>
  </div>
  <script>
    const projectsEl = document.getElementById("projects");
    const summaryEl = document.getElementById("summary");
    const createStatus = document.getElementById("createStatus");
    const createButton = document.getElementById("createButton");

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
    }
    function escapeAttr(value) {
      return escapeHtml(value).replace(/`/g, "&#96;");
    }
    function setCreateStatus(text, error=false) {
      createStatus.textContent = text;
      createStatus.style.color = error ? "#fca5a5" : "#93c5fd";
    }
    async function request(url, options={}) {
      const response = await fetch(url, options);
      let payload = null;
      try { payload = await response.json(); } catch (_) {}
      if (!response.ok) throw new Error((payload && payload.detail) || response.statusText);
      return payload ? payload.data : null;
    }
    async function loadProjects() {
      summaryEl.textContent = "loading";
      try {
        const data = await request("/api/pencil/slice-projects");
        renderProjects(data.projects || []);
      } catch (error) {
        summaryEl.textContent = error.message || String(error);
      }
    }
    function renderProjects(projects) {
      summaryEl.textContent = `${projects.length} 个项目`;
      if (!projects.length) {
        projectsEl.innerHTML = '<div class="empty">还没有项目。上传图片后会出现在这里。</div>';
        return;
      }
      projectsEl.innerHTML = projects.map(project => {
        const statusClass = project.status === "broken" ? "broken" : project.exported ? "done" : "";
        const thumb = project.thumbnailUrl || "";
        const updated = project.updatedAt ? new Date(project.updatedAt).toLocaleString() : "--";
        return `<article class="card">
          <div class="card-body">
            ${thumb ? `<img class="thumb" src="${thumb}" alt="">` : `<div class="thumb"></div>`}
            <div>
              <div class="card-title">
                <strong title="${escapeHtml(project.projectName)}">${escapeHtml(project.projectName)}</strong>
                <span class="badge ${statusClass}">${escapeHtml(project.status || "unknown")}</span>
              </div>
              <div class="muted">${escapeHtml(project.projectId)}<br>${updated}</div>
              <div class="stats">
                <div class="stat"><span>Pages</span><strong>${project.completedPageCount || 0}/${project.pageCount || 0}</strong></div>
                <div class="stat"><span>Candidates</span><strong>${project.candidateCount || 0}</strong></div>
                <div class="stat"><span>Selected</span><strong>${project.selectedSliceCount || 0}</strong></div>
              </div>
              <div class="muted">${project.rejectedCandidateCount || 0} rejected / ${project.exported ? "exported" : "not exported"}</div>
            </div>
          </div>
          <div class="actions">
            <a href="${project.reviewUrl || "#"}">继续处理</a>
            ${project.exported ? `<a href="/api/pencil/slice-projects/${project.projectId}/download.zip">项目包</a><a href="/api/pencil/slice-projects/${project.projectId}/selected-assets.zip">资源包</a>` : ""}
            <button data-project-id="${escapeAttr(project.projectId)}" data-project-name="${escapeAttr(project.projectName)}" onclick="renameProject(this.dataset.projectId, this.dataset.projectName)">重命名</button>
            <button data-project-id="${escapeAttr(project.projectId)}" onclick="cloneProject(this.dataset.projectId)">复制</button>
            <button class="warn" data-project-id="${escapeAttr(project.projectId)}" onclick="deleteProject(this.dataset.projectId)">删除</button>
          </div>
        </article>`;
      }).join("");
    }
    async function renameProject(projectId, oldName) {
      const projectName = prompt("项目名称", oldName || "Assisted Slice Project");
      if (!projectName) return;
      await request(`/api/pencil/slice-projects/${projectId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ projectName })
      });
      await loadProjects();
    }
    async function cloneProject(projectId) {
      const data = await request(`/api/pencil/slice-projects/${projectId}/clone`, { method: "POST" });
      window.location.href = data.reviewUrl;
    }
    async function deleteProject(projectId) {
      if (!confirm(`删除项目 ${projectId}？这个操作不可恢复。`)) return;
      await request(`/api/pencil/slice-projects/${projectId}`, { method: "DELETE" });
      await loadProjects();
    }
    document.getElementById("createForm").addEventListener("submit", async event => {
      event.preventDefault();
      const files = document.getElementById("files").files;
      if (!files.length) { setCreateStatus("请选择至少一张图片。", true); return; }
      const body = new FormData();
      for (const file of files) body.append("files[]", file);
      body.append("projectName", document.getElementById("projectName").value || "Assisted Slice Project");
      body.append("boundarySource", document.getElementById("boundarySource").value);
      body.append("includeDebug", document.getElementById("includeDebug").checked ? "true" : "false");
      createButton.disabled = true;
      setCreateStatus("creating...");
      try {
        const data = await request("/api/pencil/slice-projects", { method: "POST", body });
        window.location.href = data.reviewUrl || `/api/pencil/slice-projects/${data.projectId}/review`;
      } catch (error) {
        setCreateStatus(error.message || String(error), true);
        createButton.disabled = false;
      }
    });
    window.loadProjects = loadProjects;
    window.renameProject = renameProject;
    window.cloneProject = cloneProject;
    window.deleteProject = deleteProject;
    loadProjects();
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
    button.secondary { background: #374151; border-color: #4b5563; }
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
    .asset.unselected { opacity: .58; }
    .asset-head { display: grid; grid-template-columns: 84px minmax(0, 1fr); gap: 8px; align-items: start; }
    .slice-thumb, .page-thumb { border: 1px solid #334155; background: #020617; object-fit: contain; }
    .slice-thumb { width: 84px; height: 64px; border-radius: 6px; }
    .asset input, .asset select { width: 100%; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-top: 6px; }
    .muted { color: #94a3b8; font-size: 12px; }
    .status { margin-left: auto; color: #94a3b8; font-size: 12px; }
    .hud { position: absolute; left: 12px; bottom: 12px; background: rgba(15, 23, 42, .86); border: 1px solid #334155; border-radius: 6px; padding: 6px 8px; color: #cbd5e1; font-size: 12px; pointer-events: none; }
    .page-row { display: grid; grid-template-columns: 54px minmax(0, 1fr); gap: 8px; align-items: center; }
    .page-thumb { width: 54px; height: 74px; border-radius: 4px; }
    .page-meta { display: grid; gap: 2px; min-width: 0; }
    .page-state { display: inline-block; width: max-content; border-radius: 999px; padding: 1px 6px; font-size: 11px; border: 1px solid #334155; color: #cbd5e1; }
    .page-state.dirty { border-color: #f59e0b; color: #fcd34d; }
    .page-state.saved { border-color: #16a34a; color: #86efac; }
    .page-state.failed { border-color: #ef4444; color: #fca5a5; }
    .bulkbar { display: grid; gap: 8px; margin-bottom: 12px; border-bottom: 1px solid #263244; padding-bottom: 12px; }
    .search { margin-bottom: 10px; }
    .tagline { display: grid; grid-template-columns: minmax(0, 1fr) 82px; gap: 6px; margin-top: 6px; }
    .preview-links { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
    .preview-links a { color: #86efac; }
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
        <button id="mode-candidate-box">框选候选</button>
        <button id="pan">平移</button>
        <button id="fit">适屏</button>
        <button id="zoom100">100%</button>
        <button id="zoomOut">-</button>
        <button id="zoomIn">+</button>
        <button id="delete" class="warn">删除</button>
        <button id="save">保存</button>
        <button id="previewExport">导出预览</button>
        <button id="export" class="primary">导出</button>
        <a id="download" style="display:none;color:#86efac" href="#">项目包</a>
        <a id="selectedDownload" style="display:none;color:#86efac" href="#">资源包</a>
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
        <div class="filter-row" id="tierFilters"></div>
        <div class="filter-row">
          <label><input id="onlyTodoPages" type="checkbox" /> 未处理页</label>
          <label><input id="onlySelectedPages" type="checkbox" /> 已选择页</label>
          <label><input id="onlyDensePages" type="checkbox" /> 候选多</label>
        </div>
      </div>
      <div class="bulkbar">
        <h3>Candidate Batch <span id="candidateSelectionCount" class="muted"></span></h3>
        <div class="filter-row">
          <button class="secondary" onclick="bulkAddCandidates()">加入选中候选</button>
          <button class="secondary" onclick="rejectSelectedCandidates()">拒绝候选</button>
          <button class="secondary" onclick="restoreRejectedOnPage()">恢复本页拒绝</button>
          <button class="secondary" onclick="clearCandidateSelection()">清空候选选择</button>
        </div>
        <div class="muted">用“框选候选”模式拖出矩形，批量选择当前可见候选。</div>
        <div id="previewLinks" class="preview-links"></div>
      </div>
      <h3>Selected Slices <span id="selectedCount" class="muted"></span></h3>
      <input id="assetSearch" class="search" placeholder="搜索 selected assets" />
      <div class="filter-row" style="margin-bottom:10px">
        <label><input id="assetAllPages" type="checkbox" checked /> 全项目</label>
        <button class="secondary" onclick="bulkRenameSlices()">批量重命名</button>
        <button class="warn" onclick="bulkDeleteVisibleSlices()">删除可见</button>
      </div>
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
    const tierOptions = ["recommended", "normal", "noise", "text", "rejected"];
    const colors = { image: "#22c55e", icon: "#22c55e", text: "#ef4444", shape: "#3b82f6", group: "#f59e0b", unknown: "#eab308", full_screen: "#64748b", upper_region: "#64748b", middle_region: "#64748b", lower_region: "#64748b" };
    const state = {
      candidates: null, manual: null, reviewState: null, pageIndex: 0, mode: "select", image: null, activeId: null, drag: null,
      hoverCandidateId: null, hoverSliceId: null, pageImages: {}, pageSaveState: {},
      selectedCandidateIds: new Set(), assetSearch: "",
      reviewSaveTimer: null, reviewSavePromise: null, reviewSaveRevision: 0, lastSavedReviewRevision: 0,
      view: { scale: 1, offsetX: 40, offsetY: 40 }, spaceDown: false,
      autosaveTimer: null, savePromise: null, saveRevision: 0, lastSavedRevision: 0,
      assetAllPages: true,
      history: { undo: [], redo: [], limit: 50, restoring: false },
      filters: {
        showCandidates: true, showSelected: true, showLabels: true, minConfidence: 0, candidateOpacity: 0.75,
        kinds: { image: true, icon: true, text: false, shape: true, group: true, unknown: true },
        sources: { psdlike: true, m29: true, foreground_audit: true, source: true, manual: true },
        tiers: { recommended: true, normal: true, noise: false, text: false, rejected: false },
        onlyTodoPages: false, onlySelectedPages: false, onlyDensePages: false
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
      state.project = await api("");
      state.candidates = await api("/candidates");
      state.manual = await api("/manual-slices");
      state.reviewState = await api("/review-state");
      hydrateReviewFilters();
      for (const page of state.candidates.pages) state.pageSaveState[page.pageId] = "saved";
      renderFilterControls();
      const savedPage = state.candidates.pages.findIndex(page => page.pageId === state.reviewState.lastActivePageId);
      renderPages();
      await loadPage(savedPage >= 0 ? savedPage : 0);
      syncExportLinks(state.project);
      setStatus("ready");
    }
    function currentCandidatePage() { return state.candidates.pages[state.pageIndex]; }
    function currentManualPage() { return state.manual.pages[state.pageIndex]; }
    function currentReviewPage() {
      const pageId = currentCandidatePage().pageId;
      let page = state.reviewState.pages.find(item => item.pageId === pageId);
      if (!page) {
        page = { pageId, rejectedCandidateIds: [], hiddenCandidateIds: [], lastFilter: {} };
        state.reviewState.pages.push(page);
      }
      return page;
    }
    async function loadPage(index) {
      state.pageIndex = index;
      state.activeId = null;
      state.selectedCandidateIds.clear();
      const page = currentCandidatePage();
      state.hoverCandidateId = null;
      state.hoverSliceId = null;
      state.reviewState.lastActivePageId = page.pageId;
      scheduleReviewStateSave();
      state.image = await imageForPage(page.pageId);
      resizeCanvas();
      fitToScreen();
      renderPages();
      renderAssets();
    }
    function hydrateReviewFilters() {
      const saved = state.reviewState && typeof state.reviewState.filters === "object" ? state.reviewState.filters : {};
      mergeFilterGroup(state.filters, saved);
      if (typeof saved.assetAllPages === "boolean") state.assetAllPages = saved.assetAllPages;
    }
    function mergeFilterGroup(target, source) {
      if (!source || typeof source !== "object") return;
      for (const [key, value] of Object.entries(source)) {
        if (!(key in target)) continue;
        if (target[key] && typeof target[key] === "object" && !Array.isArray(target[key])) mergeFilterGroup(target[key], value);
        else if (typeof value === typeof target[key]) target[key] = value;
      }
    }
    function persistReviewFilters() {
      state.reviewState.filters = JSON.parse(JSON.stringify(state.filters));
      state.reviewState.filters.assetAllPages = state.assetAllPages;
      scheduleReviewStateSave();
    }
    function syncExportLinks(project) {
      if (!project || !project.exported) return;
      const link = document.getElementById("download");
      link.href = project.downloadUrl || `/api/pencil/slice-projects/${projectId}/download.zip`;
      link.style.display = "inline";
      const selectedLink = document.getElementById("selectedDownload");
      selectedLink.href = project.selectedAssetsDownloadUrl || `/api/pencil/slice-projects/${projectId}/selected-assets.zip`;
      selectedLink.style.display = "inline";
    }
    function imageForPage(pageId) {
      if (state.pageImages[pageId]?.complete) return Promise.resolve(state.pageImages[pageId]);
      if (state.pageImages[pageId]?.promise) return state.pageImages[pageId].promise;
      const image = new Image();
      image.src = `/api/pencil/slice-projects/${projectId}/source/${pageId}`;
      const promise = new Promise((resolve, reject) => {
        image.onload = () => {
          state.pageImages[pageId] = image;
          resolve(image);
        };
        image.onerror = () => reject(new Error(`failed to load source image: ${pageId}`));
      });
      state.pageImages[pageId] = { promise };
      return promise;
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
      return clampBoxForPage(b, currentCandidatePage());
    }
    function clampBoxForPage(b, page) {
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
          const active = candidate.id === state.hoverCandidateId || state.selectedCandidateIds.has(candidate.id);
          const tier = candidateTier(candidate);
          const selected = state.selectedCandidateIds.has(candidate.id);
          const color = tier === "rejected" ? "#64748b" : selected ? "#a78bfa" : colors[candidate.kind] || colors.unknown;
          const label = `${candidate.id.split("_").pop()} ${tier.slice(0, 1)}`;
          drawBox(candidate.bbox, color, label, active, tier === "rejected" ? Math.min(.45, state.filters.candidateOpacity) : state.filters.candidateOpacity, tier === "rejected" ? "dashed" : "solid");
        }
      }
      if (state.filters.showSelected) {
        for (const slice of currentManualPage().slices) {
          if (slice.selected !== false) drawBox(slice.bbox, "#ffffff", slice.name, slice.id === state.activeId || slice.id === state.hoverSliceId, slice.id === state.activeId ? 1 : .86);
        }
      }
      if (state.drag?.draft) drawBox(state.drag.draft, state.drag.action === "candidateBox" ? "#a78bfa" : "#f97316", state.drag.action === "candidateBox" ? "select" : "new", true, 1);
      ctx.restore();
    }
    function drawBox(b, color, label, active, alpha, style="solid") {
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.strokeStyle = color;
      ctx.lineWidth = (active ? 3 : 2) / state.view.scale;
      if (style === "dashed") ctx.setLineDash([6 / state.view.scale, 5 / state.view.scale]);
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
      const rejected = new Set(currentReviewPage().rejectedCandidateIds || []);
      return currentCandidatePage().candidates.filter(candidate => {
        const kind = state.filters.kinds[candidate.kind] !== undefined ? candidate.kind : "unknown";
        const source = state.filters.sources[candidate.source] !== undefined ? candidate.source : "manual";
        const tier = candidateTier(candidate, rejected);
        return state.filters.kinds[kind] && state.filters.sources[source] && state.filters.tiers[tier] && Number(candidate.confidence || 0) >= state.filters.minConfidence;
      });
    }
    function candidateTier(candidate, rejectedSet=null) {
      const rejected = rejectedSet || new Set(currentReviewPage().rejectedCandidateIds || []);
      if (rejected.has(candidate.id)) return "rejected";
      if (candidate.kind === "text") return "text";
      const page = currentCandidatePage();
      const areaRatio = (candidate.bbox.width * candidate.bbox.height) / Math.max(1, page.width * page.height);
      const reason = String(candidate.reason || "");
      if (areaRatio > 0.62 || reason.includes("layout_region") || candidate.kind === "full_screen") return "noise";
      if (Number(candidate.confidence || 0) >= 0.72 || candidate.source === "foreground_audit" || reason.includes("foreground")) return "recommended";
      return "normal";
    }
    function boxesIntersect(a, b) {
      return a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
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
    function manualSnapshot() { return JSON.stringify(state.manual); }
    function restoreManualSnapshot(snapshot) {
      state.history.restoring = true;
      state.manual = JSON.parse(snapshot);
      state.history.restoring = false;
      if (!state.manual.pages[state.pageIndex]) state.pageIndex = 0;
      state.activeId = null;
      state.saveRevision += 1;
      for (const page of state.manual.pages) state.pageSaveState[page.pageId] = "dirty";
      setStatus("dirty");
      renderPages();
      scheduleAutosave();
      renderAll();
    }
    function pushUndoSnapshot() {
      if (state.history.restoring) return;
      state.history.undo.push(manualSnapshot());
      if (state.history.undo.length > state.history.limit) state.history.undo.shift();
      state.history.redo = [];
    }
    function mutateManual(fn, pageId=currentManualPage()?.pageId) {
      pushUndoSnapshot();
      fn();
      markDirty(pageId);
      scheduleAutosave();
      renderAll();
    }
    function mutateManualForPages(pageIds, fn) {
      pushUndoSnapshot();
      fn();
      const unique = [...new Set(pageIds.filter(Boolean))];
      state.saveRevision += 1;
      for (const pageId of unique) state.pageSaveState[pageId] = "dirty";
      setStatus("dirty");
      renderPages();
      scheduleAutosave();
      renderAll();
    }
    function undoManual() {
      if (!state.history.undo.length) return;
      state.history.redo.push(manualSnapshot());
      restoreManualSnapshot(state.history.undo.pop());
    }
    function redoManual() {
      if (!state.history.redo.length) return;
      state.history.undo.push(manualSnapshot());
      restoreManualSnapshot(state.history.redo.pop());
    }
    function markDirty(pageId=currentManualPage()?.pageId) {
      state.saveRevision += 1;
      if (pageId) state.pageSaveState[pageId] = "dirty";
      setStatus("dirty");
      renderPages();
    }
    function markSaved() {
      for (const page of state.manual.pages) state.pageSaveState[page.pageId] = "saved";
      renderPages();
    }
    function markSaveFailed() {
      for (const page of state.manual.pages) if (state.pageSaveState[page.pageId] === "dirty") state.pageSaveState[page.pageId] = "failed";
      renderPages();
    }
    function scheduleAutosave() {
      clearTimeout(state.autosaveTimer);
      state.autosaveTimer = setTimeout(() => saveManual({ quiet: true }).catch(error => setStatus(error.message || String(error), true)), 500);
    }
    async function flushAutosave() {
      if (state.autosaveTimer) {
        clearTimeout(state.autosaveTimer);
        state.autosaveTimer = null;
        await saveManual({ quiet: true });
      }
      if (state.savePromise) await state.savePromise;
      if (state.lastSavedRevision < state.saveRevision) await saveManual({ quiet: true });
    }
    function pageByOffset(delta) {
      const next = Math.max(0, Math.min(state.candidates.pages.length - 1, state.pageIndex + delta));
      if (next !== state.pageIndex) loadPage(next);
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
      if (state.mode === "candidateBox") {
        state.drag = { action: "candidateBox", start: p, draft: clampBox({ x: p.x, y: p.y, width: 1, height: 1 }) };
        return;
      }
      const slice = hit(currentManualPage().slices.filter(item => item.selected !== false), p);
      if (slice) {
        state.activeId = slice.id;
        const handle = hitHandle(slice, screenToImage(screen));
        pushUndoSnapshot();
        state.drag = { id: slice.id, action: handle ? "resize" : "move", handle, start: p, original: { ...slice.bbox }, pageId: currentManualPage().pageId };
        renderAll(); return;
      }
      const candidate = hit(filteredCandidates(), p);
      if (candidate) {
        state.activeId = null;
        if (state.selectedCandidateIds.has(candidate.id)) state.selectedCandidateIds.delete(candidate.id);
        else state.selectedCandidateIds.add(candidate.id);
        renderAll();
        return;
      }
      state.activeId = null;
      state.hoverCandidateId = null;
      state.hoverSliceId = null;
      renderAll();
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
        } else if (state.drag.action === "draw" || state.drag.action === "candidateBox") {
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
        const hoveredSlice = hit(currentManualPage().slices.filter(item => item.selected !== false), p);
        const hoveredCandidate = hoveredSlice ? null : hit(filteredCandidates(), p);
        const nextSliceId = hoveredSlice?.id || null;
        const nextCandidateId = hoveredCandidate?.id || null;
        if (nextSliceId !== state.hoverSliceId || nextCandidateId !== state.hoverCandidateId) {
          state.hoverSliceId = nextSliceId;
          state.hoverCandidateId = nextCandidateId;
          renderAll();
        }
        canvas.style.cursor = nextSliceId ? "move" : nextCandidateId ? "crosshair" : state.mode === "pan" ? "grab" : "default";
        updateHud(p);
      }
    });
    window.addEventListener("mouseup", () => {
      if (state.drag?.action === "draw" && state.drag.draft.width > 4 && state.drag.draft.height > 4) addManualSlice(state.drag.draft);
      if (state.drag?.action === "candidateBox" && state.drag.draft.width > 4 && state.drag.draft.height > 4) selectCandidatesInBox(state.drag.draft);
      if (state.drag?.action === "move" || state.drag?.action === "resize") {
        markDirty(state.drag.pageId);
        scheduleAutosave();
      }
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
      mutateManual(() => {
        const page = currentManualPage();
        const id = `${page.pageId}__slice_${Date.now()}_${Math.floor(Math.random()*1000)}`;
        const name = `slice_${page.slices.length + 1}`;
        page.slices.push({ id, name, displayName: name, kind: normalizeKind(candidate.kind), tags: [], reviewState: "confirmed", bbox: clampBox({...candidate.bbox}), selected: true, exportMode: "rect", source: "candidate_confirmed", candidateIds: [candidate.id] });
        state.activeId = id;
      });
    }
    function addManualSlice(bbox) {
      mutateManual(() => {
        const page = currentManualPage();
        const id = `${page.pageId}__slice_${Date.now()}_${Math.floor(Math.random()*1000)}`;
        const name = `slice_${page.slices.length + 1}`;
        page.slices.push({ id, name, displayName: name, kind: "image", tags: [], reviewState: "confirmed", bbox: clampBox(bbox), selected: true, exportMode: "rect", source: "manual", candidateIds: [] });
        state.activeId = id;
      });
    }
    function duplicateActive() {
      const slice = activeSlice();
      if (!slice) return;
      mutateManual(() => {
        const page = currentManualPage();
        const id = `${page.pageId}__slice_${Date.now()}_${Math.floor(Math.random()*1000)}`;
        page.slices.push({ ...slice, id, name: `${slice.name}_copy`, bbox: clampBox({ ...slice.bbox, x: slice.bbox.x + 12, y: slice.bbox.y + 12 }) });
        state.activeId = id;
      });
    }
    function activeSlice() { return currentManualPage().slices.find(item => item.id === state.activeId); }
    function deleteActive() {
      if (!state.activeId) return;
      mutateManual(() => {
        const page = currentManualPage();
        page.slices = page.slices.filter(item => item.id !== state.activeId);
        state.activeId = null;
      });
    }
    function moveActive(dx, dy) {
      const slice = activeSlice();
      if (!slice) return;
      mutateManual(() => { slice.bbox = moveBox(slice.bbox, dx, dy); });
    }
    function normalizeKind(kind) { return kindOptions.includes(kind) ? kind : "unknown"; }
    function sliceDefaults(candidate, index) {
      const page = currentManualPage();
      const id = `${page.pageId}__slice_${Date.now()}_${Math.floor(Math.random()*1000)}_${index}`;
      return {
        id,
        name: `slice_${page.slices.length + index}`,
        displayName: `slice_${page.slices.length + index}`,
        kind: normalizeKind(candidate.kind),
        tags: [],
        reviewState: "confirmed",
        bbox: clampBox({...candidate.bbox}),
        selected: true,
        exportMode: "rect",
        source: "candidate_confirmed",
        candidateIds: [candidate.id]
      };
    }
    function selectCandidatesInBox(bbox) {
      for (const candidate of filteredCandidates()) {
        if (boxesIntersect(candidate.bbox, bbox)) state.selectedCandidateIds.add(candidate.id);
      }
      renderAll();
    }
    function selectedCandidates() {
      const visibleIds = new Set(filteredCandidates().map(candidate => candidate.id));
      return currentCandidatePage().candidates.filter(candidate => state.selectedCandidateIds.has(candidate.id) && visibleIds.has(candidate.id));
    }
    function bulkAddCandidates() {
      const candidates = selectedCandidates();
      if (!candidates.length) return;
      let added = 0;
      mutateManual(() => {
        const page = currentManualPage();
        const existingCandidateIds = new Set(page.slices.flatMap(slice => slice.candidateIds || []));
        for (const candidate of candidates) {
          if (existingCandidateIds.has(candidate.id)) continue;
          added += 1;
          page.slices.push(sliceDefaults(candidate, added));
        }
        if (added) state.activeId = page.slices[page.slices.length - 1].id;
      });
      state.selectedCandidateIds.clear();
      setStatus(added ? `added ${added} candidate(s)` : "no new candidates");
      renderAll();
    }
    function rejectSelectedCandidates() {
      const ids = [...state.selectedCandidateIds];
      if (!ids.length) return;
      const reviewPage = currentReviewPage();
      reviewPage.rejectedCandidateIds = [...new Set([...(reviewPage.rejectedCandidateIds || []), ...ids])];
      state.selectedCandidateIds.clear();
      scheduleReviewStateSave();
      setStatus(`rejected ${ids.length} candidate(s)`);
      renderAll();
    }
    function restoreRejectedOnPage() {
      const count = (currentReviewPage().rejectedCandidateIds || []).length;
      currentReviewPage().rejectedCandidateIds = [];
      state.selectedCandidateIds.clear();
      scheduleReviewStateSave();
      setStatus(`restored ${count} rejected candidate(s)`);
      renderAll();
    }
    function clearCandidateSelection() {
      state.selectedCandidateIds.clear();
      renderAll();
    }
    function scheduleReviewStateSave() {
      state.reviewSaveRevision += 1;
      clearTimeout(state.reviewSaveTimer);
      state.reviewSaveTimer = setTimeout(() => saveReviewState().catch(error => setStatus(error.message || String(error), true)), 400);
    }
    async function flushReviewStateSave() {
      if (state.reviewSaveTimer) {
        clearTimeout(state.reviewSaveTimer);
        state.reviewSaveTimer = null;
        await saveReviewState();
      }
      if (state.reviewSavePromise) await state.reviewSavePromise;
    }
    async function saveReviewState() {
      if (state.reviewSavePromise) {
        await state.reviewSavePromise;
        if (state.lastSavedReviewRevision >= state.reviewSaveRevision) return;
      }
      const revision = state.reviewSaveRevision;
      state.reviewSavePromise = api("/review-state", {
        method: "PUT",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(state.reviewState)
      }).then(() => {
        state.lastSavedReviewRevision = Math.max(state.lastSavedReviewRevision, revision);
      }).finally(() => { state.reviewSavePromise = null; });
      await state.reviewSavePromise;
      if (state.lastSavedReviewRevision < state.reviewSaveRevision) return saveReviewState();
    }

    function renderPages() {
      const visiblePages = state.candidates.pages
        .map((page, i) => ({ page, i }))
        .filter(({ page }) => {
          const manualPage = state.manual.pages.find(item => item.pageId === page.pageId);
          const selected = (manualPage?.slices || []).filter(item => item.selected !== false).length;
          if (state.filters.onlyTodoPages && selected > 0) return false;
          if (state.filters.onlySelectedPages && selected === 0) return false;
          if (state.filters.onlyDensePages && (page.candidates || []).length < 40) return false;
          return true;
        });
      document.getElementById("pages").innerHTML = visiblePages.map(({ page, i }) => {
        const manualPage = state.manual.pages.find(item => item.pageId === page.pageId);
        const count = (manualPage?.slices || []).filter(item => item.selected !== false).length;
        const saveState = state.pageSaveState[page.pageId] || "saved";
        const candidateCount = (page.candidates || []).length;
        const reviewPage = state.reviewState.pages.find(item => item.pageId === page.pageId) || {};
        const rejectedCount = (reviewPage.rejectedCandidateIds || []).length;
        const pageStatus = count > 0 ? "ready" : "untouched";
        const thumb = `/api/pencil/slice-projects/${projectId}/source/${page.pageId}`;
        return `<button class="page-btn ${i === state.pageIndex ? "active" : ""}" onclick="loadPage(${i})">
          <div class="page-row">
            <img class="page-thumb" src="${thumb}" alt="${page.pageId}" />
            <span class="page-meta">
              <span>${page.pageId}<span class="count">${count}</span></span>
              <span class="muted">${page.width}x${page.height}</span>
              <span class="muted">${candidateCount} candidates / ${count} selected / ${rejectedCount} rejected</span>
              <span><span class="page-state ${saveState}">${saveState}</span> <span class="page-state ${pageStatus === "ready" ? "saved" : ""}">${pageStatus}</span></span>
            </span>
          </div>
        </button>`;
      }).join("");
    }
    function renderAssets() {
      const selectedCount = totalSelectedSliceCount();
      document.getElementById("selectedCount").textContent = `(${selectedCount})`;
      const visibleRefs = visibleAssetRefs();
      document.getElementById("assets").innerHTML = visibleRefs.map(ref => {
        const slice = ref.slice;
        return `
        <div class="asset ${slice.id === state.activeId ? "active" : ""} ${slice.selected === false ? "unselected" : ""}" onclick="focusSlice('${slice.id}', ${ref.pageIndex})">
          <div class="asset-head">
            <canvas class="slice-thumb" data-thumb-slice-id="${slice.id}" width="84" height="64"></canvas>
            <div>
              <input name="${slice.id}__displayName" value="${escapeHtml(slice.displayName || slice.name)}" onclick="event.stopPropagation()" onchange="updateSlice('${slice.id}', 'displayName', this.value, ${ref.pageIndex})" />
              <input name="${slice.id}__name" value="${escapeHtml(slice.name)}" onclick="event.stopPropagation()" onchange="updateSlice('${slice.id}', 'name', safeName(this.value), ${ref.pageIndex})" style="margin-top:6px" />
              <div class="row">
                <select name="${slice.id}__kind" onclick="event.stopPropagation()" onchange="updateSlice('${slice.id}', 'kind', this.value, ${ref.pageIndex})">${kindOptions.map(kind => `<option value="${kind}" ${normalizeKind(slice.kind) === kind ? "selected" : ""}>${kind}</option>`).join("")}</select>
                <label><input name="${slice.id}__selected" type="checkbox" ${slice.selected !== false ? "checked" : ""} onclick="event.stopPropagation()" onchange="updateSlice('${slice.id}', 'selected', this.checked, ${ref.pageIndex})" /> selected</label>
              </div>
              <div class="tagline">
                <input name="${slice.id}__tags" value="${escapeHtml((slice.tags || []).join(','))}" placeholder="tags" onclick="event.stopPropagation()" onchange="updateTags('${slice.id}', this.value, ${ref.pageIndex})" />
                <select name="${slice.id}__reviewState" onclick="event.stopPropagation()" onchange="updateSlice('${slice.id}', 'reviewState', this.value, ${ref.pageIndex})">
                  ${["confirmed", "review", "ignored"].map(value => `<option value="${value}" ${(slice.reviewState || "confirmed") === value ? "selected" : ""}>${value}</option>`).join("")}
                </select>
              </div>
            </div>
          </div>
          <div class="row">
            <input name="${slice.id}__x" type="number" value="${slice.bbox.x}" onclick="event.stopPropagation()" onchange="updateBBox('${slice.id}', 'x', this.value, ${ref.pageIndex})" />
            <input name="${slice.id}__y" type="number" value="${slice.bbox.y}" onclick="event.stopPropagation()" onchange="updateBBox('${slice.id}', 'y', this.value, ${ref.pageIndex})" />
            <input name="${slice.id}__width" type="number" value="${slice.bbox.width}" onclick="event.stopPropagation()" onchange="updateBBox('${slice.id}', 'width', this.value, ${ref.pageIndex})" />
            <input name="${slice.id}__height" type="number" value="${slice.bbox.height}" onclick="event.stopPropagation()" onchange="updateBBox('${slice.id}', 'height', this.value, ${ref.pageIndex})" />
          </div>
          <div class="muted">${ref.page.pageId} / ${slice.source || "manual"} ${slice.candidateIds?.length ? "/ candidate" : ""} / ${slice.bbox.width}x${slice.bbox.height}</div>
        </div>`;
      }).join("");
      document.getElementById("candidateSelectionCount").textContent = `(${state.selectedCandidateIds.size})`;
      renderSliceThumbnails();
    }
    function totalSelectedSliceCount() {
      return state.manual.pages.reduce((count, page) => count + page.slices.filter(item => item.selected !== false).length, 0);
    }
    function visibleAssetRefs() {
      const needle = state.assetSearch.trim().toLowerCase();
      const pageRefs = state.manual.pages.flatMap((page, pageIndex) => (state.assetAllPages || pageIndex === state.pageIndex) ? [{ page, pageIndex }] : []);
      return pageRefs.flatMap(({ page, pageIndex }) => page.slices.map(slice => ({ page, pageIndex, slice }))).filter(({ slice }) => {
        if (!needle) return true;
        return [slice.name, slice.displayName, slice.kind, ...(slice.tags || [])].some(value => String(value || "").toLowerCase().includes(needle));
      });
    }
    function visibleAssetSlices() {
      return visibleAssetRefs().map(ref => ref.slice);
    }
    function renderSliceThumbnails() {
      for (const thumb of document.querySelectorAll("[data-thumb-slice-id]")) {
        const ref = findSliceRef(thumb.dataset.thumbSliceId);
        if (!ref) continue;
        const image = state.pageImages[ref.page.pageId];
        if (!image || !image.complete) {
          imageForPage(ref.page.pageId).then(() => renderSliceThumbnails()).catch(() => {});
          continue;
        }
        drawSliceThumbnail(thumb, image, ref.slice);
      }
    }
    function drawSliceThumbnail(thumb, image, slice) {
        const tctx = thumb.getContext("2d");
        tctx.clearRect(0, 0, thumb.width, thumb.height);
        const bbox = slice.bbox;
        const scale = Math.min(thumb.width / bbox.width, thumb.height / bbox.height);
        const w = bbox.width * scale, h = bbox.height * scale;
        const x = (thumb.width - w) / 2, y = (thumb.height - h) / 2;
        tctx.fillStyle = "#020617";
        tctx.fillRect(0, 0, thumb.width, thumb.height);
        tctx.drawImage(image, bbox.x, bbox.y, bbox.width, bbox.height, x, y, w, h);
    }
    function findSliceRef(id) {
      for (let pageIndex = 0; pageIndex < state.manual.pages.length; pageIndex += 1) {
        const page = state.manual.pages[pageIndex];
        const slice = page.slices.find(item => item.id === id);
        if (slice) return { page, pageIndex, slice };
      }
      return null;
    }
    async function focusSlice(id, pageIndex=state.pageIndex) {
      if (pageIndex !== state.pageIndex) await loadPage(pageIndex);
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
      document.getElementById("tierFilters").innerHTML = tierOptions.map(tier => `<label><input name="filter_tier_${tier}" type="checkbox" data-tier="${tier}" ${state.filters.tiers[tier] ? "checked" : ""} /> ${tier}</label>`).join("");
      for (const id of ["showCandidates", "showSelected", "showLabels", "onlyTodoPages", "onlySelectedPages", "onlyDensePages"]) document.getElementById(id).checked = Boolean(state.filters[id]);
      document.getElementById("minConfidence").value = String(state.filters.minConfidence);
      document.getElementById("candidateOpacity").value = String(state.filters.candidateOpacity);
      document.getElementById("assetAllPages").checked = Boolean(state.assetAllPages);
      for (const input of document.querySelectorAll("[data-kind]")) input.onchange = () => { state.filters.kinds[input.dataset.kind] = input.checked; persistReviewFilters(); renderAll(); };
      for (const input of document.querySelectorAll("[data-source]")) input.onchange = () => { state.filters.sources[input.dataset.source] = input.checked; persistReviewFilters(); renderAll(); };
      for (const input of document.querySelectorAll("[data-tier]")) input.onchange = () => { state.filters.tiers[input.dataset.tier] = input.checked; persistReviewFilters(); renderAll(); };
      for (const id of ["showCandidates", "showSelected", "showLabels"]) document.getElementById(id).onchange = event => { state.filters[id] = event.target.checked; persistReviewFilters(); renderAll(); };
      for (const id of ["onlyTodoPages", "onlySelectedPages", "onlyDensePages"]) document.getElementById(id).onchange = event => { state.filters[id] = event.target.checked; persistReviewFilters(); renderPages(); };
      document.getElementById("minConfidence").onchange = event => { state.filters.minConfidence = Number(event.target.value) || 0; persistReviewFilters(); renderAll(); };
      document.getElementById("candidateOpacity").onchange = event => { state.filters.candidateOpacity = Number(event.target.value) || 0.75; persistReviewFilters(); renderAll(); };
      document.getElementById("candidateOpacity").oninput = event => { state.filters.candidateOpacity = Number(event.target.value) || 0.75; renderAll(); };
      document.getElementById("assetSearch").oninput = event => { state.assetSearch = event.target.value || ""; renderAssets(); };
      document.getElementById("assetAllPages").onchange = event => { state.assetAllPages = event.target.checked; persistReviewFilters(); renderAssets(); };
    }
    function updateSlice(id, key, value, pageIndex=state.pageIndex) {
      mutateManual(() => {
        const s = state.manual.pages[pageIndex]?.slices.find(x => x.id === id);
        if (s) s[key] = value;
      }, state.manual.pages[pageIndex]?.pageId);
    }
    function updateBBox(id, key, value, pageIndex=state.pageIndex) {
      mutateManual(() => {
        const page = state.manual.pages[pageIndex];
        const candidatePage = state.candidates.pages[pageIndex];
        const s = page?.slices.find(x => x.id === id);
        if (s && candidatePage) { s.bbox[key] = Math.max(0, Number(value) || 0); s.bbox = clampBoxForPage(s.bbox, candidatePage); }
      }, state.manual.pages[pageIndex]?.pageId);
    }
    function updateTags(id, value, pageIndex=state.pageIndex) {
      mutateManual(() => {
        const s = state.manual.pages[pageIndex]?.slices.find(x => x.id === id);
        if (s) s.tags = String(value || "").split(",").map(item => safeName(item)).filter(Boolean);
      }, state.manual.pages[pageIndex]?.pageId);
    }
    function safeName(value) {
      return String(value || "").replace(/[^0-9A-Za-z_-]+/g, "_").replace(/^_+|_+$/g, "") || "slice";
    }
    function bulkRenameSlices() {
      const prefix = prompt("批量名称前缀", "slice");
      if (!prefix) return;
      const base = safeName(prefix);
      const refs = visibleAssetRefs();
      mutateManualForPages(refs.map(ref => ref.page.pageId), () => {
        refs.forEach(({ slice }, index) => {
          const name = `${base}_${String(index + 1).padStart(4, "0")}`;
          slice.displayName = name;
        });
      });
      setStatus(`renamed ${refs.length} display name(s)`);
    }
    function bulkDeleteVisibleSlices() {
      const refs = visibleAssetRefs();
      const idsByPage = new Map();
      for (const ref of refs) {
        if (!idsByPage.has(ref.page.pageId)) idsByPage.set(ref.page.pageId, new Set());
        idsByPage.get(ref.page.pageId).add(ref.slice.id);
      }
      const ids = new Set(refs.map(ref => ref.slice.id));
      if (!ids.size || !confirm(`删除当前可见的 ${ids.size} 个 selected assets？`)) return;
      mutateManualForPages([...idsByPage.keys()], () => {
        for (const page of state.manual.pages) {
          const pageIds = idsByPage.get(page.pageId);
          if (pageIds) page.slices = page.slices.filter(slice => !pageIds.has(slice.id));
        }
        state.activeId = null;
      });
      setStatus(`deleted ${ids.size} visible asset(s)`);
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
    async function saveManual(options={}) {
      clearTimeout(state.autosaveTimer);
      state.autosaveTimer = null;
      if (state.savePromise) {
        await state.savePromise;
        if (state.lastSavedRevision >= state.saveRevision) return { selectedSliceCount: currentManualPage().slices.filter(item => item.selected !== false).length };
      }
      const revision = state.saveRevision;
      const run = async () => {
        setStatus(options.quiet ? "autosaving..." : "saving...");
        try {
          const data = await api("/manual-slices", { method: "PUT", headers: {"Content-Type":"application/json"}, body: JSON.stringify(state.manual) });
          state.lastSavedRevision = Math.max(state.lastSavedRevision, revision);
          if (state.lastSavedRevision >= state.saveRevision) {
            markSaved();
            setStatus(`saved (${data.selectedSliceCount})`);
          } else {
            setStatus("dirty");
            scheduleAutosave();
          }
          return data;
        } catch (error) {
          markSaveFailed();
          setStatus(error.message || String(error), true);
          throw error;
        } finally {
          state.savePromise = null;
        }
      };
      state.savePromise = state.savePromise || run();
      return state.savePromise;
    }
    async function exportProject() {
      try {
        await flushAutosave();
        await flushReviewStateSave();
        setStatus("exporting...");
        const manifest = await api("/export", { method: "POST" });
        syncExportLinks({ exported: true, downloadUrl: manifest.projectZipUrl, selectedAssetsDownloadUrl: manifest.selectedAssetsZipUrl });
        setStatus("exported");
      } catch (error) {
        setStatus(error.message || String(error), true);
      }
    }
    async function previewExport() {
      try {
        await flushAutosave();
        await flushReviewStateSave();
        setStatus("building preview...");
        const data = await api("/export-preview", { method: "POST" });
        document.getElementById("previewLinks").innerHTML = `<a href="${data.previewHtmlUrl}" target="_blank">导出预览</a><a href="${data.contactSheetUrl}" target="_blank">contact sheet</a><span class="muted">${data.assetCount} assets</span>`;
        setStatus("preview ready");
      } catch (error) {
        setStatus(error.message || String(error), true);
      }
    }
    document.getElementById("mode-select").onclick = () => setMode("select");
    document.getElementById("mode-draw").onclick = () => setMode("draw");
    document.getElementById("mode-candidate-box").onclick = () => setMode("candidateBox");
    document.getElementById("pan").onclick = () => setMode("pan");
    document.getElementById("fit").onclick = fitToScreen;
    document.getElementById("zoom100").onclick = () => { const rect = canvas.getBoundingClientRect(); setZoom(1, { x: rect.width / 2, y: rect.height / 2 }); };
    document.getElementById("zoomOut").onclick = () => zoomBy(0.8);
    document.getElementById("zoomIn").onclick = () => zoomBy(1.25);
    document.getElementById("delete").onclick = deleteActive;
    document.getElementById("save").onclick = () => saveManual().catch(error => setStatus(error.message || String(error), true));
    document.getElementById("previewExport").onclick = previewExport;
    document.getElementById("export").onclick = exportProject;
    function setMode(mode) {
      state.mode = mode;
      for (const id of ["mode-select", "mode-draw", "mode-candidate-box", "pan"]) document.getElementById(id).classList.remove("active");
      if (mode === "select") document.getElementById("mode-select").classList.add("active");
      if (mode === "draw") document.getElementById("mode-draw").classList.add("active");
      if (mode === "candidateBox") document.getElementById("mode-candidate-box").classList.add("active");
      if (mode === "pan") document.getElementById("pan").classList.add("active");
    }
    window.addEventListener("keydown", event => {
      if (event.target && ["INPUT", "SELECT", "TEXTAREA"].includes(event.target.tagName)) return;
      if (event.code === "Space") { state.spaceDown = true; event.preventDefault(); }
      if (event.key === "Delete" || event.key === "Backspace") { deleteActive(); event.preventDefault(); }
      if (event.key === "Escape") { state.drag = null; state.activeId = null; renderAll(); event.preventDefault(); }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") { saveManual().catch(error => setStatus(error.message || String(error), true)); event.preventDefault(); }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z" && event.shiftKey) { redoManual(); event.preventDefault(); return; }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z") { undoManual(); event.preventDefault(); return; }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "d") { duplicateActive(); event.preventDefault(); }
      if (event.altKey && event.key === "ArrowLeft") { pageByOffset(-1); event.preventDefault(); return; }
      if (event.altKey && event.key === "ArrowRight") { pageByOffset(1); event.preventDefault(); return; }
      const step = event.shiftKey ? 10 : 1;
      if (event.key === "ArrowLeft") { moveActive(-step, 0); event.preventDefault(); }
      if (event.key === "ArrowRight") { moveActive(step, 0); event.preventDefault(); }
      if (event.key === "ArrowUp") { moveActive(0, -step); event.preventDefault(); }
      if (event.key === "ArrowDown") { moveActive(0, step); event.preventDefault(); }
    });
    window.addEventListener("keyup", event => { if (event.code === "Space") state.spaceDown = false; });
    window.loadPage = loadPage; window.focusSlice = focusSlice; window.updateSlice = updateSlice; window.updateBBox = updateBBox;
    window.addSliceFromCandidate = addSliceFromCandidate; window.addManualSlice = addManualSlice; window.duplicateActive = duplicateActive;
    window.undoManual = undoManual; window.redoManual = redoManual; window.flushAutosave = flushAutosave; window.pageByOffset = pageByOffset;
    window.filteredCandidates = filteredCandidates; window.currentCandidatePage = currentCandidatePage; window.currentManualPage = currentManualPage;
    window.bulkAddCandidates = bulkAddCandidates; window.rejectSelectedCandidates = rejectSelectedCandidates; window.restoreRejectedOnPage = restoreRejectedOnPage;
    window.clearCandidateSelection = clearCandidateSelection; window.bulkRenameSlices = bulkRenameSlices; window.bulkDeleteVisibleSlices = bulkDeleteVisibleSlices;
    window.previewExport = previewExport; window.saveReviewState = saveReviewState; window.flushReviewStateSave = flushReviewStateSave;
    window.state = state;
    load().catch(error => setStatus(error.message || String(error), true));
  </script>
</body>
</html>
"""
