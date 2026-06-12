import type { DraftRuntimeDSL } from "@image-figma/dsl-schema";

export const API_BASE_URL = "http://localhost:8000/api";

export interface DraftDiagnostics {
  ocrProvider?: string;
  ocrPresent?: boolean;
  ocrTextCount?: number;
  ocrCacheHit?: boolean;
  textLayerCount?: number;
  rasterLayerCount?: number;
  shapeLayerCount?: number;
  missingAssetCount?: number;
  fullPageVisibleRaster?: number;
  shapeAssetCount?: number;
}

export interface UploadResult {
  taskId: string;
  status: string;
  stage?: string;
  progress?: number;
  dslUrl?: string;
  previewUrl?: string;
  diagnostics?: DraftDiagnostics;
}

export interface TaskResult {
  taskId: string;
  status: string;
  stage?: string;
  progress?: number;
  message?: string;
  warnings?: TaskWarning[];
  dslUrl?: string;
  previewUrl?: string;
  diagnostics?: DraftDiagnostics;
  error?: {
    code?: string;
    message?: string;
  };
}

export interface TaskWarning {
  code: string;
  message: string;
  stage?: string;
}

export class BackendApiError extends Error {
  code: string;
  stage?: string;
  taskId?: string;

  constructor(code: string, message: string, stage?: string, taskId?: string) {
    super(message);
    this.name = "BackendApiError";
    this.code = code;
    if (stage !== undefined) {
      this.stage = stage;
    }
    if (taskId !== undefined) {
      this.taskId = taskId;
    }
  }
}

export async function uploadPngDraftPreview(fileName: string, bytes: Uint8Array): Promise<UploadResult> {
  return uploadPngTo("/draft-preview", fileName, bytes);
}

async function uploadPngTo(endpoint: string, fileName: string, bytes: Uint8Array): Promise<UploadResult> {
  const boundary = `image-figma-${Date.now().toString(16)}`;
  const body = createMultipartBody(boundary, "image", fileName, bytes);
  const payload = await apiFetchJson(`${API_BASE_URL}${endpoint}`, {
    method: "POST",
    headers: {
      "Content-Type": `multipart/form-data; boundary=${boundary}`
    },
    body
  });
  return normalizeUploadResult(payload);
}

export async function getDraftPreviewTask(taskId: string): Promise<TaskResult> {
  const payload = await apiFetchJson(`${API_BASE_URL}/draft-preview/${encodeURIComponent(taskId)}`);
  return normalizeTaskResult(payload);
}

export async function getDraftPreviewDsl(taskId: string): Promise<DraftRuntimeDSL> {
  const payload = await apiFetchJson(`${API_BASE_URL}/draft-preview/${encodeURIComponent(taskId)}/dsl`);
  return normalizeDraftRuntimeDsl(payload);
}

async function apiFetchJson(url: string, init?: ApiRequestInit): Promise<unknown> {
  let response: ApiResponse;
  try {
    response = await fetch(url, init);
  } catch (error) {
    throw new BackendApiError(
      "BACKEND_REQUEST_FAILED",
      error instanceof Error ? error.message : "Backend request failed."
    );
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch (_error) {
    throw new BackendApiError("BACKEND_INVALID_JSON", "Backend returned invalid JSON.");
  }

  if (!response.ok) {
    throw backendErrorFromPayload(payload, response.status);
  }

  if (isRecord(payload) && payload.success === false) {
    const error = isRecord(payload.error) ? payload.error : {};
    throw new BackendApiError(
      typeof error.code === "string" ? error.code : "BACKEND_REQUEST_FAILED",
      typeof error.message === "string" ? error.message : "Backend request failed.",
      typeof error.stage === "string" ? error.stage : undefined,
      typeof error.taskId === "string" ? error.taskId : undefined
    );
  }

  return payload;
}

export function normalizeUploadResult(payload: unknown): UploadResult {
  const data = unwrapSuccessData(payload);
  if (!isRecord(data)) {
    throw new BackendApiError("BACKEND_UPLOAD_INVALID_RESPONSE", "Backend returned an invalid upload response.");
  }
  const taskId = stringField(data, "taskId");
  const status = stringField(data, "status") || "completed";
  if (!taskId) {
    throw new BackendApiError("BACKEND_UPLOAD_INVALID_RESPONSE", "Upload response is missing taskId.");
  }
  const upload: UploadResult = {
    taskId,
    status
  };
  assignString(upload, "stage", stringField(data, "stage"));
  assignNumber(upload, "progress", numberField(data, "progress"));
  assignString(upload, "dslUrl", stringField(data, "dslUrl"));
  assignString(upload, "previewUrl", stringField(data, "previewUrl"));
  assignDiagnostics(upload, normalizeDiagnostics(data.diagnostics));
  return upload;
}

export function normalizeTaskResult(payload: unknown): TaskResult {
  const data = unwrapSuccessData(payload);
  if (!isRecord(data)) {
    throw new BackendApiError("BACKEND_TASK_INVALID_RESPONSE", "Backend returned an invalid task response.");
  }
  const taskId = stringField(data, "taskId");
  const status = stringField(data, "status");
  if (!taskId || !status) {
    throw new BackendApiError("BACKEND_TASK_INVALID_RESPONSE", "Task response is missing taskId or status.");
  }
  const task: TaskResult = { taskId, status };
  assignString(task, "stage", stringField(data, "stage"));
  assignNumber(task, "progress", numberField(data, "progress"));
  assignString(task, "message", stringField(data, "message"));
  assignString(task, "dslUrl", stringField(data, "dslUrl"));
  assignString(task, "previewUrl", stringField(data, "previewUrl"));
  assignDiagnostics(task, normalizeDiagnostics(data.diagnostics));
  const warnings = normalizeWarnings(data.warnings);
  if (warnings !== undefined) {
    task.warnings = warnings;
  }
  if (isRecord(data.error)) {
    const error: { code?: string; message?: string } = {};
    assignString(error, "code", stringField(data.error, "code"));
    assignString(error, "message", stringField(data.error, "message"));
    task.error = error;
  }
  return task;
}

export function normalizeDraftRuntimeDsl(payload: unknown): DraftRuntimeDSL {
  if (isDraftRuntimeDsl(payload)) {
    return payload;
  }
  const data = unwrapSuccessData(payload);
  if (isDraftRuntimeDsl(data)) {
    return data;
  }
  if (isRecord(data) && isDraftRuntimeDsl(data.dsl)) {
    return data.dsl;
  }
  throw new BackendApiError("BACKEND_DSL_INVALID_RESPONSE", "Backend returned an invalid Draft Runtime DSL response.");
}

function unwrapSuccessData(payload: unknown): unknown {
  if (isRecord(payload) && payload.success === true && "data" in payload) {
    return payload.data;
  }
  return payload;
}

function backendErrorFromPayload(payload: unknown, status: number): BackendApiError {
  if (isRecord(payload)) {
    const detail = payload.detail;
    if (isRecord(detail)) {
      return new BackendApiError(
        stringField(detail, "code") || `HTTP_${status}`,
        stringField(detail, "error") || stringField(detail, "message") || "Backend request failed.",
        stringField(detail, "stage"),
        stringField(detail, "taskId")
      );
    }
    if (typeof detail === "string" && detail) {
      return new BackendApiError(`HTTP_${status}`, detail);
    }
    if (isRecord(payload.error)) {
      return new BackendApiError(
        stringField(payload.error, "code") || `HTTP_${status}`,
        stringField(payload.error, "message") || "Backend request failed.",
        stringField(payload.error, "stage"),
        stringField(payload.error, "taskId")
      );
    }
  }
  return new BackendApiError(`HTTP_${status}`, "Backend request failed.");
}

function normalizeDiagnostics(value: unknown): DraftDiagnostics | undefined {
  if (!isRecord(value)) {
    return undefined;
  }
  const diagnostics: DraftDiagnostics = {};
  assignString(diagnostics, "ocrProvider", stringField(value, "ocrProvider"));
  assignBoolean(diagnostics, "ocrPresent", booleanField(value, "ocrPresent"));
  assignNumber(diagnostics, "ocrTextCount", numberField(value, "ocrTextCount"));
  assignBoolean(diagnostics, "ocrCacheHit", booleanField(value, "ocrCacheHit"));
  assignNumber(diagnostics, "textLayerCount", numberField(value, "textLayerCount"));
  assignNumber(diagnostics, "rasterLayerCount", numberField(value, "rasterLayerCount"));
  assignNumber(diagnostics, "shapeLayerCount", numberField(value, "shapeLayerCount"));
  assignNumber(diagnostics, "missingAssetCount", numberField(value, "missingAssetCount"));
  assignNumber(diagnostics, "fullPageVisibleRaster", numberField(value, "fullPageVisibleRaster"));
  assignNumber(diagnostics, "shapeAssetCount", numberField(value, "shapeAssetCount"));
  return diagnostics;
}

function normalizeWarnings(value: unknown): TaskWarning[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  const warnings: TaskWarning[] = [];
  for (const item of value) {
    if (!isRecord(item)) {
      continue;
    }
    const code = stringField(item, "code");
    const message = stringField(item, "message");
    if (!code || !message) {
      continue;
    }
    const warning: TaskWarning = { code, message };
    assignString(warning, "stage", stringField(item, "stage"));
    warnings.push(warning);
  }
  return warnings;
}

function assignString<T extends object, K extends keyof T>(target: T, key: K, value: string | undefined): void {
  if (value !== undefined) {
    target[key] = value as T[K];
  }
}

function assignNumber<T extends object, K extends keyof T>(target: T, key: K, value: number | undefined): void {
  if (value !== undefined) {
    target[key] = value as T[K];
  }
}

function assignBoolean<T extends object, K extends keyof T>(target: T, key: K, value: boolean | undefined): void {
  if (value !== undefined) {
    target[key] = value as T[K];
  }
}

function assignDiagnostics<T extends object>(target: T, value: DraftDiagnostics | undefined): void {
  if (value !== undefined) {
    (target as T & { diagnostics: DraftDiagnostics }).diagnostics = value;
  }
}

function isDraftRuntimeDsl(value: unknown): value is DraftRuntimeDSL {
  return isRecord(value) && value.version === "1.0" && value.kind === "draft_runtime";
}

function stringField(record: Record<string, unknown>, key: string): string | undefined {
  const value = record[key];
  return typeof value === "string" ? value : undefined;
}

function numberField(record: Record<string, unknown>, key: string): number | undefined {
  const value = record[key];
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function booleanField(record: Record<string, unknown>, key: string): boolean | undefined {
  const value = record[key];
  return typeof value === "boolean" ? value : undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function createMultipartBody(boundary: string, fieldName: string, fileName: string, bytes: Uint8Array): Uint8Array {
  const safeName = fileName.replace(/[^A-Za-z0-9._-]/g, "_");
  const prefix = encodeAscii(
    `--${boundary}\r\nContent-Disposition: form-data; name="${fieldName}"; filename="${safeName}"\r\nContent-Type: image/png\r\n\r\n`
  );
  const suffix = encodeAscii(`\r\n--${boundary}--\r\n`);
  const body = new Uint8Array(prefix.length + bytes.length + suffix.length);
  body.set(prefix, 0);
  body.set(bytes, prefix.length);
  body.set(suffix, prefix.length + bytes.length);
  return body;
}

function encodeAscii(value: string): Uint8Array {
  const bytes = new Uint8Array(value.length);
  for (let index = 0; index < value.length; index += 1) {
    bytes[index] = value.charCodeAt(index) & 0x7f;
  }
  return bytes;
}

interface ApiRequestInit {
  method?: string;
  headers?: Record<string, string>;
  body?: Uint8Array;
}

interface ApiResponse {
  ok: boolean;
  status: number;
  json(): Promise<unknown>;
}

declare function fetch(url: string, init?: ApiRequestInit): Promise<ApiResponse>;
