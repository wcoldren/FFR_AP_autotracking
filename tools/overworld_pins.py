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
reach the thing it names** -- or, where the door already carries an entrance
pin, on the first free tile above it. For each pin the pack draws, take every
chest under it, ask which maps those chests are on, and ask entrance_graph for
the door that reaches them. That handles the ordinary case (Ice Cave's pin on Ice Cave's
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
import pin_visibility  # noqa: E402  -- ENTRANCES_GROUP, the group stamp() reads
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


# The prefix every entrance node's name carries. Namespaced because
# tiles_by_name, mirror_of and restamp are all keyed on a bare node name, and a
# door named "Coneria" would collide with the town pin of the same name.
ENTRANCE_PREFIX = "Entrance: "


def entrance_door_pins(reader):
    """{node name: (x, y)} -- one trapezoid pin per overworld door.

    A door's *position* is not part of the shuffle. Entrances rewrites where a
    door leads, not where it is, so this is the same answer on every seed and
    marking it gives nothing away. Where it now goes is the connection half, and
    is not this.

    One pin per door rather than one per tile: door_cells takes the north-west
    corner of a town's blob, which is where a single marker belongs.
    """
    return {ENTRANCE_PREFIX + entrance_graph.DOOR_NAMES[door]: cell
            for door, cell in sorted(door_cells(reader).items())}


# The tooltip icons the entrance group hands its children. Written by a regen
# from the cartridge, like the map art, and for the same reason: they are the
# game's own pixels, so they belong beside the renders in the override rather
# than committed here.
DOOR_SHUT_IMG = "images/icons/door_shut.png"
DOOR_OPEN_IMG = "images/icons/door_open.png"


def entrance_group(doors, origin=(0, 0), map_name="overworld", tile_px=16):
    """The tree node the door pins are injected as.

    One group, named so tools/pin_visibility.py can find it: entrance pins are
    the kind classified by where a node sits rather than by what it holds, and
    the group is what says so. The rule itself is stamp()'s to write.

    Each door is its own location with its own section. Both halves are
    required rather than tidy -- CalculateLocationState walks only a node's own
    sections and does not aggregate from children, so a parent carrying markers
    and no sections is hidden; and a section with item_count below 1 and no
    hosted item is skipped, which leaves a marker that draws nothing and reports
    no error. The default item_count is 1 (locationsection.cpp:67), so the way
    to get that right is to leave it alone.

    A section also gives a door a state, which is the point: until the bridge
    watches the party walk through one, "I have been in here" is a click.

    `origin` is the crop box's top-left tile, the same measurement restamp
    takes, because the pixel is measured from the image actually written.

    The two images are the group's rather than each door's, because a section
    inherits both from its parent (location.cpp:175) -- so this one pair covers
    every door and every floor link injected under it. They are the tooltip's
    icon, which is the one place a pin can carry a picture: the marker itself is
    a shape and a colour and nothing else (mapwidget.cpp:352). PopTracker's own
    chest is the default, which is what an entrance was showing.

    A path that does not resolve falls back to that chest without a word
    (maptooltip.cpp:214, "TODO: remove silent fallback"), so the suite checks
    these two against the files a regen writes rather than trusting the string.
    """
    ox, oy = origin
    half = tile_px // 2
    return {
        "name": pin_visibility.ENTRANCES_GROUP,
        "chest_unopened_img": DOOR_SHUT_IMG,
        "chest_opened_img": DOOR_OPEN_IMG,
        "children": [
            {"name": name,
             "sections": [{"name": name[len(ENTRANCE_PREFIX):]}],
             "map_locations": [{"map": map_name,
                                "x": (cell[0] - ox) * tile_px + half,
                                "y": (cell[1] - oy) * tile_px + half,
                                "shape": "trapezoid"}]}
            for name, cell in sorted(doors.items())
        ],
    }


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
        placed[name] = where

    return placed, unplaced, anchors


def spread(placed, step, dim=256, taken=None):
    """Move pins off each other, `step` tiles at a time. -> a new dict.

    Two pins on one tile is one pin: ToFR shares the Temple of Fiends' door and
    Sky Palace shares Mirage Tower's, because that is the door you go through.

    `taken` seeds the occupied tiles before any pin is laid out, and is how the
    entrance pins keep their doors. A trapezoid is the same size box as a place
    pin, so the two coincident is one of them invisible and which one depends on
    tree order; claiming the door first makes the answer "the door is marked,
    and what is behind it is stacked above" rather than a coin toss.

    The step is a marker's height rather than a tile, and that is the whole
    point of taking it as an argument. A tile was the smallest move that
    separates two *tiles*, which is what the first version did -- and at a
    marker of 92 pixels, near six tiles, two boxes a tile apart still sit on
    top of each other. Boxes are what a player sees, so boxes are what has to
    be stacked, and how big one is depends on a crop this cannot see.

    Which is why the collision is a box overlap and not a shared tile. Taking
    the step from the marker and then asking whether two pins sat on the same
    cell answered the wrong question: Cardia Swampy stood three tiles off
    Bahamut's door, cleared the tile test, and drew half on top of it. Two
    boxes clash when they are within a step on both axes, which is the same
    measurement the step already is.
    """
    step = max(1, int(step))
    out, taken = {}, dict(taken or {})

    def clash(cell):
        """The name of a marker whose box overlaps one drawn at `cell`."""
        for (col, row), who in taken.items():
            if abs(col - cell[0]) < step and abs(row - cell[1]) < step:
                return who
        return None

    for name, where in placed.items():
        moved = where
        # North first: there is most room above a door on this art, and the
        # column then reads as one stack rather than two directions.
        while clash(moved) and moved[1] - step >= 0:
            moved = (moved[0], moved[1] - step)
        # The top edge is not a wrap point. This is not a torus -- content_box
        # clamps to the map -- and a door within a step of row 0 used to wrap to
        # y~250, which stretched the crop to nearly every row and put the pin at
        # the far bottom of the render: a silently wrong map rather than a
        # reported failure. Out of room going north, go south instead.
        while clash(moved) and moved[1] + step < dim:
            moved = (moved[0], moved[1] + step)
        blocked = clash(moved)
        if blocked:
            raise ValueError(
                f"no room to stack {name!r} clear of {blocked!r}: "
                f"{where} with a {step}-tile step on a {dim}-tile map")
        taken[moved] = name
        out[name] = moved
    return out


# How much map to keep around the pins. Eight tiles is a screen's worth of
# context at the game's own 16x15 viewport, and the floor stops a cluster of
# two from rendering as a postage stamp PopTracker then blows up to nothing.
CROP_MARGIN = 8
CROP_MIN = 32


def marker_tiles(box_tiles, num=80, den=3096):
    """How many tiles wide the overworld marker will be on a crop this wide.

    regen_maps sizes the marker as a fraction of the image's pixel width, and a
    tile is 16 pixels however wide the crop is -- so the same fraction in tiles
    needs no pixels to compute, and the stack step can be known before anything
    is drawn. Same constants, and tests/test_overworld_pins.py checks the two
    agree rather than trusting that they do.
    """
    return max(1, round(box_tiles * num / den))


def content_box(anchors, dim=256, margin=CROP_MARGIN, minimum=CROP_MIN):
    """(x0, y0, w, h) in tiles: what the pins need to be seen, clamped to the map.

    The rule is the pins rather than the land, because the land is not what an
    overworld tab is for. On a standard cartridge the pins are spread over the
    whole field and this trims ocean off the edges; on a No-Overworld one they
    are nine doors in a fourteen-tile huddle and it is the difference between a
    readable map and a green smudge.
    """
    if not anchors:
        return (0, 0, dim, dim)
    xs = [x for x, _ in anchors]
    ys = [y for _, y in anchors]
    x0, x1 = min(xs) - margin, max(xs) + margin + 1
    y0, y1 = min(ys) - margin, max(ys) + margin + 1
    def grow(lo, hi):
        while hi - lo < minimum:
            if lo > 0:
                lo -= 1
            if hi - lo < minimum and hi < dim:
                hi += 1
            if lo == 0 and hi == dim:
                break
        return max(0, lo), min(dim, hi)
    x0, x1 = grow(max(0, x0), min(dim, x1))
    y0, y1 = grow(max(0, y0), min(dim, y1))
    return (x0, y0, x1 - x0, y1 - y0)


def restamp(doc, placed, maps=("overworld", "incentives"), tile_px=16,
            origin=(0, 0)):
    """Move every overworld pin in `doc` onto the tile it was resolved to.

    `origin` is the crop box's top-left tile, so a pin's pixel is measured from
    the image that is actually written rather than from the whole 256x256 field.

    -> (moved, dropped). A pin whose place this cartridge does not have -- the
    caravan and the airship desert are both absent from a No-Overworld map --
    loses its marker rather than keeping the pixel it had on the hand-drawn
    art, which on rendered art points at open sea. Dropped pins are returned so
    the run can say so; nothing here is silent.
    """
    half = tile_px // 2
    ox, oy = origin
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
                ml["x"] = (where[0] - ox) * tile_px + half
                ml["y"] = (where[1] - oy) * tile_px + half
                keep.append(ml)
                moved += 1
            node["map_locations"] = keep
        for key in ("children", "sections"):
            walk(node.get(key) or [])

    walk(doc)
    return moved, dropped
