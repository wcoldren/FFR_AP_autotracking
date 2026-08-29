#!/usr/bin/env python3
"""Pull map-object (NPC) tile positions out of a vanilla Final Fantasy (NES) ROM.

The companion to extract_chests.py, and for the same reason: FFR randomizes
what an NPC gives you, not where the NPC stands, so vanilla map data is the
right source for tracker map markers. (The one flag that does move them,
ShuffleObjectiveNPCs, is not read by this pack -- see the note in
ram_mapping.lua about sigil/mark for the same limitation.)

Grounded in BenWenger's FinalFantasyDisassembly:

  Constants.inc:90    BANK_OBJINFO    = $00
  Constants.inc:444   lut_MapObjects  = $B400  (BANK_OBJINFO)
  Constants.inc:249+  OBJID_* names
  bank_0F.asm:9890    the pointer maths -- lut_MapObjects + map_id*48
  bank_0F.asm:9506    LoadSingleMapObject -- the 3-byte record layout:
                        +0 object id
                        +1 X coord in the low 6 bits, behaviour flags in $C0
                        +2 Y coord in the low 6 bits
                      15 objects per map, whether used or not (id 0 = none).

The stride is 48 and the payload is 45: the loop stops at CMP #15*3 but the
table is indexed by map_id*48, so three bytes per map go unread. Walking it at
45 shifts every map after the first by a growing offset -- it stays plausible
for a while (the ids are still valid, the coords still in range) and then quietly
puts Nerrick in the wrong cave. Map 19 is Dwarf Cave; if this says 20, the
stride is wrong again.

Usage:  tools/extract_npcs.py /path/to/"Final Fantasy (USA).nes" [-o out.json]
"""

import argparse
import json
import sys

INES_HEADER = 0x10

# Bank 0 is mapped at $8000, so a BANK_OBJINFO address is a flat file offset.
# extract_chests.py resolves lut_SMTilesetProp ($8800) the same way.
MAP_OBJECTS = INES_HEADER + (0xB400 - 0x8000)

MAP_COUNT = 61          # standard maps 0..60
OBJS_PER_MAP = 15
RECORD = 3
MAP_STRIDE = 48         # not OBJS_PER_MAP * RECORD; see the note above
COORD_MASK = 0x3F       # LoadSingleMapObject masks both coords to 64 tiles

# Only the objects this tracker has any use for: the ones with a turn-in or a
# check behind them. Names match Constants.inc.
WANTED = {
    0x04: "bikke",
    0x07: "astos",
    0x08: "nerrick",
    0x09: "smith",
    0x0A: "matoya",
    0x0B: "unne",
    0x0D: "sarda",
    0x0E: "bahamut",
    0x13: "fairy",
    0x14: "titan",
    # The four fiends. Not turn-ins, but the orb behind each one is a location
    # the pack tracks, and their floors hold no chests at all -- which is why
    # earthB5, volcB5, seaB5 and sky5F went uncalibrated for so long: the
    # chest-centroid solver had nothing on them to match.
    0x1B: "lich",
    0x1C: "marilith",
    0x1D: "kraken",
    0x1E: "tiamat",
}


def extract(rom):
    found = {}
    for map_id in range(MAP_COUNT):
        base = MAP_OBJECTS + map_id * MAP_STRIDE
        for i in range(OBJS_PER_MAP):
            oid = rom[base + i * RECORD]
            name = WANTED.get(oid)
            if name is None:
                continue
            found.setdefault(name, []).append({
                "map_id": map_id,
                "tile_col": rom[base + i * RECORD + 1] & COORD_MASK,
                "tile_row": rom[base + i * RECORD + 2] & COORD_MASK,
            })
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()

    rom = open(args.rom, "rb").read()
    if rom[:4] != b"NES\x1a":
        sys.exit("not an iNES ROM")

    npcs = extract(rom)
    missing = sorted(set(WANTED.values()) - set(npcs))
    for name in sorted(npcs):
        where = ", ".join(
            f"map {p['map_id']} ({p['tile_col']},{p['tile_row']})" for p in npcs[name])
        print(f"{name:8} {where}")
    if missing:
        print("not placed on any standard map: " + ", ".join(missing))

    if args.out:
        with open(args.out, "w") as f:
            json.dump({k: npcs[k] for k in sorted(npcs)}, f, indent=1, sort_keys=True)
        print(f"wrote {args.out}")
    return npcs


if __name__ == "__main__":
    main()
