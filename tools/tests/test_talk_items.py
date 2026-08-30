"""What a talk routine demands before it hands anything over.

Set FF1_ROM to a cartridge. An FFR seed of any mode is read for real; a stock
image has no requirement table at all and the reader has to say so rather than
inventing one. Without FF1_ROM it skips rather than passing quietly.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import entrance_graph as e                                     # noqa: E402

fails = []


def ok(cond, label, got=""):
    print(f"{'ok  ' if cond else 'FAIL'} {label:58} {got}")
    if not cond:
        fails.append(label)


# Every one of these is a vanilla trade the randomizer keeps: the item on the
# left has to be in the bag before the NPC on the right does anything. They are
# not read out of a table here -- the point of the check is that a cartridge
# produces them without being told.
EXPECTED = {
    0x05: "herb",       # the Elf Doctor, for the sleeping prince
    0x07: "crown",      # Astos
    0x08: "tnt",        # Nerrick
    0x09: "adamant",    # the Smith
    0x0A: "crystal",    # Matoya
    0x0B: "slab",       # Dr Unne
    0x14: "ruby",       # Titan
}

# The Elf Prince is the trap this reader exists to survive. His requirement byte
# reads 5 -- the Mystic Key -- and that is the item he *gives*: his script never
# looks at the byte. A reader that trusted the table alone would gate the key on
# holding the key.
ELF_PRINCE = 0x06

rom_path = os.environ.get("FF1_ROM")
if not rom_path or not os.path.exists(rom_path):
    print("SKIP set FF1_ROM to a Final Fantasy cartridge to run this")
else:
    rom = e.Rom(rom_path)
    reqs = e.talk_requirement_bytes(rom)
    items = e.talk_item_requirements(rom)

    if reqs is None:
        # A stock cartridge: 4-byte talk records, no requirement byte, and the
        # jump table still at its original address.
        ok(items is None, "a stock image has no requirement table and says so",
           repr(items))
        ok(e.talk_routine_bank(rom.data)[1] == e.TALK_JUMP_TBL,
           "and that is because the talk table never moved")
    else:
        ok(items is not None, "an FFR cartridge yields a requirement table")
        for oid, want in EXPECTED.items():
            ok(items.get(oid) == want,
               f"object ${oid:02X} wants the {want}", str(items.get(oid)))

        ok(reqs.get(ELF_PRINCE, 0) != 0,
           "the Elf Prince's requirement byte is set", hex(reqs.get(ELF_PRINCE, 0)))
        ok(ELF_PRINCE not in items,
           "and is still not read as a requirement, because his script never"
           " reads it")

        # Every item named has to be one the tracker knows, or the rule it ends
        # up in is a code nothing can satisfy. Against items/items.json, not
        # against ITEM_RAM: every name here came out of ITEM_RAM a moment ago,
        # so that comparison is empty by construction and would keep passing if
        # the pack lost the item entirely.
        codes = e.pack_item_codes()
        ok(codes is not None, "items/items.json is readable")
        unknown = sorted(set(items.values()) - (codes or set()))
        ok(not unknown, "every requirement names an item the pack has a code for",
           str(unknown))

        # Two readers, one cartridge. gate_objects derives what the No-Overworld
        # gate NPCs want by grouping objects onto routines; this one reads the
        # per-object requirement. Where they both have an opinion they have to
        # agree -- and where they do not overlap at all, that is the honest
        # answer too, since a gate NPC's requirement byte is zero and its check
        # is in the routine.
        gates = e.gate_objects(rom) or {}
        clash = sorted(oid for oid in set(gates) & set(items)
                       if gates[oid] != items[oid])
        ok(not clash, "the gate reader and the trade reader do not contradict",
           str(clash))

        # A routine body stops at the requirement table, not MAX_ROUTINE past
        # its own start. `starts` holds only jump-table targets, so the highest
        # routine has nothing above it to bound it and takes the flat 0x200 --
        # and $BA00, the requirement table, is in this same bank. Read as code,
        # two data coincidences (`A6 74` and `BD 20 60`) hand every object on
        # that routine a requirement it never checks.
        #
        # Built rather than waited for: point the Elf Prince at a routine
        # sixteen bytes below the table and plant the pattern in the table
        # itself. He is the subject because his byte is already set and already
        # correctly ignored, so a name appearing for him is the fabrication and
        # nothing else.
        near = e.Rom(rom_path)
        near.data = bytearray(near.data)
        bank, tbl = e.talk_routine_bank(near.data)
        slot = e.bank_off(bank, tbl) + ELF_PRINCE * 2
        near.data[slot:slot + 2] = (e.TALK_DATA_NEW - 0x10).to_bytes(2, "little")
        table = e.bank_off(bank, e.TALK_DATA_NEW)
        near.data[table:table + 5] = e.LDX_REQUIREMENT + e.LDA_ITEMS_X
        invented = e.talk_item_requirements(near)
        ok(invented is not None and ELF_PRINCE not in invented,
           "a routine beside the requirement table does not read it as code",
           str(invented.get(ELF_PRINCE) if invented else invented))

    # The refusal, on whatever cartridge is to hand: point the engine's bank
    # constant back at the vanilla bank and the reader must stop finding a
    # table, rather than reading six-byte records out of wherever $BA00 lands.
    stock = e.Rom(rom_path)
    stock.data = bytearray(stock.data)
    if e.TALK_BANK_CONST < len(stock.data):
        stock.data[e.TALK_BANK_CONST] = e.VANILLA_TALK_BANK
        ok(e.talk_item_requirements(stock) is None,
           "a talk table read back at the vanilla bank yields no requirements",
           repr(e.talk_item_requirements(stock)))

print("\n" + ("FAILURES: " + ", ".join(fails) if fails else "ALL PASS"))
sys.exit(1 if fails else 0)
