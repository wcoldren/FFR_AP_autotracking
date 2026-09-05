#!/usr/bin/env python3
"""The two permutations the flag string cannot say, read off a cartridge.

`entrance_graph.gateway_roll` and `.objective_roll`. Both are short reads at
fixed offsets, so what is worth holding is not the arithmetic but the three
identifications underneath them, each of which was wrong in a plausible way at
some point on the way here:

  * the third objective NPC is the Elf **Doctor**, $05, not the Elf Prince,
    $06. The prince holds the check and never moves. Reading $06 reports every
    seed as unshuffled in that third of the permutation, and $06 is the id
    `tools/extract_npcs.py` collects.
  * the three gateway teleport ids are fixed and only their destinations
    permute, so "which source is this" is a question about the source map, not
    about the id.
  * a cartridge with no such gateways has to say so rather than reporting the
    ordinary teleports those ids carry.

The tables are checked with no cartridge at all. The objective half then runs
against FF1_ROM with a permutation written into the object table, which is a
three-byte-record swap and needs no seed that rolled the flag. The gateway half
wants a real No-Overworld cartridge and looks for one beside the ones this
machine already names, the way test_lane_cartridges.py does; without one it
says so rather than passing quietly.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import entrance_graph as eg                                    # noqa: E402

fails = []


def ok(cond, label, got=""):
    print(f"{'ok  ' if cond else 'FAIL'} {label:62} {got}")
    if not cond:
        fails.append(label)


# --- the tables, with no cartridge -----------------------------------------

ok(sorted(eg.GATEWAY_SOURCES) == sorted(eg.GATEWAY_IDS),
   "every gateway id has a source map")
ok([eg.MAP_NAMES[eg.GATEWAY_SOURCES[t]] for t in eg.GATEWAY_IDS]
   == ["Waterfall", "IceCaveB1", "Gaia"],
   "the sources are Waterfall, Ice Cave B1 and Gaia, in id order")
ok(sorted(eg.GATEWAY_LANDINGS.values())
   == ["bahamutCave", "cardiaCaravan", "cardiaForest"],
   "three distinct landings")
ok(len(eg.GATEWAY_LANDINGS) == len(eg.GATEWAY_IDS),
   "one landing per gateway, so a roll is a permutation")

# The trap this suite exists for. $06 is the Elf Prince, who does not move.
ok(eg.OBJECTIVE_NPCS.get(0x05) == "elfdoc",
   "the third objective NPC is the Elf Doctor, $05")
ok(0x06 not in eg.OBJECTIVE_NPCS,
   "and not the Elf Prince, $06, who holds the check and stays put")
ok(sorted(eg.MAP_NAMES[m] for m in eg.OBJECTIVE_HOMES)
   == ["BahamutCaveB2", "ElflandCastle", "Melmond"],
   "the three homes are Melmond, Elfland Castle and Bahamut's Cave B2")
# NPCs.cs:277's objectiveNPCPositions, which is where the roll writes them.
ok(eg.OBJECTIVE_TILES == {3: (0x1A, 0x01), 9: (0x09, 0x05), 39: (0x15, 0x03)},
   "the home tiles are FFR's own three positions")
ok(sorted(eg.OBJECTIVE_TILES) == sorted(eg.OBJECTIVE_HOMES),
   "every home has a tile")


# --- the objective roll, on a permutation written into the table -----------

def record_at(rom, oid):
    """File offset of the first lut_MapObjects record holding this object."""
    for map_id in range(eg.MAP_COUNT):
        base = eg.MAP_OBJECTS + map_id * eg.OBJ_STRIDE
        for i in range(eg.OBJS_PER_MAP):
            if rom.data[base + i * eg.OBJ_RECORD] == oid:
                return base + i * eg.OBJ_RECORD
    return None


def free_slot(rom, map_id):
    """A record on this map that no object occupies."""
    base = eg.MAP_OBJECTS + map_id * eg.OBJ_STRIDE
    for i in range(eg.OBJS_PER_MAP):
        if rom.data[base + i * eg.OBJ_RECORD] == 0:
            return base + i * eg.OBJ_RECORD
    return None


path = os.environ.get("FF1_ROM")
if not path:
    print("SKIP  set FF1_ROM to a Final Fantasy cartridge for the object table")
else:
    rom = eg.Rom(path)
    rom.data = bytearray(rom.data)
    g = eg.Graph(rom)

    # Whatever this cartridge rolled, not an assumed arrangement: FF1_ROM may
    # be a seed that rolled the flag, and the swap below is checked against
    # what was there rather than against the vanilla trio.
    before = eg.objective_roll(g)
    ok(before is not None, "the three NPCs are one to a home on FF1_ROM",
       "" if before else "-- is this a Final Fantasy cartridge?")

    if before is not None:
        unne, bah = record_at(rom, 0x0B), record_at(rom, 0x0E)
        keep = bytes(rom.data)
        # What the roll itself does: the two objects trade positions, so the
        # whole three-byte record moves.
        one = bytes(rom.data[unne:unne + 3])
        two = bytes(rom.data[bah:bah + 3])
        rom.data[unne:unne + 3] = two
        rom.data[bah:bah + 3] = one
        after = eg.objective_roll(g)
        want = dict(before)
        want["unne"], want["bahamut"] = before["bahamut"], before["unne"]
        ok(after == want, "swapping two records swaps two homes", str(after))
        ok(after["elfdoc"] == before["elfdoc"],
           "and leaves the third where it was")

        # An objective NPC anywhere but the three homes is a cartridge this
        # read does not describe, and the answer is nothing rather than two
        # thirds of an answer.
        rom.data[:] = keep
        spare = free_slot(rom, 0)          # Coneria Town, not one of the homes
        ok(spare is not None, "a free object slot to move an NPC into")
        if spare is not None:
            rom.data[spare:spare + 3] = rom.data[unne:unne + 3]
            rom.data[unne:unne + 3] = b"\x00\x00\x00"
            ok(eg.objective_roll(g) is None,
               "an objective NPC off the three homes refuses the read")
        rom.data[:] = keep
        ok(eg.objective_roll(g) == before, "and the table is put back")


# --- the gateway roll, on real cartridges ----------------------------------
#
# Looked for beside the cartridges this machine already names rather than at a
# path written down here, since where seeds live is a fact about the machine.

def search_roots():
    roots = []
    rom_path = os.environ.get("FF1_ROM")
    if rom_path and os.path.isfile(rom_path):
        roots.append(os.path.dirname(os.path.dirname(os.path.abspath(rom_path))))
    corpus = os.environ.get("FF1_CORPUS")
    if corpus and os.path.isdir(corpus):
        roots.append(os.path.abspath(corpus))
    out = []
    for r in roots:
        if os.path.isdir(r) and not any(
                r == o or r.startswith(o + os.sep) for o in out):
            out.append(r)
    return out


carts = []
for root in search_roots():
    for dirpath, _dirs, files in os.walk(root):
        for f in sorted(files):
            if f.endswith(".nes"):
                carts.append(os.path.join(dirpath, f))

# gateway_destinations is the cheap half -- three tables and no decompression
# -- so every cartridge is asked, and only the ones that answer are walked.
gateways = []
for c in sorted(carts):
    try:
        r = eg.Rom(c)
    except Exception:
        continue
    if eg.gateway_destinations(r) is not None:
        gateways.append(c)

if not carts:
    print("SKIP  no cartridges found: set FF1_ROM or FF1_CORPUS")
elif not gateways:
    print("SKIP  no No-Overworld cartridge among %d found: the gateway half "
          "needs one" % len(carts))
else:
    seen = set()
    for c in gateways:
        roll = eg.gateway_roll(eg.Graph(eg.Rom(c)))
        name = os.path.basename(c)
        ok(len(roll) == 3, f"{name}: three gateways")
        ok(sorted(r["landing"] for r in roll)
           == sorted(eg.GATEWAY_LANDINGS.values()),
           f"{name}: one gateway per landing")
        ok(all(r["tiles"] for r in roll),
           f"{name}: every id stands on the map the call order says",
           str([(hex(r["teleport"]), r["tiles"]) for r in roll]))
        seen.add(tuple(r["landing"] for r in roll))
    print(f"     {len(gateways)} No-Overworld cartridge(s), "
          f"{len(seen)} distinct permutation(s)")

# A cartridge that has no gateways must say so rather than reporting whatever
# those three ids carry. Every non-No-Overworld cartridge on this machine is
# the sample.
others = [c for c in carts if c not in gateways]
if others:
    ok(all(eg.gateway_destinations(eg.Rom(c)) is None for c in others),
       f"{len(others)} cartridge(s) without gateways report none")

print("test_two_rolls: " + ("FAILED " + "; ".join(fails) if fails else "ok"))
sys.exit(1 if fails else 0)
