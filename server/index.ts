import cors from "@elysiajs/cors";
import { Elysia, t } from "elysia";
import fs from "node:fs";
import { allowedOrigins, apiHost, apiPort } from "./config";
import { initDatabase } from "./db";
import { HttpError, httpError } from "./errors";
import { exportAssets, getAssetsZipPath } from "./exporter";
import { exportPencilProject, exportPencilProjectPage, getProjectPageZipPath, getProjectZipPath } from "./pencil-exporter";
import { cropSliceToPng } from "./shape-cutout";
import { generateAiSliceBoxes } from "./ai-slice-boxes";
import { aiSliceBatchConcurrency } from "./config";
import {
  addPages,
  createProject,
  deletePage,
  deleteProject,
  getPageOriginalPath,
  getProjectDetail,
  getSliceForPreview,
  listProjectCards,
  renamePage,
  renameProject,
  reorderPages,
  replacePage,
  saveSlices
} from "./projects";
import type { SaveSlicesRequest } from "../shared/types";

const longExportIdleTimeoutSeconds = 255;

initDatabase();

const app = new Elysia({
  serve: {
    idleTimeout: longExportIdleTimeoutSeconds
  }
})
  .use(cors({ origin: allowedOrigins }))
  .onError(({ error, set }) => {
    if (error instanceof HttpError) {
      set.status = error.statusCode;
      return { error: error.message };
    }
    set.status = 500;
    return { error: error instanceof Error ? error.message : "Internal server error" };
  })
  .get("/api/health", () => ({ ok: true }))
  .get("/api/ai-slice-settings", () => ({ ok: true, batchConcurrency: aiSliceBatchConcurrency }))
  .get("/api/projects", () => ({ projects: listProjectCards() }))
  .post("/api/projects", ({ body }) => ({ project: createProject(body) }), {
    body: t.Object({
      name: t.Optional(t.String())
    })
  })
  .get("/api/projects/:projectId", ({ params }) => getProjectDetail(params.projectId))
  .patch("/api/projects/:projectId", ({ params, body }) => ({ project: renameProject(params.projectId, body.name) }), {
    body: t.Object({
      name: t.String()
    })
  })
  .delete("/api/projects/:projectId", ({ params }) => {
    deleteProject(params.projectId);
    return { ok: true };
  })
  .post("/api/projects/:projectId/pages", async ({ params, body }) => ({ pages: await addPages(params.projectId, body.files) }), {
    body: t.Object({
      files: t.Files({
        type: "image"
      })
    })
  })
  .patch("/api/projects/:projectId/pages/order", ({ params, body }) => reorderPages(params.projectId, body.pageIds), {
    body: t.Object({
      pageIds: t.Array(t.String())
    })
  })
  .patch("/api/projects/:projectId/pages/:pageId", ({ params, body }) => ({ page: renamePage(params.projectId, params.pageId, body.displayName) }), {
    body: t.Object({
      displayName: t.String()
    })
  })
  .post("/api/projects/:projectId/pages/:pageId/replace", async ({ params, body }) => replacePage(params.projectId, params.pageId, body.file), {
    body: t.Object({
      file: t.File({
        type: "image"
      })
    })
  })
  .delete("/api/projects/:projectId/pages/:pageId", ({ params }) => deletePage(params.projectId, params.pageId))
  .post("/api/projects/:projectId/pages/:pageId/ai-boxes", async ({ params }) => generateAiSliceBoxes(params.projectId, params.pageId))
  .get("/api/projects/:projectId/pages/:pageId/source", ({ params }) => {
    const filePath = getPageOriginalPath(params.projectId, params.pageId);
    return new Response(Bun.file(filePath), {
      headers: {
        "content-type": "image/png",
        "cache-control": "no-store"
      }
    });
  })
  .put("/api/projects/:projectId/slices", ({ params, body }) => ({ ok: true, project: saveSlices(params.projectId, body as SaveSlicesRequest) }))
  .get("/api/projects/:projectId/slices/:sliceId/preview.png", async ({ params }) => {
    const { originalPath, slice } = getSliceForPreview(params.projectId, params.sliceId);
    const png = await cropSliceToPng(fs.readFileSync(originalPath), slice);
    const body = new Uint8Array(png);
    return new Response(body, {
      headers: {
        "content-type": "image/png",
        "cache-control": "no-store"
      }
    });
  })
  .post("/api/projects/:projectId/export-assets", async ({ params }) => exportAssets(params.projectId))
  .get("/api/projects/:projectId/assets.zip", ({ params }) => {
    const zipPath = getAssetsZipPath(params.projectId);
    if (!fs.existsSync(zipPath)) throw httpError(404, "assets.zip has not been generated");
    return new Response(Bun.file(zipPath), {
      headers: {
        "content-type": "application/zip",
        "content-disposition": `attachment; filename="${params.projectId}-assets.zip"`
      }
    });
  })
  .post("/api/projects/:projectId/export-project", async ({ params }) => exportPencilProject(params.projectId))
  .post("/api/projects/:projectId/pages/:pageId/export-project", async ({ params }) => exportPencilProjectPage(params.projectId, params.pageId))
  .get("/api/projects/:projectId/pages/:pageId/project.zip", ({ params }) => {
    const zipPath = getProjectPageZipPath(params.projectId, params.pageId);
    if (!fs.existsSync(zipPath)) throw httpError(404, "page project.zip has not been generated");
    return new Response(Bun.file(zipPath), {
      headers: {
        "content-type": "application/zip",
        "content-disposition": `attachment; filename="${params.projectId}-${params.pageId}-project.zip"`
      }
    });
  })
  .get("/api/projects/:projectId/project.zip", ({ params }) => {
    const zipPath = getProjectZipPath(params.projectId);
    if (!fs.existsSync(zipPath)) throw httpError(404, "project.zip has not been generated");
    return new Response(Bun.file(zipPath), {
      headers: {
        "content-type": "application/zip",
        "content-disposition": `attachment; filename="${params.projectId}-project.zip"`
      }
    });
  })
  .listen({
    hostname: apiHost,
    port: apiPort
  });

console.log(`Slice Studio API listening on http://${app.server?.hostname}:${app.server?.port}`);
