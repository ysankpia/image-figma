import { db, type EntitlementRow, type PlanRow } from "./db";
import { httpError } from "./errors";
import { randomHex } from "./utils";

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
  db.query(`
    INSERT INTO payment_orders (id, user_id, provider, provider_order_id, plan_id, amount_cents, currency, status, checkout_url, created_at, updated_at)
    VALUES (?, ?, ?, NULL, ?, ?, ?, 'pending', NULL, ?, ?)
  `).run(id, userId, provider, plan.id, plan.price_cents, plan.currency, now, now);
  return {
    id,
    provider,
    planId: plan.id,
    amountCents: plan.price_cents,
    currency: plan.currency,
    status: "pending" as const,
    checkoutUrl: null as string | null,
    message: "XPay provider adapter is reserved; webhook fulfillment is not enabled yet."
  };
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
    pendingPaymentOrders: scalar("SELECT COUNT(*) AS count FROM payment_orders WHERE status = 'pending'")
  };
}
