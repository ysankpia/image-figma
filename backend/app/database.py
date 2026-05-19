from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_schema(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                  id TEXT PRIMARY KEY,
                  status TEXT NOT NULL,
                  stage TEXT NOT NULL,
                  progress INTEGER NOT NULL,
                  message TEXT NOT NULL,
                  original_filename TEXT NOT NULL,
                  mime_type TEXT NOT NULL,
                  file_size INTEGER NOT NULL,
                  upload_path TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  completed_at TEXT,
                  failed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS assets (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  asset_id TEXT NOT NULL,
                  task_id TEXT NOT NULL,
                  role TEXT NOT NULL,
                  path TEXT NOT NULL,
                  url TEXT NOT NULL,
                  mime_type TEXT NOT NULL,
                  width INTEGER,
                  height INTEGER,
                  created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_assets_asset_id_created_at
                  ON assets(asset_id, created_at);

                CREATE TABLE IF NOT EXISTS dsl_results (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL UNIQUE,
                  dsl_path TEXT NOT NULL,
                  version TEXT NOT NULL,
                  validation_status TEXT NOT NULL,
                  validation_errors TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ocr_results (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL UNIQUE,
                  provider TEXT NOT NULL,
                  model TEXT,
                  status TEXT NOT NULL,
                  ocr_path TEXT,
                  block_count INTEGER NOT NULL,
                  error_code TEXT,
                  error_message TEXT,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS error_logs (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT,
                  stage TEXT NOT NULL,
                  error_code TEXT NOT NULL,
                  message TEXT NOT NULL,
                  detail TEXT,
                  severity TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                """
            )

    def insert_task(self, task: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks (
                  id, status, stage, progress, message, original_filename,
                  mime_type, file_size, upload_path, created_at, updated_at,
                  completed_at, failed_at
                )
                VALUES (
                  :id, :status, :stage, :progress, :message, :original_filename,
                  :mime_type, :file_size, :upload_path, :created_at, :updated_at,
                  :completed_at, :failed_at
                )
                """,
                task,
            )

    def update_task(
        self,
        task_id: str,
        *,
        status: str | None = None,
        stage: str | None = None,
        progress: int | None = None,
        message: str | None = None,
        updated_at: str | None = None,
        completed_at: str | None = None,
        failed_at: str | None = None,
    ) -> None:
        assignments: list[str] = []
        values: list[Any] = []
        fields = {
            "status": status,
            "stage": stage,
            "progress": progress,
            "message": message,
            "updated_at": updated_at,
            "completed_at": completed_at,
            "failed_at": failed_at,
        }
        for field, value in fields.items():
            if value is not None:
                assignments.append(f"{field} = ?")
                values.append(value)
        if not assignments:
            return
        values.append(task_id)
        with self.connect() as connection:
            connection.execute(
                f"UPDATE tasks SET {', '.join(assignments)} WHERE id = ?",
                values,
            )

    def get_task(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    def insert_asset(self, asset: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO assets (
                  asset_id, task_id, role, path, url, mime_type, width, height, created_at
                )
                VALUES (
                  :asset_id, :task_id, :role, :path, :url, :mime_type, :width, :height, :created_at
                )
                """,
                asset,
            )

    def get_latest_asset(self, asset_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute(
                "SELECT * FROM assets WHERE asset_id = ? ORDER BY created_at DESC, id DESC LIMIT 1",
                (asset_id,),
            ).fetchone()

    def insert_dsl_result(self, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO dsl_results (
                  task_id, dsl_path, version, validation_status, validation_errors, created_at
                )
                VALUES (
                  :task_id, :dsl_path, :version, :validation_status, :validation_errors, :created_at
                )
                """,
                result,
            )

    def get_dsl_result(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM dsl_results WHERE task_id = ?", (task_id,)).fetchone()

    def insert_ocr_result(self, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO ocr_results (
                  task_id, provider, model, status, ocr_path, block_count,
                  error_code, error_message, created_at
                )
                VALUES (
                  :task_id, :provider, :model, :status, :ocr_path, :block_count,
                  :error_code, :error_message, :created_at
                )
                """,
                result,
            )

    def insert_error(
        self,
        *,
        stage: str,
        error_code: str,
        message: str,
        task_id: str | None = None,
        detail: str | None = None,
        severity: str = "error",
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO error_logs (task_id, stage, error_code, message, detail, severity, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (task_id, stage, error_code, message, detail, severity),
            )


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
