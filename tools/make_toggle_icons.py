#!/usr/bin/env python3
"""Draw the four pin-toggle icons, and the one warning light that shares their
style.

These are display controls, not seed flags, and they have to look like it. The
flags grid is full of cartridge sprites -- a king, a chest, a dock -- so an icon
built from one reads as "this seed did something", which is the opposite of what
a toggle says. The pack already has a house style for the other kind:
`autoTab.png` and `tabAuto.png` are 32x32 schematics on a near-black ground with
a thin border and a flat glyph, and nothing about them looks like it came off a
cartridge. These follow it, and the palette is sampled from `autoTab.png` rather
than guessed.

Nothing here reads a ROM, and the reason is the paragraph above rather than a
rule against it: `README.md` keeps whole maps out of the repo but allows single
sprites lifted for a tracker cell, which is how the door icons ship. A toggle is
the one kind of icon that must not look lifted, so these are drawn from
constants, and the script is committed so a reader can see that rather than take
it on trust.

The shapes are the pack's own vocabulary, not decoration:

    chest pins      square outlines -- what PopTracker draws for a marker
    NPC pins        diamonds -- the shape the NPC pins already use
    skipped pins    a square in PopTracker's own "checkable" blue
    incentive rings a square inside a gold ring

The two colours are read out of PopTracker rather than eyeballed off a
screenshot: `src/ui/mapwidget.cpp:32` is `checkable -> blue` and `:58` is
`Highlight::PRIORITY` gold, so an icon shows the colour the player's board
actually paints.

Only the "on" images are drawn. PopTracker greys a toggle's image itself when
it is off, which is what most of the pack's toggles rely on. Read the filter off
this pack rather than off the default: `settings.json` sets
`disabled_image_filter` to `grayscale, dim`, so the off state is an average
greyscale at full value followed by a flat halving (`imagefilter.cpp:66-81`,
where `dim` is `setBrightness(surf, 0.5)`). PopTracker's own default is `grey`,
which is the same greyscale taken at two thirds -- brighter than what this pack
actually shows, so sizing the shapes against it would flatter them.

What the halving does to the four constants below:

    GROUND    24/24/28   ->  12
    GLYPH     188        ->  94
    CHECKABLE blue       ->  61
    PRIORITY  gold       ->  78

The glyph shapes hold up at 94 on 12. The gold ring does not fare as well: 78
against a 94 glyph on a 12 ground is a ring that has stopped being gold and is
barely separable from the square it encircles, so `showIncentiveRings` is the
one of the four most likely to want a drawn `noXxx.png` rather than the filter.
Adding one is a one-line change to the item.

**The last two icons are not toggles.** `artStale` -- the drawn maps are another
cartridge's -- and `modeMismatch` -- the seed and the loaded variant disagree
about which game this is -- belong to `flagsUnread.png`'s family rather than to
the four above, and they are drawn here because that is where the canvas and the
house style live. Its amber is sampled from `flagsUnread.png`
(222/168/46, with the exclamation cut out in 60/44/10) for the same reason the
rest of the palette is sampled: two warning lights side by side in the same grid
that disagreed about their amber would look like a mistake. The glyph pairs that
triangle with three marker boxes, which is the vocabulary the toggles above
already use for "the pins on the art".

    python3 tools/make_toggle_icons.py            # write images/flags/*.png
    python3 tools/make_toggle_icons.py --check    # exit 1 if any differ
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pngio

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SIZE = 32

# Sampled from images/flags/autoTab.png, which is the icon these are siblings of.
GROUND = (24, 24, 28)
EDGE = (0, 0, 0)
GLYPH = (188, 188, 188)

# The same glyph, dimmed, from images/flags/noAutoTab.png -- which is how this
# family already says "this one is switched off".
DIM = (90, 90, 90)

# PopTracker's own, so the icon matches the board: src/ui/mapwidget.cpp:32 and :58.
CHECKABLE = (0x30, 0x40, 0xFF)
PRIORITY = (0xFF, 0xD7, 0x00)

# The warning family, sampled from images/flags/flagsUnread.png. Its ground is
# 26/26/30 rather than autoTab's 24/24/28, and the warning light drawn below
# uses the ground it is sitting next to.
WARN_GROUND = (26, 26, 30)
AMBER = (222, 168, 46)
AMBER_CUT = (60, 44, 10)


class Canvas:
    def __init__(self, w=SIZE, h=SIZE, fill=GROUND):
        self.w, self.h = w, h
        self.px = [fill] * (w * h)

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y * self.w + x] = c

    def border(self, c=EDGE):
        for i in range(self.w):
            self.set(i, 0, c)
            self.set(i, self.h - 1, c)
        for j in range(self.h):
            self.set(0, j, c)
            self.set(self.w - 1, j, c)

    def square(self, cx, cy, half, c, fill=None):
        """A marker box: outline `c`, optionally filled."""
        for y in range(cy - half, cy + half + 1):
            for x in range(cx - half, cx + half + 1):
                edge = (x in (cx - half, cx + half)
                        or y in (cy - half, cy + half))
                if edge:
                    self.set(x, y, c)
                elif fill is not None:
                    self.set(x, y, fill)

    def diamond(self, cx, cy, half, c, fill=None):
        """The shape the NPC pins use."""
        for y in range(cy - half, cy + half + 1):
            for x in range(cx - half, cx + half + 1):
                d = abs(x - cx) + abs(y - cy)
                if d == half:
                    self.set(x, y, c)
                elif d < half and fill is not None:
                    self.set(x, y, fill)

    def trapezoid(self, cx, cy, half, c, fill=None):
        """The shape an entrance pin is drawn as.

        PopTracker's geometry, not an invented one: `drawTrapezoid` puts the
        top edge at the middle half of the box and the bottom edge at its full
        width (`uilib/drawhelper.cpp:228`), so the outline widens evenly from
        top to bottom. Half a box is two pixels of slant per four rows at this
        size, which is shallow enough that the sides never break.
        """
        top, bottom = cy - half, cy + half
        span = bottom - top
        for y in range(top, bottom + 1):
            w = half // 2 + (half - half // 2) * (y - top) // span
            for x in range(cx - w, cx + w + 1):
                if y in (top, bottom) or x in (cx - w, cx + w):
                    self.set(x, y, c)
                elif fill is not None:
                    self.set(x, y, fill)

    def ring(self, cx, cy, r, c):
        """A one-pixel circle, the glow PopTracker draws around a priority pin."""
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r, cx + r + 1):
                dd = (x - cx) ** 2 + (y - cy) ** 2
                if (r - 0.6) ** 2 <= dd <= (r + 0.6) ** 2:
                    self.set(x, y, c)

    def rgb(self):
        out = bytearray()
        for p in self.px:
            out += bytes(p)
        return bytes(out)


def chest_pins():
    """Three marker boxes: the pin a chest gets, three times over."""
    c = Canvas()
    c.border()
    c.square(10, 10, 4, GLYPH)
    c.square(22, 12, 4, GLYPH)
    c.square(15, 22, 4, GLYPH)
    return c


def npc_pins():
    """Two diamonds, which is what an NPC pin is drawn as."""
    c = Canvas()
    c.border()
    c.diamond(11, 12, 6, GLYPH)
    c.diamond(22, 21, 6, GLYPH)
    return c


def skipped_pins():
    """One box in the blue an Inspect-level pin comes out."""
    c = Canvas()
    c.border()
    c.square(11, 11, 4, GLYPH)
    c.square(20, 20, 5, GLYPH, fill=CHECKABLE)
    return c


def incentive_rings():
    """A box inside the gold ring Highlight.Priority draws around it."""
    c = Canvas()
    c.border()
    c.ring(16, 16, 11, PRIORITY)
    c.ring(16, 16, 10, PRIORITY)
    c.square(16, 16, 4, GLYPH)
    return c


def art_stale():
    """The warning triangle over three marker boxes: the art is another seed's.

    Not a toggle. Same 32x32 ground and border as the four above, same amber as
    flagsUnread.png, and the boxes are the marker shape the toggles use -- so
    what it says is "a warning, about the pins on the map art", in the pack's
    own vocabulary rather than in a new one.
    """
    c = Canvas(fill=WARN_GROUND)
    c.border()
    apex_y, base_y, cx = 4, 19, 16
    for y in range(apex_y, base_y + 1):
        half = (y - apex_y) * 9 // (base_y - apex_y)
        for x in range(cx - half, cx + half + 1):
            c.set(x, y, AMBER)
    # The exclamation, cut out of the triangle rather than drawn over it.
    for y in range(9, 15):
        for x in (cx - 1, cx):
            c.set(x, y, AMBER_CUT)
    for x in (cx - 1, cx):
        c.set(x, 17, AMBER_CUT)
    for x in (9, 16, 23):
        c.square(x, 26, 2, GLYPH)
    return c


def mode_mismatch():
    """The warning triangle over a square and a diamond: the seed and the
    variant are not describing the same game.

    The third of the warning family, and the second drawn here. Same ground,
    border, triangle and amber as `art_stale` above, because two warning lights
    in one grid that disagreed about their amber would look like a mistake.

    What changes is the glyph under the triangle. `art_stale` pairs it with
    three marker boxes, which says "about the pins on the map art". This one
    pairs it with one square and one diamond -- the pack's two pin shapes,
    side by side and deliberately not the same shape -- which says "these two
    do not match" in a vocabulary the board already uses, without inventing a
    picture of a variant chooser that PopTracker does not draw either.
    """
    c = Canvas(fill=WARN_GROUND)
    c.border()
    apex_y, base_y, cx = 4, 19, 16
    for y in range(apex_y, base_y + 1):
        half = (y - apex_y) * 9 // (base_y - apex_y)
        for x in range(cx - half, cx + half + 1):
            c.set(x, y, AMBER)
    for y in range(9, 15):
        for x in (cx - 1, cx):
            c.set(x, y, AMBER_CUT)
    for x in (cx - 1, cx):
        c.set(x, 17, AMBER_CUT)
    c.square(10, 26, 3, GLYPH)
    c.diamond(22, 26, 3, GLYPH)
    return c


def entrance_pins_on():
    """Two trapezoids, which is what an entrance pin is drawn as."""
    c = Canvas()
    c.border()
    c.trapezoid(11, 12, 6, GLYPH)
    c.trapezoid(22, 21, 6, GLYPH)
    return c


def entrance_pins_off():
    """The same two, dimmed the way noAutoTab.png dims autoTab.png."""
    c = Canvas()
    c.border()
    c.trapezoid(11, 12, 6, DIM)
    c.trapezoid(22, 21, 6, DIM)
    return c


def entrance_pins_auto():
    """One of each: on some seeds these draw and on others they do not.

    The stage is "the seed decides", so the icon says the answer is not fixed
    rather than picking one of the two to show.
    """
    c = Canvas()
    c.border()
    c.trapezoid(11, 12, 6, GLYPH)
    c.trapezoid(22, 21, 6, DIM)
    return c


ICONS = {
    "showChestPins": chest_pins,
    "entrancePinsAuto": entrance_pins_auto,
    "entrancePinsOff": entrance_pins_off,
    "entrancePinsOn": entrance_pins_on,
    "showNpcPins": npc_pins,
    "showSkippedPins": skipped_pins,
    "showIncentiveRings": incentive_rings,
    "artStale": art_stale,
    "modeMismatch": mode_mismatch,
}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="report what would change and write nothing")
    args = ap.parse_args(argv)

    bad = 0
    for name, draw in sorted(ICONS.items()):
        path = os.path.join(PACK, "images", "flags", name + ".png")
        want = draw().rgb()
        have = None
        if os.path.exists(path):
            w, h, have = pngio.read_rgb(path)
            if (w, h) != (SIZE, SIZE):
                have = None
        if have == want:
            continue
        if args.check:
            print("differs: images/flags/%s.png" % name)
            bad += 1
        else:
            pngio.write_rgb(path, SIZE, SIZE, want)
            print("wrote images/flags/%s.png" % name)
    if args.check and bad:
        return 1
    if args.check:
        print("all %d icons match" % len(ICONS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
