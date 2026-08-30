#!/usr/bin/env python3
"""tools/noverworld_rules.py -- the derivation, and the two bugs that shaped it.

The full sweep is 1024 graph walks and takes over a minute, so it is not run
here. What is checked is the reasoning around it: the reachability test, the
minimisation, and the join. Those are where both real bugs were.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
sys.path.insert(0, HERE)

import entrance_graph as e          # noqa: E402
import noverworld_rules as nr       # noqa: E402

fails = []


def ok(cond, label, got=""):
    print(f"{'ok  ' if cond else 'FAIL'} {label:58} {got}")
    if not cond:
        fails.append(label)


# --- a chest is never stood on -------------------------------------------
#
# The first version of this tool asked whether the party could occupy a chest's
# own tile. walkable() says no for every chest in the game, so it called 241 of
# 249 locations unreachable on a cartridge where most of the board is open. The
# assertion below is what makes that a caught regression rather than a rerun.
every = set(e.ITEM_NAMES)
treasure = e.TP_SPEC_TREASURE
ok(not e.walkable(treasure, every),
   "a treasure tile is not walkable, holding everything")
ok(not e.walkable(treasure | e.TP_NOMOVE, every),
   "nor is one that also carries NOMOVE")

# so the test has to be adjacency, and must not accept the tile itself
tiles = {7: {(10, 11)}}
ok(nr.bump(7, 10, 10)(tiles), "bump: reachable from the tile below")
ok(not nr.bump(7, 10, 10)({7: {(10, 10)}}),
   "bump: the target's own tile does not count")
ok(not nr.bump(7, 10, 10)({7: {(12, 10)}}),
   "bump: a tile two away does not count")
ok(not nr.bump(7, 10, 10)({8: {(10, 11)}}),
   "bump: a neighbour on another map does not count")

# and its neighbours wrap, because reachable_tiles' keys are mod 64. A chest on
# column 63 approached from column 0 is the case; without the modulo it loses
# that approach and can report unreachable.
ok(nr.bump(7, 63, 10)({7: {(0, 10)}}),
   "bump: column 63 is approachable from column 0")
ok(nr.bump(7, 10, 0)({7: {(10, 63)}}),
   "bump: row 0 is approachable from row 63")

# --- minimal sets ---------------------------------------------------------
reaching = [frozenset({"key"}), frozenset({"key", "rod"})]
mins = nr.minimal_sets(reaching)
ok(mins == [["key"]], "minimal_sets keeps key and drops the key+rod superset",
   str(mins))

ok(nr.minimal_sets([]) is None,
   "minimal_sets returns None when no subset reaches it")

ok(nr.minimal_sets([frozenset(), frozenset({"key"})]) == [[]],
   "a location open from the start derives the empty set")

ok(nr.minimal_sets([frozenset({"rod"}), frozenset({"key"})]) ==
   [["key"], ["rod"]],
   "two independent routes both survive minimisation")

# --- the join -------------------------------------------------------------
rom_path = os.environ.get("FF1_ROM")
if not rom_path or not os.path.exists(rom_path):
    print("SKIP set FF1_ROM to a Final Fantasy cartridge to run the join")
else:
    with open(rom_path, "rb") as f:
        raw = f.read()
    by_name = {}
    placed = nr.placements(raw, "locations/NOverworld/overworld.json",
                           kinds=by_name)
    ok(bool(placed), "placements resolved something", f"{len(placed)} locations")

    kinds = {}
    for names in by_name.values():
        for kind in names:
            kinds[kind] = kinds.get(kind, 0) + 1
    # Eight NPCs have a node in the tree; the other six the cartridge places
    # host no section, so nothing joins to them. Guessing the kind from the
    # node name -- the first version of this -- found none of them, because
    # marker_tiles is keyed by node name and npc_positions.json by item code.
    ok(kinds.get("NPC") == 8, "exactly the eight NPCs with a node join",
       str(kinds))
    ok(kinds.get("chest", 0) > 200, "and every dungeon chest does too",
       str(kinds.get("chest")))

    for name, cells in placed.items():
        for m, c, r in cells:
            if not (0 <= m < e.MAP_COUNT and 0 <= c < 64 and 0 <= r < 64):
                ok(False, f"{name} placement in range", f"{m} ({c},{r})")
                break

    # --- the map is a torus -------------------------------------------
    #
    # SMMove_Right adds one to sm_scroll_x and masks AND #$3F, commented "and
    # wrap at 64 tiles" (bank_0F.asm:3070); the other three directions do the
    # same on their axis. The walk treated the map as a bounded rectangle, which
    # sealed off any region only reachable across an edge.
    #
    # Sea Shrine B1 is the case that found it. Three of its twelve Mermaid
    # chests sit behind an 85-tile pocket, and the vanilla route is to leave by
    # the top left and come back in at the top right. Without wrapping the walk
    # calls them unreachable holding every item in the game -- and says so
    # confidently, since nothing else about the floor looks wrong.
    rom = e.Rom.of(raw, rom_path)
    mode, _ = e.game_mode(rom)
    if mode != e.GAME_MODE_NOVERWORLD:
        print("SKIP  FF1_ROM is not a No-Overworld cartridge; "
              "the Sea Shrine wrap check needs one")
    else:
        g = e.Graph(rom)
        reach = nr.reachable_tiles(g, set(e.ITEM_NAMES))
        SEA_SHRINE_B1 = 46
        for label, col, row in (("Mermaids 4", 25, 4),
                                ("Mermaids 5", 26, 4),
                                ("Sea Incentive", 27, 4)):
            ok(nr.bump(SEA_SHRINE_B1, col, row)(reach),
               f"Sea Shrine {label} is reachable across the map edge")

print("\n" + ("FAILURES: " + ", ".join(fails) if fails else "ALL PASS"))
sys.exit(1 if fails else 0)
