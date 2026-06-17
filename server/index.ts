import cors from "@elysiajs/cors";
import { Elysia, t } from "elysia";
import fs from "node:fs";
import { allowedOrigins, apiHost, apiPort } from "./config";
import {
  buildSessionCookie,
  clearSessionCookie,
  claimUnownedProjects,
  ensureLocalOwner,
  getCurrentUser,
  requireAdmin,
  requireUser,
  seedEntitlement,
  signInWithEmail,
  signOut,
  signUpWithEmail
} from "./auth";
import { initDatabase } from "./db";
import { createPaymentOrder, getAdminOverview, getEntitlementSummary, listPaymentOrders, listPlans, listUsageEvents } from "./billing";
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
import { assertProjectExists } from "./projects";
import type { SaveSlicesRequest } from "../shared/types";

const longExportIdleTimeoutSeconds = 255;

initDatabase();
const localOwner = ensureLocalOwner();
seedEntitlement(localOwner.id);
claimUnownedProjects(localOwner.id);

const app = new Elysia({
  serve: {
    idleTimeout: longExportIdleTimeoutSeconds
  }
})
  .use(cors({ origin: allowedOrigins, credentials: true }))
  .onError(({ error, set }) => {
    if (error instanceof HttpError) {
      set.status = error.statusCode;
      return { error: error.message };
    }
    set.status = 500;
    return { error: error instanceof Error ? error.message : "Internal server error" };
  })
  .get("/api/health", () => ({ ok: true }))
  .get("/api/auth/session", ({ request }) => ({ user: getCurrentUser(request) }))
  .get("/api/me", ({ request }) => {
    const user = requireUser(request);
    return {
      user,
      entitlement: getEntitlementSummary(user.id),
      usage: listUsageEvents(user.id, 20),
      paymentOrders: listPaymentOrders(user.id, 10)
    };
  })
  .post("/api/auth/sign-up", ({ body, set }) => {
    const session = signUpWithEmail(body.name, body.email, body.password);
    set.headers["set-cookie"] = buildSessionCookie(session.token, session.expiresAt);
    return { user: session.user };
  }, {
    body: t.Object({
      name: t.String({ minLength: 1 }),
      email: t.String({ minLength: 3 }),
      password: t.String({ minLength: 8 })
    })
  })
  .post("/api/auth/sign-in", ({ body, set }) => {
    const session = signInWithEmail(body.email, body.password);
    set.headers["set-cookie"] = buildSessionCookie(session.token, session.expiresAt);
    return { user: session.user };
  }, {
    body: t.Object({
      email: t.String({ minLength: 3 }),
      password: t.String({ minLength: 1 })
    })
  })
  .post("/api/auth/sign-out", ({ request, set }) => {
    signOut(request);
    set.headers["set-cookie"] = clearSessionCookie();
    return { ok: true };
  })
  .get("/api/billing/plans", () => ({ plans: listPlans() }))
  .post("/api/billing/orders", ({ request, body }) => {
    const user = requireUser(request);
    return { order: createPaymentOrder(user.id, body.planId, body.provider) };
  }, {
    body: t.Object({
      planId: t.String(),
      provider: t.Optional(t.String())
    })
  })
  .get("/api/admin/overview", ({ request }) => {
    const user = requireAdmin(request);
    return {
      user,
      totals: getAdminOverview()
    };
  })
  .get("/api/ai-slice-settings", () => ({ ok: true, batchConcurrency: aiSliceBatchConcurrency }))
  .get("/api/projects", ({ request }) => {
    const user = requireUser(request);
    return { projects: listProjectCards(user.id) };
  })
  .post("/api/projects", ({ request, body }) => {
    const user = requireUser(request);
    return { project: createProject(user.id, body) };
  }, {
    body: t.Object({
      name: t.Optional(t.String())
    })
  })
  .get("/api/projects/:projectId", ({ request, params }) => getProjectDetail(requireUser(request).id, params.projectId))
  .patch("/api/projects/:projectId", ({ request, params, body }) => ({ project: renameProject(requireUser(request).id, params.projectId, body.name) }), {
    body: t.Object({
      name: t.String()
    })
  })
  .delete("/api/projects/:projectId", ({ request, params }) => {
    deleteProject(requireUser(request).id, params.projectId);
    return { ok: true };
  })
  .post("/api/projects/:projectId/pages", async ({ request, params, body }) => ({ pages: await addPages(requireUser(request).id, params.projectId, body.files) }), {
    body: t.Object({
      files: t.Files({
        type: "image"
      })
    })
  })
  .patch("/api/projects/:projectId/pages/order", ({ request, params, body }) => reorderPages(requireUser(request).id, params.projectId, body.pageIds), {
    body: t.Object({
      pageIds: t.Array(t.String())
    })
  })
  .patch("/api/projects/:projectId/pages/:pageId", ({ request, params, body }) => ({ page: renamePage(requireUser(request).id, params.projectId, params.pageId, body.displayName) }), {
    body: t.Object({
      displayName: t.String()
    })
  })
  .post("/api/projects/:projectId/pages/:pageId/replace", async ({ request, params, body }) => replacePage(requireUser(request).id, params.projectId, params.pageId, body.file), {
    body: t.Object({
      file: t.File({
        type: "image"
      })
    })
  })
  .delete("/api/projects/:projectId/pages/:pageId", ({ request, params }) => deletePage(requireUser(request).id, params.projectId, params.pageId))
  .post("/api/projects/:projectId/pages/:pageId/ai-boxes", async ({ request, params }) => generateAiSliceBoxes(requireUser(request).id, params.projectId, params.pageId))
  .get("/api/projects/:projectId/pages/:pageId/source", ({ request, params }) => {
    const filePath = getPageOriginalPath(requireUser(request).id, params.projectId, params.pageId);
    return new Response(Bun.file(filePath), {
      headers: {
        "content-type": "image/png",
        "cache-control": "no-store"
      }
    });
  })
  .put("/api/projects/:projectId/slices", ({ request, params, body }) => ({ ok: true, project: saveSlices(requireUser(request).id, params.projectId, body as SaveSlicesRequest) }))
  .get("/api/projects/:projectId/slices/:sliceId/preview.png", async ({ request, params }) => {
    const { originalPath, slice } = getSliceForPreview(requireUser(request).id, params.projectId, params.sliceId);
    const png = await cropSliceToPng(fs.readFileSync(originalPath), slice);
    const body = new Uint8Array(png);
    return new Response(body, {
      headers: {
        "content-type": "image/png",
        "cache-control": "no-store"
      }
    });
  })
  .post("/api/projects/:projectId/export-assets", async ({ request, params }) => exportAssets(requireUser(request).id, params.projectId))
  .get("/api/projects/:projectId/assets.zip", ({ request, params }) => {
    const user = requireUser(request);
    assertProjectExists(user.id, params.projectId);
    const zipPath = getAssetsZipPath(params.projectId);
    if (!fs.existsSync(zipPath)) throw httpError(404, "assets.zip has not been generated");
    return new Response(Bun.file(zipPath), {
      headers: {
        "content-type": "application/zip",
        "content-disposition": `attachment; filename="${params.projectId}-assets.zip"`
      }
    });
  })
  .post("/api/projects/:projectId/export-project", async ({ request, params }) => exportPencilProject(requireUser(request).id, params.projectId))
  .post("/api/projects/:projectId/pages/:pageId/export-project", async ({ request, params }) => exportPencilProjectPage(requireUser(request).id, params.projectId, params.pageId))
  .get("/api/projects/:projectId/pages/:pageId/project.zip", ({ request, params }) => {
    const user = requireUser(request);
    assertProjectExists(user.id, params.projectId);
    const zipPath = getProjectPageZipPath(params.projectId, params.pageId);
    if (!fs.existsSync(zipPath)) throw httpError(404, "page project.zip has not been generated");
    return new Response(Bun.file(zipPath), {
      headers: {
        "content-type": "application/zip",
        "content-disposition": `attachment; filename="${params.projectId}-${params.pageId}-project.zip"`
      }
    });
  })
  .get("/api/projects/:projectId/project.zip", ({ request, params }) => {
    const user = requireUser(request);
    assertProjectExists(user.id, params.projectId);
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
