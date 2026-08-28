#!/usr/bin/env python3
"""Walk a seed's overworld and answer what the party can actually get to.

The overworld is stored per row, RLE'd, with a pointer table at the head of
BANK_OWMAP ($01). Nothing else in the pack decodes it, and reachability is not
something you can read off a table: FFR's own logic switches to SanityCheckerV2
and walks tiles whenever overworld map edits are on, so ItemLocations.cs's
vanilla MapChange list is not an answer.

  Constants.inc:89   BANK_OWMAP = $01
  Constants.inc:449  lut_OWPtrTbl = $8000 (BANK_OWMAP)

Two tile-classification traps, both of which produce a confident wrong answer:

  * Docks are the wrong reachability test. The Gaia / Lefein / Castle of Ordeals
    continent has no dock tile on it at all, yet it is reachable without the
    airship, because the canoe can be boarded straight off the ship where a
    river meets the ocean. The right question is "does a river touch both the
    ocean and this landmass?", which is what --rivers answers.
  * Coast tiles are shoreline, not land and not water. The ship enters them and
    the party can walk them. Calling them pure land cuts the ship off; calling
    them pure water severs walking routes along the shore. Either one gives a
    false negative. --no-coast turns the ship's half of this off, which is what
    the earlier scratchpad scripts did.

Two results this tool does NOT reproduce, recorded here so nobody chases them
again. An earlier session's note claims that on FFR_03409C3E_GsBKsXSF the ship
plus canoe reaches Gaia, Lefein and Castle of Ordeals, via one river mouth at
(134, 33). Running that session's own scripts on that ROM gives Gaia False and
no river mouth touching Gaia's landmass at all -- (134, 33) is one of twelve
mouths on the map, none of them adjacent to that continent. With coast handling
on, Ordeals flips to reachable; Gaia and Lefein do not. The seed's flags say
why: MapGaiaMountainPass, MapHighwayToOrdeals, MapLefeinRiver and
MapBridgeLefein are all off and OwMapExchange is None, so this is the stock
overworld, on which Gaia is airship-only exactly as in vanilla. The canoe
mechanism itself is real; the seed-specific conclusion was not.

Usage:
    tools/overworld_reach.py ROM                 # ship vs ship+canoe
    tools/overworld_reach.py ROM --rivers        # river mouths onto a landmass
    tools/overworld_reach.py ROM --at 221 28     # is this tile reachable?
"""

import argparse
import sys
from collections import deque

INES_HEADER = 0x10
BANK_SIZE = 0x4000
OW_PTR_TBL = INES_HEADER + BANK_SIZE          # lut_OWPtrTbl, bank 1 at $8000
OW_DIM = 256

MOUNTAIN = {0x10, 0x11, 0x12, 0x20, 0x21, 0x22, 0x30, 0x31, 0x32, 0x33}
OCEAN = {0x17}
RIVER = {0x40, 0x41, 0x44, 0x50, 0x51}
DOCK = {0x0F, 0x1F, 0x77, 0x78, 0x79, 0x7A}
COAST = {0x06, 0x07, 0x08, 0x16, 0x18, 0x26, 0x27, 0x28}

# Somewhere in open ocean, well clear of land: where the ship starts a walk.
OPEN_SEA = (240, 60)

PLACES = {
    "Coneria": (152, 162), "Pravoka": (210, 150), "Elfland": (136, 222),
    "Melmond": (81, 160), "CrescentLake": (219, 218), "Gaia": (221, 28),
    "Onrac": (62, 56), "Lefein": (235, 99), "CastleOrdeals": (130, 45),
    "TempleOfFiends": (130, 123), "EarthCave": (65, 187),
    "GurguVolcano": (188, 205), "IceCave": (197, 183), "Cardia1": (92, 48),
    "BahamutCave": (96, 51),
}


def decompress_ow(rom):
    """256 rows: <$80 literal, $FF fills the rest of the row with ocean,
    otherwise (tile | $80) then a run length where 0 means 256."""
    rows = []
    for i in range(OW_DIM):
        ptr = int.from_bytes(rom[OW_PTR_TBL + 2 * i:OW_PTR_TBL + 2 * i + 2], "little")
        raw = rom[INES_HEADER + ptr - 0x4000:]
        row, j = [], 0
        while len(row) < OW_DIM:
            t = raw[j]
            if t < 0x80:
                row.append(t)
                j += 1
            elif t == 0xFF:
                row += [0x17] * (OW_DIM - len(row))
            else:
                run = raw[j + 1] or 256
                row += [t - 0x80] * run
                j += 2
        rows.append(row[:OW_DIM])
    return rows


def kind(t):
    if t in OCEAN:
        return "sea"
    if t in RIVER:
        return "river"
    if t in MOUNTAIN:
        return "wall"
    if t in COAST:
        return "coast"
    return "land"


def reach(m, start, canoe, coast=True):
    """Tiles reachable from `start`, tracking which vehicle you are in.

    The sea -> river step is the load-bearing one: it is the only way onto the
    northern continent short of the airship.
    """
    seen, q = set(), deque()

    def push(s):
        if s not in seen:
            seen.add(s)
            q.append(s)

    push(start)
    while q:
        x, y, mode = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = (x + dx) % OW_DIM, (y + dy) % OW_DIM
            k = kind(m[ny][nx])
            if k == "wall":
                continue
            if mode == "sea":
                if k == "sea" or (k == "coast" and coast):
                    push((nx, ny, "sea"))
                elif k == "river" and canoe:
                    push((nx, ny, "river"))
                elif k in ("land", "coast") and m[ny][nx] in DOCK:
                    push((nx, ny, "land"))
            elif mode == "river":
                if k == "river":
                    push((nx, ny, "river"))
                elif k in ("land", "coast"):
                    push((nx, ny, "land"))
                elif k == "sea":
                    push((nx, ny, "sea"))
            else:
                if k in ("land", "coast"):
                    push((nx, ny, "land"))
                elif k == "river" and canoe:
                    push((nx, ny, "river"))
                elif k == "sea" and m[y][x] in DOCK:
                    push((nx, ny, "sea"))
    return {(x, y) for x, y, _ in seen}


def landmass(m, seed):
    """Tiles walkable on foot from `seed`, ignoring every vehicle."""
    def foot(t):
        return t not in MOUNTAIN and t not in OCEAN and t not in RIVER

    seen, q = {seed}, deque([seed])
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = (x + dx) % OW_DIM, (y + dy) % OW_DIM
            if (nx, ny) not in seen and foot(m[ny][nx]):
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


def print_rivers(m, seed):
    mass = landmass(m, seed)
    print(f"landmass around {seed}: {len(mass)} tiles, "
          f"{sum(1 for p in mass if m[p[1]][p[0]] in DOCK)} dock tiles on it")
    mouths = []
    for y in range(OW_DIM):
        for x in range(OW_DIM):
            if m[y][x] not in RIVER:
                continue
            adj = [((x + dx) % OW_DIM, (y + dy) % OW_DIM)
                   for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            if any(m[b][a] in OCEAN for a, b in adj) and any(p in mass for p in adj):
                mouths.append((x, y))
    print(f"river mouths that touch both the ocean and this landmass: {mouths or 'NONE'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--rivers", action="store_true",
                    help="river mouths onto the landmass around --seed")
    ap.add_argument("--seed", nargs=2, type=int, metavar=("X", "Y"), default=(221, 28),
                    help="landmass seed tile for --rivers (default: Gaia)")
    ap.add_argument("--at", nargs=2, type=int, metavar=("X", "Y"),
                    help="report reachability of one tile")
    ap.add_argument("--no-coast", action="store_true",
                    help="do not let the ship enter shoreline tiles")
    args = ap.parse_args()

    rom = open(args.rom, "rb").read()
    if rom[:4] != b"NES\x1a":
        sys.exit("not an iNES ROM")
    m = decompress_ow(rom)

    if args.rivers:
        print_rivers(m, tuple(args.seed))
        return

    for canoe in (False, True):
        r = reach(m, (*OPEN_SEA, "sea"), canoe, coast=not args.no_coast)
        label = "ship + canoe" if canoe else "ship"
        print(f"{label:<13} {len(r):>6} tiles reachable")
        if args.at:
            print(f"              {tuple(args.at)}: {tuple(args.at) in r}")
        else:
            hits = sorted(n for n, p in PLACES.items() if p in r)
            print(f"              places: {hits}")


if __name__ == "__main__":
    main()
