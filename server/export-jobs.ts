import { randomHex } from "./utils";
import { httpError } from "./errors";
import type { ExportJobKind, ExportJobRecord } from "../shared/types";

type ExportResult = {
  assetCount: number;
  pageCount?: number;
  url: string;
  cached: boolean;
};

type ExportRunner = (job: InternalExportJob) => Promise<ExportResult>;

type InternalExportJob = ExportJobRecord & {
  userId: string;
};

type CreateExportJobInput = {
  kind: string;
  pageId?: string;
};

const jobs = new Map<string, InternalExportJob>();
const queue: string[] = [];
const maxJobs = 200;
const maxConcurrentJobs = 1;
let runningJobs = 0;
let exportRunner: ExportRunner = defaultExportRunner;

export function createExportJob(userId: string, projectId: string, input: CreateExportJobInput): ExportJobRecord {
  const kind = normalizeExportJobKind(input.kind);
  const pageId = typeof input.pageId === "string" && input.pageId.trim() ? input.pageId.trim() : undefined;
  if (kind === "page_project" && !pageId) throw httpError(400, "pageId is required for page_project export jobs");
  if (kind !== "page_project" && pageId) throw httpError(400, "pageId is only valid for page_project export jobs");

  const now = new Date().toISOString();
  const job: InternalExportJob = {
    id: `export_job_${Date.now().toString(36)}_${randomHex(4)}`,
    userId,
    projectId,
    kind,
    pageId,
    status: "queued",
    message: queuedMessage(kind),
    createdAt: now,
    updatedAt: now
  };
  jobs.set(job.id, job);
  queue.push(job.id);
  trimFinishedJobs();
  scheduleQueue();
  return publicJob(job);
}

export function getExportJob(userId: string, projectId: string, jobId: string): ExportJobRecord {
  const job = jobs.get(jobId);
  if (!job || job.userId !== userId || job.projectId !== projectId) throw httpError(404, "Export job not found");
  return publicJob(job);
}

function scheduleQueue(): void {
  queueMicrotask(() => {
    while (runningJobs < maxConcurrentJobs && queue.length) {
      const jobId = queue.shift();
      if (!jobId) return;
      const job = jobs.get(jobId);
      if (!job || job.status !== "queued") continue;
      runningJobs += 1;
      void runJob(job).finally(() => {
        runningJobs = Math.max(0, runningJobs - 1);
        scheduleQueue();
      });
    }
  });
}

async function runJob(job: InternalExportJob): Promise<void> {
  updateJob(job, {
    status: "running",
    message: runningMessage(job.kind)
  });
  try {
    const result = await exportRunner(job);
    updateJob(job, {
      status: "succeeded",
      message: result.cached ? cachedMessage(job.kind) : succeededMessage(job.kind),
      assetCount: result.assetCount,
      pageCount: result.pageCount,
      url: result.url,
      cached: result.cached,
      finishedAt: new Date().toISOString()
    });
  } catch (error) {
    updateJob(job, {
      status: "failed",
      message: "Export failed",
      error: error instanceof Error ? error.message : String(error),
      finishedAt: new Date().toISOString()
    });
  }
}

async function defaultExportRunner(job: InternalExportJob): Promise<ExportResult> {
  if (job.kind === "assets") {
    const { exportAssets } = await import("./exporter");
    return await exportAssets(job.userId, job.projectId);
  }
  if (job.kind === "project") {
    const { exportPencilProject } = await import("./pencil-exporter");
    return await exportPencilProject(job.userId, job.projectId);
  }
  if (!job.pageId) throw httpError(400, "pageId is required for page_project export jobs");
  const { exportPencilProjectPage } = await import("./pencil-exporter");
  return await exportPencilProjectPage(job.userId, job.projectId, job.pageId);
}

export function setExportJobRunnerForTests(runner: ExportRunner): void {
  exportRunner = runner;
}

export function resetExportJobsForTests(): void {
  jobs.clear();
  queue.splice(0, queue.length);
  runningJobs = 0;
  exportRunner = defaultExportRunner;
}

function updateJob(job: InternalExportJob, patch: Partial<InternalExportJob>): void {
  Object.assign(job, patch, { updatedAt: new Date().toISOString() });
  jobs.set(job.id, job);
}

function trimFinishedJobs(): void {
  if (jobs.size <= maxJobs) return;
  const removable = [...jobs.values()]
    .filter((job) => job.status === "succeeded" || job.status === "failed")
    .sort((left, right) => left.updatedAt.localeCompare(right.updatedAt));
  for (const job of removable.slice(0, Math.max(0, jobs.size - maxJobs))) {
    jobs.delete(job.id);
  }
}

function publicJob(job: InternalExportJob): ExportJobRecord {
  const { userId: _userId, ...publicFields } = job;
  return { ...publicFields };
}

function normalizeExportJobKind(kind: string): ExportJobKind {
  if (kind === "assets" || kind === "project" || kind === "page_project") return kind;
  throw httpError(400, "Invalid export job kind");
}

function queuedMessage(kind: ExportJobKind): string {
  if (kind === "assets") return "Assets package is queued";
  if (kind === "page_project") return "Current page package is queued";
  return "Project package is queued";
}

function runningMessage(kind: ExportJobKind): string {
  if (kind === "assets") return "Preparing assets package";
  if (kind === "page_project") return "Preparing current page package";
  return "Preparing project package";
}

function succeededMessage(kind: ExportJobKind): string {
  if (kind === "assets") return "Assets package is ready";
  if (kind === "page_project") return "Current page package is ready";
  return "Project package is ready";
}

function cachedMessage(kind: ExportJobKind): string {
  if (kind === "assets") return "Reused previous assets package";
  if (kind === "page_project") return "Reused previous current page package";
  return "Reused previous project package";
}
