#!/usr/bin/env python3
"""Draw a map's calibration grid over its art, so an offset can be judged by eye.

`tools/map_calibration.json` turns a ROM tile into a pixel on the drawn map, and
a wrong offset is invisible in the numbers -- every marker simply sits a little
off, which reads as sloppy art rather than as a bug. This renders the transform
the file actually encodes: the 16-pixel grid it implies, and a box on whichever
ROM tiles you name. If the grid lines up with the drawn tile boundaries, the
offset is right; if it drifts across the map, it is not.

That is the check the calibration comment means by "checked on the overlay", and
the file referred to this tool before the tool existed.

Solving an offset rather than checking one: a floor the vanilla game gives a
chest can be solved from the chest sprites, and `map_calibration.json`'s comment
says how. A floor with no chest -- every Temple of Fiends floor past the first
-- has to be solved from the room's own extent, and `--solve` prints that
proposal without writing it anywhere. It is a proposal precisely because it has
been wrong before: read the comment in `map_calibration.json` for which rule
reproduces the three known offsets and which does not.

    tools/overlay_preview.py tofrChaos --rom <rom> --tile 15,3 --tile 15,7
    tools/overlay_preview.py tofrChaos --rom <rom> --offset 13,13 -o /tmp/x.png
    tools/overlay_preview.py tofrChaos --rom <rom> --solve
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import pngio          # noqa: E402
import render_maps    # noqa: E402

CALIBRATION = os.path.join(HERE, "map_calibration.json")
GRID_RGB = (80, 80, 255)
ROOM_RGB = (255, 0, 255)
TILE_RGB = (255, 0, 0)


def calibration():
    with open(CALIBRATION) as fh:
        return json.load(fh)


def art_path(name):
    return os.path.join(PACK, "images", "maps", name + ".png")


def room_tiles(rom, map_id):
    """-> (cols, rows) the map's room occupies, by ROM tile.

    The void tile is the most common one on the grid. That is a heuristic and
    it is stated as one: it holds on every Temple of Fiends floor, where the
    room is a small island in a filled 64x64 grid, and it would not hold on a
    map that is mostly walkable.
    """
    tiles = render_maps.map_tiles(rom, map_id)
    grid = [tiles[r * 64:(r + 1) * 64] for r in range(64)]
    void = collections.Counter(tiles).most_common(1)[0][0]
    cols = [c for c in range(64) if any(grid[r][c] != void for r in range(64))]
    rows = [r for r in range(64) if any(grid[r][c] != void for c in range(64))]
    return cols, rows


def content_box(w, h, buf):
    """-> (x0, x1, y0, y1) of everything that is not the corner colour."""
    bg = buf[0:3]
    xs, ys = [], []
    for y in range(h):
        row = buf[y * w * 3:(y + 1) * w * 3]
        for x in range(w):
            if row[x * 3:x * 3 + 3] != bg:
                xs.append(x)
                ys.append(y)
                break
        # the right edge wants its own scan, cheapest done backwards
        for x in range(w - 1, -1, -1):
            if row[x * 3:x * 3 + 3] != bg:
                xs.append(x)
                break
    return min(xs), max(xs), min(ys), max(ys)


def solve(rom, map_id, w, h, buf, tile_px):
    """-> (offset_x, offset_y) proposed from the room's extent.

    Anchored on the FAR content edge. The near edge is wrong on at least one
    committed map -- tofrAir carries three rows of something above its room --
    and the far edge reproduces all three offsets that were solved from chest
    sprites. See map_calibration.json's comment.
    """
    cols, rows = room_tiles(rom, map_id)
    room_w = (cols[-1] - cols[0] + 1) * tile_px
    room_h = (rows[-1] - rows[0] + 1) * tile_px
    x0, x1, y0, y1 = content_box(w, h, buf)
    return x1 - room_w + 1, y1 - room_h + 1, room_w, room_h


def put(buf, w, h, x, y, rgb):
    if 0 <= x < w and 0 <= y < h:
        i = (y * w + x) * 3
        buf[i:i + 3] = bytes(rgb)


def box(buf, w, h, ox, oy, tile_px, col, row, rgb, rad=8):
    cx = ox + col * tile_px + tile_px // 2
    cy = oy + row * tile_px + tile_px // 2
    for d in range(-rad, rad + 1):
        put(buf, w, h, cx + d, cy - rad, rgb)
        put(buf, w, h, cx + d, cy + rad, rgb)
        put(buf, w, h, cx - rad, cy + d, rgb)
        put(buf, w, h, cx + rad, cy + d, rgb)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("map", help="map name, e.g. tofrChaos")
    ap.add_argument("--rom", help="cartridge, for --solve and the room outline")
    ap.add_argument("--offset", help="x,y to preview instead of the committed one")
    ap.add_argument("--tile", action="append", default=[],
                    help="col,row to box; repeatable")
    ap.add_argument("--solve", action="store_true",
                    help="print an offset proposed from the room extent and exit")
    ap.add_argument("-o", "--out", help="where to write the overlay")
    args = ap.parse_args(argv)

    cal = calibration()
    entry = cal.get(args.map)
    path = art_path(args.map)
    if not os.path.exists(path):
        ap.error("no art at %s" % path)
    w, h, rgb = pngio.read_rgb(path)
    buf = bytearray(rgb)
    tile_px = (entry or {}).get("tile_px", 16)

    map_id = (entry or {}).get("rom_map_id")
    if map_id is None:
        for mid, nm in render_maps.MAP_FILES.items():
            if nm == args.map:
                map_id = mid
                break

    rom = open(args.rom, "rb").read() if args.rom else None

    if args.solve:
        if rom is None:
            ap.error("--solve needs --rom")
        ox, oy, rw, rh = solve(rom, map_id, w, h, buf, tile_px)
        print("%s: art %dx%d, room %dx%d -> proposed offset (%d,%d)"
              % (args.map, w, h, rw, rh, ox, oy))
        print("This is a proposal. Run the overlay before committing it.")
        return 0

    if args.offset:
        ox, oy = (int(v) for v in args.offset.split(","))
    elif entry:
        region = entry["regions"][0]
        ox, oy = region["offset_x"], region["offset_y"]
    else:
        ap.error("%s has no calibration entry; pass --offset or --solve" % args.map)

    for x in range(ox % tile_px, w, tile_px):
        for y in range(h):
            put(buf, w, h, x, y, GRID_RGB)
    for y in range(oy % tile_px, h, tile_px):
        for x in range(w):
            put(buf, w, h, x, y, GRID_RGB)

    if rom is not None and map_id is not None:
        cols, rows = room_tiles(rom, map_id)
        rw = (cols[-1] - cols[0] + 1) * tile_px
        rh = (rows[-1] - rows[0] + 1) * tile_px
        for x in range(ox, ox + rw):
            put(buf, w, h, x, oy, ROOM_RGB)
            put(buf, w, h, x, oy + rh - 1, ROOM_RGB)
        for y in range(oy, oy + rh):
            put(buf, w, h, ox, y, ROOM_RGB)
            put(buf, w, h, ox + rw - 1, y, ROOM_RGB)

    for spec in args.tile:
        col, row = (int(v) for v in spec.split(","))
        box(buf, w, h, ox, oy, tile_px, col, row, TILE_RGB)

    out = args.out or os.path.join("/tmp", args.map + "_overlay.png")
    pngio.write_rgb(out, w, h, buf)
    print("%s at offset (%d,%d) -> %s" % (args.map, ox, oy, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
