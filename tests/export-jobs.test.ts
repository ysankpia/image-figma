import { afterEach, describe, expect, it } from "vitest";
import {
  cancelExportJob,
  createExportJob,
  getExportJob,
  listExportJobs,
  resetExportJobsForTests,
  setExportJobRunnerForTests
} from "../server/export-jobs";

function wait(ms = 0): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForStatus(
  userId: string,
  projectId: string,
  jobId: string,
  status: "succeeded" | "failed"
) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const job = getExportJob(userId, projectId, jobId);
    if (job.status === status) return job;
    await wait(5);
  }
  throw new Error(`job did not reach ${status}`);
}

afterEach(() => {
  resetExportJobsForTests();
});

describe("export jobs", () => {
  it("runs queued export jobs and exposes the signed URL on success", async () => {
    setExportJobRunnerForTests(async (job) => {
      await wait(1);
      return {
        assetCount: job.kind === "assets" ? 2 : 3,
        pageCount: job.kind === "assets" ? undefined : 1,
        url: `/api/storage-download?token=${job.id}`,
        cached: false
      };
    });

    const created = createExportJob("user_1", "project_1", { kind: "assets" });
    expect(created.status).toBe("queued");
    const finished = await waitForStatus("user_1", "project_1", created.id, "succeeded");

    expect(finished.assetCount).toBe(2);
    expect(finished.url).toBe(`/api/storage-download?token=${created.id}`);
    expect(finished.cached).toBe(false);
    expect(finished.finishedAt).toBeTruthy();
  });

  it("records export failures without throwing from job creation", async () => {
    setExportJobRunnerForTests(async () => {
      throw new Error("boom");
    });

    const created = createExportJob("user_1", "project_1", { kind: "project" });
    const failed = await waitForStatus("user_1", "project_1", created.id, "failed");

    expect(failed.error).toBe("boom");
    expect(failed.url).toBeUndefined();
  });

  it("requires pageId for page-scoped project packages", () => {
    expect(() => createExportJob("user_1", "project_1", { kind: "page_project" })).toThrow("pageId is required");
    expect(() => createExportJob("user_1", "project_1", { kind: "assets", pageId: "page_0001" })).toThrow("pageId is only valid");
  });

  it("does not expose jobs across users or projects", async () => {
    setExportJobRunnerForTests(async () => ({
      assetCount: 1,
      url: "/api/storage-download?token=ok",
      cached: true
    }));

    const created = createExportJob("user_1", "project_1", { kind: "assets" });
    await waitForStatus("user_1", "project_1", created.id, "succeeded");

    expect(() => getExportJob("user_2", "project_1", created.id)).toThrow("Export job not found");
    expect(() => getExportJob("user_1", "project_2", created.id)).toThrow("Export job not found");
  });

  it("lists jobs for the current user and project", async () => {
    setExportJobRunnerForTests(async () => ({
      assetCount: 1,
      url: "/api/storage-download?token=ok",
      cached: true
    }));

    const first = createExportJob("user_1", "project_1", { kind: "assets" });
    const second = createExportJob("user_1", "project_1", { kind: "project" });
    createExportJob("user_1", "project_2", { kind: "assets" });
    createExportJob("user_2", "project_1", { kind: "assets" });

    const jobs = listExportJobs("user_1", "project_1");

    expect(jobs.map((job) => job.id).sort()).toEqual([first.id, second.id].sort());
  });

  it("cancels queued jobs and removes them from the queue", async () => {
    let releaseFirst!: () => void;
    setExportJobRunnerForTests(async (job) => {
      if (job.kind === "assets") {
        await new Promise<void>((resolve) => {
          releaseFirst = resolve;
        });
      }
      return {
        assetCount: 1,
        url: `/api/storage-download?token=${job.id}`,
        cached: false
      };
    });

    const running = createExportJob("user_1", "project_1", { kind: "assets" });
    const queued = createExportJob("user_1", "project_1", { kind: "project" });
    await wait(5);

    const canceled = cancelExportJob("user_1", "project_1", queued.id);
    expect(canceled.status).toBe("canceled");

    releaseFirst();
    await waitForStatus("user_1", "project_1", running.id, "succeeded");
    expect(getExportJob("user_1", "project_1", queued.id).status).toBe("canceled");
  });

  it("does not pretend to cancel running jobs", async () => {
    let release!: () => void;
    setExportJobRunnerForTests(async () => {
      await new Promise<void>((resolve) => {
        release = resolve;
      });
      return {
        assetCount: 1,
        url: "/api/storage-download?token=ok",
        cached: false
      };
    });

    const running = createExportJob("user_1", "project_1", { kind: "assets" });
    await wait(5);

    expect(() => cancelExportJob("user_1", "project_1", running.id)).toThrow("Running export jobs cannot be canceled");

    release();
    await waitForStatus("user_1", "project_1", running.id, "succeeded");
  });
});
