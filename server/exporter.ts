import fs from "node:fs";
import path from "node:path";
import { consumeExport } from "./billing";
import { projectsRoot } from "./config";
import { httpError } from "./errors";
import { getPageOriginalPath, getProjectDetail } from "./projects";
import { cropSliceToPng } from "./shape-cutout";
import { buildExportManifest, pageExportDirectory } from "../shared/manifest";
import { createZipBuffer, type ZipFile } from "../shared/zip";

export async function exportAssets(userId: string, projectId: string): Promise<{ ok: true; assetCount: number; url: string }> {
  const detail = getProjectDetail(userId, projectId);
  const assetCount = detail.pages.reduce((sum, page) => sum + page.slices.length, 0);
  if (assetCount === 0) throw httpError(409, "No slices selected");
  consumeExport(userId, projectId, "export.assets", { assetCount });

  const exportDir = path.join(projectsRoot, projectId, "exports");
  fs.mkdirSync(exportDir, { recursive: true });

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
    const originalBuffer = fs.readFileSync(getPageOriginalPath(userId, projectId, page.id));
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

  fs.writeFileSync(path.join(exportDir, "assets.zip"), createZipBuffer(files));
  return {
    ok: true,
    assetCount,
    url: `/api/projects/${projectId}/assets.zip`
  };
}

export function getAssetsZipPath(projectId: string): string {
  return path.join(projectsRoot, projectId, "exports", "assets.zip");
}
