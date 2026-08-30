#!/usr/bin/env python3
"""tools/noverworld_rules.py -- the derivation, and the two bugs that shaped it.

The full sweep is 4096 graph walks and takes about a minute, so it is not run
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
# --- where the walk is allowed to begin --------------------------------------
#
# The first version seeded from everything Graph.starts() returns. That method
# answers a question about the *table* -- which entrances have a tile on the
# overworld -- and on a No-Overworld cartridge that is nine separate one-tile
# islands on an ocean stub. Seeding from all of them assumes the party begins
# standing on every town at once: 45 of 61 maps open empty-handed instead of 22,
# and 167 locations read as free where FFR says 21. Checked against FFR's own
# export, 166 of 218 comparable locations diverged, every one of them permissive.
#
# The mechanism is tested here without a cartridge, because the cartridge tests
# below skip when FF1_ROM is unset and a regression this expensive should not be
# protected only by a test that usually does not run.

import overworld_reach as owr        # noqa: E402

OCEAN, PAD, RIVER = 0, 1, 2
# A set bit refuses that vehicle (bank_0F.asm:1139). Ocean carries the ship
# alone; a pad is walkable and refuses the canoe, the ship and the airship
# alike, which is what every real pad does and why no vehicle leaves one.
FAKE_PROP = [0x0B, 0, 0x0E, 0, 0x0D, 0]


class FakeOverworld(owr.Overworld):
    def __init__(self, pads, rivers=()):
        self.rows = [[OCEAN] * owr.OW_DIM for _ in range(owr.OW_DIM)]
        self.prop = FAKE_PROP
        for x, y in pads:
            self.rows[y][x] = PAD
        for x, y in rivers:
            self.rows[y][x] = RIVER


class FakeGraph:
    def __init__(self, doors):
        self.doors = doors

    def starts(self):
        return [(d, d, (0, 0)) for d in self.doors]


def doors_from(pads, start, rivers=()):
    w = FakeOverworld(pads, rivers)
    g = FakeGraph({i + 1: [p] for i, p in enumerate(pads)})
    saved = nr.start_position
    nr.start_position = lambda raw: start
    try:
        return nr.start_doors(g, b"", w)
    finally:
        nr.start_position = saved


# Two isolated one-tile pads: the party can only be on the one it started on.
found, note = doors_from([(10, 10), (20, 20)], (10, 10))
ok([d for d, _, _ in found] == [1],
   "an isolated start pad seeds one door, not every door",
   str([d for d, _, _ in found]))
ok(note is None, "and needs no caveat")

# Adjacent pads are one landmass, so both doors are legitimately seeds.
found, note = doors_from([(10, 10), (11, 10)], (10, 10))
ok(sorted(d for d, _, _ in found) == [1, 2],
   "two pads sharing a landmass seed both doors",
   str(sorted(d for d, _, _ in found)))

# A canoe channel between two pads is a real route, and one the item sweep would
# have to account for -- so it is reported rather than silently taken.
found, note = doors_from([(10, 10), (10, 12)], (10, 10), rivers=[(10, 11)])
ok(sorted(d for d, _, _ in found) == [1, 2],
   "a canoe channel joins two pads")
ok(note is not None and "not item-independent" in note,
   "and says so, instead of quietly assuming the canoe is held", str(note))

# Nothing on the party's own landmass is not a shrug -- it means the start
# position or the overworld read is wrong, and every later number is nonsense.
try:
    doors_from([(20, 20)], (10, 10))
    ok(False, "a start with no door raises")
except SystemExit:
    ok(True, "a start with no door raises rather than returning nothing")


# --- the over-gating guard counts what the rule actually reaches -------------
#
# derive() refuses to emit a trade requirement for a node that would fan it to
# something else. That used to be an object-id count, which passes a node whose
# one trading NPC shares it with a chest -- the chest is then gated on the trade
# item with no warning at all. check_logic.load_derived_rules fans to sections,
# so sections are what the guard has to count. No node in the pack trips it
# today, which is exactly why it needs asserting against a tree built to.
import json as _j                                              # noqa: E402
import tempfile                                                # noqa: E402
import regen_maps as _rg                                       # noqa: E402

_pack = _rg.PACK
try:
    with tempfile.TemporaryDirectory() as tmp:
        os.mkdir(os.path.join(tmp, "locations"))
        with open(os.path.join(tmp, "locations", "overworld.json"), "w") as f:
            _j.dump([{"name": "Dwarf Cave", "children": [
                {"name": "Alone", "sections": [{"name": "Nerrick"}]},
                {"name": "Shared", "sections": [{"name": "Nerrick"},
                                                {"name": "Chest 42"}]},
                {"name": "Pointed At", "sections": [{"name": "Smith"},
                                                    {"ref": "elsewhere"}]},
                {"name": "Incentivised", "sections": [{"name": "Smith"}]}]}], f)
        with open(os.path.join(tmp, "locations", "incentives.json"), "w") as f:
            _j.dump([{"name": "Incentivised", "sections": [{"name": "Incentive"}]}], f)
        _rg.PACK = tmp
        seen = nr.fanned_sections("locations/overworld.json")
finally:
    _rg.PACK = _pack

ok(seen.get("Alone") == 1, "a node with one section is one section", str(seen))
ok(seen.get("Shared") == 2,
   "an NPC sharing its node with a chest counts two -- the object count is one")
ok(seen.get("Pointed At") == 1,
   "a `ref` section is not counted; it is counted where it is defined")
ok(seen.get("Incentivised") == 2,
   "and the incentive pin beside the tree counts, because check_logic fans there too")


rom_path = os.environ.get("FF1_ROM")
if not rom_path or not os.path.exists(rom_path):
    print("SKIP set FF1_ROM to a Final Fantasy cartridge to run the join")
else:
    with open(rom_path, "rb") as f:
        raw = f.read()

    # Whether this is an FFR cartridge at all, asked once and up here. Three of
    # the checks below are true only of one -- FFR places a Lefein object that
    # vanilla does not, and only FFR moves an NPC off its vanilla tile -- and
    # run.sh advertises the vanilla ROM as good enough for this file. It has to
    # stay good enough, or the suite fails under its own documented invocation.
    traded = e.talk_item_requirements(e.Rom(rom_path))
    ffr = traded is not None

    by_name, hosts = {}, {}
    placed = nr.placements(raw, "locations/NOverworld/overworld.json",
                           kinds=by_name, objects=hosts)
    ok(bool(placed), "placements resolved something", f"{len(placed)} locations")

    kinds = {}
    for names in by_name.values():
        for kind in names:
            kinds[kind] = kinds.get(kind, 0) + 1
    # Fourteen hosted_item codes in the tree name an object the cartridge
    # places, one node each. It was eight until extract_npcs was asked for the
    # other six ids (king, sara, sages, elfprince, robot, lefein), which is the
    # whole reason FFR pooled six locations that had no derived rule at all,
    # and thirteen nodes until the King and Sara were split off Coneria Castle
    # so each could carry a pin that meant only itself.
    #
    # Guessing the kind from the node name -- the first version of this -- found
    # none of them, because marker_tiles is keyed by node name and the object
    # table by item code.
    want_npcs = 14 if ffr else 13
    ok(kinds.get("NPC") == want_npcs,
       f"exactly the {want_npcs} NPC nodes join", str(kinds))
    ok(kinds.get("chest", 0) > 200, "and every dungeon chest does too",
       str(kinds.get("chest")))

    # The six that used to resolve to no tile at all. Named individually
    # because "fourteen" would still pass if one of them dropped out and an
    # unrelated node appeared. Lefein is the one that is FFR-only, for the same
    # reason the count above is: object $0F is not on a vanilla cartridge.
    named = ["Coneria Castle King", "Coneria Castle Sara", "Crescent Lake",
             "Elf Castle Elf Prince", "Waterfall Robot"]
    if ffr:
        named.append("Lefein")
    else:
        print("SKIP  a vanilla cartridge places no Lefein object ($0F)")
    for node in named:
        ok(node in placed and "NPC" in by_name.get(node, ()),
           f"{node} resolves to a tile", str(placed.get(node)))

    # And the join back to the object id, which is what lets a rule ask the
    # talk table whether that NPC wants something handed over first.
    ok(hosts.get("North West Castle Astos") == {0x07},
       "Astos's node knows it is object $07", str(hosts.get("North West Castle Astos")))
    ok(hosts.get("Dwarf Cave Nerrick") == {0x08},
       "Nerrick's node knows it is object $08", str(hosts.get("Dwarf Cave Nerrick")))

    # Positions come off this cartridge, not out of npc_positions.json. That
    # file is the vanilla table for the fourteen codes the pack pins, and it
    # reproduces those exactly; FFR moves NPCs, so deriving a seed's rules from
    # it answers about a different cartridge. Titan moves on an ordinary seed
    # and Nerrick moves on a No-Overworld one.
    import json as _json                                        # noqa: E402
    import extract_npcs                                         # noqa: E402
    import regen_maps                                           # noqa: E402
    cart = extract_npcs.extract(raw)
    with open(os.path.join(os.path.dirname(__file__), "..",
                           "npc_positions.json")) as f:
        vanilla = _json.load(f)

    def cells(places):
        return [(q["map_id"], q["tile_col"], q["tile_row"]) for q in places]

    def on_map(places):
        """The cells of `places` the party can actually stand on.

        placements() drops the rest, so an unfiltered extract is not what it
        built. The Ice Cave B1 fairy is the standing case -- a second copy of
        the Gaia object out in the black, which test_npc_pins asserts is the one
        placement outside the map -- and comparing against it unfiltered would
        fail on a correct answer.
        """
        return [c for c in cells(places)
                if regen_maps.stands_on_map(raw, *c, cache=off_map)]

    off_map = {}
    moved = sorted(code for code in cart
                   if code in vanilla and cells(cart[code]) != cells(vanilla[code]))
    if ffr:
        ok(bool(moved), "this cartridge moves at least one NPC off its vanilla tile",
           str(moved))
    else:
        ok(moved == [], "a vanilla cartridge matches npc_positions.json, which is "
           "where the file came from; nothing moves", str(moved))
    for node, ids in sorted(hosts.items()):
        if not any(extract_npcs.WANTED[oid] in moved for oid in ids):
            continue
        # Against every NPC the node hosts, not just the one that moved. No
        # node holds two objects today -- the King and Sara were split apart
        # for their pins -- but `placed` is a union either way, and a rule that
        # only ever compares one object's cells would fail on a correct result
        # the day two share a node again.
        want = sorted(c for oid in sorted(ids)
                      for c in on_map(cart.get(extract_npcs.WANTED[oid], [])))
        ok(sorted(placed[node]) == want,
           f"{node} is placed where this cartridge puts its NPCs",
           f"{sorted(placed[node])} vs {want}")

    # The trades themselves, which is the half the walk cannot see: it can put
    # the party next to Astos empty-handed, and that is not the same as getting
    # what he holds. These two were the only locations where the derived rules
    # and FFR's own logic disagreed.
    if traded is None:
        print("SKIP  FF1_ROM is not an FFR cartridge; the trades need one")
    else:
        ok(traded.get(0x07) == "crown", "Astos wants the Crown", str(traded.get(0x07)))
        ok(traded.get(0x08) == "tnt", "Nerrick wants the TNT", str(traded.get(0x08)))
        # Both are in the items the sweep varies, so the derived rule can
        # actually state them. So is the ruby, since the Titan gate landed. The
        # other trades this reader finds -- adamant, crystal, slab, herb -- are
        # outside that vocabulary and are emitted anyway, since they are real
        # requirements and the pack already uses those codes.
        for item in ("crown", "tnt"):
            ok(item in e.ITEM_NAMES, f"{item} is in the swept vocabulary")

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

# --- the same question asked of a real cartridge ------------------------------
if rom_path and os.path.exists(rom_path):
    with open(rom_path, "rb") as handle:
        raw2 = handle.read()
    rom2 = e.Rom.of(raw2, rom_path)
    if e.game_mode(rom2)[0] != e.GAME_MODE_NOVERWORLD:
        print("SKIP  FF1_ROM is not a No-Overworld cartridge; "
              "the start-pad numbers need one")
    else:
        g2 = e.Graph(rom2)
        seeds, _ = nr.start_doors(g2, raw2)
        ok(len(seeds) == 1, "a real No-Overworld cartridge seeds exactly one door",
           str([e.MAP_NAMES[m] for _, m, _ in seeds]))
        every = set(e.ITEM_NAMES)
        # The invariant docs/NOVERWORLD.md names: neither the gates nor the start
        # pad may move the all-items answer. Only the empty-handed reach changes.
        wide = nr.reachable_tiles(g2, every)
        narrow = nr.reachable_tiles(g2, every, seeds)
        ok(len(wide) == len(narrow),
           "with every item, seeding narrowly changes nothing",
           f"{len(wide)} maps either way")
        bare_wide = nr.reachable_tiles(g2, set())
        bare_narrow = nr.reachable_tiles(g2, set(), seeds)
        ok(len(bare_wide) > len(bare_narrow),
           "empty-handed, seeding from every door over-reaches",
           f"{len(bare_wide)} from all doors vs {len(bare_narrow)} from the start")


print("\n" + ("FAILURES: " + ", ".join(fails) if fails else "ALL PASS"))
sys.exit(1 if fails else 0)
