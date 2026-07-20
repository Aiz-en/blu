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

# A small subset of IEEE OUI (MAC-prefix) → vendor assignments, for public
# addresses. BLE devices frequently randomize their MAC for privacy, so this
# often won't resolve — the manufacturer company ID above is the primary,
# more reliable vendor signal. The full IEEE registry has tens of thousands of
# entries; this is just a handful of common ones.
OUI_VENDORS = {
    "F0:18:98": "Apple",
    "AC:BC:32": "Apple",
    "3C:15:C2": "Apple",
    "A4:83:E7": "Apple",
    "5C:0A:5B": "Samsung",
    "AC:5F:3E": "Samsung",
    "F4:F5:D8": "Google",
    "3C:5A:B4": "Google",
    "74:75:48": "Amazon",
    "B8:27:EB": "Raspberry Pi",
    "DC:A6:32": "Raspberry Pi",
    "E4:5F:01": "Raspberry Pi",
    "24:6F:28": "Espressif",
    "30:AE:A4": "Espressif",
    "A0:20:A6": "Espressif",
}

# Device-category classification. The 16-bit assigned number carried inside a
# standard BLE service UUID is the most reliable hint; a name-keyword pass is
# the fallback. Both are best-guess — never authoritative.
BLUETOOTH_BASE_SUFFIX = "-0000-1000-8000-00805f9b34fb"

GATT_SERVICE_CATEGORIES = {
    0x1812: "input",     # Human Interface Device
    0x180D: "wearable",  # Heart Rate
    0x183E: "wearable",  # Physical Activity Monitor
    0x1816: "fitness",   # Cycling Speed and Cadence
    0x1818: "fitness",   # Cycling Power
    0x1826: "fitness",   # Fitness Machine
    0x1808: "health",    # Glucose
    0x1809: "health",    # Health Thermometer
    0x1108: "audio",     # Headset
    0x110A: "audio",     # Audio Source
    0x110B: "audio",     # Audio Sink
    0x111E: "audio",     # Handsfree
    0x184E: "audio",     # Audio Stream Control (LE Audio)
    0xFEAA: "beacon",    # Eddystone
    0xFEED: "tag",       # Tile
}

# Service UUIDs too generic to reveal a category — skip them and keep looking.
GENERIC_SERVICE_UUIDS = {0x1800, 0x1801, 0x1804, 0x180A, 0x180F}

NAME_CATEGORY_KEYWORDS = [
    (("printer", "zebra", "brother", "label", "zpl"), "printer"),
    (("buds", "airpods", "headphone", "headset", "earbud", "earphone",
      "speaker", "soundbar", "jbl", "bose", "beats"), "audio"),
    (("watch", "band", "amazfit", "garmin", "whoop", "polar", "miband",
      "fitbit"), "wearable"),
    (("keyboard", "mouse", "trackpad", "stylus"), "input"),
    (("roku", "chromecast", "firetv", "bravia", "shield", " tv"), "tv/media"),
    (("iphone", "pixel", "galaxy", "oneplus", "phone"), "phone"),
    (("macbook", "laptop", "thinkpad", "surface", "desktop"), "computer"),
    (("tile", "airtag", "beacon", "ruuvi", "tracker"), "tag/beacon"),
    (("scale", "thermometer", "glucose", "oximeter"), "health"),
]

# BlueZ (Linux) caches per-device info beyond the live advertisement and exposes
# it in device.details["props"]. The freedesktop Icon name it assigns is the
# cleanest category signal.
BLUEZ_ICON_CATEGORIES = {
    "audio-card": "audio",
    "audio-headset": "audio",
    "audio-headphones": "audio",
    "audio-speakers": "audio",
    "input-keyboard": "input",
    "input-mouse": "input",
    "input-tablet": "input",
    "input-gaming": "input",
    "phone": "phone",
    "computer": "computer",
    "printer": "printer",
    "scanner": "printer",
    "camera-photo": "camera",
    "camera-video": "camera",
    "multimedia-player": "tv/media",
    "video-display": "tv/media",
    "network-wireless": "network",
}

# BLE "Appearance" category (the value's top 10 bits, i.e. appearance >> 6) →
# our category, for the well-established ones.
APPEARANCE_CATEGORIES = {
    1: "phone",
    2: "computer",
    3: "wearable",   # Watch
    5: "tv/media",   # Display
    15: "input",     # HID (keyboard/mouse/etc.)
}

def oui_prefix(address):
    """The 'XX:XX:XX' OUI of a colon-form MAC, or None (macOS reports an opaque
    CoreBluetooth UUID instead of a MAC, so there's no OUI to read)."""
    parts = address.split(":")
    if len(parts) == 6:
        return ":".join(parts[:3]).upper()
    return None

def resolve_vendor(device, adv_data):
    """Best-effort vendor, or None if it can't be attributed.

    For BLE the reliable signal is the 16-bit SIG company ID leading the
    manufacturer-specific advertising data; the MAC OUI is only a secondary
    hint (often randomized, and our table is a small subset of the registry)."""
    if adv_data and adv_data.manufacturer_data:
        for company_id in adv_data.manufacturer_data:
            vendor = COMPANY_IDS.get(company_id)
            if vendor:
                return vendor
    oui = oui_prefix(device.address)
    if oui:
        return OUI_VENDORS.get(oui)
    return None

def resolve_name(device, adv_data):
    """Best-effort human-readable name, trying several sources in order."""
    # 1. Name broadcast in the advertisement packet.
    if adv_data and adv_data.local_name:
        return adv_data.local_name

    # 2. Name cached by the OS from a previous connection.
    if device.name:
        return device.name

    # 3. No name at all — fall back to the vendor, then the raw company ID.
    vendor = resolve_vendor(device, adv_data)
    if vendor:
        return f"[{vendor} device]"
    if adv_data and adv_data.manufacturer_data:
        first_id = next(iter(adv_data.manufacturer_data))
        return f"[Vendor 0x{first_id:04X}]"

    return "Unknown Device"

def service_uuid_16bit(uuid):
    """The 16-bit assigned number of a standard Bluetooth SIG service UUID, or
    None for a vendor-specific 128-bit UUID."""
    u = uuid.lower()
    if u.startswith("0000") and u.endswith(BLUETOOTH_BASE_SUFFIX):
        try:
            return int(u[4:8], 16)
        except ValueError:
            return None
    return None

def category_from_uuids(uuids):
    """First category implied by a list of service UUIDs, or None."""
    for uuid in uuids or []:
        sid = service_uuid_16bit(uuid)
        if sid is None or sid in GENERIC_SERVICE_UUIDS:
            continue
        category = GATT_SERVICE_CATEGORIES.get(sid)
        if category:
            return category
    return None

def bluez_category(device):
    """Category hints BlueZ has already cached for a device (Linux only): the
    full known service-UUID list, the freedesktop Icon name, and the BLE
    Appearance value. Returns None on other platforms or when nothing is known."""
    details = getattr(device, "details", None)
    if not isinstance(details, dict):
        return None
    props = details.get("props")
    if not isinstance(props, dict):
        return None

    category = category_from_uuids(props.get("UUIDs"))
    if category:
        return category

    icon = props.get("Icon")
    if icon in BLUEZ_ICON_CATEGORIES:
        return BLUEZ_ICON_CATEGORIES[icon]

    appearance = props.get("Appearance")
    if isinstance(appearance, int):
        category = APPEARANCE_CATEGORIES.get(appearance >> 6)
        if category:
            return category
    return None

def classify_category(device, name, adv_data):
    """Best-guess device category, or '-' when nothing distinctive is known.
    Heuristic only, in order of reliability: service UUIDs in the live
    advertisement, then anything BlueZ has cached, then name keywords."""
    if adv_data:
        category = category_from_uuids(adv_data.service_uuids)
        if category:
            return category
    category = bluez_category(device)
    if category:
        return category
    lowered = (name or "").lower()
    for keywords, category in NAME_CATEGORY_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return category
    return "-"

def address_type(device):
    """'public', 'random', or None. Only BlueZ (Linux) reliably exposes the BLE
    address type in device.details, so this is best effort."""
    details = getattr(device, "details", None)
    if isinstance(details, dict):
        props = details.get("props")
        if isinstance(props, dict):
            at = props.get("AddressType")
            if at in ("public", "random"):
                return at
    return None

def is_interesting(device, adv_data):
    """Worth a second look when auditing your own RF environment: either
    unattributable (no name and no known vendor) or using a randomized private
    address (a device deliberately trying not to be tracked)."""
    has_name = bool((adv_data and adv_data.local_name) or device.name)
    has_vendor = resolve_vendor(device, adv_data) is not None
    randomized = address_type(device) == "random"
    return randomized or not (has_name or has_vendor)

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

NEAR_DEFAULT = -60  # dBm; at/above this a device is treated as "nearby"
BOLD = "\033[1m"
RESET = "\033[0m"

def passes_filters(device, adv_data, opts):
    """Apply the active display filters to a single device."""
    if opts.filter and opts.filter.lower() not in resolve_name(device, adv_data).lower():
        return False
    if opts.vendor:
        vendor = resolve_vendor(device, adv_data) or ""
        if opts.vendor.lower() not in vendor.lower():
            return False
    if opts.min_rssi is not None and adv_data.rssi < opts.min_rssi:
        return False
    if opts.unknown and not is_interesting(device, adv_data):
        return False
    return True

def active_filters(opts):
    """Human-readable summary of which filters are narrowing the view."""
    bits = []
    if opts.filter:
        bits.append(f"name~'{opts.filter}'")
    if opts.vendor:
        bits.append(f"vendor~'{opts.vendor}'")
    if opts.min_rssi is not None:
        bits.append(f"rssi>={opts.min_rssi}")
    if opts.unknown:
        bits.append("unknown/interesting only")
    return ", ".join(bits)

async def run_scanner(opts):
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

        devices_dict = await BleakScanner.discover(timeout=opts.interval, return_adv=True)
        if state["paused"]:
            continue  # paused during the scan window — keep the last table frozen

        devices = [
            (address, pair) for address, pair in devices_dict.items()
            if passes_filters(pair[0], pair[1], opts)
        ]
        sorted_devices = sorted(devices, key=lambda item: item[1][1].rssi, reverse=True)
        near_count = sum(1 for _, (_, adv) in sorted_devices if adv.rssi >= opts.near)

        print(CLEAR_SCREEN, end="")
        print("BLE Scanner — SPACE to pause, Ctrl+C to stop")
        filters = active_filters(opts)
        if filters:
            print(f"Filters: {filters}")
        print(f"\nFound {len(sorted_devices)} device(s) — "
              f"{near_count} near (>= {opts.near} dBm, shown in bold »)\n")
        header = (f"  {'Name':<18} | {'Vendor':<12} | {'Category':<9} | "
                  f"{'RSSI':<9} | {'Dist':<8} | Address")
        print(header)
        print("-" * max(len(header), 96))

        any_assumed = False
        for address, (device, adv_data) in sorted_devices:
            name = resolve_name(device, adv_data)
            vendor = resolve_vendor(device, adv_data) or "-"
            category = classify_category(device, name, adv_data)
            rssi_str = f"{adv_data.rssi} dBm"
            distance = format_distance(adv_data.rssi, adv_data.tx_power)
            if adv_data.tx_power is None:
                any_assumed = True
            near = adv_data.rssi >= opts.near
            mark = "» " if near else "  "
            row = (f"{mark}{name:<18.18} | {vendor:<12.12} | {category:<9.9} | "
                   f"{rssi_str:<9} | {distance:<8} | {address}")
            print(f"{BOLD}{row}{RESET}" if near else row)

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
    parser.add_argument("--vendor", type=str, default=None,
                         help="Only show devices whose resolved vendor contains this substring")
    parser.add_argument("--min-rssi", type=int, default=None, metavar="DBM",
                         help="Hide devices weaker than this RSSI, e.g. -70")
    parser.add_argument("--near", type=int, default=NEAR_DEFAULT, metavar="DBM",
                         help=f"RSSI at/above which a device is highlighted as near (default: {NEAR_DEFAULT})")
    parser.add_argument("--unknown", action="store_true",
                         help="Only show unattributable or randomized-address devices (RF audit view)")
    args = parser.parse_args()

    enable_ansi()
    show_menu()
    restore_terminal = make_cbreak_stdin()
    try:
        asyncio.run(run_scanner(args))
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        if restore_terminal:
            restore_terminal()

if __name__ == "__main__":
    main()
