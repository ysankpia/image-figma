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
      name TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      page_count INTEGER NOT NULL DEFAULT 0,
      slice_count INTEGER NOT NULL DEFAULT 0
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
  ensureColumn("pages", "display_name", "TEXT NOT NULL DEFAULT ''");
  ensureColumn("slices", "cut_mode", "TEXT NOT NULL DEFAULT 'rect'");
  migrateCutModeConstraint();
  db.query("UPDATE slices SET kind = 'image' WHERE kind != 'image'").run();
  db.query("UPDATE slices SET cut_mode = 'subject' WHERE cut_mode = 'shape'").run();
  db.query("UPDATE slices SET cut_mode = 'rect' WHERE cut_mode NOT IN ('rect', 'subject', 'card')").run();
}

function ensureColumn(tableName: string, columnName: string, definition: string): void {
  const columns = db.query<{ name: string }, []>(`PRAGMA table_info(${tableName})`).all();
  if (!columns.some((column) => column.name === columnName)) {
    db.exec(`ALTER TABLE ${tableName} ADD COLUMN ${columnName} ${definition}`);
  }
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

function migrateCutModeConstraint(): void {
  const sql = db.query<{ sql: string | null }, [string]>("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?").get("slices")?.sql || "";
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
