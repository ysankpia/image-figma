export type SqlRow = Record<string, unknown>;

export interface SchemaDatabase {
  provider: "sqlite" | "postgres";
  exec(sql: string): Promise<void>;
  all<Row extends SqlRow>(sql: string, params?: readonly unknown[]): Promise<Row[]>;
  get<Row extends SqlRow>(sql: string, params?: readonly unknown[]): Promise<Row | undefined>;
  run(sql: string, params?: readonly unknown[]): Promise<{ changes: number }>;
  transaction<T>(fn: () => Promise<T>): Promise<T>;
  tableExists(tableName: string): Promise<boolean>;
  columnExists(tableName: string, columnName: string): Promise<boolean>;
  tableSql(tableName: string): Promise<string>;
}

export type SchemaMigration = {
  id: string;
  description: string;
  up: (db: SchemaDatabase) => Promise<void>;
};

export const schemaMigrations: SchemaMigration[] = [
  {
    id: "001_base_current_schema",
    description: "Create the current Slice Studio tables when they do not exist yet.",
    up: async (db) => {
      await db.exec(baseSchemaSql(db.provider));
    }
  },
  {
    id: "002_projects_user_ownership",
    description: "Add the legacy projects.user_id column before ownership backfill.",
    up: async (db) => {
      await ensureColumn(db, "projects", "user_id", "TEXT");
    }
  },
  {
    id: "003_auth_profile_columns",
    description: "Repair legacy auth tables so current auth/session code has the columns it expects.",
    up: async (db) => {
      await ensureColumn(db, "users", "name", "TEXT NOT NULL DEFAULT 'User'");
      await ensureColumn(db, "users", "status", "TEXT NOT NULL DEFAULT 'active'");
      await ensureColumn(db, "sessions", "last_seen_at", "TEXT");
      await db.run("UPDATE sessions SET last_seen_at = created_at WHERE last_seen_at IS NULL OR last_seen_at = ''");
    }
  },
  {
    id: "006_pages_and_slices_contract",
    description: "Repair page display names plus the modern slice cut_mode contract.",
    up: async (db) => {
      await ensureColumn(db, "pages", "display_name", "TEXT NOT NULL DEFAULT ''");
      await ensureColumn(db, "slices", "cut_mode", "TEXT NOT NULL DEFAULT 'rect'");
      await migrateCutModeConstraint(db);
      await db.run("UPDATE slices SET kind = 'image' WHERE kind != 'image'");
      await db.run("UPDATE slices SET cut_mode = 'subject' WHERE cut_mode = 'shape'");
      await db.run("UPDATE slices SET cut_mode = 'rect' WHERE cut_mode NOT IN ('rect', 'subject', 'card')");
    }
  },
  {
    id: "008_drop_billing_payment_tables",
    description: "Remove obsolete billing, payment, entitlement, and usage tables from user-only Slice Studio.",
    up: async (db) => {
      await db.exec(`
        DROP TABLE IF EXISTS payment_events;
        DROP TABLE IF EXISTS payment_orders;
        DROP TABLE IF EXISTS entitlements;
        DROP TABLE IF EXISTS plans;
        DROP TABLE IF EXISTS usage_events;
      `);
    }
  }
];

export async function applySchemaMigrations(db: SchemaDatabase): Promise<void> {
  await ensureSchemaMigrationsTable(db);
  const applied = new Set(
    (await db.all<{ id: string }>("SELECT id FROM schema_migrations ORDER BY id")).map((row) => row.id)
  );
  for (const migration of schemaMigrations) {
    if (applied.has(migration.id)) continue;
    await runMigration(db, migration);
  }
}

async function ensureSchemaMigrationsTable(db: SchemaDatabase): Promise<void> {
  await db.exec(`
    CREATE TABLE IF NOT EXISTS schema_migrations (
      id TEXT PRIMARY KEY,
      description TEXT NOT NULL,
      applied_at TEXT NOT NULL
    );
  `);
}

async function runMigration(db: SchemaDatabase, migration: SchemaMigration): Promise<void> {
  await db.transaction(async () => {
    await migration.up(db);
    await db.run(`
      INSERT INTO schema_migrations (id, description, applied_at)
      VALUES (?, ?, ?)
    `, [migration.id, migration.description, new Date().toISOString()]);
  });
}

async function ensureColumn(db: SchemaDatabase, tableName: string, columnName: string, definition: string): Promise<void> {
  if (await db.columnExists(tableName, columnName)) return;
  await db.exec(`ALTER TABLE ${safeIdentifier(tableName)} ADD COLUMN ${safeIdentifier(columnName)} ${definition}`);
}

async function migrateCutModeConstraint(db: SchemaDatabase): Promise<void> {
  if (db.provider === "postgres") return;

  const sql = await db.tableSql("slices");
  if (sql.includes("'subject'") && sql.includes("'card'") && !sql.includes("'shape'")) return;

  await db.exec(`
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

function baseSchemaSql(provider: "sqlite" | "postgres"): string {
  const integer = provider === "postgres" ? "INTEGER" : "INTEGER";
  return `
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

    CREATE TABLE IF NOT EXISTS projects (
      id TEXT PRIMARY KEY,
      user_id TEXT,
      name TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      page_count ${integer} NOT NULL DEFAULT 0,
      slice_count ${integer} NOT NULL DEFAULT 0,
      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
      page_index ${integer} NOT NULL,
      original_name TEXT NOT NULL,
      display_name TEXT NOT NULL DEFAULT '',
      original_path TEXT NOT NULL,
      width ${integer} NOT NULL,
      height ${integer} NOT NULL,
      created_at TEXT NOT NULL,
      PRIMARY KEY (project_id, id),
      FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS slices (
      id TEXT NOT NULL,
      project_id TEXT NOT NULL,
      page_id TEXT NOT NULL,
      slice_index ${integer} NOT NULL,
      name TEXT NOT NULL,
      kind TEXT NOT NULL CHECK (kind IN ('image')),
      cut_mode TEXT NOT NULL DEFAULT 'rect' CHECK (cut_mode IN ('rect', 'subject', 'card')),
      x ${integer} NOT NULL,
      y ${integer} NOT NULL,
      width ${integer} NOT NULL,
      height ${integer} NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      PRIMARY KEY (project_id, id),
      FOREIGN KEY (project_id, page_id) REFERENCES pages(project_id, id) ON DELETE CASCADE
    );
  `;
}

function safeIdentifier(value: string): string {
  if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(value)) throw new Error(`Unsafe SQL identifier: ${value}`);
  return value;
}
