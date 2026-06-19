import { httpError } from "./errors";
import { ocrMinConfidence, ocrProvider, physicalEvidenceProvider, textBBoxSource, textStyleProvider } from "./config";
import {
  buildExportFingerprint,
  exportCacheHit,
  readExportSourceFile,
  writeExportCache,
  type ExportCacheKind,
  type ExportSourceFile
} from "./export-cache";
import { validatePencilPackage, type PencilDocument, type PencilNode } from "./pencil-contract";
import {
  buildPencilManifest,
  createRemainderPng,
  frameLayoutXPositions,
  preparePencilSliceImage,
  type PencilPageTextManifest,
  type PencilSlicePlacementManifest
} from "./pencil-package";
import { getPageOriginalKey, getProjectDetail } from "./projects";
import { buildPageRenderPlan } from "./render-plan-builder";
import type { ControlSurfaceLayer } from "./render-plan";
import { cropSliceToPng } from "./shape-cutout";
import { storage } from "./storage";
import { runOcr } from "./text-ocr";
import { reconstructTextLayers, type TextLayer, type TextReconstruction } from "./text-reconstruction";
import { pageExportDirectory } from "../shared/manifest";
import type { BBox, ProjectDetail } from "../shared/types";
import { createZipBuffer, type ZipFile } from "../shared/zip";

const penVersion = "2.11";
const pencilExporterVersion = [
  `pencil_project.${penVersion}.v5`,
  `ocr=${ocrProvider}`,
  `ocr_min=${ocrMinConfidence}`,
  `bbox=${textBBoxSource}`,
  `physical=${physicalEvidenceProvider}`,
  `style=${textStyleProvider}`
].join("|");

export async function exportPencilProject(userId: string, projectId: string): Promise<{ ok: true; assetCount: number; pageCount: number; url: string; cached: boolean }> {
  const detail = await getProjectDetail(userId, projectId);
  const assetCount = detail.pages.reduce((sum, page) => sum + page.slices.length, 0);
  if (assetCount === 0) throw httpError(409, "No slices selected");
  storage.ensureProjectDirectories(userId, projectId);

  return exportPencilDetail({
    userId,
    detail,
    zipKey: storage.projectZipKey(userId, projectId),
    zipFilename: "project.zip",
    exportKind: "pencil-project"
  });
}

export async function exportPencilProjectPage(userId: string, projectId: string, pageId: string): Promise<{ ok: true; assetCount: number; pageCount: number; url: string; cached: boolean }> {
  const detail = await getProjectDetail(userId, projectId);
  const page = detail.pages.find((candidate) => candidate.id === pageId);
  if (!page) throw httpError(404, "Page not found");
  if (page.slices.length === 0) throw httpError(409, "No slices selected");

  const pageDetail: ProjectDetail = {
    project: {
      ...detail.project,
      pageCount: 1,
      sliceCount: page.slices.length
    },
    pages: [page]
  };
  storage.ensureProjectDirectories(userId, projectId);

  return exportPencilDetail({
    userId,
    detail: pageDetail,
    zipKey: storage.projectPageZipKey(userId, projectId, pageId),
    zipFilename: "project.zip",
    exportKind: "pencil-page"
  });
}

async function exportPencilDetail(input: {
  userId: string;
  detail: ProjectDetail;
  zipKey: string;
  zipFilename: string;
  exportKind: ExportCacheKind;
}): Promise<{ ok: true; assetCount: number; pageCount: number; url: string; cached: boolean }> {
  const assetCount = input.detail.pages.reduce((sum, page) => sum + page.slices.length, 0);
  const { originalKeysByPageId, sourceFiles } = await resolveExportSources(input.userId, input.detail);
  const fingerprint = buildExportFingerprint({
    kind: input.exportKind,
    exporterVersion: pencilExporterVersion,
    detail: input.detail,
    sourceFiles
  });
  if (exportCacheHit({
    zipKey: input.zipKey,
    kind: input.exportKind,
    exporterVersion: pencilExporterVersion,
    fingerprint,
    assetCount,
    pageCount: input.detail.pages.length
  })) {
    return {
      ok: true,
      assetCount,
      pageCount: input.detail.pages.length,
      cached: true,
      url: pencilDownloadUrl(input.zipKey, input.zipFilename)
    };
  }
  const exportedAt = new Date().toISOString();
  const projectJson = {
    schema: "slice_studio_pencil_project.v1",
    exportedAt,
    project: input.detail.project,
    pages: input.detail.pages
  };
  const files: ZipFile[] = [];
  const { document, textByPageId, slicePlacements } = await buildPencilDocument(input.detail, files, exportedAt, originalKeysByPageId);

  files.unshift(
    { name: "design.pen", data: Buffer.from(JSON.stringify(document, null, 2)) },
    { name: "manifest.json", data: Buffer.from(JSON.stringify(buildPencilManifest(input.detail, exportedAt, textByPageId, slicePlacements), null, 2)) },
    { name: "project.json", data: Buffer.from(JSON.stringify(projectJson, null, 2)) }
  );
  validatePencilPackage(document, files);

  storage.write(input.zipKey, createZipBuffer(files));
  writeExportCache({
    zipKey: input.zipKey,
    kind: input.exportKind,
    exporterVersion: pencilExporterVersion,
    fingerprint,
    assetCount,
    pageCount: input.detail.pages.length
  });
  return {
    ok: true,
    assetCount,
    pageCount: input.detail.pages.length,
    cached: false,
    url: pencilDownloadUrl(input.zipKey, input.zipFilename)
  };
}

export function getProjectZipPath(userId: string, projectId: string): string {
  return storage.absolutePath(storage.projectZipKey(userId, projectId));
}

export function getProjectPageZipPath(userId: string, projectId: string, pageId: string): string {
  return storage.absolutePath(storage.projectPageZipKey(userId, projectId, pageId));
}

async function buildPencilDocument(
  detail: ProjectDetail,
  files: ZipFile[],
  exportedAt: string,
  originalKeysByPageId: Map<string, string>
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
    const originalKey = originalKeysByPageId.get(page.id);
    if (!originalKey) throw httpError(404, "Original image not found");
    const originalBuffer = storage.read(originalKey, "Original image not found");
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
    const renderPlan = buildPageRenderPlan({
      pageId: page.id,
      pageDirectory,
      width: page.width,
      height: page.height,
      textLayers: textReconstruction.layers,
      slices: page.slices
    });
    textByPageId.set(page.id, textManifest(textReconstruction));
    files.push({ name: originalPath, data: originalBuffer });
    files.push({
      name: remainderPath,
      data: await createRemainderPng(
        originalBuffer,
        page.slices.map((slice, sliceIndex) => ({ ...slice, png: slicePngs[sliceIndex] })),
        renderPlan.remainder.textKnockouts,
        renderPlan.remainder.surfaceKnockouts
      )
    });

    const children: PencilNode[] = [
      imageNode({
        id: `${page.id}__remainder`,
        name: `${pageDirectory} remainder`,
        url: `./${remainderPath}`,
        bbox: renderPlan.layers.remainder.visibleBBox,
        metadata: {
          type: "slice_studio_remainder",
          pageId: page.id,
          sourceOriginal: originalPath,
          z: 0
        }
      })
    ];

    for (const [surfaceIndex, surface] of renderPlan.layers.controlSurfaces.entries()) {
      children.push(controlSurfaceNode({
        index: surfaceIndex,
        surface,
        z: surface.zIndex
      }));
    }

    for (const [textIndex, textLayer] of renderPlan.layers.text.entries()) {
      children.push(textNode({
        layer: textLayer.layer,
        name: `text_${String(textIndex + 1).padStart(4, "0")} ${textLayer.layer.text}`,
        z: textLayer.zIndex
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
          z: renderPlan.layers.slices[sliceIndex]?.zIndex ?? textReconstruction.layers.length + sliceIndex + 1
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

async function resolveExportSources(userId: string, detail: ProjectDetail): Promise<{
  originalKeysByPageId: Map<string, string>;
  sourceFiles: ExportSourceFile[];
}> {
  const originalKeysByPageId = new Map<string, string>();
  const sourceFiles: ExportSourceFile[] = [];
  for (const page of detail.pages) {
    const originalKey = await getPageOriginalKey(userId, detail.project.id, page.id);
    originalKeysByPageId.set(page.id, originalKey);
    sourceFiles.push(readExportSourceFile(page.id, originalKey));
  }
  return { originalKeysByPageId, sourceFiles };
}

function pencilDownloadUrl(zipKey: string, zipFilename: string): string {
  return storage.downloadUrl(zipKey, {
    contentType: "application/zip",
    contentDisposition: `attachment; filename="${zipFilename}"`,
    notFoundMessage: `${zipFilename} has not been generated`
  });
}

function controlSurfaceNode(input: { index: number; surface: ControlSurfaceLayer; z: number }): PencilNode {
  return {
    id: input.surface.id,
    type: "rectangle",
    name: `control_surface_${String(input.index + 1).padStart(4, "0")}`,
    x: Math.round(input.surface.visibleBBox.x),
    y: Math.round(input.surface.visibleBBox.y),
    width: Math.round(input.surface.visibleBBox.width),
    height: Math.round(input.surface.visibleBBox.height),
    fill: input.surface.fill,
    cornerRadius: input.surface.cornerRadius,
    metadata: {
      type: "slice_studio_control_surface",
      pageId: input.surface.pageId,
      sourceTextId: input.surface.sourceTextId,
      visibleBBox: input.surface.visibleBBox,
      knockout: input.surface.knockout,
      provenance: input.surface.provenance,
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
      textStyleSource: layer.metadata.textStyleSource,
      textStyleMeasured: layer.metadata.textStyleMeasured,
      textOwnerSurface: layer.metadata.textOwnerSurface,
      textLayoutOwnerSurface: layer.metadata.textLayoutOwnerSurface
    }))
  };
}
