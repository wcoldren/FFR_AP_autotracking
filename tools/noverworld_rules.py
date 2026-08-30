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
Asked per map, four of the ten items look irrelevant: floater, crown, chime and
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
import regen_maps                   # noqa: E402
import split_locations              # noqa: E402


def reachable_tiles(g, have):
    """{map_id: {(x, y)}} -- every tile you can stand on, walking from the doors.

    The same fixed point `reachable_maps` runs, keeping the floor walk instead of
    discarding it.
    """
    seen, q, tiles = set(), deque(), {}
    for _, m, a in g.starts():
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


def sweep(g, items, progress=None):
    """{frozenset(items): {map_id: {(x, y)}}} over the whole subset lattice."""
    out = {}
    total = 2 ** len(items)
    for n in range(len(items) + 1):
        for combo in itertools.combinations(items, n):
            out[frozenset(combo)] = reachable_tiles(g, set(combo))
            if progress and len(out) % 64 == 0:
                progress(len(out), total)
    return out


def minimal_sets(lattice, test):
    """Minimal item sets satisfying `test(tiles) -> bool`, as sorted lists.

    None when nothing satisfies it -- unreachable holding everything, which for
    a No-Overworld cartridge means the seven orphaned ToFR floors.
    """
    ok = [s for s, tiles in lattice.items() if test(tiles)]
    if not ok:
        return None
    return sorted(sorted(s) for s in ok if not any(o < s for o in ok))


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
    spots = [(col + dx, row + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    return lambda t: any(s in t.get(map_id, ()) for s in spots)


def placements(rom, locations):
    """{location name: [(kind, map_id, col, row)]}, kind "chest" or "NPC".

    The same join regen_maps.marker_tiles does -- chests through the Archipelago
    id, NPCs through hosted_item -- but keeping which kind each placement is,
    because the two ask different reachability questions. You stand on a chest;
    you talk to an NPC from the tile beside it, its own being blocked.

    Guessing the kind from the node name does not work: marker_tiles is keyed by
    bare node name ("Dwarf Cave Smith") and npc_positions.json by item code
    ("smith"), and nothing maps one to the other.
    """
    ids = split_locations.load_mapping(limit=512)
    chests, _ = extract_chests.extract(rom)
    with open(os.path.join(HERE, "npc_positions.json")) as f:
        npcs = json.load(f)

    out, outside = {}, {}

    def add(name, kind, places):
        for q in places:
            cell = (q["map_id"], q["tile_col"], q["tile_row"])
            if regen_maps.stands_on_map(rom, *cell, cache=outside):
                out.setdefault(name, []).append((kind,) + cell)

    for ap, (path, _) in sorted(ids.items()):
        places = chests.get(ap - 256)
        if places:
            add(split_locations.leaf_of(path), "chest", places)

    def walk(nodes):
        for n in nodes:
            if not isinstance(n, dict):
                continue
            for sec in n.get("sections") or []:
                places = npcs.get(sec.get("hosted_item"))
                if places:
                    add(n.get("name"), "NPC", places)
            walk(n.get("children") or [])

    walk(regen_maps.lenient(os.path.join(regen_maps.PACK, locations)))
    return out


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
    cells_by_name = placements(raw, locations)
    if not cells_by_name:
        sys.exit(f"{locations}: no location resolved to a tile -- nothing to derive")

    g = e.Graph(rom)
    items = sorted(e.ITEM_NAMES)

    def note(done, total):
        if verbose:
            print(f"  {done}/{total} subsets", end="\r", file=sys.stderr)

    lattice = sweep(g, items, note)
    if verbose:
        print(f"  swept {len(lattice)} subsets" + " " * 20, file=sys.stderr)

    out, unreachable = {}, []
    for name, cells in sorted(cells_by_name.items()):
        # A node with several tiles is reachable when any one of them is: the
        # pin's state ORs its sections, and the Marsh Cave and ToFR floors are
        # exactly this case.
        per = []
        for _kind, map_id, col, row in cells:
            per.append(minimal_sets(lattice, bump(map_id, col, row)))
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
        out[name] = sorted(list(m) for m in merged
                           if not any(set(o) < set(m) for o in merged))
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
