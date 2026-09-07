"""The Temple of Fiends offsets still land on the thing they were solved from.

`tools/map_calibration.json` turns a ROM tile into a pixel on the hand-drawn
art, and a wrong offset fails silently: every marker on that floor sits a
little off, which reads as sloppy art rather than as a bug. Four of the seven
Temple entries were solved by eye on an overlay, and an eye is not a check.

Two correspondences are re-derived here, and both ends of each come from
somewhere this suite does not control -- the tile off the cartridge, the pixel
off the shipped art. The offset is the only thing joining them, so editing
either end without the other fails.

  1. **The fiend's tile against its drawn plate.** Every Temple floor except
     1F, 2F and Chaos carries exactly one fixed-formation battle tile, at the
     same coordinates on every cartridge measured -- 6BF0DEA9, C189A0EF,
     72A52C25, the No-Overworld oracle and vanilla -- and DarkmoonEX draws a
     yellow boss plate on it. The plate sits within a pixel of the tile centre
     on four of the five floors.

     `tofr3F` is the fifth and is off by 4 in y, which is the art and not the
     entry: its two drawn chest sprites sit at the same offset from their tile
     centres as tofrFire's and tofrAir's do, so the grid is right and the plate
     is high. It is pinned at its measured value rather than waved through,
     because "off by about 4" would pass an entry that had drifted by 4.

  2. **1F's four corner stair glyphs, and its outline.** 1F has no fiend. Its
     art draws a cyan glyph on each of the four corner staircases, and the
     temple itself is bounded by the map's own grass on all four sides. The
     glyphs land within 2 px, which is as tight as this one gets: the drawn
     temple is 673 px wide against 672 px of grid, so the art runs about 1.5 px
     wide across its width and no single offset can be exact at both ends.

Set FF1_ROM to a cartridge; without one this skips. Any Final Fantasy image
does -- the tiles this reads are in the same place on all of them, which is
itself asserted below.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import pngio                                                   # noqa: E402
import render_maps as rm                                       # noqa: E402
import tofr_diff as td                                         # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)

PLATE_RGB = (242, 201, 11)      # the boss plate DarkmoonEX draws on a fiend
GLYPH_RGB = (0, 232, 216)       # the stair glyph on the 1F and 2F art

# The floor, its ROM map, and where the plate sits relative to the tile centre
# the committed offset implies. Measured 2026-09-06; see map_calibration.json's
# comment for why tofr3F is the odd one.
PLATE_FLOORS = {
    "tofr3F":    (54, (0.5, -4.0)),
    "tofrEarth": (55, (-0.5, 0.0)),
    "tofrFire":  (56, (-0.5, 0.0)),
    "tofrWater": (57, (0.5, 0.0)),
    "tofrAir":   (58, (-1.0, 0.0)),
}

# 1F's four corner staircases, as ROM tiles. The map's other two teleports are
# the time warp in the middle and a warp the art draws no glyph for.
CORNERS_1F = ((1, 1), (40, 1), (1, 35), (40, 35))


def art(name):
    return pngio.read_rgb(os.path.join(PACK, "images", "maps", name + ".png"))


def blobs(w, h, buf, rgb, gap=2, minpx=8):
    """Centres of the runs of one exact colour, as (cx, cy, size)."""
    want = bytes(rgb)
    hits = set()
    for y in range(h):
        row = bytes(buf[y * w * 3:(y + 1) * w * 3])
        i = row.find(want)
        while i != -1:
            if i % 3 == 0:
                hits.add((i // 3, y))
            i = row.find(want, i + 1)
    seen, out = set(), []
    for start in hits:
        if start in seen:
            continue
        stack, group = [start], []
        seen.add(start)
        while stack:
            px, py = stack.pop()
            group.append((px, py))
            for dx in range(-gap, gap + 1):
                for dy in range(-gap, gap + 1):
                    q = (px + dx, py + dy)
                    if q in hits and q not in seen:
                        seen.add(q)
                        stack.append(q)
        if len(group) >= minpx:
            xs = [p[0] for p in group]
            ys = [p[1] for p in group]
            out.append(((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0,
                        len(group)))
    return sorted(out)


def offset_of(cal, name):
    """The one region of a single-region entry, as (offset_x, offset_y)."""
    regions = cal[name]["regions"]
    if len(regions) != 1:
        return None
    return regions[0]["offset_x"], regions[0]["offset_y"]


def centre(offset, col, row, tile_px=16):
    return (offset[0] + col * tile_px + tile_px // 2,
            offset[1] + row * tile_px + tile_px // 2)


def battle_tiles(rom, map_id):
    """The fixed-formation tiles standing on one map, as (col, row)."""
    tiles = rm.map_tiles(rom, map_id)
    return sorted(rm.map_trap_marks(rom, map_id, tiles))


def main():
    path = os.environ.get("FF1_ROM")
    if not path or not os.path.exists(path):
        print("SKIP  set FF1_ROM to a Final Fantasy cartridge to run this")
        return 0
    with open(path, "rb") as f:
        rom = f.read()
    with open(os.path.join(TOOLS, "map_calibration.json")) as f:
        cal = json.load(f)

    fails = []

    def check(label, got, want):
        if got != want:
            fails.append("%s: got %r, want %r" % (label, got, want))
        print("%s %-58s %s" % ("ok  " if got == want else "FAIL", label, got))

    # Every Temple floor a chest can land on needs an entry. 2F is left out on
    # purpose: no mode puts a chest there, so nothing would read it.
    for name in list(PLATE_FLOORS) + ["tofr1F", "tofrChaos"]:
        check("%s has a calibration entry" % name, name in cal, True)
    if fails:
        for f in fails:
            print("     " + f)
        print("FAILURES: %d" % len(fails))
        return 1

    # 1. the fiend's tile against its drawn plate
    for name, (map_id, want_delta) in sorted(PLATE_FLOORS.items()):
        found = battle_tiles(rom, map_id)
        check("%s carries one fixed-formation tile" % name, len(found), 1)
        if len(found) != 1:
            continue
        col, row = found[0]
        offset = offset_of(cal, name)
        check("%s is one region" % name, offset is not None, True)
        if offset is None:
            continue
        w, h, buf = art(name)
        plates = [b for b in blobs(w, h, buf, PLATE_RGB) if b[2] >= 30]
        # Two on every floor: the one on the map and the one in the Map Key.
        # The key's is the one that does not sit near the fiend.
        cx, cy = centre(offset, col, row)
        near = sorted(plates, key=lambda b: abs(b[0] - cx) + abs(b[1] - cy))
        check("%s draws a boss plate" % name, bool(near), True)
        if not near:
            continue
        got = (round(near[0][0] - cx, 1), round(near[0][1] - cy, 1))
        check("%s plate sits at its measured offset from tile (%d,%d)"
              % (name, col, row), got, want_delta)

    # 2. 1F's corner glyphs and its outline
    offset = offset_of(cal, "tofr1F")
    check("tofr1F is one region", offset is not None, True)
    if offset is not None:
        w, h, buf = art("tofr1F")
        glyphs = blobs(w, h, buf, GLYPH_RGB)
        check("tofr1F draws four corner stair glyphs", len(glyphs), 4)
        for col, row in CORNERS_1F:
            cx, cy = centre(offset, col, row)
            near = sorted(glyphs, key=lambda b: abs(b[0] - cx) + abs(b[1] - cy))
            far = max(abs(near[0][0] - cx), abs(near[0][1] - cy)) if near else None
            check("tofr1F glyph for tile (%d,%d) is within 2 px" % (col, row),
                  far is not None and far <= 2.0, True)

        # The outline. The ROM map's own grass is its void, so the temple's
        # extent is a tile count the art has to match in pixels.
        tiles = rm.map_tiles(rom, 52)
        grid = [tiles[r * 64:(r + 1) * 64] for r in range(64)]
        void = max(set(tiles), key=tiles.count)
        cols = [c for c in range(64) if any(grid[r][c] != void for r in range(64))]
        rows = [r for r in range(64) if any(grid[r][c] != void for c in range(64))]
        grass = {(0, 168, 0), (0, 148, 0)}
        ys = [y for y in range(h)
              if any(tuple(buf[(y * w + x) * 3:(y * w + x) * 3 + 3]) not in grass
                     for x in range(w))]
        check("tofr1F's temple is 37 ROM tiles tall", rows[-1] - rows[0] + 1, 37)
        check("tofr1F's drawn temple is 592 px tall", ys[-1] - ys[0] + 1, 592)
        check("tofr1F's offset_y is that top edge", offset[1] - rows[0] * 16,
              ys[0])
        check("tofr1F's temple is 42 ROM tiles wide", cols[-1] - cols[0] + 1, 42)

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else "FAILURES: %d" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
