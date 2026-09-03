#!/usr/bin/env python3
"""Route the with-loot lane across one floor, for playability not step count.

"Shortest" was the wrong question the moment Marsh Cave was the test case, and
the reference publishes the right one. DarkmoonEX states his objective at the
head of Appendix D, in his own words: routing a floor "is based on how many
unsafe tiles a player has to cross to get to their goal (treasure rooms, the
stairs to the next floor, and/or the boss of that dungeon)... Maximizing the
number of safe tiles you take, along with minimizing unsafe tiles, will result
in the best, fastest route through a floor", and separately that the route
"should minimize the number of trap tiles you take along your path".

So the cost is lexicographic and step count comes *last*, not first:

  * a **fixed-formation trap tile** is a fight you did not ask for, so it costs
    a great deal and the lane goes round -- unless there is no way round, which
    on MarshCaveB3 is true of three chests out of eleven;
  * an **encounter tile** is a fight you might get. Two thirds of that floor is
    encounter floor and one third is not, so preferring the safe third is fewer
    fights over the same errand;
  * **steps**, which is what this had dominant and is the same ordering upside
    down;
  * a **turn you have to count** is harder to walk than one a wall makes for
    you, so the search runs over (tile, heading) and charges for changing.

The order the chests are visited in is solved exactly rather than greedily.
Nearest-neighbour left visible detours in the middle of a floor -- it commits to
the nearest chest and pays for it later -- and the biggest floor on either duck
cartridge is eighteen checks, which Held-Karp does in twelve seconds.

The drawing lives in render_maps.draw_lanes; this module returns tiles. That
split is deliberate: render_maps is imported here for the tile properties, so a
lane import over there would be a cycle, and regen_maps already passes `crop`
and `marks` in the same shape.
"""
import heapq
import os
import sys
from typing import NamedTuple

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import entrance_graph as eg  # noqa: E402
import extract_chests  # noqa: E402
import render_maps  # noqa: E402

# Lexicographic, as weights: one trap outranks any number of encounter tiles,
# one encounter tile outranks any number of steps.
#
# The gap between ranks has to clear the longest walk that can be priced, and
# that is not the tile count. A shortest path relaxes each (tile, heading) state
# at most once -- 64*64 tiles by five headings is 20480 steps -- and the tour
# chains up to MAX_EXACT+1 of those segments, so the ceiling is around 2**20
# steps at 2 apiece for STEP and TURN. 10**7 clears it; 10**3 did not, and 64*64
# is 4096, so under the old weights an ordinary thousand-step path outweighed a
# single encounter tile and the ordering was not lexicographic anywhere near
# its stated bound. No misroute was observed at the lengths real floors produce
# -- these are integers, so the wider gaps cost nothing to carry.
TRAP, ENCOUNTER, STEP, TURN = 10 ** 14, 10 ** 7, 1, 1
DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))
FAR = float("inf")

# Every real cost is multiplied by this, leaving 1 free underneath as a
# tie-break that cannot outrank a real step. It accrues up to 1 per step, so
# this has to clear the same ~2**20-step ceiling the ranks above do; at 1000 a
# walk past a thousand non-preferred steps bought itself a whole free step.
# What it buys is coincidence: a
# second lane over the same floor has no reason to pick the same corridor as
# the first when two are equally cheap, so it picks one arbitrarily and the
# drawing gains a parallel line that means nothing. Preferring what the first
# lane already uses, but only to break an exact tie, makes the two lanes run
# together wherever they can and part only where the map makes them.
#
# The preference is over **edges**, not tiles. Tiles is what this had, and it
# is not enough: two tiles the first lane visits by separate routes are both
# "preferred", so a step straight between them is free and the second lane
# takes it, drawing a purple stub across ground that is already cyan. That is
# the same meaningless parallel the tie-break exists to remove, one step long.
# SeaShrineB2 and TempleOfFiendsRevisitedFire are where it showed.
SCALE = 10 ** 7

# Held-Karp is 2**n, so the bound is a promise about how long a regen takes.
# Measured over both duck cartridges: the largest floor is GurguVolcanoB2 at 18
# reachable checks (12s), then SkyPalace3F and GurguVolcanoB4 at 14 and Cardia
# at 15 on the No-Overworld one. The plan for this said 13 and named the wrong
# maps -- that figure was chest *tiles* on the maps that had been looked at, not
# checks over all of them. 20 is two doublings of headroom above what any
# cartridge here produces; past it the honest answer is to say so rather than
# to sit for ten minutes looking like a hang.
MAX_EXACT = 20

# ...and n on its own does not bound what the tour allocates. The two tables it
# builds are (1 << n) * ns entries each, where ns counts *standing states* and
# not checks: GurguVolcanoB2's 18 checks are 43 states, so 11.3M entries a list
# and about 180 MB for the pair. Carry that states-per-check ratio up to the
# n=20 the bound above permits and it is 50M entries a list, near a gigabyte --
# which fails on allocation rather than by being slow, so the ten-minute hang
# promised above is not the failure that arrives first and the table needs a
# ceiling of its own. 32M entries is roughly 512 MB for the pair, a doubling
# and a half of headroom over the worst floor either cartridge produces.
MAX_ENTRIES = 32 * 1024 * 1024


class Run(NamedTuple):
    """One drawn lane: where it starts, the tiles it walks, what it collects."""
    label: str            # "route" or "loot"
    start: tuple
    path: list            # [(col, row)], consecutive and 4-adjacent mod 64
    traps: frozenset      # the fixed-formation tiles on this floor
    got: list             # chest indices collected, in visit order
    missed: list          # chest indices this region cannot reach


class Lanes(NamedTuple):
    """Everything one map's art needs drawn on it."""
    runs: list            # [Run], route before loot, one pair per region
    links: list           # [(a, b)] tile pairs, the silver connectors


class Floor:
    """One map, walked holding one inventory.

    Built per (map, `have`) rather than per map: the search memo below is only
    valid for a fixed inventory, and the whole point of the second lane is to
    walk the same floor holding the key it gates on.
    """

    def __init__(self, rom, graph, map_id, have=None, prefer=()):
        self.raw = rom
        self.g = graph
        self.mid = map_id
        self.items = graph.floor_items(map_id)
        self.have = self.items if have is None else have
        # Steps another lane on this floor already draws, as unordered tile
        # pairs; see SCALE.
        self.prefer = {frozenset(e) for e in prefer}
        _, self.p0, _ = graph.grid(map_id)
        self.tiles = render_maps.map_tiles(rom, map_id)
        self.tileset = rom[render_maps.TILESET_LUT + map_id]
        # Two rules floor_walk() enforces and a cost search has to enforce too,
        # or the lane draws a walk the game refuses. A blocking object is the
        # gate NPC standing in the doorway; a teleport tile takes you off the
        # floor the moment you step on it, so a route cannot pass *through* a
        # staircase even though the tile under it is walkable.
        self.blocked = graph.blocking_objects(map_id, self.have)
        self.teleports = {(x, y) for x, y, kind, _ in graph.teleports(map_id)
                          if kind}
        fixed = render_maps.fixed_formations(rom)
        base = render_maps.TILESET_PROP + self.tileset * render_maps.PROP_STRIDE
        self.encounter, self.trap = set(), set()
        for i, t in enumerate(self.tiles):
            b0 = rom[base + (t & 0x7F) * 2]
            if (b0 & eg.TP_SPEC_MASK) != render_maps.TP_SPEC_BATTLE:
                continue
            cell = (i % 64, i // 64)
            (self.trap if (self.tileset, t & 0x7F) in fixed
             else self.encounter).add(cell)
        self._searched = {}
        self._dist = {}

    # ------------------------------------------------------------- the walk

    def walkable(self, c):
        return (c not in self.blocked
                and self.g.walkable(self.p0[c[1] * 64 + c[0]], self.have))

    def enter(self, c):
        real = STEP + (TRAP if c in self.trap else 0) \
                    + (ENCOUNTER if c in self.encounter else 0)
        return real * SCALE

    def step(self, a, b):
        """Entering `b` from `a`, with the coincidence tie-break underneath."""
        return self.enter(b) + (0 if frozenset((a, b)) in self.prefer else 1)

    def stand(self, c):
        """Where you stand to open a chest. A chest tile is not walkable.

        Never a staircase. A tour visits its targets in turn, so a target you
        cannot stand still on is one the lane arrives at and then continues
        from -- which on IceCaveB2 drew two steps straight over a staircase the
        game would have taken you down.
        """
        return [n for n in (((c[0] + d[0]) % 64, (c[1] + d[1]) % 64)
                            for d in DIRS)
                if self.walkable(n) and n not in self.teleports]

    def search(self, start):
        """(cost, prev) over (tile, heading) states, from one tile.

        `prev` is the actual predecessor the search relaxed through, so a path
        is read straight back out of it. Rebuilding one by walking the cost
        field down instead needs a tolerance for the turn charge, and that
        tolerance is what put the wandering in the middle of a floor.

        A teleport tile is an accepted destination but never a tile to walk on
        through -- the same rule floor_walk states, since stepping on one takes
        you off the floor.
        """
        if start in self._searched:
            return self._searched[start]
        cost = {(start, None): 0}
        prev = {(start, None): None}
        q = [(0, start, None)]
        done = set()
        while q:
            c, cur, head = heapq.heappop(q)
            if (cur, head) in done:
                continue
            done.add((cur, head))
            if cur in self.teleports and cur != start:
                continue
            for d in DIRS:
                n = ((cur[0] + d[0]) % 64, (cur[1] + d[1]) % 64)
                if not self.walkable(n):
                    continue
                step = self.step(cur, n) + (TURN * SCALE
                                            if head is not None and d != head
                                            else 0)
                if c + step < cost.get((n, d), FAR):
                    cost[(n, d)] = c + step
                    prev[(n, d)] = (cur, head)
                    heapq.heappush(q, (c + step, n, d))
        self._searched[start] = (cost, prev)
        return cost, prev

    def reached(self, start):
        return {t for t, _ in self.search(start)[0]}

    def best_state(self, cost, tile):
        got = [(c, s) for s, c in cost.items() if s[0] == tile]
        return min(got) if got else (FAR, None)

    def dist(self, start):
        """{tile: cheapest cost from `start`}, collapsing the heading.

        Folded once per start rather than per query. cost_to() used to scan the
        whole (tile, heading) dict every time it was asked, and the tour asks it
        inside its innermost loop -- which is why an eighteen-chest floor was
        not slow, it was quadratic in the size of the search.
        """
        if start not in self._dist:
            best = {}
            for (tile, _), c in self.search(start)[0].items():
                if c < best.get(tile, FAR):
                    best[tile] = c
            self._dist[start] = best
        return self._dist[start]

    def cost_to(self, start, tile):
        return self.dist(start).get(tile, FAR)

    def path(self, start, goal):
        cost, prev = self.search(start)
        c, state = self.best_state(cost, goal)
        if state is None:
            return None
        out = []
        while state is not None:
            out.append(state[0])
            state = prev[state]
        out.reverse()
        return out

    # -------------------------------------------------------------- the tour

    def lane(self, groups, start, finish=()):
        """The cheapest order to collect every reachable check, exactly.

        `groups` is {chest index: [tile, ...]}. A chest index can sit on more
        than one tile and opening any one of them clears the lot, so the errand
        is one visit per **index**, not per tile -- MarshCaveB2 is seven tiles
        and four checks, and walking all seven is three detours for nothing.

        Which tile of a linked set to use is part of the problem rather than
        chosen up front: the nearest one to the door is not always the one the
        rest of the round wants. So a node carries every tile you could stand
        on to open any of its tiles, and the state is (visited, node, tile).
        """
        nodes, unreachable = [], []
        for idx, tiles in sorted(groups.items()):
            spots = []
            for c in tiles:
                for a in self.stand(c):
                    if self.cost_to(start, a) < FAR and a not in spots:
                        spots.append(a)
            if spots:
                nodes.append((idx, spots))
            else:
                unreachable.append(idx)
        if not nodes:
            return [start], [], unreachable
        if len(nodes) > MAX_EXACT:
            raise ValueError(
                "map %d has %d reachable checks; the exact tour is 2**n and "
                "MAX_EXACT is %d" % (self.mid, len(nodes), MAX_EXACT))

        n = len(nodes)
        # A *state* is one tile you could be standing at on one node, flattened
        # so the tour below indexes lists rather than walking nested ones. The
        # hop from state to node was computed inside the innermost loop before,
        # each hop rescanning the whole search -- on an eighteen-check floor
        # that is the difference between seconds and not finishing.
        states = [(i, a) for i in range(n) for a in range(len(nodes[i][1]))]
        if (1 << n) * len(states) > MAX_ENTRIES:
            raise ValueError(
                "map %d has %d reachable checks over %d standing states; the "
                "exact tour's tables would be %d entries each and MAX_ENTRIES "
                "is %d" % (self.mid, n, len(states),
                           (1 << n) * len(states), MAX_ENTRIES))
        at_state = [nodes[i][1][a] for i, a in states]
        of_node = [i for i, _ in states]
        by_node = [[s for s, (i, _) in enumerate(states) if i == j]
                   for j in range(n)]
        home = [self.cost_to(start, t) for t in at_state]
        hop = [[self.cost_to(src, t) for t in at_state] for src in at_state]

        ns = len(states)
        size = ns
        dp = [FAR] * ((1 << n) * size)
        back = [-1] * ((1 << n) * size)
        for s in range(ns):
            if home[s] < FAR:
                dp[(1 << of_node[s]) * size + s] = home[s]
        for mask in range(1 << n):
            row = mask * size
            for s in range(ns):
                cost_s = dp[row + s]
                if cost_s == FAR:
                    continue
                hop_s = hop[s]
                for j in range(n):
                    if mask & (1 << j):
                        continue
                    nrow = (mask | (1 << j)) * size
                    for t in by_node[j]:
                        c = cost_s + hop_s[t]
                        if c < dp[nrow + t]:
                            dp[nrow + t] = c
                            back[nrow + t] = s
        full = (1 << n) - 1
        frow = full * size
        end = min(((dp[frow + s], s) for s in range(ns)), default=(FAR, None))
        if end[1] is None or end[0] == FAR:
            return [start], [], [idx for idx, _ in nodes] + unreachable

        order, mask, cur = [], full, end[1]
        while cur >= 0:
            order.append(states[cur])
            nxt = back[mask * size + cur]
            mask ^= (1 << of_node[cur])
            cur = nxt
        order.reverse()

        # Each leg is planned from a standing stop: search() seeds (start,
        # None), so the heading you arrived on is dropped and the first step of
        # the next leg is never charged a turn. The DP prices legs the same way
        # -- cost_to() folds dist() across headings -- so the tour and the walk
        # it reconstructs agree with each other, and both undercount the turns
        # that turns() then reports on the finished path.
        #
        # Left that way deliberately. The turn term is there because holding a
        # direction until the map stops you needs no counting (IDEAS.md, "the
        # turn tie-break"), and opening a chest is already a stop -- there is no
        # held direction at a node to lose. Charging it would mean carrying the
        # heading into the DP state, which is four times the table for a term
        # that is last in the lexicographic order. ISSUES.md keeps the question.
        walk, at = [start], start
        for j, k in order:
            seg = self.path(at, nodes[j][1][k])
            walk += seg[1:]
            at = nodes[j][1][k]
        if finish:
            best = min((self.cost_to(at, t), t) for t in finish)
            if best[0] < FAR:
                seg = self.path(at, best[1])
                if seg:
                    walk += seg[1:]
        return walk, [nodes[j][0] for j, _ in order], unreachable


# ------------------------------------------------------------- the floor plan

def chest_groups(rom, map_id, chests=None):
    """{chest index: [(col, row)]} on one map.

    Grouped by index rather than listed by tile, because opening any tile of an
    index clears them all. extract_chests already returns a list of placements
    per index for exactly this reason, so nothing new is read here.
    """
    chests = extract_chests.extract(rom)[0] if chests is None else chests
    out = {}
    for idx, places in chests.items():
        here = [(p["tile_col"], p["tile_row"])
                for p in places if p["map_id"] == map_id]
        if here:
            out[idx] = here
    return out


def arrivals(f):
    """Every tile the game can put the party down on, on this floor.

    Off the teleport tables rather than out of Graph.route(): route() walks in
    from an overworld door, so it answers "can I get here holding nothing",
    which a drawing does not ask -- and deep floors come back with no route at
    all.
    """
    g = f.g
    out = {(eg.coord(g.norm_x[i]), eg.coord(g.norm_y[i]))
           for i in range(eg.NORM_COUNT_EXT) if g.norm_map[i] == f.mid}
    out |= {(eg.coord(g.entr_x[i]), eg.coord(g.entr_y[i]))
            for i in range(eg.ENTR_COUNT) if g.entr_map[i] == f.mid}
    # A row of the table can name a tile that is a plain wall -- MatoyasCave
    # (15, 0) is TP_NOMOVE with no special on both duck cartridges. That is a
    # table entry the seed does not use, and a lane starting on it begins
    # inside the rock.
    return sorted(a for a in out if f.walkable(a))


def exits(f, not_at=()):
    """Teleport tiles that leave this floor, other than the one you came in by.

    His goal list is "treasure rooms, the stairs to the next floor, and/or the
    boss", so a lane that stops at the last chest has stopped short: the walk
    back out is part of the errand. Floor.lane appends it to the *finished*
    tour rather than solving the two together, so the exit is chosen from
    wherever the round happened to end and cannot pull the chest order towards
    itself. Charging the walk out inside the DP's final min would let it, at no
    extra table -- it is a choice about what the lane means, not a cost, and it
    would move drawn lanes, so it waits for the editor ROADMAP.md describes.

    Which staircase it ends on is the *nearest*, not the one that progresses --
    a shuffled cartridge decides that, and this drawing never reads it. Of the
    chest-bearing maps on the two duck cartridges, 33 of 38 (std) and 34 of 37
    (nov) have more than one exit, so the lane end is a proximity statement and
    not a spoiler of the permutation.
    """
    return sorted({(x, y) for x, y, kind, _ in f.g.teleports(f.mid)
                   if kind and (x, y) not in not_at})


def regions(f):
    """[[arrival, ...]] -- the arrivals that can walk to each other.

    A lane belongs to an arrival, not to a map. Where a map is two halves that
    do not connect -- MarshCaveB2 is, and it is why DarkmoonEX draws that floor
    as two separately titled images -- each half has its own way in and wants
    its own lane, or half the drawing is a map with no route on it.

    Read holding what the floor gates on. A locked door is not a region
    boundary, it is the reason for the second lane, and reading regions keyless
    files the gated checks under "not on this floor" -- which is how
    MarshCaveB3 lost its loot lane entirely.

    Mutually, and against every member rather than the first one. Reachability
    here is not symmetric: search() reaches a teleport tile but will not expand
    out of one unless it started there, and 144 arrivals across the two duck
    cartridges are themselves teleport tiles. So an arrival that is a staircase
    between two corridors that do not otherwise join reaches both, and taking it
    as a region's representative merged the two -- one lane drawn for the pair,
    the other corridor left bare with its checks filed as missed.
    """
    out = []
    for a in arrivals(f):
        seen = f.reached(a)
        for r in out:
            if all(x in seen and a in f.reached(x) for x in r):
                r.append(a)
                break
        else:
            out.append([a])
    return out


def links(groups):
    """[(a, b)] -- the silver connectors between tiles of one linked index.

    Same-map pairs only. A cross-map twin has no line to draw, and drawing one
    to the edge of the frame would say "walk that way", which is the one thing
    a connector must not say.
    """
    out = []
    for _, here in sorted(groups.items()):
        out += list(zip(here, here[1:]))
    return out


def nearest_exit(f, start):
    """The tile this region leaves by: the cheapest exit to reach from `start`.

    The rule Floor.lane already applies to its `finish` set, lifted out so the
    route lane can use it with no errand at all. Which staircase it lands on
    is a proximity statement and not a spoiler of the permutation; exits() has
    the counts that settle that.
    """
    best = min(((f.cost_to(start, t), t) for t in exits(f, not_at={start})),
               default=(FAR, None))
    return None if best[0] == FAR else best[1]


def edges(walk):
    """The steps a walk draws, as unordered pairs.

    What "this lane adds nothing" has to be measured over. The same steps in a
    different order draw the same line, so comparing paths calls two identical
    drawings different.
    """
    return {frozenset((a, b)) for a, b in zip(walk, walk[1:]) if a != b}


def plan(rom, graph, map_id, chests=None):
    """-> Lanes for one map, or None where there is nothing to draw.

    One pair of runs per region, and the pair is the one the reference draws:

    * **route** -- the arrival to the nearest exit, opening nothing. The safest
      walk for someone passing through the floor. This is a thing worth drawing
      on every floor, and not only on a floor that gates on something.
    * **loot** -- the same arrival, every check the region can reach, then out.
      "For loot" already implies the key, so the floor's items are held from
      the start rather than a keyless variant being derived to diff against.

    Both Floors hold graph.floor_items(map_id). Holding an item only ever
    widens the walkable set, so a traversal route that holds the floor's key is
    never longer or less safe than one that does not -- and the keyless Floor
    this used to build existed only to derive the second lane by difference,
    which is the framing IDEAS.md corrects. What each colour is routed for is
    the change; the two-colour drawing mechanism is untouched.
    """
    groups = chest_groups(rom, map_id, chests)
    if not groups:
        return None
    f = Floor(rom, graph, map_id)
    runs = []
    for region in regions(f):
        reach = f.reached(region[0])
        here = {i: [c for c in ts if any(x in reach for x in f.stand(c))]
                for i, ts in groups.items()}
        here = {i: v for i, v in here.items() if v}
        if not here:
            continue
        # This region's own door, and the one that reaches most of its checks.
        # A linked chest with a tile in each half belongs to both, so leaving
        # the arrival open lets the half with fewer checks be "served" by the
        # other half's door -- drawing a second lane on top of the first and
        # leaving the other half bare, which looks exactly like the bug the
        # second lane exists to fix.
        #
        # The keyless-walkability half of this key went with the keyless Floor.
        # It was here because arrivals() filters on the full inventory while
        # the old plain lane walked with none, so a door a gate NPC stands in
        # was a legal arrival that lane could not legally begin on --
        # No-Overworld ConeriaCastle1F (2, 8). On one inventory there is no
        # such tile.
        start = max(region, key=lambda a: sum(
            1 for ts in here.values()
            if any(x in f.reached(a) for c in ts for x in f.stand(c))))
        # The route lane has no errand, so it is one path() call and not a
        # tour. A region whose only way out is the way you came in gets no
        # route lane -- there is no traversal to draw -- and its loot lane
        # still draws.
        out_at = nearest_exit(f, start)
        route = (f.path(start, out_at) or []) if out_at is not None else []
        if len(route) > 1:
            runs.append(Run("route", start, route, frozenset(f.trap), [], []))
        # The loot lane prefers the route lane's edges, so the two coincide
        # wherever that is free and purple only ever means "here the loot takes
        # you somewhere the walk through would not".
        loot = Floor(rom, graph, map_id, prefer=zip(route, route[1:]))
        walk, got, miss = loot.lane(here, start,
                                    finish=exits(loot, not_at={start}))
        # A loot lane that draws nothing the route lane does not is a purple
        # key row with no purple under it.
        if got and edges(walk) - edges(route):
            runs.append(Run("loot", start, walk, frozenset(loot.trap),
                            got, miss))
    if not runs:
        return None
    return Lanes(runs, links(groups))


def turns(path):
    """Counted turns: a heading change you have to make yourself."""
    return sum(1 for a, b, c in zip(path, path[1:], path[2:])
               if (b[0] - a[0], b[1] - a[1]) != (c[0] - b[0], c[1] - b[1]))


def main():
    import argparse
    ap = argparse.ArgumentParser(
        description="Report the with-loot lane for one map, or for all of them.")
    ap.add_argument("rom")
    ap.add_argument("--map", type=int, help="one map id; default every map "
                                            "that carries a chest")
    args = ap.parse_args()
    with open(args.rom, "rb") as fh:
        raw = fh.read()
    graph = eg.Graph(eg.Rom.of(raw, args.rom))
    chests = extract_chests.extract(raw)[0]
    ids = [args.map] if args.map is not None else range(eg.MAP_COUNT)
    for mid in ids:
        lanes = plan(raw, graph, mid, chests)
        if lanes is None:
            continue
        print("%-16s %d checks, %d linked pair%s"
              % (eg.MAP_NAMES[mid],
                 len(chest_groups(raw, mid, chests)), len(lanes.links),
                 "" if len(lanes.links) == 1 else "s"))
        for r in lanes.runs:
            print("    %-5s from %-9s %2d/%d checks, %3d steps, %2d turns, "
                  "%d forced trap%s"
                  % (r.label, "(%d,%d)" % r.start, len(r.got),
                     len(r.got) + len(r.missed), len(r.path) - 1,
                     turns(r.path),
                     sum(1 for c in r.path[1:] if c in r.traps),
                     "" if sum(1 for c in r.path[1:] if c in r.traps) == 1
                     else "s"))


if __name__ == "__main__":
    main()
