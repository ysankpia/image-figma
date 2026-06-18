import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const root = fs.mkdtempSync(path.join(os.tmpdir(), "slice-db-migration-smoke-"));

process.env.SLICE_STUDIO_LOAD_LOCAL_ENV = "false";
process.env.SLICE_STUDIO_STORAGE_ROOT = root;
process.env.SLICE_STUDIO_LOCAL_OWNER_EMAIL = "owner@example.test";
process.env.SLICE_STUDIO_LOCAL_OWNER_NAME = "Owner";
process.env.SLICE_STUDIO_LOCAL_OWNER_PASSWORD = "owner-password";

try {
  const dbModule = await import("../server/db");
  const { schemaMigrations } = await import("../server/db-migrations");
  const createdAt = "2026-06-17T00:00:00.000Z";

  dbModule.db.exec(`
    CREATE TABLE projects (
      id TEXT PRIMARY KEY,
      name TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      page_count INTEGER NOT NULL DEFAULT 0,
      slice_count INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE users (
      id TEXT PRIMARY KEY,
      email TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE sessions (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      token_hash TEXT NOT NULL UNIQUE,
      expires_at TEXT NOT NULL,
      created_at TEXT NOT NULL
    );

    CREATE TABLE usage_events (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      project_id TEXT,
      action TEXT NOT NULL,
      units INTEGER NOT NULL DEFAULT 1,
      metadata_json TEXT NOT NULL DEFAULT '{}',
      created_at TEXT NOT NULL
    );

    CREATE TABLE plans (
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

    CREATE TABLE entitlements (
      user_id TEXT PRIMARY KEY,
      plan_id TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'free',
      ai_calls_remaining INTEGER NOT NULL,
      exports_remaining INTEGER NOT NULL,
      storage_mb INTEGER NOT NULL,
      renews_at TEXT,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE payment_orders (
      id TEXT PRIMARY KEY,
      user_id TEXT NOT NULL,
      provider TEXT NOT NULL,
      provider_order_id TEXT,
      plan_id TEXT NOT NULL,
      amount_cents INTEGER NOT NULL,
      currency TEXT NOT NULL DEFAULT 'CNY',
      status TEXT NOT NULL DEFAULT 'pending',
      checkout_url TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );

    CREATE TABLE payment_events (
      id TEXT PRIMARY KEY,
      order_id TEXT,
      provider TEXT NOT NULL,
      provider_event_id TEXT NOT NULL,
      verified INTEGER NOT NULL DEFAULT 0,
      payload_json TEXT NOT NULL,
      received_at TEXT NOT NULL
    );

    CREATE TABLE pages (
      id TEXT NOT NULL,
      project_id TEXT NOT NULL,
      page_index INTEGER NOT NULL,
      original_name TEXT NOT NULL,
      original_path TEXT NOT NULL,
      width INTEGER NOT NULL,
      height INTEGER NOT NULL,
      created_at TEXT NOT NULL,
      PRIMARY KEY (project_id, id),
      FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );

    CREATE TABLE slices (
      id TEXT NOT NULL,
      project_id TEXT NOT NULL,
      page_id TEXT NOT NULL,
      slice_index INTEGER NOT NULL,
      name TEXT NOT NULL,
      kind TEXT NOT NULL CHECK (kind IN ('image', 'icon')),
      cut_mode TEXT NOT NULL DEFAULT 'rect' CHECK (cut_mode IN ('rect', 'shape')),
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

  dbModule.db.query(`
    INSERT INTO users (id, email, password_hash, role, created_at, updated_at)
    VALUES (?, ?, ?, 'user', ?, ?)
  `).run("user_1", "legacy@example.test", "legacy-hash", createdAt, createdAt);
  dbModule.db.query(`
    INSERT INTO sessions (id, user_id, token_hash, expires_at, created_at)
    VALUES (?, ?, ?, ?, ?)
  `).run("session_1", "user_1", "token-hash", createdAt, createdAt);
  dbModule.db.query(`
    INSERT INTO projects (id, name, created_at, updated_at, page_count, slice_count)
    VALUES (?, ?, ?, ?, 1, 1)
  `).run("project_1", "Legacy project", createdAt, createdAt);
  dbModule.db.query(`
    INSERT INTO pages (id, project_id, page_index, original_name, original_path, width, height, created_at)
    VALUES (?, ?, 1, ?, ?, 1200, 800, ?)
  `).run("page_1", "project_1", "P1.png", "projects/project_1/originals/page_1.png", createdAt);
  dbModule.db.query(`
    INSERT INTO slices (id, project_id, page_id, slice_index, name, kind, cut_mode, x, y, width, height, created_at, updated_at)
    VALUES (?, ?, ?, 1, ?, 'icon', 'shape', 10, 20, 30, 40, ?, ?)
  `).run("slice_1", "project_1", "page_1", "CTA", createdAt, createdAt);
  dbModule.db.query(`
    INSERT INTO plans (id, name, monthly_ai_calls, monthly_exports, storage_mb, price_cents, currency, active, created_at)
    VALUES ('free', 'Free', 20, 20, 512, 0, 'CNY', 1, ?)
  `).run(createdAt);
  dbModule.db.query(`
    INSERT INTO usage_events (id, user_id, project_id, action, units, metadata_json, created_at)
    VALUES (?, ?, ?, ?, 2, ?, ?)
  `).run("usage_1", "user_1", "project_1", "ai.boxes", "{\"pageId\":\"page_1\"}", createdAt);
  dbModule.db.query(`
    INSERT INTO entitlements (user_id, plan_id, status, ai_calls_remaining, exports_remaining, storage_mb, renews_at, updated_at)
    VALUES (?, 'free', 'free', 20, 20, 512, NULL, ?)
  `).run("user_1", createdAt);
  dbModule.db.query(`
    INSERT INTO payment_orders (id, user_id, provider, provider_order_id, plan_id, amount_cents, currency, status, checkout_url, created_at, updated_at)
    VALUES (?, ?, 'legacy_provider', ?, 'free', 0, 'CNY', 'pending', ?, ?, ?)
  `).run("order_1", "user_1", "provider_1", "https://pay.example.test/order_1", createdAt, createdAt);
  dbModule.db.query(`
    INSERT INTO payment_events (id, order_id, provider, provider_event_id, verified, payload_json, received_at)
    VALUES (?, ?, 'legacy_provider', ?, 1, ?, ?)
  `).run("payment_event_1", "order_1", "provider_evt_1", "{\"trade_status\":\"TRADE_SUCCESS\"}", createdAt);

  dbModule.initDatabase();

  const migrationIds = dbModule.db
    .query<{ id: string }, []>("SELECT id FROM schema_migrations ORDER BY id")
    .all()
    .map((row) => row.id);
  const session = dbModule.db
    .query<{ last_seen_at: string }, []>("SELECT last_seen_at FROM sessions WHERE id = 'session_1'")
    .get();
  const user = dbModule.db
    .query<{ name: string; status: string }, []>("SELECT name, status FROM users WHERE id = 'user_1'")
    .get();
  const project = dbModule.db
    .query<{ user_id: string | null }, []>("SELECT user_id FROM projects WHERE id = 'project_1'")
    .get();
  const page = dbModule.db
    .query<{ display_name: string }, []>("SELECT display_name FROM pages WHERE id = 'page_1'")
    .get();
  const slice = dbModule.db
    .query<{ kind: string; cut_mode: string }, []>("SELECT kind, cut_mode FROM slices WHERE id = 'slice_1'")
    .get();

  assertEqual(migrationIds, schemaMigrations.map((migration) => migration.id), "schema migrations should be fully recorded");
  assert(session?.last_seen_at === createdAt, "legacy sessions should backfill last_seen_at");
  assertEqual(user, { name: "User", status: "active" }, "legacy users should receive current auth profile columns");
  assert(project && "user_id" in project, "legacy projects should receive user_id column");
  assertEqual(page, { display_name: "" }, "legacy pages should receive display_name column");
  assertEqual(slice, { kind: "image", cut_mode: "subject" }, "legacy slices should be normalized");
  for (const table of ["usage_events", "plans", "entitlements", "payment_orders", "payment_events"]) {
    assert(!tableExists(dbModule.db, table), `${table} should be dropped by user-only cleanup migration`);
  }

  console.log("db-migration smoke passed");
  dbModule.db.close(false);
} finally {
  fs.rmSync(root, { recursive: true, force: true });
}

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

function assertEqual(actual: unknown, expected: unknown, message: string): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${message}\nactual: ${JSON.stringify(actual)}\nexpected: ${JSON.stringify(expected)}`);
  }
}

function tableExists(db: typeof import("../server/db").db, tableName: string): boolean {
  return Boolean(db.query<{ name: string }, [string]>(
    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?"
  ).get(tableName));
}
