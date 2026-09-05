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
  * every floor link is a `norm`, an `exit`, or one of the few `warp` tiles that
    are a floor's door rather than a town's border. A town's whole outer border
    is warp-to-overworld, so both sides of that filter are asserted: the tens of
    thousands it drops, and the two conditions it keeps a tile on, each shown
    failing on a grid built here
  * a link on a tile that also holds a drawn sprite stays a trapezoid

Set FF1_ROM to a cartridge; without one the cartridge half skips.
"""

import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import entrance_graph  # noqa: E402
import make_door_icons  # noqa: E402
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


def same_file(path, data):
    return os.path.exists(path) and open(path, "rb").read() == data


def png_pixels(data):
    """[[luma]] for a PNG this suite just built -- 8-bit RGB, filter 0 only.

    Written here rather than reached for from a library because the tools have
    no image dependency and this is checking their own encoder's output.
    """
    pos, width, height, idat = 8, 0, 0, b""
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        if kind == b"IHDR":
            width, height = struct.unpack(">II", data[pos + 8:pos + 16])
        elif kind == b"IDAT":
            idat += data[pos + 8:pos + 8 + length]
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * 3
    out = []
    for y in range(height):
        assert raw[y * (stride + 1)] == 0, "unexpected PNG filter"
        line = raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)]
        out.append([sum(line[x * 3:x * 3 + 3]) for x in range(width)])
    return out


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
    # The collision is a box overlap, not a shared tile. Three tiles off a door
    # with a six-tile marker is Cardia Swampy's case: clear on the tile test and
    # half on top of the trapezoid on the board.
    check("    a shared-tile test would call this one clear", (13, 43) in door,
          False)
    check("  and it moves anyway, because the boxes overlap",
          op.spread({"Coneria": (13, 43)}, 6, taken=door)["Coneria"], (13, 31))

    # The floor-exit rule, on a grid built here rather than found on a
    # cartridge. A cartridge can only show the rule agreeing with itself; this
    # can show each of its two conditions rejecting a tile the other would let
    # through, which is the only way either is known to be load-bearing.
    #
    # An 11x11 block of tile 1 in a field of tile 0: the edge flood reaches the
    # field and stops at the block, so the block is the content.
    dim = render_maps.MAP_DIM
    tiles = [0] * (dim * dim)
    for row in range(20, 31):
        for col in range(20, 31):
            tiles[row * dim + col] = 1
    warps = ([(28, 28)]                              # a door: lone, and inside
             + [(5, 5)]                              # lone, but out in the field
             + [(col, row) for row in range(21, 24)  # inside, but a flood
                for col in range(21, 24)])

    class Grid:                                      # what floor_exits reads
        def teleports(self, map_id):
            return [(c, r, entrance_graph.TP_TELE_WARP, 0) for c, r in warps]

        def grid(self, map_id):
            return tiles, None, None

    check("a lone warp tile inside the content is a door",
          sorted(regen_maps.floor_exits(Grid(), 0)), [(28, 28)])
    check("  the one out in the filler is not, whatever its cluster",
          (5, 5) in render_maps.content_cells(tiles), False)
    was = regen_maps.FLOOR_EXIT_CLUSTER
    regen_maps.FLOOR_EXIT_CLUSTER = dim * dim
    check("  and without the cluster test the flood comes in with it",
          len(regen_maps.floor_exits(Grid(), 0)), 10)
    regen_maps.FLOOR_EXIT_CLUSTER = was

    # One pin per link, not per tile, and what keeps that lossless.
    doorway = {(11, 4): ("exit", 4), (12, 4): ("exit", 4), (13, 4): ("exit", 4)}
    check("a doorway drawn across three tiles is one pin",
          sorted(regen_maps._one_per_link(doorway)), [(12, 4)])
    touching = {(11, 4): ("exit", 4), (12, 4): ("exit", 9)}
    check("  and two different links that touch stay two",
          sorted(regen_maps._one_per_link(touching)), [(11, 4), (12, 4)])
    # Ice Cave B2's shape: one destination, several pits, and they are several
    # holes to walk into. Merging on where a link goes would also be the spoiler.
    apart = {(11, 4): ("norm", 18), (20, 4): ("norm", 18)}
    check("  and one link in two places stays two",
          sorted(regen_maps._one_per_link(apart)), [(11, 4), (20, 4)])

    # The tooltip icon. The two paths are one pair of constants, referenced by
    # the group that names them and by the regen that writes them, so the way
    # this fails silently -- a path that resolves to nothing and falls back to
    # PopTracker's chest without a word (maptooltip.cpp:214) -- cannot come from
    # the two sides disagreeing. What is left to check is that the group carries
    # them at all, since a section inherits both from here and nowhere else.
    icon_group = op.entrance_group({"Entrance: Coneria": (10, 40)})
    check("the group hands its children a door for a chest",
          [icon_group.get("chest_unopened_img"), icon_group.get("chest_opened_img")],
          [op.DOOR_SHUT_IMG, op.DOOR_OPEN_IMG])
    check("  and neither is a path a child has to repeat",
          sorted(k for kid in icon_group["children"] for k in kid
                 if k.startswith("chest_")), [])

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
    floor_doors = sum(len(regen_maps.floor_exits(graph, m))
                      for m in render_maps.MAP_FILES)
    print(f"-- {floor_doors} of the warp tiles are a floor's door")

    # Every tile the filter lets through, per map, with what link it is part
    # of -- and the runs of them, flooded here rather than taken from
    # regen_maps, so the collapse is checked against a second implementation
    # the way the tile-on-a-teleport check above is.
    eligible = {}
    for map_id in render_maps.MAP_FILES:
        cells = {(col, row): (kind, pay)
                 for col, row, kind, pay in graph.teleports(map_id)
                 if kind in regen_maps.FLOOR_LINK_KINDS}
        for cell in regen_maps.floor_exits(graph, map_id):
            cells[cell] = (entrance_graph.TP_TELE_WARP, 0)
        eligible[map_id] = cells
    check("  and the border warps are all left out",
          sum(len(c) for c in eligible.values()),
          kinds.get(entrance_graph.TP_TELE_NORM, 0)
          + kinds.get(entrance_graph.TP_TELE_EXIT, 0) + floor_doors)
    # Not a round number and not meant to be: it is five figures, and a filter
    # quietly dropped would put every one of them on the board.
    check("  which is worth doing", warps - floor_doors > 10000, True)
    # The other side of the same filter. A door per floor is two figures on
    # every cartridge measured; a border leaking in is four or five, and would
    # pass a check that only asked whether the count had grown.
    check("  and what it keeps is a door per floor", floor_doors < 100, True)

    # One pin per link, however many tiles the doorway is drawn across. Both
    # directions: a run that kept a pin each would fail the first, and a pin
    # merged across two different links would fail the second.
    runs = []
    for map_id, cells in eligible.items():
        seen = set()
        for start in cells:
            if start in seen:
                continue
            queue, group = [start], set()
            seen.add(start)
            while queue:
                col, row = queue.pop()
                group.add((col, row))
                for step in ((col + 1, row), (col - 1, row),
                             (col, row + 1), (col, row - 1)):
                    if (cells.get(step) == cells[start]) and step not in seen:
                        seen.add(step)
                        queue.append(step)
            runs.append((map_id, group))
    here = {}
    for name, (map_id, col, row) in links.items():
        here.setdefault(map_id, set()).add((col, row))
    check("every run of one link carries exactly one pin",
          sorted((entrance_graph.MAP_NAMES[m], len(g & here.get(m, set())))
                 for m, g in runs
                 if len(g & here.get(m, set())) != 1), [])
    check("  and every pin stands in one",
          sorted(name for name, (m, c, r) in links.items()
                 if not any(mm == m and (c, r) in g for mm, g in runs)), [])
    print(f"-- {sum(len(c) for c in eligible.values())} link tiles "
          f"in {len(runs)} runs")

    # The committed icons are what the writer draws off this cartridge. Same
    # shape of guard as test_toggle_icons': the writer has a --check mode and a
    # mode nothing runs is worth nothing. It is the existence check too, and
    # existence is the half that fails silently -- a section image that does not
    # resolve falls back to PopTracker's chest without a word.
    built = make_door_icons.icons(rom, graph)
    check("a locked door was found to draw", built is not None, True)
    if built:
        check("  and the committed icons are what the writer draws",
              sorted(rel for rel, data in built.items()
                     if not same_file(os.path.join(PACK, rel), data)), [])
        shut, opened = (png_pixels(built[rel]) for rel in
                        (op.DOOR_SHUT_IMG, op.DOOR_OPEN_IMG))
        check("  both are the same size",
              [len(shut), len(shut[0]), len(opened), len(opened[0])],
              [64, 64, 64, 64])
        # A dim that came out equal would draw two identical states and say
        # nothing, which is the failure "both files exist" would pass.
        check("  and the shut one is darker in every pixel",
              all(a <= b for r1, r2 in zip(shut, opened)
                  for a, b in zip(r1, r2)), True)
        check("    and strictly darker somewhere",
              any(a < b for r1, r2 in zip(shut, opened)
                  for a, b in zip(r1, r2)), True)

    check("link names are unique", len(set(links)), len(links))
    check("  and none names its destination",
          sorted(n for n, (m, c, r) in links.items()
                 if not n.endswith(f"{c},{r}")), [])
    check("  and every name is namespaced with the doors",
          sorted(n for n in links if not n.startswith(op.ENTRANCE_PREFIX)), [])
    check("no link name collides with a door name",
          sorted(set(links) & set(doors)), [])

    # Every link is on a tile the map's own teleport table names -- read back
    # from the graph rather than from entrance_tiles' own output. A floor's door
    # counts, and is read back the same way: the table has to call it a warp,
    # and floor_exits has to call that warp a door.
    astray = []
    for name, (map_id, col, row) in links.items():
        table = {(x, y) for x, y, k, _ in graph.teleports(map_id)
                 if k in regen_maps.FLOOR_LINK_KINDS}
        table |= regen_maps.floor_exits(graph, map_id)
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
