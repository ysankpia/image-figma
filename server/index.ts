import cors from "@elysiajs/cors";
import { Elysia, t } from "elysia";
import { aiSliceBatchConcurrency, aiSliceProvider, aiSliceYoloClasses, allowedOrigins, apiHost, apiPort } from "./config";
import {
  buildSessionCookie,
  clearSessionCookie,
  claimUnownedProjects,
  ensureLocalOwner,
  getCurrentUser,
  requireUser,
  signInWithEmail,
  signOut,
  signUpWithEmail
} from "./auth";
import { initDatabase } from "./db";
import { HttpError, httpError } from "./errors";
import { exportAssets } from "./exporter";
import { exportPencilProject, exportPencilProjectPage } from "./pencil-exporter";
import { cropSliceToPng } from "./shape-cutout";
import { generateAiSliceBoxes } from "./ai-slice-boxes";
import { storage } from "./storage";
import { resolveSignedStorageDownload } from "./storage-download";
import {
  addPages,
  createProject,
  deletePage,
  deleteProject,
  getPageOriginalKey,
  getPageOriginalPath,
  getPageThumbnailKey,
  getProjectDetail,
  getSliceForPreview,
  listProjectCards,
  renamePage,
  renameProject,
  reorderPages,
  replacePage,
  saveSlices
} from "./projects";
import { assertProjectExists } from "./projects";
import type { SaveSlicesRequest } from "../shared/types";

const longExportIdleTimeoutSeconds = 255;

await initDatabase();
const localOwner = await ensureLocalOwner();
await claimUnownedProjects(localOwner.id);

const app = new Elysia({
  serve: {
    idleTimeout: longExportIdleTimeoutSeconds
  }
})
  .use(cors({ origin: allowedOrigins, credentials: true }))
  .onError(({ code, error, set }) => {
    if (code === "NOT_FOUND") {
      set.status = 404;
      return { error: "Not found" };
    }
    if (error instanceof HttpError) {
      set.status = error.statusCode;
      return { error: error.message };
    }
    set.status = 500;
    return { error: error instanceof Error ? error.message : "Internal server error" };
  })
  .get("/api/health", () => ({ ok: true }))
  .get("/api/storage-download", ({ query }) => {
    const download = resolveSignedStorageDownload(query.token);
    return storage.response(download.key, download.response);
  }, {
    query: t.Object({
      token: t.String({ minLength: 1 })
    })
  })
  .get("/api/auth/session", async ({ request }) => ({ user: await getCurrentUser(request) }))
  .post("/api/auth/sign-up", async ({ body, set }) => {
    const session = await signUpWithEmail(body.name, body.email, body.password);
    set.headers["set-cookie"] = buildSessionCookie(session.token, session.expiresAt);
    return { user: session.user };
  }, {
    body: t.Object({
      name: t.String({ minLength: 1 }),
      email: t.String({ minLength: 3 }),
      password: t.String({ minLength: 8 })
    })
  })
  .post("/api/auth/sign-in", async ({ body, set }) => {
    const session = await signInWithEmail(body.email, body.password);
    set.headers["set-cookie"] = buildSessionCookie(session.token, session.expiresAt);
    return { user: session.user };
  }, {
    body: t.Object({
      email: t.String({ minLength: 3 }),
      password: t.String({ minLength: 1 })
    })
  })
  .post("/api/auth/sign-out", async ({ request, set }) => {
    await signOut(request);
    set.headers["set-cookie"] = clearSessionCookie();
    return { ok: true };
  })
  .get("/api/ai-slice-settings", () => ({
    ok: true,
    provider: aiSliceProvider,
    batchConcurrency: aiSliceBatchConcurrency,
    yoloClasses: aiSliceProvider === "yolo_local" ? aiSliceYoloClasses : undefined
  }))
  .get("/api/projects", async ({ request }) => {
    const user = await requireUser(request);
    return { projects: await listProjectCards(user.id) };
  })
  .post("/api/projects", async ({ request, body }) => {
    const user = await requireUser(request);
    return { project: await createProject(user.id, body) };
  }, {
    body: t.Object({
      name: t.Optional(t.String())
    })
  })
  .get("/api/projects/:projectId", async ({ request, params }) => getProjectDetail((await requireUser(request)).id, params.projectId))
  .patch("/api/projects/:projectId", async ({ request, params, body }) => ({ project: await renameProject((await requireUser(request)).id, params.projectId, body.name) }), {
    body: t.Object({
      name: t.String()
    })
  })
  .delete("/api/projects/:projectId", async ({ request, params }) => {
    await deleteProject((await requireUser(request)).id, params.projectId);
    return { ok: true };
  })
  .post("/api/projects/:projectId/pages", async ({ request, params, body }) => ({ pages: await addPages((await requireUser(request)).id, params.projectId, body.files) }), {
    body: t.Object({
      files: t.Files({
        type: "image"
      })
    })
  })
  .patch("/api/projects/:projectId/pages/order", async ({ request, params, body }) => reorderPages((await requireUser(request)).id, params.projectId, body.pageIds), {
    body: t.Object({
      pageIds: t.Array(t.String())
    })
  })
  .patch("/api/projects/:projectId/pages/:pageId", async ({ request, params, body }) => ({ page: await renamePage((await requireUser(request)).id, params.projectId, params.pageId, body.displayName) }), {
    body: t.Object({
      displayName: t.String()
    })
  })
  .post("/api/projects/:projectId/pages/:pageId/replace", async ({ request, params, body }) => replacePage((await requireUser(request)).id, params.projectId, params.pageId, body.file), {
    body: t.Object({
      file: t.File({
        type: "image"
      })
    })
  })
  .delete("/api/projects/:projectId/pages/:pageId", async ({ request, params }) => deletePage((await requireUser(request)).id, params.projectId, params.pageId))
  .post("/api/projects/:projectId/pages/:pageId/ai-boxes", async ({ request, params }) => generateAiSliceBoxes((await requireUser(request)).id, params.projectId, params.pageId))
  .get("/api/projects/:projectId/pages/:pageId/source", async ({ request, params }) => {
    const user = await requireUser(request);
    await getPageOriginalPath(user.id, params.projectId, params.pageId);
    return storage.response(await getPageOriginalKey(user.id, params.projectId, params.pageId), {
      contentType: "image/png",
      cacheControl: "no-store",
      notFoundMessage: "Original image not found"
    });
  })
  .get("/api/projects/:projectId/pages/:pageId/thumbnail", async ({ request, params }) => {
    const user = await requireUser(request);
    return storage.response(await getPageThumbnailKey(user.id, params.projectId, params.pageId), {
      contentType: "image/png",
      cacheControl: "no-store",
      notFoundMessage: "Page thumbnail not found"
    });
  })
  .put("/api/projects/:projectId/slices", async ({ request, params, body }) => ({ ok: true, project: await saveSlices((await requireUser(request)).id, params.projectId, body as SaveSlicesRequest) }))
  .get("/api/projects/:projectId/slices/:sliceId/preview.png", async ({ request, params }) => {
    const { originalKey, slice } = await getSliceForPreview((await requireUser(request)).id, params.projectId, params.sliceId);
    const png = await cropSliceToPng(storage.read(originalKey, "Original image not found"), slice);
    const body = new Uint8Array(png);
    return new Response(body, {
      headers: {
        "content-type": "image/png",
        "cache-control": "no-store"
      }
    });
  })
  .post("/api/projects/:projectId/export-assets", async ({ request, params }) => exportAssets((await requireUser(request)).id, params.projectId))
  .get("/api/projects/:projectId/assets.zip", async ({ request, params }) => {
    const user = await requireUser(request);
    await assertProjectExists(user.id, params.projectId);
    return storage.response(storage.firstExistingKey(storage.assetsZipKeyVariants(user.id, params.projectId), "assets.zip has not been generated"), {
      contentType: "application/zip",
      contentDisposition: `attachment; filename="${params.projectId}-assets.zip"`,
      notFoundMessage: "assets.zip has not been generated"
    });
  })
  .post("/api/projects/:projectId/export-project", async ({ request, params }) => exportPencilProject((await requireUser(request)).id, params.projectId))
  .post("/api/projects/:projectId/pages/:pageId/export-project", async ({ request, params }) => exportPencilProjectPage((await requireUser(request)).id, params.projectId, params.pageId))
  .get("/api/projects/:projectId/pages/:pageId/project.zip", async ({ request, params }) => {
    const user = await requireUser(request);
    await assertProjectExists(user.id, params.projectId);
    return storage.response(storage.firstExistingKey(storage.projectPageZipKeyVariants(user.id, params.projectId, params.pageId), "page project.zip has not been generated"), {
      contentType: "application/zip",
      contentDisposition: `attachment; filename="${params.projectId}-${params.pageId}-project.zip"`,
      notFoundMessage: "page project.zip has not been generated"
    });
  })
  .get("/api/projects/:projectId/project.zip", async ({ request, params }) => {
    const user = await requireUser(request);
    await assertProjectExists(user.id, params.projectId);
    return storage.response(storage.firstExistingKey(storage.projectZipKeyVariants(user.id, params.projectId), "project.zip has not been generated"), {
      contentType: "application/zip",
      contentDisposition: `attachment; filename="${params.projectId}-project.zip"`,
      notFoundMessage: "project.zip has not been generated"
    });
  })
  .listen({
    hostname: apiHost,
    port: apiPort
  });

console.log(`Slice Studio API listening on http://${app.server?.hostname}:${app.server?.port}`);
