import sharp from "sharp";
import { pageExportDirectory } from "../shared/manifest";
import type { BBox, ProjectDetail } from "../shared/types";

export async function createRemainderPng(originalBuffer: Buffer, slices: Array<{ bbox: BBox }>): Promise<Buffer> {
  const original = await sharp(originalBuffer)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });
  const data = Buffer.from(original.data);
  for (const slice of slices) clearAlphaRect(data, original.info.width, original.info.height, slice.bbox);
  return sharp(data, { raw: { width: original.info.width, height: original.info.height, channels: 4 } })
    .png()
    .toBuffer();
}

export function buildPencilManifest(detail: ProjectDetail, exportedAt: string) {
  return {
    schema: "slice_studio_pencil_project_manifest.v1",
    exportedAt,
    project: detail.project,
    pencil: {
      designPen: "design.pen",
      visibleAssetRoot: "assets/visible"
    },
    pages: detail.pages.map((page, pageIndex) => {
      const pageDirectory = pageExportDirectory(page.pageIndex || pageIndex + 1, page.displayName);
      return {
        pageId: page.id,
        pageIndex: page.pageIndex || pageIndex + 1,
        originalName: page.originalName,
        displayName: page.displayName,
        pageDirectory,
        original: `assets/originals/${pageDirectory}.png`,
        remainder: `assets/visible/remainders/${pageDirectory}/remainder.png`,
        width: page.width,
        height: page.height,
        slices: page.slices.map((slice, sliceIndex) => ({
          id: slice.id,
          name: slice.name,
          kind: slice.kind,
          cutMode: slice.cutMode,
          filename: `assets/visible/slices/${pageDirectory}/slice_${String(sliceIndex + 1).padStart(4, "0")}.png`,
          placement: { ...slice.bbox },
          selected: true
        }))
      };
    })
  };
}

function clearAlphaRect(data: Buffer, width: number, height: number, bbox: BBox): void {
  const left = clamp(Math.round(bbox.x), 0, width);
  const top = clamp(Math.round(bbox.y), 0, height);
  const right = clamp(Math.round(bbox.x + bbox.width), left, width);
  const bottom = clamp(Math.round(bbox.y + bbox.height), top, height);
  for (let y = top; y < bottom; y += 1) {
    const row = y * width;
    for (let x = left; x < right; x += 1) {
      data[(row + x) * 4 + 3] = 0;
    }
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
