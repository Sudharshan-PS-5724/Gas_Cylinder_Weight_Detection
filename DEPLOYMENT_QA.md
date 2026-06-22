# Deployment Q&A

Your questions from setting this up, with answers. Practical run commands live in
[`README.md`](README.md); this file is the *why*.

> **The chosen architecture:** the **laptop** runs the YOLO model server (in
> Docker), and the **Pi** is a thin client — it captures the cylinder image,
> sends it to the laptop, and shows the returned weight. See Q7 for why this is
> the right call.

---

## Q1. How do I run this project?

Two halves: the **Electron UI** (camera + display) and the **Python/YOLO backend**
(the model server). The launcher `run.py` starts the backend; `--frontend` also
starts the UI when both run on the same machine.

```bash
pip install -r requirements.txt   # backend deps
npm install                       # UI deps
python run.py --mode local --frontend
```

For the laptop-server / Pi-client split, see Q7.

---

## Q2. It mentioned "docker link reshare" — does this version actually use Docker?

No. The code you have is a plain Electron + Flask app with **no Docker
dependency** — `server.py` just loaded the models from a hard-coded
`C:\Users\suraj\...` path (now fixed to a relative path). Your *later* version
may use Docker; this one didn't.

You asked to add the Docker option anyway, so it's now there as an opt-in
**toggle** (`run.py --mode docker`) sitting next to local mode.

---

## Q3. What does the Dockerfile contain, and is a "Python sandbox" enough?

Yes — a Python sandbox is exactly right. The image only needs to run the model
server and hand back a weight. The `Dockerfile`:

- base `python:3.11-slim-bookworm` (multi-arch: x86 laptop **and** Pi arm64),
- a few native libs OpenCV/torch need at runtime (`libgl1`, `libglib2.0-0`, `libgomp1`),
- `pip install -r requirements.txt` (ultralytics pulls a matching torch),
- copies `server.py` **and bakes the two `.pt` weight files into the image**,
- starts `python server.py` on `0.0.0.0:5000`.

The Electron UI is **not** in the image — it stays on the host (the Pi) and POSTs
to the container's published port on the laptop.

---

## Q4. Local vs Docker — which is better, and how do I toggle?

**Toggle:** `--mode local` ↔ `--mode docker` on `run.py`.

| | Local (venv) | Docker |
|---|---|---|
| Startup | fast | slower (first build is slow) |
| Reproducibility | depends on the host | identical everywhere |
| Best for | quick dev / a single machine | a clean, repeatable server you can rebuild anywhere |

For your setup the model server runs **in Docker on the laptop** — Docker is a
fine choice there: an x86 laptop builds the image quickly and you get a
self-contained server with the weights baked in. (On the laptop you could also
just use `--mode local`; Docker mainly buys you reproducibility.)

---

## Q5. I'm running on a Pi — anything special?

In the chosen architecture the **Pi runs only the UI**, so it needs **no Python,
torch, or models** — just Node.js for Electron:

```bash
sudo apt update && sudo apt install -y nodejs npm
npm install
npm start                                        # uses the share link by default
# (LAN-IP setup instead? override it:)
#   GCWD_SERVER=http://<laptop-ip>:5000 npm start
```

The UI points at `https://meet-marten-55.rshare.io` by default (the Release Share
link, baked into `main.js`); set `GCWD_SERVER` only to override it. The heavy
inference happens on the laptop, so the Pi stays light and responsive.

---

## Q6. Did you change the UI or the prediction logic? What got optimized?

**The visual UI and the prediction logic are unchanged.** Rotation, ROI
splitting, digit ordering, confidence averaging, and the best-of-2 / highest-
confidence weight selection in `server.py` are byte-for-byte the original.

What changed is plumbing + safety + speed, *around* that logic:

- **`main.js`**: the backend URL now defaults to the Release Share link
  (`https://meet-marten-55.rshare.io`) and can be overridden with `GCWD_SERVER`,
  instead of a hard-coded `127.0.0.1`. No UI/markup change.
- **Removed 4 unused npm deps**, incl. two heavy native ones
  (`opencv4nodejs-prebuilt-install`, `node-webcam`) that were never imported.
- **Backend, non-logic only**: decode each frame once instead of 2–3×; read
  `roi_paths[:3]` instead of `range(3)` (same top-3 crops for your top-view setup,
  but it no longer **crashes** when the model finds fewer than 3); skip a
  degenerate/empty box; silence YOLO's per-frame console spam. Same predictions.

---

## Q7. The big one: can I run the model server in Docker on my laptop and have the Pi just send the image and get the result back? Is that viable and right?

**Yes — that's a viable, standard, and (for you) the *right* design.** It's the
classic "thin edge client + inference server" pattern:

```
   Pi (camera + Electron UI)                 Laptop (Docker model server)
   ──────────────────────────                ────────────────────────────
   GCWD_SERVER=http://<laptop-ip>:5000       python run.py --mode docker --lan
   npm start            ── POST /predict ──▶ 0.0.0.0:5000  (YOLO inference)
                        ◀── {prediction} ──
```

**Why it's the right call here:**

- A Pi is **slow** at two YOLO models on CPU; your laptop is far faster.
- The network cost is tiny — a small JPEG out, a few bytes of JSON back. Latency
  is dominated by inference, not transfer.
- The Pi stays simple: **no torch, no models, no Python** — just the camera + UI.

**Two ways to address the laptop from the Pi:**

- **A fixed share link (recommended — no IPs to chase).** Run the container in
  the background and expose it with the **Release Share** Docker Desktop
  extension (release.com), which gives a public `https://meet-marten-55.rshare.io/` URL.
  Any tunnel (ngrok / Cloudflare / VS Code dev tunnels) works the same way.
  ```powershell
  python run.py --mode docker --detach          # background container, auto-restart
  # then Docker Desktop -> Release Share -> share port 5000 -> copy the rshare.io URL
  ```
  ```bash
  # Pi:
  GCWD_SERVER=https://meet-marten-55.rshare.io npm start
  ```
  ⚠️ Make sure the link is **stable** — if the service mints a new random
  subdomain per share, fix/reserve the name or you're back to editing the Pi.
  This is why a share link beats a raw IP: it doesn't change when your DHCP lease
  or Wi-Fi does.

- **The laptop's LAN IP (same Wi-Fi, no external service).**
  ```powershell
  python run.py --mode docker --lan
  ipconfig                                       # note the IPv4, e.g. 192.168.1.50
  ```
  ```bash
  GCWD_SERVER=http://192.168.1.50:5000 npm start
  ```

**Things to get right (the usual gotchas):**

1. **Share link:** the container only needs the default `127.0.0.1:5000` publish
   (Release Share reaches it on localhost) — `--detach` does this. **LAN IP:** you
   need `--lan` (publishes on all interfaces) or the Pi can't reach it.
2. **Same network** (LAN-IP option only) and **firewall:** allow inbound TCP
   **5000** on the laptop (Windows prompts the first time → *Allow access*).
3. **DHCP changes the LAN IP** — the share link avoids this; with a raw IP,
   reserve a static IP on your router or use the laptop's hostname.
4. **The laptop must be on** whenever the Pi is used — the Pi depends on it.

**Is this "efficient" with multiple systems running in parallel?** Two readings:

- *Many Pis, one laptop server:* yes — run **one** container on the laptop, bind
  it on the LAN (`--lan`), and every Pi POSTs to the same `http://<laptop-ip>:5000`.
  The server handles requests one after another. Flask's dev server is
  single-threaded, so if several Pis fire at the exact same instant they queue
  (fine for a few devices clicking occasionally; for heavy concurrency you'd put
  it behind a proper WSGI server like gunicorn with workers — ask if you want that).
- *Many identical laptop/edge servers:* that's the "build once, share the image"
  story — build the image once and `docker push` to a registry (Docker Hub /
  GHCR), then each server `docker pull`s it. No registry? Move it as a file:
  `docker save img | gzip > img.tgz` → `docker load < img.tgz`.

**Bottom line:** laptop-as-Docker-server + Pi-as-client is the correct, efficient
shape for this project. One server, many thin Pi clients pointing at it.

---

## Q8. So what exactly do I run? (detailed runbook per case)

Quick map first, then full step-by-step below:

| Case | Server runs on | UI runs on | Jump to |
|------|----------------|------------|---------|
| **A — Recommended split** | laptop (Docker) | Pi | [Case A](#case-a--recommended-docker-server-on-laptop--ui-on-pi) |
| B — Split, no Docker | laptop (native) | Pi | [Case B](#case-b--split-but-server-runs-natively-on-the-laptop-no-docker) |
| C — All on one machine | one box | same box | [Case C](#case-c--everything-on-one-machine-devdemo) |
| D — All on the Pi | Pi | Pi | [Case D](#case-d--everything-on-the-pi-no-laptop) |
| E — Ship image to others | build box → targets | n/a | [Case E](#case-e--build-once-and-share-the-image-to-other-servers) |

> **Note on commands.** The laptop examples use **Windows PowerShell** (your
> machine). The Pi examples use its **Linux shell (bash)**. The one thing that
> differs is how you set an environment variable for one command:
> - PowerShell: `$env:GCWD_SERVER="http://..."; npm start`
> - bash: `GCWD_SERVER=http://... npm start`

---

### Case A — Recommended: Docker server on laptop + UI on Pi

The laptop runs the model in a container; the Pi only captures and displays.
There are two ways for the Pi to reach the laptop — a **fixed share link**
(A.1, no IPs to chase) or the **laptop's LAN IP** (A.2). Pick one.

**On the laptop (one-time setup, both options):**

1. Install **Docker Desktop** and make sure it's running (whale icon in the tray).
2. Open PowerShell **in the project folder**:
   ```powershell
   cd C:\Users\LENOVO\Downloads\V_SEMESTER\IFP\Gas_Cylinder_Weight_Detection
   ```

#### A.1 — Fixed share link (Release Share) — recommended, no IP edits

**Create and run the container in the background** (auto-restarts when Docker
starts, so it's already up after a reboot):

```powershell
python run.py --mode docker --detach
```

> Equivalent raw Docker, if you prefer:
> ```powershell
> docker build -t gcwd-backend .
> docker run -d --name gcwd-backend --restart unless-stopped -p 5000:5000 gcwd-backend
> ```

**Get the link:** in Docker Desktop open the **Release Share** extension, share
the `gcwd-backend` container's port **5000**, and copy the
`https://meet-marten-55.rshare.io/` URL it gives you.

**Verify it works** (from anywhere):
```powershell
curl https://meet-marten-55.rshare.io/health        # -> {"status":"ok"}
```

**On the Pi** (only Node.js needed — no Python/torch/models):
```bash
sudo apt update && sudo apt install -y nodejs npm
cd Gas_Cylinder_Weight_Detection
npm install
npm start            # uses https://meet-marten-55.rshare.io (the default in main.js)
```

> `https://meet-marten-55.rshare.io` is baked into `main.js` as the default, so
> `npm start` alone works. ⚠️ If Release Share gives a **new random name** next
> time you share, either update `DEFAULT_SERVER` in `main.js` or override per-run:
> `GCWD_SERVER=https://<new-name>.rshare.io npm start`. Reserve/fix the name in
> the extension if you can, so it never changes.

**Manage the container:** `docker logs -f gcwd-backend` (watch) ·
`docker stop gcwd-backend` / `docker start gcwd-backend` (off/on).

#### A.2 — Same Wi-Fi, laptop's LAN IP (no external service)

```powershell
# laptop — run in the foreground, exposed on the LAN:
python run.py --mode docker --lan
ipconfig                                     # note the IPv4, e.g. 192.168.1.50
```
Allow inbound TCP **5000** through the firewall when Windows prompts (or
pre-authorize as Administrator:
`New-NetFirewallRule -DisplayName "GCWD 5000" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow`).

```bash
# Pi:
npm install
GCWD_SERVER=http://192.168.1.50:5000 npm start    # use YOUR laptop IP
```

Verify from the Pi: `curl http://192.168.1.50:5000/health` → `{"status":"ok"}`.
If it fails: same Wi-Fi? firewall allowed? used `--lan`?

**Either way:** the UI window opens → **Start** → **Capture**; the frame goes to
the laptop and the predicted weight comes back.

---

### Case B — Split, but server runs natively on the laptop (no Docker)

Same as Case A, but skip Docker on the laptop (useful if Docker isn't installed).

**On the laptop:**
```powershell
cd C:\Users\LENOVO\Downloads\V_SEMESTER\IFP\Gas_Cylinder_Weight_Detection
pip install -r requirements.txt          # one-time
python run.py --mode local --lan         # --lan binds 0.0.0.0 so the Pi can reach it
ipconfig                                 # note the IPv4 for the Pi
```

**On the Pi:** identical to Case A:
```bash
GCWD_SERVER=http://192.168.1.50:5000 npm start
```

Firewall/IP/same-network notes from Case A apply here too.

---

### Case C — Everything on one machine (dev/demo)

Server and UI on the **same** computer — quickest way to test. The launcher
starts both and waits for the backend before opening the window.

```powershell
# one-time
pip install -r requirements.txt
npm install

# every time
python run.py --mode local --frontend
```

- No IP, `--lan`, or firewall needed (it talks to `127.0.0.1`).
- Want the container instead of native Python? `python run.py --mode docker --frontend`.
- `Ctrl+C` stops both the backend and the UI.

---

### Case D — Everything on the Pi (no laptop)

The Pi runs both the model server and the UI. Slower inference (Pi CPU), but no
second machine. Use **64-bit Raspberry Pi OS**.

```bash
# one-time
sudo apt update
sudo apt install -y python3-pip python3-venv nodejs npm libgl1 libglib2.0-0
cd Gas_Cylinder_Weight_Detection
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # downloads torch — slow on an SD card, one-time
npm install

# every time
source .venv/bin/activate
python run.py --mode local --frontend
```

Prefer **local** mode here (lighter than Docker on a Pi). `Ctrl+C` stops both.

---

### Case E — Build once and share the image to other servers

When several machines should run the *same* server image without each rebuilding.

**Option 1 — via a registry (Docker Hub / GHCR):**

```powershell
# on the build machine (tag with your registry username)
docker build -t youruser/gcwd-backend:1.0 .
docker login
docker push youruser/gcwd-backend:1.0
```
```bash
# on each target machine
docker pull youruser/gcwd-backend:1.0
docker run --rm -p 5000:5000 youruser/gcwd-backend:1.0      # add the IP-bind if you want LAN
```

> Building for a *different* CPU than the build machine (e.g. building on an x86
> laptop for an arm64 Pi)? Cross-build and push in one step:
> ```powershell
> docker buildx build --platform linux/arm64 -t youruser/gcwd-backend:1.0 --push .
> ```

**Option 2 — no registry, move a file (USB / scp):**

```powershell
# on the build machine
docker build -t gcwd-backend .
docker save gcwd-backend | gzip > gcwd-backend.tgz
```
```bash
# copy gcwd-backend.tgz to the target, then:
docker load < gcwd-backend.tgz
docker run --rm -p 5000:5000 gcwd-backend
```

Either way, point each UI at that server with
`GCWD_SERVER=http://<server-ip>:5000`.
