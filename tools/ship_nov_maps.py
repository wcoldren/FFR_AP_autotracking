#!/usr/bin/env python3
"""Write the committed No-Overworld art set and its location tree into the pack.

Rendering from a cartridge is an optional upgrade and always will be; what
somebody who installs this pack sees is what is committed. On a No-Overworld
seed the hand-drawn art was wrong about 34 to 39 of the 61 maps -- it drew town
walls the mode seals and omitted the 75 staircases it stamps. One committed art
set fixes that for the mode, and only for the mode, because No-Overworld is the
one variant that is nearly seed-independent: rendered without trap letters,
two No-Overworld cartridges differ on `waterfall` alone, and a third whose flags
differ adds `gaia` and `lefein`. `docs/ROADMAP.md` section 4 holds the case.

**The art is one cartridge's; the tree is not.** The art can be rendered
straight off a No-Overworld cartridge, and is -- regen_maps.py draws it into a
scratch directory with every guard it has, and the images are copied out of
that. The location tree cannot be taken the same way, because a derived tree
encodes the cartridge and not the mode:

  * `ToFRMode` decides which floors a ToFR chest is wired on, and a cartridge
    is one mode. A Short cartridge's tree carries a pin on Chaos and none on
    Fire or 3F; a Long one the reverse; and neither covers Mid, which lays
    copies on 1F, Earth and Water that exist on no other mode. The shipped
    tree wants every mode's pin, with the rule that shows only the right one --
    which is what `locations/overworld.json` already carries, at the hand art's
    pixels.
  * No-Overworld's two bonus chests, `Cardia (44,8)` and `SkyPalace5F (7,1)`,
    each borrow a ToFR chest index, and which index is rolled per cartridge --
    five cartridges give four pairs. A derived tree hangs a pin on whichever
    ToFR location the roll aliased. The committed tree carries neither, on
    purpose: they are the tree's trap letters.
  * A cartridge places NPCs the hand tree pins only on the overworld -- Astos,
    Matoya, Bikke, the Fairy, Bahamut -- and a regen gives each a pin on its
    own map. `tests/test_maps.lua` check 6 asks the two trees to agree on which
    maps every node is drawn on, so the shipped tree cannot gain those until
    the standard one does.

So the tree is built the other way round: start from the committed tree's
shape -- the nodes, and the maps each is pinned on -- and re-measure every pin
on a redrawn map from the tile its chest or NPC sits on, at the rendered art's
crop. The tiles come from three cartridges. Everything off the ToFR floors is
read from the No-Overworld cartridge the art was drawn from, because that is
the mode whose placement it is (Nerrick stands two rows from where a standard
seed puts him). The ToFR floors are read from one cartridge per mode and
unioned, since a chest is only wired on its own mode's floors and
`marker_tiles` drops the copies a cartridge lays and never wires. The ToFR
floors are laid the same way for a mode whatever the GameMode -- measured on
the art, a Long No-Overworld render and a Long standard one differ on `tof`
alone, and there on two sealed door tiles rather than on the chests -- so the
Long and Mid cartridges need not be No-Overworld ones, which is as well: no
Mid No-Overworld cartridge exists here.

A committed marker with no tile to re-measure it from, or with more tiles than
markers, stops the run and says which. A tile the committed shape has no
marker for is reported as left out, and the run says how many and where, so
"the aliases were dropped" is something the output shows rather than something
this docstring promises.

The ToFR floors that differ by mode are drawn as the Short cartridge has them
-- Chaos with its chest room, 1F with its extra stair -- because every
No-Overworld cartridge on hand that a person rolled is Short, the oracle
presets are Short, and Long exists only as a control rolled to answer this
question. A Long or Mid player sees Short's Chaos room with no pins on it, and
Mid's five copies on floors that draw no chest under the pin; both are the
hand art's own residual, which drew Chaos with no room and Mid's floors with
no copies for every mode.

    tools/ship_nov_maps.py <No-Overworld ROM, Short> --long <ROM> --mid <ROM>
    tools/ship_nov_maps.py ... --apply

Writes nothing without `--apply`. With it, writes `images/maps/nov/*.png`,
`maps/NOverworldMaps.json` and `locations/NOverworld/overworld.json`, and
nothing else: the incentive sheet keeps `nooverworldmap.jpg`, and the layouts
are shared across the variants, so the ten maps the pack never had a tab for
gain their art here and their tab elsewhere.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "ffr_flags"))

import entrance_graph  # noqa: E402
import ffr_flags  # noqa: E402
import pin_visibility  # noqa: E402
import regen_maps  # noqa: E402
import render_maps  # noqa: E402
import sprites  # noqa: E402
import tofr_diff  # noqa: E402

TREE = "locations/NOverworld/overworld.json"
INDEX = "maps/NOverworldMaps.json"
ART_DIR = "images/maps/nov"

# ToFRMode as the flag block spells it. The cartridge handed in for each role
# has to be that mode, and is checked rather than trusted: a Long cartridge
# passed as --mid would union Long's tiles twice and leave Mid's floors bare,
# and nothing downstream could tell.
SHORT, LONG, MID = 2, 0, 1


def read_rom(path):
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:4] != b"NES\x1a":
        sys.exit(f"{path}: not an iNES ROM")
    return raw


def tofr_mode(raw, path):
    try:
        _, flags = ffr_flags.decode_rom(raw)
    except ffr_flags.DecodeError as err:
        sys.exit(f"{path}: cannot read the flags: {err}")
    mode = flags.get("ToFRMode")
    if mode == tofr_diff.TOFR_MODE_RANDOM:
        # The flag block records the setting and not the roll, so a Random
        # cartridge is some mode and does not say which.
        sys.exit(f"{path}: ToFRMode is Random, which the cartridge does not "
                 "resolve; pass a cartridge that names its mode")
    return mode


def want_mode(raw, path, mode, role):
    got = tofr_mode(raw, path)
    if got != mode:
        sys.exit(f"{path}: ToFRMode is {tofr_diff.MODE_NAME.get(got, got)}, "
                 f"and --{role} wants {tofr_diff.MODE_NAME[mode]}")


def render(rom_path, out_dir):
    """Run the regen into `out_dir` and return the rendered art's paths."""
    cmd = [sys.executable, os.path.join(HERE, "regen_maps.py"), rom_path,
           "-o", out_dir, "--traps", "none"]
    done = subprocess.run(cmd, capture_output=True, text=True)
    if done.returncode != 0:
        sys.stdout.write(done.stdout)
        sys.stderr.write(done.stderr)
        sys.exit(f"regen_maps.py exited {done.returncode}; nothing written")
    art = os.path.join(out_dir, ART_DIR)
    names = sorted(n for n in os.listdir(art) if n.endswith(".png"))
    want = sorted(f"{n}.png" for n in render_maps.MAP_FILES.values())
    if names != want:
        sys.exit(f"the regen drew {len(names)} maps into {art} and this "
                 f"expected {len(want)}")
    return art


def tiles_for(raw, path, only_tofr):
    """{node name: [(map_id, col, row)]} this cartridge places, live copies only.

    `only_tofr` keeps the ToFR floors and nothing else: the Long and Mid
    cartridges are here for their ToFR wiring, and every other placement they
    hold is a standard seed's.
    """
    graph = entrance_graph.Graph(entrance_graph.Rom.of(raw, path))
    dropped = []
    tiles = regen_maps.marker_tiles(raw, TREE, dropped, graph)
    if only_tofr:
        keep = set(tofr_diff.tofr_map_ids())
        tiles = {name: [t for t in cells if t[0] in keep]
                 for name, cells in tiles.items()}
        tiles = {name: cells for name, cells in tiles.items() if cells}
    return tiles, dropped, graph


def union(*tile_sets):
    out = {}
    for tiles in tile_sets:
        for name, cells in tiles.items():
            have = out.setdefault(name, [])
            for cell in cells:
                if cell not in have:
                    have.append(cell)
    return out


def remeasure(doc, tiles_by_name, cal, sprite_cells, crops_):
    """Re-place every pin on a redrawn map from its tile, in the committed shape.

    -> (placed, left_out, failed): counts and reports. `left_out` is every
    tile the committed shape has no marker for, as (name, map name, col, row);
    `failed` is every committed marker this could not re-measure, as
    (name, map name, why) -- and every tile that lies outside the box its map
    is drawn to, since a pixel off the image is not a placement.

    `crops_` is {map name: render_maps.Crop}, the same boxes the art was cut
    to. The calibration alone cannot say a tile is off the crop: every region
    `rendered_calibration` emits spans the whole 64-tile axis, so
    `marker_pixel` answers for any tile on the grid and the pixel it gives
    for one outside the box is simply negative or past the edge. The regen
    catches that on its own tree by checking the pixel against the image
    (`stray`, on the cartridge it drew from); here the Long and Mid ToFR tiles
    are measured against the Short cartridge's crop and that check never ran
    on them, so it is made here, on the tile, before the pixel is kept.
    """
    by_rom = regen_maps.maps_by_rom_id(cal)
    placed = 0
    left_out = []
    failed = []

    def walk(nodes):
        nonlocal placed
        for n in nodes:
            if not isinstance(n, dict):
                continue
            name = n.get("name")
            marks = n.get("map_locations") or []
            # Every tile this node resolves to, as the pixel it would get,
            # grouped by the map that pixel is on. A tile outside the box its
            # map is drawn to would get a pixel off the image, and is a
            # failure like any other rather than a marker quietly off the
            # edge -- see the docstring for why the calibration cannot say so.
            fresh = {}
            for cell in tiles_by_name.get(name, ()):
                map_id, col, row = cell
                ml = regen_maps.marker_pixel(by_rom, *cell, sprite_cells)
                if ml is None:
                    failed.append((name, f"rom map {map_id}",
                                   f"tile ({col},{row}) is on no "
                                   "rendered map"))
                    continue
                if not crops_[ml["map"]].holds(col, row):
                    failed.append((name, ml["map"],
                                   f"tile ({col},{row}) is outside the box "
                                   "the map is drawn to"))
                    continue
                fresh.setdefault(ml["map"], []).append((cell, ml))
            out = []
            for ml in marks:
                map_name = ml.get("map")
                if map_name not in regen_maps.REDRAWN:
                    out.append(ml)
                    continue
                pool = fresh.get(map_name) or []
                if not pool:
                    failed.append((name, map_name, "no tile resolves here"))
                    out.append(ml)
                    continue
                # Two committed markers on one map take its tiles in tile
                # order, so the assignment is deterministic; which pin gets
                # which tile is not a fact the tree records.
                pool.sort(key=lambda pair: pair[0])
                _, pixel = pool.pop(0)
                out.append(pixel)
                placed += 1
            for map_name, pool in fresh.items():
                for cell, _ in pool:
                    left_out.append((name, map_name, cell[1], cell[2]))
            if marks:
                n["map_locations"] = out
            walk(n.get("children") or [])

    walk(doc)
    return placed, left_out, failed


def main():
    ap = argparse.ArgumentParser(
        description="Write the committed No-Overworld art set and its "
                    "location tree into the pack.")
    ap.add_argument("rom", help="the No-Overworld cartridge to draw from; "
                                "Short, which is what the art will show")
    ap.add_argument("--long", required=True, metavar="ROM",
                    help="a cartridge with ToFRMode Long, for its ToFR tiles")
    ap.add_argument("--mid", required=True, metavar="ROM",
                    help="a cartridge with ToFRMode Mid, for its ToFR tiles")
    ap.add_argument("--apply", action="store_true",
                    help="write the files; without it, report only")
    args = ap.parse_args()

    raw = read_rom(args.rom)
    if regen_maps.mode_of(raw, args.rom) != "nov":
        sys.exit(f"{args.rom}: not a No-Overworld cartridge")
    want_mode(raw, args.rom, SHORT, "rom")
    raw_long = read_rom(args.long)
    want_mode(raw_long, args.long, LONG, "long")
    raw_mid = read_rom(args.mid)
    want_mode(raw_mid, args.mid, MID, "mid")

    # The tiles, before the render: a cartridge that cannot place its own
    # tree is not worth fifteen seconds of drawing.
    tiles, dropped, graph = tiles_for(raw, args.rom, only_tofr=False)
    tofr_long, _, _ = tiles_for(raw_long, args.long, only_tofr=True)
    tofr_mid, _, _ = tiles_for(raw_mid, args.mid, only_tofr=True)
    tiles_by_name = union(tiles, tofr_long, tofr_mid)
    print(f"{len(tiles)} nodes place on the No-Overworld cartridge, "
          f"{len(tofr_long)} on the Long cartridge's ToFR floors, "
          f"{len(tofr_mid)} on the Mid one's; {len(dropped)} placements "
          "dropped as backdrop or stranded")

    # The same crop and calibration the regen draws with, from the same
    # functions on the same cartridge, so the pixel here is the pixel there.
    npc_cells = regen_maps.npc_cells_of(raw)
    crops_ = regen_maps.crops(raw, graph, npc_cells)
    cal = regen_maps.rendered_calibration(raw, crops_)
    sprite_cells = {map_id: sprites.drawn_cells(raw, graph, map_id)
                    for map_id in render_maps.MAP_FILES}

    doc = regen_maps.lenient(os.path.join(PACK, TREE))
    placed, left_out, failed = remeasure(doc, tiles_by_name, cal, sprite_cells,
                                         crops_)
    print(f"{placed} pins re-measured onto the rendered art")
    if left_out:
        print(f"{len(left_out)} placements the committed tree has no marker "
              "for, left out:")
        for name, map_name, col, row in sorted(left_out):
            print(f"  {name}: {map_name} ({col},{row})")
    if failed:
        print(f"\nFAILED: {len(failed)} committed markers could not be "
              "re-measured:")
        for name, map_name, why in failed:
            print(f"  {name} on {map_name}: {why}")
        print("\nnothing written.")
        return 1
    tally = pin_visibility.stamp(doc)
    print(f"{sum(v for k, v in tally.items() if k)} pins carry a visibility "
          "rule")
    tree = pin_visibility.render(doc)

    with tempfile.TemporaryDirectory() as tmp:
        art = render(args.rom, tmp)
        index = regen_maps.build_noverworld_maps_json({"nov"})
        index_text = json.dumps(index, indent=4) + "\n"
        names = sorted(os.listdir(art))
        # Say what would change, whether or not it is about to.
        changed = []
        dest = os.path.join(PACK, ART_DIR)
        for name in names:
            here = os.path.join(dest, name)
            with open(os.path.join(art, name), "rb") as f:
                new = f.read()
            if not os.path.exists(here):
                changed.append(f"{ART_DIR}/{name} (new)")
            else:
                with open(here, "rb") as f:
                    if f.read() != new:
                        changed.append(f"{ART_DIR}/{name}")
        for rel, text in ((INDEX, index_text), (TREE, tree)):
            path = os.path.join(PACK, rel)
            with open(path) as f:
                if f.read() != text:
                    changed.append(rel)
        print(f"{len(names)} maps rendered; {len(changed)} file(s) differ "
              "from the checkout" + (":" if changed else ""))
        for rel in changed:
            print(f"  {rel}")
        if not args.apply:
            print("\ndry run; --apply to write")
            return 0
        os.makedirs(dest, exist_ok=True)
        for name in names:
            shutil.copyfile(os.path.join(art, name), os.path.join(dest, name))
        with open(os.path.join(PACK, INDEX), "w") as f:
            f.write(index_text)
        with open(os.path.join(PACK, TREE), "w") as f:
            f.write(tree)
    print(f"wrote {len(names)} maps, {INDEX} and {TREE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
