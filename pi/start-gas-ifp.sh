#!/usr/bin/env bash
# Launches the Gas IFP app on the Pi at desktop login.
#   - activates the Python venv ('env') that holds the deps
#   - cd's into the project on the Desktop
#   - runs the full local stack (Python backend + Electron UI) full-screen
# Logs everything to ~/gas-ifp.log so you can debug a failed start.
set -u

LOG="$HOME/gas-ifp.log"
# Project location on the Pi. Override by exporting GAS_IFP_DIR.
PROJECT_DIR="${GAS_IFP_DIR:-$HOME/Desktop/Gas_Cylinder_Weight_Detection-ananth}"
# What to launch. Default: full local stack via the venv's python.
# For the laptop-server (Release Share) setup instead, use: GAS_IFP_CMD="npm start"
CMD="${GAS_IFP_CMD:-python run.py --mode local --frontend}"

echo "==== $(date) starting Gas IFP ====" >> "$LOG"

# Make sure node/npm are found even in a minimal desktop session.
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"

# Launch full-screen (kiosk). Set to 0 to run windowed for debugging.
export GCWD_KIOSK=1

# Optional: force a specific backend URL (only used in the 'npm start' setup).
# export GCWD_SERVER="https://meet-marten-55.rshare.io"

# Wait (up to ~60s) for the network.
for _ in $(seq 1 30); do
  ping -c1 -W1 8.8.8.8 >/dev/null 2>&1 && break
  sleep 2
done

cd "$PROJECT_DIR" || { echo "ERROR: project dir not found: $PROJECT_DIR" >> "$LOG"; exit 1; }

# Activate the Python venv that has the deps. Looks in GAS_IFP_VENV, then ~/env,
# then <project>/env — whichever exists first.
for cand in "${GAS_IFP_VENV:-}" "$HOME/env" "$PROJECT_DIR/env"; do
  if [ -n "$cand" ] && [ -f "$cand/bin/activate" ]; then
    # shellcheck disable=SC1090
    . "$cand/bin/activate"
    echo "activated venv: $cand" >> "$LOG"
    break
  fi
done

# First-run convenience: install Node deps if node_modules is missing.
if [ ! -d node_modules ]; then
  echo "installing npm deps (first run)..." >> "$LOG"
  npm install >> "$LOG" 2>&1
fi

echo "launching: $CMD" >> "$LOG"
# shellcheck disable=SC2086
exec $CMD >> "$LOG" 2>&1
