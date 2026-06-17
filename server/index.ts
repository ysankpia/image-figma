import cors from "@elysiajs/cors";
import { Elysia, t } from "elysia";
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
import {
  adminSetUserEntitlement,
  adminSetUserStatus,
  createPaymentOrder,
  getAccountUsage,
  getAdminOverview,
  getEntitlementSummary,
  handlePaymentWebhook,
  listAdminUsers,
  listAdminPaymentEvents,
  listAdminPaymentOrders,
  listPaymentOrders,
  listPlans,
  listUsageEvents,
  manuallyMarkOrderPaid
} from "./billing";
import { HttpError, httpError } from "./errors";
import { exportAssets } from "./exporter";
import { exportPencilProject, exportPencilProjectPage } from "./pencil-exporter";
import { cropSliceToPng } from "./shape-cutout";
import { generateAiSliceBoxes } from "./ai-slice-boxes";
import { aiSliceBatchConcurrency } from "./config";
import { storage } from "./storage";
import { resolveSignedStorageDownload } from "./storage-download";
import {
  addPages,
  createProject,
  deletePage,
  deleteProject,
  getPageOriginalKey,
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
  .get("/api/storage-download", ({ query }) => {
    const download = resolveSignedStorageDownload(query.token);
    return storage.response(download.key, download.response);
  }, {
    query: t.Object({
      token: t.String({ minLength: 1 })
    })
  })
  .get("/api/auth/session", ({ request }) => ({ user: getCurrentUser(request) }))
  .get("/api/me", ({ request }) => {
    const user = requireUser(request);
    return {
      user,
      entitlement: getEntitlementSummary(user.id),
      accountUsage: getAccountUsage(user.id),
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
  .post("/api/billing/webhooks/xpay", ({ body }) => {
    const result = handlePaymentWebhook({ provider: "xpay", body });
    return result.accepted ? "success" : "fail";
  }, {
    body: t.Object({
      pid: t.String(),
      trade_no: t.String(),
      out_trade_no: t.String(),
      type: t.String(),
      name: t.String(),
      money: t.String(),
      trade_status: t.String(),
      sign: t.String(),
      sign_type: t.String()
    })
  })
  .get("/api/admin/overview", ({ request }) => {
    const user = requireAdmin(request);
    return {
      user,
      totals: getAdminOverview()
    };
  })
  .get("/api/admin/payments", ({ request }) => {
    requireAdmin(request);
    return {
      orders: listAdminPaymentOrders(50),
      events: listAdminPaymentEvents(50)
    };
  })
  .get("/api/admin/users", ({ request }) => {
    requireAdmin(request);
    return {
      users: listAdminUsers(100),
      plans: listPlans()
    };
  })
  .patch("/api/admin/users/:userId/status", ({ request, params, body }) => {
    const admin = requireAdmin(request);
    adminSetUserStatus(params.userId, body.status, admin);
    return { ok: true };
  }, {
    body: t.Object({
      status: t.Union([t.Literal("active"), t.Literal("suspended")])
    })
  })
  .patch("/api/admin/users/:userId/entitlement", ({ request, params, body }) => {
    const admin = requireAdmin(request);
    adminSetUserEntitlement({
      userId: params.userId,
      planId: body.planId,
      status: body.status,
      admin
    });
    return { ok: true };
  }, {
    body: t.Object({
      planId: t.String(),
      status: t.Union([
        t.Literal("free"),
        t.Literal("trial"),
        t.Literal("active"),
        t.Literal("past_due"),
        t.Literal("paused"),
        t.Literal("canceled"),
        t.Literal("expired"),
        t.Literal("refunded"),
        t.Literal("manual_grant")
      ])
    })
  })
  .post("/api/admin/payment-orders/:orderId/mark-paid", ({ request, params }) => {
    const admin = requireAdmin(request);
    manuallyMarkOrderPaid(params.orderId, admin);
    return { ok: true };
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
    const user = requireUser(request);
    getPageOriginalPath(user.id, params.projectId, params.pageId);
    return storage.response(getPageOriginalKey(user.id, params.projectId, params.pageId), {
      contentType: "image/png",
      cacheControl: "no-store",
      notFoundMessage: "Original image not found"
    });
  })
  .put("/api/projects/:projectId/slices", ({ request, params, body }) => ({ ok: true, project: saveSlices(requireUser(request).id, params.projectId, body as SaveSlicesRequest) }))
  .get("/api/projects/:projectId/slices/:sliceId/preview.png", async ({ request, params }) => {
    const { originalKey, slice } = getSliceForPreview(requireUser(request).id, params.projectId, params.sliceId);
    const png = await cropSliceToPng(storage.read(originalKey, "Original image not found"), slice);
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
    return storage.response(storage.firstExistingKey(storage.assetsZipKeyVariants(user.id, params.projectId), "assets.zip has not been generated"), {
      contentType: "application/zip",
      contentDisposition: `attachment; filename="${params.projectId}-assets.zip"`,
      notFoundMessage: "assets.zip has not been generated"
    });
  })
  .post("/api/projects/:projectId/export-project", async ({ request, params }) => exportPencilProject(requireUser(request).id, params.projectId))
  .post("/api/projects/:projectId/pages/:pageId/export-project", async ({ request, params }) => exportPencilProjectPage(requireUser(request).id, params.projectId, params.pageId))
  .get("/api/projects/:projectId/pages/:pageId/project.zip", ({ request, params }) => {
    const user = requireUser(request);
    assertProjectExists(user.id, params.projectId);
    return storage.response(storage.firstExistingKey(storage.projectPageZipKeyVariants(user.id, params.projectId, params.pageId), "page project.zip has not been generated"), {
      contentType: "application/zip",
      contentDisposition: `attachment; filename="${params.projectId}-${params.pageId}-project.zip"`,
      notFoundMessage: "page project.zip has not been generated"
    });
  })
  .get("/api/projects/:projectId/project.zip", ({ request, params }) => {
    const user = requireUser(request);
    assertProjectExists(user.id, params.projectId);
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
