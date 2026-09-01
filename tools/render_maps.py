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

Cropping is what makes a tab readable. A mean 46% of the grid survives it, and
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
import os
import string
import sys
from collections import Counter, deque
from typing import NamedTuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from extract_chests import (  # noqa: E402
    BANK_SIZE, INES_HEADER, MAP_COUNT, MAP_DIM, PROP_STRIDE, TILESET_LUT,
    TILESET_PROP, decompress_map, map_data_base,
)
import entrance_graph  # noqa: E402
import extract_npcs  # noqa: E402
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
# numbers came out where the art already was. Mean kept area is 46% of the
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


def content_cells(tiles):
    """{(col, row)}: everything the edge flood could not reach."""
    tile, _ = backdrop_tile(tiles)
    outside = outside_cells(tiles, tile)
    return {(i % MAP_DIM, i // MAP_DIM) for i in range(MAP_DIM * MAP_DIM)
            if (i % MAP_DIM, i // MAP_DIM) not in outside}


# A standard map is a torus: column 63 is next to column 0, and the game scrolls
# across the join without comment. Four maps are drawn across it -- Coneria
# Castle's two halves sit at columns 0-8 and 44-63 with 35 empty columns
# between them -- and a box measured in rom coordinates has to span the void to
# hold both, which is how con_castle came out 64x35 for a map that is 31 wide.
#
# So the grid slides before it is boxed. The widest empty run goes off the end,
# the content becomes one contiguous block, and the box is measured there. Only
# the tile-to-pixel mapping learns about the slide; every consumer still
# receives a plain axis-aligned box.


def _axis_shift(occupied, pad):
    """How far to slide one axis so its widest empty run falls off the end.

    Zero unless the content actually crosses the join -- index 0 and index 63
    both in use, with something free between them.

    That test is narrower than "slide whenever it would help", and deliberately
    so. It is **not** true that a contiguous map has nothing to gain: iceB3's
    widest gap is 18 columns in its *interior*, so a forced slide would take its
    box from 62 columns to 48, and iceB2's from 62 to 58. Both are declined, and
    both should be -- they are the multi-lobe maps in docs/ISSUES.md, where
    re-phasing moves the left lobe to the right of the right one and costs more
    legibility than the columns are worth. Laying their lobes out separately is
    the fix, and it is a different idea.

    What the join test buys is that the slide only fires where the box is
    otherwise forced to span the void, which is the case it was written for and
    the only one where a re-phased image is unambiguously better. The cost of
    firing it anywhere else is a moved image and a multi-region calibration, so
    the bar is a box that cannot be measured at all rather than a box that could
    be smaller.
    """
    if len(occupied) in (0, MAP_DIM):
        return 0
    if not (0 in occupied and MAP_DIM - 1 in occupied):
        return 0
    best = (0, 0)
    for start in range(MAP_DIM):
        if start in occupied or (start - 1) % MAP_DIM not in occupied:
            continue                                  # not the start of a run
        length = 0
        while (start + length) % MAP_DIM not in occupied:
            length += 1
        if length > best[1]:
            best = (start, length)
    start, length = best
    return (pad - (start + length)) % MAP_DIM


class Crop(NamedTuple):
    """A tile box, and how far the grid slid before it was measured.

    `box` is (c0, c1, r0, r1) inclusive, axis-aligned, exactly the shape it has
    always been. `shift` is (sx, sy): what to add to a rom tile coordinate,
    modulo the grid, before the box means anything. On the maps whose content
    does not cross the join the shift is (0, 0) and the two say the same thing.

    Nothing outside this class does that arithmetic. `place` is the one
    tile-to-pixel mapping, and a consumer that wants the plain box takes
    `.box` -- which is what the calibration, the marker bounds and the render's
    own frame loop all do.
    """

    box: tuple
    shift: tuple = (0, 0)

    @property
    def size(self):
        """(cols, rows) the frame is across."""
        c0, c1, r0, r1 = self.box
        return c1 - c0 + 1, r1 - r0 + 1

    def place(self, col, row):
        """(frame col, frame row) for a rom tile, or None if it is not in frame."""
        c0, c1, r0, r1 = self.box
        c = (col + self.shift[0]) % MAP_DIM
        r = (row + self.shift[1]) % MAP_DIM
        if not (c0 <= c <= c1 and r0 <= r <= r1):
            return None
        return c - c0, r - r0

    def source(self, col, row):
        """The rom tile a frame cell draws -- place() the other way round."""
        c0, _, r0, _ = self.box
        return ((col + c0 - self.shift[0]) % MAP_DIM,
                (row + r0 - self.shift[1]) % MAP_DIM)

    def holds(self, col, row):
        return self.place(col, row) is not None


WHOLE = Crop((0, MAP_DIM - 1, 0, MAP_DIM - 1))


# A speck is a run of content the flood could not reach, holding nothing the
# map points at, far enough from the map to hold the frame open on its own.
# Lefein has five of them at one cell each, fifteen rows below the town, and
# they cost seventeen rows of empty frame.
#
# Two tests, and the pairing is the point. Size alone was tried and rejected --
# Matoya's four-cell speck against Ice Cave B3's genuine 41-cell second lobe --
# and so was walkability. What separates them here is **what the map points
# at**: a region carrying a chest, a staircase, an exit or a tracked NPC is
# content by definition, whatever its size, and is kept. The size bound then
# only has to separate specks from regions that are merely large and empty.
#
# Measured over vanilla, both duck cartridges and both oracle cartridges, that
# band is wide: the largest droppable region is 19 cells and the smallest kept
# one is 88. The bound sits in the empty middle, and tools/tests/test_crop.py
# asserts the band *stays* empty -- a cartridge that puts a region near the
# bound is one where this rule has started guessing, and the test says so
# rather than letting it guess.
#
# Both numbers moved once components() learned the grid wraps, and in the safe
# direction: the flat flood was splitting wrapped regions and offering their
# smaller halves here as droppable, which is what dragged the kept floor down
# to 58. Melmond's "one-column stalk" was one of them -- a 13-cell road that
# is torus-adjacent to the town and was never a speck at all.
MAX_SPECK = 32


def components(cells):
    """`cells` split into 4-connected regions, largest first.

    **Connectivity wraps**, because the grid is a torus -- which is the same
    fact _axis_shift exists for. A map that runs off the right edge continues
    at column 0, and a region straddling that join is one region, not two.

    Flooding this flat was a real defect rather than a nicety. It splits a
    wrapped region in two, and the smaller half then looks exactly like a
    speck to drop_specks and is thrown away: on vanilla sky4F -- a 4x4 tiling
    of sixteen 88-cell rooms -- seven rooms were being shaved to 80 cells and
    the eight 8-cell strips discarded, and melmond lost its 13-cell road and
    elf_castle its 5-cell approach the same way. None of it trips
    crop_violations, because nothing the map points at stands on those cells.
    The cut only shows in the image.
    """
    remaining, out = set(cells), []
    while remaining:
        seed = remaining.pop()
        comp, q = {seed}, deque([seed])
        while q:
            col, row = q.popleft()
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = ((col + dc) % MAP_DIM, (row + dr) % MAP_DIM)
                if n in remaining:
                    remaining.discard(n)
                    comp.add(n)
                    q.append(n)
        out.append(comp)
    return sorted(out, key=len, reverse=True)


def drop_specks(content, keep=(), limit=MAX_SPECK):
    """(kept cells, dropped regions) -- content minus the specks.

    The largest region is never dropped, so a map cannot crop to nothing here
    however small it is: Bahamut's lair is six columns wide and stays.
    """
    comps = components(content)
    if not comps:
        return content, []
    keep = set(keep)
    dropped = [c for c in comps[1:] if len(c) <= limit and not (c & keep)]
    if not dropped:
        return content, []
    gone = set().union(*dropped)
    return {c for c in content if c not in gone}, dropped


def content_crop(tiles, pad=CROP_PAD, keep=()):
    """The part of the grid worth drawing, as a Crop.

    The bounding box of everything the edge flood could not reach, measured
    after the slide above, and padded so the wall the content ends against
    stays in frame. One tile rather than none for two reasons: a room's outer
    wall is content, and tests/test_maps.lua bounds-checks every marker with a
    12px half-box, which a 16px pad clears.

    A map whose content reaches every edge comes back as the whole grid --
    Waterfall very nearly does. That is the honest answer, not a failure.

    `keep` is the cells the crop must not lose -- protected_cells' second
    element, which regen and the tests already build for crop_violations. It is
    what stops a speck-shaped region that happens to hold a chest from being
    dropped. Defaulting it to empty is safe rather than convenient: the guard
    runs on every regen and every test, so a caller that forgets to pass it is
    caught by the same check that catches a bad flood.
    """
    content = content_cells(tiles)
    if not content:
        return WHOLE
    content, _ = drop_specks(content, keep)
    sx = _axis_shift({c for c, _ in content}, pad)
    sy = _axis_shift({r for _, r in content}, pad)
    cols = [(c + sx) % MAP_DIM for c, _ in content]
    rows = [(r + sy) % MAP_DIM for _, r in content]
    return Crop((max(0, min(cols) - pad), min(MAP_DIM - 1, max(cols) + pad),
                 max(0, min(rows) - pad), min(MAP_DIM - 1, max(rows) + pad)),
                (sx, sy))


def crop_violations(rom, map_id, tiles, crop, graph, extra=()):
    """[(what, (col, row))] that the crop would cut off and must not.

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
    return [(what, cell) for what, cell in protected_cells(
        rom, map_id, tiles, graph, extra) if not crop.holds(*cell)]


def protected_cells(rom, map_id, tiles, graph, extra=()):
    """[(what, (col, row))] the crop is not allowed to lose, whatever it does.

    One list, two readers. crop_violations reports the ones a box left outside
    the frame; content_crop refuses to discard a region that holds any of them.
    Having them derive the set separately is how a rule that drops a speck and
    a guard that checks for specks come to disagree about what a speck is.
    """
    tileset = rom[TILESET_LUT + map_id]
    prop = TILESET_PROP + tileset * PROP_STRIDE
    out = []
    chest_tiles = {t for t in range(TILES_PER_SET)
                   if (rom[prop + t * 2] & entrance_graph.TP_SPEC_MASK)
                   == entrance_graph.TP_SPEC_TREASURE}
    for i, t in enumerate(tiles):
        if (t & 0x7F) in chest_tiles:
            out.append(("chest", (i % MAP_DIM, i // MAP_DIM)))
    for x, y, kind, _ in graph.teleports(map_id):
        if kind != entrance_graph.TP_TELE_WARP:
            out.append((f"teleport ${kind:02X}", (x, y)))
    for what, col, row in extra:
        out.append((what, (col, row)))
    return out


def cropped_objects(map_id, crop, graph):
    """[(object id, (col, row))] the crop leaves outside the frame.

    Reported rather than fatal, because one of these is real and correct.
    Marsh Cave B1 carries a fifth bat parked at (52,22) on void tile $3F, with
    the same graphic as its four placed ones; it is there on a vanilla
    cartridge too, so it is the game's own spare slot and not something a seed
    did. Anything else showing up here wants looking at.
    """
    return [(oid, (x, y)) for oid, x, y in graph.objects(map_id)
            if not crop.holds(x, y)]


# ---------------------------------------------------------------- trap tiles

# FFR randomizes which monsters a trap tile throws at you and the tracker says
# nothing about it. The shipped art does: a yellow capital mark on the tile,
# and a Map Key on the backdrop saying what each mark is. The marks are
# derivable, which is worth stating because it was not obvious -- they are
# positions in the cartridge's own flat tileset order.
#
# A trap tile is TP_SPEC_BATTLE, and tile properties live per tileset, so a
# tile id means the same thing on every map sharing that tileset: the same trap
# in Sea Shrine and Temple of Fiends is literally the same two ROM bytes. But a
# tile is not a fight -- the byte beside it is, and one formation is reachable
# through more than one tileset entry, which is why the mark is keyed to the
# formation and not to the tile. Keyed to the tile, the same enemies came out
# G on earthB1 and W on marshB3.
#
# The marks are handed out in tileset-scan order, which is the order the
# shipped art numbers them in, and only to formations that stand on some map.
# That second filter is what keeps a mark to one glyph, and it is also the one
# place this parts company with DarkmoonEX: he counted formation $00, which is
# a fixed trap tile in five tileset entries that no map places, so his letters
# are these shifted by exactly one -- his earthB1 G H I is this F G H, his
# volcB4 M N is this L M. tools/tests/test_crop.py asserts the shift and its
# cause rather than the bare marks.
#
# volcB1's bare `A` is not a trap mark under this scheme and is not supposed
# to be -- it is an entrance label, and the derivation agreeing about that is
# part of why it is believable.
#
# Which formations stand on a map moves with the seed, so the marks do too.
# That is fine and unavoidable: a mark's job is to key a tile to the legend
# drawn on the same image.

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
    """A, B, ... Z, AA, AB, ... -- the fallback when the marks run out."""
    a = string.ascii_uppercase
    return a[n] if n < len(a) else a[n // len(a) - 1] + a[n % len(a)]


# The marks a trap tile can carry, in the order they are handed out. Every one
# is a single glyph in the cartridge's own font, which is what lets a mark
# occupy exactly the tile it marks. `O` is left out because it and `0` are the
# same glyph in this font -- tools/font.py asserts precisely that -- so a key
# offering both would ask the reader to tell apart two identical drawings.
# Letters before digits, because the shipped art numbers its fights with
# letters and 25 of them covers most of a cartridge on its own; the digits are
# the tail that takes a busy one to 35.
TRAP_MARKS = "ABCDEFGHIJKLMNPQRSTUVWXYZ0123456789"

assert len(set(TRAP_MARKS)) == len(TRAP_MARKS) == 35
assert "O" not in TRAP_MARKS


def fixed_formations(rom):
    """{(tileset, tile): formation id} for every fixed-formation trap tile."""
    inverted = battle_byte_inverted(rom)
    out = {}
    for tileset in range(TILESET_COUNT):
        base = TILESET_PROP + tileset * PROP_STRIDE
        for tile in range(TILES_PER_SET):
            b0, b1 = rom[base + tile * 2], rom[base + tile * 2 + 1]
            if (b0 & entrance_graph.TP_SPEC_MASK) != TP_SPEC_BATTLE:
                continue
            random = (b1 == 0) if inverted else bool(b1 & 0x80)
            if not random:
                out[(tileset, tile)] = b1
    return out


def standing_formations(rom, fixed=None):
    """The fixed formations a trap tile somewhere on a map actually spawns.

    In tileset-scan order, which is the order the shipped art numbers them in.
    Two filters, and both are what make a single-glyph mark possible:

      * **by formation, not by tile.** A formation reachable through two
        tileset entries is one fight and wants one mark. Keying by
        (tileset, tile) is what drew the same enemies as G on earthB1 and W on
        marshB3;
      * **only what stands on a map.** The tileset tables carry fixed-formation
        entries no map places -- four of them on a vanilla cartridge -- and a
        mark for a fight that cannot be met is a row in the key doing nothing.

    Together they take a vanilla cartridge from 43 lettered tiles to 32 marks,
    the std oracle to 33 and the nov oracle to 32, all inside the 35 the font
    can draw one glyph for.
    """
    fixed = fixed_formations(rom) if fixed is None else fixed
    standing = set()
    for map_id in MAP_FILES:
        tileset = rom[TILESET_LUT + map_id]
        for tile in map_tiles(rom, map_id):
            if (tileset, tile & 0x7F) in fixed:
                standing.add(fixed[(tileset, tile & 0x7F)])
    order = []
    for key in sorted(fixed):
        if fixed[key] in standing and fixed[key] not in order:
            order.append(fixed[key])
    return order


def trap_marks(rom):
    """{(tileset, tile): mark} -- one mark per formation, not one per tile.

    Past what the font can draw as single glyphs the labelling switches to
    _label, rather than reusing a mark: a repeated mark is a map that lies about
    which fight is on the tile, and that is worse than a label too wide to sit
    on one. No measured cartridge reaches it -- 32 formations stand on a map on
    vanilla, std and nov2, 31 on nov and shard, against 35 marks.

    Note what the fallback actually does, because it is not "the cartridge
    switches to two-character labels". _label is per index: the first 26
    formations still come out as single letters -- including `O`, which
    TRAP_MARKS excludes on purpose because the font draws it and `0` the same
    -- and only the 27th onward is two characters. So a cartridge that trips
    this loses the O/0 guarantee across the board and gains width on the tail
    only. Widening TRAP_MARKS would be the better answer if one ever does.
    """
    fixed = fixed_formations(rom)
    order = standing_formations(rom, fixed)
    if len(order) <= len(TRAP_MARKS):
        mark = {f: TRAP_MARKS[i] for i, f in enumerate(order)}
    else:
        mark = {f: _label(i) for i, f in enumerate(order)}
    return {key: mark[f] for key, f in fixed.items() if f in mark}


def map_trap_marks(rom, map_id, tiles, marks=None):
    """{(col, row): mark} for the trap tiles standing on one map."""
    marks = trap_marks(rom) if marks is None else marks
    tileset = rom[TILESET_LUT + map_id]
    return {(i % MAP_DIM, i // MAP_DIM): marks[(tileset, t & 0x7F)]
            for i, t in enumerate(tiles) if (tileset, t & 0x7F) in marks}


# The Map Key is drawn in the phase that draws the marks; what is reserved
# here is somewhere to put it. A band below the map rather than beside it, so
# offset_y is untouched and no marker moves, filled with the map's own backdrop
# tile -- which is what the hand art does, its backdrop being the map's own
# outdoor tint. Measured: 23 of 61 maps use a mark at all and the most any
# map uses is four, so the band is small and bounded.
LEGEND_HEADING_ROWS = 2


def legend_rows_for(mark_count, lane_keys=0):
    """How many tile-height rows to reserve for a map's Map Key.

    Lane entries share the band with the trap marks rather than getting one of
    their own: the reference's key is a single list too, and two panels on a
    map that has both would push the art up twice.
    """
    n = mark_count + lane_keys
    return 0 if not n else LEGEND_HEADING_ROWS + n


# The Map Key's colours, as tile ids in the NES palette rather than as RGB
# literals: the shipped art marks its trap tiles yellow and writes its key in
# white on a dark panel, and these are the cartridge's own nearest equivalents.
LETTER_COLOUR = 0x28          # yellow
KEY_TEXT_COLOUR = 0x30        # white
SHADOW_COLOUR = 0x0F          # black
LETTER_SCALE = TILE_PX // 8   # a glyph is 8px, a tile is 16, so a mark fills it
KEY_PAD = 4

# The lane colours, NES palette ids for the same reason the mark colours are:
# the swatch in the key and the line on the map have to be the same colour, and
# naming it once is how they stay that way. The reference is not consistent
# about this -- his cyan and purple swap roles between the optimised route and
# the with-loot one from map to map -- so fixing one colour per lane across all
# 61 is the thing to improve on rather than copy.
LANE_PLAIN = 0x2C             # cyan   -- the walk you can always do
LANE_KEY = 0x34               # purple -- only the steps a key buys
LANE_FORCED = 0x16            # red    -- a trap tile with no way round
LANE_LINK = 0x10              # silver -- two tiles that are one check
LANE_START = 0x30             # white  -- where the lane begins
LANE_PX = 5                   # the drawn width of a lane, in pixels
ARROW_PX = 6                  # the drawn length of a direction arrow

# Far enough apart that a corridor is not a row of arrowheads, close enough
# that a lane which doubles back says which pass is which. A lane without them
# says where to walk but not which way round, and on a route that doubles back
# that is most of the information.
ARROW_EVERY = 7

# The key's own wording. No punctuation anywhere: font.CHARS is digits and
# letters only, so a slash in "Optimal w/Key" draws as a gap.
LANE_KEY_TEXT = {
    "plain": "Optimal Route",
    "key": "Optimal w Key",
    "forced": "Forced Fight",
    "link": "Linked Chest",
}

# The swatch column: a sample of the line, then the name. Narrower than the
# trap letters' two tiles because the key has to fit the narrowest map that
# carries a chest, and on the No-Overworld cartridge that is sky5F at 256px.
KEY_SWATCH = TILE_PX * 3 // 2
KEY_TEXT_X = KEY_PAD + KEY_SWATCH + KEY_PAD


def draw_trap_marks(rom, font, out, w, h, crop, cells):
    """Letter the trap tiles in place.

    `cells` is map_trap_marks' {(col, row): mark}. Marks are drawn at the
    tile they mark, at LETTER_SCALE so a glyph is exactly one tile, with a
    one-pixel shadow -- a trap tile can sit on any floor colour, and yellow on
    sand is otherwise unreadable. The key that says what a letter means is
    draw_map_key's job, since the band is shared with the lanes.
    """
    yellow = NES_PALETTE[LETTER_COLOUR]
    black = NES_PALETTE[SHADOW_COLOUR]
    for (col, row), mark in sorted(cells.items()):
        at = crop.place(col, row)
        if at is None:
            continue
        font.draw_text(out, w, h, at[0] * TILE_PX, at[1] * TILE_PX,
                       mark, yellow, LETTER_SCALE, rom, black)


def lane_key_entries(lanes):
    """[(colour id, text)] -- the key rows one map's lanes need.

    Only what is actually on the image. A floor with no gate gets no purple
    row, a floor whose lane never has to cross a trap gets no red one, and a
    floor with no linked chests gets no silver one -- so the band stays as
    short as the map's own facts allow.
    """
    if lanes is None:
        return []
    out = []
    if any(r.label == "plain" for r in lanes.runs):
        out.append((LANE_PLAIN, LANE_KEY_TEXT["plain"]))
    if any(r.label == "key" for r in lanes.runs):
        out.append((LANE_KEY, LANE_KEY_TEXT["key"]))
    if any(c in r.traps for r in lanes.runs for c in r.path):
        out.append((LANE_FORCED, LANE_KEY_TEXT["forced"]))
    if lanes.links:
        out.append((LANE_LINK, LANE_KEY_TEXT["link"]))
    return out


def draw_map_key(rom, font, out, w, h, crop, legend_rows, marks, lanes):
    """Write the Map Key band: the lane swatches, then the trap letters.

    Lanes first because they are the thing the map is telling you to do and
    the letters are a caveat on it -- which is the order the reference's own
    key uses. `marks` is the distinct letters on this map, `lanes` the entries
    lane_key_entries derived.
    """
    # A heading over an empty list is not a key. The band is normally sized by
    # legend_rows_for, which returns nothing when there is nothing to say, but
    # a caller is free to reserve rows anyway and must not get a bare "Map Key"
    # for it -- which is what a render with no marks and no lanes was given
    # once the key stopped being the trap marks' own job.
    if not legend_rows or not (marks or lanes):
        return
    yellow = NES_PALETTE[LETTER_COLOUR]
    white = NES_PALETTE[KEY_TEXT_COLOUR]
    black = NES_PALETTE[SHADOW_COLOUR]
    band = crop.size[1] * TILE_PX

    # The key is the map's own width, and a map is as narrow as its content --
    # sky5F on a No-Overworld cartridge is sixteen tiles across, four pixels
    # short of the longest lane row at full scale. Rather than trim the wording
    # to whatever fits today, measure and halve the scale where it does not:
    # a small key still reads, and a clipped one silently loses its last word.
    labels = [t for _, t in lanes] + [f"Trap Tile {m}" for m in marks]
    scale = LETTER_SCALE
    while scale > 1 and any(KEY_TEXT_X + font.text_px(t, scale) > w
                            for t in labels):
        scale -= 1

    font.draw_text(out, w, h, KEY_PAD, band + KEY_PAD, "Map Key", white,
                   scale, rom, black)
    row = 0
    for colour, text in lanes:
        y = band + (1 + row) * TILE_PX + KEY_PAD
        # A swatch drawn at the width the lane itself is, so the key is a
        # sample of the line rather than a differently-shaped block beside a
        # name. Centred on the glyph rather than on the row, so it lines up
        # with the text however the scale came out.
        _bar(out, w, h, KEY_PAD,
             y + font.GLYPH_PX * scale // 2 - LANE_PX // 2,
             KEY_PAD + KEY_SWATCH, LANE_PX, NES_PALETTE[colour])
        font.draw_text(out, w, h, KEY_TEXT_X, y, text, white, scale, rom, black)
        row += 1
    # Sorted, so the letters read A B C however the tiles happen to lie.
    for mark in sorted(marks):
        y = band + (1 + row) * TILE_PX + KEY_PAD
        font.draw_text(out, w, h, KEY_PAD, y, mark, yellow, scale, rom, black)
        font.draw_text(out, w, h, KEY_TEXT_X, y, f"Trap Tile {mark}", white,
                       scale, rom, black)
        row += 1


def _bar(out, w, h, x0, y0, x1, thick, rgb):
    """A horizontal run `thick` pixels tall, clipped to the image."""
    for y in range(y0, y0 + thick):
        if not 0 <= y < h:
            continue
        for x in range(max(0, x0), min(w, x1)):
            i = (y * w + x) * 3
            out[i], out[i + 1], out[i + 2] = rgb


def draw_lanes(out, w, h, crop, lanes):
    """Draw one map's route lanes onto an already-rendered frame.

    Four passes, in an order the overdraw depends on:

    1. the silver connectors, **first**, so a lane crosses over the top of one.
       A connector is not a route and must not read as one; it is straight,
       orthogonal and goes through walls where the two tiles are in different
       rooms, which is the point -- the claim is "these two are one check", not
       "you can walk between them".
    2. the plain lane, then the key lane *as an extension of it*. Where both
       use the same corridor there is one line, in the colour of the walk you
       can always do; purple appears only on the steps the key actually buys.
       Drawing both in full -- even offset by a pixel -- puts two parallel
       lines down a shared corridor, which reads as "there are two ways through
       here", and that is not what is true.
    3. the arrows, after the lanes so nothing overdraws them. Without one a
       lane says where to walk but not which way round, and on a route that
       doubles back that is most of the information.
    4. the start box, last, because it is the one thing that must be findable.
    """
    def cell(c, r):
        """Tile to top-left pixel, or None where the crop does not hold it."""
        at = crop.place(c, r)
        return None if at is None else (at[0] * TILE_PX, at[1] * TILE_PX)

    def dot(x, y, rgb):
        if 0 <= x < w and 0 <= y < h:
            i = (y * w + x) * 3
            out[i], out[i + 1], out[i + 2] = rgb

    silver = NES_PALETTE[LANE_LINK]
    for a, b in lanes.links:
        pa, pb = cell(*a), cell(*b)
        if pa is None or pb is None:
            continue
        x1, y1 = pa[0] + TILE_PX // 2, pa[1] + TILE_PX // 2
        x2, y2 = pb[0] + TILE_PX // 2, pb[1] + TILE_PX // 2
        for x in range(min(x1, x2), max(x1, x2) + 1):
            dot(x, y1, silver)
        for y in range(min(y1, y2), max(y1, y2) + 1):
            dot(x2, y, silver)

    def steps(run, shared):
        """The pairs this run draws: for a key lane, only what it adds."""
        return [(a, b) for a, b in zip(run.path, run.path[1:])
                if a != b and not (run.label == "key"
                                   and frozenset((a, b)) in shared)]

    shared = set()
    drawn = []
    for run in lanes.runs:
        if run.label == "plain":
            shared = {frozenset((a, b))
                      for a, b in zip(run.path, run.path[1:]) if a != b}
        base = NES_PALETTE[LANE_KEY if run.label == "key" else LANE_PLAIN]
        forced = NES_PALETTE[LANE_FORCED]
        mine = steps(run, shared)
        drawn.append((run, base, mine))
        for a, b in mine:
            pa, pb = cell(*a), cell(*b)
            if pa is None or pb is None:
                continue
            (x1, y1), (x2, y2) = pa, pb
            # A step across the torus join lands a frame apart on the image;
            # there is no line to draw between two tiles that are not adjacent
            # on the page, and drawing one would stripe the whole map.
            if abs(x1 - x2) > TILE_PX or abs(y1 - y2) > TILE_PX:
                continue
            # A trap the lane could not route round is drawn as itself rather
            # than pretended away: three crossings is MarshCaveB3's floor, not
            # a failure, and a player wants to see the fight coming.
            col = forced if (a in run.traps or b in run.traps) else base
            half = LANE_PX // 2
            for k in range(TILE_PX + 1):
                x = x1 + (x2 - x1) * k // TILE_PX + TILE_PX // 2
                y = y1 + (y2 - y1) * k // TILE_PX + TILE_PX // 2
                # The spread goes on the axis the step does *not* travel on --
                # the same rule _arrow states below. Putting it on the axis of
                # travel draws a line one pixel thick with a LANE_PX//2 overhang
                # past each end, which is not what the key's swatch advertises.
                for o in range(-half, half + 1):
                    dot(x + (o if x1 == x2 else 0),
                        y + (o if y1 == y2 else 0), col)

    for run, base, mine in drawn:
        for n, (a, b) in enumerate(mine):
            # By index, not by value. Comparing the pair fires on every crossing
            # of that ordered edge, not just the last -- which costs no pixels,
            # since a repeated edge ends at the same tile and _arrow is a pure
            # function of it, so the extra call redraws the same arrowhead. It
            # is still the wrong question to ask, and it stops being free the
            # moment an arrow depends on anything but (a, b).
            if n % ARROW_EVERY == ARROW_EVERY - 1 or n == len(mine) - 1:
                _arrow(dot, cell, a, b, base)

    # The start box, on a black ring. Marsh Cave's floor is light grey and a
    # bare white square on it is invisible -- the same reason the trap letters
    # carry a shadow, and the same fix: one ring outside the box and one in,
    # so it reads on any floor the game draws.
    white = NES_PALETTE[LANE_START]
    black = NES_PALETTE[SHADOW_COLOUR]
    for run in lanes.runs:
        at = cell(*run.start)
        if at is None:
            continue
        for ring, rgb in ((-1, black), (0, white), (1, black)):
            lo, hi = ring, TILE_PX - 1 - ring
            for d in range(lo, hi + 1):
                dot(at[0] + d, at[1] + lo, rgb)
                dot(at[0] + d, at[1] + hi, rgb)
                dot(at[0] + lo, at[1] + d, rgb)
                dot(at[0] + hi, at[1] + d, rgb)


def _arrow(dot, cell, a, b, rgb):
    """A triangle at `b`, pointing the way the step went.

    Drawn by stepping back along the line and spreading across it. The spread
    goes on the *perpendicular* axis -- putting it on the axis of travel draws
    a smear down the lane that reads as nothing at all.
    """
    pa, pb = cell(*a), cell(*b)
    if pa is None or pb is None:
        return
    (x1, y1), (x2, y2) = pa, pb
    if abs(x1 - x2) > TILE_PX or abs(y1 - y2) > TILE_PX:
        return
    dx, dy = (x2 - x1) // TILE_PX, (y2 - y1) // TILE_PX
    cx, cy = x2 + TILE_PX // 2, y2 + TILE_PX // 2
    for k in range(ARROW_PX):
        for spread in range(-k, k + 1):
            if dx:
                dot(cx - dx * k, cy + spread, rgb)
            else:
                dot(cx + spread, cy - dy * k, rgb)


def render(rom, map_id, inside=False, unroof=False, graph=None, only=None,
           crop=None, legend_rows=0, marks=None, lanes=None):
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

    `crop` is a Crop -- content_crop(tiles) -- and `legend_rows` reserves that
    many tile-heights of backdrop below the map for a Map Key. Both default to
    off, so a plain render is still the whole 64x64 grid at 1024x1024 and
    --check still compares like with like.

    `marks` is trap_marks(rom). Given it, the trap tiles on this map are
    lettered where they stand and the reserved band is filled in with the key,
    which is what the shipped hand-drawn art does -- see earthB1.png, whose
    G, H and I this reproduces on a vanilla cartridge.

    `lanes` is lane.plan(...)'s Lanes for this map: the route to walk to
    collect the floor, drawn on top and keyed in the same band. The router is
    not imported here -- it imports this module for the tile properties -- so
    the caller derives it, the same way it derives `crop` and `marks`.
    """
    tiles = map_tiles(rom, map_id)
    tileset = rom[TILESET_LUT + map_id]
    art = tileset_art(rom, tileset, map_palettes(rom, map_id, inside))
    open_art = tileset_art(rom, tileset, map_palettes(rom, map_id, True)) \
        if unroof and not inside else None
    rooms = hidden_cells(rom, map_id, tiles, art, open_art) if open_art else set()

    crop = crop or WHOLE
    cols, rows_ = crop.size
    w = cols * TILE_PX
    h = (rows_ + legend_rows) * TILE_PX
    out = bytearray(w * h * 3)
    for row in range(rows_):
        for col in range(cols):
            # The frame is walked, and each cell asks the crop which rom tile
            # it draws. On a map that does not cross the join that is the old
            # `row + r0`; on one that does it is the slide as well, and this is
            # the only place in the render that knows the difference.
            src_col, src_row = crop.source(col, row)
            here = open_art if (src_row, src_col) in rooms else art
            block = here[tiles[src_row * MAP_DIM + src_col] & 0x7F]
            for y in range(TILE_PX):
                dst = ((row * TILE_PX + y) * w + col * TILE_PX) * 3
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
        for row in range(rows_, rows_ + legend_rows):
            for col in range(cols):
                for y in range(TILE_PX):
                    dst = ((row * TILE_PX + y) * w + col * TILE_PX) * 3
                    line = block[y]
                    for x in range(TILE_PX):
                        r, g, b = line[x]
                        out[dst] = r
                        out[dst + 1] = g
                        out[dst + 2] = b
                        dst += 3
    cells = map_trap_marks(rom, map_id, tiles, marks) if marks else {}
    if graph is not None:
        # Imported here, not at module scope: sprites imports this module for
        # the NES palette and the tile decode.
        import sprites                                              # noqa: E402
        sprites.draw_objects(rom, graph, map_id, w, h, out, only, crop)
    # After the sprites, deliberately: a lane runs past an NPC often enough
    # that whichever goes second wins the pixels, and the lane is the thing the
    # image is for. The sprite is still legible either side of the line.
    if lanes is not None:
        draw_lanes(out, w, h, crop, lanes)
    # The trap letters go on last of all. A lane is long and a letter is one
    # tile, so whichever draws second wins and only one of the two can spare
    # the pixels: a stripe through a glyph costs the letter its meaning, while
    # a one-tile gap in a line the eye follows for a hundred tiles costs
    # nothing. The letter is also the caveat on the route, and a caveat under
    # the thing it qualifies is not a caveat.
    if cells:
        # Imported here for the same reason as sprites above: font reads this
        # module's tile decode, so a module-scope import would be a cycle.
        import font                                                 # noqa: E402
        draw_trap_marks(rom, font, out, w, h, crop, cells)
    if legend_rows:
        import font                                                 # noqa: E402
        draw_map_key(rom, font, out, w, h, crop, legend_rows,
                     set(cells.values()), lane_key_entries(lanes))
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
    for name, places in extract_npcs.extract(rom).items():
        for q in places:
            npcs.setdefault(q["map_id"], []).append(
                (f"npc {name}", q["tile_col"], q["tile_row"]))

    bad = kept = 0
    parked = []
    for map_id in range(MAP_COUNT):
        tiles = map_tiles(rom, map_id)
        crop = content_crop(tiles, keep=[
            cell for _, cell in protected_cells(
                rom, map_id, tiles, graph, npcs.get(map_id, ()))])
        kept += crop.size[0] * crop.size[1]
        for what, cell in crop_violations(rom, map_id, tiles, crop, graph,
                                          npcs.get(map_id, ())):
            print(f"  CUT OFF map {map_id} ({MAP_FILES[map_id]}): {what} at {cell}")
            bad += 1
        parked += [(MAP_FILES[map_id], oid, cell)
                   for oid, cell in cropped_objects(map_id, crop, graph)]

    print(f"crop keeps a mean {kept / MAP_COUNT / (MAP_DIM * MAP_DIM) * 100:.0f}% "
          f"of the grid across {MAP_COUNT} maps")
    for name, oid, cell in parked:
        print(f"  note: {name} object {oid} at {cell} is outside its box "
              "(parked out of bounds; marshB1's spare bat is the known one)")
    marks = trap_marks(rom)
    used = sum(1 for m in range(MAP_COUNT)
               if map_trap_marks(rom, m, map_tiles(rom, m), marks))
    fixed = fixed_formations(rom)
    print(f"{len(fixed)} fixed-formation trap tiles, {len(marks)} of them marked "
          f"across {len(standing_formations(rom, fixed))} standing formations, "
          f"used on {used} maps; "
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
    if args.objects or args.crop:
        import entrance_graph                                       # noqa: E402
        graph = entrance_graph.Graph(entrance_graph.Rom.of(rom, args.rom))

    # --crop has to frame the map the way regen_maps.crops() and self_check()
    # do, which means passing the same `keep`: a chest or exit standing in a
    # small component is content, and without this the CLI would drop it and
    # draw a tighter box than the art the pack actually ships. It costs the
    # graph, so --crop now builds one whether or not --objects asked for it.
    cli_npcs = {}
    if args.crop:
        for nm, places in extract_npcs.extract(rom).items():
            for q in places:
                cli_npcs.setdefault(q["map_id"], []).append(
                    (f"npc {nm}", q["tile_col"], q["tile_row"]))

    marks = trap_marks(rom) if args.crop else None
    ids = [args.map] if args.map is not None else range(MAP_COUNT)
    for map_id in ids:
        name = MAP_FILES[map_id]
        crop = None
        rows = None
        if args.crop:
            tiles = map_tiles(rom, map_id)
            crop = content_crop(tiles, keep=[
                cell for _, cell in protected_cells(
                    rom, map_id, tiles, graph, cli_npcs.get(map_id, ()))])
            rows = legend_rows_for(
                len(set(map_trap_marks(rom, map_id, tiles, marks).values())))
        w, h, rgb = render(rom, map_id, args.inside, args.unroof, graph,
                           crop=crop, legend_rows=rows or 0, marks=marks)
        path = os.path.join(args.out, name + ".png")
        pngio.write_rgb(path, w, h, rgb)
        where = (f"tile (c,r) is pixel {TILE_PX}((c+{crop.shift[0]}) mod {MAP_DIM} "
                 f"- {crop.box[0]}), {TILE_PX}((r+{crop.shift[1]}) mod {MAP_DIM} "
                 f"- {crop.box[2]})"
                 if crop else f"tile n is pixel {TILE_PX}n")
        print(f"wrote {path}  ({w}x{h}, {where})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
