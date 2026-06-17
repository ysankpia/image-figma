import { Database } from "bun:sqlite";
import fs from "node:fs";
import { databasePath, projectsRoot, storageRoot } from "./config";
import { applySchemaMigrations } from "./db-migrations";

fs.mkdirSync(projectsRoot, { recursive: true });
fs.mkdirSync(storageRoot, { recursive: true });

export const db = new Database(databasePath);
db.exec("PRAGMA foreign_keys = ON;");

export function initDatabase(): void {
  applySchemaMigrations(db);
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
