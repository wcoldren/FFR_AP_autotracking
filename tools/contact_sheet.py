#!/usr/bin/env python3
"""Crop a window around every proposed marker and tile them into one sheet.

Verifying a calibration means looking at whether each marker landed on a chest.
Doing that on the full map art does not work -- a seven-pixel error and a whole
misplaced row both went unnoticed that way. A grid of crops centred on each
marker does: a correct row is a row of centred chests, and a wrong one is
obvious at a glance.

One row per map, in the order given. Usage:
    tools/contact_sheet.py <proposal.json> <out.png> [map ...]
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pngio  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
CROP = 30          # source pixels around the marker
ZOOM = 2
CELL = CROP * ZOOM
PAD = 2


def marker_points(entry, chests):
    """chest key -> (x, y) from whichever region claimed it."""
    pts = {}
    for reg in entry["regions"]:
        for k in reg["matched"]:
            c, r = chests[k]
            pts[k] = (reg["offset_x"] + c * 16 + 8, reg["offset_y"] + r * 16 + 8)
    return pts


def main():
    proposal = json.load(open(sys.argv[1]))
    out_path = sys.argv[2]
    names = sys.argv[3:] or sorted(proposal)
    POS = json.load(open(os.path.join(HERE, "chest_positions.json")))

    rows = []
    for name in names:
        e = proposal[name]
        chests = {}
        for k, places in POS.items():
            for p in places:
                if p["map_id"] == e["rom_map_id"]:
                    chests[f'{k}:{p["tile_col"]},{p["tile_row"]}'] = (p["tile_col"], p["tile_row"])
        pts = marker_points(e, chests)
        w, h, rgb = pngio.read_rgb(os.path.join(PACK, "images", "maps", f"{name}.png"))
        cells = []
        for k in sorted(pts, key=lambda k: (chests[k][1], chests[k][0])):
            cx, cy = pts[k]
            cell = bytearray(CELL * CELL * 3)
            for y in range(CELL):
                sy = cy - CROP // 2 + y // ZOOM
                for x in range(CELL):
                    sx = cx - CROP // 2 + x // ZOOM
                    if 0 <= sx < w and 0 <= sy < h:
                        i = (sy * w + sx) * 3
                        j = (y * CELL + x) * 3
                        cell[j:j + 3] = rgb[i:i + 3]
            # crosshair at the exact marker point
            mid = CELL // 2
            for d in range(-4, 5):
                for px, py in ((mid + d, mid), (mid, mid + d)):
                    j = (py * CELL + px) * 3
                    cell[j:j + 3] = b"\xff\x00\xff"
            cells.append(cell)
        rows.append((name, cells))

    ncol = max((len(c) for _, c in rows), default=0)
    W = ncol * (CELL + PAD) + PAD
    H = len(rows) * (CELL + PAD) + PAD
    img = bytearray(b"\x18\x18\x18" * (W * H))
    for ri, (_, cells) in enumerate(rows):
        oy = PAD + ri * (CELL + PAD)
        for ci, cell in enumerate(cells):
            ox = PAD + ci * (CELL + PAD)
            for y in range(CELL):
                src = y * CELL * 3
                dst = ((oy + y) * W + ox) * 3
                img[dst:dst + CELL * 3] = cell[src:src + CELL * 3]
    pngio.write_rgb(out_path, W, H, img)
    print(f"{out_path}  {W}x{H}")
    for i, (name, cells) in enumerate(rows):
        print(f"  row {i + 1}: {name} ({len(cells)})")


if __name__ == "__main__":
    main()
