import fs from "node:fs";
import path from "node:path";

loadLocalEnv();

export const apiHost = process.env.SLICE_STUDIO_API_HOST || "127.0.0.1";
export const apiPort = Number(process.env.SLICE_STUDIO_API_PORT || 4110);
export const storageRoot = path.resolve(process.env.SLICE_STUDIO_STORAGE_ROOT || path.join(process.cwd(), "storage"));
export const projectsRoot = path.join(storageRoot, "projects");
export const databasePath = path.join(storageRoot, "app.sqlite");
export const publicApiBaseUrl = process.env.SLICE_STUDIO_PUBLIC_API_URL || `http://${apiHost}:${apiPort}`;
export const allowedOrigins = normalizeAllowedOrigins(process.env.SLICE_STUDIO_ALLOWED_ORIGIN);
export const authCookieName = process.env.SLICE_STUDIO_AUTH_COOKIE_NAME || "slice_studio_session";
export const authSessionTtlDays = normalizeNumber(process.env.SLICE_STUDIO_AUTH_SESSION_TTL_DAYS, 30);
export const authSecureCookies = normalizeBool(process.env.SLICE_STUDIO_AUTH_SECURE_COOKIES, process.env.NODE_ENV === "production");
export const downloadSigningSecret = process.env.SLICE_STUDIO_DOWNLOAD_SIGNING_SECRET || process.env.SLICE_STUDIO_LOCAL_OWNER_PASSWORD || "slice-studio-download-secret";
export const downloadUrlTtlSeconds = normalizeNumber(process.env.SLICE_STUDIO_DOWNLOAD_URL_TTL_SECONDS, 600);
export const localOwnerEmail = normalizeEmail(process.env.SLICE_STUDIO_LOCAL_OWNER_EMAIL || "local@slicestudio.dev");
export const localOwnerName = process.env.SLICE_STUDIO_LOCAL_OWNER_NAME || "Local Owner";
export const localOwnerPassword = process.env.SLICE_STUDIO_LOCAL_OWNER_PASSWORD || "slice-studio-local-owner";
export const maxUploadBytes = Number(process.env.SLICE_STUDIO_MAX_UPLOAD_BYTES || 20 * 1024 * 1024);
export const maxBatchUploadBytes = Number(process.env.SLICE_STUDIO_MAX_BATCH_UPLOAD_BYTES || 300 * 1024 * 1024);
export const ocrProvider = process.env.SLICE_STUDIO_OCR_PROVIDER || "baidu_ppocrv5";
export const ocrMinConfidence = Number(process.env.SLICE_STUDIO_OCR_MIN_CONFIDENCE || 0.7);
export const baiduPaddleOcrToken = process.env.BAIDU_PADDLE_OCR_TOKEN || "";
export const baiduPaddleOcrJobUrl = process.env.BAIDU_PADDLE_OCR_JOB_URL || "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs";
export const baiduPaddleOcrModel = process.env.BAIDU_PADDLE_OCR_MODEL || "PP-OCRv5";
export const baiduPaddleOcrPollIntervalSeconds = Number(process.env.BAIDU_PADDLE_OCR_POLL_INTERVAL_SECONDS || 5);
export const baiduPaddleOcrTimeoutSeconds = Number(process.env.BAIDU_PADDLE_OCR_TIMEOUT_SECONDS || 120);
export const textBBoxSource = process.env.SLICE_STUDIO_TEXT_BBOX_SOURCE || "m29_ocr_hybrid";
export type PhysicalEvidenceProvider = "ts_m29_physical_evidence" | "go_m29extract" | "ocr";
export const physicalEvidenceProvider = normalizePhysicalEvidenceProvider(process.env.SLICE_STUDIO_PHYSICAL_EVIDENCE_PROVIDER);
export const m29extractPath = path.resolve(process.env.SLICE_STUDIO_M29EXTRACT_PATH || path.join(process.cwd(), "archive/legacy-code/services/backend-go/bin/m29extract"));
export type TextStyleProvider = "psdlike" | "fallback";
export const textStyleProvider = normalizeTextStyleProvider(process.env.SLICE_STUDIO_TEXT_STYLE_PROVIDER);
export const textStyleBaseUrl = trimTrailingSlash(process.env.SLICE_STUDIO_TEXT_STYLE_BASE_URL || "http://127.0.0.1:4120");
export const textStyleTimeoutSeconds = normalizeNumber(process.env.SLICE_STUDIO_TEXT_STYLE_TIMEOUT_SECONDS, 8);
export type AiSliceProvider = "openai_responses" | "yolo_local" | "disabled";
export const aiSliceProvider = normalizeAiSliceProvider(process.env.SLICE_STUDIO_AI_SLICE_PROVIDER);
export const aiSliceBaseUrl = trimTrailingSlash(process.env.SLICE_STUDIO_AI_SLICE_BASE_URL || "https://api.openai.com");
export const aiSliceApiKey = process.env.SLICE_STUDIO_AI_SLICE_API_KEY || "";
export const aiSliceModel = process.env.SLICE_STUDIO_AI_SLICE_MODEL || "gpt-5.5";
export type AiSliceWireApi = "responses" | "chat_completions";
export const aiSliceWireApi = normalizeAiSliceWireApi(process.env.SLICE_STUDIO_AI_SLICE_WIRE_API);
export const aiSliceReasoningEffort = process.env.SLICE_STUDIO_AI_SLICE_REASONING_EFFORT || "xhigh";
export const aiSliceStore = normalizeBool(process.env.SLICE_STUDIO_AI_SLICE_STORE, false);
export const aiSliceTimeoutSeconds = normalizeNumber(process.env.SLICE_STUDIO_AI_SLICE_TIMEOUT_SECONDS, 120);
export const aiSliceTransportRetries = normalizeNumber(process.env.SLICE_STUDIO_AI_SLICE_TRANSPORT_RETRIES, 2);
export const aiSliceBatchConcurrency = normalizeNumber(process.env.SLICE_STUDIO_AI_SLICE_BATCH_CONCURRENCY, 4);
export const aiSliceTileCount = normalizeNumber(process.env.SLICE_STUDIO_AI_SLICE_TILE_COUNT, 6);
export const aiSliceTileOverlap = normalizeNumber(process.env.SLICE_STUDIO_AI_SLICE_TILE_OVERLAP, 64);
export const aiSliceMaxTileSide = normalizeNumber(process.env.SLICE_STUDIO_AI_SLICE_MAX_TILE_SIDE, 1280);
export const aiSliceJpegQuality = normalizeNumber(process.env.SLICE_STUDIO_AI_SLICE_JPEG_QUALITY, 75);
export const aiSliceMaxBoxesPerPage = normalizeNumber(process.env.SLICE_STUDIO_AI_SLICE_MAX_BOXES_PER_PAGE, 80);
export const aiSliceOverviewReview = normalizeBool(process.env.SLICE_STUDIO_AI_SLICE_OVERVIEW_REVIEW, true);
export const aiSliceYoloModelPath = process.env.SLICE_STUDIO_AI_SLICE_YOLO_MODEL_PATH || "";
export const aiSliceYoloConfidence = Number(process.env.SLICE_STUDIO_AI_SLICE_YOLO_CONFIDENCE || 0.35);
export const aiSliceYoloImageSize = normalizeNumber(process.env.SLICE_STUDIO_AI_SLICE_YOLO_IMAGE_SIZE, 1024);
export const aiSliceYoloClasses = normalizeCsv(process.env.SLICE_STUDIO_AI_SLICE_YOLO_CLASSES || "Image,BackgroundImage,Map,Icon,Modal,Drawer");

function loadLocalEnv(): void {
  if (process.env.SLICE_STUDIO_LOAD_LOCAL_ENV === "false") return;
  const filePath = path.resolve(process.cwd(), ".env.local");
  if (!fs.existsSync(filePath)) return;
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

function normalizeTextStyleProvider(value: string | undefined): TextStyleProvider {
  if (value === "fallback" || value === "disabled" || value === "off") return "fallback";
  if (value === "psdlike") return "psdlike";
  if (process.env.NODE_ENV === "test" || process.env.VITEST) return "fallback";
  return "psdlike";
}

function normalizeAiSliceProvider(value: string | undefined): AiSliceProvider {
  if (value === "disabled") return "disabled";
  if (value === "yolo_local" || value === "yolo-local" || value === "yolo") return "yolo_local";
  return "openai_responses";
}

function normalizeAiSliceWireApi(value: string | undefined): AiSliceWireApi {
  if (value === "chat_completions" || value === "chat.completions" || value === "chat-completions") return "chat_completions";
  return "responses";
}

function normalizeAllowedOrigins(value: string | undefined): string[] {
  const origins = (value || "http://127.0.0.1:3010,http://localhost:3010")
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean);
  return [...new Set(origins.flatMap((origin) => [origin, ...loopbackOriginAliases(origin)]))];
}

function loopbackOriginAliases(origin: string): string[] {
  try {
    const url = new URL(origin);
    if (url.hostname === "127.0.0.1") {
      url.hostname = "localhost";
      return [url.origin];
    }
    if (url.hostname === "localhost") {
      url.hostname = "127.0.0.1";
      return [url.origin];
    }
  } catch {
    return [];
  }
  return [];
}

function normalizeBool(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined || value.trim() === "") return fallback;
  return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
}

function normalizeNumber(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function normalizeCsv(value: string): string[] {
  return [...new Set(value.split(",").map((item) => item.trim()).filter(Boolean))];
}

function trimTrailingSlash(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function normalizeEmail(value: string): string {
  return value.trim().toLowerCase();
}
