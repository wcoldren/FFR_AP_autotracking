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

Three traps, all of which produced a wrong answer before:

  * The teleport bits are in property byte 0. Byte 1 is a payload whose meaning
    depends on byte 0 -- chest id, teleport id, or battle formation. Testing
    byte 1 for the $C0 teleport bits makes every treasure chest with an id in
    $80-$BF look like a staircase. --self-check asserts this can't come back.
  * The standard-map teleport id is the full byte. Masking it to $3F collapses
    distinct destinations onto each other on a floor-shuffled seed.
  * The maps are not in bank $04. FFR moves all 61 of them to bank $14 on every
    seed and repoints the engine's constant; banks 4-7 keep their untouched
    vanilla copies, so reading there yields vanilla topology for a cartridge
    that plays nothing like it. On a No-Overworld seed that showed up as 11
    floor links where the cartridge has 146 -- and the 11 were real vanilla
    stairs, so nothing looked wrong. extract_chests.standard_map_bank asks the
    image; --self-check asserts the answer is the bank the engine reads.

Usage:
    tools/entrance_graph.py ROM --dump
    tools/entrance_graph.py ROM --to DwarfCave [--have key]
    tools/entrance_graph.py ROM --to-npc smith
    tools/entrance_graph.py ROM --tables
    tools/entrance_graph.py ROM --rolls
    tools/entrance_graph.py ROM --self-check

Exit status: 0 all good, 1 --self-check failed, 2 the NPC asked for is not
reachable on this seed.
"""

import argparse
import json
import os
import sys
from collections import deque

from extract_chests import (
    INES_HEADER, BANK_SIZE, SM_BANK_VANILLA, SM_BANK_CONST_MIRROR,
    TILESET_PROP, TILESET_LUT, MAP_COUNT, MAP_DIM, PROP_STRIDE,
    decompress_map, map_data_base, standard_map_bank, _fixed_bank_off,
    OW_PTR_TBL, OW_DIM, decompress_ow,
)

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- ROM geometry

def bank_off(bank, addr):
    """Flat file offset of a $8000-based address in a given PRG bank."""
    return INES_HEADER + bank * BANK_SIZE + (addr - 0x8000)

BANK_TELEPORTINFO = 0x00
BANK_EXTTELEPORTINFO = 0x0F

ENTR_TELE_X, ENTR_TELE_Y, ENTR_TELE_MAP = 0xAC00, 0xAC20, 0xAC40
EXIT_TELE_X, EXIT_TELE_Y = 0xAC60, 0xAC70
NORM_TELE_X, NORM_TELE_Y, NORM_TELE_MAP = 0xAD00, 0xAD40, 0xAD80
NORM_TELE_X_EXT, NORM_TELE_Y_EXT, NORM_TELE_MAP_EXT = 0xB000, 0xB100, 0xB200

OW_TILESET_PROP = INES_HEADER + 0x0000    # lut_OWTileset, $8000 in bank 0
OW_TILES = 128
# OW_PTR_TBL and OW_DIM come from extract_chests, with decompress_ow.

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
    # What the No-Overworld gate NPCs want. They gate nothing on a standard
    # cartridge, where --have simply ignores them. "floater" is the item's own
    # name; No-Overworld renames it SIGIL on screen and nowhere else.
    "tnt": "TNT", "floater": "Floater", "canoe": "Canoe", "chime": "Chime",
    # The two objects SCMap gates by object id -- the sub engineer in Onrac and
    # the Titan in his tunnel. Both stand on a chokepoint on every cartridge,
    # standard included, so these are not a No-Overworld addition. See
    # object_gate_items() for how each one's item is read.
    "oxyale": "Oxyale", "ruby": "Ruby",
}
# What a No-Overworld player sees on the item screen. MetroidVaniaMap.cs:844
# renames exactly two items, and only the Floater is a gate -- MARK is the Earth
# Orb, which gates nothing, so it gets no alias here.
ITEM_ALIASES = {"sigil": "floater"}

# Objects that block a step and are never shoved out of the way. Stride and
# record layout are extract_npcs.py's, and its docstring explains why 48.
MAP_OBJECTS = INES_HEADER + (0xB400 - 0x8000)
OBJS_PER_MAP, OBJ_RECORD, OBJ_STRIDE = 15, 3, 48
GATED_OBJECTS = {0x16: "rod", 0x17: "lute"}

# ------------------------------------------------------------ the Black Orb
#
# The time warp back to the Temple of Fiends Revisited, and the third of the
# five object gates FF1Lib/Sanity/SCMap.cs:167-186 lists. The other four are the
# Rod and Lute plates above, and SubEngineer and Titan -- see object_gate_items.
#
# Vanilla gates that step twice: TempleOfFiends (20,17) carries TP_SPEC_4ORBS
# *and* the object, byte 0x92. FFR moves the requirement off the tile and onto
# the NPC -- BlackOrb.cs:286 Remove4OrbRequirementForToFRPortal() patches the
# portal walkable, and every FFR cartridge measured reads 0x80 there, standard
# and No-Overworld alike. A walk that models tiles and not objects therefore
# steps through the orb gate on every FFR seed.
#
# What the NPC wants is not fixed, which is why this is read rather than
# tabulated. The stock routine ANDs the four orb bytes; a shard-hunt seed gets
# `LDA $6035 / CMP #goal` instead (BlackOrb.cs:215-223), and a specific-orbs
# seed gets a shorter AND chain (:275-283). Measured on the oracle corpus: std,
# nov and nov2 carry the AND form, the shard cartridge carries the count.
#
# So this answers "orbs" only for the AND form and None for anything else. None
# leaves the walk stepping through, which is what it did before and is honest:
# a shard count is not something the item sweep can hold.
#
# The two AND forms are matched as whole sets, not as any four drawn from their
# union: the union spans $6031..$6035, and "any four of those five" accepts a
# mixed chain of three orbs plus the shard counter, installing a shard count as
# an orb gate -- the one reading this must not produce. Vanilla ANDs
# $6032..$6035; FFR's ShiftEarthOrbDown moves the Earth Orb to $6031 and the set
# becomes $6031..$6034. Order within a set is not fixed, so each is a set.
ORB_BYTE_SETS = (frozenset((0x6031, 0x6032, 0x6033, 0x6034)),
                 frozenset((0x6032, 0x6033, 0x6034, 0x6035)))
BLACK_ORB_OBJ = 0xCA


def black_orb_item(rom):
    """"orbs" when the Black Orb's routine is the four-orb AND, else None."""
    routines = talk_routines(rom)
    if routines is None or BLACK_ORB_OBJ not in routines:
        return None
    bank, _ = talk_routine_bank(rom.data)
    body = rom.data[bank_off(bank, routines[BLACK_ORB_OBJ])::][:12]
    if len(body) < 12 or body[0] != 0xAD:
        return None
    seen, ok = [], True
    for i in range(0, 12, 3):
        op = body[i]
        if op != (0xAD if i == 0 else 0x2D):
            ok = False
            break
        seen.append(body[i + 1] | (body[i + 2] << 8))
    if not ok or frozenset(seen) not in ORB_BYTE_SETS:
        return None
    return "orbs"

# ------------------------------------------------------- No-Overworld gate NPCs
#
# No-Overworld's gates are not tiles. They are NPCs standing in corridors, and
# which item each one wants is a property of the talk routine FFR assigns it,
# not of the dialogue -- the dialogue is deliberately misleading, and says
# "Lukahn's mark" at NPCs whose routine checks the Canoe.
#
# FF1Lib/Sanity/SCMap.cs:218-226 is FFR's own logic model and states it outright:
# NoOW_Floater wants Floater, NoOW_Canoe the Canoe, NoOW_Chime the Chime, and
# Talk_Nerrick the TNT. The object ids are FF1Lib/Items.cs's ObjectId enum, which
# is the game's own numbering.
#
# Nothing is taken on faith: which routine an object actually runs is read off
# the cartridge, and the eight below have to fall into four groups matching four
# items before any of it is believed. On a standard cartridge they do not -- they
# are ordinary townspeople sharing generic routines -- and that is the signal
# that this is not a No-Overworld layout rather than an error.
NOVERWORLD_GATES = {
    0x08: "tnt",                                            # Nerrick
    0x22: "floater", 0xC1: "floater", 0xC5: "floater",      # the three SIGIL barriers
    0x46: "canoe", 0x83: "canoe", 0x84: "canoe",            # the three "Lukahn's mark" NPCs
    0xB0: "chime",                                          # the Gaia robot
}
GATE_OBJ_NAMES = {
    0x08: "Nerrick", 0x22: "ConeriaCastle1FWoman1", 0xC1: "LefeinMan6",
    0xC5: "LefeinMan10", 0x46: "ElflandCastleElf2", 0x83: "CrescentWoman",
    0x84: "CastleOrdealsOldMan", 0xB0: "GaiaScholar2",
}

# The talk jump table: $D0 entries of two bytes, one per object id, giving the
# routine that runs when you talk to it.
#
# Vanilla keeps it at lut_MapObjTalkJumpTbl, $0E:90D3 (bank_0E.asm:902). FFR
# rebuilds it somewhere else entirely -- lut_MapObjTalkJumpTbl_new, $8000 of the
# bank it assembles its own routines into (FF1Lib/NPCs.cs:106,129).
#
# $90D3 in the new bank is NOT that table. Dialogues.cs:137 bulk-copies $8EA
# bytes of the vanilla region into the new bank, so the old address still holds
# a complete, well-formed, vanilla jump table -- on a No-Overworld cartridge it
# says every gate NPC is an ordinary townsperson. Same shape as the standard
# maps left behind in bank $04: reading the old address does not fail, it lies.
TALK_JUMP_TBL = 0x90D3          # vanilla
TALK_JUMP_TBL_NEW = 0x8000      # FFR
TALK_OBJ_COUNT = 0xD0

# FFR patches the engine's `LDA #<bank>` to name the bank it moved them to
# (FF1Lib/Dialogues.cs:54,178 -- $0E out, $11 in, written at rom[0x7C9F2], which
# is a header-less index, so +16 in the file).
TALK_BANK_CONST = bank_off(0x1F, 0x89F2)
VANILLA_TALK_BANK = 0x0E


def talk_routine_bank(data):
    """(bank, address) of the live talk jump table, or None if it is not there.

    Read from the engine's own constant, not assumed. A stock cartridge is 16
    banks and has no $1F:89F2 at all, which is the fallback.
    """
    def fits(bank, addr):
        return bank_off(bank, addr) + TALK_OBJ_COUNT * 2 <= len(data)

    if TALK_BANK_CONST < len(data):
        bank = data[TALK_BANK_CONST]
        if bank != VANILLA_TALK_BANK and fits(bank, TALK_JUMP_TBL_NEW):
            return bank, TALK_JUMP_TBL_NEW
    if fits(VANILLA_TALK_BANK, TALK_JUMP_TBL):
        return VANILLA_TALK_BANK, TALK_JUMP_TBL
    return None


def talk_routines(rom):
    """object id -> the address of the routine it runs, or None if unreadable."""
    where = talk_routine_bank(rom.data)
    if where is None:
        return None
    base = bank_off(*where)
    return {oid: int.from_bytes(rom.data[base + oid * 2:base + oid * 2 + 2], "little")
            for oid in range(TALK_OBJ_COUNT)}


def noverworld_gate_items(rom):
    """item -> the routine address that wants it, or None on a non-NoOW layout.

    The eight gate objects have to sort into groups by routine that each want a
    single item. A standard cartridge mixes them -- CrescentWoman and the Gaia
    scholar share one generic routine there -- and mixing is the answer "these
    are not gates", not a failure to read.
    """
    routines = talk_routines(rom)
    if routines is None:
        return None
    by_routine = {}
    for oid, item in NOVERWORLD_GATES.items():
        by_routine.setdefault(routines[oid], set()).add(item)
    # Four routines, four items, one item each, and every item accounted for.
    # Anything less and the eight objects are not the gate set -- which is the
    # answer on a standard cartridge, where they share generic routines.
    if len(by_routine) != len(set(NOVERWORLD_GATES.values())):
        return None
    if any(len(items) != 1 for items in by_routine.values()):
        return None
    out = {items.copy().pop(): addr for addr, items in by_routine.items()}
    if set(out) != set(NOVERWORLD_GATES.values()):
        return None
    return out

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

# Vanilla door -> map, matched by the enum names in FF1Lib/Enums.cs
# (OverworldTeleportIndex against MapIndex). Only ever used to flag which doors
# did not move; the shuffle itself is always read from the ROM.
#
# Written out rather than guessed from the names. A name test gets it wrong in
# both directions: the five vanilla doors at the end (TitansTunnelEast/West,
# Cardia4/5/6) do not contain the name of the map they open, and 29 pairs that a
# shuffle really did move do -- TempleOfFiends1 into any TempleOfFiendsRevisited
# floor, EarthCave1 into EarthCaveB2, and so on.
VANILLA_DOOR_MAP = {
    0: 16, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 7, 9: 8, 10: 9, 11: 10,
    12: 11, 13: 12, 14: 13, 15: 14, 16: 15, 17: 16, 18: 17, 19: 18, 20: 19,
    21: 20, 22: 21, 23: 22, 24: 23, 25: 60, 26: 60, 27: 16, 28: 16, 29: 16,
}
# FFR's spare pair. They carry an ordinary map byte and no overworld tile.
UNUSED_DOORS = (30, 31)


def gate_objects(rom):
    """object id -> the item you need to step past it, or None off this mode.

    FFR's own logic model says a gate NPC is a tile that costs an item, which is
    the same shape as the Rod and Lute objects: Sanity/SCMap.cs:218-226 stamps
    SCBitFlags.Floater, .Chime or .Canoe onto the tile the NPC stands on, and
    :214 stamps .Tnt onto Nerrick's. So blocking that one tile until the item is
    in hand is not an approximation of the mode -- it is the model FFR routes
    its own seeds with.

    Read from the cartridge, not from the eight ids below. noverworld_gate_items
    settles which four routines are the gates and what each one wants; this then
    asks the talk table which objects run them, so an object FFR hands a gate
    routine is blocked whether or not it is one of the eight we knew about.

    Nerrick is the odd one. MetroidVaniaMap.cs:833-834 leaves its NoOW_Nerrick
    assignment commented out, so he keeps the vanilla Talk_Nerrick -- already a
    TNT gate, which is why the four routines still sort.
    """
    gates = noverworld_gate_items(rom)
    if gates is None:
        return None
    want = {addr: item for item, addr in gates.items()}
    return {oid: want[addr] for oid, addr in talk_routines(rom).items()
            if addr in want}


# --------------------------------------------------- what a talk routine wants
#
# Some NPC locations are a trade, not a tile. Astos hands over what he holds
# only once the Crown is in the bag, Nerrick only once the TNT is; the walk can
# stand beside either of them empty-handed and learns nothing. Those two were
# the only locations where the derived No-Overworld rules disagreed with FFR's
# own logic.
#
# FFR keeps the answer as data. NPCs.cs rebuilds the talk table as $D0 records
# of six bytes -- dialogue x3, the item given, the item **required**, a battle
# id -- and moves them into the same bank it moved the jump table to. The
# requirement byte is an offset into the `items` array in save RAM, so 0 is "no
# requirement" and 2 is the Crown.
#
# The byte alone is not the answer, because whether it means anything depends on
# the script that object runs. FFR's generic trade routine reads it:
#
#     LDX tmp+4        A6 74        the requirement byte, as an index
#     BEQ ...          F0 05        nothing required, skip the check
#     LDA items,X      BD 20 60     do they have it?
#
# and an object whose script never touches tmp+4 leaves the byte lying there
# meaning nothing. The Elf Prince is exactly that trap: his byte reads 5, the
# Mystic Key, which is the item he *gives*, and his routine never looks at it.
# Believing the byte on its own would have said the Elf Prince needs the key he
# is holding out to you.
#
# So an object is only read as gated when one of two things is true, and both
# are two sources agreeing rather than one asserting:
#
#   - its routine reads tmp+4 as an index into `items` (the pattern above), so
#     the byte is what the engine itself consults; or
#   - its routine loads that exact item's address directly -- `LDA item_tnt` is
#     AD 26 60 -- *and* the requirement byte names the same item. Nerrick is the
#     one that needs this: MetroidVaniaMap.cs leaves him the older routine,
#     which hardcodes the TNT instead of indexing, and his byte says TNT too.
#
# On a cartridge with no moved talk table -- a stock image -- there is no
# requirement table either, and this returns None rather than guessing, the same
# way noverworld_gate_items answers "not this layout".
TALK_DATA_NEW = 0xBA00          # FF1Lib/NPCs.cs:102, in newTalkRoutinesBank
TALK_DATA_RECORD = 6            # NpcObject.GetBytes()
TALK_DATA_REQUIREMENT = 4       # ... Item, Requirement, Battle
ITEMS = 0x6020                  # variables.inc:334, items = unsram + $20
ITEM_RAM = {                    # variables.inc:336-352, offset -> the pack's code
    0x01: "lute", 0x02: "crown", 0x03: "crystal", 0x04: "herb",
    0x05: "key", 0x06: "tnt", 0x07: "adamant", 0x08: "slab",
    0x09: "ruby", 0x0A: "rod", 0x0B: "floater", 0x0C: "chime",
    0x0D: "tail", 0x0E: "cube", 0x0F: "bottle", 0x10: "oxyale",
    0x11: "canoe",
}
LDX_REQUIREMENT = b"\xa6\x74"           # LDX tmp+4
LDA_ITEMS_X = b"\xbd\x20\x60"           # LDA items,X
# A routine runs until the next one begins. Nothing promises the table is in
# address order, so the bound is the next distinct address above this one, and
# one that turns out to be last gets this much and no more -- enough for any of
# them, and short of running off into whatever else sits in the bank.
MAX_ROUTINE = 0x200
# `starts` only holds jump-table targets, so the *last* routine has nothing
# above it to stop at and takes the flat MAX_ROUTINE. Two things sit in range of
# that: the requirement table at $BA00, in this same bank, and the end of the
# bank itself. Reading either as code is how a data coincidence -- `A6 74` plus
# `BD 20 60`, or an `AD xx 60` -- marks every object on that routine as gated on
# an item it never checks, which is the exact false positive the Elf Prince
# exclusion exists to keep out. So the body stops at both.
BANK_END = 0xC000


def talk_requirement_bytes(rom):
    """object id -> its requirement byte, or None where FFR has not moved the table."""
    where = talk_routine_bank(rom.data)
    if where is None or where[1] == TALK_JUMP_TBL:
        return None                     # a stock image: 4-byte records, no such byte
    bank, _ = where
    base = bank_off(bank, TALK_DATA_NEW)
    end = base + TALK_OBJ_COUNT * TALK_DATA_RECORD
    if end > len(rom.data):
        return None
    return {oid: rom.data[base + oid * TALK_DATA_RECORD + TALK_DATA_REQUIREMENT]
            for oid in range(TALK_OBJ_COUNT)}


def talk_routine_bodies(rom):
    """routine address -> its bytes, bounded so data is never read as code.

    Factored out because two readers want it and the bounds are the whole
    subtlety: see MAX_ROUTINE and BANK_END above for why a routine stops where
    it does. {} when the cartridge has no readable talk table.
    """
    routines = talk_routines(rom)
    if routines is None:
        return {}
    bank, _ = talk_routine_bank(rom.data)
    starts = sorted(set(routines.values()))

    def code(addr):
        after = [a for a in starts if a > addr]
        end = min(after[0] if after else addr + MAX_ROUTINE, addr + MAX_ROUTINE)
        if addr < TALK_DATA_NEW:
            end = min(end, TALK_DATA_NEW)
        end = min(end, BANK_END)
        lo, hi = bank_off(bank, addr), bank_off(bank, end)
        if lo < 0 or hi > len(rom.data) or hi <= lo:
            return b""
        return rom.data[lo:hi]

    return {a: code(a) for a in starts}


def talk_item_requirements(rom):
    """object id -> the item its talk routine demands, or None off an FFR layout.

    Only objects whose script is shown to consult the requirement appear -- see
    the note above. An object whose byte nothing reads contributes nothing
    rather than a guess.
    """
    reqs = talk_requirement_bytes(rom)
    routines = talk_routines(rom)
    if reqs is None or routines is None:
        return None
    bodies = talk_routine_bodies(rom)
    out = {}
    for oid, addr in routines.items():
        item = ITEM_RAM.get(reqs[oid])
        if item is None:
            continue
        body = bodies[addr]
        indexed = LDX_REQUIREMENT in body and LDA_ITEMS_X in body
        direct = bytes([0xAD, (ITEMS + reqs[oid]) & 0xFF, (ITEMS + reqs[oid]) >> 8]) in body
        if indexed or direct:
            out[oid] = item
    return out


# ------------------------------------- the two objects gated by their own id
#
# SubEngineer and Titan, the last two of the five object gates
# FF1Lib/Sanity/SCMap.cs:167-186 lists. SCMap keys these two by *object id* and
# stamps SCBitFlags.Oxyale and .Ruby onto the tile each one stands on -- exactly
# what it does for the Rod and Lute plates -- so they are ordinary blocking
# objects and nothing about them belongs to No-Overworld. Both sit on a
# chokepoint on a standard cartridge too: the sub engineer in Onrac is the only
# way down to the Sea Shrine, and the Titan blocks his tunnel.
#
# Which item each one wants is read off its talk routine rather than tabulated,
# for the reason black_orb_item is a reader: a cartridge is free to reassign a
# routine, and a table cannot notice. The two are not equally legible, and that
# is a property of the cartridge rather than a choice made here.
#
#   - **Titan's requirement byte is set.** NPCs.cs assigns him Item.Ruby = 9,
#     and his routine opens `AD 29 60`, LDA item_ruby -- the byte and the code
#     naming the same item, which is the two-sources-agree discipline
#     talk_item_requirements exists for. So he needs nothing new: that reader
#     already answers "ruby" for object $14.
#   - **SubEngineer's byte is 0x00.** NPCs.cs never assigns him one, so the byte
#     says nothing at all and the only signal is the routine body, which opens
#     `AD 30 60`, LDA item_oxyale. One source has to carry the answer alone, so
#     the shape is pinned hard instead: the body must name exactly one item
#     address. Two, or none, and this returns nothing rather than picking.
#
# `items + $11` is deliberately not readable this way. FFR's ShiftEarthOrbDown
# moves the Earth Orb onto $6031, which is item_canoe's address, so that one
# load means two different things depending on the seed and the body cannot say
# which. The requirement *byte* has no such problem -- it is an index FFR writes
# -- which is why only the scan drops it.
OBJECT_ITEM_GATES = ("subengineer", "titan")
LDA_ABS = 0xAD
CANOE_OFFSET = 0x11


def direct_item_loads(body):
    """The `items` offsets a routine loads by absolute address, as a set.

    Not instruction-aligned, the same way talk_item_requirements' `direct` test
    is not: an operand pair can read as `AD lo hi`. That costs a false extra
    entry, never a missing one, and every caller here treats "more than one" as
    a refusal -- so the scan errs towards saying nothing.
    """
    out = set()
    for i in range(max(0, len(body) - 2)):
        if body[i] != LDA_ABS:
            continue
        off = (body[i + 1] | (body[i + 2] << 8)) - ITEMS
        if off in ITEM_RAM and off != CANOE_OFFSET:
            out.add(off)
    return out


def object_gate_items(rom):
    """object id -> the item you must hold to step past it, for the two above.

    {} rather than None when nothing is readable: an unreadable cartridge
    contributes no rows and the walk blocks what it blocked before, which is
    what these two did while they were unmodelled.

    A row is emitted only when its item is in ITEM_NAMES, which is the same
    refusal black_orb_item makes on a shard count. Both readers can name any of
    the 17 entries in ITEM_RAM, and a gate on an item the sweep never varies
    blocks that chokepoint in *every* subset -- so everything behind it derives
    as unreachable rather than gated, which is the failure mode that made the
    row and the vocabulary widening land in one commit. Enforced here rather
    than left to the two names FFR happens to stamp today: the whole reason
    this is a reader is that a cartridge is free to reassign the routine.
    """
    routines = talk_routines(rom)
    if routines is None:
        return {}
    reqs = talk_item_requirements(rom) or {}
    bodies = talk_routine_bodies(rom)
    out = {}
    for name in OBJECT_ITEM_GATES:
        oid = NPC_IDS[name]
        item = reqs.get(oid)
        if item is None:
            loads = direct_item_loads(bodies.get(routines.get(oid), b""))
            if len(loads) == 1:
                item = ITEM_RAM[loads.pop()]
        if item in ITEM_NAMES:
            out[oid] = item
    return out


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

# Everything this tool routes with lives in bank $0F, so the file has to hold
# all of it. A shorter iNES image is not a smaller version of the same answer.
MIN_ROM_SIZE = bank_off(BANK_EXTTELEPORTINFO, 0xC000)


class Rom:
    def __init__(self, path):
        with open(path, "rb") as f:
            self._load(f.read(), path)

    @classmethod
    def of(cls, data, path="<memory>"):
        """The same cartridge, for a caller that already read the bytes."""
        rom = cls.__new__(cls)
        rom._load(data, path)
        return rom

    def _load(self, data, path):
        self.data = data
        if self.data[:4] != b"NES\x1a":
            sys.exit("not an iNES ROM")
        if len(self.data) < MIN_ROM_SIZE:
            sys.exit(f"{path}: {len(self.data)} bytes, but the extended teleport "
                     f"tables live at {MIN_ROM_SIZE} -- this is not a full FFR image")
        self.path = path

    def at(self, bank, addr, n):
        o = bank_off(bank, addr)
        chunk = self.data[o:o + n]
        if len(chunk) != n:
            sys.exit(f"{self.path}: {len(self.data)} bytes, too short to hold "
                     f"bank ${bank:02X}:${addr:04X}+{n}")
        return chunk


def ffr_info(rom):
    """The cartridge's FFRInfo record, or None when it has not got one.

    Worth asking before routing anything. The tables this tool reads are FFR's
    own: GlobalHacks.ExpandNormalTeleporters writes them into bank $0F, and on a
    stock Final Fantasy cartridge that region is unrelated bank-15 bytes. Reading
    it there does not fail -- it produces a complete, confident, invented graph.
    """
    sys.path.insert(0, os.path.join(HERE, "ffr_flags"))
    try:
        import ffr_flags
        return ffr_flags.read_info(rom.data)
    except Exception:
        return None


# ------------------------------------------------------------- overworld doors

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
    grid = decompress_ow(rom.data)
    out = {}
    for y in range(OW_DIM):
        for x in range(OW_DIM):
            idx = tele.get(grid[y][x])
            if idx is not None:
                out.setdefault(idx, []).append((x, y))
    return out


# ------------------------------------------------------------------- the graph

def walkable(b0, have):
    """CanPlayerMoveSM, bank_0F.asm:2449.

    TP_NOMOVE is not an unconditional wall. The game blocks only when the
    special bits are *all clear* and NOMOVE is set -- a plain wall. If the tile
    carries a special, the jump table decides and NOMOVE is thrown away. Room
    doors are exactly this case: Marsh Cave B1's door at (35,54) is
    TP_SPEC_DOOR | TP_NOMOVE, and reading NOMOVE on its own seals every room in
    the game shut. That is what hid the Marsh Cave -> Sea Shrine B3 -> Bahamut
    -> Dwarf Cave chain.

    Module-level so a caller that only wants the rule -- render_maps, deciding
    which blank cells are floor -- need not build a whole Graph for it.
    """
    if (b0 & (TP_SPEC_MASK | TP_NOMOVE)) == TP_NOMOVE:
        return False
    spec = b0 & TP_SPEC_MASK
    if spec == TP_SPEC_TREASURE:
        return False
    need = GATED_SPECIALS.get(spec)
    return need is None or need in have


def tile_properties(rom, map_id):
    """The first property byte of every cell on a map, as a flat 64*64 list."""
    tilesets = rom[TILESET_LUT:TILESET_LUT + MAP_COUNT]
    base = map_data_base(rom)
    ptr = int.from_bytes(rom[base + map_id * 2:base + map_id * 2 + 2], "little")
    tiles = decompress_map(rom, base + ptr)
    prop = TILESET_PROP + tilesets[map_id] * PROP_STRIDE
    return tiles, [rom[prop + t * 2] for t in tiles]


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
        self.sm_bank = standard_map_bank(rom.data)
        self.sm_base = map_data_base(rom.data)
        self.grids = {}
        self.doors = door_positions(rom)
        # Every object gate SCMap.cs:167-186 knows about. The Rod and Lute
        # plates always; the sub engineer and the Titan wherever their routines
        # can be read, which is every cartridge measured, vanilla included; the
        # Black Orb where its routine is the four-orb AND; and the No-Overworld
        # gate NPCs where the layout is that mode's -- gate_objects returns None
        # on every other seed.
        #
        # Order matters where a cartridge ever puts two of those on one object.
        # SCMap switches on the object id and reaches the routine only in its
        # default case, so the id-keyed rows are the ones FFR itself uses:
        # routine-keyed gates first, everything id-keyed over the top.
        #
        # Assigning gated_objects is also what creates the walk caches -- see
        # the properties below, which is why `self.grids = {}` above has
        # already made them once.
        self.gates = gate_objects(rom)
        orb = black_orb_item(rom)
        self.gated_objects = {**(self.gates or {}), **GATED_OBJECTS,
                              **object_gate_items(rom),
                              **({BLACK_ORB_OBJ: orb} if orb else {})}

    # ------------------------------------------------------------- the memos
    #
    # A full sweep walks the same floor over and over: instrumenting a
    # 1024-subset sweep on a No-Overworld cartridge gave 86464 floor_walk calls
    # over 129 distinct (map, arrival) pairs producing 188 distinct results, and
    # 92 of the 129 walked identically whatever was held. 2^12 makes that four
    # times worse. So the walks are cached, keyed on the only part of `have`
    # that can change the answer.
    #
    # **The key is the entire risk.** One that leaves out an item the walk
    # consults returns another subset's reachability, silently, which is the
    # failure class this tree has hit repeatedly. So it is not a list: it is
    # derived from the same two tables the walk itself reads, on the same map,
    # by floor_items() below. And because the object half of that comes from
    # `gated_objects`, assigning that attribute has to throw the caches away --
    # which is what the property exists for. test_gate_objects.py strips the
    # rows back to the plates to prove the gates change something, and without
    # this it would be handed back the gated walks it had already asked for.

    def _drop_walks(self):
        self._floor_items, self._walks, self._teleports = {}, {}, {}

    @property
    def gated_objects(self):
        return self._gated_objects

    @gated_objects.setter
    def gated_objects(self, value):
        self._gated_objects = value
        self._drop_walks()

    # `grids` invalidates for the same reason, and is a property rather than a
    # plain dict for the same reason: floor_items() reads a map's tile
    # properties as well as its objects, so a caller that patches rom.data and
    # empties the grid cache has changed what a walk consults just as surely as
    # one that swaps a gate row. Both tests that patch a cartridge do clear both
    # -- but only by writing them in one statement, and a memo whose correctness
    # rests on the order of a tuple assignment is one line from being wrong.
    @property
    def grids(self):
        return self._grids

    @grids.setter
    def grids(self, value):
        self._grids = value
        self._drop_walks()

    def floor_items(self, map_id):
        """The items that can change what a walk on this floor reaches.

        Everything walkable() and blocking_objects() consult on this map and
        nothing else, so two subsets agreeing on this set walk identically.
        Read off the map's own tile properties and objects rather than listed,
        because a list is what goes stale when a gate is added.
        """
        if map_id not in self._floor_items:
            _, p0, _ = self.grid(map_id)
            need = {GATED_SPECIALS.get(b0 & TP_SPEC_MASK) for b0 in p0}
            need |= {self.gated_objects.get(oid) for oid, _, _ in self.objects(map_id)}
            need.discard(None)
            self._floor_items[map_id] = frozenset(need)
        return self._floor_items[map_id]

    def grid(self, map_id):
        """(tiles, prop0, prop1) for a map, as flat 64*64 lists."""
        if map_id not in self.grids:
            ptr = int.from_bytes(
                self.rom.data[self.sm_base + map_id * 2:self.sm_base + map_id * 2 + 2], "little")
            tiles = decompress_map(self.rom.data, self.sm_base + ptr)
            base = TILESET_PROP + self.tilesets[map_id] * PROP_STRIDE
            p0 = [self.rom.data[base + t * 2] for t in tiles]
            p1 = [self.rom.data[base + t * 2 + 1] for t in tiles]
            self.grids[map_id] = (tiles, p0, p1)
        return self.grids[map_id]

    def walkable(self, b0, have):
        """See the module-level walkable(); kept as a method for its callers."""
        return walkable(b0, have)

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
                if self.gated_objects.get(oid) not in (None, *have)}

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

        Memoized on (map, arrival, stop_on_teleport, what of `have` this floor
        consults) -- see floor_items(). The dict handed back is the cached one,
        so a caller that wants to modify it copies first; nothing here does.

        Teleport tiles end the walk by default -- stepping on one takes you off
        the floor, so you cannot route *through* a staircase.

        **A standard map is a torus.** Walking off one edge brings you in at the
        other, and the engine says so itself: SMMove_Right adds one to
        sm_scroll_x and masks `AND #$3F`, commented "and wrap at 64 tiles"
        (bank_0F.asm:3070). SMMove_Left, Up and Down do the same on their axis.

        This walk treated the map as a bounded rectangle until 2026-08-30, which
        sealed off any region only reachable by crossing an edge. Sea Shrine B1
        is the case that found it: three of its twelve Mermaid chests sit in an
        85-tile pocket walled off on every side, and vanilla's intended route is
        to leave by the top left and come back in at the top right.
        """
        sx, sy = start[0] % MAP_DIM, start[1] % MAP_DIM
        key = (map_id, sx, sy, stop_on_teleport,
               frozenset(have) & self.floor_items(map_id))
        if key in self._walks:
            return self._walks[key]
        _, p0, _ = self.grid(map_id)
        tele_at = {(x, y) for x, y, _, _ in self.teleports(map_id)} if stop_on_teleport else set()
        blocked = self.blocking_objects(map_id, have)
        seen = {(sx, sy): 0}
        q = deque([(sx, sy)])
        while q:
            x, y = q.popleft()
            if (x, y) in tele_at and (x, y) != (sx, sy):
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = (x + dx) % MAP_DIM, (y + dy) % MAP_DIM
                if (nx, ny) in seen or (nx, ny) in blocked:
                    continue
                if not self.walkable(p0[ny * MAP_DIM + nx], have):
                    continue
                seen[(nx, ny)] = seen[(x, y)] + 1
                q.append((nx, ny))
        self._walks[key] = seen
        return seen

    def can_reach_npc(self, map_id, start, spot, have):
        """You talk to an NPC from an adjacent tile; its own tile is blocked.

        The neighbours wrap for the same reason floor_walk does -- every key it
        returns is mod 64, so a raw `nx + 1` on column 63 names a tile that
        cannot be in the walk. An NPC approachable only across the edge would
        report unreachable, and on a gate NPC that prunes everything behind it.
        """
        walk = self.floor_walk(map_id, start, have)
        nx, ny = spot["tile_col"], spot["tile_row"]
        spots = [((nx + dx) % MAP_DIM, (ny + dy) % MAP_DIM)
                 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        best = [walk[s] for s in spots if s in walk]
        return min(best) if best else None

    def reachable_teleports(self, map_id, start, have):
        """Teleport tiles you can actually walk to from `start` on this map.

        Floors are not fully connected -- that is the whole point of a locked
        door -- so "the graph has an edge" is not the same as "you can take it".

        Memoized on the same key floor_walk uses, and for the same reason: this
        is the second half of the sweep's per-floor work, and a memo on one and
        not the other is half a memo. The cached dict is handed back as-is.
        """
        sx, sy = start[0] % MAP_DIM, start[1] % MAP_DIM
        key = (map_id, sx, sy, frozenset(have) & self.floor_items(map_id))
        if key in self._teleports:
            return self._teleports[key]
        _, p0, _ = self.grid(map_id)
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
                nx, ny = (x + dx) % MAP_DIM, (y + dy) % MAP_DIM
                if (nx, ny) in seen:
                    continue
                if (nx, ny) in blocked:
                    continue
                if not self.walkable(p0[ny * MAP_DIM + nx], have):
                    continue
                seen.add((nx, ny))
                q.append((nx, ny, d + 1))
        self._teleports[key] = found
        return found

    def reachable_maps(self, have):
        """Every map you can stand on with `have` in hand, walking from the doors.

        The staircase under your feet counts. reachable_teleports drops the tile
        it starts on -- stepping onto a teleport is what takes you off the floor
        and you are already standing there -- but you can step off and back on,
        and on a No-Overworld cartridge that is the only way into some floors.
        """
        seen, q, maps = set(), deque(), set()
        for _, m, a in self.starts():
            maps.add(m)
            if (m, a) not in seen:
                seen.add((m, a))
                q.append((m, a))
        while q:
            m, a = q.popleft()
            steps = {(x, y): (k, p) for (x, y), (k, p, _)
                     in self.reachable_teleports(m, a, have).items()}
            under = dict(steps)
            for x, y, kind, pay in self.teleports(m):
                if (x, y) == (a[0] % MAP_DIM, a[1] % MAP_DIM):
                    under[(x, y)] = (kind, pay)
            for kind, pay in under.values():
                if kind != TP_TELE_NORM:
                    continue
                dm = self.norm_map[pay]
                if dm >= MAP_COUNT:
                    continue
                maps.add(dm)
                arrive = (coord(self.norm_x[pay]), coord(self.norm_y[pay]))
                if (dm, arrive) not in seen:
                    seen.add((dm, arrive))
                    q.append((dm, arrive))
        return maps

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
            same = "  (unchanged)" if VANILLA_DOOR_MAP.get(i) == m else ""
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


# GameModes, FF1Lib/Enums.cs:396-404.
GAME_MODE_NOVERWORLD = 2


def game_mode(rom):
    """-> (GameMode, None), or (None, why it could not be read).

    Used only to decide which extra invariants apply, so an unreadable mode
    skips them rather than failing the run -- but the reason comes back with it
    so the skip can say so. A skip that prints nothing is indistinguishable
    from a pass, and the invariant this gates exists precisely to catch a
    silent wrong answer. A vanilla cartridge has no flag block at all, which is
    the ordinary case here and not a defect.
    """
    sys.path.insert(0, os.path.join(HERE, "ffr_flags"))
    try:
        import ffr_flags
        _, flags = ffr_flags.decode_rom(rom.data)
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    return flags.get("GameMode"), None


def check_map_bank(g):
    """The maps this tool read must be the maps the engine reads.

    Two constants name the bank and FFR patches both; if they disagree, the
    image is not one this tool understands. And an FFR cartridge that still
    claims bank $04 means the constant was not found -- reading there gets the
    untouched vanilla maps and invents a plausible graph from them.
    """
    off = _fixed_bank_off(*SM_BANK_CONST_MIRROR)
    if off < len(g.rom.data):
        mirror = g.rom.data[off]
        if mirror != g.sm_bank:
            print(f"self-check FAILED: standard maps read from bank ${g.sm_bank:02X}, "
                  f"but the mirror constant $1F:D145 says ${mirror:02X}")
            return False
    if ffr_info(g.rom) is not None and g.sm_bank == SM_BANK_VANILLA:
        print("self-check FAILED: this is an FFR cartridge but the maps resolved to "
              f"the vanilla bank ${SM_BANK_VANILLA:02X} -- every seed relocates them, "
              "so this is the vanilla copy and the whole graph would be wrong")
        return False
    return True


def check_noverworld_towns(g, mode, why=None):
    """A No-Overworld town has to have stairs out of it.

    NoOverworld seals every town's outer wall (MetroidVaniaMap.cs:109-434) and
    connects it by staircase instead. A town with no staircase is therefore not
    a quirk of the seed -- it means the map data being read is not the map data
    the seed plays, which is precisely what reading bank $04 looked like.
    """
    if mode is None:
        print("self-check SKIPPED: the No-Overworld stairless-town test needs the "
              f"GameMode, which could not be read ({why})")
        return True
    if mode != GAME_MODE_NOVERWORLD:
        return True
    stairless = []
    for door, m, _ in g.starts():
        if not any(k == TP_TELE_NORM for _, _, k, _ in g.teleports(m)):
            stairless.append((door, m))
    if stairless:
        print(f"self-check FAILED: {len(stairless)} No-Overworld entry maps have no "
              "staircase, so nothing could be reached from them")
        for door, m in stairless[:10]:
            print(f"  {DOOR_NAMES[door]} -> {MAP_NAMES[m]}")
        return False
    print(f"self-check OK: all {len(g.starts())} No-Overworld entry maps have stairs")
    return True


def self_check(g):
    """The byte-0/byte-1 regression test.

    Every tile this tool calls a staircase must not be a treasure chest. Reading
    the teleport bits out of property byte 1 instead of byte 0 makes chests with
    ids in $80-$BF read as normal teleports, which is exactly how an earlier
    router sent a route through a chest on Sea Shrine B1.
    """
    if not check_map_bank(g):
        return False
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
    print(f"self-check OK: {total} teleport tiles across {MAP_COUNT} maps in bank "
          f"${g.sm_bank:02X} ({norm} of them staircases; the rest are mostly the "
          "warp-out filler that surrounds every town), none of them a treasure chest")
    if not check_talk_bank(g):
        return False
    mode, why = game_mode(g.rom)
    if not check_noverworld_towns(g, mode, why):
        return False
    # Last, because it is the one that exercises everything above it at once.
    return check_all_reachable(g, mode, why)


# --------------------------------------------------------------- the two rolls
#
# Two permutations chosen at generation that reach neither the flag string nor
# the spoiler log, so the cartridge is the only thing that can be asked. They
# are read together because they are one read on one channel: PRG ROM at fixed
# offsets, no map decompression for either half.
#
# The gateway roll. MetroidVaniaMap.cs:717-736 shuffles a list of three
# destinations -- two Cardia landings and Bahamut's Cave B1 -- and hands them
# out to three one-way teleporters it then writes onto Waterfall, Ice Cave B1
# and Gaia, in that order. The ids come off `teleportIDtracker++` at a fixed
# point in a hand-authored table, so the three ids do not move; only their
# destinations do. Measured across all four No-Overworld cartridges in
# oracle-4.9.2: three distinct permutations, the same three ids each time.
#
# The id-to-source assignment is read off the cartridge rather than off that
# call order, because the call order is the one part of this a transcription
# could get wrong. `--rolls` prints the tile each gateway was found on, and
# says so when an id is not on the map the call order claims.

GATEWAY_IDS = (0x89, 0x8A, 0x8B)

# The map each id's tile is written onto, by the order of the three
# UpdateMapTile calls in that block. Measured on all four cartridges: Ice Cave
# and Gaia are fixed tiles, and the Waterfall stair position is rolled per seed
# -- which moves where the gateway stands, not where it goes.
GATEWAY_SOURCES = {0x89: 18, 0x8A: 15, 0x8B: 5}
# The name each source goes by on the wire and in the pack's codes. The bridge
# and scripts/autotracking/rolls_mapping.lua use these spellings, so this is
# where the two implementations agree on a vocabulary rather than each holding
# their own copy.
GATEWAY_SOURCE_NAMES = {0x89: "waterfall", 0x8A: "icecave", 0x8B: "gaia"}

# The three destinations, keyed by the (map, x, y) they land on.
#
# cardiaCaravan is the pocket holding the Caravan door and nothing else: walked
# on `nov` holding every item, it is 68 tiles, no chest and no NPC the pack
# tracks. So no rule ever asks about it. It is named anyway, because a roll
# that sends a source there is the reason the other two are where they are.
GATEWAY_LANDINGS = {
    (16, 0x3A, 0x37): "cardiaForest",
    (16, 0x2B, 0x1D): "cardiaCaravan",
    (17, 0x02, 0x02): "bahamutCave",
}


def gateway_destinations(rom):
    """{teleport id: (map, x, y)} for the three gateways, or None.

    None says this cartridge has no such gateways, and it is decided by the
    destinations rather than by the flag record: all three ids have to land on
    the three known tiles, one each. So a cartridge whose flags will not decode
    still answers, and an FFR that moves the landings says nothing rather than
    something plausible.

    Separate from gateway_roll() because it is the whole read -- three tables,
    no map decompression -- and it is what says whether decompressing anything
    is worth it. The bridge reads exactly this.
    """
    x = rom.at(BANK_EXTTELEPORTINFO, NORM_TELE_X_EXT, NORM_COUNT_EXT)
    y = rom.at(BANK_EXTTELEPORTINFO, NORM_TELE_Y_EXT, NORM_COUNT_EXT)
    m = rom.at(BANK_EXTTELEPORTINFO, NORM_TELE_MAP_EXT, NORM_COUNT_EXT)
    dest = {tid: (m[tid], coord(x[tid]), coord(y[tid])) for tid in GATEWAY_IDS}
    if sorted(dest.values()) != sorted(GATEWAY_LANDINGS):
        return None
    return dest


def gateway_roll(g):
    """Where the three Cardia/Bahamut one-way gateways go on this cartridge.

    -> [{teleport, source, tiles, dest, landing}] in id order, or None when
    this cartridge has no such gateways.

    `tiles` is where the gateway stands, read off the source map rather than
    taken from the call order in that block -- see above. An empty list is the
    one thing here that is reported rather than refused: the destination is
    still what the teleport does.
    """
    dest = gateway_destinations(g.rom)
    if dest is None:
        return None
    return [{"teleport": tid,
             "source": GATEWAY_SOURCES[tid],
             "tiles": [(x, y) for x, y, kind, payload
                       in g.teleports(GATEWAY_SOURCES[tid])
                       if kind == TP_TELE_NORM and payload == tid],
             "dest": dest[tid],
             "landing": GATEWAY_LANDINGS[dest[tid]]}
            for tid in GATEWAY_IDS]


# NPCs.cs:277 -- ShuffleObjectiveNPCs permutes these three objects across these
# three (map, tile) homes, and nothing else moves: the positions below are the
# `objectiveNPCPositions` table read back as tiles.
#
# **The third one is the Elf Doctor, $05, and not the Elf Prince, $06.** The
# prince holds the check and never moves; the doctor is who has to be reached
# with the Herb before the prince gives it up, and he is the one the roll sends
# to Melmond or Bahamut's Cave. Reading $06 here would report every seed as
# unshuffled in the elf's half of the permutation, because the object it names
# is fixed -- and $06 is what tools/extract_npcs.py collects, so that tool
# cannot answer this on its own. Measured on `objnpc497`: bahamut and unne
# trade homes, $05 stays in Elfland Castle, $06 stays at its own separate tile
# (9,5) vs (8,6) in the same map.
OBJECTIVE_NPCS = {0x05: "elfdoc", 0x0B: "unne", 0x0E: "bahamut"}
OBJECTIVE_HOMES = {3: "melmond", 9: "elflandCastle", 39: "bahamutCaveB2"}
OBJECTIVE_TILES = {3: (0x1A, 0x01), 9: (0x09, 0x05), 39: (0x15, 0x03)}


def objective_roll(rom):
    """Which home each of the three objective NPCs stands in, or None.

    -> {"elfdoc": home name, "unne": ..., "bahamut": ...}.

    Takes a Rom rather than a Graph: this is a walk of one flat table and
    decompresses nothing, and a caller that only wants the roll should not have
    to build a graph to ask for it.

    None when the three are not one to a home. The whole object table is
    walked rather than the three homes, which is what makes "they only ever
    stand on three maps" a per-cartridge measurement rather than a premise: an
    objective NPC found anywhere else refuses the read instead of being
    dropped from it.
    """
    where = {}
    for map_id in range(MAP_COUNT):
        base = MAP_OBJECTS + map_id * OBJ_STRIDE
        for i in range(OBJS_PER_MAP):
            oid = rom.data[base + i * OBJ_RECORD]
            if oid in OBJECTIVE_NPCS:
                where.setdefault(OBJECTIVE_NPCS[oid], []).append(
                    (map_id,
                     rom.data[base + i * OBJ_RECORD + 1] & COORD_MASK,
                     rom.data[base + i * OBJ_RECORD + 2] & COORD_MASK))
    if sorted(where) != sorted(OBJECTIVE_NPCS.values()):
        return None
    if any(len(v) != 1 for v in where.values()):
        return None
    homes = {}
    for name, spots in where.items():
        map_id = spots[0][0]
        if map_id not in OBJECTIVE_HOMES:
            return None
        homes[name] = OBJECTIVE_HOMES[map_id]
    if sorted(homes.values()) != sorted(OBJECTIVE_HOMES.values()):
        return None
    return homes


def print_rolls(g):
    """The two permutations the flag string cannot say."""
    print("the gateway roll -- three one-way gateways across two Cardia")
    print("landings and Bahamut's Cave, No-Overworld only")
    roll = gateway_roll(g)
    if roll is None:
        print("  no gateways on this cartridge: those three teleport ids do not")
        print("  land on the three known tiles, which is every mode but")
        print("  No-Overworld and every cartridge FFR did not write.")
    else:
        for r in roll:
            m, x, y = r["dest"]
            where = ", ".join(f"({a},{b})" for a, b in r["tiles"])
            print(f"  {GATEWAY_SOURCE_NAMES[r['teleport']]:12s} "
                  f"${r['teleport']:02X} at "
                  f"{where or 'NOT ON THIS MAP':16s} -> {r['landing']:14s} "
                  f"{MAP_NAMES[m]} ({x:02X},{y:02X})")
            if not r["tiles"]:
                print("       the id is not on the map the call order says it is "
                      "written to;")
                print("       the destination above is still what it does.")
    print()
    print("the objective-NPC roll -- Bahamut, Dr Unne and the Elf Doctor")
    print("across Melmond, Elfland Castle and Bahamut's Cave B2")
    homes = objective_roll(g.rom)
    if homes is None:
        print("  not one NPC to a home on this cartridge -- refusing to guess.")
        return
    for name in sorted(homes):
        print(f"  {name:9s} -> {homes[name]}")
    if homes == {"elfdoc": "elflandCastle", "unne": "melmond",
                 "bahamut": "bahamutCaveB2"}:
        print("  (the unrolled arrangement -- either the flag was off, or it")
        print("   rolled the identity)")


def print_gates(g):
    """Where the No-Overworld gate NPCs stand, and what each one wants."""
    where = talk_routine_bank(g.rom.data)
    if where is None:
        print("no talk jump table in this image")
        return
    print(f"Talk jump table at ${where[0]:02X}:${where[1]:04X}")
    gates = noverworld_gate_items(g.rom)
    if gates is None:
        print("  not a No-Overworld gate layout -- these eight objects share the")
        print("  generic routines they have on a standard cartridge, so none of")
        print("  them is blocking anything.")
        return
    placed = {}
    for m in range(MAP_COUNT):
        for oid, x, y in g.objects(m):
            placed.setdefault(oid, []).append((m, x, y))
    for item in sorted(gates):
        print(f"  {item} (routine ${gates[item]:04X})")
        for oid in sorted(o for o, i in NOVERWORLD_GATES.items() if i == item):
            for m, x, y in placed.get(oid, []):
                print(f"      ${oid:02X} {GATE_OBJ_NAMES[oid]:22s} "
                      f"{MAP_NAMES[m]} ({x},{y})")
            if oid not in placed:
                print(f"      ${oid:02X} {GATE_OBJ_NAMES[oid]:22s} not placed on any map")



def print_trades(g):
    """Which objects want an item handed over before they give anything up."""
    reqs = talk_requirement_bytes(g.rom)
    if reqs is None:
        print("no requirement table in this image -- the talk table has not been")
        print("moved, so these are four-byte records with no requirement byte.")
        return
    items = talk_item_requirements(g.rom)
    placed = {}
    for m in range(MAP_COUNT):
        for oid, x, y in g.objects(m):
            placed.setdefault(oid, []).append((m, x, y))
    names = {oid: name for name, oid in NPC_IDS.items()}
    print(f"{len(items)} objects want something handed over first")
    for oid in sorted(items):
        where = ", ".join(f"{MAP_NAMES[m]} ({x},{y})" for m, x, y in placed.get(oid, []))
        print(f"  ${oid:02X} {names.get(oid, GATE_OBJ_NAMES.get(oid, '')):22s} "
              f"{items[oid]:9s} {where or 'not placed on any map'}")
    unread = sorted(oid for oid, b in reqs.items()
                    if b and oid not in items and b in ITEM_RAM)
    if unread:
        print("  and %d objects carry a requirement byte their script never reads:"
              % len(unread))
        for oid in unread:
            print(f"      ${oid:02X} {names.get(oid, ''):22s} byte says "
                  f"{ITEM_RAM[reqs[oid]]}")

# The seven floors of the Temple of Fiends Revisited gauntlet, Chaos's own room
# excluded. No-Overworld strips the 4-orbs special off TempleOfFiends (20,17) --
# vanilla has both the special and a teleport there, which is the time warp --
# and repoints the plain teleport straight at TempleOfFiendsRevisitedChaos. So
# the mode skips the gauntlet, nothing on the cartridge teleports into these
# seven, and MetroidVaniaMap.cs gives them a backdrop and a tileset but no entry
# in its teleporter table. Verified on seed F258553F.
TOFR_INTERIOR = (
    "TempleOfFiendsRevisited1F", "TempleOfFiendsRevisited2F",
    "TempleOfFiendsRevisited3F", "TempleOfFiendsRevisitedEarth",
    "TempleOfFiendsRevisitedFire", "TempleOfFiendsRevisitedWater",
    "TempleOfFiendsRevisitedAir",
)


def check_all_reachable(g, mode, why=None):
    """With every item in hand, every map must be reachable from the doors.

    The oracle this repo wrote down after reading standard maps out of the wrong
    bank for weeks, and then never ran. It is the cheapest possible test of the
    whole routing stack -- map decompression, tile properties, both teleport
    tables, the door list and the gate objects all have to be right at once for
    it to pass -- and it fails loudly on every one of those going wrong.

    No-Overworld only, and not because the other modes are trusted. It is a
    theorem there and nowhere else: MetroidVaniaMap.cs connects the maps with a
    hand-authored table, so a map the walk cannot find is this tool's fault. A
    standard cartridge routes through an overworld the walk does not model, and a
    stock 16-bank image has no extended teleport table at all -- both would fail
    this for reasons that are not bugs.

    The ToFR gauntlet is the one documented exception, and it is checked rather
    than waved through: the mode reaches Chaos by a shortcut, so Chaos's room
    still has to be reachable, and the seven floors it skips still have to be
    unreachable for that reason and not some other. A seed that wires them up
    passes too -- an excepted map being reachable was never the failure.
    """
    if mode is None:
        print("self-check SKIPPED: the all-items reachability oracle needs the "
              f"GameMode, which could not be read ({why})")
        return True
    if mode != GAME_MODE_NOVERWORLD:
        return True
    reach = g.reachable_maps(set(ITEM_NAMES))
    skipped = {MAP_NAMES.index(n) for n in TOFR_INTERIOR}
    chaos = MAP_NAMES.index("TempleOfFiendsRevisitedChaos")
    if chaos not in reach:
        print("self-check FAILED: TempleOfFiendsRevisitedChaos is unreachable, so "
              "the Temple of Fiends shortcut this mode relies on is not there")
        return False
    missed = sorted(set(range(MAP_COUNT)) - reach - skipped)
    if missed:
        print(f"self-check FAILED: {len(missed)} of {MAP_COUNT} maps cannot be "
              "reached from the doors even holding every item")
        for m in missed[:10]:
            print(f"    {MAP_NAMES[m]}")
        if len(missed) > 10:
            print(f"    ... and {len(missed) - 10} more")
        return False
    also = sorted(skipped & reach)
    print(f"self-check OK: {len(reach - skipped)} of {MAP_COUNT} maps reachable "
          f"from the doors with every item in hand; the {len(skipped)} ToFR "
          "gauntlet floors the mode skips are not, as expected"
          + (f" (though {len(also)} of them are wired up on this seed)" if also else ""))
    return True


def check_talk_bank(g):
    """The talk table must not be read from the bank FFR abandoned.

    FFR leaves a byte-perfect vanilla jump table at $90D3 of the bank it moved
    the routines *to*, so the wrong address returns a confident answer in which
    no gate NPC is a gate. This is the same failure the standard maps had in
    bank $04, and it cost an afternoon here too.
    """
    where = talk_routine_bank(g.rom.data)
    if where is None:
        print("self-check FAILED: no talk jump table found at all")
        return False
    bank, addr = where
    expanded = len(g.rom.data) > INES_HEADER + 16 * BANK_SIZE
    # One test, not two: talk_routine_bank only ever returns TALK_JUMP_TBL
    # alongside the vanilla bank, so an address check and a (bank, address)
    # check say exactly the same thing.
    if expanded and addr == TALK_JUMP_TBL:
        print(f"self-check FAILED: talk table read from bank ${bank:02X} at "
              f"${addr:04X}, which is the stale copy FFR leaves behind, not "
              "lut_MapObjTalkJumpTbl_new")
        return False
    gates = noverworld_gate_items(g.rom)
    mode, why = game_mode(g.rom)
    if mode == GAME_MODE_NOVERWORLD and gates is None:
        print("self-check FAILED: GameMode 2 but the eight gate NPCs do not sort "
              "into four routines -- the talk table is being misread")
        return False
    print(f"self-check OK: talk routines in bank ${bank:02X} at ${addr:04X}"
          + (f", gates {', '.join(sorted(gates))}" if gates else ", no gate layout"))
    # The address is checked on every image; the gate layout above it only means
    # anything once the GameMode is readable. Say so, rather than letting a
    # skipped half hide behind the OK line.
    if mode is None:
        print("self-check SKIPPED: the gate-layout half of this test needs the "
              f"GameMode, which could not be read ({why})")
    return check_trades(g)


def pack_item_codes():
    """Every item code items/items.json defines, stage codes included, or None
    if the pack is not beside this script.

    What makes a trade requirement usable is a code the *pack* can turn on. Its
    own ITEM_RAM values are not that test: every name a requirement resolves to
    came out of ITEM_RAM one line earlier, so asking whether it is in ITEM_RAM
    answers yes by construction and guards nothing. items.json is the list a
    rule naming an item actually has to appear in.
    """
    path = os.path.join(HERE, "..", "items", "items.json")
    try:
        with open(path) as f:
            items = json.load(f)
    except OSError:
        return None
    codes = set()
    for item in items:
        for where in [item] + list(item.get("stages") or []):
            for code in (where.get("codes") or "").split(","):
                if code.strip():
                    codes.add(code.strip())
    return codes


def check_trades(g):
    """The two readers of the same talk table must not contradict each other.

    talk_item_requirements reads a per-object requirement byte and checks the
    object's script actually consults it; gate_objects groups objects onto the
    routines noverworld_gate_items identified. They look at different fields for
    different reasons, so where both have an opinion about an object, a
    disagreement means one of them is reading the wrong thing.
    """
    items = talk_item_requirements(g.rom)
    if items is None:
        print("self-check OK: no requirement table -- a stock image has none")
        return True
    codes = pack_item_codes()
    if codes is None:
        print("self-check SKIPPED: items/items.json is not beside this script, "
              "so the trade names cannot be checked against the pack's codes")
    else:
        unknown = sorted(set(items.values()) - codes)
        if unknown:
            print(f"self-check FAILED: requirement names {unknown}, which the "
                  "pack defines no item code for -- a rule naming one could "
                  "never be satisfied")
            return False
    gates = gate_objects(g.rom) or {}
    clash = sorted(oid for oid in set(gates) & set(items) if gates[oid] != items[oid])
    if clash:
        for oid in clash:
            print(f"self-check FAILED: object ${oid:02X} reads as a {gates[oid]} "
                  f"gate and a {items[oid]} trade")
        return False
    print(f"self-check OK: {len(items)} trades read, none contradicting the gates")
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
    """Every place an NPC stands, read from the routed ROM's own object table.

    tools/npc_positions.json is derived from a vanilla cartridge and covers only
    the ten NPCs the tracker needs -- not the Elf Doctor. Reading lut_MapObjects
    out of the ROM in hand costs nothing and stays right if a seed moves anyone.

    A list, not one spot: an object id can sit on more than one map. $13, the
    Fairy, is in both Gaia and Ice Cave B1 on a stock cartridge, and answering
    with whichever came first reports "no way in" for an NPC standing somewhere
    wide open.
    """
    key = name.lower().replace(" ", "").replace("'", "")
    if key not in NPC_IDS:
        sys.exit(f"no NPC {name!r}; known: {', '.join(sorted(NPC_IDS))}")
    oid = NPC_IDS[key]
    spots = [{"map_id": m, "tile_col": x, "tile_row": y}
             for m in range(MAP_COUNT)
             for got, x, y in g.objects(m) if got == oid]
    if not spots:
        sys.exit(f"{name} (object ${oid:02X}) does not appear on any map in this ROM")
    return spots


def route_to_npc(g, spots, have):
    """(spot, route, reached) for the best of the places an NPC stands.

    Landing on his floor is not the same as being able to walk to him: two
    staircase chains into one map commonly arrive on two sides of a locked door,
    and the shorter chain is not always the useful one. So each spot is asked
    twice -- once for a landing he can be reached from, once for any landing at
    all -- and a full answer anywhere beats a partial one everywhere. That keeps
    "the map is reachable but he is not" reading differently from "there is no
    way in at all", which are not the same answer.
    """
    best_full, best_any = None, None
    for spot in spots:
        def lands_by_npc(map_id, arrive, spot=spot):
            return g.can_reach_npc(map_id, arrive, spot, have) is not None

        r = g.route(spot["map_id"], have, lands_by_npc)
        if r is not None:
            if best_full is None or len(r[1]) < len(best_full[1][1]):
                best_full = (spot, r)
            continue
        r = g.route(spot["map_id"], have)
        if r is not None and (best_any is None or len(r[1]) < len(best_any[1][1])):
            best_any = (spot, r)
    if best_full is not None:
        return best_full[0], best_full[1], True
    if best_any is not None:
        return best_any[0], best_any[1], False
    return spots[0], None, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("--to", help="destination map name, e.g. DwarfCave")
    ap.add_argument("--to-npc", help="destination NPC name, e.g. smith")
    ap.add_argument("--have", default="",
                    help="comma-separated items in hand: "
                         + ",".join(sorted(ITEM_NAMES))
                         + " (sigil is accepted for floater)")
    ap.add_argument("--dump", action="store_true", help="all doors and floor links")
    ap.add_argument("--tables", action="store_true", help="vanilla vs extended teleport tables")
    ap.add_argument("--trades", action="store_true",
                    help="what each NPC wants handed over before it gives anything")
    ap.add_argument("--gates", action="store_true",
                    help="No-Overworld gate NPCs and the item each one wants")
    ap.add_argument("--rolls", action="store_true",
                    help="the two permutations the flag string cannot say: "
                         "the Cardia gateways and the objective NPCs")
    ap.add_argument("--self-check", action="store_true", help="staircases must not be chests")
    ap.add_argument("-o", "--out", help="write the graph as JSON")
    args = ap.parse_args()

    rom = Rom(args.rom)
    have = {ITEM_ALIASES.get(s.strip(), s.strip())
            for s in args.have.split(",") if s.strip()}
    unknown = have - set(ITEM_NAMES)
    if unknown:
        sys.exit(f"unknown item(s): {', '.join(sorted(unknown))}")

    # Anything that follows a staircase reads FFR's extended teleport tables, so
    # ask whether this cartridge has any before believing what is at that offset.
    # The rest is exempt because none of it consults them: --self-check and the
    # bare door table read vanilla structures, and --tables is the thing you run
    # to see what is at that offset on an image that has no such tables.
    info = ffr_info(rom)
    if info is None and any((args.dump, args.to, args.to_npc, args.out)):
        sys.exit(f"{args.rom}: no FFRInfo record -- this is not a Final Fantasy "
                 "Randomizer cartridge, and the tables this tool routes with only "
                 "exist on one. Try --tables to see what is at that offset.")

    g = Graph(rom)
    tabs = tab_labels()

    ok, npc_reached = True, True
    if args.self_check:
        ok = self_check(g)
    if args.gates:
        print_gates(g)
    if args.rolls:
        print_rolls(g)
    if args.trades:
        print_trades(g)
    if args.tables:
        print_tables(g)
    if args.dump:
        print_doors(g, tabs)
        print_floors(g, tabs, have)
    if args.to:
        print()
        print_route(g, tabs, resolve_map(args.to), have)
    if args.to_npc:
        spots = resolve_npc(g, args.to_npc)
        spot, r, reached = route_to_npc(g, spots, have)
        print()
        where = ", ".join(f"{MAP_NAMES[p['map_id']]} ({p['tile_col']},{p['tile_row']})"
                          for p in spots)
        print(f"{args.to_npc} stands in {where}"
              + (f" -- routing to the {MAP_NAMES[spot['map_id']]} one" if len(spots) > 1
                 else ""))
        arrive = show_route(g, tabs, spot["map_id"], have, r)
        if arrive is not None and reached:
            steps = g.can_reach_npc(spot["map_id"], arrive, spot, have)
            print(f"    walk {steps} more steps to {args.to_npc} at "
                  f"({spot['tile_col']},{spot['tile_row']})")
        elif arrive is not None:
            npc_reached = False
            print(f"    ...but you cannot walk to {args.to_npc} from anywhere this"
                  " map can be entered"
                  + (f" carrying only {', '.join(sorted(have))}" if have
                     else " with nothing in hand")
                  + " -- try --have key")
        else:
            npc_reached = False
    if not any((args.self_check, args.gates, args.rolls, args.trades, args.tables,
                args.dump, args.to, args.to_npc, args.out)):
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

    # Three outcomes, not two. "this seed does not let you reach him" is an
    # answer; "the reader is misreading the cartridge" is a failure, and a
    # caller that cannot tell them apart will eventually treat one as the other.
    if not ok:
        return 1
    return 0 if npc_reached else 2


if __name__ == "__main__":
    sys.exit(main())
