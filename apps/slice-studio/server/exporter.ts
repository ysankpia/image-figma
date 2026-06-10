import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";
import { projectsRoot } from "./config";
import { getPageOriginalPath, getProjectDetail } from "./projects";
import { buildExportManifest } from "../shared/manifest";
import { createZipBuffer, type ZipFile } from "../shared/zip";

export async function exportAssets(projectId: string): Promise<{ ok: true; assetCount: number; url: string }> {
  const detail = getProjectDetail(projectId);
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
    const originalBuffer = fs.readFileSync(getPageOriginalPath(projectId, page.id));
    files.push({
      name: `originals/page_${String(pageIndex + 1).padStart(4, "0")}.png`,
      data: originalBuffer
    });
    for (const [sliceIndex, slice] of page.slices.entries()) {
      const sliceBuffer = await sharp(originalBuffer)
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
        data: sliceBuffer
      });
    }
  }

  fs.writeFileSync(path.join(exportDir, "assets.zip"), createZipBuffer(files));
  return {
    ok: true,
    assetCount: detail.pages.reduce((sum, page) => sum + page.slices.length, 0),
    url: `/api/projects/${projectId}/assets.zip`
  };
}

export function getAssetsZipPath(projectId: string): string {
  return path.join(projectsRoot, projectId, "exports", "assets.zip");
}
