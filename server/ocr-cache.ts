import { createHash } from "node:crypto";
import { baiduPaddleOcrModel, ocrMinConfidence, ocrProvider, physicalEvidenceProvider, textBBoxSource, textStyleProvider } from "./config";
import { storage } from "./storage";
import type { TextLocationResult } from "./m29-text-locator";
import type { OcrResult } from "./text-ocr";

const cacheSchema = "slice_studio_ocr_cache.v1";

export const evidenceVersion = [
  `ocr=${ocrProvider}:${baiduPaddleOcrModel}:${ocrMinConfidence}`,
  `bbox=${textBBoxSource}:${physicalEvidenceProvider}`,
  `style=${textStyleProvider}`
].join("|");

export type EvidenceCacheEntry = {
  schema: typeof cacheSchema;
  hash: string;
  width: number;
  height: number;
  evidenceVersion: string;
  ocr?: OcrResult;
  m29Location?: TextLocationResult;
  createdAt: string;
};

export function evidenceCacheKey(userId: string, projectId: string, imageBuffer: Buffer): string {
  const hash = contentHash(imageBuffer);
  return `users/${userId}/projects/${projectId}/ocr-cache/${hash}.json`;
}

export function readEvidenceCache(userId: string, projectId: string, imageBuffer: Buffer): EvidenceCacheEntry | null {
  const key = evidenceCacheKey(userId, projectId, imageBuffer);
  try {
    if (!storage.exists(key)) return null;
    const data = JSON.parse(storage.read(key).toString("utf8")) as Partial<EvidenceCacheEntry>;
    if (data.schema !== cacheSchema) return null;
    if (data.evidenceVersion !== evidenceVersion) return null;
    return data as EvidenceCacheEntry;
  } catch {
    return null;
  }
}

export function writeEvidenceCache(
  userId: string,
  projectId: string,
  imageBuffer: Buffer,
  entry: { ocr?: OcrResult; m29Location?: TextLocationResult; width: number; height: number }
): void {
  const key = evidenceCacheKey(userId, projectId, imageBuffer);
  const cacheEntry: EvidenceCacheEntry = {
    schema: cacheSchema,
    hash: contentHash(imageBuffer),
    width: entry.width,
    height: entry.height,
    evidenceVersion,
    ocr: entry.ocr,
    m29Location: entry.m29Location,
    createdAt: new Date().toISOString()
  };
  storage.write(key, Buffer.from(JSON.stringify(cacheEntry)));
}

function contentHash(buffer: Buffer): string {
  return createHash("sha256").update(buffer).digest("hex").slice(0, 32);
}
