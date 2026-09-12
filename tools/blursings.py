#!/usr/bin/env python3
"""The class info screens off an FFR cartridge: blursings, the rolled party, and
which class waits behind each fiend.

    tools/blursings.py seed.nes              # markdown on stdout
    tools/blursings.py --write seed.nes ...  # blursings.md beside each cartridge

Why a cartridge has to be read for this: nothing else carries it. The flag
string says the classes were blursed and how many bonuses each got, not which;
FFR's spoiler log says nothing about class NPCs at all; and in the game the
screens are behind Select on the party-generation and status menus, so a
forced party (FORCED1-4) is committed to before anyone has read them.

Where it lives, from FF1Randomizer 4.9.7 (`FF1Lib/Classes/ClassesData.cs`,
`CreateDataScreens`, the same lines at 4.9.2):

    bank $1E:$8950   thirteen little-endian pointers -- six base classes, the
                     six promoted ones again, then None
    bank $1E:$8970   the template screen ("BONUS" under Blursings, empty under
                     the Transmooglifier), then the thirteen screens it points at

The text is FF1's own encoding (`FF1Text.TextToBytes`, DTE on, the extra icon
set on): one byte per glyph or digraph, $05 a newline, $00 the end, and an
extra icon as $10 followed by its code. Under Blursings the six promoted screens
are the base six repeated, and the reader checks that rather than assuming it.

The other two things the file reports come from elsewhere:

    0x784AA         lut_PtyGenBuf, one 0x10 stride per slot; the first byte is
                    the class the slot opens on, which under FORCEDn is the
                    class it is stuck with (`Party.UpdateCharacterFromOptions`)
    bank $11:$BA00  the moved NPC talk data, six bytes per object, item at +3
                    (`NpcObjectData.Write`); on the four objects `ClassAsNPC`
                    repurposes, the item byte is a class id

The four objects are fixed by dungeon, not by fiend: `Party.ClassAsNPC` puts
MelmondMan6 on Earth Cave B5, GaiaMan4 on Gurgu Volcano B5, OnracPunk1 on Sea
Shrine B5 and GaiaMan1 on Sky Palace 5F, whichever fiend FiendShuffle has
standing there. Under `ClassAsNpcForcedFiends` each stands on the one tile the
orb altar can be stepped on from (on the altar itself, in the Volcano), and the
talk routine hides it only when a swap is accepted -- so B cancels the menu
but not the gate. That was measured on the 2026-09-10 async's cartridges by
walking the four floors; see `docs/ARCHITECTURE.md`, "The tools".

Refuses rather than guesses when the flags say the classes were not
randomized: with `RandomizeClassMode` None nothing wrote the pointer table,
and decoding whatever bank $1E happens to hold there produces confident text.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "ffr_flags"))
import ffr_flags  # noqa: E402

HEADER = 0x10

SCREEN_PTRS = (0x1E, 0x8950)
SCREEN_TEMPLATE = (0x1E, 0x8970)
SCREEN_COUNT = 13               # six base, six promoted, None
PTYGEN_BUF = 0x784AA
PTYGEN_STRIDE = 0x10
TALK_DATA = (0x11, 0xBA00)
TALK_STRIDE = 6
TALK_ITEM = 3

# FF1Class, in FF1Lib's order; `Party.ClassNames` spells them this way.
CLASSES = ["Fighter", "Thief", "Black Belt", "Red Mage", "White Mage", "Black Mage",
           "Knight", "Ninja", "Master", "Red Wizard", "White Wizard", "Black Wizard"]
NONE_CLASS = 0xFF

# `Party.ClassAsNPC`'s dungeonNpc list, in its order, with the floor each is put on.
FIEND_NPCS = [("Earth Cave B5", 111), ("Gurgu Volcano B5", 183),
              ("Sea Shrine B5", 152), ("Sky Palace 5F", 174)]

# ClassRandomizationMode
MODE_NONE, MODE_BLURSINGS, MODE_TRANSMOOGLIFIER, MODE_CHAOS = range(4)
MODE_NAMES = {MODE_BLURSINGS: "Blursings", MODE_TRANSMOOGLIFIER: "Transmooglifier",
              MODE_CHAOS: "Chaos"}


def bank_off(bank, addr):
    return bank * 0x4000 + (addr - 0x8000) + HEADER


# ------------------------------------------------------------------ the text

# FF1Text.BytesByText, inverted. Digraphs first, then the single glyphs; the
# base-game icon bytes are given names in brackets since there is no glyph to
# print for them.
GLYPHS = {
    0x03: "#", 0x05: "\n",
    0x1A: "e ", 0x1B: " t", 0x1C: "th", 0x1D: "he", 0x1E: "s ", 0x1F: "in",
    0x20: " a", 0x21: "t ", 0x22: "an", 0x23: "re", 0x24: " s", 0x25: "er",
    0x26: "ou", 0x27: "d ", 0x28: "to", 0x29: "n ", 0x2A: "ng", 0x2B: "ea",
    0x2C: "es", 0x2D: " i", 0x2E: "o ", 0x2F: "ar", 0x30: "is", 0x31: " b",
    0x32: "ve", 0x33: " w", 0x34: "me", 0x35: "or", 0x36: " o", 0x37: "st",
    0x38: " c", 0x39: "at", 0x3A: "en", 0x3B: "nd", 0x3C: "on", 0x3D: "hi",
    0x3E: "se", 0x3F: "as", 0x40: "ed", 0x41: "ha", 0x42: " m", 0x43: " f",
    0x44: "r ", 0x45: "le", 0x46: "ow", 0x47: "g ", 0x48: "ce", 0x49: "om",
    0x4A: "GI", 0x4B: "y ", 0x4C: "of", 0x4D: "ro", 0x4E: "ll", 0x4F: " p",
    0x50: " y", 0x51: "ca", 0x52: "MA", 0x53: "te", 0x54: "f ", 0x55: "ur",
    0x56: "yo", 0x57: "ti", 0x58: "l ", 0x59: " h", 0x5A: "ne", 0x5B: "it",
    0x5C: "ri", 0x5D: "wa", 0x5E: "ac", 0x5F: "al", 0x60: "we", 0x61: "il",
    0x62: "be", 0x63: "rs", 0x64: "u ", 0x65: " l", 0x66: "ge", 0x67: " d",
    0x68: "li", 0x69: "..",
    0x7A: "/", 0x7B: "+",
    0xBE: "'", 0xBF: ",", 0xC0: ".", 0xC1: ";", 0xC2: "-", 0xC3: "..",
    0xC4: "!", 0xC5: "?", 0xE0: "%", 0xFF: " ",
    0xCE: "[unarmed]", 0xCF: "[rod]", 0xD0: "[scimitar]", 0xD1: "[falchion]",
    0xD2: "[rapier]", 0xD3: "[shortsword]", 0xD4: "[swords]", 0xD5: "[hammers]",
    0xD6: "[knives]", 0xD7: "[axes]", 0xD8: "[staves]", 0xD9: "[nunchucks]",
    0xDA: "[armor]", 0xDB: "[shields]", 0xDC: "[helmets]", 0xDD: "[gauntlets]",
    0xDE: "[bracelets]", 0xDF: "[shirts]", 0xE1: "[potion]",
    0xE2: "[status]", 0xE3: "[poison]", 0xE4: "[time]", 0xE5: "[death]",
    0xE6: "[fire]", 0xE7: "[ice]", 0xE8: "[lightning]", 0xE9: "[earth]",
    0xEA: "[dead]", 0xEB: "[stone]", 0xEC: "[poison]", 0xED: "[blind]",
    0xEE: "[stun]", 0xEF: "[sleep]", 0xF0: "[mute]", 0xF1: "[confuse]",
}
for _i in range(10):
    GLYPHS[0x80 + _i] = str(_i)
for _i in range(26):
    GLYPHS[0x8A + _i] = chr(ord("A") + _i)
    GLYPHS[0xA4 + _i] = chr(ord("a") + _i)

# FF1Text.Icons: what follows a $10.
ICON_PREFIX = 0x10
ICONS = {
    0xA1: "unarmed", 0xA2: "rod", 0xA3: "scimitar", 0xA4: "falchion", 0xA5: "rapier",
    0xA6: "shortsword", 0xA7: "all magic", 0xA8: "white magic", 0xA9: "grey magic",
    0xAA: "black magic", 0xAB: "recovery magic", 0xAC: "health magic",
    0xAD: "ailment magic", 0xAE: "life magic", 0xAF: "holy magic", 0xB0: "space magic",
    0xB1: "tele magic", 0xB2: "buff magic", 0xB3: "self magic",
    0xB4: "status", 0xB5: "poison", 0xB6: "time", 0xB7: "death", 0xB8: "fire",
    0xB9: "ice", 0xBA: "lightning", 0xBB: "earth",
    0xBC: "dead", 0xBD: "stone", 0xBE: "poison", 0xBF: "blind", 0xC0: "stun",
    0xC1: "sleep", 0xC2: "mute", 0xC3: "confuse",
}


def decode_text(data, off, limit=0x400):
    """The string at `off`, up to its $00. Raises on a byte with no glyph.

    An unknown byte is not rendered as a placeholder: the one time this reads
    the wrong place, every byte is plausible and the placeholder would be the
    only sign. `limit` bounds the read so a missing terminator is an error too.
    """
    out = []
    start = off
    end = min(off + limit, len(data))
    while off < end:
        b = data[off]
        off += 1
        if b == 0:
            return "".join(out)
        if b == ICON_PREFIX:
            code = data[off] if off < end else None
            off += 1
            if code not in ICONS:
                raise ValueError("$10 %s is not an icon"
                                 % ("%02X" % code if code is not None else "<end>"))
            out.append("[%s]" % ICONS[code])
            continue
        if b not in GLYPHS:
            raise ValueError("$%02X is not a glyph at %#x" % (b, off - 1))
        out.append(GLYPHS[b])
    raise ValueError("no terminator within %d bytes of %#x" % (limit, start))


def class_name(b):
    if b == NONE_CLASS:
        return "None"
    if b < len(CLASSES):
        return CLASSES[b]
    raise ValueError("$%02X is not a class id" % b)


# --------------------------------------------------------------- the reading

class Screens:
    """Everything the class screens and the two tables beside them say."""

    def __init__(self, info, flags, template, screens, party, forced, npcs):
        self.info = info
        self.flags = flags
        self.template = template
        self.screens = screens          # twelve, base then promoted
        self.party = party              # four class names
        self.forced = forced            # four bools, FORCEDn
        self.npcs = npcs                # [(floor, class name)] or None

    @property
    def mode(self):
        return self.flags["RandomizeClassMode"]

    @property
    def shared_promo(self):
        return self.screens[:6] == self.screens[6:]


def read(data):
    """A `Screens` for an FFR cartridge, or raise ValueError saying why not."""
    try:
        info, flags = ffr_flags.decode_rom(data)
    except ffr_flags.DecodeError as e:
        raise ValueError(str(e))
    mode = flags["RandomizeClassMode"]
    if mode == MODE_NONE:
        raise ValueError("RandomizeClassMode is None on this cartridge: the class"
                         " screens were never written, so there is nothing to read")

    ptrs = []
    base = bank_off(*SCREEN_PTRS)
    for i in range(SCREEN_COUNT):
        ptrs.append(data[base + 2 * i] | data[base + 2 * i + 1] << 8)
    template = decode_text(data, bank_off(*SCREEN_TEMPLATE))
    screens = [decode_text(data, bank_off(SCREEN_PTRS[0], p)) for p in ptrs[:12]]
    none_screen = decode_text(data, bank_off(SCREEN_PTRS[0], ptrs[12]))
    if none_screen != "":
        raise ValueError("the None slot's screen is %r, not empty" % none_screen)

    party = [class_name(data[PTYGEN_BUF + HEADER + i * PTYGEN_STRIDE]) for i in range(4)]
    forced = [bool(flags["FORCED%d" % i]) for i in range(1, 5)]

    npcs = None
    if flags["ClassAsNpcFiends"]:
        talk = bank_off(*TALK_DATA)
        npcs = [(floor, class_name(data[talk + oid * TALK_STRIDE + TALK_ITEM]))
                for floor, oid in FIEND_NPCS]
    return Screens(info, flags, template, screens, party, forced, npcs)


# --------------------------------------------------------------- the writing

def _items(block):
    """One markdown bullet per paragraph, the in-screen wraps joined."""
    items = [" ".join(p.split()) for p in block.split("\n\n") if p.strip()]
    return ["- " + i for i in items] or ["- (none)"]


def markdown(s, romname):
    mode = MODE_NAMES.get(s.mode, "mode %d" % s.mode)
    lines = ["# Class screens -- %s" % romname, "",
             "FFR %s, seed %s, RandomizeClassMode %s. Read from the cartridge's class"
             % (s.info.get("Version", "?"), s.info.get("Seed", "?"), mode),
             "info screens, the ones Select shows on the party and status menus."]
    if s.shared_promo:
        lines.append("Base and promoted classes share a screen.")
    lines += ["", "## Starting party", ""]
    for i, (c, f) in enumerate(zip(s.party, s.forced), 1):
        lines.append("%d. %s%s" % (i, c, " (forced)" if f else " (the slot's default)"))
    if s.npcs is not None:
        lines += ["", "## Class NPCs behind the fiends", ""]
        if s.flags["ClassAsNpcForcedFiends"]:
            lines.append("Forced Recruits is on: each stands where the orb altar is"
                         " stepped on from and moves only when a swap is accepted,"
                         " so an orb cannot be lit without taking its class.")
        else:
            lines.append("Each stands beside the orb altar; B at the lineup menu"
                         " declines and leaves the altar reachable.")
        lines += ["Taking one replaces the party member you pick: level kept,"
                  " spells and MP wiped, gear unequipped but still carried.", ""]
        for floor, c in s.npcs:
            lines.append("- %s: **%s**" % (floor, c))
    if s.mode == MODE_BLURSINGS:
        malus_split = "\n\n\nMALUS\n\n"
        for i in range(6):
            lines += ["", "## %s / %s" % (CLASSES[i], CLASSES[i + 6]), ""]
            bonus, _, malus = s.screens[i].partition(malus_split)
            lines += ["**%s**" % (s.template or "BONUS"), ""] + _items(bonus)
            lines += ["", "**MALUS**", ""] + _items(malus)
    else:
        for i in range(6 if s.shared_promo else 12):
            title = "%s / %s" % (CLASSES[i], CLASSES[i + 6]) if s.shared_promo else CLASSES[i]
            lines += ["", "## %s" % title, ""] + _items(s.screens[i])
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom", nargs="+")
    ap.add_argument("--write", action="store_true",
                    help="write blursings.md beside each cartridge instead of printing")
    args = ap.parse_args(argv)

    status = 0
    for path in args.rom:
        with open(path, "rb") as f:
            data = f.read()
        if data[:4] != b"NES\x1a":
            print("%s: not an iNES ROM" % path, file=sys.stderr)
            status = 1
            continue
        try:
            s = read(data)
        except ValueError as e:
            print("%s: %s" % (path, e), file=sys.stderr)
            status = 1
            continue
        text = markdown(s, os.path.basename(path))
        if args.write:
            out = os.path.join(os.path.dirname(os.path.abspath(path)), "blursings.md")
            with open(out, "w") as f:
                f.write(text)
            print("wrote", out)
        else:
            sys.stdout.write(text)
    return status


if __name__ == "__main__":
    sys.exit(main())
