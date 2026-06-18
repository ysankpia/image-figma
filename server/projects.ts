import fs from "node:fs";
import sharp from "sharp";
import { db, transaction, type PageRow, type ProjectRow, type SliceRow } from "./db";
import { maxBatchUploadBytes, maxUploadBytes } from "./config";
import { httpError } from "./errors";
import { randomHex, sanitizeFileName, sanitizeName } from "./utils";
import { storage } from "./storage";
import { defaultSliceName, isDefaultSliceName, normalizeDefaultSliceNames } from "../shared/slice-names";
import { assertSafeId, assertSafeSliceId, normalizeCutMode, normalizeSliceBox, normalizeSliceKind } from "../shared/validation";
import type { PageRecord, ProjectDetail, ProjectListItem, ProjectSummary, SaveSlicesRequest, SliceRecord } from "../shared/types";

export async function listProjects(userId: string): Promise<ProjectSummary[]> {
  return (await db.all<ProjectRow>(`
    SELECT id, name, created_at, updated_at, page_count, slice_count
    FROM projects
    WHERE user_id = ?
    ORDER BY updated_at DESC
  `, [userId])).map(formatProject);
}

export async function listProjectCards(userId: string): Promise<ProjectListItem[]> {
  const projects = await listProjects(userId);
  const firstPages = await db.all<PageRow>(`
    SELECT p.*
    FROM pages p
    INNER JOIN projects pr ON pr.id = p.project_id
    INNER JOIN (
      SELECT project_id, MIN(page_index) AS first_page_index
      FROM pages
      GROUP BY project_id
    ) first ON first.project_id = p.project_id AND first.first_page_index = p.page_index
    WHERE pr.user_id = ?
  `, [userId]);
  const firstPageByProject = new Map(firstPages.map((page) => [page.project_id, formatPage(page)]));
  return projects.map((project) => ({
    ...project,
    firstPage: firstPageByProject.get(project.id) || null
  }));
}

export async function createProject(userId: string, payload: { name?: string }): Promise<ProjectSummary> {
  const now = new Date().toISOString();
  const id = `project_${Date.now().toString(36)}_${randomHex(4)}`;
  const name = sanitizeName(payload.name, "未命名项目");
  await db.run(`
    INSERT INTO projects (id, user_id, name, created_at, updated_at, page_count, slice_count)
    VALUES (?, ?, ?, ?, ?, 0, 0)
  `, [id, userId, name, now, now]);
  storage.ensureProjectDirectories(userId, id);
  const project = await getProjectSummary(userId, id);
  if (!project) throw httpError(500, "Project was not created");
  return project;
}

export async function renameProject(userId: string, projectId: string, name: string): Promise<ProjectSummary> {
  assertSafeId(projectId, "projectId");
  await assertProjectExists(userId, projectId);
  await db.run("UPDATE projects SET name = ?, updated_at = ? WHERE id = ? AND user_id = ?", [sanitizeName(name, "未命名项目"), new Date().toISOString(), projectId, userId]);
  const project = await getProjectSummary(userId, projectId);
  if (!project) throw httpError(404, "Project not found");
  return project;
}

export async function renamePage(userId: string, projectId: string, pageId: string, displayName: string): Promise<PageRecord> {
  assertSafeId(projectId, "projectId");
  assertSafeId(pageId, "pageId");
  await assertProjectExists(userId, projectId);
  const now = new Date().toISOString();
  await db.run("UPDATE pages SET display_name = ? WHERE project_id = ? AND id = ?", [sanitizeName(displayName, ""), projectId, pageId]);
  await db.run("UPDATE projects SET updated_at = ? WHERE id = ?", [now, projectId]);
  const page = await db.get<PageRow>("SELECT * FROM pages WHERE project_id = ? AND id = ?", [projectId, pageId]);
  if (!page) throw httpError(404, "Page not found");
  return formatPage(page);
}

export async function deleteProject(userId: string, projectId: string): Promise<void> {
  assertSafeId(projectId, "projectId");
  await assertProjectExists(userId, projectId);
  await transaction(async () => {
    await db.run("DELETE FROM projects WHERE id = ? AND user_id = ?", [projectId, userId]);
  });
  storage.deleteProject(userId, projectId);
}

export async function addPages(userId: string, projectId: string, files: File | File[] | undefined): Promise<PageRecord[]> {
  assertSafeId(projectId, "projectId");
  await assertProjectExists(userId, projectId);
  const fileList = Array.isArray(files) ? files : files ? [files] : [];
  if (!fileList.length) throw httpError(400, "files must be provided");

  assertUploadLimits(fileList);
  const existingCount = Number((await db.get<{ count: number }>("SELECT COUNT(*) AS count FROM pages WHERE project_id = ?", [projectId]))?.count || 0);
  const nextPageIdNumber = await getNextPageIdNumber(projectId);
  const now = new Date().toISOString();
  storage.ensureProjectDirectories(userId, projectId);

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
  await transaction(async () => {
    for (const file of normalizedFiles) {
      const relativePath = storage.projectOriginalImageKey(userId, projectId, file.pageId);
      storage.write(relativePath, file.buffer);
      await db.run(`
        INSERT INTO pages (id, project_id, page_index, original_name, display_name, original_path, width, height, created_at)
        VALUES (?, ?, ?, ?, '', ?, ?, ?, ?)
      `, [file.pageId, projectId, file.pageIndex, file.originalName, relativePath, file.width, file.height, now]);
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
    await updateProjectCounts(projectId);
  });
  return pages;
}

export async function deletePage(userId: string, projectId: string, pageId: string): Promise<ProjectDetail> {
  assertSafeId(projectId, "projectId");
  assertSafeId(pageId, "pageId");
  await assertProjectExists(userId, projectId);
  const page = await getPageRow(projectId, pageId);
  const absolutePath = storage.absolutePath(page.original_path);
  const trashPath = `${absolutePath}.deleted-${Date.now()}`;
  let moved = false;
  if (fs.existsSync(absolutePath)) {
    fs.renameSync(absolutePath, trashPath);
    moved = true;
  }
  try {
    await transaction(async () => {
      await db.run("DELETE FROM pages WHERE project_id = ? AND id = ?", [projectId, pageId]);
      await reindexPages(projectId);
      await updateProjectCounts(projectId);
    });
  } catch (error) {
    if (moved && fs.existsSync(trashPath)) fs.renameSync(trashPath, absolutePath);
    throw error;
  }
  if (moved) fs.rmSync(trashPath, { force: true });
  return await getProjectDetail(userId, projectId);
}

export async function reorderPages(userId: string, projectId: string, pageIds: string[]): Promise<ProjectDetail> {
  assertSafeId(projectId, "projectId");
  await assertProjectExists(userId, projectId);
  if (!Array.isArray(pageIds) || !pageIds.length) throw httpError(400, "pageIds must be a non-empty array");
  const pages = await db.all<PageRow>("SELECT * FROM pages WHERE project_id = ?", [projectId]);
  const existingIds = pages.map((page) => page.id).sort();
  const requestedIds = pageIds.map((id) => {
    assertSafeId(String(id), "pageId");
    return String(id);
  }).sort();
  if (existingIds.length !== requestedIds.length || existingIds.some((id, index) => id !== requestedIds[index])) {
    throw httpError(400, "pageIds must include every page exactly once");
  }
  await transaction(async () => {
    for (const [index, id] of pageIds.entries()) {
      await db.run("UPDATE pages SET page_index = ? WHERE project_id = ? AND id = ?", [index + 1, projectId, id]);
    }
    await db.run("UPDATE projects SET updated_at = ? WHERE id = ?", [new Date().toISOString(), projectId]);
  });
  return await getProjectDetail(userId, projectId);
}

export async function replacePage(userId: string, projectId: string, pageId: string, file: File | undefined): Promise<ProjectDetail> {
  assertSafeId(projectId, "projectId");
  assertSafeId(pageId, "pageId");
  await assertProjectExists(userId, projectId);
  if (!file) throw httpError(400, "file must be provided");
  if (!file.type.startsWith("image/")) throw httpError(400, "uploaded file must be an image");
  assertUploadLimits([file]);

  const page = await getPageRow(projectId, pageId);
  const inputBuffer = Buffer.from(await file.arrayBuffer());
  const buffer = await sharp(inputBuffer, { failOn: "none" }).png().toBuffer();
  const metadata = await sharp(buffer).metadata();
  if (!metadata.width || !metadata.height) throw httpError(400, "invalid image");

  const relativePath = page.original_path;
  const absolutePath = storage.absolutePath(relativePath);
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
    await transaction(async () => {
      await db.run("DELETE FROM slices WHERE project_id = ? AND page_id = ?", [projectId, pageId]);
      await db.run(`
        UPDATE pages
        SET original_name = ?, width = ?, height = ?
        WHERE project_id = ? AND id = ?
      `, [sanitizeFileName(file.name || `${pageId}.png`), metadata.width, metadata.height, projectId, pageId]);
      await updateProjectCounts(projectId);
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
  return await getProjectDetail(userId, projectId);
}

export async function saveSlices(userId: string, projectId: string, payload: SaveSlicesRequest): Promise<ProjectSummary> {
  assertSafeId(projectId, "projectId");
  await assertProjectExists(userId, projectId);
  if (!Array.isArray(payload.pages)) throw httpError(400, "pages must be an array");

  const pageRows = await db.all<PageRow>("SELECT * FROM pages WHERE project_id = ?", [projectId]);
  const pageMap = new Map(pageRows.map((page) => [page.id, page]));
  const now = new Date().toISOString();
  const seenProjectSliceIds = new Set<string>();

  await transaction(async () => {
    await db.run("DELETE FROM slices WHERE project_id = ?", [projectId]);
    for (const pagePayload of payload.pages) {
      const pageId = String(pagePayload.pageId || "");
      assertSafeId(pageId, "pageId");
      const page = pageMap.get(pageId);
      if (!page) throw httpError(400, `Unknown pageId: ${pageId}`);
      const seenPageSliceIds = new Set<string>();
      const slices = (pagePayload.slices || []).map((slice, sliceIndex) => {
        const fallbackName = defaultSliceName(sliceIndex + 1);
        const name = sanitizeName(slice.name, fallbackName);
        return {
          ...slice,
          sliceIndex: sliceIndex + 1,
          name: isDefaultSliceName(name) ? fallbackName : name
        };
      });
      for (const slice of slices) {
        assertSafeSliceId(slice.id);
        if (seenPageSliceIds.has(slice.id) || seenProjectSliceIds.has(slice.id)) {
          throw httpError(400, `Duplicate slice id: ${slice.id}`);
        }
        seenPageSliceIds.add(slice.id);
        seenProjectSliceIds.add(slice.id);
        const kind = normalizeSliceKind(slice.kind);
        const cutMode = normalizeCutMode(slice.cutMode);
        const box = normalizeSliceBox(slice.bbox, { width: page.width, height: page.height });
        await db.run(`
          INSERT INTO slices (id, project_id, page_id, slice_index, name, kind, cut_mode, x, y, width, height, created_at, updated_at)
          VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        `, [slice.id, projectId, pageId, slice.sliceIndex, slice.name, kind, cutMode, box.x, box.y, box.width, box.height, now, now]);
      }
    }
    await updateProjectCounts(projectId);
  });

  const project = await getProjectSummary(userId, projectId);
  if (!project) throw httpError(404, "Project not found");
  return project;
}

export async function getProjectDetail(userId: string, projectId: string): Promise<ProjectDetail> {
  assertSafeId(projectId, "projectId");
  const project = await getProjectSummary(userId, projectId);
  if (!project) throw httpError(404, "Project not found");
  const pages = await db.all<PageRow>("SELECT * FROM pages WHERE project_id = ? ORDER BY page_index ASC", [projectId]);
  const slices = await db.all<SliceRow>("SELECT * FROM slices WHERE project_id = ? ORDER BY page_id ASC, slice_index ASC", [projectId]);
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
      slices: normalizeDefaultSliceNames(slicesByPage.get(page.id) || [])
    }))
  };
}

export async function getPageOriginalPath(userId: string, projectId: string, pageId: string): Promise<string> {
  assertSafeId(projectId, "projectId");
  assertSafeId(pageId, "pageId");
  await assertProjectExists(userId, projectId);
  const row = await db.get<Pick<PageRow, "original_path">>("SELECT original_path FROM pages WHERE project_id = ? AND id = ?", [projectId, pageId]);
  if (!row) throw httpError(404, "Page not found");
  const absolutePath = storage.absolutePath(row.original_path);
  if (!fs.existsSync(absolutePath)) throw httpError(404, "Original image not found");
  return absolutePath;
}

export async function getPageOriginalKey(userId: string, projectId: string, pageId: string): Promise<string> {
  assertSafeId(projectId, "projectId");
  assertSafeId(pageId, "pageId");
  await assertProjectExists(userId, projectId);
  const row = await db.get<Pick<PageRow, "original_path">>("SELECT original_path FROM pages WHERE project_id = ? AND id = ?", [projectId, pageId]);
  if (!row) throw httpError(404, "Page not found");
  if (!storage.exists(row.original_path)) throw httpError(404, "Original image not found");
  return row.original_path;
}

export async function getSliceForPreview(userId: string, projectId: string, sliceId: string): Promise<{ originalKey: string; slice: SliceRecord }> {
  assertSafeId(projectId, "projectId");
  assertSafeSliceId(sliceId);
  await assertProjectExists(userId, projectId);
  const slice = await db.get<SliceRow>("SELECT * FROM slices WHERE project_id = ? AND id = ?", [projectId, sliceId]);
  if (!slice) throw httpError(404, "Slice not found");
  const page = await getPageRow(projectId, slice.page_id);
  return {
    originalKey: storage.firstExistingKey([page.original_path], "Original image not found"),
    slice: formatSlice(slice)
  };
}

async function getPageRow(projectId: string, pageId: string): Promise<PageRow> {
  const page = await db.get<PageRow>("SELECT * FROM pages WHERE project_id = ? AND id = ?", [projectId, pageId]);
  if (!page) throw httpError(404, "Page not found");
  return page;
}

export async function getProjectSummary(userId: string, projectId: string): Promise<ProjectSummary | null> {
  const row = await db.get<ProjectRow>("SELECT * FROM projects WHERE id = ? AND user_id = ?", [projectId, userId]);
  return row ? formatProject(row) : null;
}

export async function assertProjectExists(userId: string, projectId: string): Promise<void> {
  if (!(await getProjectSummary(userId, projectId))) throw httpError(404, "Project not found");
}

export async function updateProjectCounts(projectId: string): Promise<void> {
  const pageCount = Number((await db.get<{ count: number }>("SELECT COUNT(*) AS count FROM pages WHERE project_id = ?", [projectId]))?.count || 0);
  const sliceCount = Number((await db.get<{ count: number }>("SELECT COUNT(*) AS count FROM slices WHERE project_id = ?", [projectId]))?.count || 0);
  await db.run("UPDATE projects SET page_count = ?, slice_count = ?, updated_at = ? WHERE id = ?", [pageCount, sliceCount, new Date().toISOString(), projectId]);
}

async function reindexPages(projectId: string): Promise<void> {
  const pages = await db.all<PageRow>("SELECT * FROM pages WHERE project_id = ? ORDER BY page_index ASC", [projectId]);
  for (const [index, page] of pages.entries()) {
    await db.run("UPDATE pages SET page_index = ? WHERE project_id = ? AND id = ?", [index + 1, projectId, page.id]);
  }
}

async function getNextPageIdNumber(projectId: string): Promise<number> {
  const pages = await db.all<Pick<PageRow, "id">>("SELECT id FROM pages WHERE project_id = ?", [projectId]);
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
    cutMode: normalizeCutMode(row.cut_mode),
    bbox: { x: row.x, y: row.y, width: row.width, height: row.height },
    selected: true
  };
}
