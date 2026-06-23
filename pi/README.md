# Auto-start the Gas IFP app on the Pi (kiosk mode)

Make the Raspberry Pi boot straight into the app: auto-login → desktop →
`npm start` automatically.

## Quick setup

On the Pi, from inside the project folder:

```bash
git pull origin ananth
chmod +x pi/*.sh
bash pi/setup-autostart.sh
sudo reboot
```

After reboot the Pi logs in as `gas-ifp` on its own and the UI launches. Logs go
to `~/gas-ifp.log`.

## What it does (and why no password in code)

The script does three things:

1. **`raspi-config nonint do_boot_behaviour B4`** — boot to the desktop, **auto
   logged-in** as the current user. This is the right way to "log in
   automatically": the OS handles it, so the password is **never** stored in any
   script. (Hardcoding a password would be insecure and is not needed.)
2. Installs `start-gas-ifp.sh` to your home folder.
3. Adds `~/.config/autostart/gas-ifp.desktop` so the launcher runs when the
   desktop session starts.

`start-gas-ifp.sh` waits for the network, `cd`s into the project, **activates the
Python venv `env`**, installs Node deps on first run, then launches the app
full-screen.

### What it launches (and the two modes)

By default it runs the **full local stack on the Pi** (Python backend + UI):
`python run.py --mode local --frontend`. That's why it activates the `env` venv —
the Python/YOLO deps live there. No laptop needed.

Override either of these by exporting them before the script runs (or editing the
defaults at the top of `start-gas-ifp.sh`):

| Variable | Default | Purpose |
|---|---|---|
| `GAS_IFP_DIR` | `~/Desktop/Gas_Cylinder_Weight_Detection-ananth` | project location |
| `GAS_IFP_VENV` | tries `~/env`, then `<project>/env` | which venv to activate |
| `GAS_IFP_CMD` | `python run.py --mode local --frontend` | what to launch |

To use the **laptop-as-server (Release Share)** setup instead of running locally,
set `GAS_IFP_CMD="npm start"` — then it just opens the UI pointing at the remote
server and the venv isn't needed.

## If the app does not start after reboot

Auto-login worked but the app didn't launch → your desktop session isn't reading
the XDG autostart entry. That happens on Raspberry Pi OS **Bookworm (Wayland)**.
Check your compositor:

```bash
echo "$XDG_SESSION_TYPE"      # x11 or wayland
echo "$XDG_CURRENT_DESKTOP"
```

**wayfire** (common on Pi 4) — add to `~/.config/wayfire.ini`:
```ini
[autostart]
gasifp = /home/gas-ifp/start-gas-ifp.sh
```

**labwc** (newer default) — add to `~/.config/labwc/autostart` (create it):
```bash
/home/gas-ifp/start-gas-ifp.sh &
```

Then `sudo reboot`.

## Full-screen kiosk

This is already wired up: `start-gas-ifp.sh` exports `GCWD_KIOSK=1`, and `main.js`
opens full-screen (no window chrome) when that is set. Everywhere else (`npm start`
during dev) stays windowed.

- Run windowed on the Pi instead: set `export GCWD_KIOSK=0` in `start-gas-ifp.sh`.
- Exit the kiosk window: `Alt+F4`, or SSH in and `pkill -f electron`.

Optionally stop the screen from blanking (X11) — add to `start-gas-ifp.sh`:
`xset s off; xset -dpms`.

## Undo / disable

```bash
rm ~/.config/autostart/gas-ifp.desktop      # stop auto-launching the app
sudo raspi-config nonint do_boot_behaviour B3   # auto-login WITHOUT it? B1=console, B3=desktop no autologin
```

## Note
The app only *reads weights* when the laptop's backend (Release Share) is up. If
the Pi boots before the laptop/container is reachable, the UI still opens — it
just errors on Capture until the server is available.
