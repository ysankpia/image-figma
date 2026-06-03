from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Sequence


SERVICE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_ROOT = Path("/Volumes/WorkDrive/pencil-exports/pencil-backend-bundle")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify a Pencil Python Backend deploy bundle after unpacking it.")
    parser.add_argument(
        "--archive",
        type=Path,
        default=DEFAULT_BUNDLE_ROOT / "pencil-python-backend-deploy.tar.gz",
        help="Deploy bundle .tar.gz produced by build_deploy_bundle.py.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        help="Directory for unpack verification. Defaults to a temporary directory.",
    )
    parser.add_argument(
        "--keep-work-dir",
        action="store_true",
        help="Keep the unpacked verification directory after success or failure.",
    )
    parser.add_argument(
        "--skip-uv-sync",
        action="store_true",
        help="Skip uv sync in unpacked Python services.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive_path = args.archive.expanduser().resolve()
    if not archive_path.exists():
        print(f"archive missing: {archive_path}", file=sys.stderr)
        return 2

    cleanup = False
    if args.work_dir:
        work_dir = args.work_dir.expanduser().resolve()
        if work_dir.exists():
            shutil.rmtree(work_dir)
        work_dir.mkdir(parents=True)
    else:
        work_dir = Path(tempfile.mkdtemp(prefix="pencil-deploy-bundle-"))
        cleanup = not args.keep_work_dir

    try:
        unpacked_root = extract_archive(archive_path, work_dir)
        print(f"workDir={work_dir}")
        print(f"unpackedRoot={unpacked_root}")

        require_file(unpacked_root / "services/pencil-python-backend/pyproject.toml")
        require_file(unpacked_root / "services/psdlike-python/pyproject.toml")
        require_file(unpacked_root / "services/backend-go/go.mod")
        require_file(unpacked_root / "services/backend-go/cmd/m29extract/main.go")
        require_file(unpacked_root / "services/pencil-python-backend/deploy/pencil-python-backend.service")
        assert_clean_bundle_tree(unpacked_root)
        print("tree=ok")

        command_env = clean_command_env()
        if not args.skip_uv_sync:
            run(["uv", "sync"], cwd=unpacked_root / "services/pencil-python-backend", env=command_env)
            run(["uv", "sync"], cwd=unpacked_root / "services/psdlike-python", env=command_env)
        else:
            print("uvSync=skipped")

        backend_go = unpacked_root / "services/backend-go"
        run(["go", "build", "-o", "bin/m29extract", "./cmd/m29extract"], cwd=backend_go, env=command_env)
        require_file(backend_go / "bin/m29extract")
        print("m29extractBuild=ok")

        env = clean_command_env()
        env.update(
            {
                "PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE": "psdlike",
                "PENCIL_BACKEND_STORAGE_ROOT": str(work_dir / "storage"),
                "PENCIL_BACKEND_PSDLIKE_ROOT": str(unpacked_root / "services/psdlike-python"),
                "PENCIL_BACKEND_M29EXTRACT": str(backend_go / "bin/m29extract"),
                "OCR_PROVIDER": "none",
                "IMAGE_FIGMA_LOAD_LOCAL_ENV": "false",
            }
        )
        run(["uv", "run", "python", "scripts/preflight.py", "--require-m29"], cwd=unpacked_root / "services/pencil-python-backend", env=env)
        print("deployBundleVerification=ok")
        return 0
    finally:
        if cleanup:
            shutil.rmtree(work_dir, ignore_errors=True)
        elif args.keep_work_dir:
            print(f"keptWorkDir={work_dir}")


def extract_archive(archive_path: Path, work_dir: Path) -> Path:
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        roots = {member.name.split("/", 1)[0] for member in members if member.name}
        if len(roots) != 1:
            raise RuntimeError(f"archive must contain exactly one top-level directory, got {sorted(roots)}")
        root_name = next(iter(roots))
        archive.extractall(work_dir, filter="data")
    unpacked_root = work_dir / root_name
    if not unpacked_root.is_dir():
        raise RuntimeError(f"unpacked root missing: {unpacked_root}")
    return unpacked_root


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)


def assert_clean_bundle_tree(root: Path) -> None:
    forbidden_names = {".venv", "__pycache__", ".pytest_cache", "storage"}
    forbidden_suffixes = {".pyc", ".pyo"}
    forbidden_paths: list[str] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root).as_posix()
        parts = set(path.relative_to(root).parts)
        if parts & forbidden_names:
            forbidden_paths.append(rel)
        elif path.suffix in forbidden_suffixes:
            forbidden_paths.append(rel)
        elif rel.startswith("services/backend-go/bin/"):
            forbidden_paths.append(rel)
    if forbidden_paths:
        preview = ", ".join(sorted(forbidden_paths)[:20])
        raise RuntimeError(f"bundle contains forbidden paths: {preview}")


def clean_command_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    return env


def run(cmd: Sequence[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"verify_deploy_bundle=fail {error}", file=sys.stderr)
        raise
