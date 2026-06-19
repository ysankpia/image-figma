import crypto from "node:crypto";
import fs from "node:fs";
import { storage } from "./storage";
import type { ProjectDetail } from "../shared/types";

export type ExportCacheKind = "assets" | "pencil-project" | "pencil-page";

export type ExportSourceFile = {
  pageId: string;
  key: string;
  size: number;
  mtimeMs: number;
};

type ExportCacheMetadata = {
  schema: "slice_studio_export_cache.v1";
  kind: ExportCacheKind;
  exporterVersion: string;
  fingerprint: string;
  assetCount: number;
  pageCount: number;
  createdAt: string;
};

type ExportCacheStorage = Pick<typeof storage, "absolutePath" | "exists" | "read" | "write">;

export function readExportSourceFile(pageId: string, key: string, adapter: ExportCacheStorage = storage): ExportSourceFile {
  const stat = fs.statSync(adapter.absolutePath(key));
  return {
    pageId,
    key,
    size: stat.size,
    mtimeMs: stat.mtimeMs
  };
}

export function buildExportFingerprint(input: {
  kind: ExportCacheKind;
  exporterVersion: string;
  detail: ProjectDetail;
  sourceFiles: ExportSourceFile[];
}): string {
  const sourcesByPageId = new Map(input.sourceFiles.map((source) => [source.pageId, source]));
  const payload = {
    schema: "slice_studio_export_fingerprint.v1",
    kind: input.kind,
    exporterVersion: input.exporterVersion,
    project: {
      id: input.detail.project.id,
      name: input.detail.project.name,
      pageCount: input.detail.project.pageCount,
      sliceCount: input.detail.project.sliceCount
    },
    pages: input.detail.pages.map((page) => {
      const source = sourcesByPageId.get(page.id);
      return {
        id: page.id,
        projectId: page.projectId,
        pageIndex: page.pageIndex,
        originalName: page.originalName,
        displayName: page.displayName,
        width: page.width,
        height: page.height,
        source: source ? {
          key: source.key,
          size: source.size,
          mtimeMs: source.mtimeMs
        } : null,
        slices: page.slices.map((slice) => ({
          id: slice.id,
          sliceIndex: slice.sliceIndex,
          name: slice.name,
          kind: slice.kind,
          cutMode: slice.cutMode,
          bbox: {
            x: slice.bbox.x,
            y: slice.bbox.y,
            width: slice.bbox.width,
            height: slice.bbox.height
          }
        }))
      };
    })
  };
  return crypto.createHash("sha256").update(JSON.stringify(payload)).digest("hex");
}

export function exportCacheHit(input: {
  zipKey: string;
  kind: ExportCacheKind;
  exporterVersion: string;
  fingerprint: string;
  assetCount: number;
  pageCount: number;
}, adapter: ExportCacheStorage = storage): boolean {
  if (!adapter.exists(input.zipKey) || !adapter.exists(exportCacheKey(input.zipKey))) return false;
  const metadata = readCacheMetadata(input.zipKey, adapter);
  return Boolean(metadata
    && metadata.kind === input.kind
    && metadata.exporterVersion === input.exporterVersion
    && metadata.fingerprint === input.fingerprint
    && metadata.assetCount === input.assetCount
    && metadata.pageCount === input.pageCount);
}

export function writeExportCache(input: {
  zipKey: string;
  kind: ExportCacheKind;
  exporterVersion: string;
  fingerprint: string;
  assetCount: number;
  pageCount: number;
}, adapter: ExportCacheStorage = storage): void {
  const metadata: ExportCacheMetadata = {
    schema: "slice_studio_export_cache.v1",
    kind: input.kind,
    exporterVersion: input.exporterVersion,
    fingerprint: input.fingerprint,
    assetCount: input.assetCount,
    pageCount: input.pageCount,
    createdAt: new Date().toISOString()
  };
  adapter.write(exportCacheKey(input.zipKey), Buffer.from(JSON.stringify(metadata, null, 2)));
}

export function exportCacheKey(zipKey: string): string {
  return `${zipKey}.cache.json`;
}

function readCacheMetadata(zipKey: string, adapter: ExportCacheStorage): ExportCacheMetadata | null {
  try {
    const metadata = JSON.parse(adapter.read(exportCacheKey(zipKey)).toString("utf8")) as Partial<ExportCacheMetadata>;
    if (metadata.schema !== "slice_studio_export_cache.v1") return null;
    if (metadata.kind !== "assets" && metadata.kind !== "pencil-project" && metadata.kind !== "pencil-page") return null;
    if (typeof metadata.exporterVersion !== "string" || typeof metadata.fingerprint !== "string") return null;
    if (!Number.isFinite(metadata.assetCount) || !Number.isFinite(metadata.pageCount)) return null;
    if (typeof metadata.createdAt !== "string") return null;
    return metadata as ExportCacheMetadata;
  } catch {
    return null;
  }
}
