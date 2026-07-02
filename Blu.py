#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["bleak"]
# ///

import argparse
import asyncio
import sys
from bleak import BleakScanner

CLEAR_SCREEN = "\033[H\033[J"  # move cursor home + clear from cursor down

def enable_ansi():
    # Legacy Windows consoles (cmd/conhost) ignore ANSI codes unless
    # virtual terminal processing is switched on for the session.
    if sys.platform != "win32":
        return
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
    mode = ctypes.c_uint32()
    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)

async def run_scanner(interval: float, name_filter: str | None):
    print("Starting BLE scanner — press Ctrl+C to stop...")
    await asyncio.sleep(1)  # let the message show before first clear

    while True:
        devices_dict = await BleakScanner.discover(timeout=interval, return_adv=True)

        devices = devices_dict.items()
        if name_filter:
            devices = [
                (address, pair) for address, pair in devices
                if name_filter.lower() in (pair[0].name or "").lower()
            ]

        sorted_devices = sorted(
            devices,
            key=lambda item: item[1][1].rssi,
            reverse=True
        )

        print(CLEAR_SCREEN, end="")
        print("BLE Scanner — press Ctrl+C to stop\n")
        print(f"Found {len(sorted_devices)} device(s):")
        print(f"{'Device Name':<30} | {'Address':<36} | {'Signal (RSSI)'}")
        print("-" * 80)

        for address, (device, adv_data) in sorted_devices:
            name = device.name if device.name else "Unknown Device"
            print(f"{name:<30} | {address:<36} | {adv_data.rssi} dBm")

def show_menu():
    print(CLEAR_SCREEN, end="")
    print("=" * 40)
    print(" BLE Scanner")
    print("=" * 40)
    input("\nPress Enter to begin scanning...")

def main():
    parser = argparse.ArgumentParser(description="Continuously scan for nearby BLE devices.")
    parser.add_argument("-i", "--interval", type=float, default=2.0,
                         help="Scan window per cycle in seconds (default: 2.0)")
    parser.add_argument("-f", "--filter", type=str, default=None,
                         help="Only show devices whose name contains this substring")
    args = parser.parse_args()

    enable_ansi()
    show_menu()
    try:
        asyncio.run(run_scanner(args.interval, args.filter))
    except KeyboardInterrupt:
        print("\nStopped.")

if __name__ == "__main__":
    main()
