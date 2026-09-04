#!/usr/bin/env python3
"""The entrance pins: on a door, named once, and switchable.

These nodes never reach the committed location trees. A door belongs to the
cartridge and the number of them is not fixed, so tools/regen_maps.py injects
them into its own output and the pack ships none -- which means
tests/test_maps.lua, the suite that owns "a marker names a real map, sits
inside its image, and hangs on a node with its own sections", cannot see a
single one of them. Those invariants are restated here, where they can still
fire.

What is checked:

  * every door pin stands on a tile the overworld property table calls a
    teleport tile, read here rather than taken from door_positions -- the same
    second-source rule test_overworld_pins.py follows
  * node names are unique across the tree, because tiles_by_name, mirror_of and
    restamp are all keyed on a bare node name and a collision is silent
  * every node carries its own single section, and nothing sets item_count --
    a section with item_count below 1 and no hosted item is skipped by
    CalculateLocationState, which leaves a marker that draws nothing and says
    nothing
  * every entrance marker is a trapezoid carrying exactly $showPin|entrance,
    and no other marker carries either
  * a place pin does not sit on a door: spread() is seeded with the door tiles,
    which is what makes the trapezoid the one you see
  * every floor link is a `norm` or an `exit` and never a `warp`. A town's whole
    outer border is warp-to-overworld, so the warp count is asserted outright:
    the filter going missing is not a pin or two out of place, it is tens of
    thousands of them
  * a link on a tile that also holds a drawn sprite stays a trapezoid

Set FF1_ROM to a cartridge; without one the cartridge half skips.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import entrance_graph  # noqa: E402
import overworld_pins as op  # noqa: E402
import pin_visibility  # noqa: E402
import regen_maps  # noqa: E402
import render_maps  # noqa: E402
import sprites  # noqa: E402

fail = 0


def check(label, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'ok  ' if ok else 'FAIL'} {label:<54} {got}")
    if not ok:
        print(f"     wanted {want}")


def markers(nodes, out=None):
    """[(node name, marker)] for every marker in a tree."""
    out = [] if out is None else out
    for node in nodes:
        if not isinstance(node, dict):
            continue
        for marker in node.get("map_locations") or []:
            out.append((node.get("name"), marker))
        markers(node.get("children") or [], out)
    return out


def teleport_tiles(reader):
    """{(x, y)} -- every overworld tile the game itself treats as a door.

    Read from the property table rather than from door_positions, so this is a
    second source and not the same answer twice. bank_0F.asm:321 tests byte 1
    bit 7 of the overworld's tileset properties; note byte *1*, the overworld's
    layout is not the standard map's.
    """
    props = reader.data[entrance_graph.OW_TILESET_PROP:
                        entrance_graph.OW_TILESET_PROP
                        + entrance_graph.OW_TILES * 2]
    doors = {t for t in range(entrance_graph.OW_TILES)
             if props[t * 2 + 1] & 0x80}
    grid = entrance_graph.decompress_ow(reader.data)
    return {(x, y)
            for y in range(entrance_graph.OW_DIM)
            for x in range(entrance_graph.OW_DIM)
            if grid[y][x] in doors}


def main():
    # Structure first, so the shape of a node is checked with or without a
    # cartridge and the failure names the field rather than the seed.
    print("-- the node a door is injected as")
    group = op.entrance_group({"Entrance: Coneria": (10, 20),
                               "Entrance: Pravoka": (30, 40)})
    check("the group is the one pin_visibility reads",
          group["name"], pin_visibility.ENTRANCES_GROUP)
    kid = group["children"][0]
    check("a door carries its own sections", len(kid["sections"]), 1)
    check("  and does not set item_count", "item_count" in kid["sections"][0],
          False)
    check("  and is a trapezoid", kid["map_locations"][0]["shape"], "trapezoid")

    # Both directions, as the stamper's own suite does it: under the group the
    # rule appears, and the same node outside it gets nothing. Keyed on the
    # group rather than on the shape, so the shape never becomes the source of
    # truth for what a pin means.
    pin_visibility.stamp([group])
    check("stamping gives every door the rule",
          sorted({tuple(m.get("restrict_visibility_rules") or ())
                  for _, m in markers([group])}),
          [(pin_visibility.ENTRANCE_RULE,)])
    renamed = op.entrance_group({"Entrance: Coneria": (10, 20)})
    renamed["name"] = "Somewhere Else"
    pin_visibility.stamp([renamed])
    check("  and a group by another name none",
          [m.get("restrict_visibility_rules") for _, m in markers([renamed])],
          [None])

    # The seeding, which is the whole collision answer. Without it the place pin
    # and the trapezoid land on one tile and which you see depends on tree
    # order.
    door = {(10, 40): "Entrance: Coneria"}
    check("a place pin moves off a seeded door",
          op.spread({"Coneria": (10, 40)}, 6, taken=door)["Coneria"], (10, 34))
    check("  and stays put where no door is seeded",
          op.spread({"Coneria": (10, 40)}, 6)["Coneria"], (10, 40))

    path = os.environ.get("FF1_ROM")
    if not path or not os.path.exists(path):
        print("SKIP  set FF1_ROM to a Final Fantasy cartridge to run this")
        return 0
    rom = open(path, "rb").read()
    reader = entrance_graph.Rom(path)
    doors = op.entrance_door_pins(reader)
    print(f"-- {os.path.basename(path)}: {len(doors)} doors carry a tile")

    on_a_door = teleport_tiles(reader)
    check("every door pin stands on a teleport tile",
          sorted(n for n, cell in doors.items() if cell not in on_a_door), [])
    check("every name carries the prefix",
          sorted(n for n in doors if not n.startswith(op.ENTRANCE_PREFIX)), [])
    check("names are unique", len(set(doors)), len(doors))
    check("  and each names a door the cartridge has",
          sorted(n for n in doors
                 if n[len(op.ENTRANCE_PREFIX):]
                 not in entrance_graph.DOOR_NAMES), [])

    # The floor links. The filter is the whole thing here, so it is asserted
    # from the other side as well: what the kinds are, and what including the
    # wrong one would cost.
    graph = entrance_graph.Graph(reader)
    links = regen_maps.entrance_tiles(graph)
    kinds = {}
    warps = 0
    for map_id in render_maps.MAP_FILES:
        for col, row, kind, _ in graph.teleports(map_id):
            kinds[kind] = kinds.get(kind, 0) + 1
            if kind == entrance_graph.TP_TELE_WARP:
                warps += 1
    print(f"-- {len(links)} floor links against {warps} warp tiles")
    check("every link is a norm or an exit",
          sorted({k for k in kinds if k in regen_maps.FLOOR_LINK_KINDS}),
          sorted(regen_maps.FLOOR_LINK_KINDS))
    check("  and the warp tiles are all left out",
          len(links), kinds.get(entrance_graph.TP_TELE_NORM, 0)
          + kinds.get(entrance_graph.TP_TELE_EXIT, 0))
    # Not a round number and not meant to be: it is five figures, and a filter
    # quietly dropped would put every one of them on the board.
    check("  which is worth doing", warps > 10000, True)

    check("link names are unique", len(set(links)), len(links))
    check("  and none names its destination",
          sorted(n for n, (m, c, r) in links.items()
                 if not n.endswith(f"{c},{r}")), [])
    check("  and every name is namespaced with the doors",
          sorted(n for n in links if not n.startswith(op.ENTRANCE_PREFIX)), [])
    check("no link name collides with a door name",
          sorted(set(links) & set(doors)), [])

    # Every link is on a tile the map's own teleport table names -- read back
    # from the graph rather than from entrance_tiles' own output.
    astray = []
    for name, (map_id, col, row) in links.items():
        table = {(x, y) for x, y, k, _ in graph.teleports(map_id)
                 if k in regen_maps.FLOOR_LINK_KINDS}
        if (col, row) not in table:
            astray.append(name)
    check("every link sits on a tile its map's table names", sorted(astray), [])

    # And the node the regen builds from one, which test_maps.lua cannot see.
    cal = regen_maps.rendered_calibration(rom, regen_maps.crops(rom, graph))
    by_rom = regen_maps.maps_by_rom_id(cal)
    sprite_cells = {m: sprites.drawn_cells(rom, graph, m)
                    for m in render_maps.MAP_FILES}
    kids, lost, shaded = regen_maps.entrance_children(by_rom, links,
                                                      sprite_cells)
    print(f"-- {len(kids)} placed, {len(lost)} unplaceable, "
          f"{len(shaded)} on a drawn sprite")
    check("every link is placeable on drawn art", sorted(lost), [])
    check("every node carries one section",
          sorted({len(k["sections"]) for k in kids}), [1])
    check("  and none sets item_count",
          sorted({("item_count" in k["sections"][0]) for k in kids}), [False])
    check("every marker is a trapezoid",
          sorted({k["map_locations"][0].get("shape") for k in kids}),
          ["trapezoid"])
    # The collision rule, stated where it can fail: a link on a sprite tile
    # would otherwise come back a diamond and start meaning something else.
    check("  including the ones standing on a sprite",
          sorted({k["map_locations"][0].get("shape") for k in kids
                  if (k["name"], k["map_locations"][0]["map"]) in set(shaded)})
          or ["trapezoid"], ["trapezoid"])
    check("every marker names a drawn map",
          sorted({k["map_locations"][0]["map"] for k in kids}
                 - set(render_maps.MAP_FILES.values())), [])

    # The whole group, stamped the way the regen stamps it.
    group = op.entrance_group(doors)
    group["children"] += kids
    pin_visibility.stamp([group])
    rules = {tuple(m.get("restrict_visibility_rules") or ())
             for _, m in markers([group])}
    check("doors and links carry the one rule between them",
          sorted(rules), [(pin_visibility.ENTRANCE_RULE,)])
    check("  and the group holds both halves",
          len(group["children"]), len(doors) + len(kids))

    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
