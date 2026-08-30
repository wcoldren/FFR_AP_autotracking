"""The letters have to come off the cartridge, not out of a hand-drawn font.

Set FF1_ROM to a cartridge; without one this skips rather than passing quietly.

The failure this guards against is the one the sprite hunt already made once:
an offset slid until the picture looks plausible. A font base is especially
easy to get wrong that way, because almost any CHR region decodes into
*something*, and 8x8 noise at a glance reads as a bad font rather than as the
wrong address. So the negative cases matter more than the positive ones -- the
neighbouring bases have to be rejected, not merely be worse.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import font                                                    # noqa: E402
import render_maps                                             # noqa: E402

fails = []


def check(label, got, want):
    ok = got == want
    print(("ok   " if ok else "FAIL ") + label, "" if ok else f"{got!r} != {want!r}")
    if not ok:
        fails.append(label)


def main():
    path = os.environ.get("FF1_ROM")
    if not path or not os.path.exists(path):
        print("SKIP  set FF1_ROM to a Final Fantasy cartridge to run this")
        return 0
    with open(path, "rb") as f:
        rom = f.read()

    check("the menu CHR reads as the game's font", font.self_check(rom), [])

    # The ordering is the whole lookup, so spot-check both ends and the seam
    # between the cases against FF1Text.cs's own byte for each character.
    check("the encoding agrees on 0, A, a and z",
          [font.TEXT_BASE + font.CHARS.index(c) for c in "0Aaz"],
          [0x80, 0x8A, 0xA4, 0xBD])

    # 0 and O really are one glyph in this font. Asserting it keeps a future
    # "the glyphs must all be distinct" tightening from being written.
    g0, gO = font.glyph(rom, "0"), font.glyph(rom, "O")
    check("0 and O are the same glyph", g0, gO)
    check("G and I are not", font.glyph(rom, "G") == font.glyph(rom, "I"), False)

    # A glyph is ink on some pixels and not others, and nothing outside CHARS
    # draws at all.
    check("A has ink", any(any(r) for r in font.glyph(rom, "A")), True)
    check("A has gaps", any(not v for r in font.glyph(rom, "A") for v in r), True)
    check("a space draws nothing", font.glyph(rom, " "), None)

    # The negative case: a base off by one tile, or by one row of sixteen,
    # must not still read as the alphabet. This is what makes the address a
    # derivation rather than a base that happened to look right.
    real = font.MENU_CHR_OFF
    for step in (-font.TILE_BYTES, font.TILE_BYTES,
                 -font.ROW_TILES * font.TILE_BYTES,
                 font.ROW_TILES * font.TILE_BYTES):
        font.MENU_CHR_OFF = real + step
        moved = font.self_check(rom)
        font.MENU_CHR_OFF = real
        check(f"a base {step:+d} bytes out is rejected", bool(moved), True)

    # And drawing actually puts pixels down, clipped to the buffer.
    w = h = 32
    out = bytearray(w * h * 3)
    font.draw_text(out, w, h, 0, 0, "A", (255, 255, 255), 2, rom)
    check("draw_text writes ink", any(out), True)
    edge = bytearray(w * h * 3)
    font.draw_text(edge, w, h, w - 2, h - 2, "A", (255, 255, 255), 2, rom)
    check("and clips at the edge without raising", True, True)

    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
