# Gas Cylinder Weight Detection

Reads the printed weight stamped on an (empty) gas cylinder from a camera frame
using two YOLO models, and classifies it. Replaces an older 9-camera prototype
with a single-camera setup.

## Architecture

Two pieces that talk over HTTP on port `5000`:

```
┌─────────────────────────┐        POST /predict (jpeg)        ┌──────────────────────────┐
│  Electron UI (Node.js)  │  ───────────────────────────────▶ │  Flask backend (Python)  │
│  webcam capture + view  │                                    │  YOLO text + digit models│
│  main.js / render.js    │  ◀─────────────────────────────── │  server.py               │
└─────────────────────────┘        { "prediction": "152" }     └──────────────────────────┘
```

- **Frontend** — `main.js`, `preload.js`, `render.js`, `main.html`, `summa.css`.
  Captures a frame from a top view of the cylinder and POSTs it to the backend.
- **Backend** — `server.py` loads `grayscale_text_detect_model.pt` and
  `grayscale_digit_detect.pt`, finds the (~3) stamped weight regions, reads the
  digits, and returns a best-of-2 majority (or highest-confidence) prediction.
  This is the part you can run **locally** or in **Docker**.

The two halves can live on the **same machine** *or* on **different machines**:
the recommended setup runs the **backend in Docker on a laptop** and the
**UI + camera on the Pi**, which just sends the image and shows the result —
see [Split deployment](#split-deployment-server-on-laptop-ui-on-pi).

## Prerequisites

- **Python 3.9+** (tested on 3.11/3.12) for the backend.
- **Node.js 18+** for the Electron UI.
- **Docker** (optional) — only if you want to run the backend in a container.
- A working **camera** for the UI.

## Quick start (TL;DR)

```bash
# 1. Install backend deps (local mode)
pip install -r requirements.txt

# 2. Install frontend deps
npm install

# 3. Run backend (local) + UI together
python run.py --mode local --frontend
```

That's it — the window opens, click **Start** → **Capture**.

## Running the backend — `run.py`

A single launcher picks how the backend runs. **Toggle with `--mode`:**

```bash
python run.py --mode local      # native Python (default) — recommended on a Pi
python run.py --mode docker     # build + run the backend in a container
```

Useful flags:

| Flag          | Default     | Meaning                                                        |
|---------------|-------------|----------------------------------------------------------------|
| `--mode`      | `local`     | `local` (native) or `docker` (container)                       |
| `--frontend`  | off         | also launch the Electron UI once the backend reports healthy   |
| `--port`      | `5000`      | backend port (UI expects `5000`)                               |
| `--host`      | `127.0.0.1` | bind host for **local** mode (`docker` always binds `0.0.0.0`) |
| `--lan`       | off         | expose the backend on the network so another machine (the Pi) can reach it |
| `--detach`/`-d` | off       | **docker only**: run the container in the background with auto-restart, then exit (point a tunnel/Release Share at it) |
| `--rebuild`   | off         | force a fresh `docker build`                                   |

Examples:

```bash
python run.py                              # local backend only
python run.py --mode docker                # containerised backend only
python run.py --mode docker --frontend     # container backend + UI
python run.py --mode docker --lan          # container backend reachable from the Pi
python run.py --mode docker --detach       # background container for a share link
python run.py --mode docker --rebuild      # rebuild the image, then run
```

Stop everything with `Ctrl+C` (the launcher also stops the Docker container).

> You can always run the two halves by hand instead:
> backend → `python server.py`, UI → `npm start`.

## Split deployment: server on laptop, UI on Pi

**Recommended setup.** The Pi is too weak to run two YOLO models quickly, so let
the laptop do the inference and let the Pi just capture and display. Only a small
JPEG goes out and a tiny JSON comes back.

```
   Pi (camera + Electron UI)                  Laptop (Docker model server + share link)
   ──────────────────────────                 ─────────────────────────────────────────
   npm start (default server)                 python run.py --mode docker --detach
                        ── POST /predict ──▶   container :5000  ── Release Share ──▶ public URL
                        ◀── {prediction} ──    https://meet-marten-55.rshare.io
```

### Option 1 — fixed share link (Release Share / a tunnel) — no IPs to chase

Run the container in the background on the laptop, then expose it with the
**Release Share** Docker Desktop extension (or any tunnel). The current link
`https://meet-marten-55.rshare.io` is already the **default** the UI uses, so the
Pi just needs `npm start`.

**On the laptop:**

```bash
python run.py --mode docker --detach     # builds, runs in background, auto-restarts
```

Then in Docker Desktop open **Release Share**, share the `gcwd-backend`
container's port **5000**, and confirm the URL is `https://meet-marten-55.rshare.io`.

**On the Pi** (only Node.js needed — no Python/torch/models):

```bash
sudo apt update && sudo apt install -y nodejs npm
npm install
npm start                                # uses https://meet-marten-55.rshare.io by default
# if the share link ever changes, override it:
#   GCWD_SERVER=https://<new-name>.rshare.io npm start
```

> Check whether your share link is **stable** across restarts. If the service
> hands out a new random subdomain each time, reserve/fix the name (most have an
> option) so you don't have to edit the Pi again.

### Option 2 — same Wi-Fi, use the laptop's LAN address

No external service; both devices on the same network.

```bash
# laptop:
python run.py --mode docker --lan        # exposed on the LAN
ipconfig                                 # note the IPv4, e.g. 192.168.1.50
# (allow inbound TCP 5000 through the laptop firewall when prompted)
```
```bash
# Pi:
GCWD_SERVER=http://192.168.1.50:5000 npm start
```

See [`DEPLOYMENT_QA.md`](DEPLOYMENT_QA.md) for the full per-case runbook and the
why behind this architecture.

### Alternative: everything on the Pi

If you'd rather run the whole thing on the Pi (no laptop), use a **64-bit
Raspberry Pi OS** and run the backend in **local** mode (lighter than Docker on a Pi):

```bash
sudo apt install -y python3-pip python3-venv nodejs npm libgl1 libglib2.0-0
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && npm install
python run.py --mode local --frontend
```

## Configuration (environment variables)

**Backend** (`server.py`) reads these (all optional):

| Variable           | Default                          | Purpose                                  |
|--------------------|----------------------------------|------------------------------------------|
| `GCWD_HOST`        | `0.0.0.0`                        | bind address                             |
| `GCWD_PORT`        | `5000`                           | listen port                              |
| `GCWD_TEXT_MODEL`  | `./grayscale_text_detect_model.pt` | text-detection weights path            |
| `GCWD_DIGIT_MODEL` | `./grayscale_digit_detect.pt`    | digit-detection weights path             |
| `GCWD_TMP`         | script directory                 | where temp/cropped images are written    |

**Frontend** (`main.js`) reads this:

| Variable      | Default                            | Purpose                                          |
|---------------|------------------------------------|--------------------------------------------------|
| `GCWD_SERVER` | `https://meet-marten-55.rshare.io` | backend URL the UI POSTs to (the Release Share link; override for a local/LAN setup, e.g. `http://127.0.0.1:5000`) |

## Notes on changes

- **Model paths are now relative / env-driven** — the old hard-coded
  `C:\Users\suraj\...` paths are gone, so it runs on any machine.
- **`requirements.txt`, `Dockerfile`, `.dockerignore`, `run.py`** added.
- **`main.js`** — the backend URL defaults to the Release Share link
  (`https://meet-marten-55.rshare.io`) and is overridable via `GCWD_SERVER`.
  No change to the visual UI.
- **Trimmed unused npm deps** (`opencv4nodejs-prebuilt-install`, `node-webcam`,
  `python-shell`, `exceljs`) — they were never `require`d and the two native
  ones make `npm install` slow/fragile on ARM. Run `npm install` to refresh the
  lockfile. (Re-add them if a later version of the UI needs them.)
- **Backend speed/robustness, prediction logic unchanged** — decodes each frame
  once, reads `roi_paths[:3]` (same top-3 crops as before, but no crash when the
  model finds fewer than 3), and silences YOLO's per-frame logging. Rotation,
  digit splitting, confidence, and weight-selection are untouched.
