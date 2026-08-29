#!/usr/bin/env python3
"""Pull treasure-chest tile positions out of a Final Fantasy (NES) ROM.

FFR randomizes what is *in* a chest, not where the chest *is*, so vanilla map
data is the right source for tracker map markers. Point this at an FFR
cartridge anyway and it reads that cartridge's own maps: which bank those live
in is asked of the image rather than assumed -- see standard_map_bank below.

Everything below is grounded in BenWenger's FinalFantasyDisassembly:

  Constants.inc:86   BANK_STANDARDMAPS = $04
  Constants.inc:450  lut_SMPtrTbl      = $8000  (BANK_STANDARDMAPS)
  Constants.inc:93   BANK_SMINFO       = $00
  Constants.inc:474  lut_SMTilesetProp = $8800  (BANK_SMINFO)
  Constants.inc:480  lut_Tilesets      = $ACC0  (BANK_TELEPORTINFO = $00)
  bank_0F.asm:4121   LoadStandardMap   -- pointer decoding
  bank_0F.asm:4227   DecompressMap     -- the RLE
  "some formats.txt" -- SM tile property layout

Usage:  tools/extract_chests.py /path/to/"Final Fantasy (USA).nes" [-o out.json]
"""

import argparse
import json
import sys

INES_HEADER = 0x10
BANK_SIZE = 0x4000

# A standard-map pointer is 16-bit. LoadStandardMap masks the high byte with
# $3F/$80 for the address and shifts its top two bits out to pick a bank
# 4..7 -- which makes the whole thing a flat offset into banks 4-7.
SM_BANK_VANILLA = 0x04
SM_DATA_BASE = INES_HEADER + SM_BANK_VANILLA * BANK_SIZE   # 0x10010
SM_PTR_TBL = SM_DATA_BASE                    # lut_SMPtrTbl sits at its head

# ...but only on a stock cartridge. FFR relocates every standard map into bank
# $14 of the expanded image and patches the engine's two #BANK_STANDARDMAPS
# references to match:
#
#   FF1Lib/StandardMaps/StandardMaps.cs:143-149
#       int MapDataOutputOffset = (0x4000 * 0x14) + 0x80;
#       rom.PutInBank(0x1F, 0xD127, Blob.FromHex("14"));
#       rom.PutInBank(0x1F, 0xD145, Blob.FromHex("14"));
#
# StandardMaps.Write() is in Randomize.cs:466's unconditional "write back
# everything" block, so this is true of *every* FFR seed, whatever its flags.
# Reading bank $04 on one of those does not fail: banks 4-7 still hold the
# vanilla maps FFR never erased, so you get a complete, confident, wrong
# answer -- vanilla topology for a cartridge the engine reads elsewhere.
#
# Bank $1F is the fixed bank at $C000-$FFFF, and FF1Rom.PutInBank (FF1Rom.cs:79)
# special-cases it to (address - 0xC000) rather than the usual (address - 0x8000).
SM_BANK_CONST = 0x1F, 0xD127
SM_BANK_CONST_MIRROR = 0x1F, 0xD145

TILESET_PROP = INES_HEADER + 0x0800          # lut_SMTilesetProp, bank 0
TILESET_LUT = INES_HEADER + 0x2CC0           # lut_Tilesets, bank 0

MAP_COUNT = 61          # standard maps 0..60
MAP_DIM = 64            # 64x64 tiles
TILES_PER_SET = 128     # 7-bit tile ids
PROP_STRIDE = TILES_PER_SET * 2   # 2 property bytes per tile

TILE_KIND_CHEST = 0x04  # "ssss=0100 = treasure chest (next byte is TC id)"


def _fixed_bank_off(bank, addr):
    """File offset of an address in the $C000-$FFFF fixed bank."""
    return INES_HEADER + bank * BANK_SIZE + (addr - 0xC000)


def standard_map_bank(rom):
    """Which PRG bank this image keeps its standard maps in.

    Read from the engine's own constant rather than assumed, so an FFR that
    moves the maps again is followed rather than silently misread. A stock
    cartridge is 16 banks and has no $1F:D127 at all, which is the fallback:
    vanilla keeps them in bank $04.
    """
    off = _fixed_bank_off(*SM_BANK_CONST)
    if off >= len(rom):
        return SM_BANK_VANILLA
    bank = rom[off]
    if INES_HEADER + bank * BANK_SIZE >= len(rom):
        return SM_BANK_VANILLA
    return bank


def map_data_base(rom):
    """File offset of lut_SMPtrTbl, which the map data immediately follows."""
    bank = standard_map_bank(rom)
    if bank == SM_BANK_VANILLA:
        return SM_DATA_BASE
    return INES_HEADER + bank * BANK_SIZE


def decompress_map(rom, start):
    """DecompressMap (bank_0F.asm:4227).

    <$80        single tile
    $80-$FE     run: tile = b & $7F, next byte = length (0 means 256)
    $FF         terminate
    """
    out = bytearray()
    i = start
    while len(out) < MAP_DIM * MAP_DIM:
        b = rom[i]
        i += 1
        if b == 0xFF:
            break
        if b < 0x80:
            out.append(b)
            continue
        tile = b & 0x7F
        run = rom[i]
        i += 1
        out.extend([tile] * (run if run else 256))
    return out


def chest_tiles(rom, tileset_id):
    """tile_id -> chest_index, for every treasure tile in this tileset."""
    base = TILESET_PROP + tileset_id * PROP_STRIDE
    found = {}
    for tile in range(TILES_PER_SET):
        b0, b1 = rom[base + tile * 2], rom[base + tile * 2 + 1]
        if (b0 >> 1) & 0x0F == TILE_KIND_CHEST:
            found[tile] = b1
    return found


def extract(rom):
    """-> (chests, per_map). chests maps a chest index to a LIST of placements.

    A chest index can be placed on more than one tile, and even on more than one
    map -- the Ordeals and Marsh look-alike rooms reuse an index so that opening
    any one of them clears the lot. Six indices do this, for ten extra
    placements. Keeping only the last would silently lose them, and
    map_locations is a list anyway.
    """
    tilesets = rom[TILESET_LUT:TILESET_LUT + MAP_COUNT]
    base = map_data_base(rom)
    chests = {}
    per_map = {}
    for map_id in range(MAP_COUNT):
        ptr = int.from_bytes(rom[base + map_id * 2:base + map_id * 2 + 2], "little")
        grid = decompress_map(rom, base + ptr)
        lut = chest_tiles(rom, tilesets[map_id])
        hits = []
        for pos, tile in enumerate(grid):
            idx = lut.get(tile)
            if idx is None:
                continue
            col, row = pos % MAP_DIM, pos // MAP_DIM
            hits.append(idx)
            chests.setdefault(idx, []).append(
                {"map_id": map_id, "tile_col": col, "tile_row": row})
        if hits:
            per_map[map_id] = sorted(hits)
    return chests, per_map


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()

    rom = open(args.rom, "rb").read()
    if rom[:4] != b"NES\x1a":
        sys.exit("not an iNES ROM")

    chests, per_map = extract(rom)
    placements = sum(len(v) for v in chests.values())
    dupes = {k: v for k, v in chests.items() if len(v) > 1}
    print(f"maps with chests: {len(per_map)}")
    print(f"distinct chest indices: {len(chests)} ({placements} placements)")
    lo, hi = min(chests), max(chests)
    print(f"chest index range: {lo}-{hi} (0x{lo:02X}-0x{hi:02X})")
    for k in sorted(dupes):
        where = ", ".join(f"map {p['map_id']} ({p['tile_col']},{p['tile_row']})" for p in dupes[k])
        print(f"  chest {k} is placed {len(dupes[k])}x: {where}")

    if args.out:
        with open(args.out, "w") as f:
            json.dump({str(k): chests[k] for k in sorted(chests)}, f, indent=1, sort_keys=True)
        print(f"wrote {args.out}")
    return chests, per_map


if __name__ == "__main__":
    main()
