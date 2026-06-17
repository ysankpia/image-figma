import crypto from "node:crypto";
import type { Database } from "bun:sqlite";

export type SchemaMigration = {
  id: string;
  description: string;
  up: (db: Database) => void;
};

const defaultPlans = [
  {
    id: "free",
    name: "Free",
    monthlyAiCalls: 20,
    monthlyExports: 20,
    storageMb: 512,
    priceCents: 0,
    currency: "CNY"
  },
  {
    id: "pro",
    name: "Pro",
    monthlyAiCalls: 1000,
    monthlyExports: 500,
    storageMb: 10240,
    priceCents: 9900,
    currency: "CNY"
  }
] as const;

export const schemaMigrations: SchemaMigration[] = [
  {
    id: "001_base_current_schema",
    description: "Create the current Slice Studio tables when they do not exist yet.",
    up: (db) => {
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
    }
  },
  {
    id: "002_projects_user_ownership",
    description: "Add the legacy projects.user_id column before ownership backfill.",
    up: (db) => {
      ensureColumn(db, "projects", "user_id", "TEXT");
    }
  },
  {
    id: "003_auth_profile_columns",
    description: "Repair legacy auth tables so current auth/session code has the columns it expects.",
    up: (db) => {
      ensureColumn(db, "users", "name", "TEXT NOT NULL DEFAULT 'User'");
      ensureColumn(db, "users", "status", "TEXT NOT NULL DEFAULT 'active'");
      ensureColumn(db, "sessions", "last_seen_at", "TEXT");
      db.query("UPDATE sessions SET last_seen_at = created_at WHERE last_seen_at IS NULL OR last_seen_at = ''").run();
    }
  },
  {
    id: "004_usage_events_contract",
    description: "Rebuild legacy usage_events rows into the explicit event_type/quantity contract.",
    up: (db) => {
      migrateUsageEventsColumns(db);
    }
  },
  {
    id: "005_payment_events_contract",
    description: "Rebuild legacy payment_events rows into the explicit webhook event contract.",
    up: (db) => {
      migratePaymentEventsColumns(db);
    }
  },
  {
    id: "006_pages_and_slices_contract",
    description: "Repair page display names plus the modern slice cut_mode contract.",
    up: (db) => {
      ensureColumn(db, "pages", "display_name", "TEXT NOT NULL DEFAULT ''");
      ensureColumn(db, "slices", "cut_mode", "TEXT NOT NULL DEFAULT 'rect'");
      migrateCutModeConstraint(db);
      db.query("UPDATE slices SET kind = 'image' WHERE kind != 'image'").run();
      db.query("UPDATE slices SET cut_mode = 'subject' WHERE cut_mode = 'shape'").run();
      db.query("UPDATE slices SET cut_mode = 'rect' WHERE cut_mode NOT IN ('rect', 'subject', 'card')").run();
    }
  },
  {
    id: "007_seed_default_plans",
    description: "Ensure the built-in free and pro plans exist for auth, quota, and billing flows.",
    up: (db) => {
      const now = new Date().toISOString();
      const insert = db.query(`
        INSERT OR IGNORE INTO plans (id, name, monthly_ai_calls, monthly_exports, storage_mb, price_cents, currency, active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
      `);
      for (const plan of defaultPlans) {
        insert.run(
          plan.id,
          plan.name,
          plan.monthlyAiCalls,
          plan.monthlyExports,
          plan.storageMb,
          plan.priceCents,
          plan.currency,
          now
        );
      }
    }
  }
];

export function applySchemaMigrations(db: Database): void {
  ensureSchemaMigrationsTable(db);
  const applied = new Set(
    db.query<{ id: string }, []>("SELECT id FROM schema_migrations ORDER BY id").all().map((row) => row.id)
  );
  for (const migration of schemaMigrations) {
    if (applied.has(migration.id)) continue;
    runMigration(db, migration);
  }
}

function ensureSchemaMigrationsTable(db: Database): void {
  db.exec(`
    CREATE TABLE IF NOT EXISTS schema_migrations (
      id TEXT PRIMARY KEY,
      description TEXT NOT NULL,
      applied_at TEXT NOT NULL
    );
  `);
}

function runMigration(db: Database, migration: SchemaMigration): void {
  db.exec("BEGIN IMMEDIATE");
  try {
    migration.up(db);
    db.query(`
      INSERT INTO schema_migrations (id, description, applied_at)
      VALUES (?, ?, ?)
    `).run(migration.id, migration.description, new Date().toISOString());
    db.exec("COMMIT");
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
}

function ensureColumn(db: Database, tableName: string, columnName: string, definition: string): void {
  const columns = db.query<{ name: string }, []>(`PRAGMA table_info(${tableName})`).all();
  if (!columns.some((column) => column.name === columnName)) {
    db.exec(`ALTER TABLE ${tableName} ADD COLUMN ${columnName} ${definition}`);
  }
}

function tableSql(db: Database, tableName: string): string {
  return db.query<{ sql: string | null }, [string]>("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?").get(tableName)?.sql || "";
}

function migrateCutModeConstraint(db: Database): void {
  const sql = tableSql(db, "slices");
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

function migrateUsageEventsColumns(db: Database): void {
  const columns = db.query<{ name: string }, []>("PRAGMA table_info(usage_events)").all().map((column) => column.name);
  const sql = tableSql(db, "usage_events");
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

function migratePaymentEventsColumns(db: Database): void {
  const columns = db.query<{ name: string }, []>("PRAGMA table_info(payment_events)").all().map((column) => column.name);
  const sql = tableSql(db, "payment_events");
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
