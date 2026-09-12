#!/usr/bin/env python3
"""The class screens reader, `tools/blursings.py`.

Two halves. The text decoder is checked against bytes encoded by hand from
`FF1Text.cs`'s table -- not by an encoder written here from the same table,
which would agree with the decoder about any typo they shared. Then every
cartridge this machine names is read, and what the screens say is held to what
the flag string says: the bonus count per class against RandomizeClassMaxBonus,
the fiend NPCs against ClassAsNpcFiends and the tavern set, and the class id in
each NPC's item byte against the sprite `Party.ClassAsNPC` sets from the same
id. A reader that had the wrong table, the wrong stride or the wrong bank would
still produce something; it would not produce something the flags agree with.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import corpus                                                  # noqa: E402
import blursings as b                                          # noqa: E402

fails = []


def ok(cond, label, got=""):
    print(f"{'ok  ' if cond else 'FAIL'} {label:62} {got}")
    if not cond:
        fails.append(label)


# --- the decoder, with no cartridge -----------------------------------------

# "+20 MDef": '+' $7B, digits $80+n, ' ' $FF, capitals $8A+n, lower $A4+n.
ok(b.decode_text(bytes.fromhex("7B 82 80 FF 96 8D A8 A9 00"), 0) == "+20 MDef",
   "single glyphs decode")
# "Hurt Undead" the way TextToBytes greedily pairs it: H, ur, t_, U, nd, ea, d.
ok(b.decode_text(bytes.fromhex("91 55 21 9E 3B 2B A7 00"), 0) == "Hurt Undead",
   "digraphs decode")
# A newline, an extra icon ($10 + code) and a base-game icon byte.
ok(b.decode_text(bytes.fromhex("8A 05 10 A7 FF DD 00"), 0) == "A\n[all magic] [gauntlets]",
   "newline, extra icon and base icon decode")
ok(b.decode_text(bytes.fromhex("00"), 0) == "", "an empty screen is empty")
ok(b.decode_text(bytes.fromhex("FF FF 8A 00"), 2) == "A", "decoding starts at the offset")

for raw, why in (("02 00", "a byte with no glyph"),
                 ("10 01 00", "an icon code that is not one"),
                 ("8A 8A 8A", "a screen with no terminator")):
    try:
        b.decode_text(bytes.fromhex(raw), 0, limit=8)
        ok(False, f"{why} is refused")
    except ValueError:
        ok(True, f"{why} is refused")

ok(b.class_name(0xFF) == "None" and b.class_name(11) == "Black Wizard",
   "class ids name the way Party.ClassNames does")
ok(b.bank_off(0x1E, 0x8950) == 0x78960 and b.bank_off(0x11, 0xBA00) == 0x47A10,
   "bank arithmetic lands where the README's flag offset does")

# The markdown, on a hand-built reading: the MALUS split and the paragraph
# joins are formatting the cartridge half would never notice going wrong.
fake = b.Screens(
    {"Version": "4-9-7", "Seed": "00000000"},
    {"RandomizeClassMode": b.MODE_BLURSINGS, "ClassAsNpcForcedFiends": True},
    "BONUS",
    ["Learn SLEEP\n +MDef\n\n+40 HP\n\n\nMALUS\n\n-150 GP"] * 12,
    ["Fighter", "None", "Thief", "Black Mage"], [True, True, False, False],
    [("Earth Cave B5", "Thief")])
text = b.markdown(fake, "x.nes")
ok("- Learn SLEEP +MDef\n- +40 HP\n\n**MALUS**\n\n- -150 GP" in text,
   "bonuses and maluses come out as separate bullet lists")
ok("2. None (forced)" in text and "3. Thief (the slot's default)" in text,
   "the party says which slots were forced")
ok("Forced Recruits is on" in text and "Earth Cave B5: **Thief**" in text,
   "the fiend NPCs and the gate are reported")
ok(text.count("## ") == 8, "six class headings, one each for party and NPCs",
   str(text.count("## ")))

# --- every cartridge on the machine -----------------------------------------

carts = corpus.cartridges()
if not carts:
    print("SKIP  no cartridges found: set FF1_ROM or FF1_CORPUS")
else:
    read = refused = 0
    bad = []
    for path in carts:
        name = os.path.basename(os.path.dirname(path)) + "/" + os.path.basename(path)
        with open(path, "rb") as f:
            data = f.read()
        try:
            s = b.read(data)
        except ValueError as e:
            # Not a failure: a cartridge whose flags say the classes were not
            # randomized is one this has to refuse. A refusal for any other
            # reason on an FFR cartridge is.
            refused += 1
            if "RandomizeClassMode is None" not in str(e) and "no FFRInfo" not in str(e):
                bad.append(f"{name}: {e}")
            continue
        read += 1
        flags = s.flags
        if len(s.screens) != 12:
            bad.append(f"{name}: {len(s.screens)} screens")
        if s.mode == b.MODE_BLURSINGS:
            if not s.shared_promo:
                bad.append(f"{name}: promoted screens differ from base")
            if s.template != "BONUS":
                bad.append(f"{name}: template is {s.template!r}")
            for i in range(6):
                bonus, sep, malus = s.screens[i].partition("\n\n\nMALUS\n\n")
                nb = len([p for p in bonus.split("\n\n") if p.strip()])
                nm = len([p for p in malus.split("\n\n") if p.strip()])
                if not sep:
                    bad.append(f"{name}: {b.CLASSES[i]} has no MALUS section")
                if nb > flags["RandomizeClassMaxBonus"]:
                    bad.append(f"{name}: {b.CLASSES[i]} lists {nb} bonuses, "
                               f"max is {flags['RandomizeClassMaxBonus']}")
                if nm > flags["RandomizeClassMaxMalus"]:
                    bad.append(f"{name}: {b.CLASSES[i]} lists {nm} maluses, "
                               f"max is {flags['RandomizeClassMaxMalus']}")
        if (s.npcs is not None) != bool(flags["ClassAsNpcFiends"]):
            bad.append(f"{name}: fiend NPCs reported {s.npcs is not None}, "
                       f"flag says {flags['ClassAsNpcFiends']}")
        if s.npcs is not None:
            # Party.ClassAsNPC draws from the TAVERN-enabled base classes (all
            # six when none is), promoted under ClassAsNpcPromotion, and does
            # not repeat one unless ClassAsNpcDuplicate -- and sets the sprite
            # from the same id it writes into the item byte.
            taverns = [i for i in range(6) if flags["TAVERN%d" % (i + 1)]] or list(range(6))
            if flags["ClassAsNpcPromotion"]:
                taverns = [i + 6 for i in taverns]
            pool = {b.CLASSES[i] for i in taverns}
            names = [c for _, c in s.npcs]
            if not set(names) <= pool:
                bad.append(f"{name}: NPC classes {names} outside the tavern set {sorted(pool)}")
            if len(set(names)) != len(names) and not flags["ClassAsNpcDuplicate"]:
                bad.append(f"{name}: NPC classes repeat: {names}")
            for (_floor, cname), (_f, oid) in zip(s.npcs, b.FIEND_NPCS):
                sprite = data[0x02E00 + b.HEADER + oid]
                want = 0xEE + b.CLASSES.index(cname)
                if sprite != want:
                    bad.append(f"{name}: object {oid} wears sprite ${sprite:02X}, "
                               f"not ${want:02X} for a {cname}")
        for i, (c, forced) in enumerate(zip(s.party, s.forced), 1):
            if c == "None" and i == 1:
                bad.append(f"{name}: slot 1 opens on None")
    for line in bad:
        print("      " + line)
    ok(not bad, f"{read} cartridge(s) read and agree with their flags; "
                f"{refused} refused", f"{len(bad)} disagreement(s)" if bad else "")

print("test_blursings: " + ("FAILED " + "; ".join(fails) if fails else "ok"))
sys.exit(1 if fails else 0)
