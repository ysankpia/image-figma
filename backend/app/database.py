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

                CREATE TABLE IF NOT EXISTS primitive_results (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL UNIQUE,
                  provider TEXT NOT NULL,
                  model TEXT,
                  status TEXT NOT NULL,
                  primitive_path TEXT,
                  primitive_count INTEGER NOT NULL,
                  relation_count INTEGER NOT NULL,
                  error_code TEXT,
                  error_message TEXT,
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

                CREATE TABLE IF NOT EXISTS dsl_patch_results (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL UNIQUE,
                  mode TEXT NOT NULL,
                  status TEXT NOT NULL,
                  patch_path TEXT,
                  patch_count INTEGER NOT NULL,
                  warning_count INTEGER NOT NULL,
                  error_code TEXT,
                  error_message TEXT,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS text_replacement_results (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL UNIQUE,
                  mode TEXT NOT NULL,
                  status TEXT NOT NULL,
                  replacement_path TEXT,
                  accepted_count INTEGER NOT NULL,
                  rejected_count INTEGER NOT NULL,
                  warning_count INTEGER NOT NULL,
                  error_code TEXT,
                  error_message TEXT,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS text_binding_results (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL UNIQUE,
                  status TEXT NOT NULL,
                  binding_path TEXT,
                  container_count INTEGER NOT NULL,
                  binding_count INTEGER NOT NULL,
                  unbound_count INTEGER NOT NULL,
                  warning_count INTEGER NOT NULL,
                  error_code TEXT,
                  error_message TEXT,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS component_structure_results (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL UNIQUE,
                  status TEXT NOT NULL,
                  structure_path TEXT,
                  component_count INTEGER NOT NULL,
                  group_count INTEGER NOT NULL,
                  unstructured_count INTEGER NOT NULL,
                  warning_count INTEGER NOT NULL,
                  error_code TEXT,
                  error_message TEXT,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS component_annotation_results (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL UNIQUE,
                  status TEXT NOT NULL,
                  annotation_path TEXT,
                  annotation_count INTEGER NOT NULL,
                  group_hint_count INTEGER NOT NULL,
                  unannotated_count INTEGER NOT NULL,
                  warning_count INTEGER NOT NULL,
                  error_code TEXT,
                  error_message TEXT,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS layer_separation_results (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL UNIQUE,
                  status TEXT NOT NULL,
                  separation_path TEXT,
                  candidate_count INTEGER NOT NULL,
                  fill_candidate_count INTEGER NOT NULL,
                  repair_required_count INTEGER NOT NULL,
                  embedded_text_count INTEGER NOT NULL,
                  blocked_count INTEGER NOT NULL,
                  warning_count INTEGER NOT NULL,
                  error_code TEXT,
                  error_message TEXT,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS asset_slice_results (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL UNIQUE,
                  status TEXT NOT NULL,
                  slice_path TEXT,
                  slice_count INTEGER NOT NULL,
                  filled_slice_count INTEGER NOT NULL,
                  blocked_count INTEGER NOT NULL,
                  failed_slice_count INTEGER NOT NULL,
                  warning_count INTEGER NOT NULL,
                  error_code TEXT,
                  error_message TEXT,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS icon_candidate_results (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL UNIQUE,
                  status TEXT NOT NULL,
                  icon_path TEXT,
                  icon_count INTEGER NOT NULL,
                  cropped_icon_count INTEGER NOT NULL,
                  blocked_count INTEGER NOT NULL,
                  failed_crop_count INTEGER NOT NULL,
                  warning_count INTEGER NOT NULL,
                  error_code TEXT,
                  error_message TEXT,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS icon_coverage_audit_results (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL UNIQUE,
                  status TEXT NOT NULL,
                  audit_path TEXT,
                  overlay_asset_id TEXT,
                  placement_count INTEGER NOT NULL,
                  missed_hint_count INTEGER NOT NULL,
                  ready_count INTEGER NOT NULL,
                  needs_fallback_coordination_count INTEGER NOT NULL,
                  needs_slice_coordination_count INTEGER NOT NULL,
                  blocked_count INTEGER NOT NULL,
                  warning_count INTEGER NOT NULL,
                  error_code TEXT,
                  error_message TEXT,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS icon_gap_candidate_results (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL UNIQUE,
                  status TEXT NOT NULL,
                  gap_path TEXT,
                  overlay_asset_id TEXT,
                  gap_icon_count INTEGER NOT NULL,
                  cropped_gap_icon_count INTEGER NOT NULL,
                  blocked_count INTEGER NOT NULL,
                  failed_crop_count INTEGER NOT NULL,
                  warning_count INTEGER NOT NULL,
                  error_code TEXT,
                  error_message TEXT,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS icon_placement_plan_results (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL UNIQUE,
                  status TEXT NOT NULL,
                  plan_path TEXT,
                  overlay_asset_id TEXT,
                  placement_count INTEGER NOT NULL,
                  ready_count INTEGER NOT NULL,
                  needs_fallback_mask_count INTEGER NOT NULL,
                  needs_slice_coordination_count INTEGER NOT NULL,
                  needs_fallback_coordination_count INTEGER NOT NULL,
                  review_required_count INTEGER NOT NULL,
                  blocked_count INTEGER NOT NULL,
                  deduped_count INTEGER NOT NULL,
                  warning_count INTEGER NOT NULL,
                  error_code TEXT,
                  error_message TEXT,
                  created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS icon_visible_fallback_results (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  task_id TEXT NOT NULL UNIQUE,
                  status TEXT NOT NULL,
                  fallback_path TEXT,
                  overlay_asset_id TEXT,
                  selected_count INTEGER NOT NULL,
                  applied_count INTEGER NOT NULL,
                  blocked_count INTEGER NOT NULL,
                  skipped_count INTEGER NOT NULL,
                  warning_count INTEGER NOT NULL,
                  error_code TEXT,
                  error_message TEXT,
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

    def insert_primitive_result(self, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO primitive_results (
                  task_id, provider, model, status, primitive_path, primitive_count,
                  relation_count, error_code, error_message, created_at
                )
                VALUES (
                  :task_id, :provider, :model, :status, :primitive_path, :primitive_count,
                  :relation_count, :error_code, :error_message, :created_at
                )
                """,
                result,
            )

    def get_primitive_result(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM primitive_results WHERE task_id = ?", (task_id,)).fetchone()

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

    def get_ocr_result(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM ocr_results WHERE task_id = ?", (task_id,)).fetchone()

    def insert_dsl_patch_result(self, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO dsl_patch_results (
                  task_id, mode, status, patch_path, patch_count, warning_count,
                  error_code, error_message, created_at
                )
                VALUES (
                  :task_id, :mode, :status, :patch_path, :patch_count, :warning_count,
                  :error_code, :error_message, :created_at
                )
                """,
                result,
            )

    def get_dsl_patch_result(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM dsl_patch_results WHERE task_id = ?", (task_id,)).fetchone()

    def insert_text_replacement_result(self, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO text_replacement_results (
                  task_id, mode, status, replacement_path, accepted_count, rejected_count,
                  warning_count, error_code, error_message, created_at
                )
                VALUES (
                  :task_id, :mode, :status, :replacement_path, :accepted_count, :rejected_count,
                  :warning_count, :error_code, :error_message, :created_at
                )
                """,
                result,
            )

    def get_text_replacement_result(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM text_replacement_results WHERE task_id = ?", (task_id,)).fetchone()

    def insert_text_binding_result(self, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO text_binding_results (
                  task_id, status, binding_path, container_count, binding_count,
                  unbound_count, warning_count, error_code, error_message, created_at
                )
                VALUES (
                  :task_id, :status, :binding_path, :container_count, :binding_count,
                  :unbound_count, :warning_count, :error_code, :error_message, :created_at
                )
                """,
                result,
            )

    def get_text_binding_result(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM text_binding_results WHERE task_id = ?", (task_id,)).fetchone()

    def insert_component_structure_result(self, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO component_structure_results (
                  task_id, status, structure_path, component_count, group_count,
                  unstructured_count, warning_count, error_code, error_message, created_at
                )
                VALUES (
                  :task_id, :status, :structure_path, :component_count, :group_count,
                  :unstructured_count, :warning_count, :error_code, :error_message, :created_at
                )
                """,
                result,
            )

    def get_component_structure_result(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM component_structure_results WHERE task_id = ?", (task_id,)).fetchone()

    def insert_component_annotation_result(self, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO component_annotation_results (
                  task_id, status, annotation_path, annotation_count, group_hint_count,
                  unannotated_count, warning_count, error_code, error_message, created_at
                )
                VALUES (
                  :task_id, :status, :annotation_path, :annotation_count, :group_hint_count,
                  :unannotated_count, :warning_count, :error_code, :error_message, :created_at
                )
                """,
                result,
            )

    def get_component_annotation_result(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM component_annotation_results WHERE task_id = ?", (task_id,)).fetchone()

    def insert_layer_separation_result(self, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO layer_separation_results (
                  task_id, status, separation_path, candidate_count, fill_candidate_count,
                  repair_required_count, embedded_text_count, blocked_count, warning_count,
                  error_code, error_message, created_at
                )
                VALUES (
                  :task_id, :status, :separation_path, :candidate_count, :fill_candidate_count,
                  :repair_required_count, :embedded_text_count, :blocked_count, :warning_count,
                  :error_code, :error_message, :created_at
                )
                """,
                result,
            )

    def get_layer_separation_result(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM layer_separation_results WHERE task_id = ?", (task_id,)).fetchone()

    def insert_asset_slice_result(self, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO asset_slice_results (
                  task_id, status, slice_path, slice_count, filled_slice_count,
                  blocked_count, failed_slice_count, warning_count, error_code,
                  error_message, created_at
                )
                VALUES (
                  :task_id, :status, :slice_path, :slice_count, :filled_slice_count,
                  :blocked_count, :failed_slice_count, :warning_count, :error_code,
                  :error_message, :created_at
                )
                """,
                result,
            )

    def get_asset_slice_result(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM asset_slice_results WHERE task_id = ?", (task_id,)).fetchone()

    def insert_icon_candidate_result(self, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO icon_candidate_results (
                  task_id, status, icon_path, icon_count, cropped_icon_count,
                  blocked_count, failed_crop_count, warning_count, error_code,
                  error_message, created_at
                )
                VALUES (
                  :task_id, :status, :icon_path, :icon_count, :cropped_icon_count,
                  :blocked_count, :failed_crop_count, :warning_count, :error_code,
                  :error_message, :created_at
                )
                """,
                result,
            )

    def get_icon_candidate_result(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM icon_candidate_results WHERE task_id = ?", (task_id,)).fetchone()

    def insert_icon_coverage_audit_result(self, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO icon_coverage_audit_results (
                  task_id, status, audit_path, overlay_asset_id, placement_count,
                  missed_hint_count, ready_count, needs_fallback_coordination_count,
                  needs_slice_coordination_count, blocked_count, warning_count,
                  error_code, error_message, created_at
                )
                VALUES (
                  :task_id, :status, :audit_path, :overlay_asset_id, :placement_count,
                  :missed_hint_count, :ready_count, :needs_fallback_coordination_count,
                  :needs_slice_coordination_count, :blocked_count, :warning_count,
                  :error_code, :error_message, :created_at
                )
                """,
                result,
            )

    def get_icon_coverage_audit_result(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM icon_coverage_audit_results WHERE task_id = ?", (task_id,)).fetchone()

    def insert_icon_gap_candidate_result(self, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO icon_gap_candidate_results (
                  task_id, status, gap_path, overlay_asset_id, gap_icon_count,
                  cropped_gap_icon_count, blocked_count, failed_crop_count,
                  warning_count, error_code, error_message, created_at
                )
                VALUES (
                  :task_id, :status, :gap_path, :overlay_asset_id, :gap_icon_count,
                  :cropped_gap_icon_count, :blocked_count, :failed_crop_count,
                  :warning_count, :error_code, :error_message, :created_at
                )
                """,
                result,
            )

    def get_icon_gap_candidate_result(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM icon_gap_candidate_results WHERE task_id = ?", (task_id,)).fetchone()

    def insert_icon_placement_plan_result(self, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO icon_placement_plan_results (
                  task_id, status, plan_path, overlay_asset_id, placement_count,
                  ready_count, needs_fallback_mask_count, needs_slice_coordination_count,
                  needs_fallback_coordination_count, review_required_count, blocked_count,
                  deduped_count, warning_count, error_code, error_message, created_at
                )
                VALUES (
                  :task_id, :status, :plan_path, :overlay_asset_id, :placement_count,
                  :ready_count, :needs_fallback_mask_count, :needs_slice_coordination_count,
                  :needs_fallback_coordination_count, :review_required_count, :blocked_count,
                  :deduped_count, :warning_count, :error_code, :error_message, :created_at
                )
                """,
                result,
            )

    def get_icon_placement_plan_result(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM icon_placement_plan_results WHERE task_id = ?", (task_id,)).fetchone()

    def insert_icon_visible_fallback_result(self, result: dict[str, Any]) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO icon_visible_fallback_results (
                  task_id, status, fallback_path, overlay_asset_id, selected_count,
                  applied_count, blocked_count, skipped_count, warning_count,
                  error_code, error_message, created_at
                )
                VALUES (
                  :task_id, :status, :fallback_path, :overlay_asset_id, :selected_count,
                  :applied_count, :blocked_count, :skipped_count, :warning_count,
                  :error_code, :error_message, :created_at
                )
                """,
                result,
            )

    def get_icon_visible_fallback_result(self, task_id: str) -> sqlite3.Row | None:
        with self.connect() as connection:
            return connection.execute("SELECT * FROM icon_visible_fallback_results WHERE task_id = ?", (task_id,)).fetchone()

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
