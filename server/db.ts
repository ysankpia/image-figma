import { AsyncLocalStorage } from "node:async_hooks";
import fs from "node:fs";
import { Database } from "bun:sqlite";
import type { SQLQueryBindings } from "bun:sqlite";
import { Pool, type PoolClient, type QueryResult, types as pgTypes } from "pg";
import { databasePath, databaseProvider, databaseUrl, projectsRoot, storageRoot, type DatabaseProvider } from "./config";
import { applySchemaMigrations, type SchemaDatabase } from "./db-migrations";

fs.mkdirSync(projectsRoot, { recursive: true });
fs.mkdirSync(storageRoot, { recursive: true });

export type SqlValue = string | number | boolean | null | Buffer;
export type SqlParams = readonly SqlValue[];
export type DbResult = {
  changes: number;
};

export interface AppDatabase extends SchemaDatabase {
  provider: DatabaseProvider;
  all<Row extends Record<string, unknown>>(sql: string, params?: SqlParams): Promise<Row[]>;
  get<Row extends Record<string, unknown>>(sql: string, params?: SqlParams): Promise<Row | undefined>;
  run(sql: string, params?: SqlParams): Promise<DbResult>;
  exec(sql: string): Promise<void>;
  transaction<T>(fn: () => Promise<T>): Promise<T>;
  close(): Promise<void>;
}

class SqliteAppDatabase implements AppDatabase {
  readonly provider = "sqlite" as const;
  private readonly sqlite = new Database(databasePath);

  constructor() {
    this.sqlite.exec("PRAGMA foreign_keys = ON;");
  }

  async all<Row extends Record<string, unknown>>(sql: string, params: SqlParams = []): Promise<Row[]> {
    return this.sqlite.query<Row, SQLQueryBindings[]>(sql).all(...sqliteParams(params));
  }

  async get<Row extends Record<string, unknown>>(sql: string, params: SqlParams = []): Promise<Row | undefined> {
    return this.sqlite.query<Row, SQLQueryBindings[]>(sql).get(...sqliteParams(params)) || undefined;
  }

  async run(sql: string, params: SqlParams = []): Promise<DbResult> {
    const result = this.sqlite.query(sql).run(...sqliteParams(params));
    return { changes: result.changes };
  }

  async exec(sql: string): Promise<void> {
    this.sqlite.exec(sql);
  }

  async transaction<T>(fn: () => Promise<T>): Promise<T> {
    this.sqlite.exec("BEGIN");
    try {
      const result = await fn();
      this.sqlite.exec("COMMIT");
      return result;
    } catch (error) {
      this.sqlite.exec("ROLLBACK");
      throw error;
    }
  }

  async close(): Promise<void> {
    this.sqlite.close(false);
  }

  async tableExists(tableName: string): Promise<boolean> {
    const row = await this.get<{ name: string }>(
      "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
      [tableName]
    );
    return Boolean(row);
  }

  async columnExists(tableName: string, columnName: string): Promise<boolean> {
    const columns = await this.all<{ name: string }>(`PRAGMA table_info(${safeIdentifier(tableName)})`);
    return columns.some((column) => column.name === columnName);
  }

  async tableSql(tableName: string): Promise<string> {
    const row = await this.get<{ sql: string | null }>(
      "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
      [tableName]
    );
    return row?.sql || "";
  }
}

class PostgresAppDatabase implements AppDatabase {
  readonly provider = "postgres" as const;
  private readonly pool: Pool;
  private readonly transactionClient = new AsyncLocalStorage<PoolClient>();

  constructor() {
    if (!databaseUrl) throw new Error("SLICE_STUDIO_DATABASE_URL is required when SLICE_STUDIO_DATABASE_PROVIDER=postgres");
    pgTypes.setTypeParser(20, (value) => Number(value));
    pgTypes.setTypeParser(1700, (value) => Number(value));
    this.pool = new Pool({ connectionString: databaseUrl, max: 6 });
  }

  async all<Row extends Record<string, unknown>>(sql: string, params: SqlParams = []): Promise<Row[]> {
    const result = await this.query<Row>(sql, params);
    return result.rows;
  }

  async get<Row extends Record<string, unknown>>(sql: string, params: SqlParams = []): Promise<Row | undefined> {
    const result = await this.query<Row>(sql, params);
    return result.rows[0];
  }

  async run(sql: string, params: SqlParams = []): Promise<DbResult> {
    const result = await this.query(sql, params);
    return { changes: result.rowCount || 0 };
  }

  async exec(sql: string): Promise<void> {
    await this.query(sql, []);
  }

  async transaction<T>(fn: () => Promise<T>): Promise<T> {
    const existingClient = this.transactionClient.getStore();
    if (existingClient) return fn();

    const client = await this.pool.connect();
    try {
      await client.query("BEGIN");
      const result = await this.transactionClient.run(client, fn);
      await client.query("COMMIT");
      return result;
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }

  async close(): Promise<void> {
    await this.pool.end();
  }

  async tableExists(tableName: string): Promise<boolean> {
    const row = await this.get<{ table_name: string }>(
      "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = ?",
      [tableName]
    );
    return Boolean(row);
  }

  async columnExists(tableName: string, columnName: string): Promise<boolean> {
    const row = await this.get<{ column_name: string }>(
      "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = ? AND column_name = ?",
      [tableName, columnName]
    );
    return Boolean(row);
  }

  async tableSql(): Promise<string> {
    return "";
  }

  private async query<Row extends Record<string, unknown> = Record<string, unknown>>(
    sql: string,
    params: SqlParams
  ): Promise<QueryResult<Row>> {
    const client = this.transactionClient.getStore();
    const querySql = params.length ? toPostgresPlaceholders(sql) : sql;
    return client
      ? client.query<Row>(querySql, [...params])
      : this.pool.query<Row>(querySql, [...params]);
  }
}

export const db: AppDatabase = databaseProvider === "postgres"
  ? new PostgresAppDatabase()
  : new SqliteAppDatabase();

export async function initDatabase(): Promise<void> {
  await applySchemaMigrations(db);
}

export async function transaction<T>(fn: () => Promise<T>): Promise<T> {
  return db.transaction(fn);
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

function toPostgresPlaceholders(sql: string): string {
  let index = 0;
  let output = "";
  let inSingleQuote = false;
  for (let i = 0; i < sql.length; i += 1) {
    const char = sql[i];
    if (char === "'") {
      output += char;
      if (inSingleQuote && sql[i + 1] === "'") {
        output += sql[i + 1];
        i += 1;
      } else {
        inSingleQuote = !inSingleQuote;
      }
      continue;
    }
    if (char === "?" && !inSingleQuote) {
      index += 1;
      output += `$${index}`;
      continue;
    }
    output += char;
  }
  return output;
}

function safeIdentifier(value: string): string {
  if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(value)) throw new Error(`Unsafe SQL identifier: ${value}`);
  return value;
}

function sqliteParams(params: SqlParams): SQLQueryBindings[] {
  return [...params] as SQLQueryBindings[];
}
