#!/usr/bin/env python3
"""Diff the Temple of Fiends Revisited between two FFR cartridges.

The oracle cannot see ToFR. `Archipelago.cs:93` drops it from the AP pool
unconditionally, so FFR writes no rule for any ToFR location and not one of them
is among the 226 that `check_logic.py` compares. Quoting 226/226 as though it
covered the derived set overstates it by exactly these eight maps -- see
`docs/ISSUES.md`, "Nothing cross-checks the ToFR rules". This is the check that
covers the gap, by comparison rather than by an oracle: hold the flags still,
change the seed, and see what the shuffle moved.

What it compares, per ToFR map:

  teleports   every staircase tile, as (x, y, kind, destination). Read straight
              off the tile properties rather than by walking, because on a
              No-Overworld seed the seven interior floors are unreachable *by
              design* -- the shortcut points TempleOfFiends at Chaos and nothing
              teleports into the gauntlet. A reachability-based reader would
              report both cartridges as empty and call that agreement.
  chests      the treasure indices sitting on the map, each with the tile it
              sits on. Index alone would miss a chest that moved *within* one
              map, which changes reachability and so changes the derived rule.
  inbound     everything on the cartridge that lands in ToFR: both the extended
              normal-teleport table and the 32-entry overworld entrance table.
              A door repointed into ToFR is invisible if you read only the
              first, and entrance shuffle repoints exactly that table.

Three answers, not two. Cartridges the flags cannot certify as comparable get
exit 2 rather than a cheerful 0 -- see `comparable` below for the three ways
that happens. Saying "I cannot tell" is different from saying nothing moved.

    tofr_diff.py a.nes b.nes          0 = same, 1 = differs, 2 = incomparable
"""

import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import entrance_graph as eg
import extract_chests
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffr_flags"))
import ffr_flags

# The gauntlet plus Chaos's own room. TOFR_INTERIOR is the seven floors that the
# No-Overworld shortcut orphans; Chaos is reachable and is where a Short seed
# puts its chests, so a diff that left it out would miss the half that moves.
TOFR_MAPS = eg.TOFR_INTERIOR + ("TempleOfFiendsRevisitedChaos",)

KIND_NAME = {eg.TP_TELE_NORM: "norm", eg.TP_TELE_EXIT: "exit",
             eg.TP_TELE_WARP: "warp"}

# ffr_flags/schemas/4-9-2.json: ToFRMode 3 is "Random". The flag block records
# the *setting*, never the roll -- FF1Lib/TempleOfFiends.cs:52 collapses Random
# to a real mode with `rng.Between` and writes that nowhere. Two cartridges from
# the same Random preset both decode as 3 while one is Long and the other Short.
TOFR_MODE_RANDOM = 3


def tofr_map_ids():
    """{map_id: name} for the ToFR maps, resolved through MAP_NAMES."""
    return {eg.MAP_NAMES.index(n): n for n in TOFR_MAPS}


def teleport_rows(g, map_id):
    """Every teleport tile on a map, as comparable tuples.

    Structural, not reachability-based: `Graph.teleports` reads the tile
    property table, so an orphaned floor still reports its staircases.
    """
    rows = []
    for x, y, kind, pay in g.teleports(map_id):
        if kind == eg.TP_TELE_NORM:
            dest = g.norm_map[pay]
            where = (eg.MAP_NAMES[dest] if dest < eg.MAP_COUNT else f"?? ({dest})",
                     eg.coord(g.norm_x[pay]), eg.coord(g.norm_y[pay]))
        elif kind == eg.TP_TELE_EXIT:
            where = ("overworld", g.exit_x[pay], g.exit_y[pay]) \
                if pay < eg.EXIT_COUNT else ("overworld", None, None)
        else:
            where = ("warp", None, None)
        rows.append((x, y, KIND_NAME[kind], where[0], where[1], where[2]))
    return rows


def read(path):
    """Everything this tool compares about one cartridge."""
    # Two readers, two conventions, and getting them the wrong way round fails
    # with 'Rom' object is not subscriptable or an embedded null byte:
    # extract_chests wants the raw bytes, entrance_graph.Rom wants the path.
    raw = open(path, "rb").read()
    if raw[:4] != b"NES\x1a":
        sys.exit(f"{path}: not an iNES ROM")
    try:
        _, flags = ffr_flags.decode_rom(raw)
    except ffr_flags.DecodeError as err:
        # Same shape as check_logic.py:680 and entrance_graph.py:1027. A vanilla
        # image, or an FFR build whose version has no schema, clears the iNES
        # check above and would otherwise exit on a traceback instead of the
        # plain reason the exception already carries.
        sys.exit(f"{path}: cannot read the flags: {err}")

    g = eg.Graph(eg.Rom(path))
    ids = tofr_map_ids()

    # The placements, not the per-map index lists: `extract` hands back the tile
    # each chest sits on, and a chest that moved from one corner of Chaos to
    # another is a real difference -- it can change what is reachable and so what
    # the derived rule has to say. Teleports are already compared with their
    # (x, y); dropping the chests' would be an asymmetry, not a decision.
    placements = collections.defaultdict(collections.Counter)
    for idx, spots in extract_chests.extract(raw)[0].items():
        for spot in spots:
            placements[spot["map_id"]][(idx, spot["tile_col"], spot["tile_row"])] += 1

    # Multisets throughout. A treasure index can sit on more than one tile, and
    # collapsing them to a set would hide a chest that gained or lost a twin.
    maps = {}
    for map_id, name in sorted(ids.items()):
        maps[name] = {
            "teleports": collections.Counter(teleport_rows(g, map_id)),
            "chests": placements.get(map_id, collections.Counter()),
        }

    # Two tables reach a map, and only one of them is staircases. Rows are
    # (source, destination map, arrival x, arrival y) with the source spelled out
    # as text, so a door and a staircase can share one counter without a tuple
    # whose fields mean different things in different rows.
    inbound = collections.Counter()
    for m in range(eg.MAP_COUNT):
        if m in ids:
            continue
        for x, y, kind, pay in g.teleports(m):
            if kind != eg.TP_TELE_NORM:
                continue
            dest = g.norm_map[pay]
            if dest in ids:
                inbound[(f"{eg.MAP_NAMES[m]} ({x},{y})", ids[dest],
                         eg.coord(g.norm_x[pay]), eg.coord(g.norm_y[pay]))] += 1

    # All 32 entrance slots, not just the ones some overworld tile currently
    # points at: this is a census of the table, the same way the rest of the tool
    # reads tables rather than walking. No entrance lands in ToFR on a stock
    # seed; entrance shuffle is what makes this worth reading.
    for i in range(eg.ENTR_COUNT):
        dest = g.entr_map[i]
        if dest in ids:
            inbound[(f"door {eg.DOOR_NAMES[i]} (#{i})", ids[dest],
                     eg.coord(g.entr_x[i]), eg.coord(g.entr_y[i]))] += 1

    return {
        "game_mode": flags.get("GameMode"),
        "tofr_mode": flags.get("ToFRMode"),
        "maps": maps,
        "inbound": inbound,
    }


def comparable(a, b):
    """Why these two cartridges cannot be compared, or None if they can.

    Comparing is only meaningful when both cartridges were built to the same
    ToFR shape, and the flags are the only place to ask. Three ways they refuse
    to certify it, and all three are exit 2 rather than a difference count --
    reporting a shape difference as a shuffle difference would be a wrong
    answer dressed as a finding.
    """
    if a["game_mode"] != b["game_mode"]:
        # No-Overworld does not merely reach ToFR differently, it repoints
        # TempleOfFiends straight at Chaos and orphans the seven interior
        # floors (docs/NOVERWORLD.md). `inbound` then differs by construction.
        return (f"GameMode differs ({a['game_mode']} vs {b['game_mode']}) -- the "
                "mode decides how ToFR is wired into the rest of the cartridge.")
    if a["tofr_mode"] != b["tofr_mode"]:
        return (f"ToFRMode differs ({a['tofr_mode']} vs {b['tofr_mode']}) -- the "
                "mode decides which floors exist at all.")
    if a["tofr_mode"] == TOFR_MODE_RANDOM:
        return ("ToFRMode is Random on both -- the cartridge records the setting, "
                "not the roll, so equal flags do not mean equal ToFR shape. One "
                "of these may be Long and the other Short.")
    if a["tofr_mode"] is None:
        return "no ToFRMode in the decoded flags -- nothing certifies the shape."
    return None


def diff_counter(a, b):
    """(only in a, only in b) as sorted [(row, count)], multiset-aware."""
    return (sorted((a - b).items()), sorted((b - a).items()))


def report(a, b, name_a, name_b, verbose=False):
    """Print the comparison; return the number of differences."""
    print(f"A  {name_a}")
    print(f"B  {name_b}")
    print(f"ToFRMode: {a['tofr_mode']} vs {b['tofr_mode']}"
          f"   GameMode: {a['game_mode']} vs {b['game_mode']}")

    why = comparable(a, b)
    if why is not None:
        print(f"\nincomparable: {why}")
        return None

    n = 0
    for name in TOFR_MAPS:
        ma, mb = a["maps"][name], b["maps"][name]
        lines = []
        for what in ("teleports", "chests"):
            only_a, only_b = diff_counter(ma[what], mb[what])
            for row, count in only_a:
                lines.append(f"      A only  {what[:-1]:9} {row}" +
                             (f" x{count}" if count > 1 else ""))
            for row, count in only_b:
                lines.append(f"      B only  {what[:-1]:9} {row}" +
                             (f" x{count}" if count > 1 else ""))
        n += len(lines)
        if lines or verbose:
            print(f"  {name}   {sum(ma['teleports'].values())}/"
                  f"{sum(mb['teleports'].values())} teleports, "
                  f"{sum(ma['chests'].values())}/{sum(mb['chests'].values())} chests")
            for line in lines:
                print(line)

    only_a, only_b = diff_counter(a["inbound"], b["inbound"])
    if only_a or only_b or verbose:
        print(f"  inbound links   {sum(a['inbound'].values())} vs "
              f"{sum(b['inbound'].values())}")
        for row, _ in only_a:
            print(f"      A only  {row}")
        for row, _ in only_b:
            print(f"      B only  {row}")
    n += len(only_a) + len(only_b)

    print(f"\n{n} difference{'' if n == 1 else 's'}")
    return n


def main():
    ap = argparse.ArgumentParser(
        description="Diff the Temple of Fiends Revisited between two FFR ROMs")
    ap.add_argument("rom_a")
    ap.add_argument("rom_b")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="also print the maps that agree")
    args = ap.parse_args()

    a, b = read(args.rom_a), read(args.rom_b)
    n = report(a, b, args.rom_a, args.rom_b, args.verbose)
    return 2 if n is None else (1 if n else 0)


if __name__ == "__main__":
    sys.exit(main())
