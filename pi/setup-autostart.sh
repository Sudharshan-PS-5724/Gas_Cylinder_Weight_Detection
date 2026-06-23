#!/usr/bin/env bash
# One-time setup so the Pi boots straight into the Gas IFP app.
#   1) enables desktop auto-login (no password prompt at boot)
#   2) installs the launcher script
#   3) registers it to run when the desktop session starts
#
# Run on the Pi from inside the project:  bash pi/setup-autostart.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

echo "[1/3] enabling desktop auto-login for user '$USER' ..."
# B4 = boot to desktop GUI, automatically logged in as the current user.
sudo raspi-config nonint do_boot_behaviour B4

echo "[2/3] installing launcher to ~/start-gas-ifp.sh ..."
install -m 755 "$HERE/start-gas-ifp.sh" "$HOME/start-gas-ifp.sh"

echo "[3/3] registering autostart entry ..."
mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/gas-ifp.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Gas IFP
Comment=Launch the Gas Cylinder Weight Detection UI at login
Exec=$HOME/start-gas-ifp.sh
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

echo
echo "Done. Reboot to test:  sudo reboot"
echo "Logs will appear in:   ~/gas-ifp.log"
echo
echo "If the app does NOT start after reboot (Wayland on Bookworm), see pi/README.md"
echo "for the wayfire/labwc autostart fallback."
