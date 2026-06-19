import { httpError } from "./errors";
import {
  buildExportFingerprint,
  exportCacheHit,
  readExportSourceFile,
  writeExportCache,
  type ExportSourceFile
} from "./export-cache";
import { getPageOriginalKey, getProjectDetail } from "./projects";
import { cropSliceToPng } from "./shape-cutout";
import { storage } from "./storage";
import { buildExportManifest, pageExportDirectory } from "../shared/manifest";
import { createZipBuffer, type ZipFile } from "../shared/zip";

const assetsExporterVersion = "assets_zip.v2";

export async function exportAssets(userId: string, projectId: string): Promise<{ ok: true; assetCount: number; url: string; cached: boolean }> {
  const detail = await getProjectDetail(userId, projectId);
  const assetCount = detail.pages.reduce((sum, page) => sum + page.slices.length, 0);
  if (assetCount === 0) throw httpError(409, "No slices selected");
  storage.ensureProjectDirectories(userId, projectId);
  const zipKey = storage.assetsZipKey(userId, projectId);
  const sourceFiles: ExportSourceFile[] = [];
  const originalKeysByPageId = new Map<string, string>();
  for (const page of detail.pages) {
    const originalKey = await getPageOriginalKey(userId, projectId, page.id);
    originalKeysByPageId.set(page.id, originalKey);
    sourceFiles.push(readExportSourceFile(page.id, originalKey));
  }
  const fingerprint = buildExportFingerprint({
    kind: "assets",
    exporterVersion: assetsExporterVersion,
    detail,
    sourceFiles
  });
  if (exportCacheHit({
    zipKey,
    kind: "assets",
    exporterVersion: assetsExporterVersion,
    fingerprint,
    assetCount,
    pageCount: detail.pages.length
  })) {
    return {
      ok: true,
      assetCount,
      cached: true,
      url: assetsDownloadUrl(projectId, zipKey)
    };
  }

  const exportedAt = new Date().toISOString();
  const manifest = buildExportManifest(detail, exportedAt);
  const projectJson = {
    schema: "slice_studio_project.v1",
    exportedAt,
    project: detail.project,
    pages: detail.pages
  };
  const files: ZipFile[] = [
    { name: "project.json", data: Buffer.from(JSON.stringify(projectJson, null, 2)) },
    { name: "manifest.json", data: Buffer.from(JSON.stringify(manifest, null, 2)) }
  ];

  for (const [pageIndex, page] of detail.pages.entries()) {
    const pageDirectory = pageExportDirectory(page.pageIndex || pageIndex + 1, page.displayName);
    const originalKey = originalKeysByPageId.get(page.id);
    if (!originalKey) throw httpError(404, "Original image not found");
    const originalBuffer = storage.read(originalKey, "Original image not found");
    files.push({
      name: `originals/${pageDirectory}.png`,
      data: originalBuffer
    });
    for (const [sliceIndex, slice] of page.slices.entries()) {
      const sliceBuffer = await cropSliceToPng(originalBuffer, slice);
      files.push({
        name: `slices/${pageDirectory}/slice_${String(sliceIndex + 1).padStart(4, "0")}.png`,
        data: sliceBuffer
      });
    }
  }

  storage.write(zipKey, createZipBuffer(files));
  writeExportCache({
    zipKey,
    kind: "assets",
    exporterVersion: assetsExporterVersion,
    fingerprint,
    assetCount,
    pageCount: detail.pages.length
  });
  return {
    ok: true,
    assetCount,
    cached: false,
    url: assetsDownloadUrl(projectId, zipKey)
  };
}

export function getAssetsZipPath(userId: string, projectId: string): string {
  return storage.absolutePath(storage.assetsZipKey(userId, projectId));
}

function assetsDownloadUrl(projectId: string, zipKey: string): string {
  return storage.downloadUrl(zipKey, {
    contentType: "application/zip",
    contentDisposition: `attachment; filename="${projectId}-assets.zip"`,
    notFoundMessage: "assets.zip has not been generated"
  });
}
