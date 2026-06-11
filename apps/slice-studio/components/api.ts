import type { AiSliceBoxesResponse, AiSliceSettingsResponse, PageRecord, ProjectDetail, ProjectSummary, SaveSlicesRequest } from "@/shared/types";

export const apiBaseUrl = process.env.NEXT_PUBLIC_SLICE_STUDIO_API_URL || "http://127.0.0.1:4110";

export async function apiGet<T>(path: string): Promise<T> {
  return request<T>(path, { method: "GET" });
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: JSON.stringify(body || {}),
    headers: { "content-type": "application/json" }
  });
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "PATCH",
    body: JSON.stringify(body),
    headers: { "content-type": "application/json" }
  });
}

export async function apiDelete<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE" });
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "PUT",
    body: JSON.stringify(body),
    headers: { "content-type": "application/json" }
  });
}

export async function uploadPages(projectId: string, files: File[]): Promise<{ pages: ProjectDetail["pages"] }> {
  const formData = new FormData();
  for (const file of files) formData.append("files", file);
  return request(`/api/projects/${projectId}/pages`, {
    method: "POST",
    body: formData
  });
}

export async function saveSlices(projectId: string, payload: SaveSlicesRequest): Promise<{ ok: true; project: ProjectSummary }> {
  return apiPut(`/api/projects/${projectId}/slices`, payload);
}

export async function generateAiBoxes(projectId: string, pageId: string): Promise<AiSliceBoxesResponse> {
  return apiPost(`/api/projects/${projectId}/pages/${pageId}/ai-boxes`, {});
}

export async function getAiSliceSettings(): Promise<AiSliceSettingsResponse> {
  return apiGet("/api/ai-slice-settings");
}

export async function renamePage(projectId: string, pageId: string, displayName: string): Promise<{ page: PageRecord }> {
  return apiPatch(`/api/projects/${projectId}/pages/${pageId}`, { displayName });
}

export async function reorderPages(projectId: string, pageIds: string[]): Promise<ProjectDetail> {
  return apiPatch(`/api/projects/${projectId}/pages/order`, { pageIds });
}

export async function deletePage(projectId: string, pageId: string): Promise<ProjectDetail> {
  return apiDelete(`/api/projects/${projectId}/pages/${pageId}`);
}

export async function replacePage(projectId: string, pageId: string, file: File): Promise<ProjectDetail> {
  const formData = new FormData();
  formData.append("file", file);
  return request(`/api/projects/${projectId}/pages/${pageId}/replace`, {
    method: "POST",
    body: formData
  });
}

export async function request<T>(path: string, init: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, init);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    throw new Error(typeof data === "object" && data && "error" in data ? String(data.error) : `HTTP ${response.status}`);
  }
  return data as T;
}
