#!/usr/bin/env python3
"""Turn ROM chest tile coordinates into map-image pixel coordinates.

Reads tools/chest_positions.json (from extract_chests.py) and
tools/map_calibration.json, writes tools/marker_positions.json:

    chest_index -> {"map": <maps.json name>, "x": px, "y": px}

Only maps present in the calibration file are emitted, so this grows one
dungeon at a time as calibrations are eyeballed and added.
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    with open(os.path.join(HERE, "chest_positions.json")) as f:
        chests = json.load(f)
    with open(os.path.join(HERE, "map_calibration.json")) as f:
        cal = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    return chests, cal


def region_for(cal_entry, col, row):
    for r in cal_entry["regions"]:
        rlo, rhi = r.get("rows", (0, 63))
        clo, chi = r.get("cols", (0, 63))
        if rlo <= row <= rhi and clo <= col <= chi:
            return r
    return None


def build(chests, cal):
    by_rom = {}
    for name, entry in cal.items():
        by_rom.setdefault(entry["rom_map_id"], []).append((name, entry))

    out = {}
    for idx, places in chests.items():
        # A chest index can sit on several tiles; each one wants its own marker,
        # so this collects a list rather than the last one seen.
        marks = []
        for pos in places:
            for name, entry in by_rom.get(pos["map_id"], []):
                r = region_for(entry, pos["tile_col"], pos["tile_row"])
                if r is None:
                    continue
                half = entry["tile_px"] // 2
                marks.append({
                    "map": name,
                    "x": r["offset_x"] + pos["tile_col"] * entry["tile_px"] + half,
                    "y": r["offset_y"] + pos["tile_row"] * entry["tile_px"] + half,
                })
                break
        if marks:
            out[int(idx)] = marks
    return out


def main():
    chests, cal = load()
    out = build(chests, cal)
    path = os.path.join(HERE, "marker_positions.json")
    with open(path, "w") as f:
        json.dump({str(k): out[k] for k in sorted(out)}, f, indent=1)
    per = {}
    n = 0
    for marks in out.values():
        for v in marks:
            per[v["map"]] = per.get(v["map"], 0) + 1
            n += 1
    print(f"wrote {path}: {n} markers for {len(out)} chests")
    for m in sorted(per):
        print(f"  {m}: {per[m]}")


if __name__ == "__main__":
    main()
