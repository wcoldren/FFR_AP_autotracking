#!/usr/bin/env python3
"""Draw a seed's overworld out of the cartridge, using the game's own tile art.

The pack ships DarkmoonEX's hand-drawn overworld, and both the Overworld tab and
the Incentive sheet point at it (`maps/maps.json`). It is a vanilla map. Every
flag that edits the overworld -- the drydock, the northern docks, Sarda's
forest, the Gaia pass, the Lefein bridge and river, the highway to Ordeals, the
Melmond river, Cardia's land bridge -- moves tiles the drawing does not have,
and an `OwMapExchange` seed replaces the continents outright. `render_maps.py`
answered the same problem for the 61 dungeon maps; this is the overworld half.

The overworld draw path is the standard-map one with the per-map parts taken
out: one tileset, one palette set, one pattern table, no tileset assignment and
no inside/outside variant. Four reads and it is all here:

  Constants.inc:89    BANK_OWMAP  = $01, lut_OWPtrTbl = $8000 -- 256 row
                      pointers, each row RLE'd (decompress_ow, in
                      overworld_reach.py, which is where the format is written
                      down)
  Constants.inc:92    BANK_OWINFO = $00, lut_OWTileset = $8000 -- $400 bytes
  bank_0F.asm:645     LoadOWTilesetData copies that block whole into RAM, so
                      variables.inc:279-285 is also the ROM layout:
                        +$000  tileset_prop  128 tiles x 2
                        +$100  tsa_ul        128    the four CHR indices that
                        +$180  tsa_ur        128    make up one 16x16 tile
                        +$200  tsa_dl        128
                        +$280  tsa_dr        128
                        +$300  tsa_attr      128    & 3 picks the palette
                        +$380  load_map_pal  $30    four 4-byte BG palettes
  bank_0F.asm:9750    LoadOWBGCHR: BANK_MAPCHR = $02, source $8000, "16 rows"
                      at 256 bytes a row -- $1000 bytes, the full 256-pattern
                      table
  bank_0F.asm:4325    the draw loop: tile id t is drawn as tsa_ul/ur/dl/dr[t]
                      under palette tsa_attr[t]. No 16x8 sheet, no indirection.

Sprites.cs:218's PPU decode and Sprites.cs:23's 64-colour table are
render_maps.py's, imported rather than transcribed: transcribing that table by
hand went wrong twice, and the checksum guarding it lives there.

**The tile ids come from the seed, the art does not.** FFR rewrites the
overworld tilemap and leaves the tileset and its CHR alone -- which is why one
tileset can draw every seed, `OwMapExchange` included. If that ever stops being
true the render says so loudly rather than subtly: a wrong CHR bank is noise,
not a map.

**No cropping and no wrap handling, deliberately.** The overworld is a 256x256
torus in the engine, but a drawing of it is a flat field: 256 tiles at 16 pixels
is 4096x4096, tile (col, row) is pixel (16col, 16row) exactly, and that is what
makes every marker on it a derivation rather than a hand-solved offset. The
wrap only matters to something walking the map, which is overworld_reach.py's
job.

    tools/render_overworld.py FFR_seed.nes -o overworld.png
    tools/render_overworld.py FFR_seed.nes --scale 4      # 1024x1024 to look at
    tools/render_overworld.py FFR_seed.nes --audit        # tiles vs properties
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import overworld_reach  # noqa: E402
import pngio  # noqa: E402
from render_maps import NES_PALETTE, decode_ppu  # noqa: E402

INES_HEADER = 0x10
BANK_SIZE = 0x4000
TILE_PX = 16
OW_DIM = 256
OW_TILES = 128

# bank $00 at $8000 is file offset $10; the $400 block's parts follow
# variables.inc:279-285.
OW_INFO = INES_HEADER
OW_PROP = OW_INFO + 0x000
OW_TSA = (OW_INFO + 0x100, OW_INFO + 0x180, OW_INFO + 0x200, OW_INFO + 0x280)
OW_ATTR = OW_INFO + 0x300
OW_PAL = OW_INFO + 0x380

# bank $02 at $8000, the full background pattern table.
OW_CHR = INES_HEADER + 2 * BANK_SIZE
OW_CHR_LEN = 0x1000

# The vehicle bits, for --audit. overworld_reach.py has the reasoning.
FOOT, CANOE, SHIP = 0x01, 0x02, 0x04

# Byte 0's top two bits: the chime/caravan/floater specials. The caravan is read
# from here rather than from a tile id, because a tile id is FFR's to move and
# the property is the game's own test (bank_0F.asm:1164).
#
# The *doors* are the other half of the same table -- byte 1, bit 7 -- and are
# entrance_graph.door_positions', which was here first and gets the mask right:
# the game clears bit 6 as well (bank_0F.asm:396, `AND #$3F`), because bit 6 is
# the battle bit and not part of the id.
OWTP_SPEC_MASK = 0xC0
OWTP_SPEC_CARAVAN = 0x80


def palettes(rom):
    """The four background palettes, as NES colour indices."""
    return [rom[OW_PAL + n * 4:OW_PAL + n * 4 + 4] for n in range(4)]


def props(rom):
    """The tile property table: two bytes per tile id."""
    return rom[OW_PROP:OW_PROP + OW_TILES * 2]


def cells_where(rom, want):
    """{tile id -> [(x, y)]} for every tile id `want(prop0, prop1)` accepts.

    Positions come from the seed's own map, so a flag that moves a cave moves
    its pin, and a No-Overworld cartridge -- which has no caravan and no
    overworld entrances at all -- reports none rather than the vanilla ones.
    """
    p = props(rom)
    ids = {t for t in range(OW_TILES) if want(p[t * 2], p[t * 2 + 1])}
    out = {}
    if not ids:
        return out
    for y, row in enumerate(overworld_reach.decompress_ow(rom)):
        for x, t in enumerate(row):
            if t in ids:
                out.setdefault(t, []).append((x, y))
    return out


def caravan(rom):
    """[(x, y)] for the caravan, which is one tile on a standard cartridge.

    Worth having a name for. It is the only thing on the overworld that is a
    shop rather than a place -- stepping on it opens shop 70 without a map
    change (bank_0F.asm:1167-1176) -- so it is the tile the pack's `I: Shop
    Item` pin stands on, and the one annotation the shipped hand-drawn
    overworld carries. A player with no annotation has no way to know the check
    is there.
    """
    cells = cells_where(
        rom, lambda p0, p1: p0 & OWTP_SPEC_MASK == OWTP_SPEC_CARAVAN)
    return sorted(c for cs in cells.values() for c in cs)


def tileset_art(rom):
    """tile id -> 16 rows of 48 bytes, one 16x16 block ready to paste."""
    pal = palettes(rom)
    attr = rom[OW_ATTR:OW_ATTR + OW_TILES]
    quads = [rom[base:base + OW_TILES] for base in OW_TSA]
    blocks = []
    for t in range(OW_TILES):
        colours = pal[attr[t] & 3]
        block = [bytearray(TILE_PX * 3) for _ in range(TILE_PX)]
        for n, (ox, oy) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
            off = OW_CHR + quads[n][t] * 16
            px = decode_ppu(rom[off:off + 16])
            for i, v in enumerate(px):
                x, y = ox + (i & 7), oy + (i >> 3)
                block[y][x * 3:x * 3 + 3] = bytes(NES_PALETTE[colours[v]])
        blocks.append([bytes(row) for row in block])
    return blocks


def render(rom, scale=1, box=None):
    """(width, height, rgb) for the seed's overworld.

    `box` is (x0, y0, w, h) in tiles, or None for all 256x256. Cropping is what
    makes a No-Overworld map readable: its nine stub doors sit within fourteen
    tiles of each other on a field of 65536, so the whole map is a picture of
    nothing you can do. It is not a torus crop -- a box is clamped to the map
    rather than wrapped, because a cluster that straddles the seam is a case
    nothing has produced and guessing at it would be untested code.
    """
    rows = overworld_reach.decompress_ow(rom)
    art = tileset_art(rom)
    px = TILE_PX
    x0, y0, tw, th = box or (0, 0, OW_DIM, OW_DIM)
    out = bytearray()
    for row in rows[y0:y0 + th]:
        blocks = [art[t] for t in row[x0:x0 + tw]]
        for y in range(px):
            out += b"".join(block[y] for block in blocks)
    w, h = tw * px, th * px
    if scale > 1:
        out, w, h = downscale(out, w, h, scale)
    return w, h, out


def downscale(rgb, w, h, n):
    """Box-filter by an integer factor, for a copy small enough to look at."""
    ow, oh = w // n, h // n
    out = bytearray(ow * oh * 3)
    area = n * n
    for oy in range(oh):
        for ox in range(ow):
            r = g = b = 0
            for dy in range(n):
                base = ((oy * n + dy) * w + ox * n) * 3
                for dx in range(n):
                    r += rgb[base + dx * 3]
                    g += rgb[base + dx * 3 + 1]
                    b += rgb[base + dx * 3 + 2]
            i = (oy * ow + ox) * 3
            out[i], out[i + 1], out[i + 2] = r // area, g // area, b // area
    return out, ow, oh


def audit(rom):
    """Every tile the map uses, its movement properties and its drawn colour.

    The point is that the art and the property table are read from different
    places and have to agree. A tile the party cannot walk on and the ship can
    is ocean and has to be drawn blue; one that takes the party on foot is land
    and cannot be. A wrong palette base or CHR bank breaks that correspondence
    long before it looks wrong to a person.
    """
    rows = overworld_reach.decompress_ow(rom)
    art = tileset_art(rom)
    prop = rom[OW_PROP:OW_PROP + OW_TILES * 2]
    used = sorted({t for row in rows for t in row})

    def mean(block):
        n = TILE_PX * TILE_PX
        acc = [0, 0, 0]
        for line in block:
            for x in range(TILE_PX):
                for c in range(3):
                    acc[c] += line[x * 3 + c]
        return tuple(v // n for v in acc)

    sea = land = 0
    seablue = landblue = 0
    print(f"{len(used)} of {OW_TILES} tile ids used by this map")
    for t in used:
        p = prop[t * 2]
        rgb = mean(art[t])
        walk = "-" if p & FOOT else "foot"
        ship = "ship" if not p & SHIP else "-"
        blue = rgb[2] > rgb[0] + 24 and rgb[2] > rgb[1] + 24
        if (p & FOOT) and not (p & SHIP):
            sea += 1
            seablue += blue
        elif not p & FOOT:
            land += 1
            landblue += blue
        print(f"  ${t:02X}  prop ${p:02X}  {walk:<4} {ship:<4} "
              f"rgb {rgb[0]:3d},{rgb[1]:3d},{rgb[2]:3d}  {'blue' if blue else ''}")
    print(f"\n  {seablue}/{sea} ship-only tiles are blue, "
          f"{landblue}/{land} walkable tiles are")
    return seablue == sea and landblue == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("rom")
    ap.add_argument("-o", "--out", help="PNG to write (default: <rom>_ow.png)")
    ap.add_argument("--scale", type=int, default=1,
                    help="box-filter down by this integer factor")
    ap.add_argument("--audit", action="store_true",
                    help="check the drawn tiles against the property table")
    ap.add_argument("--places", action="store_true",
                    help="the overworld doors and the caravan, in tile coordinates")
    args = ap.parse_args()

    rom = open(args.rom, "rb").read()
    if args.audit:
        ok = audit(rom)
        sys.exit(0 if ok else 1)
    if args.places:
        import entrance_graph
        doors = entrance_graph.door_positions(entrance_graph.Rom.of(rom, args.rom))
        print(f"{len(doors)} overworld doors")
        for eid in sorted(doors):
            cells = doors[eid]
            print(f"  entrance {eid:2d}  {len(cells)} tile(s)  {cells[0]}"
                  + (f" .. {cells[-1]}" if len(cells) > 1 else ""))
        car = caravan(rom)
        print(f"caravan: {car if car else 'none on this cartridge'}")
        return

    w, h, rgb = render(rom, args.scale)
    out = args.out or os.path.splitext(args.rom)[0] + "_ow.png"
    pngio.write_rgb(out, w, h, rgb)
    print(f"{out}: {w}x{h}")


if __name__ == "__main__":
    main()
