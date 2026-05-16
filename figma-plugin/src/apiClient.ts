import type { DesignDSL } from "@image-figma/dsl-schema";

export const API_BASE_URL = "http://localhost:8000/api";

export interface UploadResult {
  taskId: string;
  status: string;
  stage: string;
  progress: number;
}

export interface TaskResult {
  taskId: string;
  status: string;
  stage: string;
  progress: number;
  message: string;
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

export async function uploadPng(fileName: string, bytes: Uint8Array): Promise<UploadResult> {
  const boundary = `image-figma-${Date.now().toString(16)}`;
  const body = createMultipartBody(boundary, fileName, bytes);
  const response = await apiFetch(`${API_BASE_URL}/upload`, {
    method: "POST",
    headers: {
      "Content-Type": `multipart/form-data; boundary=${boundary}`
    },
    body
  });
  return response.data as UploadResult;
}

export async function getTask(taskId: string): Promise<TaskResult> {
  const response = await apiFetch(`${API_BASE_URL}/tasks/${encodeURIComponent(taskId)}`);
  return response.data as TaskResult;
}

export async function getTaskDsl(taskId: string): Promise<DesignDSL> {
  const response = await apiFetch(`${API_BASE_URL}/tasks/${encodeURIComponent(taskId)}/dsl`);
  const data = response.data as { dsl?: unknown };
  if (!data || typeof data !== "object" || !data.dsl) {
    throw new BackendApiError("BACKEND_DSL_INVALID_RESPONSE", "Backend returned an invalid DSL response.");
  }
  return data.dsl as DesignDSL;
}

async function apiFetch(url: string, init?: ApiRequestInit): Promise<ApiSuccessResponse> {
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

  const apiResponse = payload as ApiEnvelope;
  if (!apiResponse.success) {
    const error = apiResponse.error || {};
    throw new BackendApiError(
      error.code || "BACKEND_REQUEST_FAILED",
      error.message || "Backend request failed.",
      error.stage,
      error.taskId
    );
  }

  return apiResponse as ApiSuccessResponse;
}

function createMultipartBody(boundary: string, fileName: string, bytes: Uint8Array): Uint8Array {
  const safeName = fileName.replace(/[^A-Za-z0-9._-]/g, "_");
  const prefix = encodeAscii(
    `--${boundary}\r\nContent-Disposition: form-data; name="file"; filename="${safeName}"\r\nContent-Type: image/png\r\n\r\n`
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
  json(): Promise<unknown>;
}

interface ApiSuccessResponse {
  success: true;
  data: unknown;
}

interface ApiFailureResponse {
  success: false;
  error?: {
    code?: string;
    message?: string;
    stage?: string;
    taskId?: string;
  };
}

type ApiEnvelope = ApiSuccessResponse | ApiFailureResponse;

declare function fetch(url: string, init?: ApiRequestInit): Promise<ApiResponse>;
