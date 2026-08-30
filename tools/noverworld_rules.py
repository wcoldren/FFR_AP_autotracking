#!/usr/bin/env python3
"""Derive No-Overworld access rules from a cartridge.

    tools/noverworld_rules.py FFR_seed.nes [-o rules.json]

The pack's access rules describe the *standard* overworld: ship, canal, canoe,
the docks and the two mountain passes. No-Overworld has no overworld -- it swaps
it for an ocean stub with nine pads and wires everything else through a fixed
table of teleporters -- so roughly two-thirds of the rule surface is gating a
No-Overworld seed on geography that is not there. Ship and bridge are free in
that mode; the real gates are four NPCs standing in corridors, plus the ordinary
locked doors and rod plates.

None of that is expressible as a substitution on the standard rules, because the
mode's gating is per *floor* rather than per vehicle. So it is derived instead:
walk the cartridge holding every subset of the key items and see which tiles you
can stand on.

Why tiles and not maps. `Graph.reachable_maps` answers "can you enter this
floor", and a gate NPC or a locked door cuts a floor in half -- you enter Castle
Ordeals 1F freely and the half with the chests in it is behind a SIGIL barrier.
Asked per map, four of the items look irrelevant: floater, crown, chime and
tnt change no map's reachability at all. Asked per tile they do, which is the
whole point of the mode.

Minimal sets, not one set. An item that opens nothing on its own can still be
half of a pair that opens something -- floater and crown both add zero tiles
alone here -- so the lattice is swept rather than probed one item at a time.

Requires GameMode 2. On a standard cartridge this refuses rather than emitting
rules that would describe nothing.
"""

import argparse
import itertools
import json
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import entrance_graph as e          # noqa: E402
import extract_chests               # noqa: E402
import extract_npcs                 # noqa: E402
import overworld_reach as owr        # noqa: E402
import regen_maps                   # noqa: E402
import split_locations              # noqa: E402

# Where FFR writes the party's starting overworld position, and the offset it
# stores it at. MetroidVaniaMap.cs:93 puts (coneria_x, coneria_y) here, and
# those came from LoadInTown as (tile_x - 7, tile_y - 7) -- the scroll origin,
# not the party. Sanity/SCCoords is built as (x + 7, y + 7) from the same pair,
# which is what says the seven is the convention rather than a coincidence.
START_POS = 0x00, 0xB010
START_OFFSET = 7


def start_position(raw):
    """(x, y) the party stands on when a new game begins."""
    bank, addr = START_POS
    off = e.INES_HEADER + bank * 0x2000 + (addr - 0x8000)
    return raw[off] + START_OFFSET, raw[off + 1] + START_OFFSET


def start_doors(g, raw, w=None):
    """The doors the party can actually walk to, as (doors, note).

    `w` is the decompressed overworld, decompressed here when not supplied.

    `Graph.starts()` answers a question about the *table*: which entrances have a
    tile on the overworld. Seeding a reachability walk from all of them assumes
    the party begins standing on every one at once, and on a No-Overworld
    cartridge that is nine separate one-tile islands -- the eight towns and
    Coneria Castle -- scattered across an ocean stub. It is not a small error:
    it opened 45 of 61 maps empty-handed where the true figure is 22, and made
    167 locations read as free where FFR says 21.

    So ask the overworld instead. `overworld_reach.reach` is the transcription of
    the three move handlers, and it is run with the canoe granted, which is the
    most generous traversal the party could ever have. Every pad on the stub
    carries tile property 0x0E -- walkable on foot, and refused to the canoe, the
    ship and the airship alike -- so no vehicle moves you between pads and the
    answer does not depend on what is held. That is measured here rather than
    assumed: if a cartridge ever does let a vehicle off the start pad, the note
    says so instead of the tool quietly picking one reading.
    """
    if w is None:
        w = owr.Overworld(raw)
    sx, sy = start_position(raw)
    walkable = owr.reach(w, (sx, sy, "land"), canoe=True)
    on_foot = owr.landmass(w, (sx, sy))

    doors = [s for s in g.starts()
             if any(xy in walkable for xy in g.doors.get(s[0], []))]
    note = None
    if walkable != on_foot:
        extra = sorted(d for d, _, _ in doors
                       if not any(xy in on_foot for xy in g.doors.get(d, [])))
        if extra:
            note = ("a vehicle reaches doors %s from the start pad, so the seed"
                    " set is not item-independent on this cartridge" % extra)
    if not doors:
        raise SystemExit("no door on the party's own landmass at %s -- the start"
                         " position or the overworld read is wrong" % ((sx, sy),))
    return doors, note


def reachable_tiles(g, have, seeds=None):
    """{map_id: {(x, y)}} -- every tile you can stand on, walking from `seeds`.

    The same fixed point `reachable_maps` runs, keeping the floor walk instead of
    discarding it. `seeds` defaults to every door with a tile, which is what
    `reachable_maps` asks and the wrong question for a player -- see
    `start_doors`.
    """
    seen, q, tiles = set(), deque(), {}
    for _, m, a in (g.starts() if seeds is None else seeds):
        if (m, a) not in seen:
            seen.add((m, a))
            q.append((m, a))
    while q:
        m, a = q.popleft()
        tiles.setdefault(m, set()).update(g.floor_walk(m, a, have).keys())
        under = {(x, y): (k, p) for (x, y), (k, p, _)
                 in g.reachable_teleports(m, a, have).items()}
        for x, y, kind, pay in g.teleports(m):
            if (x, y) == (a[0] % e.MAP_DIM, a[1] % e.MAP_DIM):
                under[(x, y)] = (kind, pay)
        for kind, pay in under.values():
            if kind != e.TP_TELE_NORM:
                continue
            dm = g.norm_map[pay]
            if dm >= e.MAP_COUNT:
                continue
            arrive = (e.coord(g.norm_x[pay]), e.coord(g.norm_y[pay]))
            if (dm, arrive) not in seen:
                seen.add((dm, arrive))
                q.append((dm, arrive))
    return tiles


def sweep(g, items, targets, progress=None, seeds=None):
    """{target: [frozenset(items), ...]} -- which subsets can reach each target.

    `targets` is an iterable of (map_id, col, row). The answer for each is
    evaluated while that subset's walk is still in hand and the walk is then
    dropped, so only one tile set is ever live.

    Keeping the whole lattice instead -- {subset: {map_id: {(x, y)}}} -- is the
    obvious shape and does not fit in memory. One entry is about 1.7 MB on a
    cartridge reaching 26 of 61 maps, so 4096 of them is roughly 7 GB, and a
    No-Overworld cartridge reaches 54 maps and would want three or four. That is
    a MemoryError after the minute of walking is already spent, on the
    machine the tool exists for. Nothing is lost by folding early: `bump`
    membership is the only question ever asked of a walk.
    """
    targets = list(targets)
    tests = [(t, bump(*t)) for t in targets]
    out = {t: [] for t in targets}
    total = 2 ** len(items)
    done = 0
    for n in range(len(items) + 1):
        for combo in itertools.combinations(items, n):
            subset = frozenset(combo)
            tiles = reachable_tiles(g, set(combo), seeds)
            for t, hit in tests:
                if hit(tiles):
                    out[t].append(subset)
            done += 1
            if progress and done % 64 == 0:
                progress(done, total)
    return out


def minimal_sets(reaching):
    """The minimal item sets among `reaching`, as sorted lists.

    None when the target is reachable by no subset at all -- not even holding
    everything.
    """
    if not reaching:
        return None
    return sorted(sorted(s) for s in reaching
                  if not any(o < s for o in reaching))


def bump(map_id, col, row):
    """Reachable from a tile beside (col, row) -- which is how both kinds work.

    Neither a chest nor an NPC is stood on. `walkable` returns False for
    TP_SPEC_TREASURE (entrance_graph.py:515) because the engine does: you open a
    chest by walking into it from the side, and an NPC is talked to the same way.
    So asking whether the party can occupy the target tile answers "never" for
    every chest in the game -- which is exactly what it did, calling 241 of 249
    locations unreachable on a cartridge where most of the board is open from the
    start.
    """
    #
    # The neighbours wrap, because the walk does. Every key in reachable_tiles is
    # mod 64 now, so a raw col+1 on column 63 names a tile that can never be in
    # the set -- a chest on an edge would quietly lose an approach, and if that
    # were its only one the location would report unreachable. Exactly the bug
    # the wrapping fix exists to kill, one FFR layout change away from firing.
    spots = [((col + dx) % e.MAP_DIM, (row + dy) % e.MAP_DIM)
             for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    return lambda t: any(s in t.get(map_id, ()) for s in spots)


# The join back from a location's hosted_item code to the object id the
# cartridge knows it by. Inverted from extract_npcs.WANTED rather than written
# out again: one table naming these objects is already one more than the ROM
# needs, and two would drift.
OBJECT_IDS = {code: oid for oid, code in extract_npcs.WANTED.items()}


def placements(rom, locations, kinds=None, objects=None):
    """{location name: [(map_id, col, row)]} for every location on a dungeon map.

    The same join regen_maps.marker_tiles does: chests through the Archipelago
    id, NPCs through hosted_item -- but with both halves read off the cartridge
    in front of it, which is what lets the six NPC locations FFR pools resolve
    at all: king, sara, sages, elfprince, robot and lefein were simply not among
    the ids extract_npcs asked for.

    Chests and NPCs are not told apart here, because they ask the *same*
    reachability question -- see bump(). An earlier version returned the kind so
    the two could be tested differently; nothing consumed it, and a docstring
    promising a distinction the code does not make is an invitation to restore
    the stand-on-the-tile test for chests, which is the bug that called 241 of
    249 locations unreachable.

    `kinds`, if given, collects {name: {"chest"|"NPC"}} for a caller that wants
    the split for its own reasons -- the test asserts the NPCs join. `objects`
    collects {name: {object id}} for the NPCs, which is what a caller needs to
    ask the talk table whether that NPC wants something handed over first.
    """
    ids = split_locations.load_mapping(limit=512)
    chests, _ = extract_chests.extract(rom)
    # Off this cartridge, not out of npc_positions.json. That file is the
    # *vanilla* table, and FFR moves NPCs: Titan by (60,8,7) -> (60,4,8) on an
    # ordinary seed, and Nerrick by (19,16,45) -> (19,15,47) on a No-Overworld
    # one, where MetroidVaniaMap.cs re-places him. Deriving a No-Overworld rule
    # from a vanilla tile is the same mistake as reading the standard maps from
    # bank $04: it does not fail, it answers about a different cartridge.
    npcs = extract_npcs.extract(rom)

    out, outside = {}, {}

    def add(name, kind, places, oid=None):
        for q in places:
            cell = (q["map_id"], q["tile_col"], q["tile_row"])
            if regen_maps.stands_on_map(rom, *cell, cache=outside):
                out.setdefault(name, []).append(cell)
                if kinds is not None:
                    kinds.setdefault(name, set()).add(kind)
                if objects is not None and oid is not None:
                    objects.setdefault(name, set()).add(oid)

    for ap, (path, _) in sorted(ids.items()):
        places = chests.get(ap - 256)
        if places:
            add(split_locations.leaf_of(path), "chest", places)

    def walk(nodes):
        for n in nodes:
            if not isinstance(n, dict):
                continue
            for sec in n.get("sections") or []:
                code = sec.get("hosted_item")
                places = npcs.get(code)
                if places:
                    add(n.get("name"), "NPC", places, OBJECT_IDS.get(code))
            walk(n.get("children") or [])

    walk(regen_maps.lenient(os.path.join(regen_maps.PACK, locations)))
    return out


def fanned_sections(locations):
    """{node name: how many sections a derived rule for it would reach}.

    check_logic.load_derived_rules keys the derived rules on a *node* name and
    attaches each one to every section under that node -- chests and incentive
    pins included, not only the NPC it was derived for. So "would this rule
    reach something it was not derived for" is a question about sections, not
    about object ids: a node hosting one trading NPC and one chest holds a
    single object and two sections, and gating that chest on the trade item is
    exactly the over-reach the guard in derive() refuses.

    Both files, because check_logic.LOCATION_FILES is a pair -- the incentive
    pins live in incentives.json beside the tree, and a node named in both is
    fanned across both. `ref` sections are skipped for the same reason
    load_pack_rules skips them: they point at a section defined elsewhere, which
    is where it is already counted.
    """
    counts = {}

    def walk(nodes):
        for n in nodes:
            if not isinstance(n, dict) or n.get("name") is None:
                continue
            for sec in n.get("sections") or []:
                if "ref" in sec or sec.get("name") is None:
                    continue
                counts[n["name"]] = counts.get(n["name"], 0) + 1
            walk(n.get("children") or [])

    beside = os.path.join(os.path.dirname(locations), "incentives.json")
    for rel in (locations, beside):
        path = os.path.join(regen_maps.PACK, rel)
        if os.path.exists(path):
            walk(regen_maps.lenient(path))
    return counts


def derive(rom_path, locations, verbose=True):
    # Two views of the same cartridge. entrance_graph routes off a Rom object;
    # extract_chests and stands_on_map index raw bytes. Read once and hand each
    # what it wants rather than converting in the middle of a walk.
    with open(rom_path, "rb") as f:
        raw = f.read()
    rom = e.Rom.of(raw, rom_path)

    mode, why = e.game_mode(rom)
    if mode != e.GAME_MODE_NOVERWORLD:
        sys.exit(f"{rom_path}: GameMode {mode} ({why or 'read'}) -- these rules "
                 "only describe No-Overworld (GameMode 2)")

    # Before the sweep, not after: the join is where the cheap mistakes live and
    # the sweep is 70 seconds of work that would throw them away.
    hosts = {}
    cells_by_name = placements(raw, locations, objects=hosts)
    if not cells_by_name:
        sys.exit(f"{locations}: no location resolved to a tile -- nothing to derive")

    g = e.Graph(rom)
    items = sorted(e.ITEM_NAMES)

    # What has to be handed over before an NPC gives up what it holds. The walk
    # answers "can the party stand beside this object", which is a different
    # question -- Astos and Nerrick were the only two locations where the
    # derived rules and FFR's own logic disagreed, and both were this.
    traded = e.talk_item_requirements(rom) or {}
    if verbose and traded:
        print("  %d objects want something handed over first" % len(traded),
              file=sys.stderr)

    # Whose doors the walk may begin at. Everything the sweep says rests on this
    # -- getting it wrong is not a small over-count, it is the difference
    # between 22 maps open empty-handed and 45.
    seeds, note = start_doors(g, raw)
    if verbose:
        print("  starting from %s"
              % ", ".join(e.MAP_NAMES[m] for _, m, _ in seeds), file=sys.stderr)
        if note:
            print("  %s" % note, file=sys.stderr)

    def progress(done, total):
        if verbose:
            print(f"  {done}/{total} subsets", end="\r", file=sys.stderr)

    targets = {cell for cells in cells_by_name.values() for cell in cells}
    reaching = sweep(g, items, targets, progress, seeds)
    if verbose:
        print(f"  swept {2 ** len(items)} subsets over {len(targets)} tiles"
              + " " * 20, file=sys.stderr)

    fanned = fanned_sections(locations)

    out, unreachable = {}, []
    for name, cells in sorted(cells_by_name.items()):
        # A node with several tiles is reachable when any one of them is: the
        # pin's state ORs its sections, and the Marsh Cave and ToFR floors are
        # exactly this case.
        per = []
        for cell in cells:
            per.append(minimal_sets(reaching[cell]))
        live = [p for p in per if p is not None]
        if not live:
            unreachable.append(name)
            continue
        # Dedupe before minimising. A node with several tiles contributes one
        # group per tile, and identical groups are the common case -- four
        # chests in one room all come back "(free)". Without this the rule reads
        # "(free) OR (free) OR (free)", which is the same rule written three
        # times and would have shipped as three alternatives.
        merged = {tuple(s) for group in live for s in group}
        rules = sorted(list(m) for m in merged
                       if not any(set(o) < set(m) for o in merged))

        # A trade is a requirement on top of getting there, so it ANDs into
        # every alternative rather than adding one.
        want = sorted({traded[oid] for oid in hosts.get(name, ()) if oid in traded})
        if want:
            # The rules are keyed by location, and check_logic fans a location's
            # rule to each of its sections. So a node holding a second section
            # -- another NPC, a chest, an incentive pin -- would have that
            # section gated on an item it never asked for. Nothing in the tree
            # does that today: the four trading nodes expose one section each,
            # and the one node that used to hold two NPCs, Coneria Castle, now
            # exposes none of its own -- the King and Sara were split onto a
            # node apiece, and what is left under it is `ref` sections, which
            # fanned_sections skips. If one ever does trade, the honest answer
            # is to say so rather than over-gate it.
            #
            # Sections, not object ids. Counting objects passes a node whose one
            # trading NPC shares it with a chest, which is the same over-gating
            # with none of the warning.
            reach = fanned.get(name, 0)
            if reach > 1:
                sys.exit("%s exposes %d sections and one of its NPCs wants %s"
                         " handed over first; the rule is per location and fans"
                         " to every section, so applying it would gate the others"
                         " too. Split the node, or teach this to emit per"
                         " section." % (name, reach, ", ".join(want)))
            rules = [sorted(set(alt) | set(want)) for alt in rules]
            rules = sorted(a for a in rules
                           if not any(set(b) < set(a) for b in rules))
        out[name] = rules
    return out, unreachable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("-o", "--out", help="write the rules as JSON")
    ap.add_argument("--locations", default="locations/NOverworld/overworld.json",
                    help="location tree to join against")
    args = ap.parse_args()

    rules, unreachable = derive(args.rom, args.locations)

    shapes = {}
    for name, sets in rules.items():
        shapes.setdefault(tuple(tuple(s) for s in sets), []).append(name)
    print(f"{len(rules)} locations placed, {len(unreachable)} unreachable")
    for shape, names in sorted(shapes.items(), key=lambda kv: -len(kv[1])):
        pretty = " OR ".join(",".join(s) or "(free)" for s in shape) or "(none)"
        print(f"  {len(names):3}  {pretty}")
    if unreachable:
        print("\nno rule derived -- not reachable holding every item.")
        print("These keep whatever access_rules they already have; a location")
        print("silently losing its rule is worse than one that keeps a wrong.")
        for n in unreachable:
            print(f"  {n}")

    if args.out:
        with open(args.out, "w") as f:
            json.dump({"rules": rules, "unreachable": unreachable}, f, indent=1)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
