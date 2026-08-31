"""Every tracked NPC gets a pin, on its own tile, on a node that means only it.

The pins used to exist for three NPCs out of eight. The other five carried
`map_locations` on the `overworld` map alone -- the pin on the town or cave
they live in, not on the tab for the map itself -- and regen_maps only ever
rebuilt a node that already had a marker on a redrawn map, so a node with none
was never given one. Three checks, one for each way that can come back:

  * **every NPC the pack tracks resolves to a tile.** Fourteen of the twenty
    the cartridge places have a location node; the other six -- Unne, Titan and
    the four fiends -- host no section anywhere, so there is nothing to pin.
    That split is asserted by name, because gaining or losing a node should be
    a deliberate edit and not a silent drift in a count.

  * **an NPC pin sits on a node that holds only that NPC.** A map marker's
    state is per *location*: TrackerView::CalculateLocationState ORs every
    section of the node, refs resolved. So a pin on Astos's tile, dropped on a
    node that also carries North West Castle's three chests, would sit on
    Astos and report the chests. Astos, Matoya and Bahamut were split out into
    their own child locations for exactly this reason -- the shape Dwarf Cave
    Smith and Nerrick already had -- and this is the check that keeps them
    there.

  * **a pin goes only where the party can stand.** The Ice Cave B1 fairy is a
    second copy of the Gaia object sitting in the black outside the cave, on a
    cell the edge flood reaches. The renderer draws it and the crop keeps it in
    frame; a pin there would be a pin in the void. Exactly one placement
    fails that test and it is that one.

Positions come off the cartridge handed to it, not out of npc_positions.json:
FFR moves people, and a pin derived from a vanilla snapshot lands beside the
sprite it marks rather than on it. That file survives as the vanilla anchor
tests/test_maps.lua reads, and its code list is still asserted here.

Run against both location trees, because regen_maps picks the tree by mode and
No-Overworld is the mode this work exists for. The two files are byte-identical
today, so the second pass costs a few seconds and asserts nothing new -- but
No-Overworld is what turns towns into rooms with chests, and "a node holds only
that NPC" is exactly the invariant that would break for Pravoka and Gaia when
it does. The pass that would catch it should not be the one nobody runs.

Set FF1_ROM to a cartridge; without one this skips.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import entrance_graph                                          # noqa: E402
import extract_npcs                                            # noqa: E402
import regen_maps as rg                                        # noqa: E402
import split_locations as sl                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)

LOCATIONS = ("locations/overworld.json", "locations/NOverworld/overworld.json")

# The fourteen NPCs with a section somewhere in the location tree, and the node
# each one's pin belongs to. Written out rather than counted so that moving a
# section between nodes has to come here and say so.
#
# King, Sara, the Elf Prince and the Robot each got a node of their own in the
# same change that gave them pins. They hosted on Coneria Castle, Elf Castle
# and Waterfall, which also carry those dungeons' chests, and a map marker's
# state is per *location* -- so the pin would have sat on the King and reported
# the castle. That is the shape Astos, Matoya and Bahamut were split into
# first, and the "holds only that NPC" check below is what keeps them there.
PINNED = {
    "astos": "North West Castle Astos",
    "bahamut": "Bahamut's Cave Bahamut",
    "bikke": "Pravoka",
    "elfprince": "Elf Castle Elf Prince",
    "fairy": "Gaia",
    "king": "Coneria Castle King",
    "lefein": "Lefein",
    "matoya": "Matoya's Cave Matoya",
    "nerrick": "Dwarf Cave Nerrick",
    "robot": "Waterfall Robot",
    "sages": "Crescent Lake",
    "sara": "Coneria Castle Sara",
    "sarda": "Sarda's Cave",
    "smith": "Dwarf Cave Smith",
}

# The six the cartridge places that the pack has no box for. Not an oversight:
# none of them holds a shuffled item, the four fiends write no flag that could
# be autotracked at all, and `titan` as a code is already taken by ruby stage 2.
UNPINNED = ("kraken", "lich", "marilith", "tiamat", "titan", "unne")

# What tools/npc_positions.json holds. Not the pin list any more -- the pins
# read the cartridge -- but tests/test_maps.lua has no cartridge, and reads
# that file for two things Lua cannot derive: the three shipped hand-art pins
# (check 4c) and the three map_calibration.json entries solved from a fiend's
# tile, on floors that hold no chest to calibrate from (check 4d). Asserted by
# name here so the snapshot cannot drift away from what it anchors.
VANILLA = ("astos", "bahamut", "bikke", "fairy", "kraken", "lich", "marilith",
           "matoya", "nerrick", "sarda", "smith", "tiamat", "titan", "unne")

# $0F is not placed on a vanilla cartridge at all -- FFR is what puts a Lefein
# object on a map -- so that one code is absent there and nowhere else.
VANILLA_ABSENT = "lefein"


OUTSIDE = {}


def cells_of(rom, places):
    """The (map, col, row) of `places` the party can actually reach."""
    return [(q["map_id"], q["tile_col"], q["tile_row"]) for q in places
            if rg.stands_on_map(rom, q["map_id"], q["tile_col"],
                                q["tile_row"], OUTSIDE)]


def nodes_of(doc):
    """{name: [node]} for every location in the tree, children included.

    A list rather than the node, so a duplicate name cannot quietly decide
    which node the assertions below run against. Duplicates are not
    hypothetical in this pack -- `I: Marsh Cave` is two nodes in
    locations/NOverworld/incentives.json -- and a "holds only Astos" check that
    silently tested whichever Astos node came last would be no check at all.
    """
    out = {}

    def walk(nodes):
        for n in nodes:
            if isinstance(n, dict):
                out.setdefault(n["name"], []).append(n)
                walk(n.get("children") or [])

    walk(doc)
    return out


def only(named, name):
    """The one node called `name`, or None if there is not exactly one."""
    got = named.get(name) or []
    return got[0] if len(got) == 1 else None


def main():
    path = os.environ.get("FF1_ROM")
    if not path or not os.path.exists(path):
        print("SKIP  set FF1_ROM to a Final Fantasy cartridge to run this")
        return 0
    with open(path, "rb") as f:
        rom = f.read()
    fails = []

    def check(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")
        print(f"{'ok  ' if got == want else 'FAIL'} {label}")

    npcs = extract_npcs.extract(rom)
    traded = entrance_graph.talk_item_requirements(
        entrance_graph.Rom.of(rom, path))

    codes = sorted(list(PINNED) + list(UNPINNED))
    if traded is None:                          # a stock image, not an FFR seed
        codes = [c for c in codes if c != VANILLA_ABSENT]
    check("every NPC the cartridge places is accounted for",
          sorted(npcs), codes)

    with open(os.path.join(TOOLS, "npc_positions.json")) as f:
        check("npc_positions.json still holds what test_maps.lua anchors on",
              sorted(json.load(f)), sorted(VANILLA))

    # The void placement is dropped, and no other is. Which tree is loaded does
    # not change that, so it is asked once.
    ice = [(q["map_id"], q["tile_col"], q["tile_row"]) for q in npcs["fairy"]]
    outside = [c for c in ice if not rg.stands_on_map(rom, *c, cache=OUTSIDE)]
    check("the Ice Cave B1 fairy is the one placement outside the map",
          outside, [(15, 47, 30)])
    check("no other tracked object stands outside its map",
          [(who, q["map_id"]) for who, places in sorted(npcs.items())
           for q in places
           if not rg.stands_on_map(rom, q["map_id"], q["tile_col"],
                                   q["tile_row"], OUTSIDE)],
          [("fairy", 15)])

    # One flood for both passes; the calibration is a property of the cartridge
    # and the crop, not of which location tree names the markers.
    npc_cells = {}
    for name, places in extract_npcs.extract(rom).items():
        for q in places:
            npc_cells.setdefault(q["map_id"], []).append(
                (f"npc {name}", q["tile_col"], q["tile_row"]))
    graph = entrance_graph.Graph(entrance_graph.Rom.of(rom, path))
    cal = rg.rendered_calibration(rom, rg.crops(rom, graph, npc_cells))

    for rel in LOCATIONS:
        tag = "nov" if "NOverworld" in rel else "std"
        print(f"\n-- {tag}: {rel}")
        doc = sl.lenient(os.path.join(PACK, rel))
        nodes = nodes_of(doc)
        dropped = []
        tiles = rg.marker_tiles(rom, rel, dropped)

        check(f"{tag}: no chest placement is dropped as backdrop",
              [d for d in dropped if d[1] == "chest"], [])
        check(f"{tag}: the fairy's void copy is the one placement dropped",
              dropped, [("Gaia", "NPC", 15, 47, 30)])

        # Every assertion below reaches for a node by name, so a duplicate name
        # would decide which node got tested. Rule it out first rather than
        # letting `only` turn it into a confusing None further down.
        check(f"{tag}: no two locations share a name",
              sorted(n for n, got in nodes.items() if len(got) > 1), [])

        # {code: [node names hosting it]}, so a code hosted twice fails the
        # comparison rather than resolving to whichever node came last.
        hosts = {}
        for name, got in nodes.items():
            for node in got:
                for sec in node.get("sections") or []:
                    hosts.setdefault(sec.get("hosted_item"), []).append(name)
        for who, want in sorted(PINNED.items()):
            check(f"{tag}: {who} hosts on {want}, and only there",
                  sorted(hosts.get(who, ())), [want])
            check(f"{tag}: {who}'s tile is the one the cartridge puts it on",
                  sorted(tiles.get(want, ())),
                  sorted(cells_of(rom, npcs.get(who, ()))))

        for who in UNPINNED:
            check(f"{tag}: {who} hosts nowhere", hosts.get(who), None)

        # The invariant that makes a pin mean one thing: the node an NPC pin
        # lands on holds that NPC and nothing else. One section, hosting that
        # code. This is the check No-Overworld is most likely to break, because
        # it is what turns Pravoka and Gaia from towns into rooms with chests.
        for who, name in sorted(PINNED.items()):
            node = only(nodes, name)
            check(f"{tag}: {name} holds only {who}",
                  [s.get("hosted_item")
                   for s in (node or {}).get("sections") or []], [who])

        check(f"{tag}: the fairy's void copy gets no pin",
              (15, 47, 30) in tiles["Gaia"], False)
        check(f"{tag}: while the Gaia one does",
              (5, 49, 19) in tiles["Gaia"], True)

        # place_locations then has to actually emit them, on the pixel that
        # reads back as the ROM's own tile. The rendered calibration is one
        # offset per axis per map, so inverting it is exact -- a pin that came
        # out a tile away, the way the shipped hand art draws Astos, shows up
        # right here.
        out, _, _, bad, _ = rg.place_locations(cal, tiles, rel)
        check(f"{tag}: nothing is left unplaceable", bad, [])
        placed = nodes_of(out)
        for who, name in sorted(PINNED.items()):
            got = []
            node = only(placed, name)
            for m in (node or {}).get("map_locations") or []:
                if m["map"] not in rg.REDRAWN:
                    continue
                e = cal[m["map"]]
                r = e["regions"][0]
                got.append((e["rom_map_id"],
                            (m["x"] - r["offset_x"]) // e["tile_px"],
                            (m["y"] - r["offset_y"]) // e["tile_px"]))
            check(f"{tag}: {name}'s pin reads back as {who}'s tile",
                  sorted(got), sorted(cells_of(rom, npcs.get(who, ()))))

    print()
    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
