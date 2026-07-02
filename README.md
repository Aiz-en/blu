# blu

A tiny command-line Bluetooth Low Energy (BLE) scanner for macOS. It continuously
scans for nearby BLE devices and shows them in a live-updating table sorted by
signal strength.

```
Device Name                    | Address                              | Signal (RSSI)
--------------------------------------------------------------------------------
Isaac's AirPods Pro            | 1B2M2Y8A-...                         | -42 dBm
Unknown Device                 | 5D41402A-...                         | -67 dBm
```

## Install

The script manages its own dependencies via [uv](https://docs.astral.sh/uv/) —
no virtualenv or pip needed.

```sh
brew install uv
git clone https://github.com/Aiz-en/blu.git
ln -s "$PWD/blu/Blu.py" /opt/homebrew/bin/blu
```

## Usage

```sh
blu                # scan everything
blu -i 5           # 5-second scan window per refresh (default: 2)
blu -f airpods     # only show devices whose name contains "airpods"
```

Press `Ctrl+C` to stop.

Note: on macOS, addresses are per-device UUIDs assigned by CoreBluetooth, not
real MAC addresses, and they can change between runs. The first run may ask for
permission to use Bluetooth — that's expected.
