import { Database } from "bun:sqlite";
import fs from "node:fs";
import { databasePath, projectsRoot, storageRoot } from "./config";

fs.mkdirSync(projectsRoot, { recursive: true });
fs.mkdirSync(storageRoot, { recursive: true });

export const db = new Database(databasePath);
db.exec("PRAGMA foreign_keys = ON;");

export function initDatabase(): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS projects (
      id TEXT PRIMARY KEY,
      user_id TEXT,
      name TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      page_count INTEGER NOT NULL DEFAULT 0,
      slice_count INTEGER NOT NULL DEFAULT 0,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS users (
      id TEXT PRIMARY KEY,
      email TEXT NOT NULL UNIQUE,
      name TEXT NOT NULL,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
      status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sessions (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      token_hash TEXT NOT NULL UNIQUE,
      expires_at TEXT NOT NULL,
      created_at TEXT NOT NULL,
      last_seen_at TEXT NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS usage_events (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      project_id TEXT,
      event_type TEXT NOT NULL,
      quantity INTEGER NOT NULL DEFAULT 1,
      metadata_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
      FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS plans (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      monthly_ai_calls INTEGER NOT NULL,
      monthly_exports INTEGER NOT NULL,
      storage_mb INTEGER NOT NULL,
      price_cents INTEGER NOT NULL DEFAULT 0,
      currency TEXT NOT NULL DEFAULT 'CNY',
      active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS entitlements (
      user_id TEXT PRIMARY KEY,
      plan_id TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'free' CHECK (status IN ('free', 'trial', 'active', 'past_due', 'paused', 'canceled', 'expired', 'refunded', 'manual_grant')),
      ai_calls_remaining INTEGER NOT NULL,
      exports_remaining INTEGER NOT NULL,
      storage_mb INTEGER NOT NULL,
      renews_at TEXT,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
      FOREIGN KEY (plan_id) REFERENCES plans(id)
    );

    CREATE TABLE IF NOT EXISTS payment_orders (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      provider TEXT NOT NULL,
      provider_order_id TEXT,
      plan_id TEXT NOT NULL,
      amount_cents INTEGER NOT NULL,
      currency TEXT NOT NULL DEFAULT 'CNY',
      status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'paid', 'failed', 'closed', 'refunded')),
      checkout_url TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
      FOREIGN KEY (plan_id) REFERENCES plans(id)
    );

    CREATE TABLE IF NOT EXISTS payment_events (
      id TEXT PRIMARY KEY,
      order_id TEXT,
      provider TEXT NOT NULL,
      event_type TEXT NOT NULL,
      signature_valid INTEGER NOT NULL DEFAULT 0,
      payload_json TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY (order_id) REFERENCES payment_orders(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS pages (
      id TEXT NOT NULL,
      project_id TEXT NOT NULL,
      page_index INTEGER NOT NULL,
      original_name TEXT NOT NULL,
      display_name TEXT NOT NULL DEFAULT '',
      original_path TEXT NOT NULL,
      width INTEGER NOT NULL,
      height INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      PRIMARY KEY (project_id, id),
      FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS slices (
      id TEXT NOT NULL,
      project_id TEXT NOT NULL,
      page_id TEXT NOT NULL,
      slice_index INTEGER NOT NULL,
      name TEXT NOT NULL,
      kind TEXT NOT NULL CHECK (kind IN ('image')),
      cut_mode TEXT NOT NULL DEFAULT 'rect' CHECK (cut_mode IN ('rect', 'subject', 'card')),
      x INTEGER NOT NULL,
      y INTEGER NOT NULL,
      width INTEGER NOT NULL,
      height INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      PRIMARY KEY (project_id, id),
      FOREIGN KEY (project_id, page_id) REFERENCES pages(project_id, id) ON DELETE CASCADE
    );
  `);
  ensureColumn("projects", "user_id", "TEXT");
  ensureColumn("users", "name", "TEXT NOT NULL DEFAULT 'User'");
  ensureColumn("users", "status", "TEXT NOT NULL DEFAULT 'active'");
  ensureColumn("sessions", "last_seen_at", "TEXT");
  db.query("UPDATE sessions SET last_seen_at = created_at WHERE last_seen_at IS NULL OR last_seen_at = ''").run();
  migrateUsageEventsColumns();
  migratePaymentEventsColumns();
  ensureColumn("pages", "display_name", "TEXT NOT NULL DEFAULT ''");
  ensureColumn("slices", "cut_mode", "TEXT NOT NULL DEFAULT 'rect'");
  migrateCutModeConstraint();
  db.query("UPDATE slices SET kind = 'image' WHERE kind != 'image'").run();
  db.query("UPDATE slices SET cut_mode = 'subject' WHERE cut_mode = 'shape'").run();
  db.query("UPDATE slices SET cut_mode = 'rect' WHERE cut_mode NOT IN ('rect', 'subject', 'card')").run();
  seedDefaultPlans();
}

function ensureColumn(tableName: string, columnName: string, definition: string): void {
  const columns = db.query<{ name: string }, []>(`PRAGMA table_info(${tableName})`).all();
  if (!columns.some((column) => column.name === columnName)) {
    db.exec(`ALTER TABLE ${tableName} ADD COLUMN ${columnName} ${definition}`);
  }
}

function columnExists(tableName: string, columnName: string): boolean {
  return db.query<{ name: string }, []>(`PRAGMA table_info(${tableName})`).all().some((column) => column.name === columnName);
}

function tableSql(tableName: string): string {
  return db.query<{ sql: string | null }, [string]>("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?").get(tableName)?.sql || "";
}

export function transaction<T>(fn: () => T): T {
  db.exec("BEGIN");
  try {
    const result = fn();
    db.exec("COMMIT");
    return result;
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
}

export type ProjectRow = {
  id: string;
  user_id: string | null;
  name: string;
  created_at: string;
  updated_at: string;
  page_count: number;
  slice_count: number;
};

export type PageRow = {
  id: string;
  project_id: string;
  page_index: number;
  original_name: string;
  display_name: string;
  original_path: string;
  width: number;
  height: number;
  created_at: string;
};

export type SliceRow = {
  id: string;
  project_id: string;
  page_id: string;
  slice_index: number;
  name: string;
  kind: "image";
  cut_mode: "rect" | "subject" | "card" | "shape";
  x: number;
  y: number;
  width: number;
  height: number;
  created_at: string;
  updated_at: string;
};

export type UserRow = {
  id: string;
  email: string;
  name: string;
  password_hash: string;
  role: "user" | "admin";
  status: "active" | "suspended";
  created_at: string;
  updated_at: string;
};

export type SessionRow = {
  id: string;
  user_id: string;
  token_hash: string;
  expires_at: string;
  created_at: string;
  last_seen_at: string;
};

export type PlanRow = {
  id: string;
  name: string;
  monthly_ai_calls: number;
  monthly_exports: number;
  storage_mb: number;
  price_cents: number;
  currency: string;
  active: number;
  created_at: string;
};

export type EntitlementRow = {
  user_id: string;
  plan_id: string;
  status: "free" | "trial" | "active" | "past_due" | "paused" | "canceled" | "expired" | "refunded" | "manual_grant";
  ai_calls_remaining: number;
  exports_remaining: number;
  storage_mb: number;
  renews_at: string | null;
  updated_at: string;
};

function migrateCutModeConstraint(): void {
  const sql = tableSql("slices");
  if (sql.includes("'subject'") && sql.includes("'card'") && !sql.includes("'shape'")) return;

  db.exec(`
    CREATE TABLE slices_next (
      id TEXT NOT NULL,
      project_id TEXT NOT NULL,
      page_id TEXT NOT NULL,
      slice_index INTEGER NOT NULL,
      name TEXT NOT NULL,
      kind TEXT NOT NULL CHECK (kind IN ('image')),
      cut_mode TEXT NOT NULL DEFAULT 'rect' CHECK (cut_mode IN ('rect', 'subject', 'card')),
      x INTEGER NOT NULL,
      y INTEGER NOT NULL,
      width INTEGER NOT NULL,
      height INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      PRIMARY KEY (project_id, id),
      FOREIGN KEY (project_id, page_id) REFERENCES pages(project_id, id) ON DELETE CASCADE
    );

    INSERT INTO slices_next (id, project_id, page_id, slice_index, name, kind, cut_mode, x, y, width, height, created_at, updated_at)
    SELECT id, project_id, page_id, slice_index, name, 'image',
      CASE
        WHEN cut_mode = 'shape' THEN 'subject'
        WHEN cut_mode IN ('rect', 'subject', 'card') THEN cut_mode
        ELSE 'rect'
      END,
      x, y, width, height, created_at, updated_at
    FROM slices;

    DROP TABLE slices;
    ALTER TABLE slices_next RENAME TO slices;
  `);
}

function migrateUsageEventsColumns(): void {
  const columns = db.query<{ name: string }, []>("PRAGMA table_info(usage_events)").all().map((column) => column.name);
  const sql = tableSql("usage_events");
  const targetColumns = ["id", "user_id", "project_id", "event_type", "quantity", "metadata_json", "created_at"];
  const needsRebuild =
    targetColumns.some((column) => !columns.includes(column)) ||
    columns.includes("action") ||
    columns.includes("units") ||
    !sql.includes("event_type TEXT NOT NULL") ||
    !sql.includes("quantity INTEGER NOT NULL DEFAULT 1");

  if (!needsRebuild) return;

  const rows = db.query<Record<string, unknown>, []>("SELECT * FROM usage_events").all();
  const now = new Date().toISOString();

  db.exec(`
    DROP TABLE IF EXISTS usage_events_next;
    CREATE TABLE usage_events_next (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      project_id TEXT,
      event_type TEXT NOT NULL,
      quantity INTEGER NOT NULL DEFAULT 1,
      metadata_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
      FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
    );
  `);

  const insert = db.query(`
    INSERT INTO usage_events_next (id, user_id, project_id, event_type, quantity, metadata_json, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);
  for (const row of rows) {
    const userId = stringValue(row.user_id);
    if (!userId) continue;
    insert.run(
      stringValue(row.id) || `usage_${crypto.randomUUID()}`,
      userId,
      stringValue(row.project_id) || null,
      stringValue(row.event_type) || stringValue(row.action) || "unknown",
      numberValue(row.quantity) ?? numberValue(row.units) ?? 1,
      stringValue(row.metadata_json) || "{}",
      stringValue(row.created_at) || now
    );
  }

  db.exec(`
    DROP TABLE usage_events;
    ALTER TABLE usage_events_next RENAME TO usage_events;
  `);
}

function migratePaymentEventsColumns(): void {
  const columns = db.query<{ name: string }, []>("PRAGMA table_info(payment_events)").all().map((column) => column.name);
  const sql = tableSql("payment_events");
  const targetColumns = ["id", "order_id", "provider", "event_type", "signature_valid", "payload_json", "created_at"];
  const needsRebuild =
    targetColumns.some((column) => !columns.includes(column)) ||
    columns.includes("provider_event_id") ||
    columns.includes("received_at") ||
    columns.includes("verified") ||
    !sql.includes("event_type TEXT NOT NULL") ||
    !sql.includes("signature_valid INTEGER NOT NULL DEFAULT 0");

  if (!needsRebuild) return;

  const rows = db.query<Record<string, unknown>, []>("SELECT * FROM payment_events").all();
  const now = new Date().toISOString();

  db.exec(`
    DROP TABLE IF EXISTS payment_events_next;
    CREATE TABLE payment_events_next (
      id TEXT PRIMARY KEY,
      order_id TEXT,
      provider TEXT NOT NULL,
      event_type TEXT NOT NULL,
      signature_valid INTEGER NOT NULL DEFAULT 0,
      payload_json TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY (order_id) REFERENCES payment_orders(id) ON DELETE SET NULL
    );
  `);

  const insert = db.query(`
    INSERT INTO payment_events_next (id, order_id, provider, event_type, signature_valid, payload_json, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);
  for (const row of rows) {
    insert.run(
      stringValue(row.id) || `payment_event_${crypto.randomUUID()}`,
      stringValue(row.order_id) || null,
      stringValue(row.provider) || "unknown",
      stringValue(row.event_type) || stringValue(row.provider_event_id) || "unknown",
      numberValue(row.signature_valid) ?? numberValue(row.verified) ?? 0,
      stringValue(row.payload_json) || "{}",
      stringValue(row.created_at) || stringValue(row.received_at) || now
    );
  }

  db.exec(`
    DROP TABLE payment_events;
    ALTER TABLE payment_events_next RENAME TO payment_events;
  `);
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function numberValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function seedDefaultPlans(): void {
  const existing = Number(db.query<{ count: number }, []>("SELECT COUNT(*) AS count FROM plans").get()?.count || 0);
  if (existing > 0) return;
  const now = new Date().toISOString();
  db.query(`
    INSERT INTO plans (id, name, monthly_ai_calls, monthly_exports, storage_mb, price_cents, currency, active, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
  `).run("free", "Free", 20, 20, 512, 0, "CNY", now);
  db.query(`
    INSERT INTO plans (id, name, monthly_ai_calls, monthly_exports, storage_mb, price_cents, currency, active, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
  `).run("pro", "Pro", 1000, 500, 10240, 9900, "CNY", now);
}
