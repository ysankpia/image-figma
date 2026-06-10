import type { CandidatesDoc, ManualDoc, ProjectSummary, ReviewState } from './types';

type ApiResponse<T> = { success: boolean; data: T };

export async function apiGet<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(await response.text());
  return ((await response.json()) as ApiResponse<T>).data;
}

export async function apiPut<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(await response.text());
  return ((await response.json()) as ApiResponse<T>).data;
}

export async function apiPost<T>(url: string, body?: BodyInit): Promise<T> {
  const response = await fetch(url, { method: 'POST', body });
  if (!response.ok) throw new Error(await response.text());
  return ((await response.json()) as ApiResponse<T>).data;
}

export async function listProjects(): Promise<ProjectSummary[]> {
  return (await apiGet<{ projects: ProjectSummary[] }>('/api/handoff-projects')).projects;
}

export async function getProject(projectId: string): Promise<ProjectSummary> {
  return apiGet<ProjectSummary>(`/api/handoff-projects/${projectId}`);
}

export async function getCandidates(projectId: string): Promise<CandidatesDoc> {
  return apiGet<CandidatesDoc>(`/api/handoff-projects/${projectId}/candidates`);
}

export async function getManual(projectId: string): Promise<ManualDoc> {
  return apiGet<ManualDoc>(`/api/handoff-projects/${projectId}/manual-slices`);
}

export async function getReviewState(projectId: string): Promise<ReviewState> {
  return apiGet<ReviewState>(`/api/handoff-projects/${projectId}/review-state`);
}
