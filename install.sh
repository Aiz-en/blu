#!/usr/bin/env bash
# Installs blu — a CLI BLE scanner — and puts a `blu` command on your PATH.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Aiz-en/blu/main/install.sh | bash

set -euo pipefail

install_dir="${XDG_DATA_HOME:-$HOME/.local/share}/blu"
bin_dir="$HOME/.local/bin"

# On Linux, bleak talks to the BlueZ daemon (bluetoothd) over D-Bus — the
# bluetoothctl CLI isn't required. Warn early if the service isn't running,
# rather than failing with a cryptic D-Bus error at scan time.
if [ "$(uname -s)" = "Linux" ] && \
   [ "$(systemctl is-active bluetooth 2>/dev/null || echo inactive)" != "active" ]; then
    echo "Warning: the BlueZ bluetooth service isn't active. Install and start it, e.g.:"
    echo "  Arch:          sudo pacman -S bluez bluez-utils"
    echo "  Debian/Ubuntu: sudo apt install bluez"
    echo "  Fedora:        sudo dnf install bluez"
    echo "and make sure the service is running: sudo systemctl enable --now bluetooth"
    echo
fi

# uv runs the script and manages its Python + dependencies
if ! command -v uv >/dev/null 2>&1; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

if [ -d "$install_dir/.git" ]; then
    echo "Updating existing install..."
    git -C "$install_dir" pull --ff-only
elif command -v git >/dev/null 2>&1; then
    git clone https://github.com/Aiz-en/blu.git "$install_dir"
else
    mkdir -p "$install_dir"
    curl -fsSL https://raw.githubusercontent.com/Aiz-en/blu/main/Blu.py \
        -o "$install_dir/Blu.py"
fi

chmod +x "$install_dir/Blu.py"

# `blu` command: a symlink into a PATH directory
mkdir -p "$bin_dir"
ln -sf "$install_dir/Blu.py" "$bin_dir/blu"

echo "Done. Installed to $bin_dir/blu"
case ":$PATH:" in
    *":$bin_dir:"*) echo "Run: blu" ;;
    *) echo "Add $bin_dir to your PATH, then run: blu" ;;
esac
