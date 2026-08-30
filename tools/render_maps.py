#!/usr/bin/env python3
"""Draw every standard map out of a cartridge, using the game's own tile art.

The pack's dungeon images used to be screenshots: right for a vanilla layout,
approximate about scale, and silent about anything the seed changed. A
No-Overworld seed changes a great deal -- it stamps 75 new staircases across 34
maps and seals every town's outer wall -- so a screenshot of the vanilla castle
shows the right rooms and the wrong exits. Drawing from the cartridge instead
gets the seed's own map, whatever mode it is in.

It also makes calibration a derivation rather than an eyeballed number. Plain,
every image is 64 tiles at 16 pixels, so tile (col, row) is pixel (16col, 16row)
exactly. With --crop each image starts at its own content box instead, which is
one offset per axis per map -- still computed from the cartridge, still one
region, and still nothing to solve by hand. The 51 images the pack ships are
hand-drawn composites at 51 different sizes, each with a hand-solved offset in
tools/map_calibration.json; those offsets stay where they are and keep serving
that art. Dropping these renders on top of it is a job for tools/regen_maps.py,
which rebuilds the markers from the cartridge rather than moving the old ones.

Cropping is what makes a tab readable. A mean 48% of the grid survives it, and
the box lands within a tile of the one DarkmoonEX drew on 22 of the 30 maps
where both exist -- which is the reason to trust it, since the rule is the
border tile and a flood and knows nothing about the art.

The rendering is FF1Lib/Sprites/MapSprites.cs's, in Python:

  RelocateChests.cs:21      TILESETPATTERNTABLE_OFFSET = $C000, CHR for tileset
                            t at $C000 + (t << 11) + pattern * 16, 16 bytes
  MapSprites.cs:28          MAPPALETTE_OFFSET = $2000, 0x30 bytes per map: four
                            4-byte palettes for outside, four more at +$20 for
                            the "inside" (room) variant
  MapSprites.cs:31          MAPTILESET_ASSIGNMENT = $2CC0, one tileset per map
  Data/TileSet.cs:236-241   per tileset t, the four CHR indices that make up a
                            16x16 tile: $1000/$1080/$1100/$1180 + $200 * t, and
                            the palette index at $400 + $80 * t
  Sprites.cs:218            DecodePPU, the ordinary NES 2bpp planar decode
  MapSprites.cs:425         RenderMap: map tile value t is drawn from the
                            tileset's tile t, so the 16x8 sheet is skipped here
                            and each tile is drawn straight onto the output

Standard map data does not live where a stock cartridge keeps it -- see
extract_chests.standard_map_bank -- which is asked rather than assumed.

**FFR's own `FF1R renderdungeon` is not a correctness oracle for this.** Its
StandardMaps constructor loads from `MapPointerOffset = 0x10000`, bank $04
(StandardMaps.cs:63-66), while StandardMaps.Write() emits to bank $14
(:143-145). It therefore draws the *vanilla* map for every seed -- the same
trap entrance_graph.py fell into. On a No-Overworld cartridge that means it
misses every sealed wall, all 75 new staircases, and both of the rooms
MetroidVaniaMap.cs:281-300 builds inside Coneria Castle. Deliberately reading
bank $04 here reproduces its output on 59 of 61 maps, which is what identified
the cause; --check still runs that comparison, but a disagreement on a map the
seed modified is the expected result and not a defect.

What this was actually verified against is the game. Two unscaled 256x240 Mesen
grabs of Coneria Castle 1F on seed F258553F, one in the corridor and one in the
throne room, use exactly the background colours this renderer produces for that
map -- NES indices $0F, $00, $10, $30 and the two greens $19/$1A, and no blue
in the surround. Mesen converts NES indices to RGB with its own table (its $00
is 102,102,102 where FFR's is 123,123,123), so the comparison is on palette
indices, not raw RGB.

Usage:
    tools/render_maps.py ROM -o /tmp/maps              # all 61, pack names
    tools/render_maps.py ROM --map 8                   # just Coneria Castle 1F
    tools/render_maps.py ROM --check DIR               # diff against FF1R's
"""

import argparse
import hashlib
import json
import os
import string
import sys
from collections import Counter, deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from extract_chests import (  # noqa: E402
    BANK_SIZE, INES_HEADER, MAP_COUNT, MAP_DIM, PROP_STRIDE, TILESET_LUT,
    TILESET_PROP, decompress_map, map_data_base,
)
import entrance_graph  # noqa: E402
import pngio  # noqa: E402

TILE_PX = 16                      # a standard-map tile is 16x16 pixels
CHR_BASE = INES_HEADER + 0xC000   # TILESETPATTERNTABLE_OFFSET
PALETTE_BASE = INES_HEADER + 0x2000
PALETTE_STRIDE = 0x30
PALETTE_INSIDE = 0x20
ATTR_BASE = INES_HEADER + 0x400   # tile -> which of the four palettes
QUAD_BASE = INES_HEADER + 0x1000  # the four CHR indices per tile
TILES_PER_SET = 128

# Sprites.cs:23. Sixty-four entries, RGB, six hex characters each.
_NES = (
    "7b7b7b" "0000ff" "0000bf" "472bbf" "970087" "ab0023" "ab1300" "8b1700"
    "533000" "007800" "006b00" "005b00" "004358" "000000" "000000" "000000"
    "bdbdbd" "0078f8" "0058f8" "6b47ff" "db00cd" "e7005b" "f83800" "e75f13"
    "af7f00" "00b800" "00ab00" "00ab47" "008b8b" "000000" "000000" "000000"
    "f8f8f8" "3fbfff" "6b88ff" "9878f8" "f878f8" "f85898" "f87858" "ffa347"
    "f8b800" "b8f818" "5bdb57" "58f898" "00ebdb" "787878" "000000" "000000"
    "ffffff" "a7e7ff" "b8b8f8" "d8b8f8" "f8b8f8" "fba7c3" "f0d0b0" "ffe3ab"
    "fbdb7b" "d8f878" "b8f8b8" "b8f8d8" "00ffff" "f8d8f8" "000000" "000000"
)

NES_PALETTE = [tuple(int(_NES[i + k:i + k + 2], 16) for k in (0, 2, 4))
               for i in range(0, len(_NES), 6)]

# Transcribing 64 colours by hand went wrong twice: a dropped digit shifted
# everything from $10 on, and "004358" "000000" got re-split as "000043"
# "580000", which only showed up as the Waterfall rendering navy instead of
# teal. Neither a length check nor a handful of spot anchors catches that --
# the first still divides into 64 entries, and the second only guards the
# entries you thought to name. Checksum the whole table instead. The value is
# sha256 of the concatenated hex of FF1Lib/Sprites/Sprites.cs's NESpalette;
# regenerate it from that array rather than editing it to match.
assert len(_NES) == 64 * 6, len(_NES)

assert hashlib.sha256(_NES.encode()).hexdigest()[:16] == "5258fbbe2c508ceb", \
    "NES palette table does not match FF1Lib/Sprites/Sprites.cs"

def decode_ppu(chunk):
    """16 PPU bytes -> 64 pixel indices 0-3 (Sprites.cs:218)."""
    out = bytearray(64)
    for i in range(64):
        row = (i >> 3) & 7
        col = 7 - (i & 7)
        bit0 = (chunk[row] >> col) & 1
        bit1 = (chunk[row + 8] >> col) & 1
        out[i] = (bit1 << 1) | bit0
    return out


def map_palettes(rom, map_id, inside=False):
    """The map's four 4-colour palettes, as NES colour indices."""
    base = PALETTE_BASE + map_id * PALETTE_STRIDE + (PALETTE_INSIDE if inside else 0)
    return [rom[base + n * 4:base + n * 4 + 4] for n in range(4)]


def tileset_art(rom, tileset, palettes):
    """tile id -> a 16x16 block of (r, g, b), for one tileset."""
    attrs = rom[ATTR_BASE + 0x80 * tileset:ATTR_BASE + 0x80 * tileset + TILES_PER_SET]
    quads = [rom[QUAD_BASE + 0x80 * n + 0x200 * tileset:
                 QUAD_BASE + 0x80 * n + 0x200 * tileset + TILES_PER_SET]
             for n in range(4)]
    chr_base = CHR_BASE + (tileset << 11)
    blocks = []
    for t in range(TILES_PER_SET):
        pal = palettes[attrs[t] & 3]
        block = [[(0, 0, 0)] * TILE_PX for _ in range(TILE_PX)]
        # top-left, top-right, bottom-left, bottom-right
        for n, (ox, oy) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
            off = chr_base + quads[n][t] * 16
            px = decode_ppu(rom[off:off + 16])
            for i, v in enumerate(px):
                block[oy + (i >> 3)][ox + (i & 7)] = NES_PALETTE[pal[v]]
        blocks.append(block)
    return blocks


# A roof is not separate tile data. The room interior -- chests, furniture and
# floor alike -- is already in the map, painted over with colours that collapse
# it to a featureless slab. Stepping through the door swaps the map to its
# "inside" palette and the same tiles resolve. Every chest in Coneria Castle 1F,
# Elfland Castle and Ice Cave B1 sits under one of these.
#
# Ask the *rendered tile* whether it is blank, not the palette. An earlier
# version asked the palette -- were its three non-background colours equal? --
# and so found a room's furniture but not the floor between it. Coneria Castle
# 1F's room floor is tile $04 on sub-palette 1, which is `0F 30 30 10` and
# therefore not a flat palette, yet every pixel of that tile is $30: outdoors it
# draws flat white. It came out as a hole with the furniture floating in it, and
# an NPC standing there looked pasted on.
#
# The tile itself has the answer. $04 draws flat white outdoors and flat *black*
# inside, which is exactly what the shipped hand-drawn maps show -- DarkmoonEX's
# con_castle.png draws both throne rooms as black floor with orange furniture.
# So there is nothing to invent and no substitute tile to choose: swap the cell
# to the inside palette and the cartridge draws the room.
#
# Flatness alone is not enough, because a uniform rock wall is flat for the same
# reason. Two tests, and a cell has to pass both:
#
#   * its outdoor art draws ONE colour, and its inside art draws something
#     different -- a cave floor renders identically under both palettes, so it
#     is never a hidden cell and Ice Cave B1's 3177 flat walkable cells never
#     enter the running;
#   * and its connected component is small. A room is a small closed region;
#     the wall is one mass spanning the map.
ROOM_MAX_CELLS = 256


def flat_art(block):
    """True when a tile draws one colour, so it carries no information."""
    return len({px for row in block for px in row}) == 1


def _colours(block):
    return frozenset(px for row in block for px in row)


def _components(cells):
    """The 4-connected components of a cell set, as a list of lists."""
    seen, out = set(), []
    for start in cells:
        if start in seen:
            continue
        seen.add(start)
        stack, comp = [start], []
        while stack:
            r, c = stack.pop()
            comp.append((r, c))
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (r + dr, c + dc)
                if n in cells and n not in seen:
                    seen.add(n)
                    stack.append(n)
        out.append(comp)
    return out


def roof_palettes(rom, map_id):
    """Sub-palette indices that are a flat slab outdoors and detailed inside."""
    def flat(p):
        return p[1] == p[2] == p[3]
    out = map_palettes(rom, map_id, False)
    ins = map_palettes(rom, map_id, True)
    return {i for i in range(4) if flat(out[i]) and not flat(ins[i])}


# What the engine itself calls a room. `inroom` ($0D) is a single global byte:
# stepping on a door tile sets it (SMMove_Door, bank_0F.asm:3486), stepping on a
# close-room tile clears it (:3430), and while it is set the whole background
# palette comes from inroom_pal (:5879-5883). So the engine has no per-cell
# notion of a room and never shows one open while the outside is closed --
# unroofing is our invention. But the transition is tile-driven, so the region
# is derivable: what you can walk to from a door without crossing a close-room
# tile.
#
# This is the only test that can work, because no property of a tile can decide
# it. Waterfall's room floor is tile $46 -- flat cyan outdoors, flat black
# inside -- and $46 is also the open water outside the room, 1820 cells of it.
# The same two ROM bytes are room floor in one place and outdoors in another.
DOOR_SPECS = (entrance_graph.TP_SPEC_DOOR, entrance_graph.TP_SPEC_LOCKED)


def door_rooms(rom, map_id):
    """The cells the engine would have you in a room for, as a set."""
    _, props = entrance_graph.tile_properties(rom, map_id)
    spec = [p & entrance_graph.TP_SPEC_MASK for p in props]
    seen = set()
    for start in (i for i, sp in enumerate(spec) if sp in DOOR_SPECS):
        stack = [start]
        while stack:
            i = stack.pop()
            if i in seen:
                continue
            seen.add(i)
            r, c = divmod(i, MAP_DIM)
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nr, nc = r + dr, c + dc
                if not (0 <= nr < MAP_DIM and 0 <= nc < MAP_DIM):
                    continue
                j = nr * MAP_DIM + nc
                if j in seen or spec[j] == entrance_graph.TP_SPEC_CLOSEROOM:
                    continue
                if entrance_graph.walkable(props[j], set()) or spec[j] in DOOR_SPECS:
                    stack.append(j)
    return {(i // MAP_DIM, i % MAP_DIM) for i in seen}


def room_and_walls(rom, map_id, tiles, art, open_art):
    """A door-flood room plus the wall it is enclosed by."""
    _, props = entrance_graph.tile_properties(rom, map_id)
    wall = {(i // MAP_DIM, i % MAP_DIM) for i, t in enumerate(tiles)
            if not entrance_graph.walkable(props[i], set())
            and _colours(art[t & 0x7F]) != _colours(open_art[t & 0x7F])}
    room = door_rooms(rom, map_id)
    while True:
        grown = room | ({(r + dr, c + dc) for r, c in room
                         for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))} & wall)
        if grown == room:
            break
        room = grown

    # Finally fill pockets fully enclosed by the room. Mirage Tower 1F has a
    # trap tile at (15,17) with chests on three sides and the room's wall on
    # the fourth: walkable, but the flood cannot reach it because a chest tile
    # is not walkable, so it kept drawing as roof between four chests where
    # mirage1F.png has black floor. Requiring *all four* neighbours to be
    # inside already is what makes this safe -- it cannot escape a region it
    # is not enclosed by. 39 cells across all 61 maps.
    while True:
        pockets = {(r, c) for r in range(MAP_DIM) for c in range(MAP_DIM)
                   if (r, c) not in room
                   and all((r + dr, c + dc) in room
                           for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)))}
        if not pockets:
            break
        room |= pockets
    return room


def hidden_cells(rom, map_id, tiles, art=None, open_art=None):
    """The (row, col) cells a roof covers, as a set. Empty when there is none.

    Two tests, because neither alone is right and their failure modes are
    opposite. Each is size-guarded on its own components, then unioned: a room
    is a small closed region, a rock wall is one mass spanning the map.

    **The sub-palette** says a tile's three non-background colours are equal
    outdoors and not inside. That is the game's own mechanism and it is exact,
    but it only finds what the roof palette covers.

    **The rendered tile** says the tile draws one colour outdoors and something
    different inside. That catches what the palette test cannot: Coneria Castle
    1F's room floor is tile $04 on sub-palette 1 -- `0F 30 30 10`, not a flat
    palette -- yet every pixel of it is $30, so outdoors it draws flat white and
    the palette test walks straight past. Left shut, the room reads as a void
    with its furniture floating in it.

    Neither test may define a region on its own terms. Two ways that goes wrong,
    both found by asking whether the result was closer to the shipped
    hand-drawn maps or farther from them:

      * the art test *alone* admits enough extra cells that separate rooms merge
        into one region, which then fails the size guard and closes rooms the
        palette test had open -- Temple of Fiends Air went 241 cells -> 1;
      * and seeding on the palette test then flooding through art-blank cells
        runs away, because a room can touch a wall that is also art-blank.
        Mirage Tower 1F's outer wall is 458 such cells; absorbing them redrew
        the ring bright orange where the shipped art has dark red brick.

    So: guard each test's own components, then union. Measured on F258553F --
    6360 cells, no map opening less than the palette test alone, and **zero**
    walkable cells left drawing flat white, which is the check that matters
    because the shipped maps never show one.
    """
    tileset = rom[TILESET_LUT + map_id]
    if art is None:
        art = tileset_art(rom, tileset, map_palettes(rom, map_id, False))
    if open_art is None:
        open_art = tileset_art(rom, tileset, map_palettes(rom, map_id, True))

    roof = roof_palettes(rom, map_id)
    attrs = rom[ATTR_BASE + 0x80 * tileset:ATTR_BASE + 0x80 * tileset + TILES_PER_SET]
    seeded = {(i // MAP_DIM, i % MAP_DIM) for i, t in enumerate(tiles)
              if (attrs[t & 0x7F] & 3) in roof} if roof else set()
    blank = {(i // MAP_DIM, i % MAP_DIM) for i, t in enumerate(tiles)
             if flat_art(art[t & 0x7F])
             and _colours(art[t & 0x7F]) != _colours(open_art[t & 0x7F])}

    keep = {cell
            for cells in (seeded, blank)
            for comp in _components(cells) if len(comp) <= ROOM_MAX_CELLS
            for cell in comp}

    # The door flood needs no size guard: it is bounded by the room itself, so
    # it opens Mirage Tower's 458-cell interior without opening Waterfall's
    # 1820-cell water. Unioned rather than substituted -- it finds rooms the
    # other two miss, and misses some they find.
    #
    # Then grown into the wall around it, because `inroom` is global: standing
    # in a room the engine draws the *whole screen* from inroom_pal, walls
    # included, and the shipped art follows it. Without this Mirage Tower's
    # ring keeps a scatter of bright orange blocks where mirage1F.png has
    # uniform dark red brick -- tiles $01-$08, which are textured outdoors and
    # so are not "blank" at all; they are simply wall.
    #
    # Growth crosses only cells that are *not walkable* and that draw
    # differently under the two palettes. Not-walkable stops it running out of
    # the room across the floor, which Waterfall's water would otherwise carry
    # the width of the map; drawing-differently stops it at the out-of-bounds
    # void, which is black either way.
    #
    # It opens 3695 of Dwarf Cave's 4096 cells, and that is correct rather than
    # a runaway: the cave is entirely indoors, so nearly all of it *is* one
    # room in the engine's terms. A large fraction opened is not evidence of a
    # leak, which is a mistake worth not repeating -- it was called one here on
    # the cell count alone, before anybody looked at the picture.
    return keep | room_and_walls(rom, map_id, tiles, art, open_art)


# --------------------------------------------------------------------- crop

# A 64x64 map is mostly not map. What fills the rest is one tile repeated --
# the out-of-bounds void in a dungeon, the warp-out field around a town -- so a
# render of the whole grid puts Mirage Tower 1F's interior in a corner of a
# 1024x1024 image and leaves the rest empty. The shipped hand-drawn maps are
# cropped, which is why con_castle.png is 1074x605 and matoya.png 273x258.
#
# The crop derives, and the hand art is what says so. On the 30 maps
# map_calibration.json covers, the box below lands within one tile of the box
# DarkmoonEX drew on about 25 of them and exactly on tofrAir. That agreement
# was not tuned for: the rule is the border tile and a flood inward, and the
# numbers came out where the art already was. Mean kept area is 48% of the
# grid.


def map_tiles(rom, map_id):
    """The decompressed 64*64 tile grid for one standard map."""
    base = map_data_base(rom)
    ptr = int.from_bytes(rom[base + map_id * 2:base + map_id * 2 + 2], "little")
    return decompress_map(rom, base + ptr)


def backdrop_tile(tiles):
    """(tile id, how many of the 256 border cells it holds).

    The ring around the outside of the grid is filler on every map, so its
    modal tile names the filler. The count comes back with it because a map
    whose ring is not overwhelmingly one tile is a map to be careful about.
    """
    ring = [tiles[c] for c in range(MAP_DIM)]
    ring += [tiles[(MAP_DIM - 1) * MAP_DIM + c] for c in range(MAP_DIM)]
    ring += [tiles[r * MAP_DIM] for r in range(MAP_DIM)]
    ring += [tiles[r * MAP_DIM + MAP_DIM - 1] for r in range(MAP_DIM)]
    return Counter(ring).most_common(1)[0]


def outside_cells(tiles, tile):
    """The filler reachable from the edge of the grid, as {(col, row)}.

    Flooded inward rather than tested cell by cell, and the difference is not
    academic. Waterfall's $46 is the open water *outside* the map and the room
    floor *inside* it -- the same tile id and the same two property bytes in
    both places, which is the fact that defeated every per-tile test the room
    work tried. `tiles[i] == filler` would call that room floor filler and crop
    the room away. A flood from the edge cannot reach it: the wall is in the
    way.
    """
    seen, q = set(), deque()

    def push(col, row):
        if (col, row) not in seen and tiles[row * MAP_DIM + col] == tile:
            seen.add((col, row))
            q.append((col, row))

    for n in range(MAP_DIM):
        push(n, 0)
        push(n, MAP_DIM - 1)
        push(0, n)
        push(MAP_DIM - 1, n)
    while q:
        col, row = q.popleft()
        for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            c, r = col + dc, row + dr
            if 0 <= c < MAP_DIM and 0 <= r < MAP_DIM:
                push(c, r)
    return seen


CROP_PAD = 1


def content_box(tiles, pad=CROP_PAD):
    """(c0, c1, r0, r1), inclusive: the part of the grid worth drawing.

    The bounding box of everything the edge flood could not reach, padded so
    the wall the content ends against stays in frame. One tile rather than none
    for two reasons: a room's outer wall is content, and tests/test_maps.lua
    bounds-checks every marker with a 12px half-box, which a 16px pad clears.

    A map whose content reaches every edge comes back as the whole grid --
    Waterfall very nearly does, sky4F does. That is the honest answer, not a
    failure.
    """
    tile, _ = backdrop_tile(tiles)
    outside = outside_cells(tiles, tile)
    content = [(i % MAP_DIM, i // MAP_DIM) for i in range(MAP_DIM * MAP_DIM)
               if (i % MAP_DIM, i // MAP_DIM) not in outside]
    if not content:
        return 0, MAP_DIM - 1, 0, MAP_DIM - 1
    cols = [c for c, _ in content]
    rows = [r for _, r in content]
    return (max(0, min(cols) - pad), min(MAP_DIM - 1, max(cols) + pad),
            max(0, min(rows) - pad), min(MAP_DIM - 1, max(rows) + pad))


def in_box(box, col, row):
    c0, c1, r0, r1 = box
    return c0 <= col <= c1 and r0 <= row <= r1


def crop_violations(rom, map_id, tiles, box, graph, extra=()):
    """[(what, (col, row))] that the box would cut off and must not.

    Zero on all 61 maps of three FFR cartridges, a fourth FFR seed and a
    vanilla image, which is what makes this a guard rather than a hope. What it
    covers, and why each is in it:

      * **treasure-chest tiles**, because a cropped-away chest is a marker with
        nowhere to draw;
      * **NORM and EXIT teleports** -- every staircase and every map exit. WARP
        is left out on purpose: it is the warp-out field that blankets a town
        or castle exterior, 30875 tiles of it on one cartridge, and it *is* the
        filler being cropped rather than content standing in it;
      * **`extra`**, whatever else the caller draws markers for. regen_maps
        passes the pack's tracked NPCs, and that is not decoration: the Ice
        Cave B1 fairy stands on a cell the flood reaches, so it is exactly the
        kind of thing a bad box would lose.
    """
    tileset = rom[TILESET_LUT + map_id]
    prop = TILESET_PROP + tileset * PROP_STRIDE
    bad = []
    chest_tiles = {t for t in range(TILES_PER_SET)
                   if (rom[prop + t * 2] & entrance_graph.TP_SPEC_MASK)
                   == entrance_graph.TP_SPEC_TREASURE}
    for i, t in enumerate(tiles):
        cell = (i % MAP_DIM, i // MAP_DIM)
        if (t & 0x7F) in chest_tiles and not in_box(box, *cell):
            bad.append(("chest", cell))
    for x, y, kind, _ in graph.teleports(map_id):
        if kind != entrance_graph.TP_TELE_WARP and not in_box(box, x, y):
            bad.append((f"teleport ${kind:02X}", (x, y)))
    for what, col, row in extra:
        if not in_box(box, col, row):
            bad.append((what, (col, row)))
    return bad


def cropped_objects(map_id, box, graph):
    """[(object id, (col, row))] the box leaves outside the frame.

    Reported rather than fatal, because one of these is real and correct.
    Marsh Cave B1 carries a fifth bat parked at (52,22) on void tile $3F, with
    the same graphic as its four placed ones; it is there on a vanilla
    cartridge too, so it is the game's own spare slot and not something a seed
    did. Anything else showing up here wants looking at.
    """
    return [(oid, (x, y)) for oid, x, y in graph.objects(map_id)
            if not in_box(box, x, y)]


# ---------------------------------------------------------------- trap tiles

# FFR randomizes which monsters a trap tile throws at you and the tracker says
# nothing about it. The shipped art does: a yellow capital letter on the tile,
# and a Map Key on the backdrop saying what each letter is. The letters are
# derivable, which is worth stating because it was not obvious -- they are
# positions in the cartridge's own flat tileset order.
#
# A trap tile is TP_SPEC_BATTLE, and tile properties live per tileset, so a
# tile id means the same thing on every map sharing that tileset: the same trap
# in Sea Shrine and Temple of Fiends is literally the same two ROM bytes.
# Enumerating the fixed-formation ones over all eight tilesets in order and
# labelling them A, B, C ... reproduces the shipped art on a vanilla cartridge:
# earthB1 comes out {G, H, I} and volcB4 {M, N}, which is what DarkmoonEX drew.
# volcB1's bare `A` is not a trap letter under this scheme and is not supposed
# to be -- it is an entrance label, and the derivation agreeing about that is
# part of why it is believable.
#
# The letters shift by a place or two on an FFR seed, because the shuffle turns
# some fixed formations random and they drop out of the ordering. That is fine
# and unavoidable: a letter's job is to key a tile to the legend drawn on the
# same image.

TP_SPEC_BATTLE = 0x0A
TILESET_COUNT = 8
SMMOVE_BATTLE_BPL = 0x0DC5    # offset into the fixed $C000 bank


def fixed_bank(rom):
    """The last bank: $0F on a stock 16-bank image, $1F on an FFR one."""
    return (len(rom) - INES_HEADER) // BANK_SIZE - 1


def battle_byte_inverted(rom):
    """True when SMMove_Battle's BPL has been patched to BNE.

    FFR does this on every seed (SpikeTile.cs:136-151, called unconditionally
    from Randomize.cs:220) and it inverts what byte 1 of a trap tile means:

        vanilla   b1 & 0x80 set -> random encounter, else fixed formation b1
        FFR       b1 == 0x00    -> random encounter, else fixed formation b1,
                                   0x80-0xFF included

    Read rather than assumed. The opcode sits at 0x0DC5 in the fixed bank --
    file offset 0x3CDD5 on a vanilla cartridge and 0x7CDD5 on an FFR one, the
    same `LDA $45 / branch / JSR $C571` either way.
    """
    off = INES_HEADER + fixed_bank(rom) * BANK_SIZE + SMMOVE_BATTLE_BPL
    op = rom[off]
    if op not in (0x10, 0xD0):
        raise ValueError(f"SMMove_Battle branch is ${op:02X} at 0x{off:X}, "
                         "expected $10 (BPL) or $D0 (BNE)")
    return op == 0xD0


def _label(n):
    """A, B, ... Z, AA, AB, ... -- there are more trap tiles than letters."""
    a = string.ascii_uppercase
    return a[n] if n < len(a) else a[n // len(a) - 1] + a[n % len(a)]


def trap_letters(rom):
    """{(tileset, tile): letter} for every fixed-formation trap tile."""
    inverted = battle_byte_inverted(rom)
    out = {}
    for tileset in range(TILESET_COUNT):
        base = TILESET_PROP + tileset * PROP_STRIDE
        for tile in range(TILES_PER_SET):
            b0, b1 = rom[base + tile * 2], rom[base + tile * 2 + 1]
            if (b0 & entrance_graph.TP_SPEC_MASK) != TP_SPEC_BATTLE:
                continue
            random = (b1 == 0) if inverted else bool(b1 & 0x80)
            if random:
                continue
            out[(tileset, tile)] = _label(len(out))
    return out


def map_trap_letters(rom, map_id, tiles, letters=None):
    """{(col, row): letter} for the trap tiles standing on one map."""
    letters = trap_letters(rom) if letters is None else letters
    tileset = rom[TILESET_LUT + map_id]
    return {(i % MAP_DIM, i // MAP_DIM): letters[(tileset, t & 0x7F)]
            for i, t in enumerate(tiles) if (tileset, t & 0x7F) in letters}


# The Map Key is drawn in the phase that draws the letters; what is reserved
# here is somewhere to put it. A band below the map rather than beside it, so
# offset_y is untouched and no marker moves, filled with the map's own backdrop
# tile -- which is what the hand art does, its backdrop being the map's own
# outdoor tint. Measured: 23 of 61 maps use a letter at all and the most any
# map uses is four, so the band is small and bounded.
LEGEND_HEADING_ROWS = 2


def legend_rows_for(letter_count):
    """How many tile-height rows to reserve for a map's Map Key."""
    return 0 if not letter_count else LEGEND_HEADING_ROWS + letter_count


def render(rom, map_id, inside=False, unroof=False, graph=None, only=None,
           crop=None, legend_rows=0):
    """(w, h, rgb_bytes) for one standard map.

    `unroof` draws the rooms open: outdoor palette everywhere, room palette on
    the cells a roof covers, so a single image shows the map as you walk it and
    the room contents at the same time -- floor included, see hidden_cells. It
    is a no-op on a map with no rooms.

    Pass an entrance_graph.Graph as `graph` to draw the map's NPCs on the tiles
    they stand on, which is how a gate NPC becomes visible as the barrier it is
    rather than a line of --gates output. The caller supplies the graph because
    building one reads and decompresses map data, and a caller rendering all 61
    maps should pay for that once. `only` narrows that to a set of object ids.

    `crop` is a (c0, c1, r0, r1) tile box -- content_box(tiles) -- and
    `legend_rows` reserves that many tile-heights of backdrop below the map for
    a Map Key. Both default to off, so a plain render is still the whole 64x64
    grid at 1024x1024 and --check still compares like with like.
    """
    tiles = map_tiles(rom, map_id)
    tileset = rom[TILESET_LUT + map_id]
    art = tileset_art(rom, tileset, map_palettes(rom, map_id, inside))
    open_art = tileset_art(rom, tileset, map_palettes(rom, map_id, True)) \
        if unroof and not inside else None
    rooms = hidden_cells(rom, map_id, tiles, art, open_art) if open_art else set()

    c0, c1, r0, r1 = crop if crop else (0, MAP_DIM - 1, 0, MAP_DIM - 1)
    w = (c1 - c0 + 1) * TILE_PX
    h = (r1 - r0 + 1 + legend_rows) * TILE_PX
    out = bytearray(w * h * 3)
    for row in range(r0, r1 + 1):
        for col in range(c0, c1 + 1):
            here = open_art if (row, col) in rooms else art
            block = here[tiles[row * MAP_DIM + col] & 0x7F]
            for y in range(TILE_PX):
                dst = (((row - r0) * TILE_PX + y) * w + (col - c0) * TILE_PX) * 3
                line = block[y]
                for x in range(TILE_PX):
                    r, g, b = line[x]
                    out[dst] = r
                    out[dst + 1] = g
                    out[dst + 2] = b
                    dst += 3
    if legend_rows:
        # The band is the map's own backdrop tile, tiled -- the same thing the
        # hand art fills its margins with, so the Map Key drawn into it later
        # sits on the map's colour rather than on an invented one.
        block = art[backdrop_tile(tiles)[0] & 0x7F]
        for row in range(r1 - r0 + 1, r1 - r0 + 1 + legend_rows):
            for col in range(c1 - c0 + 1):
                for y in range(TILE_PX):
                    dst = ((row * TILE_PX + y) * w + col * TILE_PX) * 3
                    line = block[y]
                    for x in range(TILE_PX):
                        r, g, b = line[x]
                        out[dst] = r
                        out[dst + 1] = g
                        out[dst + 2] = b
                        dst += 3
    if graph is not None:
        # Imported here, not at module scope: sprites imports this module for
        # the NES palette and the tile decode.
        import sprites                                              # noqa: E402
        sprites.draw_objects(rom, graph, map_id, w, h, out, only, (c0, r0))
    return w, h, bytes(out)


# The pack's own name for each standard map, taken from
# scripts/autotracking/mapValues.lua's MAP_VALUE, which is what the tracker
# itself keys off. Nine of these -- the eight towns and Coneria Castle 2F --
# name images the pack does not ship yet: it screenshotted only what vanilla
# gives a tab to, and No-Overworld turns the towns into real rooms. Rendering
# them is the point; wiring the tabs is a separate step. Bahamut's Lair and
# Coneria Castle are two maps apiece (17/39 and 8/24), which the pack draws as
# one composite image each, so those keep the floor suffix here.
MAP_FILES = {
    0: "coneria_town", 1: "pravoka", 2: "elfland", 3: "melmond",
    4: "crescent_lake", 5: "gaia", 6: "onrac", 7: "lefein",
    8: "con_castle", 9: "elf_castle", 10: "nw_castle",
    11: "ordeals1F", 12: "tof", 13: "earthB1", 14: "volcB1",
    15: "iceB1", 16: "cardia", 17: "bahamut", 18: "waterfall",
    19: "dwarves", 20: "matoya", 21: "sarda", 22: "marshB1",
    23: "mirage1F", 24: "con_castle2F", 25: "ordeals2F", 26: "ordeals3F",
    27: "marshB2", 28: "marshB3", 29: "earthB2", 30: "earthB3",
    31: "earthB4", 32: "earthB5", 33: "volcB2", 34: "volcB3",
    35: "volcB4", 36: "volcB5", 37: "iceB2", 38: "iceB3",
    39: "bahamutB2", 40: "mirage2F", 41: "mirage3F", 42: "seaB5",
    43: "seaB4", 44: "seaB3", 45: "seaB2", 46: "seaB1",
    47: "sky1F", 48: "sky2F", 49: "sky3F", 50: "sky4F",
    51: "sky5F", 52: "tofr1F", 53: "tofr2F", 54: "tofr3F",
    55: "tofrEarth", 56: "tofrFire", 57: "tofrWater", 58: "tofrAir",
    59: "tofrChaos", 60: "titans",
}

assert len(MAP_FILES) == MAP_COUNT and len(set(MAP_FILES.values())) == MAP_COUNT


def check(rom, ref_dir):
    """Compare against FF1R renderdungeon output in ref_dir.

    A diagnostic, not a gate: FF1R draws the vanilla map (see the module
    docstring), so every map the seed changed is *expected* to differ. What the
    comparison is good for is spotting a difference on a map the seed did not
    touch, which would mean something here is wrong rather than there.
    """
    bad = missing = 0
    for map_id in range(MAP_COUNT):
        ref = os.path.join(ref_dir, f"dungeonmap{map_id}.png")
        if not os.path.exists(ref):
            missing += 1
            continue
        rw, rh, rgb = pngio.read_rgb(ref)
        w, h, mine = render(rom, map_id)
        if (rw, rh) != (w, h) or rgb != mine:
            diff = sum(1 for a, b in zip(rgb, mine) if a != b) if (rw, rh) == (w, h) else -1
            print(f"  DIFFER map {map_id} ({MAP_FILES[map_id]}): {diff} bytes")
            bad += 1
    checked = MAP_COUNT - missing
    if missing:
        print(f"  ({missing} maps had no reference image)")
    print(f"{bad} of {checked} maps differ from FF1R's renderer. FF1R draws the "
          "vanilla map, so on a seed that edits maps this is expected -- the "
          "count should track how many maps the seed changed. A difference on "
          "an untouched map is the thing worth chasing.")
    return True


def self_check(rom, path):
    """Every crop box against the cartridge it came from.

    The box is derived from one flood, so the way it goes wrong is by cutting
    something off. That is the thing tested: chests, staircases, exits and the
    pack's own tracked NPCs all have to survive it. Zero violations is the
    measured baseline on three FFR seeds, a fourth, and a vanilla image.
    """
    graph = entrance_graph.Graph(entrance_graph.Rom.of(rom, path))
    npcs = {}
    with open(os.path.join(HERE, "npc_positions.json")) as f:
        for name, places in json.load(f).items():
            for q in places:
                npcs.setdefault(q["map_id"], []).append(
                    (f"npc {name}", q["tile_col"], q["tile_row"]))

    bad = kept = 0
    parked = []
    for map_id in range(MAP_COUNT):
        tiles = map_tiles(rom, map_id)
        box = content_box(tiles)
        kept += (box[1] - box[0] + 1) * (box[3] - box[2] + 1)
        for what, cell in crop_violations(rom, map_id, tiles, box, graph,
                                          npcs.get(map_id, ())):
            print(f"  CUT OFF map {map_id} ({MAP_FILES[map_id]}): {what} at {cell}")
            bad += 1
        parked += [(MAP_FILES[map_id], oid, cell)
                   for oid, cell in cropped_objects(map_id, box, graph)]

    print(f"crop keeps a mean {kept / MAP_COUNT / (MAP_DIM * MAP_DIM) * 100:.0f}% "
          f"of the grid across {MAP_COUNT} maps")
    for name, oid, cell in parked:
        print(f"  note: {name} object {oid} at {cell} is outside its box "
              "(parked out of bounds; marshB1's spare bat is the known one)")
    letters = trap_letters(rom)
    used = sum(1 for m in range(MAP_COUNT)
               if map_trap_letters(rom, m, map_tiles(rom, m), letters))
    print(f"{len(letters)} fixed-formation trap tiles, used on {used} maps; "
          f"SMMove_Battle byte 1 is "
          f"{'FFR (b1 == 0 is random)' if battle_byte_inverted(rom) else 'vanilla (b1 & $80 is random)'}")
    if bad:
        print(f"self-check FAILED: {bad} things the crop would cut off")
        return False
    print("self-check passed: the crop cuts off nothing it must not")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("-o", "--out", help="directory to write PNGs into")
    ap.add_argument("--map", type=int, help="render one standard map id (0-60)")
    ap.add_argument("--inside", action="store_true",
                    help="use the room palette rather than the outdoor one")
    ap.add_argument("--unroof", action="store_true",
                    help="draw rooms open, so their chests and furniture show")
    ap.add_argument("--objects", action="store_true",
                    help="draw the map's NPCs on the tiles they stand on")
    ap.add_argument("--check", metavar="DIR",
                    help="compare against FF1R renderdungeon output in DIR")
    ap.add_argument("--crop", action="store_true",
                    help="crop each map to its content, with a Map Key band")
    ap.add_argument("--self-check", action="store_true",
                    help="check every crop box against the cartridge")
    args = ap.parse_args()

    with open(args.rom, "rb") as f:
        rom = f.read()
    if rom[:4] != b"NES\x1a":
        sys.exit("not an iNES ROM")

    if args.check:
        return 0 if check(rom, args.check) else 1

    if args.self_check:
        return 0 if self_check(rom, args.rom) else 1

    if not args.out:
        sys.exit("nothing to do: pass -o DIR to write images, or --check DIR")
    os.makedirs(args.out, exist_ok=True)

    if args.map is not None and args.map not in MAP_FILES:
        sys.exit(f"no such standard map: {args.map} (0-{MAP_COUNT - 1})")
    graph = None
    if args.objects:
        import entrance_graph                                       # noqa: E402
        graph = entrance_graph.Graph(entrance_graph.Rom.of(rom, args.rom))

    letters = trap_letters(rom) if args.crop else None
    ids = [args.map] if args.map is not None else range(MAP_COUNT)
    for map_id in ids:
        name = MAP_FILES[map_id]
        box = rows = None
        if args.crop:
            tiles = map_tiles(rom, map_id)
            box = content_box(tiles)
            rows = legend_rows_for(
                len(set(map_trap_letters(rom, map_id, tiles, letters).values())))
        w, h, rgb = render(rom, map_id, args.inside, args.unroof, graph,
                           crop=box, legend_rows=rows or 0)
        path = os.path.join(args.out, name + ".png")
        pngio.write_rgb(path, w, h, rgb)
        where = (f"tile (c,r) is pixel ({TILE_PX}(c-{box[0]}), {TILE_PX}(r-{box[2]}))"
                 if box else f"tile n is pixel {TILE_PX}n")
        print(f"wrote {path}  ({w}x{h}, {where})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
