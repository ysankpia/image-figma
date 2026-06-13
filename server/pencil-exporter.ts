import fs from "node:fs";
import path from "node:path";
import { projectsRoot } from "./config";
import { httpError } from "./errors";
import { validatePencilPackage, type PencilDocument, type PencilNode } from "./pencil-contract";
import {
  buildPencilManifest,
  createRemainderPng,
  frameLayoutXPositions,
  preparePencilSliceImage,
  type PencilPageTextManifest,
  type PencilSlicePlacementManifest
} from "./pencil-package";
import { getPageOriginalPath, getProjectDetail } from "./projects";
import { cropSliceToPng } from "./shape-cutout";
import { runOcr } from "./text-ocr";
import { reconstructTextLayers, type TextLayer, type TextReconstruction } from "./text-reconstruction";
import { pageExportDirectory } from "../shared/manifest";
import type { BBox, ProjectDetail } from "../shared/types";
import { createZipBuffer, type ZipFile } from "../shared/zip";

const penVersion = "2.11";

type ExportControlSurface = {
  key: string;
  bbox: BBox;
  fill: string;
  cornerRadius: number;
  sourceTextId: string;
};

export async function exportPencilProject(projectId: string): Promise<{ ok: true; assetCount: number; pageCount: number; url: string }> {
  const detail = getProjectDetail(projectId);
  const assetCount = detail.pages.reduce((sum, page) => sum + page.slices.length, 0);
  if (assetCount === 0) throw httpError(409, "No slices selected");

  const exportDir = path.join(projectsRoot, projectId, "exports");
  fs.mkdirSync(exportDir, { recursive: true });

  return exportPencilDetail({
    detail,
    exportDir,
    zipFilename: "project.zip",
    url: `/api/projects/${projectId}/project.zip`
  });
}

export async function exportPencilProjectPage(projectId: string, pageId: string): Promise<{ ok: true; assetCount: number; pageCount: number; url: string }> {
  const detail = getProjectDetail(projectId);
  const page = detail.pages.find((candidate) => candidate.id === pageId);
  if (!page) throw httpError(404, "Page not found");

  const pageDetail: ProjectDetail = {
    project: {
      ...detail.project,
      pageCount: 1,
      sliceCount: page.slices.length
    },
    pages: [page]
  };
  const exportDir = path.join(projectsRoot, projectId, "exports", "pages", pageId);
  fs.mkdirSync(exportDir, { recursive: true });

  return exportPencilDetail({
    detail: pageDetail,
    exportDir,
    zipFilename: "project.zip",
    url: `/api/projects/${projectId}/pages/${pageId}/project.zip`
  });
}

async function exportPencilDetail(input: {
  detail: ProjectDetail;
  exportDir: string;
  zipFilename: string;
  url: string;
}): Promise<{ ok: true; assetCount: number; pageCount: number; url: string }> {
  const assetCount = input.detail.pages.reduce((sum, page) => sum + page.slices.length, 0);
  const exportedAt = new Date().toISOString();
  const projectJson = {
    schema: "slice_studio_pencil_project.v1",
    exportedAt,
    project: input.detail.project,
    pages: input.detail.pages
  };
  const files: ZipFile[] = [];
  const { document, textByPageId, slicePlacements } = await buildPencilDocument(input.detail, files, exportedAt);

  files.unshift(
    { name: "design.pen", data: Buffer.from(JSON.stringify(document, null, 2)) },
    { name: "manifest.json", data: Buffer.from(JSON.stringify(buildPencilManifest(input.detail, exportedAt, textByPageId, slicePlacements), null, 2)) },
    { name: "project.json", data: Buffer.from(JSON.stringify(projectJson, null, 2)) }
  );
  validatePencilPackage(document, files);

  fs.writeFileSync(path.join(input.exportDir, input.zipFilename), createZipBuffer(files));
  return {
    ok: true,
    assetCount,
    pageCount: input.detail.pages.length,
    url: input.url
  };
}

export function getProjectZipPath(projectId: string): string {
  return path.join(projectsRoot, projectId, "exports", "project.zip");
}

export function getProjectPageZipPath(projectId: string, pageId: string): string {
  return path.join(projectsRoot, projectId, "exports", "pages", pageId, "project.zip");
}

async function buildPencilDocument(
  detail: ProjectDetail,
  files: ZipFile[],
  exportedAt: string
): Promise<{
  document: PencilDocument;
  textByPageId: Map<string, PencilPageTextManifest>;
  slicePlacements: Map<string, PencilSlicePlacementManifest>;
}> {
  const frames: PencilNode[] = [];
  const textByPageId = new Map<string, PencilPageTextManifest>();
  const slicePlacements = new Map<string, PencilSlicePlacementManifest>();
  const frameXs = frameLayoutXPositions(detail.pages);
  for (const [pageIndex, page] of detail.pages.entries()) {
    const pageDirectory = pageExportDirectory(page.pageIndex || pageIndex + 1, page.displayName);
    const originalBuffer = fs.readFileSync(getPageOriginalPath(detail.project.id, page.id));
    const originalPath = `assets/originals/${pageDirectory}.png`;
    const remainderPath = `assets/visible/remainders/${pageDirectory}/remainder.png`;
    const slicePngs = await Promise.all(page.slices.map((slice) => cropSliceToPng(originalBuffer, slice)));
    const pencilSliceImages = await Promise.all(page.slices.map((slice, sliceIndex) => preparePencilSliceImage(
      slicePngs[sliceIndex],
      slice.bbox,
      slice.cutMode
    )));
    const textReconstruction = await reconstructTextLayers({
      pageId: page.id,
      width: page.width,
      height: page.height,
      imageBuffer: originalBuffer,
      slices: page.slices,
      ocr: await runOcr(originalBuffer)
    });
    textByPageId.set(page.id, textManifest(textReconstruction));
    files.push({ name: originalPath, data: originalBuffer });
    files.push({
      name: remainderPath,
      data: await createRemainderPng(
        originalBuffer,
        page.slices.map((slice, sliceIndex) => ({ ...slice, png: slicePngs[sliceIndex] })),
        textReconstruction.layers.map((layer) => layer.knockoutBBox)
      )
    });

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

    const controlSurfaces = controlSurfacesFromTextLayers(textReconstruction.layers);
    for (const [surfaceIndex, surface] of controlSurfaces.entries()) {
      children.push(controlSurfaceNode({
        pageId: page.id,
        index: surfaceIndex,
        surface,
        z: surfaceIndex + 1
      }));
    }

    for (const [textIndex, layer] of textReconstruction.layers.entries()) {
      children.push(textNode({
        layer,
        name: `text_${String(textIndex + 1).padStart(4, "0")} ${layer.text}`,
        z: controlSurfaces.length + textIndex + 1
      }));
    }
    for (const [sliceIndex, slice] of page.slices.entries()) {
      const slicePath = `assets/visible/slices/${pageDirectory}/slice_${String(sliceIndex + 1).padStart(4, "0")}.png`;
      const pencilSlice = pencilSliceImages[sliceIndex];
      slicePlacements.set(slice.id, {
        placement: { ...pencilSlice.placement },
        originalBBox: roundBBox(slice.bbox),
        alphaTrim: pencilSlice.alphaTrim ? { ...pencilSlice.alphaTrim } : undefined
      });
      files.push({ name: slicePath, data: pencilSlice.data });
      children.push(imageNode({
        id: `${page.id}__slice_${String(sliceIndex + 1).padStart(4, "0")}`,
        name: `${String(sliceIndex + 1).padStart(2, "0")} ${slice.name || `slice_${String(sliceIndex + 1).padStart(2, "0")}`}`,
        url: `./${slicePath}`,
        bbox: pencilSlice.placement,
        metadata: {
          type: "slice_studio_asset",
          pageId: page.id,
          sliceId: slice.id,
          sliceIndex: sliceIndex + 1,
          kind: slice.kind,
          cutMode: slice.cutMode,
          originalBBox: { ...slice.bbox },
          visibleBBox: { ...pencilSlice.placement },
          alphaTrim: pencilSlice.alphaTrim,
          z: textReconstruction.layers.length + sliceIndex + 1
        }
      }));
    }

    frames.push({
      id: `${page.id}__frame`,
      type: "frame",
      name: pageDirectory,
      x: frameXs[pageIndex],
      y: 0,
      width: page.width,
      height: page.height,
      layout: "none",
      fill: "#FFFFFF",
      clip: true,
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
    document: {
      version: penVersion,
      children: frames
    },
    textByPageId,
    slicePlacements
  };
}

function controlSurfacesFromTextLayers(layers: TextLayer[]): ExportControlSurface[] {
  const surfaces = new Map<string, ExportControlSurface>();
  for (const layer of layers) {
    const surface = parseControlSurface(layer);
    if (!surface) continue;
    if (surfaceIsBackgroundLike(surface.fill)) continue;
    if (!surfaces.has(surface.key)) surfaces.set(surface.key, surface);
  }
  return [...surfaces.values()];
}

function parseControlSurface(layer: TextLayer): ExportControlSurface | null {
  const raw = layer.metadata.textLayoutOwnerSurface || layer.metadata.textOwnerSurface;
  if (!raw || typeof raw !== "object") return null;
  const candidate = raw as { bbox?: unknown; fill?: unknown; cornerRadius?: unknown; reason?: unknown };
  if (candidate.reason !== "filled_control_surface") return null;
  if (!candidate.bbox || typeof candidate.bbox !== "object" || typeof candidate.fill !== "string") return null;
  const bbox = candidate.bbox as Partial<BBox>;
  if (
    typeof bbox.x !== "number"
    || typeof bbox.y !== "number"
    || typeof bbox.width !== "number"
    || typeof bbox.height !== "number"
    || bbox.width <= 0
    || bbox.height <= 0
  ) return null;
  const rounded = roundBBox(bbox as BBox);
  const maxRadius = Math.floor(Math.min(rounded.width, rounded.height) / 2);
  const cornerRadius = typeof candidate.cornerRadius === "number"
    ? Math.max(0, Math.round(candidate.cornerRadius))
    : maxRadius;
  const fill = candidate.fill;
  return {
    key: `${rounded.x}:${rounded.y}:${rounded.width}:${rounded.height}:${fill}`,
    bbox: rounded,
    fill,
    cornerRadius: Math.min(cornerRadius, maxRadius),
    sourceTextId: layer.id
  };
}

function surfaceIsBackgroundLike(fill: string): boolean {
  const rgb = rgbFromHex(fill);
  if (!rgb) return true;
  return rgb.r >= 245 && rgb.g >= 245 && rgb.b >= 245;
}

function controlSurfaceNode(input: { pageId: string; index: number; surface: ExportControlSurface; z: number }): PencilNode {
  return {
    id: `${input.pageId}__control_surface_${String(input.index + 1).padStart(4, "0")}`,
    type: "rectangle",
    name: `control_surface_${String(input.index + 1).padStart(4, "0")}`,
    x: Math.round(input.surface.bbox.x),
    y: Math.round(input.surface.bbox.y),
    width: Math.round(input.surface.bbox.width),
    height: Math.round(input.surface.bbox.height),
    fill: input.surface.fill,
    cornerRadius: input.surface.cornerRadius,
    metadata: {
      type: "slice_studio_control_surface",
      pageId: input.pageId,
      sourceTextId: input.surface.sourceTextId,
      z: input.z
    }
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

function roundBBox(bbox: BBox): BBox {
  return {
    x: Math.round(bbox.x),
    y: Math.round(bbox.y),
    width: Math.round(bbox.width),
    height: Math.round(bbox.height)
  };
}

function textNode(input: { layer: TextLayer; name: string; z: number }): PencilNode {
  return {
    id: input.layer.id,
    type: "text",
    name: input.name,
    x: Math.round(input.layer.textRenderBBox.x),
    y: Math.round(input.layer.textRenderBBox.y),
    width: Math.round(input.layer.textRenderBBox.width),
    height: Math.round(input.layer.textRenderBBox.height),
    content: input.layer.text,
    textGrowth: "fixed-width-height",
    fontFamily: input.layer.fontFamily,
    fontSize: input.layer.fontSize,
    fontWeight: input.layer.fontWeight,
    letterSpacing: 0,
    textAlign: input.layer.metadata.textLayoutOwnerSurface ? "center" : "left",
    textAlignVertical: "middle",
    fill: input.layer.color,
    metadata: {
      ...input.layer.metadata,
      z: input.z
    }
  };
}

function rgbFromHex(value: string): { r: number; g: number; b: number } | null {
  if (!value.startsWith("#")) return null;
  const hex = value.slice(1);
  if (!/^[0-9a-f]{6}$/iu.test(hex)) return null;
  return {
    r: Number.parseInt(hex.slice(0, 2), 16),
    g: Number.parseInt(hex.slice(2, 4), 16),
    b: Number.parseInt(hex.slice(4, 6), 16)
  };
}

function textManifest(reconstruction: TextReconstruction): PencilPageTextManifest {
  return {
    ocr: reconstruction.ocr,
    textLayerCount: reconstruction.layers.length,
    textLayers: reconstruction.layers.map((layer) => ({
      id: layer.id,
      text: layer.text,
      placement: { ...layer.bbox },
      textRenderBBox: { ...layer.textRenderBBox },
      originalBBox: { ...layer.originalBBox },
      knockoutBBox: { ...layer.knockoutBBox },
      fontSize: layer.fontSize,
      fontFamily: layer.fontFamily,
      fontWeight: layer.fontWeight,
      color: layer.color,
      confidence: layer.confidence,
      textOwnerSurface: layer.metadata.textOwnerSurface,
      textLayoutOwnerSurface: layer.metadata.textLayoutOwnerSurface
    }))
  };
}
