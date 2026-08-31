#!/usr/bin/env python3
"""Where each overworld pin stands, read off the cartridge.

The pack's 55 overworld and incentive-sheet pins are pixels on DarkmoonEX's
drawing, placed by eye. That is fine for a drawing and no use at all on a
rendered map, where tile (col, row) is pixel (16col, 16row) and the pin has to
land on the tile the cartridge actually put the place on.

It is also less accurate than it looks. Fitting the drawn pins against the tiles
the cartridge names gives residuals up to eleven tiles -- Waterfall is the
worst, Mirage Tower and Ordeals next -- so the drawing is not a scaled map and
there is no transform to invert. Every pin here is derived instead.

**One rule does almost all of it: a pin stands on the door you go through to
reach the thing it names.** For each pin the pack draws, take every chest under
it, ask which maps those chests are on, and ask entrance_graph for the door that
reaches them. That handles the ordinary case (Ice Cave's pin on Ice Cave's
door), the five-doors-one-map case (Cardia is one map with five entrances; the
door whose arrival tile is nearest the pack's own chests for that name is the
one), and the no-door case (Sky Palace, Sea Shrine and ToFR have no overworld
tile at all, so the route walk hands back the door you enter the chain from --
Mirage Tower, Onrac and the Temple of Fiends). It follows a shuffled seed for
the same reason: nothing here is a coordinate, it is a question about topology.

Two pins name no chest and are read from the tile property table instead, which
is the game's own test rather than a tile id FFR is free to move:

  Constants.inc:336   OWTP_SPEC_CARAVAN -- `I: Shop Item`. The caravan is the
                      only thing on the overworld that is a shop rather than a
                      place, and the one annotation the hand-drawn map carries.
  Constants.inc:337   OWTP_SPEC_FLOATER -- `Ryukahn Desert`, the 49 tiles where
                      the floater digs up the airship. The pin goes on the
                      middle of them.

Anything that resolves to nothing is reported, never guessed: a pin quietly
moved to the wrong continent is worse than one that is missing and said so.

**The staircase half of this wants an FFR cartridge.** entrance_graph routes
through the expanded teleport tables FFR's ExpandNormalTeleporters writes into
bank $0F, and a stock Final Fantasy image has nothing there -- so on one, the
six pins whose place is behind a staircase rather than on a door come back
unplaced. That is the intended domain, not a gap: this runs from regen_maps,
which is drawing a seed.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import entrance_graph  # noqa: E402
import render_overworld  # noqa: E402

OWTP_SPEC_FLOATER = 0xC0

# The two pins with no chest under them anywhere. Keyed by the pack's name,
# without the incentive sheet's "I: " prefix, which is stripped before lookup.
BY_PROPERTY = {
    "Shop Item": "caravan",
    "Ryukahn Desert": "floater",
}

# Maps that are not a place you walk into from the overworld, so no chest under
# these pins is ever on a map with a door. The route walk answers them anyway;
# this is only here to say that it is expected to.
NO_DOOR_OF_THEIR_OWN = ("ToFR", "Sky Palace", "Sea Shrine")


def pin_names(doc, maps=("overworld", "incentives")):
    """[(name, [descendant names])] for every node carrying an overworld pin."""
    out = []

    def names_under(node, acc):
        if isinstance(node, list):
            for n in node:
                names_under(n, acc)
            return acc
        if not isinstance(node, dict):
            return acc
        if node.get("name"):
            acc.append(node["name"])
        for key in ("children", "sections"):
            names_under(node.get(key) or [], acc)
        return acc

    def walk(node):
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if not isinstance(node, dict):
            return
        if any(ml.get("map") in maps for ml in node.get("map_locations") or []):
            out.append((node.get("name"), names_under(node, [])))
        for key in ("children", "sections"):
            walk(node.get(key) or [])

    walk(doc)
    return out


def floater(rom):
    """The middle of the desert the floater digs the airship out of."""
    cells = render_overworld.cells_where(
        rom, lambda p0, p1: p0 & render_overworld.OWTP_SPEC_MASK == OWTP_SPEC_FLOATER)
    flat = sorted(c for cs in cells.values() for c in cs)
    if not flat:
        return None
    return (sum(c[0] for c in flat) // len(flat),
            sum(c[1] for c in flat) // len(flat))


def door_cells(reader):
    """{door id: (x, y)} -- a door's first overworld tile.

    Towns are a blob of several tiles and caves are one; the first is the
    north-west corner of the blob, which is where a single pin belongs.
    """
    return {d: cells[0] for d, cells in
            entrance_graph.door_positions(reader).items() if cells}


# Every key item, for the route walk. The question is where a door *is*, not
# whether the player can get through it yet, so nothing here should be gated:
# a Sky Palace pin that only appears once you hold the cube is a pin that is
# missing when you most want to look at it.
EVERYTHING = frozenset(entrance_graph.ITEM_NAMES)


def reaching_doors(graph, target_maps):
    """[(door, arrival)] for the doors that reach any of `target_maps`.

    Direct first: a door whose own destination is one of them. Only when none
    is does this fall back to Graph.route, which walks the staircases and is
    the expensive question -- and the one that answers Sky Palace, Sea Shrine
    and ToFR, none of which has an overworld tile of its own.
    """
    direct = [(door, arrive) for door, dest, arrive in graph.starts()
              if dest in target_maps]
    if direct:
        return direct
    out = []
    for target in sorted(target_maps):
        best = graph.route(target, EVERYTHING)
        if best is None:
            continue
        door, _, m0, arrive0 = best
        out.append((door, arrive0))
    return out


def mirror_of(doc, placed, maps=("overworld", "incentives")):
    """{any name in the tree: where its nearest pinned ancestor stands}.

    The incentive sheet does not repeat the overworld's shape exactly. Most of
    its pins are `I: ` plus an overworld pin's name, but `I: Cardia Incentive`
    names a *chest* -- a leaf under Cardia Forest -- and there is no pin of that
    name to mirror. Carrying every name down from the pin above it answers both
    kinds with one rule, and the deepest pin wins so a name under two of them
    takes the nearer.
    """
    out = {}

    def walk(node, above):
        if isinstance(node, list):
            for n in node:
                walk(n, above)
            return
        if not isinstance(node, dict):
            return
        name = node.get("name")
        here = above
        if name and any(ml.get("map") in maps
                        for ml in node.get("map_locations") or []):
            here = placed.get(name, above)
        if name and here is not None:
            out[name] = here
        for key in ("children", "sections"):
            walk(node.get(key) or [], here)

    walk(doc, None)
    return out


def _squashed(text):
    return "".join(c for c in text.lower() if c.isalnum())


def named_map(name):
    """The map a pin's own name is the name of, or None.

    The last resort, and it earns its place on exactly one pin: Melmond has no
    chest anywhere under it -- its checks are a shop and an NPC -- so there is
    nothing to ask the topology about. MAP_NAMES is entrance_graph's canonical
    list and `Melmond` is map 3 in it. Matching on a squashed name rather than
    on a table written out here means a town added later needs no edit.
    """
    want = _squashed(name)
    for map_id, canonical in enumerate(entrance_graph.MAP_NAMES):
        if _squashed(canonical) == want:
            return map_id
    return None


def resolve(rom, reader, graph, doc, tiles_by_name, mirror=None, report=None):
    """-> (placed, unplaced, anchors), all keyed by the pack's pin name.

    `placed` is where the pin goes and `anchors` where it resolved to before
    any nudge. The two differ only where several pins resolved to one tile, and
    on a No-Overworld cartridge that is most of them: nine stub doors in a
    cluster carry all 27 pins, six of them on one door. Keeping the anchor is
    what lets a caller say so, and what lets a test check the resolution rather
    than the tidying.

    `tiles_by_name` is regen_maps.marker_tiles' answer -- {location name:
    [(map_id, col, row)]} -- and is passed in rather than recomputed so this
    stays a question about topology and the cartridge reading stays in one
    place. `mirror` is an earlier call's answer: the incentive sheet is the
    overworld tree name for name with `I: ` on the front, and an incentive pin
    belongs wherever the place it is an incentive for belongs. That is not a
    shortcut -- the two trees are built to agree -- and it is what puts a pin
    on the twelve incentive slots that hold no chest of their own.
    """
    doors = door_cells(reader)
    car = render_overworld.caravan(rom)
    props = {"caravan": car[0] if car else None, "floater": floater(rom)}
    placed, unplaced, anchors = {}, [], {}
    taken = {}

    def door_for(target, chests):
        candidates = [(d, a) for d, a in reaching_doors(graph, target)
                      if d in doors]
        if not candidates:
            return None
        if len(candidates) > 1 and chests:
            # One map, several doors -- Cardia. The door whose arrival tile is
            # nearest this pin's own chests is the one it names.
            def nearest(item):
                _, (ax, ay) = item
                return min(abs(ax - c) + abs(ay - r) for _, c, r in chests)

            candidates.sort(key=nearest)
        return candidates[0][0]

    for name, under in pin_names(doc):
        bare = name[3:] if name.startswith("I: ") else name
        where = why = None

        if bare in BY_PROPERTY:
            where = props[BY_PROPERTY[bare]]
            why = f"this cartridge has no {BY_PROPERTY[bare]}"
        elif mirror and bare in mirror:
            where = mirror[bare]
        else:
            chests = [t for n in under for t in tiles_by_name.get(n, ())]
            target = {map_id for map_id, _, _ in chests}
            if not target:
                own = named_map(bare)
                target = {own} if own is not None else set()
            if not target:
                why = "no chest under it and no map of its own name"
            else:
                door = door_for(target, chests)
                if door is None:
                    why = f"no door reaches map(s) {sorted(target)}"
                else:
                    where = doors[door]
                    if report is not None and bare in NO_DOOR_OF_THEIR_OWN:
                        report.append((name, door, where))

        if where is None:
            unplaced.append((name, why or "nothing resolved it"))
            continue
        anchors[name] = where
        # Two pins on one tile is one pin: ToFR shares the Temple of Fiends'
        # door and Sky Palace shares Mirage Tower's, because that is the door
        # you go through. Nudging the second one north keeps both visible, and
        # a tile is the smallest move that can do it.
        while where in taken:
            where = (where[0], (where[1] - 1) % render_overworld.OW_DIM)
        taken[where] = name
        placed[name] = where

    return placed, unplaced, anchors


def restamp(doc, placed, maps=("overworld", "incentives"), tile_px=16):
    """Move every overworld pin in `doc` onto the tile it was resolved to.

    -> (moved, dropped). A pin whose place this cartridge does not have -- the
    caravan and the airship desert are both absent from a No-Overworld map --
    loses its marker rather than keeping the pixel it had on the hand-drawn
    art, which on rendered art points at open sea. Dropped pins are returned so
    the run can say so; nothing here is silent.
    """
    half = tile_px // 2
    moved, dropped = 0, []

    def walk(node):
        nonlocal moved
        if isinstance(node, list):
            for n in node:
                walk(n)
            return
        if not isinstance(node, dict):
            return
        marks = node.get("map_locations")
        if marks:
            keep = []
            for ml in marks:
                if ml.get("map") not in maps:
                    keep.append(ml)
                    continue
                where = placed.get(node.get("name"))
                if where is None:
                    dropped.append((node.get("name"), ml.get("map")))
                    continue
                ml["x"] = where[0] * tile_px + half
                ml["y"] = where[1] * tile_px + half
                keep.append(ml)
                moved += 1
            node["map_locations"] = keep
        for key in ("children", "sections"):
            walk(node.get(key) or [])

    walk(doc)
    return moved, dropped
