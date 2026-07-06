# blu

A tiny command-line Bluetooth Low Energy (BLE) scanner for macOS and Windows.
It continuously scans for nearby BLE devices and shows them in a live-updating
table sorted by signal strength.

```
Device Name                    | Address                              | Signal (RSSI)
--------------------------------------------------------------------------------
Isaac's AirPods Pro            | 1B2M2Y8A-...                         | -42 dBm
[Samsung device]               | 5D41402A-...                         | -67 dBm
[Vendor 0x0313]                | 7D793037-...                         | -81 dBm
```

For unnamed devices, blu falls back through several sources to identify them:
the advertised name, then the OS-cached name, then the manufacturer's Bluetooth
company ID (shown as a vendor name when known, or the raw ID otherwise).

## Install

The script manages its own dependencies via [uv](https://docs.astral.sh/uv/) —
no virtualenv or pip needed.

### macOS

```sh
brew install uv
git clone https://github.com/Aiz-en/blu.git
ln -s "$PWD/blu/Blu.py" /opt/homebrew/bin/blu
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

Press `Ctrl+C` to stop.

Note: on macOS, addresses are per-device UUIDs assigned by CoreBluetooth, not
real MAC addresses, and they can change between runs. The first run may ask for
permission to use Bluetooth — that's expected. On Windows, addresses are the
devices' actual MAC addresses.
