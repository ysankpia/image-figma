import fs from "node:fs";
import path from "node:path";
import { projectsRoot } from "./config";
import { httpError } from "./errors";
import { buildPencilManifest, createRemainderPng } from "./pencil-package";
import { getPageOriginalPath, getProjectDetail } from "./projects";
import { cropSliceToPng } from "./shape-cutout";
import { pageExportDirectory } from "../shared/manifest";
import type { BBox, ProjectDetail } from "../shared/types";
import { createZipBuffer, type ZipFile } from "../shared/zip";

const penVersion = "2.11";

type PencilNode = {
  id: string;
  type: "frame" | "rectangle";
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
  layout?: "none";
  fill?: string | { type: "image"; enabled: true; url: string; mode: "stretch" };
  clip?: boolean;
  locked?: boolean;
  visible?: boolean;
  opacity?: number;
  metadata?: Record<string, unknown>;
  children?: PencilNode[];
};

type PencilDocument = {
  version: string;
  children: PencilNode[];
};

export async function exportPencilProject(projectId: string): Promise<{ ok: true; assetCount: number; pageCount: number; url: string }> {
  const detail = getProjectDetail(projectId);
  const assetCount = detail.pages.reduce((sum, page) => sum + page.slices.length, 0);
  if (assetCount === 0) throw httpError(409, "No slices selected");

  const exportDir = path.join(projectsRoot, projectId, "exports");
  fs.mkdirSync(exportDir, { recursive: true });

  const exportedAt = new Date().toISOString();
  const projectJson = {
    schema: "slice_studio_pencil_project.v1",
    exportedAt,
    project: detail.project,
    pages: detail.pages
  };
  const files: ZipFile[] = [];
  const document = await buildPencilDocument(detail, files, exportedAt);

  files.unshift(
    { name: "design.pen", data: Buffer.from(JSON.stringify(document, null, 2)) },
    { name: "manifest.json", data: Buffer.from(JSON.stringify(buildPencilManifest(detail, exportedAt), null, 2)) },
    { name: "project.json", data: Buffer.from(JSON.stringify(projectJson, null, 2)) }
  );
  validatePencilPackage(document, files);

  fs.writeFileSync(path.join(exportDir, "project.zip"), createZipBuffer(files));
  return {
    ok: true,
    assetCount,
    pageCount: detail.pages.length,
    url: `/api/projects/${projectId}/project.zip`
  };
}

export function getProjectZipPath(projectId: string): string {
  return path.join(projectsRoot, projectId, "exports", "project.zip");
}

async function buildPencilDocument(detail: ProjectDetail, files: ZipFile[], exportedAt: string): Promise<PencilDocument> {
  const frames: PencilNode[] = [];
  for (const [pageIndex, page] of detail.pages.entries()) {
    const pageDirectory = pageExportDirectory(page.pageIndex || pageIndex + 1, page.displayName);
    const originalBuffer = fs.readFileSync(getPageOriginalPath(detail.project.id, page.id));
    const originalPath = `assets/originals/${pageDirectory}.png`;
    const remainderPath = `assets/visible/remainders/${pageDirectory}/remainder.png`;
    files.push({ name: originalPath, data: originalBuffer });
    files.push({ name: remainderPath, data: await createRemainderPng(originalBuffer, page.slices) });

    const children: PencilNode[] = [
      imageNode({
        id: `${page.id}__remainder`,
        name: `${pageDirectory} remainder`,
        url: `./${remainderPath}`,
        bbox: { x: 0, y: 0, width: page.width, height: page.height },
        metadata: {
          type: "slice_studio_remainder",
          pageId: page.id,
          sourceOriginal: originalPath,
          z: 0
        }
      })
    ];

    for (const [sliceIndex, slice] of page.slices.entries()) {
      const slicePath = `assets/visible/slices/${pageDirectory}/slice_${String(sliceIndex + 1).padStart(4, "0")}.png`;
      files.push({ name: slicePath, data: await cropSliceToPng(originalBuffer, slice) });
      children.push(imageNode({
        id: `${page.id}__slice_${String(sliceIndex + 1).padStart(4, "0")}`,
        name: slice.name || `slice_${String(sliceIndex + 1).padStart(2, "0")}`,
        url: `./${slicePath}`,
        bbox: slice.bbox,
        metadata: {
          type: "slice_studio_asset",
          pageId: page.id,
          sliceId: slice.id,
          sliceIndex: sliceIndex + 1,
          kind: slice.kind,
          cutMode: slice.cutMode,
          originalBBox: { ...slice.bbox },
          z: sliceIndex + 1
        }
      }));
    }

    frames.push({
      id: `${page.id}__frame`,
      type: "frame",
      name: pageDirectory,
      x: pageIndex * (page.width + 160),
      y: 0,
      width: page.width,
      height: page.height,
      layout: "none",
      fill: "#FFFFFF",
      clip: false,
      metadata: {
        type: "slice_studio_page",
        pageId: page.id,
        pageIndex: page.pageIndex || pageIndex + 1,
        originalName: page.originalName,
        displayName: page.displayName,
        sourceOriginal: originalPath,
        exportedAt
      },
      children
    });
  }

  return {
    version: penVersion,
    children: frames
  };
}

function imageNode(input: { id: string; name: string; url: string; bbox: BBox; metadata: Record<string, unknown> }): PencilNode {
  return {
    id: input.id,
    type: "rectangle",
    name: input.name,
    x: Math.round(input.bbox.x),
    y: Math.round(input.bbox.y),
    width: Math.round(input.bbox.width),
    height: Math.round(input.bbox.height),
    fill: {
      type: "image",
      enabled: true,
      url: input.url,
      mode: "stretch"
    },
    metadata: input.metadata
  };
}

function validatePencilPackage(document: PencilDocument, files: ZipFile[]): void {
  const fileNames = new Set(files.map((file) => file.name));
  const ids = new Set<string>();
  const visit = (node: PencilNode) => {
    if (ids.has(node.id)) throw new Error(`duplicate .pen node id: ${node.id}`);
    ids.add(node.id);
    if (node.fill && typeof node.fill === "object" && node.fill.type === "image") {
      validateImageRef(node.fill.url, fileNames, node.id);
    }
    for (const child of node.children || []) visit(child);
  };
  for (const frame of document.children) visit(frame);
}

function validateImageRef(url: string, fileNames: Set<string>, nodeId: string): void {
  if (!url.startsWith("./assets/visible/")) {
    throw new Error(`Pencil contract violation: image url outside visible assets on ${nodeId}: ${url}`);
  }
  if (url.includes("://") || url.startsWith("/") || url.startsWith("../") || url.includes("/../")) {
    throw new Error(`Pencil contract violation: non-portable image url on ${nodeId}: ${url}`);
  }
  if (url.includes("debug/") || url.includes("raw") || url.includes("masks/")) {
    throw new Error(`Pencil contract violation: forbidden image url on ${nodeId}: ${url}`);
  }
  const fileName = url.slice(2);
  if (!fileNames.has(fileName)) {
    throw new Error(`Pencil contract violation: missing image asset on ${nodeId}: ${url}`);
  }
}
