#!/usr/bin/env python3
"""Read an FFR cartridge's entrance/floor shuffle and route between maps.

FFR moves what is *behind* a door, not where the door sits, so the shuffle lives
entirely in the teleport lookup tables. Read those and the map tile data and you
have the whole graph: which overworld door opens into which map, and which
staircase inside each map leads where.

Grounded in BenWenger's FinalFantasyDisassembly and FFR's own patches:

  Constants.inc:89    BANK_OWMAP        = $01
  Constants.inc:95    BANK_TELEPORTINFO = $00
  Constants.inc:449   lut_OWPtrTbl      = $8000  (BANK_OWMAP)
  Constants.inc:469   lut_OWTileset     = $8000  (BANK_OWINFO = $00) -- one page,
                                                 128 tiles x 2 property bytes
  Constants.inc:486   lut_EntrTele_X/Y/Map = $AC00/$AC20/$AC40  (32 entries)
  Constants.inc:484   lut_ExitTele_X/Y     = $AC60/$AC70        (16 entries)
  Constants.inc:481   lut_NormTele_X/Y/Map = $AD00/$AD40/$AD80  (64 entries)
  Constants.inc:299   TP_SPEC_DOOR/LOCKED/CLOSEROOM/TREASURE ... (byte 0, bits 1-4)
  Constants.inc:317   TP_TELE_EXIT/NORM/WARP                    (byte 0, bits 6-7)
  Constants.inc:326   TP_NOMOVE                                 (byte 0, bit 0)
  bank_0F.asm:321     BIT tileprop+1 / BMI @Teleport -- the OVERWORLD test is on
                      byte 1 bit 7, and the id is byte 1 & $3F
  bank_0F.asm:2234    LDX tileprop+1 -- the STANDARD MAP norm-teleport id is the
                      whole of byte 1, unmasked, even in vanilla
  bank_0F.asm:3269    lut_SMMoveJmpTbl -- which specials block movement
  bank_0F.asm:3470    SMMove_Door -- TP_SPEC_LOCKED needs item_mystickey
  bank_0F.asm:2451    IsObjectInPath -- map objects block a step too. Most get
                      shoved aside, but the Rod and Lute plates do not: they are
                      item gates implemented as NPCs rather than tiles.
  Constants.inc:263   OBJID_RODPLATE = $16, OBJID_LUTEPLATE = $17
  Constants.inc:444   lut_MapObjects = $B400 (BANK_OBJINFO = $00), stride 48

  FF1Randomizer/FF1Lib/GlobalHacks/GlobalHacks.cs:208
      ExpandNormalTeleporters() copies lut_NormTele_X/Y/Map into
      BANK_EXTTELEPORTINFO = $0F at $B000/$B100/$B200, 256 entries each.
  FF1Randomizer/FF1Lib/asm/0F_9200_TeleportXYInroom.asm
      the room-to-room patch reads those extended tables. The shuffle is written
      to the extended copy; on a shuffled seed the vanilla $AD80 table still holds
      near-vanilla data and is the wrong table to read. --tables shows both.
      The same file's $9200 routine also steals the top bit of each coordinate:
      bit 7 of Y says "the X high bit is meaningful", and bit 7 of X is then the
      "arrive inside a room" flag. A raw coordinate is therefore not a
      coordinate -- Elfland Castle's entrance reads $9F, which is y=31, not 159.

Two traps, both of which produced a wrong answer before:

  * The teleport bits are in property byte 0. Byte 1 is a payload whose meaning
    depends on byte 0 -- chest id, teleport id, or battle formation. Testing
    byte 1 for the $C0 teleport bits makes every treasure chest with an id in
    $80-$BF look like a staircase. --self-check asserts this can't come back.
  * The standard-map teleport id is the full byte. Masking it to $3F collapses
    distinct destinations onto each other on a floor-shuffled seed.

Usage:
    tools/entrance_graph.py ROM --dump
    tools/entrance_graph.py ROM --to DwarfCave [--have key]
    tools/entrance_graph.py ROM --to-npc smith
    tools/entrance_graph.py ROM --tables
    tools/entrance_graph.py ROM --self-check
"""

import argparse
import json
import os
import sys
from collections import deque

from extract_chests import (
    INES_HEADER, BANK_SIZE, SM_DATA_BASE, SM_PTR_TBL, TILESET_PROP, TILESET_LUT,
    MAP_COUNT, MAP_DIM, PROP_STRIDE, decompress_map,
)

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- ROM geometry

def bank_off(bank, addr):
    """Flat file offset of a $8000-based address in a given PRG bank."""
    return INES_HEADER + bank * BANK_SIZE + (addr - 0x8000)

BANK_TELEPORTINFO = 0x00
BANK_EXTTELEPORTINFO = 0x0F
BANK_OWMAP = 0x01

ENTR_TELE_X, ENTR_TELE_Y, ENTR_TELE_MAP = 0xAC00, 0xAC20, 0xAC40
EXIT_TELE_X, EXIT_TELE_Y = 0xAC60, 0xAC70
NORM_TELE_X, NORM_TELE_Y, NORM_TELE_MAP = 0xAD00, 0xAD40, 0xAD80
NORM_TELE_X_EXT, NORM_TELE_Y_EXT, NORM_TELE_MAP_EXT = 0xB000, 0xB100, 0xB200

OW_PTR_TBL = bank_off(BANK_OWMAP, 0x8000)
OW_TILESET_PROP = INES_HEADER + 0x0000    # lut_OWTileset, $8000 in bank 0
OW_DIM = 256
OW_TILES = 128

ENTR_COUNT = 32
EXIT_COUNT = 16
NORM_COUNT_EXT = 256

# ------------------------------------------------------------ tile properties

TP_TELE_MASK = 0xC0
TP_TELE_WARP = 0x40
TP_TELE_NORM = 0x80
TP_TELE_EXIT = 0xC0

TP_SPEC_MASK = 0x1E
TP_NOMOVE = 0x01

TP_SPEC_DOOR = 0x02
TP_SPEC_LOCKED = 0x04
TP_SPEC_CLOSEROOM = 0x06
TP_SPEC_TREASURE = 0x08
TP_SPEC_CROWN = 0x0E
TP_SPEC_CUBE = 0x10
TP_SPEC_4ORBS = 0x12

COORD_MASK = 0x3F     # maps are 64x64; the top bits are flags, see $9200 above
INROOM_FLAG = 0x80


def coord(v):
    return v & COORD_MASK


def inroom(x_raw, y_raw):
    """$9200: the Y high bit arms the flag, the X high bit is its value."""
    return bool(y_raw & INROOM_FLAG) and bool(x_raw & INROOM_FLAG)

# lut_SMMoveJmpTbl (bank_0F.asm:3269): the only specials that can refuse a step.
# Treasure always refuses (SMMove_Treasure, bank_0F.asm:3291). The rest refuse
# only until you hold the item. Rod and Lute tiles do NOT gate movement -- both
# handlers are a bare CLC/RTS; the item check happens when you use them.
GATED_SPECIALS = {
    TP_SPEC_LOCKED: "key",
    TP_SPEC_CROWN: "crown",
    TP_SPEC_CUBE: "cube",
    TP_SPEC_4ORBS: "orbs",
}
ITEM_NAMES = {
    "key": "Mystic Key", "crown": "Crown", "cube": "Warp Cube",
    "orbs": "all four Orbs", "rod": "Rod", "lute": "Lute",
}

# Objects that block a step and are never shoved out of the way. Stride and
# record layout are extract_npcs.py's, and its docstring explains why 48.
MAP_OBJECTS = INES_HEADER + (0xB400 - 0x8000)
OBJS_PER_MAP, OBJ_RECORD, OBJ_STRIDE = 15, 3, 48
GATED_OBJECTS = {0x16: "rod", 0x17: "lute"}

# The map-object ids worth routing to by name. OBJID_* in Constants.inc:247,
# except $05, which the disassembly leaves unnamed -- the pack's
# scripts/autotracking/ram_mapping.lua pins it as the Elf Doctor, the NPC the
# Herb is handed to.
NPC_IDS = {
    "garland": 0x02, "princess": 0x03, "bikke": 0x04, "elfdoctor": 0x05,
    "elfprince": 0x06, "astos": 0x07, "nerrick": 0x08, "smith": 0x09,
    "matoya": 0x0A, "unne": 0x0B, "vampire": 0x0C, "sarda": 0x0D,
    "bahamut": 0x0E, "subengineer": 0x10, "fairy": 0x13, "titan": 0x14,
}

# ------------------------------------------------------------------- id tables

# FF1Lib/Enums.cs:4 -- enum MapIndex. This is the ROM's own map order; the pack's
# scripts/autotracking/mapValues.lua carries display labels for the same ids and
# they are NOT interchangeable (it calls map 22 "Marsh Split" and map 27
# "Marsh B1", one floor off from the names here). Tab labels are loaded
# separately, as an alias, so the two tables can't be confused.
MAP_NAMES = [
    "ConeriaTown", "Pravoka", "Elfland", "Melmond", "CrescentLake", "Gaia",
    "Onrac", "Lefein", "ConeriaCastle1F", "ElflandCastle", "NorthwestCastle",
    "CastleOrdeals1F", "TempleOfFiends", "EarthCaveB1", "GurguVolcanoB1",
    "IceCaveB1", "Cardia", "BahamutCaveB1", "Waterfall", "DwarfCave",
    "MatoyasCave", "SardasCave", "MarshCaveB1", "MirageTower1F",
    "ConeriaCastle2F", "CastleOrdeals2F", "CastleOrdeals3F", "MarshCaveB2",
    "MarshCaveB3", "EarthCaveB2", "EarthCaveB3", "EarthCaveB4", "EarthCaveB5",
    "GurguVolcanoB2", "GurguVolcanoB3", "GurguVolcanoB4", "GurguVolcanoB5",
    "IceCaveB2", "IceCaveB3", "BahamutCaveB2", "MirageTower2F", "MirageTower3F",
    "SeaShrineB5", "SeaShrineB4", "SeaShrineB3", "SeaShrineB2", "SeaShrineB1",
    "SkyPalace1F", "SkyPalace2F", "SkyPalace3F", "SkyPalace4F", "SkyPalace5F",
    "TempleOfFiendsRevisited1F", "TempleOfFiendsRevisited2F",
    "TempleOfFiendsRevisited3F", "TempleOfFiendsRevisitedEarth",
    "TempleOfFiendsRevisitedFire", "TempleOfFiendsRevisitedWater",
    "TempleOfFiendsRevisitedAir", "TempleOfFiendsRevisitedChaos", "TitansTunnel",
]
assert len(MAP_NAMES) == MAP_COUNT

# FF1Lib/Enums.cs:255 -- enum OverworldTeleportIndex.
DOOR_NAMES = [
    "Cardia1", "Coneria", "Pravoka", "Elfland", "Melmond", "CrescentLake",
    "Gaia", "Onrac", "Lefein", "ConeriaCastle1", "ElflandCastle",
    "NorthwestCastle", "CastleOrdeals1", "TempleOfFiends1", "EarthCave1",
    "GurguVolcano1", "IceCave1", "Cardia2", "BahamutCave1", "Waterfall",
    "DwarfCave", "MatoyasCave", "SardasCave", "MarshCave1", "MirageTower1",
    "TitansTunnelEast", "TitansTunnelWest", "Cardia4", "Cardia5", "Cardia6",
    "Unused1", "Unused2",
]
assert len(DOOR_NAMES) == ENTR_COUNT


def tab_labels():
    """map id -> the pack's PopTracker tab label, for cross-reference only."""
    path = os.path.join(HERE, os.pardir, "scripts", "autotracking", "mapValues.lua")
    out = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line.startswith("["):
                    continue
                key, _, rest = line[1:].partition("]")
                label = rest.split('"')[1] if '"' in rest else None
                if label:
                    out[int(key)] = label.rsplit("/", 1)[-1]
    except OSError:
        pass
    return out


# ------------------------------------------------------------------ ROM reader

class Rom:
    def __init__(self, path):
        self.data = open(path, "rb").read()
        if self.data[:4] != b"NES\x1a":
            sys.exit("not an iNES ROM")
        self.path = path

    def at(self, bank, addr, n):
        o = bank_off(bank, addr)
        return self.data[o:o + n]


# ------------------------------------------------------------- overworld doors

def decompress_ow(rom):
    """The overworld is 256 rows, each RLE'd and pointed to from lut_OWPtrTbl.

    Row encoding differs from DecompressMap: <$80 is a literal tile, $FF fills
    the rest of the row with ocean, and anything else is (tile | $80) followed
    by a run length (0 means 256).
    """
    rows = []
    for i in range(OW_DIM):
        ptr = int.from_bytes(rom.data[OW_PTR_TBL + 2 * i:OW_PTR_TBL + 2 * i + 2], "little")
        raw = rom.data[INES_HEADER + ptr - 0x4000:]
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


def door_positions(rom):
    """entrance id -> [(x, y), ...] overworld tiles that open it.

    bank_0F.asm:321 tests byte 1 bit 7 for "this is a teleport tile" and
    bank_0F.asm:396 masks the id with $3F. Note this is byte *1* -- the
    overworld's property layout is not the standard map's.
    """
    props = rom.data[OW_TILESET_PROP:OW_TILESET_PROP + OW_TILES * 2]
    tele = {}
    for t in range(OW_TILES):
        b1 = props[t * 2 + 1]
        if b1 & 0x80:
            tele[t] = b1 & 0x3F
    if not tele:
        return {}
    grid = decompress_ow(rom)
    out = {}
    for y in range(OW_DIM):
        for x in range(OW_DIM):
            idx = tele.get(grid[y][x])
            if idx is not None:
                out.setdefault(idx, []).append((x, y))
    return out


# ------------------------------------------------------------------- the graph

class Graph:
    def __init__(self, rom):
        self.rom = rom
        self.entr_x = rom.at(BANK_TELEPORTINFO, ENTR_TELE_X, ENTR_COUNT)
        self.entr_y = rom.at(BANK_TELEPORTINFO, ENTR_TELE_Y, ENTR_COUNT)
        self.entr_map = rom.at(BANK_TELEPORTINFO, ENTR_TELE_MAP, ENTR_COUNT)
        self.exit_x = rom.at(BANK_TELEPORTINFO, EXIT_TELE_X, EXIT_COUNT)
        self.exit_y = rom.at(BANK_TELEPORTINFO, EXIT_TELE_Y, EXIT_COUNT)
        self.norm_x = rom.at(BANK_EXTTELEPORTINFO, NORM_TELE_X_EXT, NORM_COUNT_EXT)
        self.norm_y = rom.at(BANK_EXTTELEPORTINFO, NORM_TELE_Y_EXT, NORM_COUNT_EXT)
        self.norm_map = rom.at(BANK_EXTTELEPORTINFO, NORM_TELE_MAP_EXT, NORM_COUNT_EXT)
        self.tilesets = rom.data[TILESET_LUT:TILESET_LUT + MAP_COUNT]
        self.grids = {}
        self.doors = door_positions(rom)

    def grid(self, map_id):
        """(tiles, prop0, prop1) for a map, as flat 64*64 lists."""
        if map_id not in self.grids:
            ptr = int.from_bytes(
                self.rom.data[SM_PTR_TBL + map_id * 2:SM_PTR_TBL + map_id * 2 + 2], "little")
            tiles = decompress_map(self.rom.data, SM_DATA_BASE + ptr)
            base = TILESET_PROP + self.tilesets[map_id] * PROP_STRIDE
            p0 = [self.rom.data[base + t * 2] for t in tiles]
            p1 = [self.rom.data[base + t * 2 + 1] for t in tiles]
            self.grids[map_id] = (tiles, p0, p1)
        return self.grids[map_id]

    def walkable(self, b0, have):
        """CanPlayerMoveSM, bank_0F.asm:2449.

        TP_NOMOVE is not an unconditional wall. The game blocks only when the
        special bits are *all clear* and NOMOVE is set -- a plain wall. If the
        tile carries a special, the jump table decides and NOMOVE is thrown
        away. Room doors are exactly this case: Marsh Cave B1's door at (35,54)
        is TP_SPEC_DOOR | TP_NOMOVE, and reading NOMOVE on its own seals every
        room in the game shut. That is what hid the Marsh Cave -> Sea Shrine B3
        -> Bahamut -> Dwarf Cave chain.
        """
        if (b0 & (TP_SPEC_MASK | TP_NOMOVE)) == TP_NOMOVE:
            return False
        spec = b0 & TP_SPEC_MASK
        if spec == TP_SPEC_TREASURE:
            return False
        need = GATED_SPECIALS.get(spec)
        return need is None or need in have

    def objects(self, map_id):
        """[(object id, x, y)] for one map, from lut_MapObjects."""
        base = MAP_OBJECTS + map_id * OBJ_STRIDE
        out = []
        for i in range(OBJS_PER_MAP):
            oid = self.rom.data[base + i * OBJ_RECORD]
            if oid:
                out.append((oid,
                            self.rom.data[base + i * OBJ_RECORD + 1] & COORD_MASK,
                            self.rom.data[base + i * OBJ_RECORD + 2] & COORD_MASK))
        return out

    def blocking_objects(self, map_id, have):
        return {(x, y) for oid, x, y in self.objects(map_id)
                if GATED_OBJECTS.get(oid) not in (None, *have)}

    def teleports(self, map_id):
        """[(x, y, kind, payload)] for every teleport tile on a map."""
        _, p0, p1 = self.grid(map_id)
        out = []
        for pos, b0 in enumerate(p0):
            kind = b0 & TP_TELE_MASK
            if kind:
                out.append((pos % MAP_DIM, pos // MAP_DIM, kind, p1[pos]))
        return out

    def floor_walk(self, map_id, start, have, stop_on_teleport=True):
        """Tiles reachable on foot from `start`, as {(x, y): steps}.

        Teleport tiles end the walk by default -- stepping on one takes you off
        the floor, so you cannot route *through* a staircase.
        """
        _, p0, _ = self.grid(map_id)
        sx, sy = start[0] % MAP_DIM, start[1] % MAP_DIM
        tele_at = {(x, y) for x, y, _, _ in self.teleports(map_id)} if stop_on_teleport else set()
        blocked = self.blocking_objects(map_id, have)
        seen = {(sx, sy): 0}
        q = deque([(sx, sy)])
        while q:
            x, y = q.popleft()
            if (x, y) in tele_at and (x, y) != (sx, sy):
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < MAP_DIM and 0 <= ny < MAP_DIM):
                    continue
                if (nx, ny) in seen or (nx, ny) in blocked:
                    continue
                if not self.walkable(p0[ny * MAP_DIM + nx], have):
                    continue
                seen[(nx, ny)] = seen[(x, y)] + 1
                q.append((nx, ny))
        return seen

    def can_reach_npc(self, map_id, start, spot, have):
        """You talk to an NPC from an adjacent tile; its own tile is blocked."""
        walk = self.floor_walk(map_id, start, have)
        nx, ny = spot["tile_col"], spot["tile_row"]
        best = [walk[(nx + dx, ny + dy)]
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if (nx + dx, ny + dy) in walk]
        return min(best) if best else None

    def reachable_teleports(self, map_id, start, have):
        """Teleport tiles you can actually walk to from `start` on this map.

        Floors are not fully connected -- that is the whole point of a locked
        door -- so "the graph has an edge" is not the same as "you can take it".
        """
        _, p0, _ = self.grid(map_id)
        sx, sy = start
        sx, sy = sx % MAP_DIM, sy % MAP_DIM
        seen = {(sx, sy)}
        q = deque([(sx, sy, 0)])
        found = {}
        tele_at = {(x, y): (kind, pay) for x, y, kind, pay in self.teleports(map_id)}
        blocked = self.blocking_objects(map_id, have)
        while q:
            x, y, d = q.popleft()
            hit = tele_at.get((x, y))
            if hit and (x, y) != (sx, sy):
                found[(x, y)] = (hit[0], hit[1], d)
                continue          # stepping on it takes you off the floor
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < MAP_DIM and 0 <= ny < MAP_DIM):
                    continue
                if (nx, ny) in seen:
                    continue
                if (nx, ny) in blocked:
                    continue
                if not self.walkable(p0[ny * MAP_DIM + nx], have):
                    continue
                seen.add((nx, ny))
                q.append((nx, ny, d + 1))
        return found

    def starts(self):
        """[(door_id, map_id, (x, y))] for every overworld entrance you can take.

        A door with no tile on the overworld cannot be entered, whatever its
        row in lut_EntrTele_Map says. Doors 30 and 31 are FFR's unused pair and
        their map bytes are ordinary small numbers, so admitting them routes
        the player in through a door that is not on the map -- and seeds the
        floor-link walk from rooms nothing opens into.

        The tile lookup is skipped entirely when the overworld's own tile
        properties named no entrance at all, since filtering on an empty table
        would leave nothing to route from.
        """
        out = []
        for i in range(ENTR_COUNT):
            m = self.entr_map[i]
            if m >= MAP_COUNT:
                continue
            if self.doors and i not in self.doors:
                continue
            out.append((i, m, (coord(self.entr_x[i]), coord(self.entr_y[i]))))
        return out

    def route(self, target_map, have, accept=None):
        """Shortest door-and-staircase chain into target_map, or None.

        `accept(map_id, arrive)` narrows what counts as having arrived. A floor
        is commonly entered at two different landing spots by two different
        staircase chains, and the chain with fewer hops is not always the one
        that lands on your side of a locked door -- so a caller that wants to
        reach something *on* the map has to say so, or it gets told the map is
        a dead end when only the first chain into it was.
        """
        if accept is None:
            def accept(map_id, arrive):
                return True
        best = None
        for door, m0, arrive0 in self.starts():
            prev = {(m0, arrive0): None}
            q = deque([(m0, arrive0)])
            while q:
                m, arrive = q.popleft()
                if m == target_map and accept(m, arrive):
                    break
                for (x, y), (kind, pay, steps) in self.reachable_teleports(m, arrive, have).items():
                    if kind != TP_TELE_NORM:
                        continue
                    dm = self.norm_map[pay]
                    if dm >= MAP_COUNT:
                        continue
                    nxt = (dm, (coord(self.norm_x[pay]), coord(self.norm_y[pay])))
                    if nxt in prev:
                        continue
                    prev[nxt] = (m, arrive, x, y, steps)
                    q.append(nxt)
            hits = [k for k in prev if k[0] == target_map and accept(*k)]
            if not hits:
                continue
            node = hits[0]
            path = []
            while prev[node] is not None:
                pm, pa, x, y, steps = prev[node]
                path.append((pm, pa, x, y, steps, node))
                node = (pm, pa)
            path.reverse()
            if best is None or len(path) < len(best[1]):
                best = (door, path, m0, arrive0)
        return best


# ------------------------------------------------------------------- reporting

def fmt_map(mid, tabs):
    """Canonical name, plus the pack's tab label when it actually differs.

    Every town's tab label is just "Overworld", which says nothing, so skip it.
    """
    name = MAP_NAMES[mid]
    tab = tabs.get(mid)
    if not tab or tab == "Overworld" or tab.replace(" ", "").replace("'", "") == name:
        return name
    return f"{name} [{tab}]"


def door_where(g, door):
    """Overworld tiles that open a door. Towns are a blob of several; caves one."""
    pos = g.doors.get(door, [])
    if not pos:
        return "-", ""
    first = f"{pos[0][0]}, {pos[0][1]}"
    extra = f" (+{len(pos) - 1} more tiles)" if len(pos) > 1 else ""
    return first, extra


def print_doors(g, tabs):
    print("All 32 overworld entrances")
    print(f"  {'#':>2}  {'door (still at its vanilla spot)':<20} {'overworld':<12} now opens into")
    for i in range(ENTR_COUNT):
        m = g.entr_map[i]
        where, _ = door_where(g, i)
        if m < MAP_COUNT:
            dest = fmt_map(m, tabs)
            same = "  (unchanged)" if DOOR_NAMES[i].rstrip("123") in MAP_NAMES[m] else ""
        else:
            # The unused pair is not the only way this happens -- --tables
            # counts out-of-range entries in these tables on real seeds.
            dest, same = f"?? ({m})", ""
        print(f"  {i:>2}  {DOOR_NAMES[i]:<20} {where:<12} {dest}{same}")


def print_floors(g, tabs, have):
    print()
    print("Floor links (staircase -> destination), as reached from each entry point")
    seen_pairs = set()
    for door, m0, arrive0 in g.starts():
        stack = [(m0, arrive0)]
        visited = {(m0, arrive0)}
        while stack:
            m, arrive = stack.pop()
            for (x, y), (kind, pay, steps) in g.reachable_teleports(m, arrive, have).items():
                if kind == TP_TELE_NORM:
                    dm = g.norm_map[pay]
                    if dm >= MAP_COUNT:
                        continue
                    key = (m, x, y, dm)
                    if key not in seen_pairs:
                        seen_pairs.add(key)
                        print(f"  {fmt_map(m, tabs):<28} ({x:>2},{y:>2}) -> "
                              f"{fmt_map(dm, tabs)} at "
                              f"({coord(g.norm_x[pay])},{coord(g.norm_y[pay])})")
                    nxt = (dm, (coord(g.norm_x[pay]), coord(g.norm_y[pay])))
                    if nxt not in visited:
                        visited.add(nxt)
                        stack.append(nxt)


def print_route(g, tabs, target, have, accept=None):
    return show_route(g, tabs, target, have, g.route(target, have, accept))


def show_route(g, tabs, target, have, r):
    print(f"=== route to {fmt_map(target, tabs)} ===")
    if r is None:
        print("  no route found from any overworld door"
              + (f" (carrying: {', '.join(sorted(have))})" if have else " with nothing in hand"))
        return None
    door, path, m0, arrive0 = r
    where, extra = door_where(g, door)
    print(f"  Enter the {DOOR_NAMES[door]} door"
          + (f" -- overworld {where}{extra}" if where != "-" else ""))
    print(f"    it opens into {fmt_map(m0, tabs)}, arriving at ({arrive0[0]},{arrive0[1]})")
    if not path:
        print("    you are already there")
    arrive = arrive0
    for pm, pa, x, y, steps, node in path:
        dm, da = node
        print(f"    in {fmt_map(pm, tabs)}: walk to the stairs at ({x},{y}), "
              f"{steps} steps -> {fmt_map(dm, tabs)} at ({da[0]},{da[1]})")
        arrive = da
    return arrive


def print_tables(g):
    van = g.rom.at(BANK_TELEPORTINFO, NORM_TELE_MAP, 0x40)
    ext = g.norm_map
    print("lut_NormTele_Map, vanilla ($AD80 bank $00) vs extended ($B200 bank $0F)")
    print(f"  low $40 agree: {bytes(van) == bytes(ext[:0x40])}")
    if bytes(van) != bytes(ext[:0x40]):
        diff = [i for i in range(0x40) if van[i] != ext[i]]
        print(f"  they differ at {len(diff)} of 64 entries -- the extended copy is the")
        print("  one the running game reads, so that is what this tool uses.")
    bad = [i for i, v in enumerate(ext) if v >= MAP_COUNT]
    print(f"  extended entries out of range (>= {MAP_COUNT}): {len(bad)} of {NORM_COUNT_EXT}")


def self_check(g):
    """The byte-0/byte-1 regression test.

    Every tile this tool calls a staircase must not be a treasure chest. Reading
    the teleport bits out of property byte 1 instead of byte 0 makes chests with
    ids in $80-$BF read as normal teleports, which is exactly how an earlier
    router sent a route through a chest on Sea Shrine B1.
    """
    path = os.path.join(HERE, "chest_positions.json")
    try:
        with open(path) as f:
            chests = json.load(f)
    except OSError:
        print(f"self-check SKIPPED: {path} not found")
        return True
    chest_tiles = {(p["map_id"], p["tile_col"], p["tile_row"])
                   for v in chests.values() for p in v}
    clashes = []
    for m in range(MAP_COUNT):
        for x, y, kind, _ in g.teleports(m):
            if (m, x, y) in chest_tiles:
                clashes.append((m, x, y, kind))
    if clashes:
        print(f"self-check FAILED: {len(clashes)} 'staircases' are treasure chests")
        for m, x, y, kind in clashes[:10]:
            print(f"  {MAP_NAMES[m]} ({x},{y}) kind ${kind:02X}")
        return False
    total = sum(len(g.teleports(m)) for m in range(MAP_COUNT))
    norm = sum(1 for m in range(MAP_COUNT)
               for _, _, k, _ in g.teleports(m) if k == TP_TELE_NORM)
    print(f"self-check OK: {total} teleport tiles across {MAP_COUNT} maps "
          f"({norm} of them staircases; the rest are mostly the warp-out filler "
          "that surrounds every town), none of them a treasure chest")
    return True


def resolve_map(name):
    lowered = name.lower().replace(" ", "").replace("'", "")
    exact = [i for i, n in enumerate(MAP_NAMES) if n.lower() == lowered]
    if exact:
        return exact[0]
    part = [i for i, n in enumerate(MAP_NAMES) if lowered in n.lower()]
    if len(part) == 1:
        return part[0]
    if not part:
        sys.exit(f"no map matches {name!r}")
    sys.exit(f"{name!r} is ambiguous: {', '.join(MAP_NAMES[i] for i in part)}")


def resolve_npc(g, name):
    """Where an NPC stands, read from the routed ROM's own object table.

    tools/npc_positions.json is derived from a vanilla cartridge and covers only
    the ten NPCs the tracker needs -- not the Elf Doctor. Reading lut_MapObjects
    out of the ROM in hand costs nothing and stays right if a seed moves anyone.
    """
    key = name.lower().replace(" ", "").replace("'", "")
    if key not in NPC_IDS:
        sys.exit(f"no NPC {name!r}; known: {', '.join(sorted(NPC_IDS))}")
    oid = NPC_IDS[key]
    for m in range(MAP_COUNT):
        for got, x, y in g.objects(m):
            if got == oid:
                return {"map_id": m, "tile_col": x, "tile_row": y}
    sys.exit(f"{name} (object ${oid:02X}) does not appear on any map in this ROM")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--to", help="destination map name, e.g. DwarfCave")
    ap.add_argument("--to-npc", help="destination NPC name, e.g. smith")
    ap.add_argument("--have", default="",
                    help="comma-separated items in hand: " + ",".join(sorted(ITEM_NAMES)))
    ap.add_argument("--dump", action="store_true", help="all doors and floor links")
    ap.add_argument("--tables", action="store_true", help="vanilla vs extended teleport tables")
    ap.add_argument("--self-check", action="store_true", help="staircases must not be chests")
    ap.add_argument("-o", "--out", help="write the graph as JSON")
    args = ap.parse_args()

    g = Graph(Rom(args.rom))
    tabs = tab_labels()
    have = {s.strip() for s in args.have.split(",") if s.strip()}
    unknown = have - set(ITEM_NAMES)
    if unknown:
        sys.exit(f"unknown item(s): {', '.join(sorted(unknown))}")

    ok = True
    if args.self_check:
        ok = self_check(g)
    if args.tables:
        print_tables(g)
    if args.dump:
        print_doors(g, tabs)
        print_floors(g, tabs, have)
    if args.to:
        print()
        print_route(g, tabs, resolve_map(args.to), have)
    if args.to_npc:
        spot = resolve_npc(g, args.to_npc)
        print()
        print(f"{args.to_npc} stands in {MAP_NAMES[spot['map_id']]} at "
              f"({spot['tile_col']},{spot['tile_row']})")

        def lands_by_npc(map_id, arrive):
            return g.can_reach_npc(map_id, arrive, spot, have) is not None

        # Ask for a landing spot he can be walked to from, not merely for the
        # right map. Falling back to the plain route keeps "the map is
        # reachable but he is not" reading differently from "there is no way
        # in at all", which are not the same answer.
        r = g.route(spot["map_id"], have, lands_by_npc)
        reached = r is not None
        arrive = show_route(g, tabs, spot["map_id"], have,
                            r if reached else g.route(spot["map_id"], have))
        if arrive is not None and reached:
            steps = g.can_reach_npc(spot["map_id"], arrive, spot, have)
            print(f"    walk {steps} more steps to {args.to_npc} at "
                  f"({spot['tile_col']},{spot['tile_row']})")
        elif arrive is not None:
            ok = False
            print(f"    ...but you cannot walk to {args.to_npc} from anywhere this"
                  " map can be entered"
                  + (f" carrying only {', '.join(sorted(have))}" if have
                     else " with nothing in hand")
                  + " -- try --have key")
    if not any((args.self_check, args.tables, args.dump, args.to, args.to_npc, args.out)):
        print_doors(g, tabs)

    if args.out:
        payload = {
            "doors": [
                {"id": i, "name": DOOR_NAMES[i],
                 "overworld": g.doors.get(i, []),
                 "map_id": g.entr_map[i],
                 "map": MAP_NAMES[g.entr_map[i]] if g.entr_map[i] < MAP_COUNT else None,
                 "arrive": [coord(g.entr_x[i]), coord(g.entr_y[i])],
                 "in_room": inroom(g.entr_x[i], g.entr_y[i])}
                for i in range(ENTR_COUNT)],
            "maps": [
                {"id": m, "name": MAP_NAMES[m], "tab": tabs.get(m),
                 "teleports": [
                     {"x": x, "y": y,
                      "kind": {TP_TELE_NORM: "norm", TP_TELE_EXIT: "exit",
                               TP_TELE_WARP: "warp"}[k],
                      "id": pay,
                      "to_map": g.norm_map[pay] if k == TP_TELE_NORM else None,
                      "to": [coord(g.norm_x[pay]), coord(g.norm_y[pay])]
                            if k == TP_TELE_NORM
                            else ([g.exit_x[pay], g.exit_y[pay]]
                                  if k == TP_TELE_EXIT and pay < EXIT_COUNT else None)}
                     for x, y, k, pay in g.teleports(m)]}
                for m in range(MAP_COUNT)],
        }
        with open(args.out, "w") as f:
            json.dump(payload, f, indent=1)
        print(f"wrote {args.out}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
