const http = require("http");
const { Buffer } = require("buffer");
const fs = require("fs");
const path = require("path");
const { DatabaseSync } = require("node:sqlite");

const HOST = process.env.HOST || "127.0.0.1";
const PORT = Number(process.env.PORT || 4173);
const ROOT_DIR = __dirname;
const STORAGE_DIR = path.join(ROOT_DIR, "storage");
const PROJECTS_DIR = path.join(STORAGE_DIR, "projects");
const DB_FILE = path.join(STORAGE_DIR, "app.sqlite");
const MAX_JSON_BYTES = Number(process.env.MANUAL_SLICE_MAX_JSON_BYTES || 80 * 1024 * 1024);

fs.mkdirSync(PROJECTS_DIR, { recursive: true });

const db = new DatabaseSync(DB_FILE);
initDatabase();

const server = http.createServer(async (request, response) => {
  try {
    if (request.method === "OPTIONS") {
      sendJson(response, 204, {});
      return;
    }

    const url = new URL(request.url || "/", `http://${request.headers.host || `${HOST}:${PORT}`}`);
    const pathname = decodeURIComponent(url.pathname);

    if (request.method === "GET" && pathname === "/api/health") {
      sendJson(response, 200, { ok: true, storageRoot: STORAGE_DIR });
      return;
    }

    if (request.method === "GET" && pathname === "/api/projects") {
      sendJson(response, 200, { projects: listProjects() });
      return;
    }

    if (request.method === "POST" && pathname === "/api/projects") {
      const payload = await readJson(request);
      const project = createProject(payload);
      sendJson(response, 201, { project });
      return;
    }

    const projectMatch = /^\/api\/projects\/([^/]+)(?:\/(.*))?$/.exec(pathname);
    if (projectMatch) {
      await handleProjectRoute(request, response, projectMatch[1], projectMatch[2] || "");
      return;
    }

    if (request.method === "GET") {
      serveStatic(pathname, response);
      return;
    }

    sendJson(response, 404, { error: "Not found" });
  } catch (error) {
    const statusCode = error.statusCode || 500;
    sendJson(response, statusCode, { error: error.message || "Internal server error" });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`Manual Slice Studio listening on http://${HOST}:${PORT}`);
});

async function handleProjectRoute(request, response, projectId, rest) {
  assertSafeId(projectId, "projectId");
  const project = getProjectRow(projectId);
  if (!project) {
    throw httpError(404, "Project not found");
  }

  if (request.method === "GET" && rest === "") {
    sendJson(response, 200, getProjectDetail(projectId));
    return;
  }

  if (request.method === "PATCH" && rest === "") {
    const payload = await readJson(request);
    sendJson(response, 200, { project: renameProject(projectId, payload.name) });
    return;
  }

  if (request.method === "DELETE" && rest === "") {
    deleteProject(projectId);
    sendJson(response, 200, { ok: true });
    return;
  }

  if (request.method === "POST" && rest === "pages") {
    const payload = await readJson(request);
    sendJson(response, 201, { pages: await addPages(projectId, payload.files) });
    return;
  }

  const sourceMatch = /^pages\/([^/]+)\/source$/.exec(rest);
  if (request.method === "GET" && sourceMatch) {
    sendPageSource(projectId, sourceMatch[1], response);
    return;
  }

  if (request.method === "PUT" && rest === "slices") {
    const payload = await readJson(request);
    saveSlices(projectId, payload);
    sendJson(response, 200, { ok: true, project: getProjectSummary(projectId) });
    return;
  }

  if (request.method === "POST" && rest === "export-assets") {
    const result = await exportAssets(projectId);
    sendJson(response, 200, result);
    return;
  }

  if (request.method === "GET" && rest === "assets.zip") {
    sendProjectZip(projectId, response);
    return;
  }

  sendJson(response, 404, { error: "Not found" });
}

function initDatabase() {
  db.exec(`
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS projects (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      page_count INTEGER NOT NULL DEFAULT 0,
      slice_count INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS pages (
      id TEXT NOT NULL,
      project_id TEXT NOT NULL,
      page_index INTEGER NOT NULL,
      original_name TEXT NOT NULL,
      original_path TEXT NOT NULL,
      width INTEGER NOT NULL,
      height INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      PRIMARY KEY (project_id, id),
      FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS slices (
      id TEXT NOT NULL,
      project_id TEXT NOT NULL,
      page_id TEXT NOT NULL,
      slice_index INTEGER NOT NULL,
      name TEXT NOT NULL,
      kind TEXT NOT NULL CHECK (kind IN ('image', 'icon')),
      x INTEGER NOT NULL,
      y INTEGER NOT NULL,
      width INTEGER NOT NULL,
      height INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      PRIMARY KEY (project_id, id),
      FOREIGN KEY (project_id, page_id) REFERENCES pages(project_id, id) ON DELETE CASCADE
    );
  `);
}

function listProjects() {
  return db.prepare(`
    SELECT id, name, created_at, updated_at, page_count, slice_count
    FROM projects
    ORDER BY updated_at DESC
  `).all().map(formatProject);
}

function createProject(payload) {
  const now = new Date().toISOString();
  const id = `project_${Date.now().toString(36)}_${randomHex(4)}`;
  const name = sanitizeName(payload && payload.name ? payload.name : "未命名项目");
  db.prepare(`
    INSERT INTO projects (id, name, created_at, updated_at, page_count, slice_count)
    VALUES (?, ?, ?, ?, 0, 0)
  `).run(id, name, now, now);
  fs.mkdirSync(path.join(PROJECTS_DIR, id, "originals"), { recursive: true });
  fs.mkdirSync(path.join(PROJECTS_DIR, id, "exports"), { recursive: true });
  return getProjectSummary(id);
}

function renameProject(projectId, name) {
  const nextName = sanitizeName(name || "未命名项目");
  db.prepare("UPDATE projects SET name = ?, updated_at = ? WHERE id = ?").run(nextName, new Date().toISOString(), projectId);
  return getProjectSummary(projectId);
}

function deleteProject(projectId) {
  runTransaction(() => {
    db.prepare("DELETE FROM projects WHERE id = ?").run(projectId);
  });
  fs.rmSync(path.join(PROJECTS_DIR, projectId), { recursive: true, force: true });
}

async function addPages(projectId, files) {
  if (!Array.isArray(files) || files.length === 0) {
    throw httpError(400, "files must be a non-empty array");
  }
  const existingCount = Number(db.prepare("SELECT COUNT(*) AS count FROM pages WHERE project_id = ?").get(projectId).count || 0);
  const now = new Date().toISOString();
  const projectDir = path.join(PROJECTS_DIR, projectId);
  const originalsDir = path.join(projectDir, "originals");
  fs.mkdirSync(originalsDir, { recursive: true });
  const normalizedFiles = [];

  for (const [fileIndex, file] of files.entries()) {
    const pageIndex = existingCount + fileIndex + 1;
    const pageId = `page_${String(pageIndex).padStart(4, "0")}`;
    const image = decodeImageDataUrl(file && file.dataUrl);
    const normalized = await normalizeUploadedImage(image);
    normalizedFiles.push({
      pageIndex,
      pageId,
      originalName: sanitizeFileName(file.name || `${pageId}.png`),
      buffer: normalized.buffer,
      width: normalized.width,
      height: normalized.height
    });
  }

  const pages = [];

  runTransaction(() => {
    for (const file of normalizedFiles) {
      const pageId = file.pageId;
      const relativePath = `projects/${projectId}/originals/${pageId}.png`;
      const absolutePath = path.join(STORAGE_DIR, relativePath);
      fs.writeFileSync(absolutePath, file.buffer);
      db.prepare(`
        INSERT INTO pages (id, project_id, page_index, original_name, original_path, width, height, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
      `).run(pageId, projectId, file.pageIndex, file.originalName, relativePath, file.width, file.height, now);
      pages.push({
        id: pageId,
        name: file.originalName,
        width: file.width,
        height: file.height,
        sourceUrl: `/api/projects/${projectId}/pages/${pageId}/source`,
        slices: []
      });
    }
    updateProjectCounts(projectId);
  });

  return pages;
}

function saveSlices(projectId, payload) {
  if (!payload || !Array.isArray(payload.pages)) {
    throw httpError(400, "pages must be an array");
  }
  const pageRows = db.prepare("SELECT id, width, height FROM pages WHERE project_id = ?").all(projectId);
  const pageMap = new Map(pageRows.map((page) => [page.id, page]));
  const now = new Date().toISOString();
  const seenProjectSliceIds = new Set();

  runTransaction(() => {
    db.prepare("DELETE FROM slices WHERE project_id = ?").run(projectId);
    for (const pagePayload of payload.pages) {
      const pageId = String(pagePayload.pageId || "");
      assertSafeId(pageId, "pageId");
      const page = pageMap.get(pageId);
      if (!page) {
        throw httpError(400, `Unknown pageId: ${pageId}`);
      }
      const slices = Array.isArray(pagePayload.slices) ? pagePayload.slices : [];
      const seenSliceIds = new Set();
      for (const [sliceIndex, slice] of slices.entries()) {
        const id = String(slice.id || `${pageId}__slice_${sliceIndex + 1}`);
        assertSafeSliceId(id);
        if (seenSliceIds.has(id)) {
          throw httpError(400, `Duplicate slice id: ${id}`);
        }
        if (seenProjectSliceIds.has(id)) {
          throw httpError(400, `Duplicate slice id across project: ${id}`);
        }
        seenSliceIds.add(id);
        seenProjectSliceIds.add(id);
        const kind = normalizeSliceKind(slice.kind);
        const box = normalizeBox(slice.bbox || {}, page);
        db.prepare(`
          INSERT INTO slices (id, project_id, page_id, slice_index, name, kind, x, y, width, height, created_at, updated_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `).run(id, projectId, pageId, sliceIndex + 1, sanitizeName(slice.name || `slice_${String(sliceIndex + 1).padStart(2, "0")}`), kind, box.x, box.y, box.width, box.height, now, now);
      }
    }
    updateProjectCounts(projectId);
  });
}

function getProjectDetail(projectId) {
  const project = getProjectSummary(projectId);
  if (!project) {
    throw httpError(404, "Project not found");
  }
  const pages = getProjectPages(projectId);
  const slices = db.prepare(`
    SELECT id, page_id, slice_index, name, kind, x, y, width, height
    FROM slices
    WHERE project_id = ?
    ORDER BY page_id ASC, slice_index ASC
  `).all(projectId);
  const sliceMap = new Map();
  for (const slice of slices) {
    if (!sliceMap.has(slice.page_id)) sliceMap.set(slice.page_id, []);
    sliceMap.get(slice.page_id).push(formatSlice(slice));
  }
  return {
    project,
    pages: pages.map((page) => ({
      ...page,
      slices: sliceMap.get(page.id) || []
    }))
  };
}

function getProjectPages(projectId) {
  return db.prepare(`
    SELECT id, original_name, width, height
    FROM pages
    WHERE project_id = ?
    ORDER BY page_index ASC
  `).all(projectId).map((page) => ({
    id: page.id,
    name: page.original_name,
    width: page.width,
    height: page.height,
    sourceUrl: `/api/projects/${projectId}/pages/${page.id}/source`
  }));
}

async function exportAssets(projectId) {
  const sharp = await loadSharp();
  const detail = getProjectDetail(projectId);
  const exportDir = path.join(PROJECTS_DIR, projectId, "exports");
  fs.mkdirSync(exportDir, { recursive: true });
  const files = [];
  const projectJson = {
    schema: "manual_slice_project.v1",
    exportedAt: new Date().toISOString(),
    project: detail.project,
    pages: detail.pages
  };
  const manifest = buildExportManifest(detail);
  files.push({ name: "project.json", data: Buffer.from(JSON.stringify(projectJson, null, 2)) });
  files.push({ name: "manifest.json", data: Buffer.from(JSON.stringify(manifest, null, 2)) });

  for (const [pageIndex, page] of detail.pages.entries()) {
    const originalName = `originals/page_${String(pageIndex + 1).padStart(4, "0")}.png`;
    const originalBuffer = fs.readFileSync(getPageOriginalPath(projectId, page.id));
    files.push({ name: originalName, data: originalBuffer });
    for (const [sliceIndex, slice] of page.slices.entries()) {
      const buffer = await sharp(originalBuffer)
        .extract({
          left: slice.bbox.x,
          top: slice.bbox.y,
          width: slice.bbox.width,
          height: slice.bbox.height
        })
        .png()
        .toBuffer();
      files.push({
        name: `slices/${page.id}/slice_${String(sliceIndex + 1).padStart(4, "0")}.png`,
        data: buffer
      });
    }
  }

  const zipPath = path.join(exportDir, "assets.zip");
  fs.writeFileSync(zipPath, createZipBuffer(files));
  return {
    ok: true,
    assetCount: detail.pages.reduce((sum, page) => sum + page.slices.length, 0),
    url: `/api/projects/${projectId}/assets.zip`
  };
}

function sendProjectZip(projectId, response) {
  const zipPath = path.join(PROJECTS_DIR, projectId, "exports", "assets.zip");
  if (!fs.existsSync(zipPath)) {
    throw httpError(404, "assets.zip has not been generated");
  }
  response.writeHead(200, {
    "content-type": "application/zip",
    "content-disposition": `attachment; filename="${projectId}-assets.zip"`,
    "access-control-allow-origin": "*"
  });
  fs.createReadStream(zipPath).pipe(response);
}

function buildExportManifest(detail) {
  return {
    schema: "manual_ui_slices.v1",
    exportedAt: new Date().toISOString(),
    project: detail.project,
    pages: detail.pages.map((page, pageIndex) => ({
      pageId: page.id,
      originalName: page.name,
      original: `originals/page_${String(pageIndex + 1).padStart(4, "0")}.png`,
      width: page.width,
      height: page.height,
      slices: page.slices.map((slice, sliceIndex) => ({
        id: slice.id,
        name: slice.name,
        kind: slice.kind,
        filename: `slices/${page.id}/slice_${String(sliceIndex + 1).padStart(4, "0")}.png`,
        placement: { ...slice.bbox },
        selected: true
      }))
    }))
  };
}

function sendPageSource(projectId, pageId, response) {
  assertSafeId(pageId, "pageId");
  const filePath = getPageOriginalPath(projectId, pageId);
  response.writeHead(200, {
    "content-type": "image/png",
    "cache-control": "no-store",
    "access-control-allow-origin": "*"
  });
  fs.createReadStream(filePath).pipe(response);
}

function getPageOriginalPath(projectId, pageId) {
  const row = db.prepare("SELECT original_path FROM pages WHERE project_id = ? AND id = ?").get(projectId, pageId);
  if (!row) {
    throw httpError(404, "Page not found");
  }
  const filePath = path.join(STORAGE_DIR, row.original_path);
  assertInside(STORAGE_DIR, filePath);
  if (!fs.existsSync(filePath)) {
    throw httpError(404, "Original image not found");
  }
  return filePath;
}

function getProjectRow(projectId) {
  return db.prepare("SELECT * FROM projects WHERE id = ?").get(projectId);
}

function getProjectSummary(projectId) {
  const row = getProjectRow(projectId);
  return row ? formatProject(row) : null;
}

function formatProject(row) {
  return {
    id: row.id,
    name: row.name,
    pageCount: row.page_count,
    sliceCount: row.slice_count,
    createdAt: row.created_at,
    updatedAt: row.updated_at
  };
}

function formatSlice(row) {
  return {
    id: row.id,
    name: row.name,
    kind: row.kind,
    selected: true,
    bbox: {
      x: row.x,
      y: row.y,
      width: row.width,
      height: row.height
    }
  };
}

function updateProjectCounts(projectId) {
  const pageCount = Number(db.prepare("SELECT COUNT(*) AS count FROM pages WHERE project_id = ?").get(projectId).count || 0);
  const sliceCount = Number(db.prepare("SELECT COUNT(*) AS count FROM slices WHERE project_id = ?").get(projectId).count || 0);
  db.prepare("UPDATE projects SET page_count = ?, slice_count = ?, updated_at = ? WHERE id = ?").run(pageCount, sliceCount, new Date().toISOString(), projectId);
}

function runTransaction(fn) {
  db.exec("BEGIN");
  try {
    const result = fn();
    db.exec("COMMIT");
    return result;
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
}

function serveStatic(pathname, response) {
  const routePath = pathname === "/" ? "/workspace.html" : pathname;
  if (routePath === "/storage" || routePath.startsWith("/storage/")) {
    sendJson(response, 404, { error: "Not found" });
    return;
  }
  const filePath = path.normalize(path.join(ROOT_DIR, routePath));
  assertInside(ROOT_DIR, filePath);
  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    sendJson(response, 404, { error: "Not found" });
    return;
  }
  response.writeHead(200, {
    "content-type": contentTypeFor(filePath),
    "cache-control": "no-store"
  });
  fs.createReadStream(filePath).pipe(response);
}

async function readJson(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_JSON_BYTES) {
      throw httpError(413, "Request body too large");
    }
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw httpError(400, "Invalid JSON");
  }
}

function sendJson(response, statusCode, data) {
  response.writeHead(statusCode, {
    "content-type": "application/json; charset=utf-8",
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
    "access-control-allow-headers": "content-type"
  });
  response.end(JSON.stringify(data));
}

function decodeImageDataUrl(dataUrl) {
  const match = /^data:(image\/[A-Za-z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+)$/.exec(String(dataUrl || ""));
  if (!match) {
    throw httpError(400, "image dataUrl must be a base64 image data URL");
  }
  return { mime: match[1], buffer: Buffer.from(match[2].replace(/\s/g, ""), "base64") };
}

async function normalizeUploadedImage(image) {
  if (image.mime === "image/png") {
    const size = parsePngSize(image.buffer);
    return { buffer: image.buffer, width: size.width, height: size.height };
  }
  const sharp = await loadSharp();
  const normalizedBuffer = await sharp(image.buffer, { failOn: "none" }).png().toBuffer();
  const size = parsePngSize(normalizedBuffer);
  return { buffer: normalizedBuffer, width: size.width, height: size.height };
}

function parsePngSize(buffer) {
  if (buffer.length < 24 || buffer.readUInt32BE(0) !== 0x89504e47 || buffer.readUInt32BE(4) !== 0x0d0a1a0a) {
    throw httpError(400, "Invalid PNG image");
  }
  return {
    width: buffer.readUInt32BE(16),
    height: buffer.readUInt32BE(20)
  };
}

function normalizeBox(box, page) {
  const x = clampInteger(box.x, 0, page.width - 1, "bbox.x");
  const y = clampInteger(box.y, 0, page.height - 1, "bbox.y");
  const width = clampInteger(box.width, 1, page.width - x, "bbox.width");
  const height = clampInteger(box.height, 1, page.height - y, "bbox.height");
  return { x, y, width, height };
}

function clampInteger(value, min, max, name) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    throw httpError(400, `${name} must be a number`);
  }
  const integer = Math.round(number);
  if (integer < min || integer > max) {
    throw httpError(400, `${name} is out of bounds`);
  }
  return integer;
}

function normalizeSliceKind(value) {
  if (value !== "image" && value !== "icon") {
    throw httpError(400, "slice kind must be image or icon");
  }
  return value;
}

function createZipBuffer(files) {
  const localParts = [];
  const centralParts = [];
  let offset = 0;
  for (const file of files) {
    const name = Buffer.from(file.name);
    const data = Buffer.isBuffer(file.data) ? file.data : Buffer.from(file.data);
    const crc = crc32(data);
    const local = Buffer.concat([
      uint32(0x04034b50), uint16(20), uint16(0), uint16(0), uint16(0), uint16(0),
      uint32(crc), uint32(data.length), uint32(data.length), uint16(name.length), uint16(0), name, data
    ]);
    localParts.push(local);
    centralParts.push(Buffer.concat([
      uint32(0x02014b50), uint16(20), uint16(20), uint16(0), uint16(0), uint16(0), uint16(0),
      uint32(crc), uint32(data.length), uint32(data.length), uint16(name.length), uint16(0), uint16(0),
      uint16(0), uint16(0), uint32(0), uint32(offset), name
    ]));
    offset += local.length;
  }
  const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
  const centralOffset = offset;
  const end = Buffer.concat([
    uint32(0x06054b50), uint16(0), uint16(0), uint16(files.length), uint16(files.length),
    uint32(centralSize), uint32(centralOffset), uint16(0)
  ]);
  return Buffer.concat([...localParts, ...centralParts, end]);
}

function uint16(value) {
  const buffer = Buffer.alloc(2);
  buffer.writeUInt16LE(value);
  return buffer;
}

function uint32(value) {
  const buffer = Buffer.alloc(4);
  buffer.writeUInt32LE(value >>> 0);
  return buffer;
}

function crc32(bytes) {
  let crc = -1;
  for (const byte of bytes) {
    crc ^= byte;
    for (let index = 0; index < 8; index += 1) {
      crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
    }
  }
  return (crc ^ -1) >>> 0;
}

function sanitizeName(value) {
  return String(value || "untitled").trim().replace(/[\\/:*?"<>|]+/g, "_").slice(0, 80) || "untitled";
}

function sanitizeFileName(value) {
  const name = path.basename(String(value || "source.png")).replace(/[\\/:*?"<>|]+/g, "_").slice(0, 120);
  return name || "source.png";
}

function assertSafeId(value, name) {
  if (!/^[A-Za-z0-9_-]+$/.test(String(value || ""))) {
    throw httpError(400, `${name} is invalid`);
  }
}

function assertSafeSliceId(value) {
  if (!/^[A-Za-z0-9_-]+(?:__[A-Za-z0-9_-]+)*$/.test(String(value || ""))) {
    throw httpError(400, "slice id is invalid");
  }
}

function assertInside(root, target) {
  const relative = path.relative(root, target);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw httpError(400, "Invalid path");
  }
}

function randomHex(bytes) {
  return Array.from({ length: bytes }, () => Math.floor(Math.random() * 256).toString(16).padStart(2, "0")).join("");
}

function contentTypeFor(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === ".html") return "text/html; charset=utf-8";
  if (ext === ".js") return "text/javascript; charset=utf-8";
  if (ext === ".css") return "text/css; charset=utf-8";
  if (ext === ".json") return "application/json; charset=utf-8";
  if (ext === ".png") return "image/png";
  if (ext === ".svg") return "image/svg+xml";
  return "application/octet-stream";
}

function httpError(statusCode, message) {
  const error = new Error(message);
  error.statusCode = statusCode;
  return error;
}

async function loadSharp() {
  try {
    return require("sharp");
  } catch (error) {
    throw httpError(500, `sharp is required for export. Run npm install first. ${error.message}`);
  }
}
