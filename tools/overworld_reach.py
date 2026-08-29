#!/usr/bin/env python3
"""Walk a seed's overworld and answer what the party can actually get to.

The overworld is stored per row, RLE'd, with a pointer table at the head of
BANK_OWMAP ($01). Nothing else in the pack decodes it, and reachability is not
something you can read off a table: FFR's own logic switches to SanityCheckerV2
and walks tiles whenever overworld map edits are on, so ItemLocations.cs's
vanilla MapChange list is not an answer.

  Constants.inc:89   BANK_OWMAP = $01
  Constants.inc:449  lut_OWPtrTbl = $8000 (BANK_OWMAP)
  Constants.inc:469  lut_OWTileset = $8000 (BANK_OWINFO = $00), 128 tiles x 2
  Constants.inc:332  OWTP_DOCKSHIP = %00100000
  variables.inc:70   vehicle = 1 walking, 2 canoe, 4 ship, 8 airship
  bank_0F.asm:1139   AND vehicle -- the entire movement test
  bank_0F.asm:1391   UnboardBoat: AND #$01, so stepping off needs a walkable
                     tile; @MoveShip at :604 needs OWTP_DOCKSHIP as well

Which tile is water and which is wall is not a judgement call: the low nibble of
each tile's first property byte is one "this vehicle may not enter" bit per
vehicle, and the game's whole movement check is `tileprop & vehicle`. An earlier
version of this file guessed at the classes instead, with tile-id sets for
mountain, ocean, river, dock and coast, and the sets were wrong in both
directions on a stock cartridge: of the 126 tile ids a real overworld uses, 32
disagreed with the cartridge. Tile $32 is in the mountain set and is walked on,
and the other 31 are tiles the party cannot step on that were treated as open
ground -- which merges landmasses and makes --rivers report a mouth touching a
continent it does not touch.

The one trap that survives reading the table:

  * Docks are the wrong reachability test. The Gaia / Lefein / Castle of Ordeals
    continent has no dock tile on it at all, yet it is reachable without the
    airship, because the canoe can be boarded straight off the ship where a
    river meets the ocean. The right question is "does a river touch both the
    ocean and this landmass?", which is what --rivers answers.

The "coast" class is gone with the guesswork. Shoreline tiles are not a third
thing: $07, $16, $18 and $27 carry the ship and refuse the party exactly as the
open sea does, while $06, $08, $26 and $28 are ordinary walkable land the ship
cannot enter. The old --no-coast switch existed to hedge between those two
readings and had nothing left to hedge.

Two results this tool does NOT reproduce, recorded here so nobody chases them
again. An earlier session's note claims that on FFR_03409C3E_GsBKsXSF the ship
plus canoe reaches Gaia, Lefein and Castle of Ordeals, via one river mouth at
(134, 33). On that ROM this tool gives Gaia False and no river mouth touching
Gaia's landmass at all -- (134, 33) is one of twelve mouths on the map, none of
them adjacent to that continent. Ordeals is reachable; Gaia and Lefein are not.
The seed's flags say why: MapGaiaMountainPass, MapHighwayToOrdeals,
MapLefeinRiver and MapBridgeLefein are all off and OwMapExchange is None, so
this is the stock overworld, on which Gaia is airship-only exactly as in
vanilla. The canoe mechanism itself is real; the seed-specific conclusion was
not.

Reading the table rather than guessing changes the landmass numbers a great
deal, which is worth knowing when comparing against an older run of this file:
on that same ROM the guessed classes had Coneria and Pravoka sharing one
3223-tile continent when they are 1077 and 1673 tiles and separate, and had
Castle of Ordeals on 1090 tiles rather than its actual 87. The set of places the
ship and canoe reach did not move.

Usage:
    tools/overworld_reach.py ROM                 # ship vs ship+canoe
    tools/overworld_reach.py ROM --rivers        # river mouths onto a landmass
    tools/overworld_reach.py ROM --at 221 28     # can the party get to this tile?

--at and --seed both mean a tile the party stands on, not a tile the ship
crosses. Ocean and river coordinates are rejected or answered False on purpose.
"""

import argparse
import sys
from collections import deque

INES_HEADER = 0x10
BANK_SIZE = 0x4000
OW_PTR_TBL = INES_HEADER + BANK_SIZE          # lut_OWPtrTbl, bank 1 at $8000
OW_TILESET_PROP = INES_HEADER                 # lut_OWTileset, bank 0 at $8000
OW_DIM = 256
OW_TILES = 128

# The vehicle bits, which are also the "may not enter" bits in property byte 0.
FOOT, CANOE, SHIP = 0x01, 0x02, 0x04
OWTP_DOCKSHIP = 0x20

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


class Overworld:
    """The decompressed map, plus the table that says who may stand on what."""

    def __init__(self, rom):
        self.rows = decompress_ow(rom)
        self.prop = rom[OW_TILESET_PROP:OW_TILESET_PROP + OW_TILES * 2]

    def at(self, x, y):
        """Property byte 0 of the tile at (x, y)."""
        return self.prop[self.rows[y][x] * 2]

    def allows(self, x, y, vehicle):
        """bank_0F.asm:1139: a set bit is this vehicle being refused."""
        return (self.at(x, y) & vehicle) == 0

    def docks(self, x, y):
        """Where the ship can be left, and therefore where it can be found."""
        return (self.at(x, y) & OWTP_DOCKSHIP) != 0

    def neighbours(self, x, y):
        # Modulo, because the game's own coordinates are 8-bit and wrap. On the
        # stock overworld every edge is open sea, so it never comes up; it would
        # on an OwMapExchange map with land against an edge, and there the wrap
        # is what the party would actually do.
        return [((x + dx) % OW_DIM, (y + dy) % OW_DIM)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]


def reach(w, start, canoe):
    """Tiles the party can end up standing on, starting from `start`.

    The walk tracks which vehicle you are in; only the land it puts you on comes
    back. See the note at the return.

    The three move handlers at bank_0F.asm:540-628, transcribed. Each vehicle
    moves onto any tile its own bit is clear on; where it is not, the game tries
    to change vehicles instead:

      on foot   board the canoe on a canoe tile, or the ship on the tile it is
                docked at
      in ship   board the canoe on a canoe tile -- the sea-to-river step, and
                the only way onto the northern continent short of the airship
                -- or step off onto a tile that is both walkable and flagged
                OWTP_DOCKSHIP, which is what docking is
      in canoe  step off onto any walkable tile

    Boarding the ship is modelled as "any dock tile you can walk to", which
    assumes the ship can be sailed to that dock. The one thing it cannot model
    is the canoe carrying you back out to sea: BoardShip wants the ship at the
    tile you are standing on, and where the ship actually is is not something a
    reachability walk tracks. It costs nothing here -- the search starts at sea,
    so every tile the ship can be on has already been walked.
    """
    seen, q = set(), deque()

    def push(s):
        if s not in seen:
            seen.add(s)
            q.append(s)

    push(start)
    while q:
        x, y, mode = q.popleft()
        for nx, ny in w.neighbours(x, y):
            if mode == "sea":
                if w.allows(nx, ny, SHIP):
                    push((nx, ny, "sea"))
                elif canoe and w.allows(nx, ny, CANOE):
                    push((nx, ny, "river"))
                elif w.allows(nx, ny, FOOT) and w.docks(nx, ny):
                    push((nx, ny, "land"))
            elif mode == "river":
                if w.allows(nx, ny, CANOE):
                    push((nx, ny, "river"))
                elif w.allows(nx, ny, FOOT):
                    push((nx, ny, "land"))
            else:
                if w.allows(nx, ny, FOOT):
                    push((nx, ny, "land"))
                elif canoe and w.allows(nx, ny, CANOE):
                    push((nx, ny, "river"))
                elif w.allows(nx, ny, SHIP) and w.docks(x, y):
                    push((nx, ny, "sea"))
    # Only the tiles the party ends up standing on. The walk visits every ocean
    # tile the ship crosses and every river tile the canoe follows, and
    # collapsing all three modes to bare coordinates made --at answer True for
    # open sea -- a tile nothing can ever stand on, reported as reachable.
    return {(x, y) for x, y, mode in seen if mode == "land"}


def landmass(w, seed):
    """Tiles walkable on foot from `seed`, ignoring every vehicle.

    The seed has to be land. Starting on water gives a one-tile "landmass" with
    no dock on it and no river mouth touching it, which is not an error message
    -- it is the same shape as the real answer this tool is usually asked for,
    and NONE is the conclusion the notes above draw about Gaia.
    """
    x, y = seed
    if not (0 <= x < OW_DIM and 0 <= y < OW_DIM):
        sys.exit(f"--seed {x} {y} is off a {OW_DIM}x{OW_DIM} overworld")
    if not w.allows(x, y, FOOT):
        sys.exit(f"--seed {x} {y} is tile ${w.rows[y][x]:02X}, which the party "
                 "cannot stand on -- a landmass has to start on land")
    seen, q = {seed}, deque([seed])
    while q:
        x, y = q.popleft()
        for nx, ny in w.neighbours(x, y):
            if (nx, ny) not in seen and w.allows(nx, ny, FOOT):
                seen.add((nx, ny))
                q.append((nx, ny))
    return seen


def print_rivers(w, seed):
    mass = landmass(w, seed)
    print(f"landmass around {seed}: {len(mass)} tiles, "
          f"{sum(1 for p in mass if w.docks(*p))} dock tiles on it")
    mouths = []
    for y in range(OW_DIM):
        for x in range(OW_DIM):
            # A river tile: the canoe goes there and the party cannot walk it.
            if not w.allows(x, y, CANOE) or w.allows(x, y, FOOT):
                continue
            adj = w.neighbours(x, y)
            if (any(w.allows(a, b, SHIP) for a, b in adj)
                    and any(p in mass for p in adj)):
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
    args = ap.parse_args()

    with open(args.rom, "rb") as f:
        rom = f.read()
    if rom[:4] != b"NES\x1a":
        sys.exit("not an iNES ROM")
    w = Overworld(rom)

    if args.at and not all(0 <= v < OW_DIM for v in args.at):
        sys.exit(f"--at {args.at[0]} {args.at[1]} is off a {OW_DIM}x{OW_DIM} overworld")

    if args.rivers:
        print_rivers(w, tuple(args.seed))
        return

    for canoe in (False, True):
        r = reach(w, (*OPEN_SEA, "sea"), canoe)
        label = "ship + canoe" if canoe else "ship"
        print(f"{label:<13} {len(r):>6} tiles the party can stand on")
        if args.at:
            at = tuple(args.at)
            why = "" if w.allows(*at, FOOT) else "  (nothing can stand on this tile)"
            print(f"              {at}: {at in r}{why}")
        else:
            hits = sorted(n for n, p in PLACES.items() if p in r)
            print(f"              places: {hits}")


if __name__ == "__main__":
    main()
