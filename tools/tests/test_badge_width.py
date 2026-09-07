#!/usr/bin/env python3
"""Every badge an entrance pin can draw fits the slot the pack asks for.

The badge is an item overlay, and PopTracker neither measures an overlay into
the hover tooltip's width nor clips it when it draws it (item.cpp:336-368,
maptooltip.cpp:202-205). So an overlay wider than its slot renders out through
the popup's background, and nothing in the app complains. The pack's answer is
two halves that have to agree: overworld_pins.ENTRANCE_ITEM_WIDTH sizes the
slot, and entrance_items.lua's BADGE_SHORT trims the handful of names that
would not fit. This is what stops them drifting apart -- a tab renamed longer
in mapValues.lua fails here rather than in a popup nobody is looking at.

Measures rather than counts characters. A character budget would be a guess
about a proportional font, and picking a marker size by guess has cost this
repo two wrong claims before.

Reads no cartridge. Skips when the PopTracker clone is absent, since the font
is where the answer comes from -- the clone is optional in pins.yaml.
"""

import os
import re
import struct
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import overworld_pins  # noqa: E402

# DEFAULT_FONT_NAME, defaults.h:10 -- the overlay is drawn in the bold face,
# which trackerview.cpp:123 hands it. Measuring the regular one is how the
# first cut of this set the slot a pixel under what the badge draws.
FONT_REL = os.path.join("PopTracker", "assets", "DejaVuSans-Bold.ttf")


def find_font():
    """The app's own font, or None.

    Searched for rather than written down. The workspace's tools/vendor_paths.py
    is what knows where a clone lives, but it sits above this repo and the
    pack's tests do not import it -- and a vendor subpath hardcoded here would
    be exactly the thing that resolver exists to stop. So: an explicit
    FF1_POPTRACKER wins, and otherwise every directory on the way up is asked
    whether it holds a PopTracker, directly or under a vendor/.
    """
    named = os.environ.get("FF1_POPTRACKER")
    if named:
        at = os.path.join(named, "assets", "DejaVuSans-Bold.ttf")
        return at if os.path.exists(at) else None
    at = PACK
    while True:
        up = os.path.dirname(at)
        if up == at:
            return None
        at = up
        for guess in (os.path.join(at, FONT_REL),
                      os.path.join(at, "vendor", FONT_REL)):
            if os.path.exists(guess):
                return guess


FONT = find_font()

# trackerview.cpp:123 hands the overlay the default font at the size the item
# asked for, and entrance_items.lua asks for 10.
PPEM = 10

# item.cpp:305 builds the overlay surface two pixels wider than the text, for
# the light and shadow passes offset by one each.
OVERLAY_PAD = 2

fail = 0


def check(label, got, want):
    global fail
    ok = got <= want
    if not ok:
        fail += 1
    print(f"{'ok  ' if ok else 'FAIL'} {label:<46} {got:6.1f} <= {want}")


def _font(path):
    """(units per em, advance widths, char -> glyph id) for a TrueType file.

    Enough of the format to measure a string and no more: head for the scale,
    hhea and hmtx for the advances, and whichever cmap subtable is keyed on
    Unicode. The arrows the badge draws are outside Latin-1, so a format 4
    subtable is asked for by name rather than taken in file order.
    """
    with open(path, "rb") as fh:
        d = fh.read()
    tabs = {}
    for i in range(struct.unpack(">H", d[4:6])[0]):
        off = 12 + 16 * i
        o, _ = struct.unpack(">II", d[off + 8:off + 16])
        tabs[d[off:off + 4].decode("latin1")] = o
    upem = struct.unpack(">H", d[tabs["head"] + 18:tabs["head"] + 20])[0]
    count = struct.unpack(">H", d[tabs["hhea"] + 34:tabs["hhea"] + 36])[0]
    adv = [struct.unpack(">H", d[tabs["hmtx"] + 4 * i:tabs["hmtx"] + 4 * i + 2])[0]
           for i in range(count)]
    co = tabs["cmap"]
    subs = {}
    for i in range(struct.unpack(">H", d[co + 2:co + 4])[0]):
        pid, eid, off = struct.unpack(">HHI", d[co + 4 + 8 * i:co + 12 + 8 * i])
        subs[(pid, eid)] = co + off
    sub = subs.get((3, 1)) or subs.get((0, 3))
    assert struct.unpack(">H", d[sub:sub + 2])[0] == 4, "expected a format 4 cmap"
    seg2 = struct.unpack(">H", d[sub + 6:sub + 8])[0]
    seg = seg2 // 2
    read = lambda at: list(struct.unpack(f">{seg}H", d[at:at + seg2]))
    end, start = read(sub + 14), read(sub + 16 + seg2)
    delta, ro_at = read(sub + 16 + 2 * seg2), sub + 16 + 3 * seg2
    ro = read(ro_at)

    def gid(ch):
        c = ord(ch)
        for i in range(seg):
            if c > end[i]:
                continue
            if c < start[i]:
                return 0
            if ro[i] == 0:
                return (c + delta[i]) & 0xFFFF
            at = ro_at + 2 * i + ro[i] + 2 * (c - start[i])
            g = struct.unpack(">H", d[at:at + 2])[0]
            return 0 if g == 0 else (g + delta[i]) & 0xFFFF
        return 0

    return upem, adv, gid


def width(font, text):
    upem, adv, gid = font
    return sum(adv[min(gid(ch), len(adv) - 1)] for ch in text) * PPEM / upem


def main():
    if not FONT:
        print("skip: no PopTracker clone found (set FF1_POPTRACKER to name one)")
        return 0
    font = _font(FONT)

    src = open(os.path.join(PACK, "scripts", "entrance_items.lua"),
               encoding="utf-8").read()
    short = dict(re.findall(r'\["([^"]+)"\] = "([^"]+)",', src))
    arrows = re.findall(r'= "(\\226\\134\\1\d\d)"', src)
    assert len(arrows) == 3, "the three badge arrows"
    glyphs = [bytes(int(n) for n in re.findall(r"\\(\d+)", a)).decode("utf-8")
              for a in arrows]

    values = open(os.path.join(PACK, "scripts", "autotracking", "mapValues.lua"),
                  encoding="utf-8").read()
    leaves = sorted({v.split("/")[-1]
                     for _, v in re.findall(r'\[(-?\d+)\] = "([^"]+)"', values)})
    names = open(os.path.join(PACK, "scripts", "map_names.lua"),
                 encoding="utf-8").read()
    leaves += sorted({v for _, v in re.findall(r'\[(-?\d+)\] = "([^"]+)"', names)})

    budget = overworld_pins.ENTRANCE_ITEM_WIDTH - OVERLAY_PAD
    widest = max(((width(font, arrow + short.get(leaf, leaf)), leaf)
                  for leaf in leaves for arrow in glyphs), key=lambda r: r[0])
    check(f"widest badge line ({widest[1]})", widest[0], budget)

    # The abbreviations earn their place: without them the same measurement
    # does not fit, so a future reader can see what BADGE_SHORT is for rather
    # than take the comment's word for it.
    raw = max(width(font, glyphs[0] + leaf) for leaf in leaves)
    global fail
    if raw <= budget:
        fail += 1
        print(f"FAIL BADGE_SHORT no longer changes the answer  {raw:6.1f}")
    else:
        print(f"ok   without BADGE_SHORT it would not fit      {raw:6.1f} >  {budget}")

    # Every abbreviation names a leaf that exists, so a tab rename cannot leave
    # a dead row behind that looks like it is still doing something.
    for leaf in sorted(short):
        ok = leaf in leaves
        if not ok:
            fail += 1
        print(f"{'ok  ' if ok else 'FAIL'} abbreviated leaf exists: {leaf}")

    return fail


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
