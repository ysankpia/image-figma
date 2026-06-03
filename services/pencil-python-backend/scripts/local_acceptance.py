from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local Pencil backend acceptance: preflight, server, smoke, upload.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default="8100")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--project-name", default="Pencil Local Acceptance")
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    service_root = Path(__file__).resolve().parents[1]
    image = args.image.expanduser().resolve()
    out = args.out.expanduser().resolve()
    if not image.exists():
        print(f"image does not exist: {image}", file=sys.stderr)
        return 2

    env = os.environ.copy()
    env.setdefault("PENCIL_BACKEND_DEFAULT_BOUNDARY_SOURCE", "psdlike")
    env.setdefault("OCR_PROVIDER", "none")
    env.setdefault("PENCIL_BACKEND_ADDR", f"{args.host}:{args.port}")

    run([sys.executable, "scripts/preflight.py"], cwd=service_root, env=env)

    server = subprocess.Popen(
        ["uv", "run", "uvicorn", "app.main:app", "--host", args.host, "--port", args.port],
        cwd=service_root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for_health(f"http://{args.host}:{args.port}", args.timeout_seconds)
        run(
            [
                sys.executable,
                "scripts/http_smoke.py",
                "--base-url",
                f"http://{args.host}:{args.port}",
                "--image",
                str(image),
                "--out",
                str(out / "smoke"),
            ],
            cwd=service_root,
            env=env,
        )
        run(
            [
                sys.executable,
                "scripts/upload_project.py",
                "--base-url",
                f"http://{args.host}:{args.port}",
                "--input",
                str(image),
                "--out",
                str(out / "upload"),
                "--project-name",
                args.project_name,
                "--mode",
                "all",
            ],
            cwd=service_root,
            env=env,
        )
    finally:
        stop_server(server)
    print("local_acceptance=ok")
    return 0


def run(cmd: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def wait_for_health(base_url: str, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = requests.get(f"{base_url}/api/health", timeout=1)
            response.raise_for_status()
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


if __name__ == "__main__":
    raise SystemExit(main())
