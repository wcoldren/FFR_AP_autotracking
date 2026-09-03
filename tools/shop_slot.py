"""Which shop holds the key item, read off an FFR cartridge.

The Python twin of the reader in `bridge/ffr_uat_bridge.lua`. The bridge is what
runs during play; this is what the tests and the logic checker can point at a
whole corpus. The two have to agree, and `tools/tests/test_shop_slot.py` is what
holds them together.

Why the cartridge has to be read at all: FFR gives the item shop slot a
synthetic object id of 0xFF, so buying a key item out of a shop sets flag byte
0xFF bit 0x02 -- Archipelago location 767. But on the 4.9.x line
`GlobalImprovements.cs` installs that patch only under `if (archipelagoenabled)`,
so a solo seed never writes the byte. The shop's stock is in PRG ROM either way,
and since FFR places each key item exactly once, the item sitting in the shop
identifies the purchase by its inventory byte instead.
"""

HEADER = 0x10           # iNES header; ROM offsets below are headerless

SHOP_PTR = 0x38300      # lut_ShopData, bank 0x0E $8300; entry 0 is unused
# lut_ShopTypes lives in the fixed bank -- 0x0F on a 256K image, 0x1F once FFR
# expands to 512K. A disassembly of the original gives only the first.
SHOP_TYPE_CANDIDATES = (0x7EBB5, 0x3EBB5)
# FF1Lib/Data/ShopData.cs indices 60..65 and 69, plus the +1 the game applies
# (bank_0F.asm loads 70 for the caravan against FF1Lib index 69).
SHOP_TOWNS = {61: "Coneria", 62: "Pravoka", 63: "Elfland",
              64: "CrescentLake", 65: "Gaia", 66: "Onrac", 70: "Caravan"}
ITEM_BASE = 0x6020      # inventory byte for item id N
KEY_ITEM_MAX = 16       # 17-20 are the orbs and 21 the Shard, not shop stock

# NewCheckForSpace. Present only on an Archipelago cartridge; a solo seed keeps
# 0xEA all through here.
AP_PATCH = 0x39F48
AP_PATCH_HEAD = bytes((0xAE, 0x0C, 0x03, 0xE0, 0x16))

ITEM_NAMES = {1: "Lute", 2: "Crown", 3: "Crystal", 4: "Herb", 5: "Key", 6: "Tnt",
              7: "Adamant", 8: "Slab", 9: "Ruby", 10: "Rod", 11: "Floater",
              12: "Chime", 13: "Tail", 14: "Cube", 15: "Bottle", 16: "Oxyale"}


class ShopSlot:
    """What the cartridge says about the shop slot."""

    def __init__(self, shop=None, item=None, archipelago=False):
        self.shop = shop
        self.item = item
        self.archipelago = archipelago

    @property
    def town(self):
        return SHOP_TOWNS.get(self.shop)

    @property
    def watch(self):
        """The inventory byte a purchase shows up in, or None."""
        return None if self.item is None else ITEM_BASE + self.item

    def __repr__(self):
        if self.archipelago:
            return "ShopSlot(archipelago)"
        if self.item is None:
            return "ShopSlot(no key item in any shop)"
        return (f"ShopSlot({self.town} shop {self.shop}, "
                f"{ITEM_NAMES.get(self.item, self.item)}, ${self.watch:04X})")


def type_base(rom):
    """Where lut_ShopTypes actually is, found by reading rather than assuming.

    The six item shops must come back as type 6 and the caravan as 7, which is
    what makes the probe self-validating instead of a guess.
    """
    for base in SHOP_TYPE_CANDIDATES:
        if base + HEADER + 70 >= len(rom):
            continue
        if all((rom[base + HEADER + sid] & 0x07) == (7 if sid == 70 else 6)
               for sid in SHOP_TOWNS):
            return base
    return None


def shop_stock(rom, base, shop_id):
    """The item ids a shop sells, zero-terminated, at most five."""
    lo = rom[SHOP_PTR + HEADER + shop_id * 2]
    hi = rom[SHOP_PTR + HEADER + shop_id * 2 + 1]
    addr = lo | (hi << 8)
    if not 0x8000 <= addr < 0xC000:
        return []
    off = 0x38000 + HEADER + (addr - 0x8000)
    out = []
    for k in range(5):
        b = rom[off + k]
        if b == 0:
            break
        out.append(b)
    return out


def read(rom):
    """The cartridge's shop slot, or None when it cannot be read.

    An Archipelago cartridge short-circuits: its slot holds the FireOrb sentinel,
    whose inventory byte is the Fire Orb's own, so reading it as a purchase would
    be wrong in both directions. Flag byte 0xFF answers there instead.
    """
    if rom[AP_PATCH + HEADER:AP_PATCH + HEADER + len(AP_PATCH_HEAD)] == AP_PATCH_HEAD:
        return ShopSlot(archipelago=True)

    base = type_base(rom)
    if base is None:
        return None

    found = None
    for shop_id in sorted(SHOP_TOWNS):
        for item in shop_stock(rom, base, shop_id):
            if 1 <= item <= KEY_ITEM_MAX:
                # FFR places exactly one item in the slot, so a second reading
                # means the decode is wrong rather than the seed unusual.
                if found is not None:
                    return None
                found = (shop_id, item)

    # Nothing found is an ordinary outcome, not a failure: roughly half of solo
    # seeds put a plain consumable in the slot.
    if found is None:
        return ShopSlot()
    return ShopSlot(shop=found[0], item=found[1])


if __name__ == "__main__":
    import sys
    for path in sys.argv[1:]:
        with open(path, "rb") as handle:
            slot = read(handle.read())
        name = path.rsplit("/", 1)[-1]
        print(f"{name:38s} {slot if slot else 'unreadable'}")
