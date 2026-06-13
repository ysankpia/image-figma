import type { BBox } from "../shared/types";
import { textStyleBaseUrl, textStyleProvider, textStyleTimeoutSeconds, type TextStyleProvider } from "./config";

export type TextStyleOwnerSurface = {
  bbox: BBox;
  fill: string;
  reason: string;
};

export type TextStyleBatchItem = {
  text: string;
  bbox: BBox;
  ownerSurface?: TextStyleOwnerSurface | null;
};

export type TextStyleBatchResult = {
  fontSize: number;
  fontWeight: string;
  fontFamily: string;
  color: string;
  lineHeight: number;
  textAlign: "left" | "center";
  measured: {
    width: number;
    height: number;
  };
  source: "psdlike";
};

type FetchTextStyleOptions = {
  provider?: TextStyleProvider;
  baseUrl?: string;
  timeoutSeconds?: number;
  fetchImpl?: typeof fetch;
};

type WireResult = {
  fontSize?: unknown;
  fontWeight?: unknown;
  fontFamily?: unknown;
  color?: unknown;
  lineHeight?: unknown;
  textAlign?: unknown;
  measured?: {
    width?: unknown;
    height?: unknown;
  };
  source?: unknown;
  error?: unknown;
};

const transientHttpStatuses = new Set([408, 425, 429, 500, 502, 503, 504]);
const httpMaxAttempts = 2;

export async function fetchTextStyleBatch(
  imageBuffer: Buffer,
  items: TextStyleBatchItem[],
  options: FetchTextStyleOptions = {}
): Promise<Array<TextStyleBatchResult | null> | null> {
  const provider = options.provider || textStyleProvider;
  if (provider !== "psdlike") return null;
  if (!items.length) return [];

  const baseUrl = trimTrailingSlash(options.baseUrl || textStyleBaseUrl);
  const timeoutSeconds = options.timeoutSeconds || textStyleTimeoutSeconds;
  const fetchImpl = options.fetchImpl || fetch;
  const form = new FormData();
  form.append("image", new File([arrayBufferFromBuffer(imageBuffer)], "page.png", { type: "image/png" }));
  form.append("items", JSON.stringify(items.map(serializeItem)));

  try {
    const response = await fetchWithRetry(`${baseUrl}/api/text-style-batch`, {
      method: "POST",
      body: form
    }, timeoutSeconds, fetchImpl);
    if (!response.ok) return null;
    const body = await response.json() as { results?: WireResult[] };
    if (!Array.isArray(body.results) || body.results.length !== items.length) return null;
    return body.results.map(parseWireResult);
  } catch {
    return null;
  }
}

function serializeItem(item: TextStyleBatchItem): Record<string, unknown> {
  return {
    text: item.text,
    bbox: roundBBox(item.bbox),
    ownerSurface: item.ownerSurface ? {
      bbox: roundBBox(item.ownerSurface.bbox),
      fill: item.ownerSurface.fill,
      reason: item.ownerSurface.reason
    } : null
  };
}

function parseWireResult(result: WireResult): TextStyleBatchResult | null {
  if (result.error) return null;
  const fontSize = Number(result.fontSize);
  const lineHeight = Number(result.lineHeight);
  const measuredWidth = Number(result.measured?.width);
  const measuredHeight = Number(result.measured?.height);
  if (![fontSize, lineHeight, measuredWidth, measuredHeight].every(Number.isFinite)) return null;
  if (fontSize <= 0 || lineHeight <= 0 || measuredWidth < 0 || measuredHeight < 0) return null;
  if (typeof result.fontFamily !== "string" || !result.fontFamily) return null;
  if (typeof result.color !== "string" || !/^#[0-9a-f]{6}$/iu.test(result.color)) return null;
  const textAlign = result.textAlign === "center" ? "center" : "left";
  return {
    fontSize,
    fontWeight: String(result.fontWeight || "400"),
    fontFamily: result.fontFamily,
    color: result.color,
    lineHeight,
    textAlign,
    measured: {
      width: measuredWidth,
      height: measuredHeight
    },
    source: "psdlike"
  };
}

async function fetchWithRetry(
  url: string,
  init: RequestInit,
  timeoutSeconds: number,
  fetchImpl: typeof fetch
): Promise<Response> {
  let lastError: unknown;
  for (let attempt = 1; attempt <= httpMaxAttempts; attempt += 1) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), Math.max(1, timeoutSeconds) * 1000);
    try {
      const response = await fetchImpl(url, { ...init, signal: controller.signal });
      if (transientHttpStatuses.has(response.status) && attempt < httpMaxAttempts) {
        await sleep(250 * 2 ** (attempt - 1));
        continue;
      }
      return response;
    } catch (error) {
      lastError = error;
      if (attempt >= httpMaxAttempts) break;
      await sleep(250 * 2 ** (attempt - 1));
    } finally {
      clearTimeout(timeout);
    }
  }
  throw lastError instanceof Error ? lastError : new Error(String(lastError));
}

function roundBBox(bbox: BBox): BBox {
  return {
    x: Math.round(bbox.x),
    y: Math.round(bbox.y),
    width: Math.round(bbox.width),
    height: Math.round(bbox.height)
  };
}

function arrayBufferFromBuffer(buffer: Buffer): ArrayBuffer {
  const arrayBuffer = new ArrayBuffer(buffer.byteLength);
  new Uint8Array(arrayBuffer).set(buffer);
  return arrayBuffer;
}

function trimTrailingSlash(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
