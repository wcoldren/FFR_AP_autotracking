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

  2. **1F's outline, cross-checked against its four corner stair glyphs.** 1F
     has no fiend. The temple is bounded by the map's own grass on all four
     sides, so both edges of that box are read exactly: offset_y against the
     top edge, offset_x against the near edge. Its art also draws a cyan glyph
     on each of the four corner staircases, and those land within 2 px.

     2 px is as tight as the glyphs get, and that is why they are the
     cross-check rather than the anchor: the drawn temple is 673 px wide
     against 672 px of grid, so the art runs about 1.5 px wide across its
     width, no single offset is exact at both ends, and a 2 px tolerance
     cannot separate offset_x 27 from 28 -- it admits both. The near edge
     can, and does.

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

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)

PLATE_RGB = (242, 201, 11)      # the boss plate DarkmoonEX draws on a fiend
GLYPH_RGB = (0, 232, 216)       # the stair glyph on the 1F and 2F art

# Where the plate sits relative to the tile centre the committed offset
# implies. Measured 2026-09-06; see map_calibration.json's comment for why
# tofr3F is the odd one. Which ROM map each name stands for is deliberately
# not repeated here: it is read off the entry and checked below.
PLATE_FLOORS = {
    "tofr3F":    (0.5, -4.0),
    "tofrEarth": (-0.5, 0.0),
    "tofrFire":  (-0.5, 0.0),
    "tofrWater": (0.5, 0.0),
    "tofrAir":   (-1.0, 0.0),
}

# Every Temple floor a chest can land on. 2F is left out on purpose: no mode
# puts a chest there, so nothing would read it.
TOFR_FLOORS = list(PLATE_FLOORS) + ["tofr1F", "tofrChaos"]

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

    def bail():
        for f in fails:
            print("     " + f)
        print("FAILURES: %d" % len(fails))
        return 1

    for name in TOFR_FLOORS:
        check("%s has a calibration entry" % name, name in cal, True)
    if fails:
        return bail()

    # The entry's own rom_map_id is what regen_maps and overlay_preview resolve
    # a marker through, so an entry pointing at another floor's map moves every
    # marker on it while the offset still looks right. render_maps' table is the
    # authority on which id carries which name, and this suite reads the id off
    # the entry from here on rather than keeping a second copy to disagree with.
    for name in TOFR_FLOORS:
        check("%s's rom_map_id is the map of that name" % name,
              rm.MAP_FILES.get(cal[name]["rom_map_id"]), name)
    if fails:
        return bail()

    # An entry records what it was solved from, and there are two shapes of
    # that. `_derived_from` is an NPC and a pixel, and test_maps.lua check 4d
    # re-derives it from npc_positions.json. The readings behind the Temple
    # floors are a battle tile and an outline rather than an NPC, so 4d cannot
    # read them and they carry `_solved_from` instead -- with this suite as
    # their checker, which is the whole reason the second name exists.
    #
    # What keeps that honest is one-directional and asserted here: an entry may
    # record its evidence under `_solved_from` only if this suite re-derives
    # that floor. Put the key on a map nothing here looks at and it reads as
    # checked while nothing checks it, which is worse than no key at all.
    solved = sorted(k for k, v in cal.items()
                    if isinstance(v, dict) and "_solved_from" in v)
    check("_solved_from sits only on floors this suite re-derives",
          [k for k in solved if k not in TOFR_FLOORS], [])
    check("no entry claims both kinds of evidence",
          sorted(k for k, v in cal.items()
                 if isinstance(v, dict)
                 and "_solved_from" in v and "_derived_from" in v), [])
    check("at least one entry carries a _solved_from", bool(solved), True)

    # 1. the fiend's tile against its drawn plate
    for name, want_delta in sorted(PLATE_FLOORS.items()):
        found = battle_tiles(rom, cal[name]["rom_map_id"])
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
        tiles = rm.map_tiles(rom, cal["tofr1F"]["rom_map_id"])
        grid = [tiles[r * 64:(r + 1) * 64] for r in range(64)]
        void = max(set(tiles), key=tiles.count)
        cols = [c for c in range(64) if any(grid[r][c] != void for r in range(64))]
        rows = [r for r in range(64) if any(grid[r][c] != void for c in range(64))]
        grass = {(0, 168, 0), (0, 148, 0)}
        ys = [y for y in range(h)
              if any(tuple(buf[(y * w + x) * 3:(y * w + x) * 3 + 3]) not in grass
                     for x in range(w))]
        xs = [x for x in range(w)
              if any(tuple(buf[(y * w + x) * 3:(y * w + x) * 3 + 3]) not in grass
                     for y in range(h))]
        check("tofr1F's temple is 37 ROM tiles tall", rows[-1] - rows[0] + 1, 37)
        check("tofr1F's drawn temple is 592 px tall", ys[-1] - ys[0] + 1, 592)
        check("tofr1F's offset_y is that top edge", offset[1] - rows[0] * 16,
              ys[0])
        check("tofr1F's temple is 42 ROM tiles wide", cols[-1] - cols[0] + 1, 42)
        # 673 against 672 px of grid: the one pixel the art runs wide. The near
        # edge is the answer, so offset_x is read there and not at the far one.
        check("tofr1F's drawn temple is 673 px wide", xs[-1] - xs[0] + 1, 673)
        check("tofr1F's offset_x is that near edge", offset[0] - cols[0] * 16,
              xs[0])

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else "FAILURES: %d" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
