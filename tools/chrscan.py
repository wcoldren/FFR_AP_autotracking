#!/usr/bin/env python3
"""Decode a ROM range as NES pattern tiles and tile them into one sheet.

FFR names an offset for every table it randomizes, so anything it leaves alone
-- the map object sprite art, for one -- has no constant to read and has to be
found. Graphics and code look completely different once decoded as 2bpp tiles:
code is static, art is ordered. So sweep the ROM at low resolution, find the
ordered bands by eye, then zoom.

    tools/chrscan.py ROM 0x10 0x80010 sweep.png --per-row 256 --scale 1
    tools/chrscan.py ROM 0xA210 0xC010 npcs.png --per-row 4 --scale 3 --group 4

The second is the map object art, which this found and sprites.py then pinned
off the engine's own constants -- see "Sprites on the map" in STATUS.md. Worth
knowing the difference: a band located this way is a band, not an origin. The
neighbouring band at 0x9010 is the twelve class mapmen and looks just as much
like the answer.

--group 4 draws every four consecutive tiles as one 16x16 cell instead, which
is the shape a map object sprite is actually in (row-major: top-left,
top-right, bottom-left, bottom-right).

Greyscale by default because the real palette is a separate question; the point
is to find the art, not to colour it.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pngio                                                    # noqa: E402
from render_maps import decode_ppu                              # noqa: E402

SHADES = [(20, 20, 26), (95, 95, 100), (175, 175, 180), (250, 250, 250)]


def sheet(rom, start, end, per_row=64, scale=3, group=1):
    """(w, h, rgb) for the range, `group` tiles to a cell."""
    span = 4 if group == 4 else 1           # cells are 2x2 tiles when grouped
    cw = ch = 8 * span * scale
    cells = (end - start) // (16 * group)
    rows = (cells + per_row - 1) // per_row
    w, h = per_row * cw, rows * ch
    buf = bytearray(w * h * 3)
    for i in range(w * h):
        buf[i * 3:i * 3 + 3] = bytes(SHADES[0])
    for c in range(cells):
        for k in range(group):
            off = start + c * 16 * group + k * 16
            ox, oy = ((k & 1) * 8, (k >> 1) * 8) if group == 4 else (0, 0)
            for i, v in enumerate(decode_ppu(rom[off:off + 16])):
                r, g, b = SHADES[v]
                x = (c % per_row) * cw + (ox + (i & 7)) * scale
                y = (c // per_row) * ch + (oy + (i >> 3)) * scale
                for sy in range(scale):
                    row = (y + sy) * w
                    for sx in range(scale):
                        d = (row + x + sx) * 3
                        buf[d], buf[d + 1], buf[d + 2] = r, g, b
    return w, h, bytes(buf)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("out")
    ap.add_argument("--per-row", type=int, default=64)
    ap.add_argument("--scale", type=int, default=3)
    ap.add_argument("--group", type=int, default=1, choices=(1, 4),
                    help="4 draws each four tiles as one 16x16 sprite cell")
    args = ap.parse_args()

    with open(args.rom, "rb") as f:
        rom = f.read()
    start, end = int(args.start, 0), int(args.end, 0)
    if not 0 <= start < end <= len(rom):
        sys.exit(f"range 0x{start:X}-0x{end:X} is not inside a {len(rom)}-byte file")
    w, h, rgb = sheet(rom, start, end, args.per_row, args.scale, args.group)
    pngio.write_rgb(args.out, w, h, rgb)
    per_row_bytes = args.per_row * 16 * args.group
    print(f"wrote {args.out}  {w}x{h}  from 0x{start:X}, each row 0x{per_row_bytes:X} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
