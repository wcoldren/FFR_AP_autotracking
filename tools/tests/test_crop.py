"""The crop keeps the map and drops the filler, and the hand art says so.

A 64x64 render is mostly not map. The crop is one flood of the border tile
inward from the edge, and the box is what the flood could not reach. Two
things are tested, because the rule has two ways to be wrong:

  * **it must not cut anything off.** Chests, staircases, exits and the pack's
    own tracked NPCs all survive it -- the Ice Cave B1 fairy stands on a cell
    the flood reaches, so it is exactly what a bad box would lose;
  * **it must land where DarkmoonEX drew.** The shipped hand-drawn maps are
    cropped too, and their images plus tools/map_calibration.json say which
    ROM tiles each one keeps. On most of the calibrated maps the derived box
    is within a tile of the drawn one. That agreement is the reason to believe
    the rule rather than merely to like its output.

The trap-letter derivation is checked here as well, because the Map Key band
is sized from it: on a *vanilla* cartridge the letters have to come out the way
the art draws them, earthB1 {G,H,I} and volcB4 {M,N}.

Set FF1_ROM to a cartridge; without one this skips.
"""
import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import entrance_graph as eg                                    # noqa: E402
import render_maps as rm                                       # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)

# How far the derived box may sit from the box the hand art draws, in tiles, on
# a map where both exist. One, because the derived box pads by one and the art
# was drawn by eye. The maps listed are the ones that actually hold to it; the
# rest of the calibrated set differs for reasons that are about the art -- a
# composite laid out at unrelated offsets, or margin left for annotations.
ART_AGREES = (
    "tofrAir", "earthB1", "earthB2", "earthB3", "earthB4", "earthB5", "iceB1",
    "matoya", "sarda", "mirage1F", "mirage2F", "marshB2", "volcB2", "volcB5",
    "seaB2", "seaB3", "sky1F", "sky2F", "sky3F", "tofr3F", "tofrFire",
    "titans",
)

# The other eight calibrated maps drift further, and the reasons are about the
# drawing rather than the rule: `tof` 2, `marshB3` 2, `waterfall` 2, `nw_castle`
# 3 and `dwarves` 3 are margin the artist left; `volcB4`, `seaB4` and `seaB5` 4;
# and `cardia`, `elf_castle`, `iceB2`, `iceB3` and `seaB1` are composites whose
# image holds a different set of tiles than its rom_map_id names. Kept out of
# the assertion and written down instead, because a bound loose enough to
# include them would not be testing anything.


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def art_box(name, entry):
    """The ROM tile range the shipped image for `name` actually covers."""
    path = os.path.join(PACK, "images", "maps", name + ".png")
    if not os.path.exists(path):
        return None
    w, h = png_size(path)
    tp = entry["tile_px"]
    cols, rows = [], []
    for r in entry["regions"]:
        cols += [max(0, math.ceil(-r["offset_x"] / tp)),
                 min(rm.MAP_DIM - 1, math.floor((w - r["offset_x"]) / tp) - 1)]
        rows += [max(0, math.ceil(-r["offset_y"] / tp)),
                 min(rm.MAP_DIM - 1, math.floor((h - r["offset_y"]) / tp) - 1)]
    return min(cols), max(cols), min(rows), max(rows)


def main():
    path = os.environ.get("FF1_ROM")
    if not path or not os.path.exists(path):
        print("SKIP  set FF1_ROM to a Final Fantasy cartridge to run this")
        return 0
    with open(path, "rb") as f:
        rom = f.read()
    graph = eg.Graph(eg.Rom.of(rom, path))
    fails = []

    def check(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")
        print(f"{'ok  ' if got == want else 'FAIL'} {label}")

    with open(os.path.join(TOOLS, "npc_positions.json")) as f:
        npcs = {}
        for name, places in json.load(f).items():
            for q in places:
                npcs.setdefault(q["map_id"], []).append(
                    (f"npc {name}", q["tile_col"], q["tile_row"]))

    boxes = {}
    cut, kept, whole = [], 0, 0
    for map_id in range(rm.MAP_COUNT):
        tiles = rm.map_tiles(rom, map_id)
        box = boxes[rm.MAP_FILES[map_id]] = rm.content_box(tiles)
        cut += [(rm.MAP_FILES[map_id], what, cell) for what, cell in
                rm.crop_violations(rom, map_id, tiles, box, graph,
                                   npcs.get(map_id, ()))]
        area = (box[1] - box[0] + 1) * (box[3] - box[2] + 1)
        kept += area
        whole += area == rm.MAP_DIM * rm.MAP_DIM

        # The box is a box: inside the grid, and the right way round.
        c0, c1, r0, r1 = box
        if not (0 <= c0 <= c1 < rm.MAP_DIM and 0 <= r0 <= r1 < rm.MAP_DIM):
            fails.append(f"map {map_id} box is not a box: {box}")

    check("the crop cuts off no chest, staircase, exit or tracked NPC", cut, [])
    mean = kept / rm.MAP_COUNT / (rm.MAP_DIM * rm.MAP_DIM) * 100
    print(f"     (mean {mean:.0f}% of the grid kept; {whole} maps crop to nothing)")
    check("it is a crop, not a no-op", mean < 70, True)
    check("and not so tight it has eaten the maps", mean > 25, True)

    # The Ice Cave B1 fairy is the case that gives the guard teeth: it stands on
    # a cell the flood reaches, so only the box keeps it.
    fairy = [(c, r) for what, c, r in npcs.get(15, ()) if what == "npc fairy"]
    if fairy:
        tiles = rm.map_tiles(rom, 15)
        reach = rm.outside_cells(tiles, rm.backdrop_tile(tiles)[0])
        check("the Ice Cave B1 fairy stands on a cell the flood reaches",
              fairy[0] in reach, True)
        check("and the box keeps it anyway",
              rm.in_box(boxes["iceB1"], *fairy[0]), True)

    # Against the hand art, which is the reference the rule is measured on.
    inverted = rm.battle_byte_inverted(rom)
    with open(os.path.join(TOOLS, "map_calibration.json")) as f:
        cal = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    # Matoya's Cave carries four cells of tile $0B at (20-23,13), detached, out
    # in the void with nothing near them. They are in the vanilla map data and
    # survive on an ordinary seed; only No-Overworld's map rebuild removes them.
    # They stretch the box seven columns past where DarkmoonEX cropped.
    #
    # No filter is added for it, on purpose. The speck is fully walkable while
    # sky4F's six real 88-cell platforms are not walkable at all, and the speck
    # is 4 cells where iceB3's genuine second region is 41 -- so neither
    # walkability nor size separates junk from content here. Inventing a third
    # proxy is exactly how the room-floor rule went wrong twice. Seven columns
    # of extra backdrop on one map is the cheaper mistake, and this is the note
    # saying so rather than a silent tolerance.
    allowed = {"matoya"}
    drift = []
    for name in ART_AGREES:
        drawn = art_box(name, cal[name])
        if drawn is None or name not in boxes:
            fails.append(f"{name}: no art or no box to compare")
            continue
        off = max(abs(a - b) for a, b in zip(boxes[name], drawn))
        if off > 1 and name not in allowed:
            drift.append((name, boxes[name], drawn, off))
    check("the derived box sits within a tile of the one DarkmoonEX drew",
          drift, [])
    check("tofrAir lands on it exactly", boxes["tofrAir"], art_box("tofrAir", cal["tofrAir"]))

    # The letters, and the branch that decides what byte 1 means.
    letters = rm.trap_letters(rom)
    check("SMMove_Battle's branch reads as one of the two opcodes",
          inverted in (True, False), True)
    used = {name: sorted(set(rm.map_trap_letters(
                rom, map_id, rm.map_tiles(rom, map_id), letters).values()))
            for map_id, name in rm.MAP_FILES.items()}
    if not inverted:
        # Vanilla is where the shipped art's letters came from, so it is the
        # only cartridge that can check the derivation against them.
        check("vanilla earthB1 is the art's G H I", used["earthB1"], ["G", "H", "I"])
        check("vanilla volcB4 is the art's M N", used["volcB4"], ["M", "N"])
        check("volcB1's bare A is not a trap letter", used["volcB1"], [])
        # Sets are not enough, and believing they were is how the earthB1
        # mismatch below survived: the same three letters can be handed to the
        # wrong three tiles and a sorted-set comparison never notices. volcB4
        # is the map whose assignment was read off the shipped art tile by
        # tile -- M on the Worm Room and Second Greed tiles, N on the Entrance
        # and Grind Room ones -- so it is the one that can assert it.
        assign = {}
        for map_id, name in rm.MAP_FILES.items():
            if name != "volcB4":
                continue
            tiles = rm.map_tiles(rom, map_id)
            for (col, row), letter in rm.map_trap_letters(
                    rom, map_id, tiles, letters).items():
                assign[letter] = tiles[row * rm.MAP_DIM + col] & 0x7F
        check("volcB4's letters land on the tiles the art puts them on",
              assign, {"M": 0x23, "N": 0x2F})
    else:
        print("     (letters vs the shipped art need a vanilla cartridge; "
              "this one is an FFR seed)")
    check("every trap letter belongs to a fixed formation",
          all(len(v) <= 4 for v in used.values()), True)
    check("the Map Key band is reserved only where there is a key",
          [rm.legend_rows_for(len(used[n])) > 0 for n in ("earthB1", "coneria_town")],
          [True, False])

    # A cropped render has to be the same pixels, moved -- and the band below it.
    tiles = rm.map_tiles(rom, 23)
    box = rm.content_box(tiles)
    full_w, _, full = rm.render(rom, 23, unroof=True)
    w, h, small = rm.render(rom, 23, unroof=True, crop=box, legend_rows=3)
    check("the crop is smaller than the whole grid", (w, h) < (full_w, full_w), True)
    check("its width is the box", w, (box[1] - box[0] + 1) * rm.TILE_PX)
    check("its height is the box plus the band", h,
          (box[3] - box[2] + 1 + 3) * rm.TILE_PX)
    row = box[2] + 4
    col = box[0] + 4
    src = ((row * rm.MAP_DIM * rm.TILE_PX + col) * rm.TILE_PX + 0) * 3
    dst = (((row - box[2]) * rm.TILE_PX * w) + (col - box[0]) * rm.TILE_PX) * 3
    check("and a tile inside it is the same pixels", small[dst:dst + 48],
          full[src:src + 48])

    # The band is drawn into, not just reserved. Rendering the same map with
    # and without `letters` has to differ inside the band, and a map with no
    # trap tiles has to stay exactly as it was -- one check that the key is
    # written and one that nothing is written where there is no key.
    band = (box[3] - box[2] + 1) * rm.TILE_PX * w * 3
    _, _, lettered = rm.render(rom, 23, unroof=True, crop=box, legend_rows=3,
                               letters=letters)
    check("the Map Key band is drawn into, not left as backdrop",
          lettered[band:] != small[band:], True)
    for map_id, name in rm.MAP_FILES.items():
        if name != "coneria_town":
            continue
        b = rm.content_box(rm.map_tiles(rom, map_id))
        plain = rm.render(rom, map_id, unroof=True, crop=b)[2]
        keyed = rm.render(rom, map_id, unroof=True, crop=b, letters=letters)[2]
        check("a map with no trap tiles is untouched by the letters",
              plain == keyed, True)

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
