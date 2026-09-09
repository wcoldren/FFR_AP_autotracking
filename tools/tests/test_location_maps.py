#!/usr/bin/env python3
"""scripts/location_maps.lua says what the location trees say.

The pack needs the map a location's pin is drawn on so a hint can say where to
look, and no runtime source can answer: a section's Lua surface knows its counts
and its highlight and nothing about where it is drawn. So the answer is joined
offline out of the trees and committed, and this is what stops the copy
drifting.

Reads no cartridge.
"""

import os
import sys

TESTS = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(TESTS)
PACK = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import location_maps  # noqa: E402
import render_maps  # noqa: E402
import split_locations  # noqa: E402

fail = 0


def check(label, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'ok  ' if ok else 'FAIL'} {label:<58} {got}")
    if not ok:
        print(f"     wanted {want}")


# Every map that holds no location the multiworld has an id for. The eight towns
# are here because the shipped hand art draws their NPCs on the overworld poster
# rather than on the town tab, not because anything is missing; the rest carry no
# chest at all. Named rather than counted so that a regen which starts placing a
# marker on one of them reads as a deliberate change instead of a silent diff.
NO_MAPPED_LOCATION = [
    "bahamut", "bahamutB2", "con_castle2F", "coneria_town", "crescent_lake",
    "earthB5", "elfland", "gaia", "lefein", "marshB1", "melmond", "mirage3F",
    "onrac", "ordeals1F", "pravoka", "seaB5", "sky4F", "sky5F", "tofr2F",
    "volcB1", "volcB3",
]


def main():
    rows, unknown, unplaced = location_maps.table()

    check("no map name the trees use is unknown to render_maps", unknown, [])
    check("and every mapped location is placed somewhere", unplaced, [])

    mapping = split_locations.load_mapping(limit=None)
    paths = sorted({path for path, _ in mapping.values()})
    check("every location the multiworld names has a map",
          sorted(set(paths) - set(rows)), [])
    check("  and the table names nothing else",
          sorted(set(rows) - set(paths)), [])

    with open(os.path.join(PACK, "scripts", "location_maps.lua")) as fh:
        committed = fh.read()
    check("the committed table is what the tool writes now",
          committed == location_maps.render(rows), True)

    ids = set(render_maps.MAP_FILES) | {location_maps.OVERWORLD_ID}
    stray = sorted({i for v in rows.values() for i in v} - ids)
    check("every map id is a cartridge map or the overworld", stray, [])

    # One table serves all eight variants, so the two trees have to agree about
    # where a location is drawn. A No-Overworld art that moved a chest to another
    # floor has to be noticed rather than quietly averaged into the union.
    saved = location_maps.TREES
    try:
        location_maps.TREES = ("locations/overworld.json",
                               "locations/incentives.json")
        std, _, _ = location_maps.table()
        location_maps.TREES = ("locations/NOverworld/overworld.json",
                               "locations/NOverworld/incentives.json")
        nov, _, _ = location_maps.table()
    finally:
        location_maps.TREES = saved
    check("the standard and No-Overworld trees agree on every location",
          sorted(p for p in std if std[p] != nov.get(p)), [])

    # The incentive sheet is not a cartridge map, so it is dropped -- which is
    # only safe because every path it would have spoken for is in the overworld
    # tree too, carrying a real map.
    try:
        location_maps.TREES = ("locations/overworld.json",
                               "locations/NOverworld/overworld.json")
        without, _, unplaced_without = location_maps.table()
    finally:
        location_maps.TREES = saved
    check("the incentive sheet adds no location the dungeons lack",
          unplaced_without, [])
    check("  and leaves every map id unchanged",
          sorted(p for p in rows if rows[p] != without.get(p)), [])

    used = {i for v in rows.values() for i in v}
    bare = sorted(render_maps.MAP_FILES[i]
                  for i in set(render_maps.MAP_FILES) - used)
    check("the maps holding no mapped location are the ones we know about",
          bare, sorted(NO_MAPPED_LOCATION))

    print("")
    if fail:
        print(f"{fail} FAILED")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
