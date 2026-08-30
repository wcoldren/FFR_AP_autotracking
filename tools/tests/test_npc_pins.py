"""Every tracked NPC gets a pin, on its own tile, on a node that means only it.

The pins used to exist for three NPCs out of eight. The other five carried
`map_locations` on the `overworld` map alone -- the pin on the town or cave
they live in, not on the tab for the map itself -- and regen_maps only ever
rebuilt a node that already had a marker on a redrawn map, so a node with none
was never given one. Three checks, one for each way that can come back:

  * **every NPC the pack tracks resolves to a tile.** Eight of the fourteen the
    cartridge places have a location node; the other six -- Unne, Titan and the
    four fiends -- host no section anywhere, so there is nothing to pin. That
    split is asserted by name, because gaining or losing a node should be a
    deliberate edit and not a silent drift in a count.

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
    frame; a pin there would be a pin in the void. One of the fifteen
    placements fails that test and it is that one.

Set FF1_ROM to a cartridge; without one this skips.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import regen_maps as rg                                        # noqa: E402
import split_locations as sl                                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)

LOCATIONS = "locations/overworld.json"

# The eight NPCs with a section somewhere in the location tree, and the node
# each one's pin belongs to. Written out rather than counted so that moving a
# section between nodes has to come here and say so.
PINNED = {
    "astos": "North West Castle Astos",
    "bahamut": "Bahamut's Cave Bahamut",
    "bikke": "Pravoka",
    "fairy": "Gaia",
    "matoya": "Matoya's Cave Matoya",
    "nerrick": "Dwarf Cave Nerrick",
    "sarda": "Sarda's Cave",
    "smith": "Dwarf Cave Smith",
}

# The six the cartridge places that the pack has no box for. Not an oversight:
# none of them holds a shuffled item, the four fiends write no flag that could
# be autotracked at all, and `titan` as a code is already taken by ruby stage 2.
UNPINNED = ("kraken", "lich", "marilith", "tiamat", "titan", "unne")


OUTSIDE = {}


def cells_of(rom, places):
    """The (map, col, row) of `places` the party can actually reach."""
    return [(q["map_id"], q["tile_col"], q["tile_row"]) for q in places
            if rg.stands_on_map(rom, q["map_id"], q["tile_col"],
                                q["tile_row"], OUTSIDE)]


def nodes_of(doc):
    """{name: node} for every location in the tree, children included."""
    out = {}

    def walk(nodes):
        for n in nodes:
            if isinstance(n, dict):
                out[n["name"]] = n
                walk(n.get("children") or [])

    walk(doc)
    return out


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

    with open(os.path.join(TOOLS, "npc_positions.json")) as f:
        npcs = json.load(f)
    doc = sl.lenient(os.path.join(PACK, LOCATIONS))
    nodes = nodes_of(doc)
    tiles = rg.marker_tiles(rom, LOCATIONS)

    check("every NPC the cartridge places is accounted for",
          sorted(npcs), sorted(list(PINNED) + list(UNPINNED)))

    hosts = {sec.get("hosted_item"): name
             for name, node in nodes.items()
             for sec in node.get("sections") or []}
    for who, want in sorted(PINNED.items()):
        check(f"{who} hosts on {want}", hosts.get(who), want)
        check(f"{who}'s tile is the one the cartridge puts it on",
              sorted(tiles.get(want, ())), sorted(cells_of(rom, npcs[who])))

    for who in UNPINNED:
        check(f"{who} hosts nowhere", hosts.get(who), None)

    # The invariant that makes a pin mean one thing: the node an NPC pin lands
    # on holds that NPC and nothing else. One section, hosting that code.
    for who, name in sorted(PINNED.items()):
        secs = nodes[name].get("sections") or []
        check(f"{name} holds only {who}",
              [s.get("hosted_item") for s in secs], [who])

    # And the void placement is dropped, without dropping any other.
    ice = [(q["map_id"], q["tile_col"], q["tile_row"]) for q in npcs["fairy"]]
    outside = [c for c in ice if not rg.stands_on_map(rom, *c, cache=OUTSIDE)]
    check("the Ice Cave B1 fairy is the one placement outside the map",
          outside, [(15, 47, 30)])
    check("and it gets no pin", (15, 47, 30) in tiles["Gaia"], False)
    check("while the Gaia one does", (5, 49, 19) in tiles["Gaia"], True)
    check("no other tracked object stands outside its map",
          [(who, q["map_id"]) for who, places in sorted(npcs.items())
           for q in places
           if not rg.stands_on_map(rom, q["map_id"], q["tile_col"],
                                   q["tile_row"], OUTSIDE)],
          [("fairy", 15)])

    # place_locations then has to actually emit them, on the pixel that reads
    # back as the ROM's own tile. The rendered calibration is one offset per
    # axis per map, so inverting it is exact -- a pin that came out a tile
    # away, the way the shipped hand art draws Astos, shows up right here.
    cal = rg.rendered_calibration(rom, rg.crop_boxes(rom))
    out, _, _, bad, _ = rg.place_locations(cal, tiles, LOCATIONS)
    check("nothing is left unplaceable", bad, [])
    placed = nodes_of(out)
    for who, name in sorted(PINNED.items()):
        got = []
        for m in placed[name].get("map_locations") or []:
            if m["map"] not in rg.REDRAWN:
                continue
            e = cal[m["map"]]
            r = e["regions"][0]
            got.append((e["rom_map_id"],
                        (m["x"] - r["offset_x"]) // e["tile_px"],
                        (m["y"] - r["offset_y"]) // e["tile_px"]))
        check(f"{name}'s pin reads back as {who}'s tile",
              sorted(got), sorted(cells_of(rom, npcs[who])))

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
