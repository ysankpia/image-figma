import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";
import { db, transaction, type PageRow, type ProjectRow, type SliceRow } from "./db";
import { maxBatchUploadBytes, maxUploadBytes, projectsRoot, storageRoot } from "./config";
import { httpError } from "./errors";
import { assertInside, randomHex, sanitizeFileName, sanitizeName } from "./utils";
import { assertSafeId, assertSafeSliceId, normalizeSliceBox, normalizeSliceKind } from "../shared/validation";
import type { PageRecord, ProjectDetail, ProjectListItem, ProjectSummary, SaveSlicesRequest, SliceRecord } from "../shared/types";

export function listProjects(): ProjectSummary[] {
  return db.query<ProjectRow, []>(`
    SELECT id, name, created_at, updated_at, page_count, slice_count
    FROM projects
    ORDER BY updated_at DESC
  `).all().map(formatProject);
}

export function listProjectCards(): ProjectListItem[] {
  const projects = listProjects();
  const firstPages = db.query<PageRow, []>(`
    SELECT p.*
    FROM pages p
    INNER JOIN (
      SELECT project_id, MIN(page_index) AS first_page_index
      FROM pages
      GROUP BY project_id
    ) first ON first.project_id = p.project_id AND first.first_page_index = p.page_index
  `).all();
  const firstPageByProject = new Map(firstPages.map((page) => [page.project_id, formatPage(page)]));
  return projects.map((project) => ({
    ...project,
    firstPage: firstPageByProject.get(project.id) || null
  }));
}

export function createProject(payload: { name?: string }): ProjectSummary {
  const now = new Date().toISOString();
  const id = `project_${Date.now().toString(36)}_${randomHex(4)}`;
  const name = sanitizeName(payload.name, "未命名项目");
  db.query(`
    INSERT INTO projects (id, name, created_at, updated_at, page_count, slice_count)
    VALUES (?, ?, ?, ?, 0, 0)
  `).run(id, name, now, now);
  fs.mkdirSync(path.join(projectsRoot, id, "originals"), { recursive: true });
  fs.mkdirSync(path.join(projectsRoot, id, "exports"), { recursive: true });
  const project = getProjectSummary(id);
  if (!project) throw httpError(500, "Project was not created");
  return project;
}

export function renameProject(projectId: string, name: string): ProjectSummary {
  assertSafeId(projectId, "projectId");
  assertProjectExists(projectId);
  db.query("UPDATE projects SET name = ?, updated_at = ? WHERE id = ?").run(sanitizeName(name, "未命名项目"), new Date().toISOString(), projectId);
  const project = getProjectSummary(projectId);
  if (!project) throw httpError(404, "Project not found");
  return project;
}

export function renamePage(projectId: string, pageId: string, displayName: string): PageRecord {
  assertSafeId(projectId, "projectId");
  assertSafeId(pageId, "pageId");
  assertProjectExists(projectId);
  const now = new Date().toISOString();
  db.query("UPDATE pages SET display_name = ? WHERE project_id = ? AND id = ?").run(sanitizeName(displayName, ""), projectId, pageId);
  db.query("UPDATE projects SET updated_at = ? WHERE id = ?").run(now, projectId);
  const page = db.query<PageRow, [string, string]>("SELECT * FROM pages WHERE project_id = ? AND id = ?").get(projectId, pageId);
  if (!page) throw httpError(404, "Page not found");
  return formatPage(page);
}

export function deleteProject(projectId: string): void {
  assertSafeId(projectId, "projectId");
  assertProjectExists(projectId);
  transaction(() => {
    db.query("DELETE FROM projects WHERE id = ?").run(projectId);
  });
  fs.rmSync(path.join(projectsRoot, projectId), { recursive: true, force: true });
}

export async function addPages(projectId: string, files: File | File[] | undefined): Promise<PageRecord[]> {
  assertSafeId(projectId, "projectId");
  assertProjectExists(projectId);
  const fileList = Array.isArray(files) ? files : files ? [files] : [];
  if (!fileList.length) throw httpError(400, "files must be provided");

  assertUploadLimits(fileList);
  const existingCount = Number(db.query<{ count: number }, [string]>("SELECT COUNT(*) AS count FROM pages WHERE project_id = ?").get(projectId)?.count || 0);
  const nextPageIdNumber = getNextPageIdNumber(projectId);
  const now = new Date().toISOString();
  const originalsDir = path.join(projectsRoot, projectId, "originals");
  fs.mkdirSync(originalsDir, { recursive: true });

  const normalizedFiles: Array<{
    pageIndex: number;
    pageId: string;
    originalName: string;
    buffer: Buffer;
    width: number;
    height: number;
  }> = [];

  for (const [fileIndex, file] of fileList.entries()) {
    if (!file.type.startsWith("image/")) throw httpError(400, "uploaded files must be images");
    const pageIndex = existingCount + fileIndex + 1;
    const pageId = `page_${String(nextPageIdNumber + fileIndex).padStart(4, "0")}`;
    const inputBuffer = Buffer.from(await file.arrayBuffer());
    const buffer = await sharp(inputBuffer, { failOn: "none" }).png().toBuffer();
    const metadata = await sharp(buffer).metadata();
    if (!metadata.width || !metadata.height) throw httpError(400, "invalid image");
    normalizedFiles.push({
      pageIndex,
      pageId,
      originalName: sanitizeFileName(file.name || `${pageId}.png`),
      buffer,
      width: metadata.width,
      height: metadata.height
    });
  }

  const pages: PageRecord[] = [];
  transaction(() => {
    for (const file of normalizedFiles) {
      const relativePath = `projects/${projectId}/originals/${file.pageId}.png`;
      const absolutePath = path.join(storageRoot, relativePath);
      assertInside(storageRoot, absolutePath);
      fs.writeFileSync(absolutePath, file.buffer);
      db.query(`
        INSERT INTO pages (id, project_id, page_index, original_name, display_name, original_path, width, height, created_at)
        VALUES (?, ?, ?, ?, '', ?, ?, ?, ?)
      `).run(file.pageId, projectId, file.pageIndex, file.originalName, relativePath, file.width, file.height, now);
      pages.push(formatPage({
        id: file.pageId,
        project_id: projectId,
        page_index: file.pageIndex,
        original_name: file.originalName,
        display_name: "",
        original_path: relativePath,
        width: file.width,
        height: file.height,
        created_at: now
      }));
    }
    updateProjectCounts(projectId);
  });
  return pages;
}

export function deletePage(projectId: string, pageId: string): ProjectDetail {
  assertSafeId(projectId, "projectId");
  assertSafeId(pageId, "pageId");
  assertProjectExists(projectId);
  const page = getPageRow(projectId, pageId);
  const absolutePath = path.join(storageRoot, page.original_path);
  assertInside(storageRoot, absolutePath);
  const trashPath = `${absolutePath}.deleted-${Date.now()}`;
  let moved = false;
  if (fs.existsSync(absolutePath)) {
    fs.renameSync(absolutePath, trashPath);
    moved = true;
  }
  try {
    transaction(() => {
      db.query("DELETE FROM pages WHERE project_id = ? AND id = ?").run(projectId, pageId);
      reindexPages(projectId);
      updateProjectCounts(projectId);
    });
  } catch (error) {
    if (moved && fs.existsSync(trashPath)) fs.renameSync(trashPath, absolutePath);
    throw error;
  }
  if (moved) fs.rmSync(trashPath, { force: true });
  return getProjectDetail(projectId);
}

export function reorderPages(projectId: string, pageIds: string[]): ProjectDetail {
  assertSafeId(projectId, "projectId");
  assertProjectExists(projectId);
  if (!Array.isArray(pageIds) || !pageIds.length) throw httpError(400, "pageIds must be a non-empty array");
  const pages = db.query<PageRow, [string]>("SELECT * FROM pages WHERE project_id = ?").all(projectId);
  const existingIds = pages.map((page) => page.id).sort();
  const requestedIds = pageIds.map((id) => {
    assertSafeId(String(id), "pageId");
    return String(id);
  }).sort();
  if (existingIds.length !== requestedIds.length || existingIds.some((id, index) => id !== requestedIds[index])) {
    throw httpError(400, "pageIds must include every page exactly once");
  }
  transaction(() => {
    for (const [index, id] of pageIds.entries()) {
      db.query("UPDATE pages SET page_index = ? WHERE project_id = ? AND id = ?").run(index + 1, projectId, id);
    }
    db.query("UPDATE projects SET updated_at = ? WHERE id = ?").run(new Date().toISOString(), projectId);
  });
  return getProjectDetail(projectId);
}

export async function replacePage(projectId: string, pageId: string, file: File | undefined): Promise<ProjectDetail> {
  assertSafeId(projectId, "projectId");
  assertSafeId(pageId, "pageId");
  assertProjectExists(projectId);
  if (!file) throw httpError(400, "file must be provided");
  if (!file.type.startsWith("image/")) throw httpError(400, "uploaded file must be an image");
  assertUploadLimits([file]);

  const page = getPageRow(projectId, pageId);
  const inputBuffer = Buffer.from(await file.arrayBuffer());
  const buffer = await sharp(inputBuffer, { failOn: "none" }).png().toBuffer();
  const metadata = await sharp(buffer).metadata();
  if (!metadata.width || !metadata.height) throw httpError(400, "invalid image");

  const relativePath = page.original_path;
  const absolutePath = path.join(storageRoot, relativePath);
  assertInside(storageRoot, absolutePath);
  const replacementPath = `${absolutePath}.replacement-${Date.now()}`;
  const backupPath = `${absolutePath}.backup-${Date.now()}`;
  fs.writeFileSync(replacementPath, buffer);
  let hasBackup = false;
  try {
    if (fs.existsSync(absolutePath)) {
      fs.renameSync(absolutePath, backupPath);
      hasBackup = true;
    }
    fs.renameSync(replacementPath, absolutePath);
    transaction(() => {
      db.query("DELETE FROM slices WHERE project_id = ? AND page_id = ?").run(projectId, pageId);
      db.query(`
        UPDATE pages
        SET original_name = ?, width = ?, height = ?
        WHERE project_id = ? AND id = ?
      `).run(sanitizeFileName(file.name || `${pageId}.png`), metadata.width, metadata.height, projectId, pageId);
      updateProjectCounts(projectId);
    });
  } catch (error) {
    fs.rmSync(replacementPath, { force: true });
    if (hasBackup) {
      fs.rmSync(absolutePath, { force: true });
      fs.renameSync(backupPath, absolutePath);
    } else {
      fs.rmSync(absolutePath, { force: true });
    }
    throw error;
  }
  if (hasBackup) fs.rmSync(backupPath, { force: true });
  return getProjectDetail(projectId);
}

export function saveSlices(projectId: string, payload: SaveSlicesRequest): ProjectSummary {
  assertSafeId(projectId, "projectId");
  assertProjectExists(projectId);
  if (!Array.isArray(payload.pages)) throw httpError(400, "pages must be an array");

  const pageRows = db.query<PageRow, [string]>("SELECT * FROM pages WHERE project_id = ?").all(projectId);
  const pageMap = new Map(pageRows.map((page) => [page.id, page]));
  const now = new Date().toISOString();
  const seenProjectSliceIds = new Set<string>();

  transaction(() => {
    db.query("DELETE FROM slices WHERE project_id = ?").run(projectId);
    for (const pagePayload of payload.pages) {
      const pageId = String(pagePayload.pageId || "");
      assertSafeId(pageId, "pageId");
      const page = pageMap.get(pageId);
      if (!page) throw httpError(400, `Unknown pageId: ${pageId}`);
      const seenPageSliceIds = new Set<string>();
      for (const [sliceIndex, slice] of (pagePayload.slices || []).entries()) {
        assertSafeSliceId(slice.id);
        if (seenPageSliceIds.has(slice.id) || seenProjectSliceIds.has(slice.id)) {
          throw httpError(400, `Duplicate slice id: ${slice.id}`);
        }
        seenPageSliceIds.add(slice.id);
        seenProjectSliceIds.add(slice.id);
        const kind = normalizeSliceKind(slice.kind);
        const box = normalizeSliceBox(slice.bbox, { width: page.width, height: page.height });
        db.query(`
          INSERT INTO slices (id, project_id, page_id, slice_index, name, kind, x, y, width, height, created_at, updated_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `).run(slice.id, projectId, pageId, sliceIndex + 1, sanitizeName(slice.name, `slice_${String(sliceIndex + 1).padStart(2, "0")}`), kind, box.x, box.y, box.width, box.height, now, now);
      }
    }
    updateProjectCounts(projectId);
  });

  const project = getProjectSummary(projectId);
  if (!project) throw httpError(404, "Project not found");
  return project;
}

export function getProjectDetail(projectId: string): ProjectDetail {
  assertSafeId(projectId, "projectId");
  const project = getProjectSummary(projectId);
  if (!project) throw httpError(404, "Project not found");
  const pages = db.query<PageRow, [string]>("SELECT * FROM pages WHERE project_id = ? ORDER BY page_index ASC").all(projectId);
  const slices = db.query<SliceRow, [string]>("SELECT * FROM slices WHERE project_id = ? ORDER BY page_id ASC, slice_index ASC").all(projectId);
  const slicesByPage = new Map<string, SliceRecord[]>();
  for (const slice of slices) {
    const list = slicesByPage.get(slice.page_id) || [];
    list.push(formatSlice(slice));
    slicesByPage.set(slice.page_id, list);
  }
  return {
    project,
    pages: pages.map((page) => ({
      ...formatPage(page),
      slices: slicesByPage.get(page.id) || []
    }))
  };
}

export function getPageOriginalPath(projectId: string, pageId: string): string {
  assertSafeId(projectId, "projectId");
  assertSafeId(pageId, "pageId");
  const row = db.query<Pick<PageRow, "original_path">, [string, string]>("SELECT original_path FROM pages WHERE project_id = ? AND id = ?").get(projectId, pageId);
  if (!row) throw httpError(404, "Page not found");
  const absolutePath = path.join(storageRoot, row.original_path);
  assertInside(storageRoot, absolutePath);
  if (!fs.existsSync(absolutePath)) throw httpError(404, "Original image not found");
  return absolutePath;
}

function getPageRow(projectId: string, pageId: string): PageRow {
  const page = db.query<PageRow, [string, string]>("SELECT * FROM pages WHERE project_id = ? AND id = ?").get(projectId, pageId);
  if (!page) throw httpError(404, "Page not found");
  return page;
}

export function getProjectSummary(projectId: string): ProjectSummary | null {
  const row = db.query<ProjectRow, [string]>("SELECT * FROM projects WHERE id = ?").get(projectId);
  return row ? formatProject(row) : null;
}

export function assertProjectExists(projectId: string): void {
  if (!getProjectSummary(projectId)) throw httpError(404, "Project not found");
}

export function updateProjectCounts(projectId: string): void {
  const pageCount = Number(db.query<{ count: number }, [string]>("SELECT COUNT(*) AS count FROM pages WHERE project_id = ?").get(projectId)?.count || 0);
  const sliceCount = Number(db.query<{ count: number }, [string]>("SELECT COUNT(*) AS count FROM slices WHERE project_id = ?").get(projectId)?.count || 0);
  db.query("UPDATE projects SET page_count = ?, slice_count = ?, updated_at = ? WHERE id = ?").run(pageCount, sliceCount, new Date().toISOString(), projectId);
}

function reindexPages(projectId: string): void {
  const pages = db.query<PageRow, [string]>("SELECT * FROM pages WHERE project_id = ? ORDER BY page_index ASC").all(projectId);
  for (const [index, page] of pages.entries()) {
    db.query("UPDATE pages SET page_index = ? WHERE project_id = ? AND id = ?").run(index + 1, projectId, page.id);
  }
}

function getNextPageIdNumber(projectId: string): number {
  const pages = db.query<Pick<PageRow, "id">, [string]>("SELECT id FROM pages WHERE project_id = ?").all(projectId);
  const maxId = pages.reduce((max, page) => {
    const match = /^page_(\d+)$/.exec(page.id);
    return match ? Math.max(max, Number(match[1])) : max;
  }, 0);
  return maxId + 1;
}

function assertUploadLimits(files: File[]): void {
  let total = 0;
  for (const file of files) {
    if (file.size > maxUploadBytes) {
      throw httpError(400, `File exceeds ${Math.round(maxUploadBytes / 1024 / 1024)}MB limit`);
    }
    total += file.size;
  }
  if (total > maxBatchUploadBytes) {
    throw httpError(400, `Upload batch exceeds ${Math.round(maxBatchUploadBytes / 1024 / 1024)}MB limit`);
  }
}

function formatProject(row: ProjectRow): ProjectSummary {
  return {
    id: row.id,
    name: row.name,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    pageCount: row.page_count,
    sliceCount: row.slice_count
  };
}

function formatPage(row: PageRow): PageRecord {
  return {
    id: row.id,
    projectId: row.project_id,
    pageIndex: row.page_index,
    originalName: row.original_name,
    displayName: row.display_name,
    width: row.width,
    height: row.height,
    sourceUrl: `/api/projects/${row.project_id}/pages/${row.id}/source`
  };
}

function formatSlice(row: SliceRow): SliceRecord {
  return {
    id: row.id,
    projectId: row.project_id,
    pageId: row.page_id,
    sliceIndex: row.slice_index,
    name: row.name,
    kind: row.kind,
    bbox: { x: row.x, y: row.y, width: row.width, height: row.height },
    selected: true
  };
}
