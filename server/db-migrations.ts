import type { Database } from "bun:sqlite";

export type SchemaMigration = {
  id: string;
  description: string;
  up: (db: Database) => void;
};

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
    id: "008_drop_billing_payment_tables",
    description: "Remove obsolete billing, payment, entitlement, and usage tables from user-only Slice Studio.",
    up: (db) => {
      db.exec(`
        DROP TABLE IF EXISTS payment_events;
        DROP TABLE IF EXISTS payment_orders;
        DROP TABLE IF EXISTS entitlements;
        DROP TABLE IF EXISTS plans;
        DROP TABLE IF EXISTS usage_events;
      `);
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
