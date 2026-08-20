#!/usr/bin/env python3
"""Print an FFR seed's flag set.

    python3 tools/ffr_flags/decode.py seed.nes
    python3 tools/ffr_flags/decode.py seed.nes --logic
    python3 tools/ffr_flags/decode.py --flags "4-9-7" "g5jrLtdMmcv8HX6L..."
    python3 tools/ffr_flags/decode.py --flags "4-9-7" "https://4-9-7.finalfantasyrandomizer.com/?s=..&f=.."

--logic narrows the dump to the flags that change where you can go, which is
what the tracker cares about. --json prints everything for a script to read.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ffr_flags  # noqa: E402

# The flags that move the logic, grouped the way FFR's own Overworld tab is.
# Anything not listed here still decodes; it just does not affect reachability.
LOGIC_FLAGS = [
    ("Overworld shape", [
        "MapOpenProgression", "MapOpenProgressionExtended", "MapOpenProgressionDocks",
        "MapAirshipDock", "MapBahamutCardiaDock", "MapLefeinRiver", "MapBridgeLefein",
        "MapGaiaMountainPass", "MapHighwayToOrdeals", "MapRiverToMelmond",
        "MapSardasForest", "MapAirshipHike", "MapCardiaLandBridge",
        "OwMapExchange", "OwShuffledAccess",
    ]),
    ("Vehicles", ["AirBoat", "FreeShip", "FreeCanal", "FreeCanoe", "FreeAirship",
                  "FreeBridge", "DockAnywhere"]),
    ("Free items", ["FreeLute", "FreeRod", "FreeTail"]),
    ("Early NPCs", ["EarlyKing", "EarlySarda", "EarlySage", "EarlyOrdeals"]),
    ("Goal", ["ShardHunt", "ShardCount", "OrbsRequiredCount", "OrbsRequiredMode",
              "ChaosRush", "ExitToFR", "ToFRMode", "GameMode"]),
    ("Shuffles that move checks", ["Entrances", "Floors", "Towns", "Treasures",
                                   "Shops", "NPCItems", "NPCFetchItems", "TitansTrove"]),
    ("Incentives", ["IncentivizeIceCave", "IncentivizeOrdeals", "IncentivizeMarsh",
                    "IncentivizeMarshKeyLocked", "IncentivizeTitansTrove",
                    "IncentivizeEarth", "IncentivizeVolcano", "IncentivizeSkyPalace",
                    "IncentivizeSeaShrine", "IncentivizeConeria", "IncentivizeCardia",
                    "IncentivizeFetchNPCs", "IncentivizeFreeNPCs",
                    "IncentivizeFetchItems", "IncentivizeMainItems"]),
]


def show(value, entry=None):
    if value is None:
        return "random"          # a tri-state left unset, rolled at generation
    if value is True:
        return "on"
    if value is False:
        return "off"
    if entry and entry.get("names"):
        name = entry["names"].get(str(value))
        if name:
            return "%s (%d)" % (name, value)
    return str(value)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", nargs="?", help="an FFR .nes")
    ap.add_argument("--flags", nargs=2, metavar=("VERSION", "FLAGS"),
                    help="decode a bare flag string or permalink instead of a ROM")
    ap.add_argument("--logic", action="store_true",
                    help="only the flags that change reachability")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.flags:
        version, text = args.flags
        schema = ffr_flags.load_schema(version)
        if schema is None:
            raise SystemExit("no schema for FFR " + version)
        info = {"Version": version, "Seed": "?"}
        flags = ffr_flags.decode(ffr_flags.permalink_flags(text), schema)
    elif args.rom:
        with open(os.path.expanduser(args.rom), "rb") as handle:
            info, flags = ffr_flags.decode_rom(handle.read())
        schema = ffr_flags.load_schema(info["Version"])
    else:
        ap.error("give a ROM or --flags")

    entries = {e["name"]: e for e in schema["properties"]}

    if args.json:
        json.dump({"info": info, "flags": flags}, sys.stdout, indent=1, sort_keys=True)
        sys.stdout.write("\n")
        return

    print("seed %s, FFR %s" % (info.get("Seed", "?"), info["Version"]))
    if not args.logic:
        for name in sorted(flags):
            print("  %-40s %s" % (name, show(flags[name], entries.get(name))))
        return

    for heading, names in LOGIC_FLAGS:
        present = [n for n in names if n in flags]
        if not present:
            continue
        print("\n%s" % heading)
        for name in present:
            print("  %-40s %s" % (name, show(flags[name], entries.get(name))))
    missing = [n for _, names in LOGIC_FLAGS for n in names if n not in flags]
    if missing:
        print("\nnot in this FFR version: %s" % ", ".join(sorted(missing)))


if __name__ == "__main__":
    # Being piped into head is not an error worth a traceback.
    try:
        import signal
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (ImportError, AttributeError, ValueError):
        pass
    main()
