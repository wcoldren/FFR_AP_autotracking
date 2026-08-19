#!/usr/bin/env python3
"""Draw the computed markers onto the pack's map art so a human can check the
calibration by eye.

The art is hand-composited rather than machine-rendered, so no automated score
settles whether a calibration is right -- looking at the overlay does. Run this
before committing coordinates for a new dungeon.

Usage: tools/overlay_preview.py <out_dir> [map_name ...]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pngio          # noqa: E402
import make_markers   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
GREEN = b"\x00\xff\x00"


def box(rgb, w, h, cx, cy, half, colour):
    for d in range(-half, half + 1):
        for x, y in ((cx + d, cy - half), (cx + d, cy + half),
                     (cx - half, cy + d), (cx + half, cy + d)):
            if 0 <= x < w and 0 <= y < h:
                rgb[(y * w + x) * 3:(y * w + x) * 3 + 3] = colour


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("maps", nargs="*")
    args = ap.parse_args()

    chests, cal = make_markers.load()
    markers = make_markers.build(chests, cal)
    os.makedirs(args.out_dir, exist_ok=True)

    for name in (args.maps or sorted(cal)):
        w, h, rgb = pngio.read_rgb(os.path.join(PACK, "images", "maps", f"{name}.png"))
        n = 0
        for pos in markers.values():
            if pos["map"] != name:
                continue
            box(rgb, w, h, pos["x"], pos["y"], 10, GREEN)
            box(rgb, w, h, pos["x"], pos["y"], 11, GREEN)
            n += 1
        out = os.path.join(args.out_dir, f"{name}_overlay.png")
        pngio.write_rgb(out, w, h, rgb)
        print(f"{name}: {n} markers -> {out}")


if __name__ == "__main__":
    main()
