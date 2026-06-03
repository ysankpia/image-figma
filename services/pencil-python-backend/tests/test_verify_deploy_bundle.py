from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from scripts.verify_deploy_bundle import assert_clean_bundle_tree, assert_port_free, sha256_file, verify_archive_hash


def test_assert_clean_bundle_tree_rejects_runtime_artifacts(tmp_path: Path) -> None:
    (tmp_path / "services/backend-go/bin").mkdir(parents=True)
    (tmp_path / "services/backend-go/bin/m29extract").write_text("binary", encoding="utf-8")

    with pytest.raises(RuntimeError, match="forbidden paths"):
        assert_clean_bundle_tree(tmp_path)


def test_assert_clean_bundle_tree_accepts_required_sources(tmp_path: Path) -> None:
    (tmp_path / "services/pencil-python-backend/app").mkdir(parents=True)
    (tmp_path / "services/pencil-python-backend/app/main.py").write_text("", encoding="utf-8")
    (tmp_path / "services/backend-go/cmd/m29extract").mkdir(parents=True)
    (tmp_path / "services/backend-go/cmd/m29extract/main.go").write_text("", encoding="utf-8")

    assert_clean_bundle_tree(tmp_path)


def test_assert_port_free_rejects_bound_port() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        port = str(sock.getsockname()[1])

        with pytest.raises(RuntimeError, match="port already in use"):
            assert_port_free("127.0.0.1", port)


def test_verify_archive_hash_accepts_matching_manifest(tmp_path: Path) -> None:
    archive = tmp_path / "pencil-python-backend-deploy.tar.gz"
    archive.write_bytes(b"deploy bundle")
    (tmp_path / "bundle-manifest.json").write_text(
        json.dumps({"archiveSha256": sha256_file(archive)}),
        encoding="utf-8",
    )

    verify_archive_hash(archive)


def test_verify_archive_hash_rejects_mismatch(tmp_path: Path) -> None:
    archive = tmp_path / "pencil-python-backend-deploy.tar.gz"
    archive.write_bytes(b"deploy bundle")
    (tmp_path / "bundle-manifest.json").write_text(
        json.dumps({"archiveSha256": "0" * 64}),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="archive sha256 mismatch"):
        verify_archive_hash(archive)
