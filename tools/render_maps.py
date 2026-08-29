#!/usr/bin/env python3
"""Draw every standard map out of a cartridge, using the game's own tile art.

The pack's dungeon images used to be screenshots: right for a vanilla layout,
approximate about scale, and silent about anything the seed changed. A
No-Overworld seed changes a great deal -- it stamps 75 new staircases across 34
maps and seals every town's outer wall -- so a screenshot of the vanilla castle
shows the right rooms and the wrong exits. Drawing from the cartridge instead
gets the seed's own map, whatever mode it is in.

It also makes calibration disappear -- but only for a pack that has been moved
over wholesale. Every image here is 64 tiles at 16 pixels, so tile (col, row) is
pixel (col * 16, row * 16) exactly, with no offset to eyeball and no map left
uncalibrated. The 51 images the pack ships today are hand-drawn composites at 51
different sizes, each with a hand-solved offset in tools/map_calibration.json
that make_markers.py bakes into the pixel coordinates in locations/*.json.
Dropping these renders on top of those without rewriting map_calibration.json
(every offset zero, one region per map) and re-running make_markers.py moves the
art out from under every dungeon marker. Render somewhere else until that swap
is done as one piece.

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
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from extract_chests import (  # noqa: E402
    INES_HEADER, MAP_COUNT, MAP_DIM, TILESET_LUT,
    decompress_map, map_data_base,
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


def render(rom, map_id, inside=False, unroof=False, graph=None, only=None):
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
    """
    base = map_data_base(rom)
    ptr = int.from_bytes(rom[base + map_id * 2:base + map_id * 2 + 2], "little")
    tiles = decompress_map(rom, base + ptr)
    tileset = rom[TILESET_LUT + map_id]
    art = tileset_art(rom, tileset, map_palettes(rom, map_id, inside))
    open_art = tileset_art(rom, tileset, map_palettes(rom, map_id, True)) \
        if unroof and not inside else None
    rooms = hidden_cells(rom, map_id, tiles, art, open_art) if open_art else set()

    side = MAP_DIM * TILE_PX
    out = bytearray(side * side * 3)
    for row in range(MAP_DIM):
        for col in range(MAP_DIM):
            here = open_art if (row, col) in rooms else art
            block = here[tiles[row * MAP_DIM + col] & 0x7F]
            for y in range(TILE_PX):
                dst = ((row * TILE_PX + y) * side + col * TILE_PX) * 3
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
        sprites.draw_objects(rom, graph, map_id, side, out, only)
    return side, side, bytes(out)


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
    args = ap.parse_args()

    with open(args.rom, "rb") as f:
        rom = f.read()
    if rom[:4] != b"NES\x1a":
        sys.exit("not an iNES ROM")

    if args.check:
        return 0 if check(rom, args.check) else 1

    if not args.out:
        sys.exit("nothing to do: pass -o DIR to write images, or --check DIR")
    os.makedirs(args.out, exist_ok=True)

    if args.map is not None and args.map not in MAP_FILES:
        sys.exit(f"no such standard map: {args.map} (0-{MAP_COUNT - 1})")
    graph = None
    if args.objects:
        import entrance_graph                                       # noqa: E402
        graph = entrance_graph.Graph(entrance_graph.Rom.of(rom, args.rom))

    ids = [args.map] if args.map is not None else range(MAP_COUNT)
    for map_id in ids:
        name = MAP_FILES[map_id]
        w, h, rgb = render(rom, map_id, args.inside, args.unroof, graph)
        path = os.path.join(args.out, name + ".png")
        pngio.write_rgb(path, w, h, rgb)
        print(f"wrote {path}  ({w}x{h}, tile n is pixel {TILE_PX}n)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
