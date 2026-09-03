"""`tools/shop_slot.py` against the cartridges, and against what FFR itself said.

The reader has a twin in `bridge/ffr_uat_bridge.lua`, and both are decoding a
layout nobody documented for them: `lut_ShopTypes` is not where a disassembly of
the original puts it, because FFR expands the ROM and the fixed bank moves. A
decode like that fails quietly and plausibly -- it returns *an* item id, just the
wrong one -- so the guard is not "does it run" but "does it agree with something
that was written down independently".

Three independent sources of truth, all recorded before this reader existed:

  * `seeds/ff1/duck-weekly-0831-v2/Spoiler_*.txt` -- FFR's own spoiler names the
    key item, its shop, and that shop's number: "Herb Elfland -> ElflandShop1",
    "Item Elfland - HERB", "- Elfland - Shop - Item.Elfland.63 -".
  * `docs/ISSUES.md` -- records FFR exporting `PravokaShop1` for `std497` and
    `ElflandShop4` for `drydock497`, which is the same fact for two Archipelago
    cartridges.
  * the shape of the thing: FFR places exactly one item in the slot, so more
    than one key item across the shops means the decode is wrong.

Needs the seed tree; without one this skips rather than passing quietly.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import shop_slot

SEEDS = os.environ.get("FF1_SEEDS",
                       os.path.expanduser("~/repos/AP/seeds/ff1"))

fails = 0


def ok(name, got, want):
    global fails
    if got == want:
        print(f"ok   {name:56s} {got}")
    else:
        fails += 1
        print(f"FAIL {name:56s} got={got!r} want={want!r}")


def load(*parts):
    path = os.path.join(SEEDS, *parts)
    if not os.path.exists(path):
        return None
    with open(path, "rb") as handle:
        return handle.read()


def one(pattern):
    """The single .nes under a seed directory, or None."""
    directory = os.path.join(SEEDS, pattern)
    if not os.path.isdir(directory):
        return None
    roms = [f for f in sorted(os.listdir(directory)) if f.endswith(".nes")]
    return load(pattern, roms[0]) if roms else None


if not os.path.isdir(SEEDS):
    print(f"SKIP  no seed tree at {SEEDS} -- set FF1_SEEDS")
    sys.exit(0)

# --- the spoiler's own answer -------------------------------------------------
# The one played cartridge whose spoiler was kept. Every field is checked,
# because getting the item right off the wrong shop would still be a bug.
rom = one("duck-weekly-0831-v2")
if rom is None:
    print("SKIP  duck-weekly-0831-v2 not in the seed tree")
else:
    slot = shop_slot.read(rom)
    ok("the spoiler's cartridge decodes at all", slot is not None, True)
    ok("...to the shop the spoiler numbers", slot.shop, 63)
    ok("...in the town the spoiler names", slot.town, "Elfland")
    ok("...holding the item the spoiler lists", shop_slot.ITEM_NAMES[slot.item], "Herb")
    ok("...watched at that item's inventory byte", hex(slot.watch), "0x6024")
    ok("...and not mistaken for an Archipelago cartridge", slot.archipelago, False)

# --- Archipelago cartridges ---------------------------------------------------
# These must short-circuit rather than decode: the slot holds the FireOrb
# sentinel, and its inventory byte $6032 is the Fire Orb's own.
for name in ("std497", "drydock497"):
    rom = load("oracle-4.9.7", name, name + ".nes")
    if rom is None:
        print(f"SKIP  oracle-4.9.7/{name} not in the seed tree")
        continue
    slot = shop_slot.read(rom)
    ok(f"{name} reads as an Archipelago cartridge", slot.archipelago, True)
    ok(f"{name} offers no inventory byte to watch", slot.watch, None)

# The same two cartridges, decoded past the short-circuit: the sentinel's shop
# is what FFR's export named, and that is the cross-check that established the
# table offsets in the first place.
for name, town in (("std497", "Pravoka"), ("drydock497", "Elfland")):
    rom = load("oracle-4.9.7", name, name + ".nes")
    if rom is None:
        continue
    base = shop_slot.type_base(rom)
    ok(f"{name}'s shop tables are found", base is not None, True)
    holders = [sid for sid in sorted(shop_slot.SHOP_TOWNS)
               if 18 in shop_slot.shop_stock(rom, base, sid)]
    ok(f"{name} has exactly one shop holding the sentinel", len(holders), 1)
    if holders:
        ok(f"{name}'s sentinel sits in the shop FFR exported",
           shop_slot.SHOP_TOWNS[holders[0]], town)

# --- the shape, across every cartridge in the tree ----------------------------
# Never more than one key item across the shops, on anything readable. `read`
# returns None on a second hit, so this catches a table offset that drifted.
#
# It also returns None on an image that is not an FFR cartridge at all -- a
# vanilla dump or another game's ROM left in the seed tree -- and that is not
# evidence of anything. The two are told apart by `type_base`: if the shop
# tables were found, the reader was reading FFR and stopping on a second key
# item is the drift this guard is for.
seen = 0
for root, _dirs, files in os.walk(SEEDS):
    for name in sorted(files):
        if not name.endswith(".nes"):
            continue
        with open(os.path.join(root, name), "rb") as handle:
            rom = handle.read()
        slot = shop_slot.read(rom)
        if slot is None and shop_slot.type_base(rom) is None:
            print(f"SKIP  {name:56s} no shop tables -- not an FFR cartridge")
            continue
        seen += 1
        if slot is None:
            ok(f"{name} decodes to a single slot", "more than one key item", "one slot")
        elif not slot.archipelago and slot.item is not None:
            # A key item id that ram_mapping.lua owns as an orb would mean the
            # reader walked off the table rather than that FFR shelved an orb.
            ok(f"{name}'s item is a real key item id",
               1 <= slot.item <= shop_slot.KEY_ITEM_MAX, True)

if seen:
    ok("cartridges examined", seen > 0, True)
else:
    # Same rule as the missing tree at the top: a corpus this reader cannot read
    # is a question this machine cannot answer, not an answer of "fine".
    print("SKIP  no FFR cartridges in the seed tree")

print("\nshop slot tests passed" if not fails else f"\n{fails} FAILURE(S)")
sys.exit(1 if fails else 0)
