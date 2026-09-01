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

The trap-mark derivation is checked here as well, because the Map Key band
is sized from it: on a *vanilla* cartridge the marks have to come out the way
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
import extract_npcs as en                                      # noqa: E402
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

    # Off this cartridge, the way render_maps.check_crops reads it. The vanilla
    # snapshot in npc_positions.json would check the crop against tiles this
    # seed does not use, which is the whole reason the pins stopped reading it.
    npcs = {}
    for name, places in en.extract(rom).items():
        for q in places:
            npcs.setdefault(q["map_id"], []).append(
                (f"npc {name}", q["tile_col"], q["tile_row"]))

    crops = {}
    cut, kept, whole = [], 0, 0
    for map_id in range(rm.MAP_COUNT):
        tiles = rm.map_tiles(rom, map_id)
        keep = [cell for _, cell in rm.protected_cells(
            rom, map_id, tiles, graph, npcs.get(map_id, ()))]
        crop = crops[rm.MAP_FILES[map_id]] = rm.content_crop(tiles, keep=keep)
        cut += [(rm.MAP_FILES[map_id], what, cell) for what, cell in
                rm.crop_violations(rom, map_id, tiles, crop, graph,
                                   npcs.get(map_id, ()))]
        area = crop.size[0] * crop.size[1]
        kept += area
        whole += area == rm.MAP_DIM * rm.MAP_DIM

        # The box is a box: inside the grid, and the right way round. The
        # slide does not get to make it anything else -- that is the point of
        # boxing after the rotation rather than carrying a torn box around.
        c0, c1, r0, r1 = crop.box
        if not (0 <= c0 <= c1 < rm.MAP_DIM and 0 <= r0 <= r1 < rm.MAP_DIM):
            fails.append(f"map {map_id} box is not a box: {crop.box}")
        if not all(0 <= v < rm.MAP_DIM for v in crop.shift):
            fails.append(f"map {map_id} shift is not a shift: {crop.shift}")

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
              crops["iceB1"].holds(*fairy[0]), True)

    # Against the hand art, which is the reference the rule is measured on.
    inverted = rm.battle_byte_inverted(rom)
    with open(os.path.join(TOOLS, "map_calibration.json")) as f:
        cal = {k: v for k, v in json.load(f).items() if not k.startswith("_")}
    # Matoya's Cave carries four cells of tile $0B at (20-23,13), detached, out
    # in the void with nothing near them, and they used to stretch the box seven
    # columns past where DarkmoonEX cropped. That was written down here as an
    # accepted mistake, because neither walkability nor size separates the speck
    # from Ice Cave B3's genuine 41-cell second lobe.
    #
    # The speck rule separates them on a third question -- does the map point at
    # anything there -- and the seven columns are gone: Matoya boxes 18 wide
    # where it boxed 25, which is DarkmoonEX's crop. So the exemption is gone
    # too, and Matoya is asserted like the rest. A tolerance that turns into a
    # passing check is the best evidence the rule is the right one.
    allowed = set()
    drift = []
    for name in ART_AGREES:
        drawn = art_box(name, cal[name])
        if drawn is None or name not in crops:
            fails.append(f"{name}: no art or no box to compare")
            continue
        off = max(abs(a - b) for a, b in zip(crops[name].box, drawn))
        if off > 1 and name not in allowed:
            drift.append((name, crops[name].box, drawn, off))
    check("the derived box sits within a tile of the one DarkmoonEX drew",
          drift, [])

    # The speck rule, and the band its bound sits in. Dropping a region is only
    # safe while "speck" and "small region of a real map" stay far apart; if a
    # cartridge ever puts one near MAX_SPECK this has started guessing, and the
    # gap check is what says so instead of letting it.
    dropped_sizes, kept_sizes = [], []
    for map_id in range(rm.MAP_COUNT):
        tiles = rm.map_tiles(rom, map_id)
        keep = {cell for _, cell in rm.protected_cells(
            rom, map_id, tiles, graph, npcs.get(map_id, ()))}
        content = rm.content_cells(tiles)
        comps = rm.components(content)
        _, dropped = rm.drop_specks(content, keep)
        dropped_sizes += [len(c) for c in dropped]
        kept_sizes += [len(c) for c in comps[1:]
                       if c not in dropped and not (c & keep)]
    biggest, smallest = max(dropped_sizes, default=0), min(kept_sizes, default=10**9)
    print(f"     ({len(dropped_sizes)} specks dropped, largest {biggest}; "
          f"smallest region kept with nothing on it {smallest})")
    check("every dropped speck is well under the bound", biggest < rm.MAX_SPECK, True)
    check("and every region kept is well over it", smallest > rm.MAX_SPECK, True)
    check("so the bound sits in an empty band, not on a real value",
          smallest - biggest > rm.MAX_SPECK, True)

    # The largest region is never a speck, so no map can be dropped to nothing.
    tiny = [rm.MAP_FILES[m] for m in range(rm.MAP_COUNT)
            if not rm.content_cells(rm.map_tiles(rom, m))
            or not rm.drop_specks(rm.content_cells(rm.map_tiles(rom, m)))[0]]
    check("no map is dropped to nothing", tiny, [])
    check("tofrAir lands on it exactly", crops["tofrAir"].box,
          art_box("tofrAir", cal["tofrAir"]))
    check("and none of the maps it is measured on slid",
          [n for n in ART_AGREES if crops[n].shift != (0, 0)], [])

    # The marks, and the branch that decides what byte 1 means.
    marks = rm.trap_marks(rom)
    check("SMMove_Battle's branch reads as one of the two opcodes",
          inverted in (True, False), True)
    used = {name: sorted(set(rm.map_trap_marks(
                rom, map_id, rm.map_tiles(rom, map_id), marks).values()))
            for map_id, name in rm.MAP_FILES.items()}
    if not inverted:
        # Vanilla is where the shipped art's marks came from, so it is the
        # only cartridge that can check the derivation against them -- and the
        # derivation no longer reproduces them, by one place, on purpose.
        #
        # DarkmoonEX numbered every fixed-formation entry in the tileset
        # tables. This numbers the formations that stand on a map, so that a
        # mark can be one glyph. The gap between the two is nameable rather
        # than a fudge: formation $00 is a fixed trap tile in five tileset
        # entries and no map places any of them, it sorts ahead of earthB1's
        # three, and it is the whole shift. Asserted as the shift, because a
        # bare list of marks would not say why they moved.
        check("vanilla earthB1 is the art's G H I, back one", used["earthB1"],
              ["F", "G", "H"])
        check("vanilla volcB4 is the art's M N, back one", used["volcB4"],
              ["L", "M"])
        check("and the one is formation $00, which stands on no map",
              (0x00 in rm.fixed_formations(rom).values(),
               0x00 in rm.standing_formations(rom)), (True, False))
        check("volcB1's bare A is not a trap mark", used["volcB1"], [])
        # Sets are not enough, and believing they were is how the earthB1
        # mismatch below survived: the same three marks can be handed to the
        # wrong three tiles and a sorted-set comparison never notices. volcB4
        # is the map whose assignment was read off the shipped art tile by
        # tile -- the art's M on the Worm Room and Second Greed tiles, its N on
        # the Entrance and Grind Room ones -- so it is the one that can assert
        # it, one mark back on each.
        assign = {}
        for map_id, name in rm.MAP_FILES.items():
            if name != "volcB4":
                continue
            tiles = rm.map_tiles(rom, map_id)
            for (col, row), mark in rm.map_trap_marks(
                    rom, map_id, tiles, marks).items():
                assign[mark] = tiles[row * rm.MAP_DIM + col] & 0x7F
        check("volcB4's marks land on the tiles the art puts them on",
              assign, {"L": 0x23, "M": 0x2F})
    else:
        print("     (marks vs the shipped art need a vanilla cartridge; "
              "this one is an FFR seed)")
    check("every trap mark belongs to a fixed formation",
          all(len(v) <= 4 for v in used.values()), True)

    # One formation, one mark, and one mark, one formation. This is the defect
    # the formation keying closes: keyed by (tileset, tile), the same enemies
    # were G on earthB1 and W on marshB3, so a mark said nothing about which
    # fight was on the tile.
    #
    # Grouping trap_marks' own dict by formation would not catch that, or
    # anything else. It is built {key: mark[fixed[key]]} from a per-formation
    # dict, so a formation carries one mark by construction and a mark stands
    # for one formation because TRAP_MARKS is asserted duplicate-free -- both
    # halves pass for every cartridge and every labelling, including the broken
    # one. So byte 1 is re-read here, off the tileset property table, and the
    # question is put to the *maps*: two tiles that spawn the same fight, on
    # whatever maps they stand on, have to carry the same mark.
    inverted = rm.battle_byte_inverted(rom)
    seen = {}                              # formation -> {mark: {map names}}
    for map_id, name in rm.MAP_FILES.items():
        tiles = rm.map_tiles(rom, map_id)
        base = rm.TILESET_PROP + rom[rm.TILESET_LUT + map_id] * rm.PROP_STRIDE
        for (col, row), mark in rm.map_trap_marks(
                rom, map_id, tiles, marks).items():
            tile = tiles[row * rm.MAP_DIM + col] & 0x7F
            b1 = rom[base + tile * 2 + 1]
            random = (b1 == 0) if inverted else bool(b1 & 0x80)
            if random:                     # a marked tile that fights randomly
                seen.setdefault("random", {}).setdefault(mark, set()).add(name)
                continue
            seen.setdefault(b1, {}).setdefault(mark, set()).add(name)
    check("no marked tile spawns a random encounter",
          sorted(seen.get("random", {})), [])
    check("no fight carries two marks across the maps it stands on",
          {f"${f:02X}": {m: sorted(v) for m, v in d.items()}
           for f, d in seen.items() if len(d) > 1}, {})
    per_mark = {}
    for f, d in seen.items():
        for m in d:
            per_mark.setdefault(m, set()).add(f)
    check("no mark stands for two fights",
          {m: sorted(f"${f:02X}" for f in v)
           for m, v in per_mark.items() if len(v) > 1}, {})

    # And the check above has something to compare, which is the part that
    # makes it able to fail: at least one fight has to stand on more than one
    # map. On a cartridge where none did, the two checks would be vacuous
    # again and this says so instead of letting them pass quietly.
    spread = max(len(set().union(*d.values())) for d in seen.values())
    check("at least one fight stands on two maps, so the check can fail",
          spread > 1, True)
    print(f"     (the widest-spread fight stands on {spread} maps)")

    # And every mark is a single glyph, which is what lets it sit on the tile
    # it marks rather than spilling across its neighbour. The fallback to
    # two-character labels exists for a cartridge past 35 formations and no
    # measured one reaches it -- so what is asserted is the count that keeps
    # the fallback unused, not the fallback.
    standing = rm.standing_formations(rom)
    check("every mark is one glyph the font can draw",
          sorted({m for m in marks.values()
                  if len(m) != 1 or m not in rm.TRAP_MARKS}), [])
    check("and the formations standing on a map fit inside the marks",
          len(standing) <= len(rm.TRAP_MARKS), True)
    print(f"     ({len(standing)} formations stand on a map, "
          f"{len(set(marks.values()))} marks, {len(rm.TRAP_MARKS)} available)")
    check("the Map Key band is reserved only where there is a key",
          [rm.legend_rows_for(len(used[n])) > 0 for n in ("earthB1", "coneria_town")],
          [True, False])

    # A cropped render has to be the same pixels, moved -- and the band below
    # it. Two maps, because a crop has two shapes now: mirage1F sits inside the
    # grid and is boxed where it stands, and con_castle is drawn across the
    # join and is boxed after the slide. The second is the case with somewhere
    # to go wrong, and there was no wrapped case here at all before.
    for map_id, wrapped in ((23, False), (8, True)):
        tiles = rm.map_tiles(rom, map_id)
        crop = rm.content_crop(tiles)
        name = rm.MAP_FILES[map_id]
        check(f"{name} is {'' if wrapped else 'not '}drawn across the join",
              crop.shift != (0, 0), wrapped)
        full_w, _, full = rm.render(rom, map_id, unroof=True)
        w, h, small = rm.render(rom, map_id, unroof=True, crop=crop,
                                legend_rows=3)
        check(f"{name}'s crop is smaller than the whole grid",
              (w, h) < (full_w, full_w), True)
        check(f"{name}'s width is the box", w, crop.size[0] * rm.TILE_PX)
        check(f"{name}'s height is the box plus the band", h,
              (crop.size[1] + 3) * rm.TILE_PX)

        # Every frame tile, not one sample: on a slid map a single cell can
        # agree by luck while the two halves are swapped, and the whole point
        # of the slide is which half went where.
        moved = []
        for fr in range(crop.size[1]):
            for fc in range(crop.size[0]):
                col, row = crop.source(fc, fr)
                src = ((row * rm.MAP_DIM * rm.TILE_PX + col) * rm.TILE_PX) * 3
                dst = ((fr * rm.TILE_PX * w) + fc * rm.TILE_PX) * 3
                if small[dst:dst + 48] != full[src:src + 48]:
                    moved.append((fc, fr))
        check(f"and every tile of {name} is the same pixels, moved", moved, [])

        # ... and the move is the one the calibration will publish: place() is
        # the inverse of source(), which is what keeps a marker on its chest.
        roundtrip = [(fc, fr) for fr in range(crop.size[1])
                     for fc in range(crop.size[0])
                     if crop.place(*crop.source(fc, fr)) != (fc, fr)]
        check(f"and {name}'s tile-to-pixel mapping inverts", roundtrip, [])

    # The band is drawn into, not just reserved. Rendering the same map with
    # and without `marks` has to differ inside the band, and a map with no
    # trap tiles has to stay exactly as it was -- one check that the key is
    # written and one that nothing is written where there is no key.
    #
    # The map is chosen for having a mark rather than named. This was mirage1F,
    # which has three on the standard duck cartridge and **none** on the
    # No-Overworld one -- so on that cartridge the check was passing on an
    # artefact: a `Map Key` heading over an empty list, written because the key
    # was the trap marks' own job and ran whenever it was handed the table. Fix
    # that and the check had nothing left to demonstrate, which is how it came
    # to light.
    keyed_map = next((m for m in rm.MAP_FILES
                      if rm.map_trap_marks(rom, m, rm.map_tiles(rom, m),
                                           marks)), None)
    check("some map on this cartridge carries a trap mark",
          keyed_map is not None, True)
    # Guarded, so a cartridge with no mark anywhere records that one failure and
    # goes on. Reading straight through leaves map_tiles(rom, None) to raise,
    # and the traceback takes the rest of this file's checks with it.
    if keyed_map is not None:
        tiles = rm.map_tiles(rom, keyed_map)
        crop = rm.content_crop(tiles)
        w, h, small = rm.render(rom, keyed_map, unroof=True, crop=crop,
                                legend_rows=3)
        band = crop.size[1] * rm.TILE_PX * w * 3
        _, _, lettered = rm.render(rom, keyed_map, unroof=True, crop=crop,
                                   legend_rows=3, marks=marks)
        check(f"the Map Key band on {rm.MAP_FILES[keyed_map]} is drawn into, "
              "not left as backdrop", lettered[band:] != small[band:], True)
    for map_id, name in rm.MAP_FILES.items():
        if name != "coneria_town":
            continue
        b = rm.content_crop(rm.map_tiles(rom, map_id))
        plain = rm.render(rom, map_id, unroof=True, crop=b)[2]
        keyed = rm.render(rom, map_id, unroof=True, crop=b, marks=marks)[2]
        check("a map with no trap tiles is untouched by the marks",
              plain == keyed, True)

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
