import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  baiduPaddleOcrJobUrl,
  baiduPaddleOcrModel,
  baiduPaddleOcrPollIntervalSeconds,
  baiduPaddleOcrTimeoutSeconds,
  baiduPaddleOcrToken,
  ocrMinConfidence,
  ocrProvider
} from "./config";
import type { BBox } from "../shared/types";

export type OcrStatus = "ok" | "skipped" | "failed";
export type OcrProvider = "baidu_ppocrv5" | "tesseract";

export type OcrLine = {
  text: string;
  bbox: BBox;
  confidence: number;
  wordCount: number;
};

export type OcrResult = {
  provider: OcrProvider;
  status: OcrStatus;
  language: string;
  lines: OcrLine[];
  reason?: string;
  model?: string;
  meta?: Record<string, unknown>;
};

type TsvWord = {
  text: string;
  bbox: BBox;
  confidence: number;
  block: number;
  paragraph: number;
  line: number;
  word: number;
};

const defaultLanguage = "chi_sim+eng";
const minWordConfidence = 25;
const transientHttpStatuses = new Set([408, 425, 429, 500, 502, 503, 504]);
const httpMaxAttempts = 3;

export async function runOcr(imageBuffer: Buffer): Promise<OcrResult> {
  if (ocrProvider === "tesseract") return runTesseractOcr(imageBuffer);
  if (ocrProvider !== "baidu_ppocrv5") return skipped("baidu_ppocrv5", "default", `unsupported_ocr_provider_${ocrProvider}`);
  return runBaiduPpocrv5(imageBuffer);
}

export async function runBaiduPpocrv5(imageBuffer: Buffer): Promise<OcrResult> {
  if (!baiduPaddleOcrToken) return skipped("baidu_ppocrv5", baiduPaddleOcrModel, "baidu_paddle_ocr_token_missing");
  try {
    const { jobId, submitSeconds } = await submitBaiduJob(imageBuffer);
    const { jsonUrl, pollSeconds, pollCount } = await pollBaiduJob(jobId);
    const rows = await downloadBaiduJsonl(jsonUrl);
    const lines = parseBaiduPpocrv5Rows(rows, ocrMinConfidence);
    return {
      provider: "baidu_ppocrv5",
      status: "ok",
      language: "zh+en",
      model: baiduPaddleOcrModel,
      lines,
      meta: {
        remoteJobId: jobId,
        submitSeconds,
        pollSeconds,
        pollCount,
        rawRowCount: rows.length
      }
    };
  } catch (error) {
    return failed("baidu_ppocrv5", baiduPaddleOcrModel, error instanceof Error ? error.message : String(error));
  }
}

export function runTesseractOcr(imageBuffer: Buffer, language = defaultLanguage): OcrResult {
  if (!hasTesseract()) {
    return skipped("tesseract", language, "tesseract_not_found");
  }

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "slice-studio-ocr-"));
  const imagePath = path.join(tmpDir, "input.png");
  try {
    fs.writeFileSync(imagePath, imageBuffer);
    const result = spawnSync("tesseract", [imagePath, "stdout", "-l", language, "--psm", "6", "tsv"], {
      encoding: "utf8",
      maxBuffer: 10 * 1024 * 1024
    });
    if (result.error) return failed("tesseract", language, result.error.message);
    if (result.status !== 0) {
      return failed("tesseract", language, normalizeReason(result.stderr) || `tesseract_exit_${result.status ?? "unknown"}`);
    }
    return {
      provider: "tesseract",
      status: "ok",
      language,
      model: "tesseract",
      lines: parseTesseractTsv(result.stdout)
    };
  } catch (error) {
    return failed("tesseract", language, error instanceof Error ? error.message : String(error));
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

export function parseBaiduPpocrv5Rows(rows: Array<Record<string, unknown>>, minConfidence = ocrMinConfidence): OcrLine[] {
  const lines: OcrLine[] = [];
  for (const row of rows) {
    const result = objectValue(row, "result");
    const ocrResults = arrayValue(result, "ocrResults");
    for (const item of ocrResults) {
      const pruned = objectValue(item, "prunedResult");
      const texts = arrayValue(pruned, "rec_texts");
      const scores = arrayValue(pruned, "rec_scores");
      const boxes = arrayValue(pruned, "rec_boxes");
      const polys = arrayValue(pruned, "rec_polys");
      for (const [index, value] of texts.entries()) {
        const text = String(value || "").trim();
        if (!text) continue;
        const confidence = parseScore(scores[index]);
        if (confidence < minConfidence) continue;
        const bbox = recBoxToBBox(boxes[index]) || polygonToBBox(polys[index]);
        if (!bbox) continue;
        lines.push({ text, bbox, confidence: Math.round(confidence * 100), wordCount: 1 });
      }
    }
  }
  return lines.sort((a, b) => a.bbox.y - b.bbox.y || a.bbox.x - b.bbox.x);
}

export function parseTesseractTsv(tsv: string): OcrLine[] {
  const rows = tsv.trim().split(/\r?\n/);
  if (rows.length < 2) return [];
  const header = rows[0].split("\t");
  const index = new Map(header.map((name, position) => [name, position]));
  const words: TsvWord[] = [];
  for (const row of rows.slice(1)) {
    const columns = row.split("\t");
    const level = numberColumn(columns, index, "level");
    if (level !== 5) continue;
    const text = stringColumn(columns, index, "text").trim();
    const confidence = numberColumn(columns, index, "conf");
    const bbox = {
      x: numberColumn(columns, index, "left"),
      y: numberColumn(columns, index, "top"),
      width: numberColumn(columns, index, "width"),
      height: numberColumn(columns, index, "height")
    };
    if (!text || confidence < minWordConfidence || bbox.width <= 0 || bbox.height <= 0) continue;
    words.push({
      text,
      bbox,
      confidence,
      block: numberColumn(columns, index, "block_num"),
      paragraph: numberColumn(columns, index, "par_num"),
      line: numberColumn(columns, index, "line_num"),
      word: numberColumn(columns, index, "word_num")
    });
  }
  return mergeWordsIntoLines(words);
}

function hasTesseract(): boolean {
  const result = spawnSync("tesseract", ["--version"], { encoding: "utf8", maxBuffer: 1024 * 1024 });
  return !result.error && result.status === 0;
}

function mergeWordsIntoLines(words: TsvWord[]): OcrLine[] {
  const groups = new Map<string, TsvWord[]>();
  for (const word of words) {
    const key = `${word.block}:${word.paragraph}:${word.line}`;
    groups.set(key, [...(groups.get(key) || []), word]);
  }
  return [...groups.values()]
    .map((lineWords) => lineFromWords(lineWords.sort((a, b) => a.word - b.word || a.bbox.x - b.bbox.x)))
    .filter((line) => line.text.length > 0)
    .sort((a, b) => a.bbox.y - b.bbox.y || a.bbox.x - b.bbox.x);
}

function lineFromWords(words: TsvWord[]): OcrLine {
  const left = Math.min(...words.map((word) => word.bbox.x));
  const top = Math.min(...words.map((word) => word.bbox.y));
  const right = Math.max(...words.map((word) => word.bbox.x + word.bbox.width));
  const bottom = Math.max(...words.map((word) => word.bbox.y + word.bbox.height));
  return {
    text: joinWords(words),
    bbox: { x: left, y: top, width: right - left, height: bottom - top },
    confidence: Math.round(words.reduce((sum, word) => sum + word.confidence, 0) / words.length),
    wordCount: words.length
  };
}

function joinWords(words: TsvWord[]): string {
  let text = "";
  for (const [index, word] of words.entries()) {
    if (index > 0 && shouldInsertSpace(words[index - 1], word)) text += " ";
    text += word.text;
  }
  return text.trim();
}

function shouldInsertSpace(previous: TsvWord, current: TsvWord): boolean {
  if (hasCjk(previous.text) || hasCjk(current.text)) return false;
  const gap = current.bbox.x - (previous.bbox.x + previous.bbox.width);
  return gap > Math.max(2, Math.min(previous.bbox.height, current.bbox.height) * 0.2);
}

function hasCjk(text: string): boolean {
  return /[\p{Script=Han}\p{Script=Hiragana}\p{Script=Katakana}\p{Script=Hangul}]/u.test(text);
}

function numberColumn(columns: string[], index: Map<string, number>, name: string): number {
  const raw = stringColumn(columns, index, name);
  const value = Number(raw);
  return Number.isFinite(value) ? value : 0;
}

function stringColumn(columns: string[], index: Map<string, number>, name: string): string {
  const position = index.get(name);
  return position === undefined ? "" : columns[position] || "";
}

async function submitBaiduJob(imageBuffer: Buffer): Promise<{ jobId: string; submitSeconds: number }> {
  const started = performance.now();
  const form = new FormData();
  form.append("model", baiduPaddleOcrModel);
  form.append("optionalPayload", JSON.stringify({
    useDocOrientationClassify: false,
    useDocUnwarping: false,
    useTextlineOrientation: false
  }));
  form.append("file", new File([arrayBufferFromBuffer(imageBuffer)], "input.png", { type: "image/png" }));
  const response = await fetchWithRetry(baiduPaddleOcrJobUrl, {
    method: "POST",
    headers: { Authorization: `bearer ${baiduPaddleOcrToken}` },
    body: form
  });
  if (!response.ok) throw new Error(`Baidu PP-OCRv5 submit failed with HTTP ${response.status}`);
  const body = await response.json() as { data?: { jobId?: unknown } };
  const jobId = body.data?.jobId;
  if (typeof jobId !== "string" || !jobId) throw new Error("Baidu PP-OCRv5 submit response missing data.jobId");
  return { jobId, submitSeconds: secondsSince(started) };
}

async function pollBaiduJob(jobId: string): Promise<{ jsonUrl: string; pollSeconds: number; pollCount: number }> {
  const started = performance.now();
  let pollCount = 0;
  while (true) {
    pollCount += 1;
    const response = await fetchWithRetry(`${baiduPaddleOcrJobUrl.replace(/\/$/, "")}/${jobId}`, {
      headers: { Authorization: `bearer ${baiduPaddleOcrToken}` }
    });
    if (!response.ok) throw new Error(`Baidu PP-OCRv5 poll failed with HTTP ${response.status}`);
    const body = await response.json() as { data?: { state?: unknown; errorMsg?: unknown; resultUrl?: { jsonUrl?: unknown } } };
    const data = body.data || {};
    if (data.state === "done") {
      const jsonUrl = data.resultUrl?.jsonUrl;
      if (typeof jsonUrl !== "string" || !jsonUrl) throw new Error("Baidu PP-OCRv5 result missing resultUrl.jsonUrl");
      return { jsonUrl, pollSeconds: secondsSince(started), pollCount };
    }
    if (data.state === "failed") throw new Error(`Baidu PP-OCRv5 job failed: ${String(data.errorMsg || "unknown error")}`);
    if (secondsSince(started) >= baiduPaddleOcrTimeoutSeconds) throw new Error("Baidu PP-OCRv5 job timed out");
    await sleep(baiduPaddleOcrPollIntervalSeconds * 1000);
  }
}

async function downloadBaiduJsonl(url: string): Promise<Array<Record<string, unknown>>> {
  const response = await fetchWithRetry(url);
  if (!response.ok) throw new Error(`Baidu PP-OCRv5 JSONL download failed with HTTP ${response.status}`);
  const text = await response.text();
  const rows: Array<Record<string, unknown>> = [];
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (trimmed) rows.push(JSON.parse(trimmed) as Record<string, unknown>);
  }
  if (!rows.length) throw new Error("Baidu PP-OCRv5 JSONL response is empty");
  return rows;
}

async function fetchWithRetry(url: string, init: RequestInit = {}): Promise<Response> {
  let lastError: unknown;
  for (let attempt = 1; attempt <= httpMaxAttempts; attempt += 1) {
    try {
      const response = await fetch(url, init);
      if (transientHttpStatuses.has(response.status) && attempt < httpMaxAttempts) {
        await sleep(500 * 2 ** (attempt - 1));
        continue;
      }
      return response;
    } catch (error) {
      lastError = error;
      if (attempt >= httpMaxAttempts) break;
      await sleep(500 * 2 ** (attempt - 1));
    }
  }
  throw lastError instanceof Error ? lastError : new Error(String(lastError));
}

function objectValue(value: unknown, key: string): Record<string, unknown> {
  if (!value || typeof value !== "object") return {};
  const child = (value as Record<string, unknown>)[key];
  return child && typeof child === "object" && !Array.isArray(child) ? child as Record<string, unknown> : {};
}

function arrayValue(value: Record<string, unknown>, key: string): unknown[] {
  const child = value[key];
  return Array.isArray(child) ? child : [];
}

function parseScore(value: unknown): number {
  const score = Number(value);
  return Number.isFinite(score) ? score : 0;
}

function recBoxToBBox(value: unknown): BBox | null {
  if (!Array.isArray(value) || value.length !== 4) return null;
  const [x1, y1, x2, y2] = value.map(Number);
  if (![x1, y1, x2, y2].every(Number.isFinite)) return null;
  const width = x2 - x1;
  const height = y2 - y1;
  if (width <= 1 || height <= 1) return null;
  return { x: Math.round(x1), y: Math.round(y1), width: Math.round(width), height: Math.round(height) };
}

function polygonToBBox(value: unknown): BBox | null {
  if (!Array.isArray(value) || !value.length) return null;
  const points: Array<[number, number]> = [];
  for (const point of value) {
    if (!Array.isArray(point) || point.length < 2) return null;
    const x = Number(point[0]);
    const y = Number(point[1]);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
    points.push([x, y]);
  }
  const xs = points.map((point) => point[0]);
  const ys = points.map((point) => point[1]);
  const width = Math.max(...xs) - Math.min(...xs);
  const height = Math.max(...ys) - Math.min(...ys);
  if (width <= 1 || height <= 1) return null;
  return { x: Math.round(Math.min(...xs)), y: Math.round(Math.min(...ys)), width: Math.round(width), height: Math.round(height) };
}

function skipped(provider: OcrProvider, language: string, reason: string): OcrResult {
  return { provider, status: "skipped", language, model: provider === "baidu_ppocrv5" ? baiduPaddleOcrModel : "tesseract", lines: [], reason };
}

function failed(provider: OcrProvider, language: string, reason: string): OcrResult {
  return { provider, status: "failed", language, model: provider === "baidu_ppocrv5" ? baiduPaddleOcrModel : "tesseract", lines: [], reason: normalizeReason(reason) || "ocr_failed" };
}

function normalizeReason(reason: string): string {
  return reason.trim().replace(/\s+/g, " ").slice(0, 240);
}

function arrayBufferFromBuffer(buffer: Buffer): ArrayBuffer {
  const arrayBuffer = new ArrayBuffer(buffer.byteLength);
  new Uint8Array(arrayBuffer).set(buffer);
  return arrayBuffer;
}

function secondsSince(started: number): number {
  return Math.round((performance.now() - started) / 10) / 100;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
