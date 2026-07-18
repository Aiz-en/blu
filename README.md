# blu

A command-line Bluetooth Low Energy (BLE) scanner for macOS, Linux, and Windows.
Continuously scans for BLE devices and shows them in a live
table sorted by signal strength.

```
Device Name                    | Address                              | RSSI     | Distance
------------------------------------------------------------------------------------------
John's AirPods Pro             | 1B2M2Y8A-...                         | -42 dBm  | ~1.1 m
[Samsung device]               | 5D41402A-...                         | -67 dBm  | ~2.5 m*
[Vendor 0x0313]                | 7D793037-...                         | -81 dBm  | ~13 m*
```

For unnamed devices, blu falls back through several sources to identify them:
the advertised name, then the OS-cached name, then the manufacturer's Bluetooth
company ID (shown as a vendor name when known, or the raw ID otherwise).

Distance is a rough estimate from RSSI and the device's advertised TX power,
using a free-space path-loss model. Walls, bodies, and device orientation all
skew it, so treat it as an order of magnitude, not a measurement. A `*` marks
devices that don't advertise TX power, where a typical reference is assumed.

## Install

The script manages its own dependencies via [uv](https://docs.astral.sh/uv/) —
no virtualenv or pip needed.

### macOS

```sh
brew install uv
git clone https://github.com/Aiz-en/blu.git
ln -s "$PWD/blu/Blu.py" /opt/homebrew/bin/blu
```

### Linux

blu talks to the BlueZ Bluetooth stack over D-Bus, so make sure it's installed
and running first:

```sh
sudo pacman -S bluez bluez-utils          # Arch
sudo apt install bluez                     # Debian/Ubuntu
sudo dnf install bluez                     # Fedora
sudo systemctl enable --now bluetooth
```

Then install blu:

```sh
curl -fsSL https://raw.githubusercontent.com/Aiz-en/blu/main/install.sh | bash
```

This installs uv if it's missing, clones blu to
`~/.local/share/blu`, and adds a `blu` command to `~/.local/bin` (make sure
that's on your PATH). To install manually instead:

```sh
git clone https://github.com/Aiz-en/blu.git
ln -s "$PWD/blu/Blu.py" ~/.local/bin/blu
```

### Windows

Run in PowerShell:

```powershell
irm https://raw.githubusercontent.com/Aiz-en/blu/main/install.ps1 | iex
```

This installs uv if it's missing, puts blu in `%LOCALAPPDATA%\Programs\blu`,
and adds a `blu` command to your PATH (open a new terminal afterwards).

## Usage

```sh
blu                # scan everything
blu -i 5           # 5-second scan window per refresh (default: 2)
blu -f airpods     # only show devices whose name contains "airpods"
```

Press `Space` to pause/resume the live table, `Ctrl+C` to stop.

Note: on macOS, addresses are per-device UUIDs assigned by CoreBluetooth, not
real MAC addresses, and they can change between runs. The first run may ask for
permission to use Bluetooth — that's expected. On Windows and Linux, addresses
are the devices' actual MAC addresses.
