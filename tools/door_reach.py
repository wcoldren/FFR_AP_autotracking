#!/usr/bin/env python3
"""What travel each overworld door needs, derived from the cartridge.

The pack's region rules are hand-written disjunctions of item sets -- "here is
every way to reach the marsh cave's door" -- transcribed against FFR's export
and graded by `check_logic`. This derives the same answer by walking the map,
and it exists for the one case the hand-written rules cannot serve: **on an
entrance-shuffled seed the rules stay attached to the wrong contents**, because
`Entrances` repoints a door without moving it. Where a door *is*, and what it
costs to stand on it, is invariant under that shuffle -- measured, not assumed:
`oracle_std` and `oracle_entrances` are the same seed three flags apart and
produce byte-identical output here for all 30 doors.

Two more properties worth knowing before using it:

  * **Map-edit flags come for free.** `openProgression`, `extendedOpen`,
    `melmondRiver`, `gaiaMountain` and the rest are applied at generation, so
    they are already in the stored map. The walk picks them up with no flag
    vocabulary at all -- on a seed with open progression the Marsh Cave door
    derives as free, and on `std497` as canoe-or-ship-or-airship.
  * **It under-reports a door reachable only through a dungeon.** Sarda's Cave
    and Titan's Tunnel West sit on a strip with no overworld route; the pack
    encodes that as `ruby` conjoined with travel to Titan's Tunnel East. This
    walks the overworld and nothing else, so it says "no route" where the pack
    says "ruby". Both are describing the same fact from different ends.

`--compare` grades it against the pack's own rules, reduced under the
cartridge's flags. 20 of 21 mapped doors agree exactly on every cartridge in the
corpus, the exception being Sarda's for the reason above.

Three modelling points, each of which was wrong in the first cut and each of
which moved the answer:

  * **The ship stays in its own sea.** `overworld_reach.reach` may board at any
    dock the party can walk to, which is safe for its question because it starts
    at sea with the ship. Starting on land it is not: the party docks, walks
    over the isthmus and re-boards on the far side, carrying the ship past the
    canal, and the `canal` term vanishes from every derived rule. FFR gates the
    same step on the ship's own area (`SanityCheckerV2.cs:428`,
    `area.Index == shipDockAreaIndex`).
  * **The airship lands, then the party walks.** Treating landable tiles as the
    answer rather than as seeds for the walk left eight doors unreachable.
  * **A door can be entered from a vehicle.** `overworld_reach` keeps only the
    tiles the party stands on, because collapsing the modes made `--at` answer
    True for open sea. The Waterfall is entered from the canoe, so asking only
    about land called it unreachable with every item in the game.

The bridge and the canal are gates rather than tiles, and their coordinates are
read off the cartridge rather than hardcoded: `0x3000 + UnsramIndex.BridgeX` and
`CanalX` (`Items.cs:373-377`, `OwLocationData.cs:31-32`), plus the iNES header.
FFR replaces the classification at those two cells (`SCOwMap.cs:119-120`) and
crosses them with `CheckLink` (`SanityCheckerV2.cs:299-306`): the bridge takes
the ship always and the party only with the bridge, the canal the reverse.

Usage:
    tools/door_reach.py ROM              # what each door costs
    tools/door_reach.py ROM --compare    # against the pack's own rules
"""

import argparse
import itertools
import json
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "ffr_flags"))

import entrance_graph                                          # noqa: E402
import overworld_pins as op                                    # noqa: E402
import overworld_reach as orch                                 # noqa: E402
from extract_chests import INES_HEADER                          # noqa: E402

FOOT, CANOE, SHIP, AIRSHIP = 0x01, 0x02, 0x04, 0x08

# The initial unsram block, which is where FFR stores where the ship, the
# airship, the bridge and the canal start. Two bytes each, x then y.
UNSRAM = INES_HEADER + 0x3000
SHIP_XY, AIRSHIP_XY, BRIDGE_XY, CANAL_XY = 1, 5, 9, 13

# What a rule may be written in terms of. Not an item list: `airship` here means
# "the party can fly", however the seed lets them -- the pack's rules spell the
# airship hike out as `floater+ship` in every alternative, which is the same
# capability reached another way and belongs in one place rather than in each
# rule.
CAPS = ("bridge", "canal", "canoe", "ship", "airship")

# The door the party starts at. Read as a name rather than a coordinate so a
# cartridge that moves it is followed rather than mis-walked.
START_DOOR = "ConeriaCastle1"


def coords(rom, index):
    return (rom[UNSRAM + index], rom[UNSRAM + index + 1])


def standable(w, rom, start, caps, bridge, canal):
    """Tiles the party can reach with this capability set, in any vehicle.

    Includes river and sea tiles, unlike `overworld_reach.reach`: a door is
    somewhere you arrive, and some of them are arrived at afloat.
    """
    have = set(caps)

    def foot_ok(x, y):
        if (x, y) == bridge:
            return "bridge" in have
        if (x, y) == canal:
            return True                      # walkable until it is blown
        return w.allows(x, y, FOOT)

    def ship_ok(x, y):
        if (x, y) == canal:
            return "canal" in have
        if (x, y) == bridge:
            return True                      # the ship passes under it
        return w.allows(x, y, SHIP)

    ship_at = coords(rom, SHIP_XY)

    # Where the ship itself can float, flooded from where it is moored. The
    # party may only put to sea at a dock touching this component; see the
    # module docstring for what happens without it.
    ship_sea = set()
    if "ship" in have:
        ship_sea.add(ship_at)
        sq = deque([ship_at])
        while sq:
            x, y = sq.popleft()
            for nx, ny in w.neighbours(x, y):
                if (nx, ny) not in ship_sea and ship_ok(nx, ny):
                    ship_sea.add((nx, ny))
                    sq.append((nx, ny))

    seen, q = set(), deque()

    def push(state):
        if state not in seen:
            seen.add(state)
            q.append(state)

    push((start[0], start[1], "land"))
    if "airship" in have:
        for y in range(orch.OW_DIM):
            for x in range(orch.OW_DIM):
                if w.allows(x, y, AIRSHIP) and w.allows(x, y, FOOT):
                    push((x, y, "land"))

    while q:
        x, y, mode = q.popleft()
        if mode == "land" and (x, y) == ship_at and ship_at in ship_sea:
            push((x, y, "sea"))
        for nx, ny in w.neighbours(x, y):
            if mode == "sea":
                if (nx, ny) in ship_sea:
                    push((nx, ny, "sea"))
                elif "canoe" in have and w.allows(nx, ny, CANOE):
                    push((nx, ny, "river"))
                elif foot_ok(nx, ny) and w.docks(nx, ny):
                    push((nx, ny, "land"))
            elif mode == "river":
                if w.allows(nx, ny, CANOE):
                    push((nx, ny, "river"))
                elif foot_ok(nx, ny):
                    push((nx, ny, "land"))
            else:
                if foot_ok(nx, ny):
                    push((nx, ny, "land"))
                elif "canoe" in have and w.allows(nx, ny, CANOE):
                    push((nx, ny, "river"))
                elif (nx, ny) in ship_sea and w.docks(x, y):
                    push((nx, ny, "sea"))
    return {(x, y) for x, y, _ in seen}


def minimal(sets):
    """The antichain of `sets`: drop any one a smaller one already implies."""
    out = []
    for s in sorted((frozenset(s) for s in sets), key=len):
        if not any(kept <= s for kept in out):
            out.append(s)
    return sorted(out, key=lambda s: (len(s), sorted(s)))


def show(sets):
    if not sets:
        return "(no route)"
    return " OR ".join("+".join(sorted(s)) if s else "(free)" for s in sets)


def door_rules(rom, graph):
    """{door name: [capability set]} -- what standing on each door costs."""
    w = orch.Overworld(rom)
    bridge = coords(rom, BRIDGE_XY)
    canal = coords(rom, CANAL_XY)
    doors = op.entrance_door_pins(graph.doors)
    start = doors.get(op.ENTRANCE_PREFIX + START_DOOR)
    if start is None:
        raise SystemExit(f"no {START_DOOR} door on this cartridge to start from")

    reach = {}
    for n in range(len(CAPS) + 1):
        for caps in itertools.combinations(CAPS, n):
            reach[caps] = standable(w, rom, start, caps, bridge, canal)

    out = {}
    for name, cell in doors.items():
        out[name[len(op.ENTRANCE_PREFIX):]] = minimal(
            [caps for caps, tiles in reach.items() if cell in tiles])
    return out


# ------------------------------------------------------------------ comparison

# Which region node in the pack's tree speaks for each door. Left out where the
# pack has no node for it, or where one node covers several doors -- the five
# Cardia islands share three nodes between them, and a town shares its node with
# its castle, so neither is a 1:1 claim this can grade.
DOOR_NODE = {
    "ConeriaCastle1": "Coneria Castle", "TempleOfFiends1": "Temple of Fiends",
    "DwarfCave": "Dwarf Cave", "NorthwestCastle": "North West Castle",
    "MatoyasCave": "Matoya's Cave", "ElflandCastle": "Elf Castle",
    "Pravoka": "Pravoka", "MarshCave1": "Marsh Cave", "Melmond": "Melmond",
    "EarthCave1": "Earth Cave", "TitansTunnelEast": "Titan's Tunnel Titan",
    "SardasCave": "Sarda's Cave", "CrescentLake": "Crescent Lake",
    "IceCave1": "Ice Cave", "GurguVolcano1": "Volcano",
    "CastleOrdeals1": "Ordeals", "Lefein": "Lefein", "Gaia": "Gaia",
    "MirageTower1": "Mirage Tower", "Waterfall": "Waterfall",
    "BahamutCave1": "Bahamut's Cave",
}

# Terms that are not travel: a key to the door, an item the check behind it is
# under, or a gate inside a dungeon. This answers "can the party stand on the
# tile", so these are set aside on both sides rather than counted as a
# disagreement.
NOT_TRAVEL = {"slab", "chime", "cube", "oxyale", "ruby", "rod", "tnt", "key",
              "$hasCanoe", "$hasFloater"}


def inherited_rules(parent, child):
    """The alternatives a child node actually runs under, parent folded in.

    PopTracker does not read a node's access_rules on their own. Alternatives
    are OR and inheritance is AND, so a child's list is crossed with its
    parent's -- every parent alternative concatenated with every child one --
    and a child with no rules of its own inherits the parent's outright
    (location.cpp:105-137). An empty result is the always-reachable case, which
    the caller's term loop reaches through the one empty alternative below.

    This function is why the region loop cannot just read `kid["access_rules"]`.
    No region in locations/overworld.json carries a rule today, so the two agree
    on the current file -- but the child-only reading turns a region rule into
    "(free)" for every door beneath it, and it does it in silence, which would
    either invent a DIFFER or hide one against the `differ <= 1` gate in
    tests/test_door_reach.py. Every other unknown this file meets raises.
    """
    if not child:
        return list(parent) or [""]
    if not parent:
        return list(child)
    return [f"{p},{c}" for p in parent for c in child]


def pack_rules(rom, codes):
    """{node name: [capability set]} -- the pack's rules under these flags."""
    # The $name calls the rules make, answered the way scripts/logic.lua does.
    # check_logic.LUA_RULES is the same table read off the flags; here the flag
    # has already become a code, so a guard is that code's absence.
    #
    # It has to be complete, which is what the raise below is for: a $name that
    # fell through landed in the term list and came out as a capability the
    # party had to *have*. $noSardasForest did exactly that and got away with it
    # -- Sarda's other alternative reduces to {airship}, so minimal() absorbed
    # the inflated set and the total came out right. The next one added to a
    # node with no such sibling would print a silent DIFFER and spend the one
    # disagreement `differ <= 1` allows on a bug in this file.
    pred = {"$standardWorld": True, "$noOverworld": False,
            "$noShipDrydock": "shipDrydock" not in codes,
            "$noSardasForest": "sardasForest" not in codes,
            "$gatewayRollUnknown": False}
    with open(os.path.join(PACK, "locations/overworld.json")) as fh:
        doc = json.load(fh)
    out = {}
    for region in doc:
        parent = region.get("access_rules") or []
        for kid in region.get("children") or []:
            alts = []
            for alt in inherited_rules(parent, kid.get("access_rules") or []):
                terms, dead = [], False
                for t in (x.strip() for x in alt.split(",") if x.strip()):
                    if t in pred:
                        dead = dead or pred[t] is False
                    elif t.startswith("$") and t not in NOT_TRAVEL:
                        raise SystemExit(
                            f"{kid['name']}: {t} is not a predicate this knows. "
                            "Add it to pred (if it guards an alternative) or to "
                            "NOT_TRAVEL (if it is an item), because falling "
                            "through would make it a travel capability.")
                    elif t in CAPS or t in NOT_TRAVEL or t == "floater":
                        terms.append(t)
                    elif t not in codes:
                        dead = True             # a flag this seed did not roll
                if not dead:
                    alts.append(terms)
            out[kid["name"]] = normalise(alts)
    return out


def normalise(alts):
    """Capability sets, with the non-travel terms and the airship hike folded."""
    out = []
    for a in alts:
        terms = frozenset(t for t in a if t not in NOT_TRAVEL)
        # The airship hike is how a seed lets you reach the airship early. As a
        # capability it *is* the airship, and folding it here is what keeps the
        # derivation's single `airship` term comparable.
        if "floater" in terms and "ship" in terms:
            terms = (terms - {"floater", "ship"}) | {"airship"}
        out.append(terms)
    return minimal(out)


def compare(rom, graph, derived):
    import check_logic
    import ffr_flags
    _, flags = ffr_flags.decode_rom(rom)
    codes = check_logic.flag_codes(flags)
    theirs = pack_rules(rom, codes)
    agree = differ = 0
    print(f"  {'door':21} {'derived':36} {'pack':36} verdict")
    for door in sorted(derived):
        node = DOOR_NODE.get(door)
        if node is None or node not in theirs:
            continue
        same = derived[door] == theirs[node]
        agree += same
        differ += not same
        print(f"  {door:21} {show(derived[door]):36} "
              f"{show(theirs[node]):36} {'agree' if same else 'DIFFER'}")
    print(f"\n  {agree} agree, {differ} differ, "
          f"{len(derived) - agree - differ} doors with no single node")
    return differ


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("rom")
    ap.add_argument("--compare", action="store_true",
                    help="grade against the pack's own region rules")
    args = ap.parse_args()

    with open(args.rom, "rb") as fh:
        rom = fh.read()
    if rom[:4] != b"NES\x1a":
        sys.exit("not an iNES ROM")
    graph = entrance_graph.Graph(entrance_graph.Rom.of(rom, args.rom))
    derived = door_rules(rom, graph)

    print(f"cartridge {os.path.basename(args.rom)}")
    print(f"bridge {coords(rom, BRIDGE_XY)}  canal {coords(rom, CANAL_XY)}  "
          f"ship {coords(rom, SHIP_XY)}\n")
    if args.compare:
        return 1 if compare(rom, graph, derived) else 0
    for door in sorted(derived):
        print(f"  {door:22} {show(derived[door])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
