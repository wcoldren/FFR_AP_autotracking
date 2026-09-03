"""The route lane is a walk the game would actually let you take.

A drawn lane is a claim, and every one of these is a way the claim could be
false while the picture still looked plausible:

  * **every tile on it is walkable holding what that lane holds.** DwarfCave is
    the case that needs saying out loud -- its corridors are drawn in the same
    rough brown as its walls, so a lane through solid rock is invisible to the
    eye and obvious to the tile properties;
  * **consecutive tiles are one step apart**, mod 64, because a standard map is
    a torus and a path that jumps is a path reconstructed wrong;
  * **it never walks through a gate NPC or through a staircase.** Both are rules
    Graph.floor_walk() enforces and the router's own cost search has to enforce
    separately. They are not decoration: on the standard duck cartridge they
    change the lane on 8 of 38 chest maps, and TitansTunnel is the clearest --
    without the NPC rule its route lane strolls past the Titan and collects all
    four chests;
  * **each colour is routed for its own errand** -- a route lane opens
    nothing and ends on a way off the floor, a loot lane opens something --
    which is Graph.floor_items()'s answer and not a list here;
  * **the Map Key fits the map it is drawn on.** The band is the map's own
    width and the narrowest map carrying a chest is sixteen tiles across;
  * **an authored lane walks the same floor the solver does.** The stops are a
    person's, but the walking between them is the router's, so handing back the
    order a solved lane already found has to reproduce that lane -- and a stop
    that resolves to nowhere has to be refused rather than stepped over.

Set FF1_ROM to a cartridge; without one this skips. A real FFR seed is
strictly stronger than the vanilla image here -- vanilla has no shuffled
teleports and no second region on MarshCaveB2.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import entrance_graph as eg                                    # noqa: E402
import extract_chests as ec                                    # noqa: E402
import font                                                    # noqa: E402
import lane as L                                               # noqa: E402
import render_maps as rm                                       # noqa: E402


def loose(cls):
    """The router with the two floor_walk rules turned off.

    Only the gate row's own demonstration uses this: a rule that changes
    nothing anywhere is either dead code or evidence the enforcement is not
    wired, and both are worth catching here rather than in play.
    """
    class Loose(cls):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self.blocked, self.teleports = set(), set()
    return Loose


def shape(lanes):
    return None if lanes is None else [
        (r.label, r.start, len(r.path), tuple(r.got)) for r in lanes.runs]


def regions_do_not_share_edges():
    """A loot lane in one region must not subtract another region's route lane.

    plan() emits [route?, loot?] per region, and a region whose only way out
    is the way it came in gets no route run at all -- MatoyasCave, Waterfall,
    Cardia's islands. So the run before a loot run is not always its own
    region's. Regions overlap in tiles -- search() reachability is asymmetric
    across staircase arrivals -- so the edges the two share are real steps of
    both, and subtracting the first region's set from the second's lane erases
    the middle of a line that is drawn as continuous.

    The third case below is the one position cannot get right: a bare route
    run for one region followed by a bare loot run for another. It is not on
    either duck cartridge today, but both of the shapes it is made of are --
    `route,loot,route,loot` and four bare loot runs on one map -- so it is a
    seed away, and Run.region is what tells them apart.

    Needs no cartridge: draw_lanes takes a frame, a crop and the runs, and the
    colours it writes are the whole answer. Runs both ways round, because a
    check that only passes after the fix says nothing about what it protects --
    the first case is the behaviour that must survive the second.
    """
    fails = []
    crop = rm.Crop(box=(0, 9, 0, 9))
    w, h = 10 * rm.TILE_PX, 10 * rm.TILE_PX
    route = rm.NES_PALETTE[rm.LANE_ROUTE]
    purple = rm.NES_PALETTE[rm.LANE_LOOT]

    def run(label, path, region=0):
        return L.Run(label, path[0], list(path), frozenset(), [1], [], region)

    # Region A walks the corridor keyless and its loot lane extends it by one
    # tile. Region B is key-only and walks the same corridor.
    a_route = run("route", [(1, 1), (2, 1), (3, 1), (4, 1)])
    a_loot = run("loot", [(1, 1), (2, 1), (3, 1), (4, 1), (4, 2)])
    b_loot = run("loot", [(1, 1), (2, 1), (3, 1)], region=1)

    def corridor_colour(runs):
        out = bytearray(w * h * 3)
        rm.draw_lanes(out, w, h, crop, L.Lanes(list(runs), []))
        # Midway between (2,1) and (3,1), on the centre line both lanes walk.
        x, y = 3 * rm.TILE_PX, 1 * rm.TILE_PX + rm.TILE_PX // 2
        i = (y * w + x) * 3
        return tuple(out[i:i + 3])

    def check(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")
        print(f"{'ok  ' if got == want else 'FAIL'} {label}")

    # The shared corridor stays the colour of the walk you can always do.
    check("a loot lane adds nothing where it follows its own route lane",
          corridor_colour([a_route, a_loot]), route)
    # And a second region's loot lane still draws over it.
    check("a second region's loot lane is not subtracted by the first's",
          corridor_colour([a_route, a_loot, b_loot]), purple)
    # The same, with region A's loot run dropped so that region B's is the run
    # immediately after region A's route. Position says these two are a pair
    # and they are not.
    check("nor by the route lane it merely follows",
          corridor_colour([a_route, b_loot]), purple)
    return fails


def main():
    fails = regions_do_not_share_edges()
    path = os.environ.get("FF1_ROM")
    if not path or not os.path.exists(path):
        print("SKIP  set FF1_ROM to a Final Fantasy cartridge for the rest")
        for f in fails:
            print("     " + f)
        print("ALL PASS" if not fails else f"{len(fails)} FAILED")
        return 1 if fails else 0
    with open(path, "rb") as f:
        rom = f.read()
    graph = eg.Graph(eg.Rom.of(rom, path))
    chests = ec.extract(rom)[0]

    def check(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")
        print(f"{'ok  ' if got == want else 'FAIL'} {label}")

    plans = {}
    for map_id in range(eg.MAP_COUNT):
        got = L.plan(rom, graph, map_id, chests)
        if got is not None:
            plans[map_id] = got

    check("some map carries a lane at all", bool(plans), True)
    check("a lane is only drawn where there are chests",
          sorted(m for m in plans if not L.chest_groups(rom, m, chests)), [])

    # ---------------------------------------------------- the walk is legal
    unwalkable, jumps, through_npc, through_stair = [], [], [], []
    for map_id, lanes in plans.items():
        for run in lanes.runs:
            # Both lanes hold what the floor gates on, so there is no
            # per-run inventory any more. Checking either against the empty
            # one would fail it for walking through a door the floor's own key
            # opens -- which is a walk the game allows and the drawing claims.
            floor = L.Floor(rom, graph, map_id)
            for i, cell in enumerate(run.path):
                if not floor.walkable(cell):
                    unwalkable.append((eg.MAP_NAMES[map_id], run.label, cell))
                if cell in floor.blocked:
                    through_npc.append((eg.MAP_NAMES[map_id], cell))
                # The start is an arrival and the end is the exit it finishes
                # on; a teleport anywhere between the two is a floor the lane
                # left in the middle of its errand.
                if cell in floor.teleports and 0 < i < len(run.path) - 1:
                    through_stair.append((eg.MAP_NAMES[map_id], cell))
            for a, b in zip(run.path, run.path[1:]):
                dx = min((a[0] - b[0]) % 64, (b[0] - a[0]) % 64)
                dy = min((a[1] - b[1]) % 64, (b[1] - a[1]) % 64)
                if dx + dy != 1:
                    jumps.append((eg.MAP_NAMES[map_id], a, b))

    check("every tile a lane walks is walkable holding what it holds",
          unwalkable, [])
    check("and consecutive tiles are one step apart on the torus", jumps, [])
    check("no lane walks through a gate NPC", through_npc, [])
    check("and none routes through a staircase", through_stair, [])

    # -------------------------------------- the two rules demonstrate a bite
    orig = L.Floor
    L.Floor = loose(orig)
    try:
        without = {m: shape(L.plan(rom, graph, m, chests)) for m in plans}
    finally:
        L.Floor = orig
    moved = sorted(eg.MAP_NAMES[m] for m in plans
                   if without[m] != shape(plans[m]))
    print(f"     ({len(moved)} of {len(plans)} lanes move when the NPC and "
          f"staircase rules come off: {', '.join(moved) or 'none'})")
    check("turning those two rules off changes a lane somewhere",
          bool(moved), True)

    # ------------------------------------------ what each lane is routed for
    # The pair is a traversal and a loot round, not two loot rounds that differ
    # by an inventory. A route run that collects something is the old errand
    # back under a new name; a loot run that collects nothing is a purple key
    # row with nothing under it.
    wrong = []
    for map_id, lanes in plans.items():
        for run in lanes.runs:
            if run.label == "route" and run.got:
                wrong.append((eg.MAP_NAMES[map_id], "route lane collects",
                              run.got))
            if run.label == "loot" and not run.got:
                wrong.append((eg.MAP_NAMES[map_id], "loot lane collects nothing"))
    check("a route lane opens nothing and a loot lane opens something",
          wrong, [])

    # And a traversal lane is arrival *to an exit*, so its last tile is a way
    # off the floor. Without this the label is only a colour: a route that
    # stopped anywhere else would still be drawn and still be called the walk
    # through. A floor whose only way out is the way in gets no route lane at
    # all rather than one that ends in the middle -- MatoyasCave, Waterfall.
    not_out = []
    for map_id, lanes in plans.items():
        outs = set(L.exits(L.Floor(rom, graph, map_id)))
        for run in lanes.runs:
            if run.label == "route" and run.path[-1] not in outs:
                not_out.append((eg.MAP_NAMES[map_id], run.path[-1]))
    check("a route lane ends on a way off the floor", not_out, [])

    # --------------------------------------------------- one lane per region
    # Every region that holds a check gets a lane starting at one of its own
    # arrivals, and no two route lanes share a start. Serving one region from
    # another's door is the bug that drew a second lane on top of the first.
    strays, shared_starts = [], []
    for map_id, lanes in plans.items():
        probe = L.Floor(rom, graph, map_id)
        rs = L.regions(probe)
        seen = set()
        for run in lanes.runs:
            if run.label != "route":
                continue
            if not any(run.start in r for r in rs):
                strays.append((eg.MAP_NAMES[map_id], run.start))
            if run.start in seen:
                shared_starts.append((eg.MAP_NAMES[map_id], run.start))
            seen.add(run.start)
    check("every lane starts at an arrival the game can put you down on",
          strays, [])
    check("and no two route lanes on a map start in the same place",
          shared_starts, [])

    # ------------------------------------------------- the authored lane
    # The order is the author's and the walking is still the router's, so a
    # solved lane handed back as its own stops must come out the same lane.
    # This is the whole claim of "the router becomes the pathing primitive":
    # if the two disagree, the editor would draw something the solver never
    # would and neither would be wrong about the cartridge.
    diverged, illegal = [], []
    for map_id, lanes in plans.items():
        f = L.Floor(rom, graph, map_id)
        outs = set(L.exits(f))
        spec = []
        for r in lanes.runs:
            stops = [{"kind": "arrival", "at": list(r.start),
                      "in": list(r.start)}]
            stops += [{"kind": "chest", "index": i} for i in r.got]
            if r.path[-1] in outs:
                stops.append({"kind": "exit", "at": list(r.path[-1])})
            spec.append({"flavour": r.label, "stops": stops,
                         "region": r.region})
        back = L.authored(rom, graph, map_id, {"lanes": spec}, chests)
        for r, a in zip(lanes.runs, back.runs):
            if len(a.path) != len(r.path) or sorted(a.got) != sorted(r.got):
                diverged.append((eg.MAP_NAMES[map_id], r.label,
                                 len(a.path), len(r.path)))
            for i, cell in enumerate(a.path):
                if not f.walkable(cell):
                    illegal.append((eg.MAP_NAMES[map_id], r.label, cell))
            for x, y in zip(a.path, a.path[1:]):
                dx = min((x[0] - y[0]) % 64, (y[0] - x[0]) % 64)
                dy = min((x[1] - y[1]) % 64, (y[1] - x[1]) % 64)
                if dx + dy != 1:
                    illegal.append((eg.MAP_NAMES[map_id], r.label, x, y))
    check("an authored lane reproduces the solved one it came from",
          diverged, [])
    check("and every step of it is a step the game allows", illegal, [])

    # A stop that resolves to nowhere is a refusal, not a leg to step over.
    # Drawing the lane without it reads as a shorter route rather than as a
    # broken one, which is the failure that would never be noticed.
    one = sorted(plans)[0]
    wall = None
    probe = L.Floor(rom, graph, one)
    for c in ((x, y) for y in range(64) for x in range(64)):
        if not probe.walkable(c):
            wall = c
            break
    refused = []
    for stops in ([{"kind": "arrival", "at": list(plans[one].runs[0].start),
                    "in": list(plans[one].runs[0].start)},
                   {"kind": "tile", "at": list(wall)}],
                  [{"kind": "chest", "index": 9999},
                   {"kind": "tile", "at": list(plans[one].runs[0].start)}]):
        try:
            L.authored(rom, graph, one,
                       {"lanes": [{"flavour": "route", "stops": stops}]},
                       chests)
            refused.append(("drew it anyway", stops[-1]))
        except ValueError:
            pass
    check("a stop that resolves to no tile is refused", refused, [])

    # ------------------------------------------------ the drawing's own rules
    # A loot lane is drawn as the *extension* of the route one, so purple should
    # mean "here the key buys you something" rather than "here the search
    # picked the other corridor". That "extra segments only" is true by
    # construction -- draw_lanes subtracts the shared set -- so asserting it
    # here would test nothing. What is worth testing is the tie-break that
    # makes the two lanes coincide in the first place: turn it off and the
    # purple has to grow. A preference that changes no drawing is dead weight.
    #
    # It cannot go to zero, and should not: SeaShrineB2's loot lane steps
    # straight from (14,22) to (15,22), two tiles the route lane reaches by
    # separate routes and never walks between. One purple step there is a real
    # shortcut, not a duplicate.
    def extras(rom_, mid_, prefer_edges):
        runs_ = {r.label: r for r in plans[mid_].runs}
        # Both, or there is no coincidence to measure: a floor whose checks all
        # sit behind the gate draws the loot lane on its own.
        if "loot" not in runs_ or "route" not in runs_:
            return None
        groups = {i: v for i, v in L.chest_groups(rom_, mid_, chests).items()}
        probe = L.Floor(rom_, graph, mid_)
        reach = probe.reached(runs_["route"].start)
        here = {i: [c for c in v if any(x in reach for x in probe.stand(c))]
                for i, v in groups.items()}
        here = {i: v for i, v in here.items() if v}
        walk = runs_["route"].path
        f = L.Floor(rom_, graph, mid_,
                    prefer=zip(walk, walk[1:]) if prefer_edges else ())
        k = f.lane(here, runs_["route"].start,
                   finish=L.exits(f, not_at={runs_["route"].start}))[0]
        seg = lambda p: {frozenset((a, b))                        # noqa: E731
                         for a, b in zip(p, p[1:]) if a != b}
        return len(seg(k) - seg(walk))

    grew = []
    for map_id in sorted(plans):
        on = extras(rom, map_id, True)
        if on is None:
            continue
        off = extras(rom, map_id, False)
        if off > on:
            grew.append((eg.MAP_NAMES[map_id], off, on))
    print("     (turning the coincidence tie-break off adds purple on "
          f"{len(grew)} map(s): "
          + ", ".join(f"{n} {a}->{b}" for n, a, b in grew) + ")")
    check("the coincidence tie-break removes purple that means nothing",
          bool(grew), True)

    # A connector joins two tiles of one index, both on this map.
    bad_links = []
    for map_id, lanes in plans.items():
        groups = L.chest_groups(rom, map_id, chests)
        pairs = {frozenset(p) for p in L.links(groups)}
        for a, b in lanes.links:
            if frozenset((a, b)) not in pairs:
                bad_links.append((eg.MAP_NAMES[map_id], a, b))
    check("every silver connector joins two tiles of one check", bad_links, [])

    # ------------------------------------------------------------ the Map Key
    # The band is the map's own width, so the longest row has to fit the
    # narrowest map that can carry one. draw_map_key drops a scale when it does
    # not, and that fallback is only worth having if it lands somewhere legible.
    longest = max(list(rm.LANE_KEY_TEXT.values()) + ["Trap Tile W"], key=len)
    narrow = []
    for map_id, lanes in plans.items():
        tiles = rm.map_tiles(rom, map_id)
        crop = rm.content_crop(tiles)
        w = crop.size[0] * rm.TILE_PX
        scale = rm.LETTER_SCALE
        while scale > 1 and rm.KEY_TEXT_X + font.text_px(longest, scale) > w:
            scale -= 1
        if rm.KEY_TEXT_X + font.text_px(longest, scale) > w:
            narrow.append((eg.MAP_NAMES[map_id], w))
    check("the longest Map Key row fits every map that carries a lane",
          narrow, [])

    # And the band is actually reserved for what goes in it: a map whose lanes
    # want four rows must not be given a band sized for the trap letters alone.
    short = []
    for map_id, lanes in plans.items():
        tiles = rm.map_tiles(rom, map_id)
        marks = rm.map_trap_marks(rom, map_id, tiles, rm.trap_marks(rom))
        entries = len(set(marks.values())) + len(rm.lane_key_entries(lanes))
        rows = rm.legend_rows_for(len(set(marks.values())),
                                  len(rm.lane_key_entries(lanes)))
        if rows < entries + 1:
            short.append((eg.MAP_NAMES[map_id], rows, entries))
    check("and the band has a row for every entry plus the heading", short, [])

    # ----------------------------------------------- the lane reaches the art
    # The whole point is pixels on the tab. Rendering one map with and without
    # its lane has to differ, and a map with no lane has to be untouched.
    lit = next(iter(sorted(plans)))
    tiles = rm.map_tiles(rom, lit)
    crop = rm.content_crop(tiles)
    rows = rm.legend_rows_for(0, len(rm.lane_key_entries(plans[lit])))
    bare = rm.render(rom, lit, unroof=True, crop=crop, legend_rows=rows)[2]
    drawn = rm.render(rom, lit, unroof=True, crop=crop, legend_rows=rows,
                      lanes=plans[lit])[2]
    check(f"{eg.MAP_NAMES[lit]}'s render changes when its lane is drawn",
          bare != drawn, True)
    blank = next((m for m in range(eg.MAP_COUNT) if m not in plans), None)
    if blank is not None:
        b = rm.content_crop(rm.map_tiles(rom, blank))
        check("a map with no chests is untouched by the lane pass",
              rm.render(rom, blank, unroof=True, crop=b)[2]
              == rm.render(rom, blank, unroof=True, crop=b, lanes=None)[2],
              True)

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
