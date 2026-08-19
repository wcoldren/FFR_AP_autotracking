#!/usr/bin/env python3
"""Pull treasure-chest tile positions out of a vanilla Final Fantasy (NES) ROM.

FFR randomizes what is *in* a chest, not where the chest *is*, so vanilla map
data is the right source for tracker map markers.

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
SM_DATA_BASE = INES_HEADER + 4 * BANK_SIZE   # 0x10010
SM_PTR_TBL = SM_DATA_BASE                    # lut_SMPtrTbl sits at its head

TILESET_PROP = INES_HEADER + 0x0800          # lut_SMTilesetProp, bank 0
TILESET_LUT = INES_HEADER + 0x2CC0           # lut_Tilesets, bank 0

MAP_COUNT = 61          # standard maps 0..60
MAP_DIM = 64            # 64x64 tiles
TILES_PER_SET = 128     # 7-bit tile ids
PROP_STRIDE = TILES_PER_SET * 2   # 2 property bytes per tile

TILE_KIND_CHEST = 0x04  # "ssss=0100 = treasure chest (next byte is TC id)"


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
    chests = {}
    per_map = {}
    for map_id in range(MAP_COUNT):
        ptr = int.from_bytes(rom[SM_PTR_TBL + map_id * 2:SM_PTR_TBL + map_id * 2 + 2], "little")
        grid = decompress_map(rom, SM_DATA_BASE + ptr)
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
