#!/usr/bin/env python3
"""Diff the Temple of Fiends Revisited between two FFR cartridges.

The oracle cannot see ToFR. `Archipelago.cs:93` drops it from the AP pool
unconditionally, so FFR writes no rule for any ToFR location and not one of them
is among the set `check_logic.py` compares. Quoting that figure as though it
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

`--dump` reads one cartridge instead of comparing two. It exists because the
refusal above is not a gap to be closed: the mode really does decide which
floors exist, so Long against Mid is not a shuffle difference and never will
be. The only way to record what each mode does is to read each one and put the
readings side by side, which is what the flag prints -- which floors have a way
in, and where the seven chest indices landed.

    tofr_diff.py a.nes b.nes          0 = same, 1 = differs, 2 = incomparable
    tofr_diff.py --dump a.nes [b.nes] one cartridge's shape, not a comparison
"""

import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import entrance_graph as eg
import extract_chests
import noverworld_rules
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

# For the dump's heading only. The diff never spells a mode out, because it only
# ever reports that two of them differ.
MODE_NAME = {0: "Long", 1: "Mid", 2: "Short", TOFR_MODE_RANDOM: "Random"}


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
    inbound = inbound_rows(g, ids)

    return {
        "game_mode": flags.get("GameMode"),
        "tofr_mode": flags.get("ToFRMode"),
        "maps": maps,
        "inbound": inbound,
        # Not compared, and no test fixture carries it: the walk `--dump` does
        # wants the same decompressed maps this function already built, and
        # handing the graph on is cheaper than reading the cartridge twice.
        "graph": g,
    }


def inbound_rows(g, ids):
    """Counter of (source, ToFR map name, arrival x, arrival y) -- every way in.

    Two tables reach a map, and only one of them is staircases. Rows spell the
    source out as text so a door and a staircase can share one counter without a
    tuple whose fields mean different things in different rows.

    All 32 entrance slots, not just the ones some overworld tile currently
    points at: this is a census of the table, the same way the rest of the tool
    reads tables rather than walking. No entrance lands in ToFR on a stock seed;
    entrance shuffle is what makes this worth reading.
    """
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
    for i in range(eg.ENTR_COUNT):
        dest = g.entr_map[i]
        if dest in ids:
            inbound[(f"door {eg.DOOR_NAMES[i]} (#{i})", ids[dest],
                     eg.coord(g.entr_x[i]), eg.coord(g.entr_y[i]))] += 1
    return inbound


def live_chest_tiles(raw, g):
    """{(map_id, col, row)} -- the ToFR chest tiles this cartridge really wires.

    No mode erases a chest tile. `MidToFR` and `ShortToFR` lay fresh copies on
    the floors they put you on and leave the originals exactly where they were,
    so a chest index sits on two tiles and only one of them can be opened. A
    tool that draws every tile a chest resolves to therefore draws the stranded
    copy as well -- on a Mid cartridge, two markers on ToFR 3F, a floor that
    mode does not wire at all.

    The walk is the only thing that can tell them apart, and `reached` says why:
    Mid blocks the passages with wall tiles and leaves every teleport table
    entry in place, so a census of ways in still reports 2F and 3F wired. Only
    Short's change is table-visible.

    ToFR maps only. The walk is seeded at ToFR arrivals and answers one
    question -- what this cartridge wired -- so it has nothing to say about any
    other floor, and a caller must not read a tile's absence here as a verdict
    on one. Cartridge and not ToFRMode: GameMode decides the wiring as well, and
    No-Overworld repoints TempleOfFiends at Chaos and orphans the seven interior
    floors on its own (docs/NOVERWORLD.md). A floor missing from this walk is
    not a fact about ToFRMode alone.

    The walk itself is `reached`, called rather than repeated. Two copies of the
    seeding would be two answers to "what did this cartridge wire" -- `--dump`'s
    walk column and the regen's pin filter -- that could drift apart while both
    still claimed to be the same walk.
    """
    ids = tofr_map_ids()
    inbound = inbound_rows(g, ids)
    if not inbound:
        # reachable_tiles falls back to the doors only when `seeds` is None; an
        # empty list is taken at face value and walks nothing. That would class
        # every ToFR chest stranded and clear the floors of pins, with a count
        # line as the only signal. No cartridge is really like that -- a
        # beatable seed has to reach Chaos, and the sample cartridges each carry
        # exactly one inbound row -- so an empty census is this tool having
        # misread the tables, and it should say so rather than answer.
        raise ValueError("no teleport or door lands in ToFR on this cartridge; "
                         "the entrance and teleport tables did not read")
    tiles = reached(g, {"inbound": inbound})
    live = set()
    for idx, spots in extract_chests.extract(raw)[0].items():
        for spot in spots:
            cell = (spot["map_id"], spot["tile_col"], spot["tile_row"])
            if cell[0] in ids and noverworld_rules.bump(*cell)(tiles):
                live.add(cell)
    return live


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


def wiring(state):
    """{map name: (ways in, ways out)} for the eight ToFR maps.

    Built out of what `read` already holds rather than by a second pass over the
    cartridge. Only a normal teleport can land on a map: `inbound` is the census
    of those from every map outside ToFR, and a floor's own rows carry the ones
    from inside the gauntlet. So a floor with no way in is a floor the mode did
    not wire, which is the question Long, Mid and Short answer differently --
    Mid blocks the passages to Stairs B and repoints 1F's left stairs at the
    Earth floor, and Short repoints the Black Orb warp at Chaos and orphans all
    seven (FF1Lib/TempleOfFiends.cs, MidToFR and ShortenToFR).
    """
    into = collections.Counter()
    for row, count in state["inbound"].items():
        into[row[1]] += count
    for name in TOFR_MAPS:
        for row, count in state["maps"][name]["teleports"].items():
            if row[3] in TOFR_MAPS:
                into[row[3]] += count
    return {name: (into[name], sum(state["maps"][name]["teleports"].values()))
            for name in TOFR_MAPS}


def reached(g, state):
    """{map_id: {(x, y)}} -- every tile you can stand on, entering ToFR.

    A walk, and it has to be. The teleport tables do not say which floors a mode
    puts in the dungeon: `MidToFR` blocks the passages to Stairs B by writing
    walls onto 1F (`0x39` at [0x1C,0x15] and [0x11,0x20]) and leaves 2F and 3F
    with every table entry and every staircase they had. A census of ways in
    reports them wired on a Mid cartridge, and they are not reachable. Only
    Short's change is table-visible, because it repoints a teleport.

    Seeded at the arrivals `read` already found rather than at the doors, which
    is what makes this answerable on a standard cartridge at all: the walk does
    not model an overworld, but it does not have to -- entering ToFR is the only
    question, and `inbound` is the census of every way in. That is the only
    key `state` has to carry, so a caller holding just a census can walk without
    reading the whole cartridge a second time -- `live_chest_tiles` does.

    Every item is in hand on purpose. What is being asked is what the cartridge
    wired, not what the seed gates, and holding everything separates the two: a
    floor missing from this walk is missing because there is no way in.
    """
    seeds = [(None, eg.MAP_NAMES.index(row[1]), (row[2], row[3]))
             for row in state["inbound"]]
    return noverworld_rules.reachable_tiles(g, set(eg.ITEM_NAMES), seeds)


def dump(state, path):
    """Print one cartridge's ToFR shape.

    The diff refuses across modes on purpose, so a comparison can never say what
    Long does that Mid does not. Three of these tables side by side can, and
    that is the whole reason this exists.

    Two readings per floor, because they disagree and the disagreement is the
    finding. `tele in` is how many teleports on the cartridge land on the floor,
    read off the tables; `walk` is whether you can actually stand there entering
    from outside with every item in hand. On Mid, 2F and 3F keep their table
    entries and lose the walk.

    Chests are listed by index rather than by floor, because the index is what
    stays put. No mode erases a chest tile: Mid and Short lay fresh copies on
    the floors they do put you on and leave the originals where they were, so an
    index on two floors is the normal case there and the walk is what tells the
    live copy from the stranded one.
    """
    mode = state["tofr_mode"]
    print(path)
    print(f"ToFRMode: {mode} ({MODE_NAME.get(mode, '?')})   "
          f"GameMode: {state['game_mode']}")
    ways = wiring(state)
    tiles = reached(state["graph"], state)
    print(f"  {'floor':34}{'tele in':>8}{'out':>5}{'chests':>8}  walk")
    rows = []
    for name in TOFR_MAPS:
        map_id = eg.MAP_NAMES.index(name)
        n_in, n_out = ways[name]
        chests = sum(state["maps"][name]["chests"].values())
        print(f"  {name:34}{n_in:8}{n_out:5}{chests:8}  "
              + ("reached" if tiles.get(map_id) else "NOT REACHED"))
        for (idx, col, row), count in state["maps"][name]["chests"].items():
            # A chest is opened from beside it, never stood on -- the shared
            # test for that is noverworld_rules.bump, which every derived rule
            # in this repo already goes through.
            rows.append((idx, name, col, row, count,
                         noverworld_rules.bump(map_id, col, row)(tiles)))
    print(f"  {'chest':>5}   {'floor':34}tile      walk")
    for idx, name, col, row, count, live in sorted(rows):
        print(f"  {idx:5}   {name:34}({col},{row})".ljust(54)
              + ("open" if live else "stranded")
              + (f" x{count}" if count > 1 else ""))
    if not rows:
        print("      none -- no ToFR map on this cartridge carries a chest")


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
    ap.add_argument("rom_b", nargs="?")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="also print the maps that agree")
    ap.add_argument("--dump", action="store_true",
                    help="print each cartridge's ToFR shape instead of "
                         "comparing two")
    args = ap.parse_args()

    if args.dump:
        for i, path in enumerate(p for p in (args.rom_a, args.rom_b) if p):
            if i:
                print()
            dump(read(path), path)
        return 0
    if args.rom_b is None:
        # Not a usage nicety: a comparison silently given one cartridge is the
        # shape of a check that cannot fail, which is what this whole tool
        # exists to avoid.
        ap.error("two ROMs are needed to compare; --dump reads one or two")

    a, b = read(args.rom_a), read(args.rom_b)
    n = report(a, b, args.rom_a, args.rom_b, args.verbose)
    return 2 if n is None else (1 if n else 0)


if __name__ == "__main__":
    sys.exit(main())
