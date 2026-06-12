from __future__ import annotations


WORKSPACE_HTML = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Pencil Asset Workspace</title>
  <style>
    :root{color-scheme:dark}
    body{margin:0;background:#0f1419;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
    header{display:flex;align-items:center;justify-content:space-between;padding:18px 22px;border-bottom:1px solid #29313a;background:#111820}
    h1{font-size:18px;margin:0;font-weight:650}
    main{display:grid;grid-template-columns:340px 1fr;min-height:calc(100vh - 61px)}
    aside{border-right:1px solid #29313a;padding:18px;background:#0c1117}
    section{padding:18px}
    label{display:block;font-size:12px;color:#94a3b8;margin:12px 0 6px}
    input[type=text],input[type=file]{width:100%;box-sizing:border-box;background:#0f1720;border:1px solid #324152;color:#e5e7eb;padding:9px;border-radius:6px}
    button,a.button{display:inline-flex;align-items:center;gap:6px;background:#2563eb;border:0;color:#fff;text-decoration:none;padding:9px 12px;border-radius:6px;cursor:pointer;font-weight:600}
    button.secondary,a.secondary{background:#263241;color:#dbe4ef}
    button.danger{background:#b42318}
    .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:12px}
    .muted{color:#8b98a7;font-size:12px;line-height:1.5}
    .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
    .card{border:1px solid #29313a;background:#111820;border-radius:8px;overflow:hidden}
    .thumb{height:150px;background:#05080c;display:flex;align-items:center;justify-content:center}
    .thumb img{max-width:100%;max-height:150px}
    .card-body{padding:12px}
    .card h3{font-size:15px;margin:0 0 8px}
    .meta{font-size:12px;color:#9aa8b6;display:grid;grid-template-columns:1fr 1fr;gap:4px}
    .status{font-size:12px;color:#a7f3d0}
  </style>
</head>
<body>
<header>
  <h1>Pencil Asset Workspace</h1>
  <button id="refresh" class="secondary">刷新</button>
</header>
<main>
  <aside>
    <h2 style="font-size:15px;margin:0 0 12px">新建资产项目</h2>
    <form id="createForm">
      <label>项目名</label>
      <input name="projectName" type="text" value="Pencil Asset Project">
      <label>UI 截图，1..20 张</label>
      <input name="files[]" type="file" accept="image/png,image/jpeg,image/webp" multiple required>
      <div class="row"><button type="submit">上传并生成候选</button></div>
      <p class="muted">YOLO 是必需候选源；M29/PSD-like/OCR 只作为辅助证据。最终导出只看人工确认的 manual_slices。</p>
    </form>
    <pre id="log" class="muted"></pre>
  </aside>
  <section>
    <div id="projects" class="grid"></div>
  </section>
</main>
<script>
const projectsEl = document.getElementById('projects');
const logEl = document.getElementById('log');
async function json(url, opts={}) {
  const res = await fetch(url, opts);
  const data = await res.json().catch(()=>({detail:res.statusText}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data));
  return data.data;
}
async function loadProjects() {
  const data = await json('/api/asset-projects');
  projectsEl.innerHTML = '';
  for (const p of data.projects || []) {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <div class="thumb">${p.thumbnailUrl ? `<img src="${p.thumbnailUrl}">` : ''}</div>
      <div class="card-body">
        <h3>${escapeHtml(p.projectName || p.projectId)}</h3>
        <div class="meta">
          <span>页数 ${p.pageCount}</span><span>候选 ${p.candidateCount}</span>
          <span>已选 ${p.selectedSliceCount}</span><span class="status">${p.status}</span>
        </div>
        <div class="row">
          <a class="button" href="${p.reviewUrl}">打开 Review</a>
          ${p.exported ? `<a class="button secondary" href="${p.downloadUrl}">project.zip</a><a class="button secondary" href="${p.selectedAssetsDownloadUrl}">assets.zip</a>` : ''}
        </div>
      </div>`;
    projectsEl.appendChild(card);
  }
}
document.getElementById('refresh').onclick = loadProjects;
document.getElementById('createForm').onsubmit = async (event) => {
  event.preventDefault();
  logEl.textContent = 'uploading...';
  const fd = new FormData(event.currentTarget);
  try {
    const data = await json('/api/asset-projects', {method:'POST', body:fd});
    location.href = data.reviewUrl;
  } catch (e) {
    logEl.textContent = String(e.message || e);
  }
};
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
loadProjects().catch(e => logEl.textContent = e.message);
</script>
</body>
</html>"""


REVIEW_HTML = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Pencil Asset Review</title>
  <style>
    :root{color-scheme:dark}
    body{margin:0;background:#0b1016;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;overflow:auto}
    header{height:54px;display:flex;align-items:center;justify-content:space-between;padding:0 14px;border-bottom:1px solid #26313c;background:#101820}
    h1{font-size:15px;margin:0;font-weight:650}
    button,a.button{background:#2563eb;border:0;color:#fff;text-decoration:none;border-radius:6px;padding:8px 10px;cursor:pointer;font-weight:650;font-size:13px}
    button.secondary,a.secondary{background:#263241;color:#dbe4ef}
    button.danger{background:#b42318}
    select,input{background:#0e1620;border:1px solid #334155;color:#e5e7eb;border-radius:6px;padding:7px}
    #app{display:grid;grid-template-columns:220px minmax(420px,1fr) 300px;height:calc(100vh - 55px);min-width:940px}
    #pages,#side{background:#0d131a;overflow:auto}
    #pages{border-right:1px solid #26313c;padding:12px}
    #side{border-left:1px solid #26313c;padding:12px}
    #stage{position:relative;background:#05080c;overflow:hidden}
    canvas{position:absolute;left:0;top:0;image-rendering:auto}
    .page{display:flex;gap:8px;align-items:center;padding:8px;border:1px solid #25313d;border-radius:7px;margin-bottom:8px;cursor:pointer;background:#111820}
    .page.active{border-color:#3b82f6}
    .page img{width:48px;height:74px;object-fit:cover;background:#05080c}
    .page .name{font-size:13px;font-weight:650}
    .page .meta{font-size:11px;color:#94a3b8;margin-top:3px}
    .toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
    .tool.active{background:#16a34a;color:#fff}
    .panel-title{font-size:13px;font-weight:700;margin:10px 0 8px;color:#cbd5e1}
    .slice{border:1px solid #26313c;border-radius:7px;padding:8px;margin-bottom:8px;background:#111820}
    .slice.active{border-color:#22c55e}
    .slice .top{display:flex;justify-content:space-between;gap:8px}
    .slice input{width:100%;box-sizing:border-box;margin-top:7px}
    .small{font-size:12px;color:#94a3b8}
    .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0}
    .color-field{display:grid;grid-template-columns:1fr 40px;gap:6px;align-items:center;font-size:12px;color:#94a3b8}
    input[type=color]{width:40px;height:32px;padding:2px}
    #contextMenu{position:fixed;z-index:10;display:none;min-width:210px;border:1px solid #334155;border-radius:8px;background:#101820;box-shadow:0 18px 48px rgba(0,0,0,.42);padding:7px}
    #contextMenu .group{padding:5px 0;border-top:1px solid #25313d}
    #contextMenu .group:first-child{border-top:0}
    #contextMenu .label{font-size:11px;color:#94a3b8;padding:4px 6px}
    #contextMenu button{display:block;width:100%;text-align:left;background:transparent;color:#e5e7eb;padding:7px 8px;border-radius:5px;font-weight:550}
    #contextMenu button:hover{background:#1f2a37}
    #contextMenu button.danger{color:#fecaca;background:transparent}
    #contextMenu button.danger:hover{background:#4c1d1d}
    #message{font-size:12px;color:#fbbf24;max-width:38vw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  </style>
</head>
<body>
<header>
  <h1>Pencil Asset Review</h1>
  <div class="toolbar">
    <button id="toolSelect" class="tool active">选择</button>
    <button id="toolDraw" class="tool secondary">画框</button>
    <button id="toolPan" class="tool secondary">拖动</button>
    <select id="kind"><option value="image">image</option><option value="icon">icon</option></select>
    <button id="save">保存</button>
    <button id="preview" class="secondary">导出预览</button>
    <button id="export">导出</button>
    <a id="projectZip" class="button secondary" style="display:none">project.zip</a>
    <a id="assetsZip" class="button secondary" style="display:none">assets.zip</a>
    <span id="message"></span>
  </div>
</header>
<div id="app">
  <aside id="pages"></aside>
  <main id="stage"><canvas id="canvas"></canvas></main>
  <aside id="side">
    <div class="panel-title">Selected image/icon assets</div>
    <div class="small">选择：左键确认候选；右键打开菜单隐藏候选或删除资产。画框：拖拽任意区域创建手动资产。选中资产后可拖动和缩放。</div>
    <div class="row"><button id="delete" class="danger">删除选中</button><button id="fit" class="secondary">适应屏幕</button><button id="actual" class="secondary">100%</button></div>
    <div class="row"><button id="toggleRejected" class="secondary">显示已隐藏候选</button><button id="restoreRejected" class="secondary">恢复本页隐藏</button></div>
    <div class="panel-title">Frame colors</div>
    <div class="row">
      <label class="color-field">候选 image<input id="colorCandidateImage" data-color-key="candidateImage" type="color"></label>
      <label class="color-field">候选 icon<input id="colorCandidateIcon" data-color-key="candidateIcon" type="color"></label>
      <label class="color-field">已选<input id="colorSlice" data-color-key="slice" type="color"></label>
      <label class="color-field">选中<input id="colorActive" data-color-key="activeSlice" type="color"></label>
    </div>
    <div id="pageStats" class="small"></div>
    <div id="slices"></div>
  </aside>
</div>
<div id="contextMenu"></div>
<script>
const projectId = "__PROJECT_ID__";
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const stage = document.getElementById('stage');
const msg = document.getElementById('message');
const contextMenu = document.getElementById('contextMenu');
let project, candidatesDoc, manualDoc;
let reviewState = null;
let pageIndex = 0;
let image = new Image();
let view = {scale:1, x:20, y:20};
let drag = null;
let activeSliceId = null;
let showRejected = false;
let reviewSavePromise = null;
let toolMode = 'select';
const defaultColors = {
  candidateImage:'#22c55e',
  candidateIcon:'#38bdf8',
  rejected:'#64748b',
  slice:'#facc15',
  activeSlice:'#f97316',
  handle:'#111827',
  draft:'#ffffff'
};

async function api(url, opts={}) {
  const res = await fetch(url, opts);
  const data = await res.json().catch(()=>({detail:res.statusText}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data));
  return data.data;
}
async function init() {
  project = await api(`/api/asset-projects/${projectId}`);
  candidatesDoc = await api(`/api/asset-projects/${projectId}/candidates`);
  manualDoc = await api(`/api/asset-projects/${projectId}/manual-slices`);
  reviewState = await api(`/api/asset-projects/${projectId}/review-state`);
  ensureColors();
  syncColorInputs();
  syncExportLinks(project);
  renderPages();
  await loadPage(0);
}
function currentCandidatePage(){return candidatesDoc.pages[pageIndex]}
function currentManualPage(){return manualDoc.pages[pageIndex]}
function currentReviewPage(){
  if (!reviewState) return {pageId:currentCandidatePage().pageId,rejectedCandidateIds:[],hiddenCandidateIds:[],lastFilter:{}};
  const pageId = currentCandidatePage().pageId;
  let page = (reviewState.pages || []).find(p => p.pageId === pageId);
  if (!page) {
    page = {pageId,rejectedCandidateIds:[],hiddenCandidateIds:[],lastFilter:{}};
    reviewState.pages = [...(reviewState.pages || []), page];
  }
  page.rejectedCandidateIds ||= [];
  page.hiddenCandidateIds ||= [];
  page.lastFilter ||= {};
  return page;
}
function ensureColors(){
  reviewState ||= {schema:'pencil_asset.review_state.v1',projectId,pages:[],filters:{}};
  reviewState.filters ||= {};
  reviewState.filters.colors = {...defaultColors, ...(reviewState.filters.colors || {})};
  return reviewState.filters.colors;
}
function colors(){return ensureColors()}
function syncColorInputs(){
  const c = colors();
  for (const input of document.querySelectorAll('input[data-color-key]')) {
    input.value = c[input.dataset.colorKey] || defaultColors[input.dataset.colorKey] || '#ffffff';
  }
}
async function loadPage(index) {
  hideContextMenu();
  pageIndex = index;
  if (reviewState) reviewState.lastActivePageId = currentCandidatePage().pageId;
  const p = currentCandidatePage();
  image = new Image();
  image.onload = () => {fit(); draw(); renderPages(); renderSlices();};
  image.src = `/api/asset-projects/${projectId}/source/${p.pageId}?t=${Date.now()}`;
}
function renderPages() {
  const el = document.getElementById('pages');
  el.innerHTML = '';
  candidatesDoc.pages.forEach((p,i)=>{
    const selected = (manualDoc.pages[i]?.slices || []).filter(s=>s.selected!==false).length;
    const reviewPage = (reviewState?.pages || []).find(item => item.pageId === p.pageId);
    const rejected = (reviewPage?.rejectedCandidateIds || []).length;
    const div = document.createElement('div');
    div.className = 'page' + (i===pageIndex ? ' active':'');
    div.innerHTML = `<img src="/api/asset-projects/${projectId}/source/${p.pageId}"><div><div class="name">${p.pageId}</div><div class="meta">${p.candidates.length} 候选 / ${selected} 已选 / ${rejected} 已隐藏</div></div>`;
    div.onclick = ()=>loadPage(i);
    el.appendChild(div);
  });
}
function renderSlices() {
  const el = document.getElementById('slices');
  const p = currentManualPage();
  const stats = document.getElementById('pageStats');
  const reviewPage = currentReviewPage();
  const hidden = new Set([...(reviewPage.rejectedCandidateIds || []), ...(reviewPage.hiddenCandidateIds || [])]);
  stats.textContent = `${currentCandidatePage().candidates.length} 候选 / ${hidden.size} 已隐藏 / ${(p.slices || []).filter(s=>s.selected!==false).length} 已选`;
  el.innerHTML = '';
  (p.slices || []).forEach((s, i)=>{
    const div = document.createElement('div');
    div.className = 'slice' + (s.id===activeSliceId ? ' active':'');
    div.innerHTML = `<div class="top"><b>${i+1}. ${s.kind}</b><span class="small">${s.bbox.width}x${s.bbox.height}</span></div>
      <input value="${escapeHtml(s.displayName || s.name)}" data-id="${s.id}">
      <div class="small">${s.bbox.x}, ${s.bbox.y} -> ${s.name}</div>`;
    div.onclick = ()=>{activeSliceId=s.id; draw(); renderSlices();};
    div.querySelector('input').onchange = (e)=>{s.displayName=e.target.value;s.name=slug(e.target.value)||s.name;markManualDirty('资产名称已修改，记得保存');renderSlices();};
    el.appendChild(div);
  });
}
function fit() {
  const rect = stage.getBoundingClientRect();
  const p = currentCandidatePage();
  const sx = (rect.width - 40) / p.width;
  const sy = (rect.height - 40) / p.height;
  view.scale = Math.max(0.05, Math.min(sx, sy));
  view.x = 20;
  view.y = 20;
  resizeCanvas();
}
function actualSize() {
  view.scale = 1;
  view.x = 20;
  view.y = 20;
  draw();
}
function resizeCanvas(){
  const r = stage.getBoundingClientRect();
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const cssWidth = Math.max(1, Math.round(r.width));
  const cssHeight = Math.max(1, Math.round(r.height));
  const pixelWidth = Math.round(cssWidth * dpr);
  const pixelHeight = Math.round(cssHeight * dpr);
  if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
    canvas.width = pixelWidth;
    canvas.height = pixelHeight;
    canvas.style.width = `${cssWidth}px`;
    canvas.style.height = `${cssHeight}px`;
  }
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return {width: cssWidth, height: cssHeight, dpr};
}
function draw() {
  const color = colors();
  const size = resizeCanvas();
  ctx.clearRect(0,0,size.width,size.height);
  ctx.imageSmoothingEnabled = view.scale < 1;
  ctx.imageSmoothingQuality = 'high';
  ctx.save();
  ctx.translate(view.x, view.y);
  ctx.scale(view.scale, view.scale);
  ctx.drawImage(image, 0, 0);
  const rejected = rejectedCandidateSet();
  for (const c of currentCandidatePage().candidates || []) {
    if (!['strong','normal'].includes(c.level || 'normal')) continue;
    const isRejected = rejected.has(c.id);
    if (isRejected && !showRejected) continue;
    if (isRejected) {
      drawBox(c.bbox, color.rejected, '', false, true);
    } else {
      drawBox(c.bbox, c.kind === 'icon' ? color.candidateIcon : color.candidateImage, '', false, false);
    }
  }
  for (const s of currentManualPage().slices || []) {
    drawSelectedSlice(s);
  }
  if (drag?.mode === 'draw') drawDraftBox(dragBox());
  ctx.restore();
  canvas.style.cursor = canvasCursor();
}
function stroke(b,c,w){ctx.strokeStyle=c;ctx.lineWidth=w;ctx.strokeRect(b.x,b.y,b.width,b.height)}
function drawBox(b,c,label,active=false,dashed=false){
  ctx.save();
  if (dashed) ctx.setLineDash([6 / view.scale, 4 / view.scale]);
  stroke(b,'#000000', (active ? 5 : 4) / view.scale);
  stroke(b,c, (active ? 3 : 2) / view.scale);
  if (label) {
    ctx.font = `${12 / view.scale}px sans-serif`;
    const text = String(label);
    const w = Math.min(150, Math.max(36, text.length * 12 + 10)) / view.scale;
    const h = 18 / view.scale;
    const y = Math.max(0, b.y - h);
    ctx.fillStyle = 'rgba(0,0,0,.78)';
    ctx.fillRect(b.x, y, w, h);
    ctx.fillStyle = c;
    ctx.fillText(text, b.x + 4 / view.scale, y + 13 / view.scale);
  }
  ctx.restore();
}
function drawSelectedSlice(s){
  const color = colors();
  const active = s.id === activeSliceId;
  drawBox(s.bbox, active ? color.activeSlice : color.slice, active ? '已选' : '', active, false);
  if (!active) return;
  ctx.save();
  const size = 9 / view.scale;
  ctx.fillStyle = color.handle;
  ctx.strokeStyle = '#ffffff';
  ctx.lineWidth = 2 / view.scale;
  for (const handle of handlesFor(s.bbox)) {
    ctx.fillRect(handle.x - size / 2, handle.y - size / 2, size, size);
    ctx.strokeRect(handle.x - size / 2, handle.y - size / 2, size, size);
  }
  ctx.restore();
}
function drawDraftBox(b){
  ctx.save();
  stroke(b,'#000000', 5 / view.scale);
  stroke(b,'#ffffff', 3 / view.scale);
  ctx.restore();
}
function screenToImage(ev){const r=canvas.getBoundingClientRect();return {x:(ev.clientX-r.left-view.x)/view.scale,y:(ev.clientY-r.top-view.y)/view.scale}}
function boxContains(b, pt){return pt.x>=b.x && pt.y>=b.y && pt.x<=b.x+b.width && pt.y<=b.y+b.height}
function candidateAt(pt, includeRejected=false) {
  const rejected = rejectedCandidateSet();
  const matches = (currentCandidatePage().candidates || []).filter(c => {
    if (!['strong','normal'].includes(c.level || 'normal')) return false;
    if (rejected.has(c.id) && !(includeRejected || showRejected)) return false;
    return boxContains(c.bbox, pt);
  });
  matches.sort((a,b) => {
    const areaA = a.bbox.width * a.bbox.height;
    const areaB = b.bbox.width * b.bbox.height;
    if (areaA !== areaB) return areaA - areaB;
    const confA = Number(a.confidence || 0);
    const confB = Number(b.confidence || 0);
    if (confA !== confB) return confB - confA;
    return String(a.id).localeCompare(String(b.id));
  });
  return matches[0] || null;
}
function sliceAt(pt) {
  return [...(currentManualPage().slices || [])].reverse().find(s => s.selected !== false && boxContains(s.bbox, pt)) || null;
}
function activeSlice(){return (currentManualPage().slices || []).find(s => s.id === activeSliceId) || null}
function handlesFor(b) {
  const cx = b.x + b.width / 2, cy = b.y + b.height / 2, r = b.x + b.width, bt = b.y + b.height;
  return [
    {name:'nw',x:b.x,y:b.y},{name:'n',x:cx,y:b.y},{name:'ne',x:r,y:b.y},
    {name:'e',x:r,y:cy},{name:'se',x:r,y:bt},{name:'s',x:cx,y:bt},
    {name:'sw',x:b.x,y:bt},{name:'w',x:b.x,y:cy}
  ];
}
function hitHandle(slice, pt) {
  if (!slice) return null;
  const threshold = 10 / view.scale;
  for (const handle of handlesFor(slice.bbox)) {
    if (Math.abs(pt.x - handle.x) <= threshold && Math.abs(pt.y - handle.y) <= threshold) return handle.name;
  }
  return null;
}
function hitTargetsAt(pt, includeRejected=false){
  const active = activeSlice();
  const handle = active ? hitHandle(active, pt) : null;
  const slice = handle ? active : sliceAt(pt);
  const candidate = candidateAt(pt, includeRejected);
  return {handle, slice, candidate};
}
function resizeBox(original, handle, dx, dy) {
  let x = original.x, y = original.y, right = original.x + original.width, bottom = original.y + original.height;
  if (handle.includes('w')) x += dx;
  if (handle.includes('e')) right += dx;
  if (handle.includes('n')) y += dy;
  if (handle.includes('s')) bottom += dy;
  const p = currentCandidatePage();
  x = Math.max(0, Math.min(x, right - 1));
  y = Math.max(0, Math.min(y, bottom - 1));
  right = Math.max(x + 1, Math.min(p.width, right));
  bottom = Math.max(y + 1, Math.min(p.height, bottom));
  return {x:Math.round(x), y:Math.round(y), width:Math.round(right - x), height:Math.round(bottom - y)};
}
function moveBox(original, dx, dy) {
  const p = currentCandidatePage();
  return {
    x:Math.round(Math.max(0, Math.min(p.width - original.width, original.x + dx))),
    y:Math.round(Math.max(0, Math.min(p.height - original.height, original.y + dy))),
    width:original.width,
    height:original.height
  };
}
function canvasCursor(){
  if (drag?.mode === 'pan' || toolMode === 'pan') return 'grab';
  if (drag?.mode === 'resize') return `${drag.handle}-resize`;
  if (drag?.mode === 'move') return 'move';
  if (toolMode === 'draw') return 'crosshair';
  return 'default';
}
function hoverCursor(pt){
  if (toolMode === 'draw') return 'crosshair';
  if (toolMode === 'pan') return 'grab';
  const hit = hitTargetsAt(pt);
  if (hit.handle) return `${hit.handle}-resize`;
  if (hit.slice) return 'move';
  if (hit.candidate) return 'pointer';
  return 'default';
}
function markManualDirty(message='已修改，记得保存') {
  msg.textContent = message;
}
canvas.onmousedown = (ev) => {
  hideContextMenu();
  const pt = screenToImage(ev);
  if (ev.button === 2) return;
  if (ev.button === 1 || ev.shiftKey || ev.getModifierState('Space') || toolMode === 'pan') {
    drag = {mode:'pan', sx:ev.clientX, sy:ev.clientY, vx:view.x, vy:view.y};
    return;
  }
  if (toolMode === 'draw') {
    drag = {mode:'draw', start:pt, end:pt};
    draw();
    return;
  }
  const hit = hitTargetsAt(pt);
  if (hit.slice) {
    activeSliceId = hit.slice.id;
    drag = {mode:hit.handle ? 'resize' : 'move', handle:hit.handle, start:pt, original:{...hit.slice.bbox}, sliceId:hit.slice.id};
    draw(); renderSlices();
    return;
  }
  if (hit.candidate) {
    if (ev.altKey) {
      rejectCandidate(hit.candidate.id);
      return;
    }
    addSliceFromCandidate(hit.candidate);
    draw(); renderSlices(); renderPages();
    return;
  }
  activeSliceId = null;
  draw(); renderSlices();
};
canvas.oncontextmenu = (ev) => {
  ev.preventDefault();
  const hit = hitTargetsAt(screenToImage(ev), showRejected);
  showContextMenu(ev.clientX, ev.clientY, hit);
};
canvas.onmousemove = (ev) => {
  if (!drag) {
    canvas.style.cursor = hoverCursor(screenToImage(ev));
    return;
  }
  if (drag.mode === 'pan') { view.x = drag.vx + ev.clientX - drag.sx; view.y = drag.vy + ev.clientY - drag.sy; }
  if (drag.mode === 'draw') drag.end = screenToImage(ev);
  if (drag.mode === 'move' || drag.mode === 'resize') {
    const s = (currentManualPage().slices || []).find(item => item.id === drag.sliceId);
    if (s) {
      const pt = screenToImage(ev);
      const dx = pt.x - drag.start.x;
      const dy = pt.y - drag.start.y;
      s.bbox = drag.mode === 'resize' ? resizeBox(drag.original, drag.handle, dx, dy) : moveBox(drag.original, dx, dy);
    }
  }
  draw();
};
window.onmouseup = () => {
  if (drag?.mode === 'move' || drag?.mode === 'resize') {
    markManualDirty('资产框已调整，记得保存');
    renderSlices(); renderPages();
  }
  if (drag?.mode === 'draw') {
    const b = dragBox();
    if (b.width >= 4 && b.height >= 4) {
      addManualSlice(b);
      msg.textContent = `已画框 ${b.width}x${b.height}，记得保存`;
    }
    renderSlices(); renderPages();
  }
  drag = null;
  draw();
};
canvas.onwheel = (ev) => {
  ev.preventDefault();
  const before = screenToImage(ev);
  const factor = ev.deltaY < 0 ? 1.08 : 0.92;
  view.scale = Math.max(0.05, Math.min(8, view.scale * factor));
  const r = canvas.getBoundingClientRect();
  view.x = ev.clientX - r.left - before.x * view.scale;
  view.y = ev.clientY - r.top - before.y * view.scale;
  draw();
};
function dragBox(){const a=drag.start,b=drag.end;return normBox({x:Math.min(a.x,b.x),y:Math.min(a.y,b.y),width:Math.abs(a.x-b.x),height:Math.abs(a.y-b.y)})}
function normBox(b){const p=currentCandidatePage();let x=Math.max(0,Math.round(b.x));let y=Math.max(0,Math.round(b.y));let w=Math.max(1,Math.round(b.width));let h=Math.max(1,Math.round(b.height));w=Math.min(w,p.width-x);h=Math.min(h,p.height-y);return {x,y,width:w,height:h}}
function addSliceFromCandidate(c) {
  const p = currentManualPage();
  const existing = (p.slices || []).find(s => (s.candidateIds || []).includes(c.id));
  if (existing) {
    activeSliceId = existing.id;
    msg.textContent = '该候选已加入资产，已选中现有资产';
    return;
  }
  const id = `${p.pageId}__slice_${String((p.slices || []).length + 1).padStart(4,'0')}`;
  p.slices.push({id, name:id, displayName:c.kind, kind:c.kind === 'icon' ? 'icon':'image', bbox:c.bbox, selected:true, exportMode:'rect', source:'candidate_confirmed', candidateIds:[c.id], tags:[]});
  activeSliceId = id;
  markManualDirty('已加入候选资产，记得保存');
}
function addManualSlice(bbox) {
  const p = currentManualPage();
  const id = `${p.pageId}__slice_${String((p.slices || []).length + 1).padStart(4,'0')}`;
  const kind = document.getElementById('kind').value;
  p.slices.push({id, name:id, displayName:kind, kind, bbox, selected:true, exportMode:'rect', source:'manual', candidateIds:[], tags:[]});
  activeSliceId = id;
  markManualDirty('已创建手动资产，记得保存');
}
document.getElementById('delete').onclick = () => {
  deleteActiveSlice();
};
function deleteActiveSlice() {
  if (!activeSliceId) return;
  const p = currentManualPage();
  p.slices = (p.slices || []).filter(s => s.id !== activeSliceId);
  activeSliceId = null;
  markManualDirty('已删除资产，记得保存');
  draw(); renderSlices(); renderPages();
}
document.getElementById('fit').onclick = fit;
document.getElementById('actual').onclick = actualSize;
document.getElementById('save').onclick = save;
document.getElementById('toolSelect').onclick = () => setToolMode('select');
document.getElementById('toolDraw').onclick = () => setToolMode('draw');
document.getElementById('toolPan').onclick = () => setToolMode('pan');
document.getElementById('toggleRejected').onclick = () => {
  showRejected = !showRejected;
  document.getElementById('toggleRejected').textContent = showRejected ? '隐藏已隐藏候选' : '显示已隐藏候选';
  draw();
};
document.getElementById('restoreRejected').onclick = () => {
  const reviewPage = currentReviewPage();
  const count = new Set([...(reviewPage.rejectedCandidateIds || []), ...(reviewPage.hiddenCandidateIds || [])]).size;
  reviewPage.rejectedCandidateIds = [];
  reviewPage.hiddenCandidateIds = [];
  autosaveReviewState(`已恢复 ${count} 个候选`);
  draw(); renderSlices(); renderPages();
};
for (const input of document.querySelectorAll('input[data-color-key]')) {
  input.oninput = () => {
    colors()[input.dataset.colorKey] = input.value;
    draw();
  };
  input.onchange = () => autosaveReviewState('已保存框颜色');
}
document.getElementById('preview').onclick = async()=>{await save(); const data=await api(`/api/asset-projects/${projectId}/export-preview`,{method:'POST'}); msg.innerHTML=`预览 ${data.assetCount} 个资产 <a style="color:#93c5fd" href="${data.previewHtmlUrl}" target="_blank">打开</a>`};
document.getElementById('export').onclick = async()=>{await save(); const data=await api(`/api/asset-projects/${projectId}/export`,{method:'POST'}); document.getElementById('projectZip').style.display='inline-flex';document.getElementById('assetsZip').style.display='inline-flex';document.getElementById('projectZip').href=data.projectZipUrl;document.getElementById('assetsZip').href=data.selectedAssetsZipUrl;msg.textContent=`已导出 ${data.selectedAssetCount} 个资产`};
function syncExportLinks(p){if(!p?.exported)return;document.getElementById('projectZip').style.display='inline-flex';document.getElementById('assetsZip').style.display='inline-flex';document.getElementById('projectZip').href=p.downloadUrl;document.getElementById('assetsZip').href=p.selectedAssetsDownloadUrl}
async function save(){hideContextMenu(); const data=await api(`/api/asset-projects/${projectId}/manual-slices`,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(manualDoc)}); msg.textContent=`已保存 ${data.selectedSliceCount} 个资产`; return data}
function rejectedCandidateSet(){const page=currentReviewPage();return new Set([...(page.rejectedCandidateIds || []), ...(page.hiddenCandidateIds || [])])}
function rejectCandidate(candidateId) {
  const page = currentReviewPage();
  const rejected = new Set(page.rejectedCandidateIds || []);
  if (rejected.has(candidateId)) {
    rejected.delete(candidateId);
    page.rejectedCandidateIds = [...rejected].sort();
    autosaveReviewState('已恢复候选');
  } else {
    rejected.add(candidateId);
    page.rejectedCandidateIds = [...rejected].sort();
    page.hiddenCandidateIds = (page.hiddenCandidateIds || []).filter(id => id !== candidateId);
    autosaveReviewState('已隐藏错误候选');
  }
  draw(); renderSlices(); renderPages();
}
function showContextMenu(x, y, hit) {
  contextMenu.innerHTML = '';
  if (!hit.slice && !hit.candidate) {
    hideContextMenu();
    return;
  }
  if (hit.slice) {
    const group = document.createElement('div');
    group.className = 'group';
    group.innerHTML = `<div class="label">已选资产 ${escapeHtml(hit.slice.displayName || hit.slice.name)}</div>`;
    const setImage = menuButton('设为 image', () => {hit.slice.kind = 'image'; markManualDirty('资产已设为 image，记得保存'); hideContextMenu(); draw(); renderSlices();});
    const setIcon = menuButton('设为 icon', () => {hit.slice.kind = 'icon'; markManualDirty('资产已设为 icon，记得保存'); hideContextMenu(); draw(); renderSlices();});
    const del = menuButton('删除资产', () => {activeSliceId = hit.slice.id; deleteActiveSlice(); hideContextMenu();}, 'danger');
    group.append(setImage, setIcon, del);
    contextMenu.appendChild(group);
  }
  if (hit.candidate) {
    const rejected = rejectedCandidateSet().has(hit.candidate.id);
    const group = document.createElement('div');
    group.className = 'group';
    group.innerHTML = `<div class="label">候选框 ${escapeHtml(hit.candidate.id)}</div>`;
    const add = menuButton('加入资产', () => {addSliceFromCandidate(hit.candidate); hideContextMenu(); draw(); renderSlices(); renderPages();});
    const hide = menuButton(rejected ? '恢复候选' : '隐藏候选', () => {rejectCandidate(hit.candidate.id); hideContextMenu();});
    group.append(add, hide);
    contextMenu.appendChild(group);
  }
  contextMenu.style.left = `${Math.min(x, window.innerWidth - 230)}px`;
  contextMenu.style.top = `${Math.min(y, window.innerHeight - 160)}px`;
  contextMenu.style.display = 'block';
}
function menuButton(text, onClick, className='') {
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = text;
  if (className) button.className = className;
  button.onclick = onClick;
  return button;
}
function hideContextMenu(){contextMenu.style.display='none';contextMenu.innerHTML=''}
document.addEventListener('click', (ev) => {
  if (!contextMenu.contains(ev.target)) hideContextMenu();
});
function autosaveReviewState(message) {
  reviewSavePromise = api(`/api/asset-projects/${projectId}/review-state`, {
    method:'PUT',
    headers:{'content-type':'application/json'},
    body:JSON.stringify(reviewState)
  }).then(data => {
    reviewState = data.reviewState || reviewState;
    msg.textContent = `${message}，共隐藏 ${data.rejectedCandidateCount} 个候选`;
    return data;
  }).catch(e => {msg.textContent = `保存候选状态失败：${e.message || e}`;});
}
window.onkeydown = (ev) => {
  if (!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName || '')) {
    if (ev.key === 'v' || ev.key === 'V') { setToolMode('select'); return; }
    if (ev.key === 'b' || ev.key === 'B') { setToolMode('draw'); return; }
    if (ev.key === 'h' || ev.key === 'H') { setToolMode('pan'); return; }
  }
  if ((ev.key === 'Delete' || ev.key === 'Backspace') && activeSliceId && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName || '')) {
    ev.preventDefault();
    deleteActiveSlice();
  }
};
function setToolMode(mode) {
  hideContextMenu();
  toolMode = mode;
  for (const [id, value] of [['toolSelect','select'], ['toolDraw','draw'], ['toolPan','pan']]) {
    const button = document.getElementById(id);
    button.classList.toggle('active', value === mode);
    button.classList.toggle('secondary', value !== mode);
  }
  msg.textContent = mode === 'draw' ? '画框模式：拖拽任意区域创建手动资产' : mode === 'pan' ? '拖动模式：拖动画布' : '选择模式：点击候选加入资产';
  draw();
}
function slug(s){return String(s).replace(/[^0-9A-Za-z_-]+/g,'_').replace(/^_+|_+$/g,'')}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
window.onresize = draw;
init().catch(e => msg.textContent = e.message);
</script>
</body>
</html>"""
