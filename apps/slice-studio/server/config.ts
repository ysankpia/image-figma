import fs from "node:fs";
import path from "node:path";

loadLocalEnv();

export const apiHost = process.env.SLICE_STUDIO_API_HOST || "127.0.0.1";
export const apiPort = Number(process.env.SLICE_STUDIO_API_PORT || 4110);
export const storageRoot = path.resolve(process.env.SLICE_STUDIO_STORAGE_ROOT || path.join(process.cwd(), "storage"));
export const projectsRoot = path.join(storageRoot, "projects");
export const databasePath = path.join(storageRoot, "app.sqlite");
export const publicApiBaseUrl = process.env.SLICE_STUDIO_PUBLIC_API_URL || `http://${apiHost}:${apiPort}`;
export const allowedOrigin = process.env.SLICE_STUDIO_ALLOWED_ORIGIN || "http://127.0.0.1:3010";
export const maxUploadBytes = Number(process.env.SLICE_STUDIO_MAX_UPLOAD_BYTES || 20 * 1024 * 1024);
export const maxBatchUploadBytes = Number(process.env.SLICE_STUDIO_MAX_BATCH_UPLOAD_BYTES || 300 * 1024 * 1024);
export const ocrProvider = process.env.SLICE_STUDIO_OCR_PROVIDER || "baidu_ppocrv5";
export const ocrMinConfidence = Number(process.env.SLICE_STUDIO_OCR_MIN_CONFIDENCE || process.env.OCR_MIN_CONFIDENCE || 0.7);
export const baiduPaddleOcrToken = process.env.BAIDU_PADDLE_OCR_TOKEN || "";
export const baiduPaddleOcrJobUrl = process.env.BAIDU_PADDLE_OCR_JOB_URL || "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs";
export const baiduPaddleOcrModel = process.env.BAIDU_PADDLE_OCR_MODEL || "PP-OCRv5";
export const baiduPaddleOcrPollIntervalSeconds = Number(process.env.BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS || 5);
export const baiduPaddleOcrTimeoutSeconds = Number(process.env.BAIDU_PADDLE_OCR_TIMEOUT_SECONDS || 120);
export const textBBoxSource = process.env.SLICE_STUDIO_TEXT_BBOX_SOURCE || "m29_ocr_hybrid";
export type PhysicalEvidenceProvider = "ts_m29_physical_evidence" | "go_m29extract" | "ocr";
export const physicalEvidenceProvider = normalizePhysicalEvidenceProvider(process.env.SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER);
export const m29extractPath = path.resolve(process.env.SLICE_STUDIO_M29EXTRACT_PATH || path.join(process.cwd(), "../../services/backend-go/bin/m29extract"));

function loadLocalEnv(): void {
  if (process.env.IMAGE_FIGMA_LOAD_LOCAL_ENV === "false") return;
  for (const filePath of [path.resolve(process.cwd(), "../../.env.local"), path.resolve(process.cwd(), ".env.local")]) {
    if (!fs.existsSync(filePath)) continue;
    for (const rawLine of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
      const line = rawLine.trim();
      if (!line || line.startsWith("#")) continue;
      const separator = line.indexOf("=");
      if (separator <= 0) continue;
      const key = line.slice(0, separator).trim();
      const value = stripEnvQuotes(line.slice(separator + 1).trim());
      if (process.env[key] === undefined) process.env[key] = value;
    }
  }
}

function stripEnvQuotes(value: string): string {
  if ((value.startsWith("\"") && value.endsWith("\"")) || (value.startsWith("'") && value.endsWith("'"))) {
    return value.slice(1, -1);
  }
  return value;
}

function normalizePhysicalEvidenceProvider(value: string | undefined): PhysicalEvidenceProvider {
  if (value === "go_m29extract" || value === "ocr" || value === "ts_m29_physical_evidence") return value;
  return "ts_m29_physical_evidence";
}
