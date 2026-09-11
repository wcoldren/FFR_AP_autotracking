"""The shipped No-Overworld tree keeps the committed shape, and the regen keeps
the shipped set.

`tools/ship_nov_maps.py` re-measures every pin on a redrawn map from cartridge
tiles, in the shape `locations/NOverworld/overworld.json` already has. The
shape is the guarantee: `tests/test_maps.lua` check 6 asks the two trees to
agree on which maps every node is drawn on, and that agreement is what drops
the two rolled bonus-chest aliases and the NPC pins a derived tree gains. So
what is checked here is the part of the tool that does the dropping, on a
synthetic tree, without a cartridge:

  * a tile the shape has no marker for is reported, not placed;
  * a marker the tiles cannot re-measure is a failure, not a silent keep;
  * two markers on one map take that map's tiles in tile order;
  * a marker on a map the regen does not draw is left exactly as it was.

And the other half, on the real index: with no No-Overworld render in an
override, `build_noverworld_maps_json` writes the pack's index unchanged. It
used to put the hand-drawn art back for every map that had some, which on a
pack that ships a No-Overworld set is a standard-only regen swapping the set
out for the vanilla drawings.
"""
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import regen_maps as r              # noqa: E402
import ship_nov_maps as ship        # noqa: E402

fails = []


def ok(cond, label, got=""):
    print(f"{'ok  ' if cond else 'FAIL'} {label:66} {got}")
    if not cond:
        fails.append(label)


# Two rendered maps, one region each, tile 16px from the origin -- the shape
# rendered_calibration emits for a map that did not slide.
CAL = {
    "dwarves": {"rom_map_id": 19, "tile_px": 16,
                "regions": [{"offset_x": 0, "offset_y": 0}]},
    "cardia": {"rom_map_id": 20, "tile_px": 16,
               "regions": [{"offset_x": 0, "offset_y": 0}]},
}
assert "dwarves" in r.REDRAWN and "cardia" in r.REDRAWN

TREE = [
    {"name": "Dwarf Cave",
     "map_locations": [{"map": "overworld", "x": 1, "y": 2}],
     "children": [
         {"name": "Dwarf Cave Dwarf Armory 5",
          "map_locations": [{"map": "dwarves", "x": 9, "y": 9}]},
         {"name": "Dwarf Cave Chests",
          "map_locations": [{"map": "dwarves", "x": 9, "y": 9},
                            {"map": "dwarves", "x": 9, "y": 9}]},
     ]},
]

# 1. a tile on a map the shape has no marker for is left out and said so
doc = copy.deepcopy(TREE)
tiles = {"Dwarf Cave Dwarf Armory 5": [(19, 10, 41), (20, 37, 27)],
         "Dwarf Cave Chests": [(19, 3, 4), (19, 1, 2)]}
placed, left_out, failed = ship.remeasure(doc, tiles, CAL, {})
ok(failed == [], "nothing failed on a tree every marker can be re-measured", failed)
ok(placed == 3, "three pins re-measured", placed)
ok(left_out == [("Dwarf Cave Dwarf Armory 5", "cardia", 37, 27)],
   "the tile on a map the shape has no marker for is left out", left_out)
armory = doc[0]["children"][0]["map_locations"]
ok(armory == [{"map": "dwarves", "x": 168, "y": 664}],
   "the one marker is re-measured to its tile's pixel", armory)

# 2. two markers on one map take its tiles in tile order
chests = doc[0]["children"][1]["map_locations"]
ok(chests == [{"map": "dwarves", "x": 24, "y": 40},
              {"map": "dwarves", "x": 56, "y": 72}],
   "two markers on one map take that map's tiles in tile order", chests)

# 3. a marker on a map the regen does not draw is untouched
ok(doc[0]["map_locations"] == [{"map": "overworld", "x": 1, "y": 2}],
   "a marker on a map the regen does not draw is left as it was")

# 4. a marker with no tile to re-measure it from is a failure, and the marker
#    is kept rather than dropped, so a run that ignored the failure would still
#    draw something
doc = copy.deepcopy(TREE)
tiles = {"Dwarf Cave Chests": [(19, 3, 4), (19, 1, 2)]}
placed, left_out, failed = ship.remeasure(doc, tiles, CAL, {})
ok(failed == [("Dwarf Cave Dwarf Armory 5", "dwarves", "no tile resolves here")],
   "a marker no tile re-measures is reported as a failure", failed)
ok(doc[0]["children"][0]["map_locations"] == [{"map": "dwarves", "x": 9, "y": 9}],
   "and the marker is kept as it was")

# 5. fewer tiles than markers on one map fails the markers it cannot fill
doc = copy.deepcopy(TREE)
tiles = {"Dwarf Cave Dwarf Armory 5": [(19, 10, 41)],
         "Dwarf Cave Chests": [(19, 3, 4)]}
placed, left_out, failed = ship.remeasure(doc, tiles, CAL, {})
ok(failed == [("Dwarf Cave Chests", "dwarves", "no tile resolves here")],
   "a map with fewer tiles than markers fails the marker left over", failed)
ok(placed == 2, "and places the ones it could", placed)

# 6. a sprite under a pin makes it a diamond, as the regen's own pins are
doc = copy.deepcopy(TREE)
tiles = {"Dwarf Cave Dwarf Armory 5": [(19, 10, 41)],
         "Dwarf Cave Chests": [(19, 3, 4), (19, 1, 2)]}
ship.remeasure(doc, tiles, CAL, {19: {(10, 41)}})
ok(doc[0]["children"][0]["map_locations"][0].get("shape") == "diamond",
   "a pin on a drawn sprite is a diamond")

# 7. with no No-Overworld render, the regen writes the pack's index unchanged
shipped = r.lenient(os.path.join(PACK, "maps", "NOverworldMaps.json"))
ok(r.build_noverworld_maps_json(set()) == shipped,
   "no nov render: the pack's NOverworldMaps.json is written as it is")
ok(r.build_noverworld_maps_json({"std"}) == shipped,
   "a std-only render leaves it alone too")
nov_rows = {e["name"]: e["img"] for e in shipped if e["name"] != "incentives"}
ok(nov_rows == {n: f"images/maps/nov/{n}.png" for n in r.render_maps.MAP_FILES.values()},
   "the shipped index points all 61 maps at images/maps/nov/",
   f"{len(nov_rows)} rows")
rendered = r.build_noverworld_maps_json({"nov"})
ok(rendered == shipped,
   "a nov render writes the same index, since the paths are the same")
ok(all(os.path.exists(os.path.join(PACK, img)) for img in nov_rows.values()),
   "every image the index names is in the checkout")

print()
if fails:
    print(f"{len(fails)} FAILED")
    for f in fails:
        print("  " + f)
    raise SystemExit(1)
print("all ship_nov_maps checks passed")
