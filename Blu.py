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

# Bluetooth SIG "Company Identifiers" — the 16-bit code that leads a device's
# manufacturer-specific advertising data. Subset of the most common consumer
# vendors; the full registry has thousands of entries.
COMPANY_IDS = {
    0x0000: "Ericsson",
    0x0001: "Nokia",
    0x0002: "Intel",
    0x0006: "Microsoft",
    0x000D: "Texas Instruments",
    0x000F: "Broadcom",
    0x004C: "Apple",
    0x0059: "Nordic Semiconductor",
    0x0075: "Samsung",
    0x0087: "Garmin",
    0x00D7: "Qualcomm",
    0x00E0: "Google",
    0x0157: "Huami (Amazfit)",
    0x0171: "Amazon",
    0x0499: "Ruuvi",
}

def resolve_name(device, adv_data):
    """Best-effort human-readable name, trying several sources in order."""
    # 1. Name broadcast in the advertisement packet.
    if adv_data and adv_data.local_name:
        return adv_data.local_name

    # 2. Name cached by the OS from a previous connection.
    if device.name:
        return device.name

    # 3. No name at all — fall back to the manufacturer's company ID.
    if adv_data and adv_data.manufacturer_data:
        for company_id in adv_data.manufacturer_data:
            vendor = COMPANY_IDS.get(company_id)
            if vendor:
                return f"[{vendor} device]"
        first_id = next(iter(adv_data.manufacturer_data))
        return f"[Vendor 0x{first_id:04X}]"

    return "Unknown Device"

# Log-distance path-loss model: distance = 10 ^ ((rssi_at_1m - rssi) / (10 * n)).
# Advertised TX power is the strength at the antenna; free-space loss over the
# first meter at 2.4 GHz is ~41 dB, so expected RSSI at 1 m = tx_power - 41.
PATH_LOSS_AT_1M = 41
DEFAULT_RSSI_AT_1M = -59  # typical for BLE devices that don't advertise TX power
PATH_LOSS_EXPONENT = 2.0  # free space; indoors with walls it's closer to 2.5-4

def estimate_distance(rssi, tx_power):
    """Approximate distance in meters. Rough — RSSI varies with obstacles,
    orientation, and multipath, so treat this as an order of magnitude."""
    if tx_power is not None:
        rssi_at_1m = tx_power - PATH_LOSS_AT_1M
    else:
        rssi_at_1m = DEFAULT_RSSI_AT_1M
    return 10 ** ((rssi_at_1m - rssi) / (10 * PATH_LOSS_EXPONENT))

def format_distance(rssi, tx_power):
    distance = estimate_distance(rssi, tx_power)
    # * = device didn't advertise TX power, estimate uses an assumed reference
    marker = "" if tx_power is not None else "*"
    if distance >= 100:
        return f">100 m{marker}"
    if distance >= 10:
        return f"~{distance:.0f} m{marker}"
    return f"~{distance:.1f} m{marker}"

def enable_ansi():
    # Legacy Windows consoles (cmd/conhost) ignore ANSI codes unless virtual terminal processing is switched on for the session.
    if sys.platform != "win32":
        return
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
    mode = ctypes.c_uint32()
    if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)

def make_cbreak_stdin():
    """Switch the terminal to cbreak mode so single keypresses arrive without
    Enter. Returns a restore function, or None where it isn't needed (Windows
    reads keys via msvcrt; non-TTY stdin has no keyboard)."""
    if sys.platform == "win32" or not sys.stdin.isatty():
        return None
    import termios, tty
    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    return lambda: termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)

async def watch_keys(state: dict):
    """Background task: toggle state['paused'] whenever SPACE is pressed."""
    if not sys.stdin.isatty():
        return  # stdin is piped/redirected — no keyboard to watch
    if sys.platform == "win32":
        import msvcrt
        while True:
            while msvcrt.kbhit():
                if msvcrt.getwch() == " ":
                    state["paused"] = not state["paused"]
            await asyncio.sleep(0.05)
    else:
        import select
        while True:
            while select.select([sys.stdin], [], [], 0)[0]:
                if sys.stdin.read(1) == " ":
                    state["paused"] = not state["paused"]
            await asyncio.sleep(0.05)

async def run_scanner(interval: float, name_filter: str | None):
    print("Starting BLE scanner — press Ctrl+C to stop...")
    await asyncio.sleep(1)  # let the message show before first clear

    state = {"paused": False}
    key_task = asyncio.create_task(watch_keys(state))  # keep a reference so it isn't GC'd
    paused_shown = False

    while True:
        if state["paused"]:
            if not paused_shown:
                print("\nPaused — press SPACE to resume")
                paused_shown = True
            await asyncio.sleep(0.1)
            continue
        paused_shown = False

        devices_dict = await BleakScanner.discover(timeout=interval, return_adv=True)
        if state["paused"]:
            continue  # paused during the scan window — keep the last table frozen

        devices = devices_dict.items()
        if name_filter:
            devices = [
                (address, pair) for address, pair in devices
                if name_filter.lower() in resolve_name(pair[0], pair[1]).lower()
            ]

        sorted_devices = sorted(
            devices,
            key=lambda item: item[1][1].rssi,
            reverse=True
        )

        print(CLEAR_SCREEN, end="")
        print("BLE Scanner — SPACE to pause, Ctrl+C to stop\n")
        print(f"Found {len(sorted_devices)} device(s):")
        print(f"{'Device Name':<30} | {'Address':<36} | {'RSSI':<8} | {'Distance'}")
        print("-" * 90)

        any_assumed = False
        for address, (device, adv_data) in sorted_devices:
            name = resolve_name(device, adv_data)
            rssi_str = f"{adv_data.rssi} dBm"
            distance = format_distance(adv_data.rssi, adv_data.tx_power)
            if adv_data.tx_power is None:
                any_assumed = True
            print(f"{name:<30} | {address:<36} | {rssi_str:<8} | {distance}")

        if any_assumed:
            print(f"\n* no TX power advertised; assumes {DEFAULT_RSSI_AT_1M} dBm at 1 m")

BANNER = r"""__/\\\\\\\\\\\\\____/\\\______________/\\\________/\\\_        
 _\/\\\/////////\\\_\/\\\_____________\/\\\_______\/\\\_       
  _\/\\\_______\/\\\_\/\\\_____________\/\\\_______\/\\\_      
   _\/\\\\\\\\\\\\\\__\/\\\_____________\/\\\_______\/\\\_     
    _\/\\\/////////\\\_\/\\\_____________\/\\\_______\/\\\_    
     _\/\\\_______\/\\\_\/\\\_____________\/\\\_______\/\\\_   
      _\/\\\_______\/\\\_\/\\\_____________\//\\\______/\\\__  
       _\/\\\\\\\\\\\\\/__\/\\\\\\\\\\\\\\\__\///\\\\\\\\\/___ 
        _\/////////////____\///////////////_____\/////////_____"""

# Width of the widest banner row, so the rules match the art exactly.
BANNER_WIDTH = max(len(line) for line in BANNER.splitlines())

def show_menu():
    print(CLEAR_SCREEN, end="")
    print("=" * BANNER_WIDTH)
    print(BANNER)
    print("=" * BANNER_WIDTH)
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
    restore_terminal = make_cbreak_stdin()
    try:
        asyncio.run(run_scanner(args.interval, args.filter))
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        if restore_terminal:
            restore_terminal()

if __name__ == "__main__":
    main()
