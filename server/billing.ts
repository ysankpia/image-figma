import type { CurrentUser } from "./auth";
import { db, type EntitlementRow, type PlanRow } from "./db";
import { freeProjectLimit, maxPagesPerProject, paidProjectLimit } from "./config";
import { httpError } from "./errors";
import { randomHex } from "./utils";
import { storage } from "./storage";
import { createXPayOrder, isXPaySuccessStatus, verifyXPayNotify, type XPayNotify } from "./xpay";

export type UsageEventType =
  | "project.create"
  | "page.upload"
  | "ai.boxes"
  | "export.assets"
  | "export.project"
  | "export.project_page";

export type EntitlementSummary = {
  plan: PlanRow;
  entitlement: EntitlementRow;
};

export type AdminUserRecord = {
  id: string;
  email: string;
  name: string;
  role: "user" | "admin";
  status: "active" | "suspended";
  created_at: string;
  updated_at: string;
  plan_id: string | null;
  entitlement_status: EntitlementRow["status"] | null;
  ai_calls_remaining: number | null;
  exports_remaining: number | null;
  storage_mb: number | null;
  renews_at: string | null;
  project_count: number;
  page_count: number;
  storage_bytes: number;
};

export function getEntitlementSummary(userId: string): EntitlementSummary {
  const entitlement = db.query<EntitlementRow, [string]>("SELECT * FROM entitlements WHERE user_id = ?").get(userId);
  if (!entitlement) throw httpError(500, "Entitlement missing");
  const plan = db.query<PlanRow, [string]>("SELECT * FROM plans WHERE id = ?").get(entitlement.plan_id);
  if (!plan) throw httpError(500, "Plan missing");
  return { plan, entitlement };
}

export function listPlans(): PlanRow[] {
  return db.query<PlanRow, []>("SELECT * FROM plans WHERE active = 1 ORDER BY price_cents ASC").all();
}

export function listUsageEvents(userId: string, limit = 25) {
  return db.query<{
    id: string;
    project_id: string | null;
    event_type: string;
    quantity: number;
    metadata_json: string;
    created_at: string;
  }, [string, number]>(`
    SELECT id, project_id, event_type, quantity, metadata_json, created_at
    FROM usage_events
    WHERE user_id = ?
    ORDER BY created_at DESC
    LIMIT ?
  `).all(userId, Math.max(1, Math.min(100, Math.floor(limit))));
}

export function getAccountUsage(userId: string): {
  projectCount: number;
  pageCount: number;
  storageBytes: number;
} {
  const projectCount = Number(db.query<{ count: number }, [string]>("SELECT COUNT(*) AS count FROM projects WHERE user_id = ?").get(userId)?.count || 0);
  const pageCount = Number(db.query<{ count: number }, [string]>(`
    SELECT COUNT(*) AS count
    FROM pages p
    INNER JOIN projects pr ON pr.id = p.project_id
    WHERE pr.user_id = ?
  `).get(userId)?.count || 0);
  return {
    projectCount,
    pageCount,
    storageBytes: getUserStorageBytes(userId)
  };
}

export function recordUsageEvent(input: {
  userId: string;
  projectId?: string | null;
  eventType: UsageEventType;
  quantity?: number;
  metadata?: Record<string, unknown>;
}): void {
  db.query(`
    INSERT INTO usage_events (id, user_id, project_id, event_type, quantity, metadata_json, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(
    `usage_${randomHex(8)}`,
    input.userId,
    input.projectId || null,
    input.eventType,
    input.quantity ?? 1,
    JSON.stringify(input.metadata || {}),
    new Date().toISOString()
  );
}

export function consumeAiCall(userId: string, projectId: string, metadata: Record<string, unknown> = {}): void {
  const current = getEntitlementSummary(userId).entitlement;
  if (!["free", "trial", "active", "manual_grant"].includes(current.status)) {
    throw httpError(402, "Current plan does not allow AI usage");
  }
  if (current.ai_calls_remaining <= 0) throw httpError(402, "AI call quota exhausted");
  db.query("UPDATE entitlements SET ai_calls_remaining = ai_calls_remaining - 1, updated_at = ? WHERE user_id = ?").run(new Date().toISOString(), userId);
  recordUsageEvent({ userId, projectId, eventType: "ai.boxes", metadata });
}

export function consumeExport(userId: string, projectId: string, eventType: Extract<UsageEventType, "export.assets" | "export.project" | "export.project_page">, metadata: Record<string, unknown> = {}): void {
  const current = getEntitlementSummary(userId).entitlement;
  if (!["free", "trial", "active", "manual_grant"].includes(current.status)) {
    throw httpError(402, "Current plan does not allow exports");
  }
  if (current.exports_remaining <= 0) throw httpError(402, "Export quota exhausted");
  db.query("UPDATE entitlements SET exports_remaining = exports_remaining - 1, updated_at = ? WHERE user_id = ?").run(new Date().toISOString(), userId);
  recordUsageEvent({ userId, projectId, eventType, metadata });
}

export function assertCanCreateProject(userId: string): void {
  const { entitlement } = getEntitlementSummary(userId);
  if (!["free", "trial", "active", "manual_grant"].includes(entitlement.status)) {
    throw httpError(402, "Current plan does not allow new projects");
  }
  const limit = entitlement.status === "active" || entitlement.status === "manual_grant" ? paidProjectLimit : freeProjectLimit;
  const count = Number(db.query<{ count: number }, [string]>("SELECT COUNT(*) AS count FROM projects WHERE user_id = ?").get(userId)?.count || 0);
  if (count >= limit) throw httpError(402, `Project quota exhausted (${limit})`);
}

export function assertCanAddPages(input: {
  userId: string;
  projectId: string;
  incomingPageCount: number;
  incomingBytes: number;
}): void {
  const { entitlement } = getEntitlementSummary(input.userId);
  if (!["free", "trial", "active", "manual_grant"].includes(entitlement.status)) {
    throw httpError(402, "Current plan does not allow uploads");
  }
  const existingPageCount = Number(db.query<{ count: number }, [string]>("SELECT COUNT(*) AS count FROM pages WHERE project_id = ?").get(input.projectId)?.count || 0);
  if (existingPageCount + input.incomingPageCount > maxPagesPerProject) {
    throw httpError(402, `Project page quota exhausted (${maxPagesPerProject})`);
  }
  const usedBytes = getUserStorageBytes(input.userId);
  const limitBytes = entitlement.storage_mb * 1024 * 1024;
  if (usedBytes + input.incomingBytes > limitBytes) {
    throw httpError(402, `Storage quota exhausted (${entitlement.storage_mb}MB)`);
  }
}

export function assertCanReplacePage(input: {
  userId: string;
  projectId: string;
  currentBytes: number;
  incomingBytes: number;
}): void {
  const { entitlement } = getEntitlementSummary(input.userId);
  if (!["free", "trial", "active", "manual_grant"].includes(entitlement.status)) {
    throw httpError(402, "Current plan does not allow uploads");
  }
  const usedBytes = getUserStorageBytes(input.userId);
  const projectedBytes = Math.max(0, usedBytes - input.currentBytes) + input.incomingBytes;
  if (projectedBytes > entitlement.storage_mb * 1024 * 1024) {
    throw httpError(402, `Storage quota exhausted (${entitlement.storage_mb}MB)`);
  }
}

export function getUserStorageBytes(userId: string): number {
  const rows = db.query<{ original_path: string }, [string]>(`
    SELECT p.original_path
    FROM pages p
    INNER JOIN projects pr ON pr.id = p.project_id
    WHERE pr.user_id = ?
  `).all(userId);
  let total = 0;
  for (const row of rows) {
    total += storageFileSize(row.original_path);
  }
  return total;
}

export function createPaymentOrder(userId: string, planId: string, provider = "xpay") {
  const plan = db.query<PlanRow, [string]>("SELECT * FROM plans WHERE id = ? AND active = 1").get(planId);
  if (!plan) throw httpError(404, "Plan not found");
  if (plan.price_cents <= 0) throw httpError(400, "Free plan does not require payment");
  const now = new Date().toISOString();
  const id = `order_${randomHex(10)}`;
  let checkoutUrl: string | null = null;
  let providerOrderId: string | null = null;
  if (provider === "xpay") {
    const xpay = createXPayOrder({
      outTradeNo: id,
      name: plan.name,
      money: plan.price_cents / 100,
      type: "alipay"
    });
    if (xpay) {
      checkoutUrl = `${xpay.payUrl}?${new URLSearchParams(xpay.params).toString()}`;
      providerOrderId = id;
    }
  }
  db.query(`
    INSERT INTO payment_orders (id, user_id, provider, provider_order_id, plan_id, amount_cents, currency, status, checkout_url, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
  `).run(id, userId, provider, providerOrderId, plan.id, plan.price_cents, plan.currency, checkoutUrl, now, now);
  return {
    id,
    provider,
    planId: plan.id,
    amountCents: plan.price_cents,
    currency: plan.currency,
    status: "pending" as const,
    checkoutUrl,
    message: checkoutUrl ? "XPay checkout URL generated." : "XPay provider adapter is reserved; webhook fulfillment is not enabled yet."
  };
}

export function handlePaymentWebhook(input: { provider: string; body: XPayNotify }): {
  accepted: boolean;
  orderId: string;
  status: string;
  signatureValid: boolean;
} {
  const orderId = input.body.out_trade_no;
  const order = db.query<{
    id: string;
    user_id: string;
    provider: string;
    provider_order_id: string | null;
    plan_id: string;
    amount_cents: number;
    currency: string;
    status: string;
    checkout_url: string | null;
    created_at: string;
    updated_at: string;
  }, [string]>("SELECT * FROM payment_orders WHERE id = ?").get(orderId);
  if (!order) throw httpError(404, "Payment order not found");
  if (order.provider !== input.provider) throw httpError(400, "Payment provider mismatch");

  const signatureValid = input.provider === "xpay" ? verifyXPayNotify(input.body) : false;
  db.query(`
    INSERT INTO payment_events (id, order_id, provider, event_type, signature_valid, payload_json, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(
    `payment_event_${randomHex(8)}`,
    order.id,
    input.provider,
    input.body.trade_status,
    signatureValid ? 1 : 0,
    JSON.stringify(input.body),
    new Date().toISOString()
  );

  if (!signatureValid) {
    return { accepted: false, orderId: order.id, status: order.status, signatureValid };
  }
  if (!isXPaySuccessStatus(input.body.trade_status)) {
    return { accepted: true, orderId: order.id, status: order.status, signatureValid };
  }
  if (order.status !== "paid") {
    markOrderPaid(order.id);
  }
  return { accepted: true, orderId: order.id, status: "paid", signatureValid };
}

export function markOrderPaid(orderId: string): void {
  const order = db.query<{ id: string; user_id: string; plan_id: string; status: string }, [string]>("SELECT id, user_id, plan_id, status FROM payment_orders WHERE id = ?").get(orderId);
  if (!order) throw httpError(404, "Payment order not found");
  const now = new Date().toISOString();
  db.query("UPDATE payment_orders SET status = 'paid', updated_at = ? WHERE id = ?").run(now, orderId);
  const plan = db.query<PlanRow, [string]>("SELECT * FROM plans WHERE id = ?").get(order.plan_id);
  if (!plan) throw httpError(500, "Plan missing");
  const existing = db.query<{ user_id: string }, [string]>("SELECT user_id FROM entitlements WHERE user_id = ?").get(order.user_id);
  if (existing) {
    db.query(`
      UPDATE entitlements
      SET plan_id = ?, status = 'active', ai_calls_remaining = ?, exports_remaining = ?, storage_mb = ?, updated_at = ?
      WHERE user_id = ?
    `).run(plan.id, plan.monthly_ai_calls, plan.monthly_exports, plan.storage_mb, now, order.user_id);
  } else {
    db.query(`
      INSERT INTO entitlements (user_id, plan_id, status, ai_calls_remaining, exports_remaining, storage_mb, renews_at, updated_at)
      VALUES (?, ?, 'active', ?, ?, ?, NULL, ?)
    `).run(order.user_id, plan.id, plan.monthly_ai_calls, plan.monthly_exports, plan.storage_mb, now);
  }
}

export function manuallyMarkOrderPaid(orderId: string, admin: CurrentUser): void {
  if (admin.role !== "admin") throw httpError(403, "Admin only");
  const order = db.query<{ id: string; status: string }, [string]>("SELECT id, status FROM payment_orders WHERE id = ?").get(orderId);
  if (!order) throw httpError(404, "Payment order not found");
  if (order.status === "paid") throw httpError(409, "Order is already paid");
  if (order.status === "refunded" || order.status === "closed") {
    throw httpError(409, `Cannot mark ${order.status} order as paid`);
  }
  markOrderPaid(order.id);
  db.query(`
    INSERT INTO payment_events (id, order_id, provider, event_type, signature_valid, payload_json, created_at)
    VALUES (?, ?, 'admin', 'manual_mark_paid', 1, ?, ?)
  `).run(
    `payment_event_${randomHex(8)}`,
    order.id,
    JSON.stringify({
      adminId: admin.id,
      adminEmail: admin.email,
      previousStatus: order.status,
      reason: "admin_manual_repair"
    }),
    new Date().toISOString()
  );
}

export function listPaymentOrders(userId: string, limit = 20) {
  return db.query<{
    id: string;
    provider: string;
    provider_order_id: string | null;
    plan_id: string;
    amount_cents: number;
    currency: string;
    status: string;
    checkout_url: string | null;
    created_at: string;
    updated_at: string;
  }, [string, number]>(`
    SELECT id, provider, provider_order_id, plan_id, amount_cents, currency, status, checkout_url, created_at, updated_at
    FROM payment_orders
    WHERE user_id = ?
    ORDER BY created_at DESC
    LIMIT ?
  `).all(userId, Math.max(1, Math.min(100, Math.floor(limit))));
}

export function listAdminPaymentOrders(limit = 50) {
  return db.query<{
    id: string;
    user_id: string;
    user_email: string;
    provider: string;
    provider_order_id: string | null;
    plan_id: string;
    amount_cents: number;
    currency: string;
    status: string;
    checkout_url: string | null;
    created_at: string;
    updated_at: string;
  }, [number]>(`
    SELECT po.id, po.user_id, u.email AS user_email, po.provider, po.provider_order_id, po.plan_id, po.amount_cents, po.currency, po.status, po.checkout_url, po.created_at, po.updated_at
    FROM payment_orders po
    INNER JOIN users u ON u.id = po.user_id
    ORDER BY po.created_at DESC
    LIMIT ?
  `).all(Math.max(1, Math.min(100, Math.floor(limit))));
}

export function listAdminPaymentEvents(limit = 50) {
  return db.query<{
    id: string;
    order_id: string | null;
    provider: string;
    event_type: string;
    signature_valid: number;
    payload_json: string;
    created_at: string;
  }, [number]>(`
    SELECT id, order_id, provider, event_type, signature_valid, payload_json, created_at
    FROM payment_events
    ORDER BY created_at DESC
    LIMIT ?
  `).all(Math.max(1, Math.min(100, Math.floor(limit))));
}

export function listAdminUsers(limit = 100): AdminUserRecord[] {
  const rows = db.query<{
    id: string;
    email: string;
    name: string;
    role: "user" | "admin";
    status: "active" | "suspended";
    created_at: string;
    updated_at: string;
    plan_id: string | null;
    entitlement_status: EntitlementRow["status"] | null;
    ai_calls_remaining: number | null;
    exports_remaining: number | null;
    storage_mb: number | null;
    renews_at: string | null;
    project_count: number;
    page_count: number;
  }, [number]>(`
    SELECT
      u.id,
      u.email,
      u.name,
      u.role,
      u.status,
      u.created_at,
      u.updated_at,
      e.plan_id,
      e.status AS entitlement_status,
      e.ai_calls_remaining,
      e.exports_remaining,
      e.storage_mb,
      e.renews_at,
      COUNT(DISTINCT pr.id) AS project_count,
      COUNT(DISTINCT p.id) AS page_count
    FROM users u
    LEFT JOIN entitlements e ON e.user_id = u.id
    LEFT JOIN projects pr ON pr.user_id = u.id
    LEFT JOIN pages p ON p.project_id = pr.id
    GROUP BY
      u.id, u.email, u.name, u.role, u.status, u.created_at, u.updated_at,
      e.plan_id, e.status, e.ai_calls_remaining, e.exports_remaining, e.storage_mb, e.renews_at
    ORDER BY u.created_at DESC
    LIMIT ?
  `).all(Math.max(1, Math.min(200, Math.floor(limit))));

  return rows.map((row) => ({
    ...row,
    storage_bytes: getUserStorageBytes(row.id)
  }));
}

export function adminSetUserStatus(userId: string, status: "active" | "suspended", admin: CurrentUser): void {
  if (admin.role !== "admin") throw httpError(403, "Admin only");
  const user = db.query<{ id: string; role: "user" | "admin"; status: "active" | "suspended" }, [string]>(`
    SELECT id, role, status
    FROM users
    WHERE id = ?
  `).get(userId);
  if (!user) throw httpError(404, "User not found");
  if (user.status === status) return;
  if (admin.id === user.id && status === "suspended") {
    throw httpError(409, "Cannot suspend current admin");
  }
  if (user.role === "admin" && status === "suspended") {
    const activeAdminCount = Number(db.query<{ count: number }, []>(`
      SELECT COUNT(*) AS count
      FROM users
      WHERE role = 'admin' AND status = 'active'
    `).get()?.count || 0);
    if (activeAdminCount <= 1) throw httpError(409, "Cannot suspend the last active admin");
  }
  db.query("UPDATE users SET status = ?, updated_at = ? WHERE id = ?").run(status, new Date().toISOString(), userId);
}

export function adminSetUserEntitlement(input: {
  userId: string;
  planId: string;
  status: EntitlementRow["status"];
  admin: CurrentUser;
}): void {
  if (input.admin.role !== "admin") throw httpError(403, "Admin only");
  const user = db.query<{ id: string }, [string]>("SELECT id FROM users WHERE id = ?").get(input.userId);
  if (!user) throw httpError(404, "User not found");
  const plan = db.query<PlanRow, [string]>("SELECT * FROM plans WHERE id = ?").get(input.planId);
  if (!plan) throw httpError(404, "Plan not found");
  const now = new Date().toISOString();
  const existing = db.query<{ user_id: string }, [string]>("SELECT user_id FROM entitlements WHERE user_id = ?").get(input.userId);
  if (existing) {
    db.query(`
      UPDATE entitlements
      SET plan_id = ?, status = ?, ai_calls_remaining = ?, exports_remaining = ?, storage_mb = ?, updated_at = ?
      WHERE user_id = ?
    `).run(input.planId, input.status, plan.monthly_ai_calls, plan.monthly_exports, plan.storage_mb, now, input.userId);
  } else {
    db.query(`
      INSERT INTO entitlements (user_id, plan_id, status, ai_calls_remaining, exports_remaining, storage_mb, renews_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, NULL, ?)
    `).run(input.userId, input.planId, input.status, plan.monthly_ai_calls, plan.monthly_exports, plan.storage_mb, now);
  }
}

export function getAdminOverview() {
  const scalar = (sql: string) => Number(db.query<{ count: number }, []>(sql).get()?.count || 0);
  return {
    users: scalar("SELECT COUNT(*) AS count FROM users"),
    projects: scalar("SELECT COUNT(*) AS count FROM projects"),
    pages: scalar("SELECT COUNT(*) AS count FROM pages"),
    slices: scalar("SELECT COUNT(*) AS count FROM slices"),
    usageEvents: scalar("SELECT COUNT(*) AS count FROM usage_events"),
    paymentOrders: scalar("SELECT COUNT(*) AS count FROM payment_orders"),
    pendingPaymentOrders: scalar("SELECT COUNT(*) AS count FROM payment_orders WHERE status = 'pending'"),
    paidPaymentOrders: scalar("SELECT COUNT(*) AS count FROM payment_orders WHERE status = 'paid'"),
    paymentEvents: scalar("SELECT COUNT(*) AS count FROM payment_events")
  };
}

function storageFileSize(relativePath: string): number {
  try {
    return storage.size(relativePath);
  } catch {
    return 0;
  }
}
