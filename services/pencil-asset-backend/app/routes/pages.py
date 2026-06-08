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
    .panel-title{font-size:13px;font-weight:700;margin:10px 0 8px;color:#cbd5e1}
    .slice{border:1px solid #26313c;border-radius:7px;padding:8px;margin-bottom:8px;background:#111820}
    .slice.active{border-color:#22c55e}
    .slice .top{display:flex;justify-content:space-between;gap:8px}
    .slice input{width:100%;box-sizing:border-box;margin-top:7px}
    .small{font-size:12px;color:#94a3b8}
    .row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0}
    #message{font-size:12px;color:#fbbf24;max-width:38vw;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  </style>
</head>
<body>
<header>
  <h1>Pencil Asset Review</h1>
  <div class="toolbar">
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
    <div class="small">点击候选框加入；在空白处拖拽可手动画框；滚轮缩放，按住 Space 或中键拖动画布。</div>
    <div class="row"><button id="delete" class="danger">删除选中</button><button id="fit" class="secondary">适应屏幕</button><button id="actual" class="secondary">100%</button></div>
    <div id="slices"></div>
  </aside>
</div>
<script>
const projectId = "__PROJECT_ID__";
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const stage = document.getElementById('stage');
const msg = document.getElementById('message');
let project, candidatesDoc, manualDoc;
let pageIndex = 0;
let image = new Image();
let view = {scale:1, x:20, y:20};
let drag = null;
let activeSliceId = null;

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
  syncExportLinks(project);
  renderPages();
  await loadPage(0);
}
function currentCandidatePage(){return candidatesDoc.pages[pageIndex]}
function currentManualPage(){return manualDoc.pages[pageIndex]}
async function loadPage(index) {
  pageIndex = index;
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
    const div = document.createElement('div');
    div.className = 'page' + (i===pageIndex ? ' active':'');
    div.innerHTML = `<img src="/api/asset-projects/${projectId}/source/${p.pageId}"><div><div class="name">${p.pageId}</div><div class="meta">${p.candidates.length} 候选 / ${selected} 已选</div></div>`;
    div.onclick = ()=>loadPage(i);
    el.appendChild(div);
  });
}
function renderSlices() {
  const el = document.getElementById('slices');
  const p = currentManualPage();
  el.innerHTML = '';
  (p.slices || []).forEach((s, i)=>{
    const div = document.createElement('div');
    div.className = 'slice' + (s.id===activeSliceId ? ' active':'');
    div.innerHTML = `<div class="top"><b>${i+1}. ${s.kind}</b><span class="small">${s.bbox.width}x${s.bbox.height}</span></div>
      <input value="${escapeHtml(s.displayName || s.name)}" data-id="${s.id}">
      <div class="small">${s.bbox.x}, ${s.bbox.y} -> ${s.name}</div>`;
    div.onclick = ()=>{activeSliceId=s.id; draw(); renderSlices();};
    div.querySelector('input').onchange = (e)=>{s.displayName=e.target.value;s.name=slug(e.target.value)||s.name;};
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
  const size = resizeCanvas();
  ctx.clearRect(0,0,size.width,size.height);
  ctx.imageSmoothingEnabled = view.scale < 1;
  ctx.imageSmoothingQuality = 'high';
  ctx.save();
  ctx.translate(view.x, view.y);
  ctx.scale(view.scale, view.scale);
  ctx.drawImage(image, 0, 0);
  for (const c of currentCandidatePage().candidates || []) {
    if (!['strong','normal'].includes(c.level || 'normal')) continue;
    stroke(c.bbox, c.kind === 'icon' ? '#38bdf8' : '#22c55e', 2 / view.scale);
  }
  for (const s of currentManualPage().slices || []) {
    stroke(s.bbox, s.id===activeSliceId ? '#f97316' : '#facc15', 3 / view.scale);
  }
  if (drag?.mode === 'draw') stroke(dragBox(), '#ffffff', 2 / view.scale);
  ctx.restore();
}
function stroke(b,c,w){ctx.strokeStyle=c;ctx.lineWidth=w;ctx.strokeRect(b.x,b.y,b.width,b.height)}
function screenToImage(ev){const r=canvas.getBoundingClientRect();return {x:(ev.clientX-r.left-view.x)/view.scale,y:(ev.clientY-r.top-view.y)/view.scale}}
function candidateAt(pt) {
  return [...(currentCandidatePage().candidates || [])].reverse().find(c => pt.x>=c.bbox.x && pt.y>=c.bbox.y && pt.x<=c.bbox.x+c.bbox.width && pt.y<=c.bbox.y+c.bbox.height);
}
canvas.onmousedown = (ev) => {
  const pt = screenToImage(ev);
  if (ev.button === 1 || ev.shiftKey || ev.getModifierState('Space')) {
    drag = {mode:'pan', sx:ev.clientX, sy:ev.clientY, vx:view.x, vy:view.y};
    return;
  }
  const c = candidateAt(pt);
  if (c) {
    addSliceFromCandidate(c);
    draw(); renderSlices(); renderPages();
    return;
  }
  drag = {mode:'draw', start:pt, end:pt};
};
canvas.onmousemove = (ev) => {
  if (!drag) return;
  if (drag.mode === 'pan') { view.x = drag.vx + ev.clientX - drag.sx; view.y = drag.vy + ev.clientY - drag.sy; }
  if (drag.mode === 'draw') drag.end = screenToImage(ev);
  draw();
};
window.onmouseup = () => {
  if (drag?.mode === 'draw') {
    const b = dragBox();
    if (b.width >= 4 && b.height >= 4) addManualSlice(b);
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
  if ((p.slices || []).some(s => (s.candidateIds || []).includes(c.id))) return;
  const id = `${p.pageId}__slice_${String((p.slices || []).length + 1).padStart(4,'0')}`;
  p.slices.push({id, name:id, displayName:c.kind, kind:c.kind === 'icon' ? 'icon':'image', bbox:c.bbox, selected:true, exportMode:'rect', source:'candidate_confirmed', candidateIds:[c.id], tags:[]});
  activeSliceId = id;
}
function addManualSlice(bbox) {
  const p = currentManualPage();
  const id = `${p.pageId}__slice_${String((p.slices || []).length + 1).padStart(4,'0')}`;
  const kind = document.getElementById('kind').value;
  p.slices.push({id, name:id, displayName:kind, kind, bbox, selected:true, exportMode:'rect', source:'manual', candidateIds:[], tags:[]});
  activeSliceId = id;
}
document.getElementById('delete').onclick = () => {
  if (!activeSliceId) return;
  const p = currentManualPage();
  p.slices = (p.slices || []).filter(s => s.id !== activeSliceId);
  activeSliceId = null;
  draw(); renderSlices(); renderPages();
};
document.getElementById('fit').onclick = fit;
document.getElementById('actual').onclick = actualSize;
document.getElementById('save').onclick = save;
document.getElementById('preview').onclick = async()=>{await save(); const data=await api(`/api/asset-projects/${projectId}/export-preview`,{method:'POST'}); msg.innerHTML=`预览 ${data.assetCount} 个资产 <a style="color:#93c5fd" href="${data.previewHtmlUrl}" target="_blank">打开</a>`};
document.getElementById('export').onclick = async()=>{await save(); const data=await api(`/api/asset-projects/${projectId}/export`,{method:'POST'}); document.getElementById('projectZip').style.display='inline-flex';document.getElementById('assetsZip').style.display='inline-flex';document.getElementById('projectZip').href=data.projectZipUrl;document.getElementById('assetsZip').href=data.selectedAssetsZipUrl;msg.textContent=`已导出 ${data.selectedAssetCount} 个资产`};
function syncExportLinks(p){if(!p?.exported)return;document.getElementById('projectZip').style.display='inline-flex';document.getElementById('assetsZip').style.display='inline-flex';document.getElementById('projectZip').href=p.downloadUrl;document.getElementById('assetsZip').href=p.selectedAssetsDownloadUrl}
async function save(){const data=await api(`/api/asset-projects/${projectId}/manual-slices`,{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(manualDoc)}); msg.textContent=`已保存 ${data.selectedSliceCount} 个资产`; return data}
function slug(s){return String(s).replace(/[^0-9A-Za-z_-]+/g,'_').replace(/^_+|_+$/g,'')}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
window.onresize = draw;
init().catch(e => msg.textContent = e.message);
</script>
</body>
</html>"""
