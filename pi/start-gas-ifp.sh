#!/usr/bin/env bash
# Launches the Gas IFP Electron UI on the Pi at desktop login.
# Logs everything to ~/gas-ifp.log so you can debug a failed start.
set -u

LOG="$HOME/gas-ifp.log"
# Where the project lives on the Pi. Override by exporting GAS_IFP_DIR.
PROJECT_DIR="${GAS_IFP_DIR:-$HOME/Desktop/Gas_Cylinder_Weight_Detection-ananth}"

echo "==== $(date) starting Gas IFP ====" >> "$LOG"

# Make sure node/npm are found even in a minimal desktop session.
export PATH="/usr/local/bin:/usr/bin:/bin:$PATH"
# If you installed Node via nvm instead of apt, uncomment these:
# export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

# Launch full-screen (kiosk). Set to 0 to run windowed for debugging.
export GCWD_KIOSK=1

# Optional: force a specific backend URL. If you leave this commented, the UI
# uses the default baked into main.js (the Release Share link).
# export GCWD_SERVER="https://meet-marten-55.rshare.io"

# Wait (up to ~60s) for the network, since the app talks to a remote server.
for _ in $(seq 1 30); do
  ping -c1 -W1 8.8.8.8 >/dev/null 2>&1 && break
  sleep 2
done

cd "$PROJECT_DIR" || { echo "ERROR: project dir not found: $PROJECT_DIR" >> "$LOG"; exit 1; }

# First-run convenience: install deps if node_modules is missing.
if [ ! -d node_modules ]; then
  echo "installing npm deps (first run)..." >> "$LOG"
  npm install >> "$LOG" 2>&1
fi

echo "launching: npm start" >> "$LOG"
exec npm start >> "$LOG" 2>&1
