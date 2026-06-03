from __future__ import annotations

from pathlib import Path
import socket

import pytest

from scripts.verify_deploy_bundle import assert_clean_bundle_tree, assert_port_free


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
