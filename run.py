#!/usr/bin/env python3
"""Launch the Gas Cylinder Weight Detection inference backend.

Two interchangeable ways to run the Python/YOLO server, selected with --mode:

    python run.py --mode local     # run natively with this Python interpreter
    python run.py --mode docker    # build + run it inside a Docker container

Add --frontend to also start the Electron UI (npm start) once the backend is up.

Examples
--------
    python run.py                            # local backend only (default)
    python run.py --mode docker              # containerised backend only
    python run.py --mode local --frontend    # backend + UI, the usual dev combo
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMAGE_TAG = "gcwd-backend"


def wait_until_ready(port: int, timeout: float = 180.0) -> bool:
    """Poll /health until the backend answers or we give up."""
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(1.0)
    return False


def start_local(host: str, port: int) -> subprocess.Popen:
    env = {**os.environ, "GCWD_HOST": host, "GCWD_PORT": str(port)}
    print(f"[run] starting local backend on {host}:{port} ...")
    return subprocess.Popen([sys.executable, str(ROOT / "server.py")], env=env)


def start_docker(port: int, rebuild: bool, lan: bool, detach: bool) -> subprocess.Popen | None:
    if shutil.which("docker") is None:
        sys.exit("[run] docker not found on PATH — install Docker or use --mode local")

    existing = subprocess.run(
        ["docker", "images", "-q", IMAGE_TAG], capture_output=True, text=True
    ).stdout.strip()
    if rebuild or not existing:
        print(f"[run] building image '{IMAGE_TAG}' "
              "(first build downloads torch — this can take a while) ...")
        subprocess.check_call(["docker", "build", "-t", IMAGE_TAG, str(ROOT)])

    # With --lan, publish on every interface so another machine (e.g. the Pi)
    # can reach this server; otherwise keep it on localhost only (enough for a
    # tunnel/share-link, which forwards from localhost).
    publish = f"{port}:{port}" if lan else f"127.0.0.1:{port}:{port}"
    where = "all interfaces (LAN)" if lan else "127.0.0.1"

    if detach:
        # Persistent background container: auto-restarts when Docker starts, so
        # "turn the machine on -> the server is already running". Point your
        # share-link/tunnel at this host's port, then put that link in the Pi.
        subprocess.run(["docker", "rm", "-f", IMAGE_TAG],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"[run] starting detached docker backend on {where}:{port} "
              "(--restart unless-stopped) ...")
        subprocess.check_call(
            ["docker", "run", "-d", "--name", IMAGE_TAG,
             "--restart", "unless-stopped",
             "-p", publish,
             "-e", f"GCWD_PORT={port}", IMAGE_TAG]
        )
        return None

    print(f"[run] starting docker backend, publishing {where} on port {port} ...")
    return subprocess.Popen(
        ["docker", "run", "--rm", "--name", IMAGE_TAG,
         "-p", publish,
         "-e", f"GCWD_PORT={port}", IMAGE_TAG]
    )


def start_frontend() -> subprocess.Popen:
    npm = shutil.which("npm")
    if npm is None:
        sys.exit("[run] npm not found on PATH — install Node.js to use --frontend")
    print("[run] starting Electron frontend (npm start) ...")
    # shell=True on Windows so the npm.cmd shim resolves correctly.
    return subprocess.Popen([npm, "start"], cwd=str(ROOT), shell=(os.name == "nt"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the inference backend (and optionally the Electron UI)."
    )
    parser.add_argument("--mode", choices=["local", "docker"], default="local",
                        help="how to run the backend (default: local)")
    parser.add_argument("--port", type=int, default=5000,
                        help="backend port (default: 5000)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="bind host for local mode "
                             "(default: 127.0.0.1; ignored in docker mode)")
    parser.add_argument("--lan", action="store_true",
                        help="expose the backend on the network so another machine "
                             "(e.g. a Raspberry Pi client) can reach it")
    parser.add_argument("--frontend", action="store_true",
                        help="also launch the Electron UI once the backend is ready")
    parser.add_argument("--detach", "-d", action="store_true",
                        help="docker mode: run the container in the background with "
                             "auto-restart and exit (point a tunnel/share-link at it)")
    parser.add_argument("--rebuild", action="store_true",
                        help="force a docker image rebuild")
    args = parser.parse_args()

    # --lan means "reachable from other machines": bind all interfaces.
    if args.lan:
        args.host = "0.0.0.0"

    detached = args.mode == "docker" and args.detach

    procs: list[subprocess.Popen] = []
    try:
        if args.mode == "local":
            procs.append(start_local(args.host, args.port))
        else:
            proc = start_docker(args.port, args.rebuild, args.lan, args.detach)
            if proc is not None:
                procs.append(proc)

        if detached:
            print(f"[run] container '{IMAGE_TAG}' is running in the background on "
                  f"port {args.port}.")
            print("[run] expose it with your tunnel/Release Share, then on the Pi run:")
            print(f"      GCWD_SERVER=<your-share-link> npm start")
            print(f"[run] manage it:  docker logs -f {IMAGE_TAG}  |  "
                  f"docker stop {IMAGE_TAG}")
            return 0

        if args.frontend:
            if wait_until_ready(args.port):
                print("[run] backend is ready.")
            else:
                print("[run] warning: backend did not report ready in time; "
                      "starting UI anyway.")
            procs.append(start_frontend())
        else:
            print(f"[run] backend running on port {args.port}. "
                  "Start the UI separately with 'npm start', or pass --frontend.")

        # Wait for any child to exit, then tear the rest down.
        while True:
            for p in procs:
                if p.poll() is not None:
                    return p.returncode or 0
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[run] shutting down ...")
        return 0
    finally:
        # Don't stop a detached container — it's meant to keep running.
        if args.mode == "docker" and not detached:
            subprocess.run(["docker", "stop", IMAGE_TAG],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except Exception:
                p.kill()


if __name__ == "__main__":
    raise SystemExit(main())
