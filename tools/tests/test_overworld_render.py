#!/usr/bin/env python3
"""The overworld render, checked against tables it does not read.

Drawing cannot be checked by drawing. What can be checked is that the picture
and the cartridge's own answers about the same map agree, and every check here
is one of those:

  * a tile the ship may enter and the party may not is ocean, and has to come
    out blue; one the party walks on cannot. The properties are read from
    `lut_OWTileset` and the colours from the TSA tables, the CHR bank and the
    palette block -- four separate reads, and a wrong base for any of them
    breaks the correspondence long before it looks wrong to a person.
  * the doors the tile properties name have to be the doors the teleport
    tables name. `entrance_graph.door_positions` reads property byte 1 in bank
    $00; `entrance_graph.Graph.starts` reads lut_EntrTele_Map in bank $0F.
    Neither reading knows about the other.
  * FF1Lib's own tile constants say what tile $17 and $21 are for. A render
    that draws OCEAN green passes every structural check and is still wrong.

Set FF1_ROM to a cartridge; without one this skips rather than passing quietly.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)

import entrance_graph  # noqa: E402
import overworld_reach  # noqa: E402
import render_overworld as ro  # noqa: E402

fail = 0


def check(label, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'ok  ' if ok else 'FAIL'} {label:<52} {got}")
    if not ok:
        print(f"     wanted {want}")


# FF1Lib/procgen/OverworldTiles.cs. Only the ones whose colour is not a
# judgement call: a family, not an exact value, because FFR is free to
# repaint the tileset and these still have to hold.
NAMED = {
    0x00: ("LAND", "green"),
    0x14: ("FOREST", "green"),
    0x17: ("OCEAN", "blue"),
    0x21: ("MOUNTAIN", "grey"),
    0x44: ("RIVER", "blue"),
    0x45: ("DESERT", "warm"),
}


def family(rgb):
    r, g, b = rgb
    if b > r + 24 and b > g + 24:
        return "blue"
    if g > r + 24 and g > b + 24:
        return "green"
    if r > b + 24 and g > b + 24:
        return "warm"
    if abs(r - g) <= 24 and abs(g - b) <= 24:
        return "grey"
    return "other"


def mean(block):
    n = ro.TILE_PX * ro.TILE_PX
    acc = [0, 0, 0]
    for line in block:
        for x in range(ro.TILE_PX):
            for c in range(3):
                acc[c] += line[x * 3 + c]
    return tuple(v // n for v in acc)


def main():
    path = os.environ.get("FF1_ROM")
    if not path or not os.path.exists(path):
        print("SKIP  set FF1_ROM to a Final Fantasy cartridge to run this")
        return 0
    rom = open(path, "rb").read()

    print("-- the image")
    w, h, rgb = ro.render(rom)
    check("width", w, ro.OW_DIM * ro.TILE_PX)
    check("height", h, ro.OW_DIM * ro.TILE_PX)
    check("bytes", len(rgb), w * h * 3)

    art = ro.tileset_art(rom)
    check("one block per tile id", len(art), ro.OW_TILES)

    print("\n-- the tiles FF1Lib names")
    for tile, (name, want) in sorted(NAMED.items()):
        check(f"${tile:02X} {name} is {want}", family(mean(art[tile])), want)

    print("\n-- the art against the movement properties")
    rows = overworld_reach.decompress_ow(rom)
    prop = ro.props(rom)
    used = sorted({t for row in rows for t in row})
    sea = [t for t in used if prop[t * 2] & ro.FOOT and not prop[t * 2] & ro.SHIP]
    land = [t for t in used if not prop[t * 2] & ro.FOOT]
    check("the map uses tiles", len(used) > 32, True)
    check("some are ship-only", len(sea) > 0, True)
    check("some are walkable", len(land) > 0, True)
    check("every ship-only tile is blue",
          [f"${t:02X}" for t in sea if family(mean(art[t])) != "blue"], [])
    check("no walkable tile is",
          [f"${t:02X}" for t in land if family(mean(art[t])) == "blue"], [])

    print("\n-- the doors, against the teleport tables in another bank")
    reader = entrance_graph.Rom(path)
    doors = entrance_graph.door_positions(reader)
    graph = entrance_graph.Graph(reader)
    named = {door for door, _, _ in graph.starts()}
    check("the tile properties name doors", len(doors) > 0, True)
    # A door the teleport table admits but no tile carries is exactly what
    # Graph.starts filters out, so the tiles are the subset and not the reverse.
    check("every tile door is a real door", sorted(set(doors) - named), [])
    check("and each stands on at least one tile",
          [d for d, cells in doors.items() if not cells], [])

    print("\n-- the caravan")
    car = ro.caravan(rom)
    mode = "nov" if not car else "std"
    check("a standard cartridge has exactly one, a No-Overworld one none",
          len(car) in (0, 1), True)
    if car:
        x, y = car[0]
        check("  it is on the map", 0 <= x < 256 and 0 <= y < 256, True)
        check("  and the tile it names carries the caravan special",
              prop[rows[y][x] * 2] & ro.OWTP_SPEC_MASK, ro.OWTP_SPEC_CARAVAN)
    print(f"     ({mode} cartridge)")

    print("")
    if fail:
        print(f"{fail} FAILED")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
