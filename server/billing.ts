import { db, type EntitlementRow, type PlanRow } from "./db";
import { httpError } from "./errors";
import { randomHex } from "./utils";
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
