from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Sequence

import requests


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
    parser.add_argument(
        "--acceptance-image",
        type=Path,
        help="Optional image for HTTP smoke against the unpacked bundle service.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default="8110")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    archive_path = args.archive.expanduser().resolve()
    if not archive_path.exists():
        print(f"archive missing: {archive_path}", file=sys.stderr)
        return 2
    verify_archive_hash(archive_path)
    acceptance_image = args.acceptance_image.expanduser().resolve() if args.acceptance_image else None
    if acceptance_image and not acceptance_image.exists():
        print(f"acceptance image missing: {acceptance_image}", file=sys.stderr)
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
                "PENCIL_BACKEND_ADDR": f"{args.host}:{args.port}",
                "PENCIL_BACKEND_STORAGE_ROOT": str(work_dir / "storage"),
                "PENCIL_BACKEND_PSDLIKE_ROOT": str(unpacked_root / "services/psdlike-python"),
                "PENCIL_BACKEND_M29EXTRACT": str(backend_go / "bin/m29extract"),
                "OCR_PROVIDER": "none",
                "IMAGE_FIGMA_LOAD_LOCAL_ENV": "false",
            }
        )
        run(["uv", "run", "python", "scripts/preflight.py", "--require-m29"], cwd=unpacked_root / "services/pencil-python-backend", env=env)
        if acceptance_image:
            run_http_acceptance(
                service_root=unpacked_root / "services/pencil-python-backend",
                image=acceptance_image,
                out_dir=work_dir / "http-acceptance",
                host=args.host,
                port=args.port,
                timeout_seconds=args.timeout_seconds,
                env=env,
            )
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


def verify_archive_hash(archive_path: Path) -> None:
    manifest_path = archive_path.parent / "bundle-manifest.json"
    if not manifest_path.exists():
        print("archiveSha256=skip manifest missing", flush=True)
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = manifest.get("archiveSha256")
    if not isinstance(expected, str) or not expected:
        print("archiveSha256=skip manifest has no archiveSha256", flush=True)
        return
    actual = sha256_file(archive_path)
    if actual != expected:
        raise RuntimeError(f"archive sha256 mismatch: actual={actual} expected={expected}")
    print(f"archiveSha256=ok {actual}", flush=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def run_http_acceptance(
    *,
    service_root: Path,
    image: Path,
    out_dir: Path,
    host: str,
    port: str,
    timeout_seconds: float,
    env: dict[str, str],
) -> None:
    assert_port_free(host, port)
    server = subprocess.Popen(
        ["uv", "run", "uvicorn", "app.main:app", "--host", host, "--port", port],
        cwd=service_root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for_health(f"http://{host}:{port}", timeout_seconds, server)
        run(
            [
                "uv",
                "run",
                "python",
                "scripts/http_smoke.py",
                "--base-url",
                f"http://{host}:{port}",
                "--image",
                str(image),
                "--out",
                str(out_dir),
                "--project-name",
                "Deploy Bundle HTTP Acceptance",
            ],
            cwd=service_root,
            env=env,
        )
        print("httpAcceptance=ok")
    finally:
        stop_server(server)


def assert_port_free(host: str, port: str) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        if sock.connect_ex((host, int(port))) == 0:
            raise RuntimeError(f"port already in use: {host}:{port}")


def wait_for_health(base_url: str, timeout_seconds: float, server: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if server.poll() is not None:
            dump_server_output(server)
            raise RuntimeError(f"server exited before readiness: code={server.returncode}")
        try:
            response = requests.get(f"{base_url}/api/health", timeout=1)
            response.raise_for_status()
            if server.poll() is not None:
                dump_server_output(server)
                raise RuntimeError(f"server exited during readiness check: code={server.returncode}")
            print("server=ready", flush=True)
            return
        except Exception as error:
            last_error = error
            time.sleep(0.25)
    raise TimeoutError(f"server did not become ready: {last_error}")


def stop_server(server: subprocess.Popen[str]) -> None:
    if server.poll() is not None:
        dump_server_output(server)
        return
    server.send_signal(signal.SIGINT)
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=5)
    dump_server_output(server)


def dump_server_output(server: subprocess.Popen[str]) -> None:
    if server.stdout is None:
        return
    output = server.stdout.read()
    if output:
        print(output, end="")


def run(cmd: Sequence[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"verify_deploy_bundle=fail {error}", file=sys.stderr)
        raise
