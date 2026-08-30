#!/usr/bin/env python3
"""The cartridge's own font, for annotating a rendered map.

Nothing here is drawn by hand. `LoadMenuCHR` (`bank_0F.asm:9856-9863`) swaps in
`BANK_MENUCHR` -- `$09`, `Constants.inc:84` -- points at `$8800` and loads
`LDX #8` rows to PPU `$0800`. `CHRLoad`'s header says a row is 16 tiles or 256
bytes (`bank_0F.asm:9797`), so the menu CHR is the $800 bytes at `$09:8800`:
128 tiles, of which the first 62 are `0-9`, `A-Z`, `a-z` in that order.

That ordering is the whole lookup -- a digit is its own value, `A` is 10, `a` is
36 -- and it is what makes this a derivation rather than a hand-drawn font
substituted for one the cartridge already has. See "derive before substituting".

What pins the base is arithmetic across two sources that know nothing about
each other, the same guard sprites.py puts on `lut_MapObjCHR`. `LoadMenuCHR`
writes this art to PPU `$0800`, so its first tile is background tile `$80`; and
FFR's own encoding table independently says the byte that prints `0` is `$80`,
`A` is `$8A`, `a` is `$A4` (`FF1Lib/FF1Text.cs:174,184,210`). Those are the same
numbers as `TEXT_BASE + CHARS.index(ch)`, and they are asserted below. A base
off by a tile would need both to be wrong in step.

The glyphs are two-colour: every pixel decodes to 2 (the cell) or 3 (the ink).
Do not expect them all to be distinct -- `0` and `O` are the same glyph in this
font, which is a property of the font and is asserted as such.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import entrance_graph as eg                                     # noqa: E402
from render_maps import decode_ppu                              # noqa: E402

MENU_CHR_BANK = 0x09          # BANK_MENUCHR, Constants.inc:84
MENU_CHR = 0x8800             # LoadMenuCHR's source pointer
MENU_ROWS = 8                 # LDX #8, and a row is 16 tiles
ROW_TILES = 16
TILE_BYTES = 16
GLYPH_PX = 8
INK = 3                       # the font's foreground value; the cell is 2

CHARS = ("0123456789"
         "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
         "abcdefghijklmnopqrstuvwxyz")

TEXT_BASE = 0x80              # PPU $0800 / 16 -- the tile LoadMenuCHR starts at
MENU_CHR_OFF = eg.bank_off(MENU_CHR_BANK, MENU_CHR)

# The 62 glyphs have to fit inside what LoadMenuCHR actually loads, and the
# order they are in has to be the order the game's own text encoding assumes.
# FF1Text.cs is not derived from the disassembly and the disassembly is not
# derived from it, so these agreeing is the pin.
assert len(CHARS) <= MENU_ROWS * ROW_TILES
assert TEXT_BASE + CHARS.index("0") == 0x80     # FF1Text.cs:174
assert TEXT_BASE + CHARS.index("9") == 0x89     # FF1Text.cs:183
assert TEXT_BASE + CHARS.index("A") == 0x8A     # FF1Text.cs:184
assert TEXT_BASE + CHARS.index("O") == 0x98     # FF1Text.cs:198
assert TEXT_BASE + CHARS.index("Z") == 0xA3     # FF1Text.cs:209
assert TEXT_BASE + CHARS.index("a") == 0xA4     # FF1Text.cs:210
assert TEXT_BASE + CHARS.index("z") == 0xBD     # FF1Text.cs:235


def base(rom=None):
    """File offset of the menu CHR. The bank is fixed, so `rom` is unused."""
    return MENU_CHR_OFF


def glyph(rom, ch):
    """8x8 of booleans -- True where the character has ink -- or None.

    None for anything outside `CHARS`, space included, so a caller advances
    the pen without drawing.
    """
    i = CHARS.find(ch)
    if i < 0:
        return None
    off = base(rom) + i * TILE_BYTES
    px = decode_ppu(rom[off:off + TILE_BYTES])
    return [[px[r * GLYPH_PX + c] == INK for c in range(GLYPH_PX)]
            for r in range(GLYPH_PX)]


def text_px(text, scale=1):
    """Width in pixels of `text` drawn at `scale`."""
    return len(text) * GLYPH_PX * scale


def draw_text(out, w, h, x, y, text, rgb, scale=1, rom=None, shadow=None):
    """Blit `text` onto an RGB buffer, clipped, transparent off the ink.

    `shadow`, if given, is drawn one scaled pixel down and right first, which
    is what keeps a letter readable on top of map art rather than only on the
    flat backdrop of the Map Key band.
    """
    for pen, ch in enumerate(text):
        g = glyph(rom, ch)
        if g is None:
            continue
        gx = x + pen * GLYPH_PX * scale
        for colour, dx, dy in ((shadow, scale, scale), (rgb, 0, 0)):
            if colour is None:
                continue
            for r, row in enumerate(g):
                for c, ink in enumerate(row):
                    if not ink:
                        continue
                    for sy in range(scale):
                        py = y + dy + r * scale + sy
                        if not 0 <= py < h:
                            continue
                        for sx in range(scale):
                            px = gx + dx + c * scale + sx
                            if not 0 <= px < w:
                                continue
                            d = (py * w + px) * 3
                            out[d], out[d + 1], out[d + 2] = colour


def self_check(rom):
    """-> [problem]. Empty when the font base reads as a font.

    Two properties, and the second is the one with teeth. Every one of the 62
    glyphs must be two-colour and non-blank; and the only two that may be
    identical are `0` and `O`, which this font really does draw the same. A
    base landing on menu borders, shop art or map tiles fails the first; a base
    off by whole rows fails the second, because the punctuation and the item
    icons past `z` repeat shapes that the alphabet does not.
    """
    bad = []
    seen = {}
    off = base(rom)
    for i, ch in enumerate(CHARS):
        px = decode_ppu(rom[off + i * TILE_BYTES:off + (i + 1) * TILE_BYTES])
        stray = set(px) - {2, 3}
        if stray:
            bad.append(f"glyph {ch!r} is not two-colour (values "
                       f"{sorted(set(px))})")
            continue
        if INK not in px:
            bad.append(f"glyph {ch!r} is blank")
            continue
        key = tuple(px)
        if key in seen and {ch, seen[key]} != {"0", "O"}:
            bad.append(f"glyph {ch!r} is identical to {seen[key]!r}")
        seen[key] = ch
    if len(seen) != len(CHARS) - 1:
        bad.append(f"expected exactly one repeated glyph (0 and O), got "
                   f"{len(CHARS) - len(seen)}")
    return bad


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("rom")
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--text", help="draw this and write it to --out")
    ap.add_argument("--out", default="text.png")
    ap.add_argument("--scale", type=int, default=2)
    args = ap.parse_args(argv)

    with open(args.rom, "rb") as f:
        rom = f.read()

    if args.self_check:
        bad = self_check(rom)
        for b in bad:
            print("  " + b)
        print(f"self-check: {len(bad)} problems; {len(CHARS)} glyphs at "
              f"${MENU_CHR_BANK:02X}:{MENU_CHR:04X} (file ${base(rom):06X})")
        return 1 if bad else 0

    if args.text:
        import pngio
        w = text_px(args.text, args.scale)
        h = GLYPH_PX * args.scale
        out = bytearray(w * h * 3)
        draw_text(out, w, h, 0, 0, args.text, (255, 255, 255), args.scale, rom)
        pngio.write_rgb(args.out, w, h, out)
        print(f"wrote {args.out}  {w}x{h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
