import cors from "@elysiajs/cors";
import { Elysia, t } from "elysia";
import fs from "node:fs";
import { allowedOrigin, apiHost, apiPort } from "./config";
import { initDatabase } from "./db";
import { HttpError, httpError } from "./errors";
import { exportAssets, getAssetsZipPath } from "./exporter";
import {
  addPages,
  createProject,
  deletePage,
  deleteProject,
  getPageOriginalPath,
  getProjectDetail,
  listProjectCards,
  renamePage,
  renameProject,
  reorderPages,
  replacePage,
  saveSlices
} from "./projects";
import type { SaveSlicesRequest } from "../shared/types";

initDatabase();

const app = new Elysia()
  .use(cors({ origin: allowedOrigin }))
  .onError(({ error, set }) => {
    if (error instanceof HttpError) {
      set.status = error.statusCode;
      return { error: error.message };
    }
    set.status = 500;
    return { error: error instanceof Error ? error.message : "Internal server error" };
  })
  .get("/api/health", () => ({ ok: true }))
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
  .listen({
    hostname: apiHost,
    port: apiPort
  });

console.log(`Slice Studio API listening on http://${app.server?.hostname}:${app.server?.port}`);
