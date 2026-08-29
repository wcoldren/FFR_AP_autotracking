#!/usr/bin/env python3
"""Draw the map objects -- townspeople, orbs, the gate NPCs -- from a cartridge.

Which sprite an object wears is a byte per object at lut_MapObjGfx; the art is
$100 bytes per sprite at lut_MapObjCHR. Both come from the routine that puts
one on screen, LoadMapObjCHR (bank_0F.asm:$E99E), rather than from anything
found by eye:

    LDA (tmp+4), Y       ; object ID for this slot of the map's object list
    TAX
    LDA lut_MapObjGfx, X ; -> the graphic ID
    CLC
    ADC #>lut_MapObjCHR  ; added to the HIGH byte, so the graphic ID is a page
    ...                  ;   index: source = lut_MapObjCHR + gfx_id * $100
    LDY #0
  @CHRLoop:
      LDA (tmp), Y       ; 256 bytes -- 16 tiles -- into CHR RAM, per object
      STA $2007
      INY
      BNE @CHRLoop

Constants.inc puts lut_MapObjGfx at $AE00 in bank $00 and lut_MapObjCHR at
$A200 in bank $02. The second is what was missing: the art was located by eye
at roughly the right place and never aligned, so sprite 4 did not draw as the
Orb it has to be. It does now, and the origin is not a guess -- bank $02 turns
out to be fully accounted for, with no gap anywhere for the base to slide into:

    $8000  LoadOWBGCHR          16 pages, the overworld's background tiles
    $9000  LoadPlayerMapmanCHR  12 pages, $9x00 where x is the lead's class
    $9C00  LoadOWObjectCHR       6 pages, ship / canoe / airship / bridge/canal
    $A200  lut_MapObjCHR        30 pages, one per ObjectSprites entry, ending
                                at $C000 exactly -- where the background
                                tileset CHR starts (render_maps.CHR_BASE)

Inside one sprite's 16 tiles, DrawMapObject's four construction tables
(bank_0F.asm:$E7AB) spend them as four 2x2 poses, each row-major:

    lut_2x2MapObj_Down:  $00,$02,$02,$03,$01,$02,$03,$03   tiles 0-3
    lut_2x2MapObj_Up:    $04,$02,$06,$03,$05,$02,$07,$03   tiles 4-7
    lut_2x2MapObj_Left:  $08,$02,$0A,$03,$09,$02,$0B,$03   tiles 8-11
                         (walking frame)                   tiles 12-15

Draw2x2Sprite reads those as (tile, attribute) in UL, DL, UR, DR order, so the
tiles themselves are UL, UR, DL, DR -- row-major, which is the reading that
comes out unscrambled. Facing right is facing left with every tile flipped
(lut_2x2MapObj_Right is the same tiles with attribute bit $40 set), so there is
no right-facing art to find.

The attribute bytes are the other half of the answer. $02 on the top row and
$03 on the bottom: sprite palettes 2 and 3, and colour 0 of a sprite palette is
transparent. The map's own $30-byte palette block is four BG palettes, then
four sprite palettes at +$10, then the four "inside" BG palettes at +$20 that
render_maps already reads. That the middle $10 bytes are the sprite palettes is
checkable and checked: LoadMapPalettes (bank_0F.asm:$D8AB) copies all $30 to
cur_pal and then overwrites cur_pal+$12 and cur_pal+$16 with the lead
character's mapman colours, and those two bytes -- sprite palettes 0 and 1,
which are the player -- are the only ones in the block that are identical on
all 61 maps, because the engine always replaces them. Palettes 2 and 3 vary map
by map, and are blank on exactly the maps with no objects on them.

Usage:
    tools/sprites.py ROM --sheet /tmp/sprites.png    # all 30, named
    tools/sprites.py ROM --map 8                     # what stands on a map
    tools/sprites.py ROM --gates                     # just the gate NPCs
    tools/sprites.py ROM --self-check                # the invariants above
"""

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import entrance_graph as eg                                     # noqa: E402
import pngio                                                    # noqa: E402
from render_maps import (                                       # noqa: E402
    CHR_BASE, MAP_COUNT, MAP_FILES, NES_PALETTE, PALETTE_BASE, PALETTE_STRIDE,
    TILE_PX, decode_ppu,
)

GFX_TABLE = eg.bank_off(0x00, 0xAE00)     # lut_MapObjGfx, BANK_OBJINFO
CHR_BANK = 0x02                           # BANK_MAPCHR
MAPOBJ_CHR = 0xA200                       # lut_MapObjCHR
MAPMAN_CHR = 0x9000                       # LoadPlayerMapmanCHR, $9x00 per class
OW_OBJECT_PAGES = 6                       # LoadOWObjectCHR, $9C00, 6 rows
BANK_WINDOW = (0x8000, 0xC000)            # what a swapped-in PRG bank covers
SPRITE_BYTES = 0x100                      # 16 tiles, one page, per sprite
OBJ_COUNT = 0xD0                          # 208 objects, NPCs.cs npcObjectQty
PALETTE_SPRITE = 0x10                     # sprite palettes, +$10 into the block
PALETTE_OBJECT = (2, 3)                   # the two an object draws with
SPRITE_PX = 16                            # a map object is 2x2 tiles

# FF1Lib/NPCs.cs:13, in order. The enum is the cartridge's own numbering: the
# byte at GFX_TABLE + object_id indexes straight into it.
SPRITE_NAMES = (
    "Princess", "Woman", "OldWoman", "Dancer", "Orb", "Witch", "Prince",
    "Soldier", "Scholar", "Mohawk", "Boy", "OldMan", "Dwarf", "Mermaid",
    "Lefein", "King", "Broom", "Bat", "Garland", "Pirate", "Fairy", "Robot",
    "Dragon", "Bahamut", "ElfWoman", "ElfMan", "ElfPrince", "Plate", "Titan",
    "Vampire",
)

# FF1Lib/FF1Class.cs, the order LoadPlayerMapmanCHR indexes $9x00 by.
CLASS_NAMES = (
    "Fighter", "Thief", "BlackBelt", "RedMage", "WhiteMage", "BlackMage",
    "Knight", "Ninja", "Master", "RedWiz", "WhiteWiz", "BlackWiz",
)

# What actually pins the base is arithmetic, not a picture: bank $02 has no gap
# and no overlap. Three engine constants that know nothing about each other --
# twelve mapman pages from $9000, six overworld-object pages from $9C00, and
# thirty ObjectSprites pages ending where render_maps reads the background
# tileset CHR -- meet exactly at $A200 and exactly at $C000. Slide the base by
# a page in either direction and one of these fails, which is the guard the
# eyeballed origin never had. Keep them as asserts: they are the reason the
# number is right, and --self-check restates them for the reader.
assert MAPMAN_CHR + (len(CLASS_NAMES) + OW_OBJECT_PAGES) * SPRITE_BYTES == MAPOBJ_CHR
assert MAPOBJ_CHR + len(SPRITE_NAMES) * SPRITE_BYTES == BANK_WINDOW[1]
assert eg.bank_off(CHR_BANK, MAPOBJ_CHR) + len(SPRITE_NAMES) * SPRITE_BYTES == CHR_BASE

# Tile indices within a sprite's 16, as (UL, UR, DL, DR). "right" is "left"
# mirrored, which is how the cartridge draws it too.
POSES = {
    "down": (0, 1, 2, 3),
    "up": (4, 5, 6, 7),
    "left": (8, 9, 10, 11),
    "walk": (12, 13, 14, 15),
}
QUADRANTS = ((0, 0), (8, 0), (0, 8), (8, 8))   # matching POSES' UL, UR, DL, DR


def chr_page(gfx_id):
    """The CPU address the engine's own arithmetic reaches for a graphic id.

    The add lands on the *high* byte and the carry out is dropped, so the
    graphic id is a page index that wraps. That is not an accident FFR works
    around, it is a door FFR walks through: MIAB.cs:451 gives Chaos graphic
    $F4, and $A2 + $F4 = $196 -> $96, which is $9600 -- the Knight's mapman.
    Party.cs:581 does the same thing twelve times over, giving a recruited
    class NPC graphics $EE-$F9, exactly the twelve mapman pages $9000-$9B00.
    So a graphic id above the 30-entry enum is not corrupt data; it is a
    deliberate reach into the other art in the same bank.
    """
    return ((((MAPOBJ_CHR >> 8) + gfx_id) & 0xFF) << 8)


def sprite_ids(rom):
    """object id -> graphic id, for all 208 objects (lut_MapObjGfx)."""
    return list(rom[GFX_TABLE:GFX_TABLE + OBJ_COUNT])


def sprite_name(gfx_id):
    """The enum name, the class whose mapman it is, or the bare page."""
    if gfx_id < len(SPRITE_NAMES):
        return SPRITE_NAMES[gfx_id]
    page = chr_page(gfx_id)
    if MAPMAN_CHR <= page < MAPMAN_CHR + len(CLASS_NAMES) * SPRITE_BYTES:
        return CLASS_NAMES[(page - MAPMAN_CHR) >> 8] + "Mapman"
    return f"#{gfx_id:02X}@${page:04X}"


def sprite_palettes(rom, map_id):
    """The map's four 4-colour sprite palettes, as NES colour indices."""
    base = PALETTE_BASE + map_id * PALETTE_STRIDE + PALETTE_SPRITE
    return [rom[base + n * 4:base + n * 4 + 4] for n in range(4)]


def sprite_pixels(rom, gfx_id, pose="down", flip=False):
    """16x16 colour indices 0-3 for one pose, with 0 meaning transparent.

    Returned per index rather than resolved to colour, because which palette a
    pixel uses depends on which half of the sprite it is in and the colours
    depend on the map. `flip` mirrors, which is how the game faces an object
    right. None when the graphic id reaches outside the swapped-in bank, where
    there is no art to read and a plausible-looking block of bytes would be a
    lie.
    """
    page = chr_page(gfx_id)
    if not BANK_WINDOW[0] <= page < BANK_WINDOW[1]:
        return None
    base = eg.bank_off(CHR_BANK, page)
    px = [[0] * SPRITE_PX for _ in range(SPRITE_PX)]
    for tile, (ox, oy) in zip(POSES[pose], QUADRANTS):
        off = base + tile * 16
        for i, v in enumerate(decode_ppu(rom[off:off + 16])):
            px[oy + (i >> 3)][ox + (i & 7)] = v
    return [row[::-1] for row in px] if flip else px


def sprite_rgb(rom, gfx_id, map_id, pose="down", flip=False):
    """[[(r, g, b) or None]] -- None where the sprite is transparent."""
    px = sprite_pixels(rom, gfx_id, pose, flip)
    if px is None:
        return None
    pals = sprite_palettes(rom, map_id)
    top, bottom = (pals[n] for n in PALETTE_OBJECT)
    return [[None if v == 0 else NES_PALETTE[(top if y < SPRITE_PX // 2
                                              else bottom)[v]] for v in row]
            for y, row in enumerate(px)]


def paste(out, side, x, y, block):
    """Composite one 16x16 sprite onto an RGB buffer, skipping transparency."""
    for dy, row in enumerate(block):
        py = y + dy
        if not 0 <= py < side:
            continue
        for dx, rgb in enumerate(row):
            px = x + dx
            if rgb is None or not 0 <= px < side:
                continue
            d = (py * side + px) * 3
            out[d], out[d + 1], out[d + 2] = rgb


def draw_objects(rom, graph, map_id, side, out, only=None):
    """Draw the objects standing on a map onto a rendered map buffer.

    Tile (col, row) is pixel (16col, 16row) in render_maps' output, and a map
    object occupies exactly one tile, so the sprite lands on the tile it
    stands on. DrawMapObject nudges it three pixels up on screen for looks; a
    map drawing wants it on its tile, so that is left out.

    `only` restricts to a set of object ids -- the gate NPCs, say, which are
    the ones with no marker of their own to collide with. Returns how many
    were drawn.
    """
    ids = sprite_ids(rom)
    drawn = 0
    for oid, x, y in graph.objects(map_id):
        if only is not None and oid not in only:
            continue
        block = sprite_rgb(rom, ids[oid], map_id)
        if block is None:
            continue
        paste(out, side, x * TILE_PX, y * TILE_PX, block)
        drawn += 1
    return drawn


def contact_sheet(rom, map_id, scale=3):
    """(w, h, rgb) -- the 30 sprites, one per row, four poses across."""
    poses = [("down", False), ("up", False), ("left", False), ("left", True)]
    cell = SPRITE_PX * scale
    w, h = len(poses) * cell, len(SPRITE_NAMES) * cell
    ground = NES_PALETTE[rom[PALETTE_BASE + map_id * PALETTE_STRIDE]]
    out = bytearray(bytes(ground) * (w * h))
    for gfx_id in range(len(SPRITE_NAMES)):
        for n, (pose, flip) in enumerate(poses):
            block = sprite_rgb(rom, gfx_id, map_id, pose, flip)
            for y, row in enumerate(block):
                for x, rgb in enumerate(row):
                    if rgb is None:
                        continue
                    for sy in range(scale):
                        d = ((gfx_id * cell + y * scale + sy) * w
                             + n * cell + x * scale) * 3
                        for _ in range(scale):
                            out[d], out[d + 1], out[d + 2] = rgb
                            d += 3
    return w, h, bytes(out)


def self_check(rom, graph):
    """The invariants these two tables have to satisfy. True when they hold.

    Worth running on any cartridge before believing a drawing, because a wrong
    CHR base fails by producing a sheet of plausible art rather than an error.

    Be clear about the division of labour. The *base* is pinned by the bank
    arithmetic asserted at import, not by anything below -- slide it one page
    and it lands on the tail of the overworld-object art, which is distinct and
    non-blank and would satisfy every check here. What these catch is the other
    half: a misread object-to-graphic table, a misread palette region, and any
    object wearing art that is not in the bank at all.
    """
    bad = []
    ids = sprite_ids(rom)

    # Every object a map actually places has to wear art we can find. An id
    # outside the enum is allowed -- see chr_page -- but it still has to land
    # inside the bank.
    placed = {oid for m in range(MAP_COUNT) for oid, _, _ in graph.objects(m)}
    for oid in sorted(placed):
        if sprite_pixels(rom, ids[oid]) is None:
            bad.append(f"object ${oid:02X} has graphic ${ids[oid]:02X}, which "
                       f"reaches ${chr_page(ids[oid]):04X} -- outside the bank")

    # The 30 named sprites are 30 distinct, non-empty drawings. This does not
    # pin the base -- see the docstring -- but it does catch a bank that never
    # got its art, and a decode that collapses.
    seen = {}
    for gfx_id in range(len(SPRITE_NAMES)):
        art = sprite_pixels(rom, gfx_id)
        if art is None:
            bad.append(f"sprite {gfx_id} ({SPRITE_NAMES[gfx_id]}) reaches "
                       f"${chr_page(gfx_id):04X}, outside the bank")
            continue
        px = tuple(tuple(r) for r in art)
        if not any(any(r) for r in px):
            bad.append(f"sprite {gfx_id} ({SPRITE_NAMES[gfx_id]}) is blank")
        if px in seen:
            bad.append(f"sprite {gfx_id} ({SPRITE_NAMES[gfx_id]}) is identical "
                       f"to {seen[px]} ({SPRITE_NAMES[seen[px]]})")
        seen[px] = gfx_id

    # Sprite palettes 0 and 1 are the player's and the engine overwrites two of
    # their bytes per class, so they are the same on every map; 2 and 3 are the
    # objects' and are not. Reading the block at the wrong offset loses this.
    blocks = [rom[PALETTE_BASE + m * PALETTE_STRIDE + PALETTE_SPRITE:
                  PALETTE_BASE + m * PALETTE_STRIDE + PALETTE_SPRITE + 0x10]
              for m in range(MAP_COUNT)]
    if len({b[:8] for b in blocks}) != 1:
        bad.append("sprite palettes 0-1 differ between maps; they are the "
                   "player's and should not")
    if len({b[8:] for b in blocks}) < 2:
        bad.append("sprite palettes 2-3 are the same on every map; they are "
                   "the objects' and should not be")

    # And the object palettes are blank exactly where there is nothing to draw.
    # Two independent tables agreeing is the check the CHR base cannot fake.
    for m in range(MAP_COUNT):
        if graph.objects(m) and set(blocks[m][8:]) <= {0}:
            bad.append(f"map {m} ({MAP_FILES[m]}) places objects but its "
                       "object palettes are blank")

    for line in bad:
        print(f"  FAIL {line}")
    print(f"self-check: {len(bad)} problems, {len(placed)} placed objects, "
          f"{len(SPRITE_NAMES)} sprites from ${MAPOBJ_CHR:04X} in bank "
          f"${CHR_BANK:02X}")
    return not bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--sheet", metavar="PNG",
                    help="write a contact sheet of all 30 sprites")
    ap.add_argument("--palette-map", type=int, default=0, metavar="ID",
                    help="colour the sheet with this map's sprite palettes")
    ap.add_argument("--scale", type=int, default=3)
    ap.add_argument("--map", type=int, metavar="ID",
                    help="list the objects standing on one standard map")
    ap.add_argument("--gates", action="store_true",
                    help="list the No-Overworld gate NPCs and their sprites")
    ap.add_argument("--self-check", action="store_true",
                    help="check the invariants that pin the sprite tables")
    args = ap.parse_args()

    with open(args.rom, "rb") as f:
        rom = f.read()
    if rom[:4] != b"NES\x1a":
        sys.exit("not an iNES ROM")
    ids = sprite_ids(rom)

    if args.sheet:
        w, h, rgb = contact_sheet(rom, args.palette_map, args.scale)
        pngio.write_rgb(args.sheet, w, h, rgb)
        print(f"wrote {args.sheet}  ({w}x{h}, one sprite per row, top to "
              f"bottom: {', '.join(SPRITE_NAMES)})")

    if args.map is not None:
        if args.map not in MAP_FILES:
            sys.exit(f"no such standard map: {args.map}")
        graph = eg.Graph(eg.Rom.of(rom, args.rom))
        print(f"map {args.map} ({MAP_FILES[args.map]}):")
        for oid, x, y in graph.objects(args.map):
            gate = (graph.gates or {}).get(oid)
            print(f"  object ${oid:02X} at ({x:2d},{y:2d})  "
                  f"{sprite_name(ids[oid])}{f'   gate: {gate}' if gate else ''}")

    if args.gates:
        graph = eg.Graph(eg.Rom.of(rom, args.rom))
        if not graph.gates:
            print("no gate layout on this cartridge")
        else:
            where = {oid: (m, x, y) for m in range(MAP_COUNT)
                     for oid, x, y in graph.objects(m)}
            for oid, item in sorted(graph.gates.items()):
                m, x, y = where.get(oid, (None, 0, 0))
                place = f"{MAP_FILES[m]} ({x},{y})" if m is not None else "unplaced"
                print(f"  object ${oid:02X}  wants {item:8s} "
                      f"{sprite_name(ids[oid]):10s} {place}")

    if args.self_check:
        return 0 if self_check(rom, eg.Graph(eg.Rom.of(rom, args.rom))) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
