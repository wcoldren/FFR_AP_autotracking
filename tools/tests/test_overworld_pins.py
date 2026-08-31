#!/usr/bin/env python3
"""Every overworld pin lands on the door the cartridge puts its place on.

The pins used to be pixels on a drawing, and the drawing is not a scaled map:
fitting the drawn pins against the tiles the cartridge names leaves residuals up
to eleven tiles. So there is no transform to check against, and the checks that
are worth anything are these:

  * every pin the pack draws on the overworld resolves to somewhere. A pin the
    resolver cannot place keeps no position at all on rendered art, so silence
    here would be pins vanishing.
  * a resolved pin stands on a tile that is actually a door -- the property
    table says which tiles those are, and it is not the table the resolver
    walked to get there.
  * the three Cardia pins land on three different doors. They are one map with
    five entrances, which is the case that cannot be answered by asking what
    map a door leads to, and the case a careless fix collapses onto one island.
  * `I: Shop Item` lands on the caravan and `Ryukahn Desert` on the desert the
    floater digs the airship out of. Neither has a chest to ask about; both are
    a tile property.
  * two pins never share a tile, because a pin under a pin is one pin.

Set FF1_ROM to a cartridge; without one this skips. A No-Overworld cartridge is
tested as it is: it has no caravan and no airship desert, so those two pins are
expected to come back unplaced rather than placed somewhere plausible.

**A vanilla image is not an FFR one and the difference matters here.** The
staircase walk reads the expanded teleport tables FFR's ExpandNormalTeleporters
writes into bank $0F, which a stock cartridge does not have -- so on one, the six
pins whose place is behind a staircase rather than on a door cannot resolve, and
that is the tool being honest rather than failing. standard_map_bank tells the
two apart ($14 on an FFR seed, $04 on a stock one) and the checks below say
which of them each cartridge is being held to.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import entrance_graph  # noqa: E402
import extract_chests  # noqa: E402
import overworld_pins as op  # noqa: E402
import regen_maps  # noqa: E402
import render_overworld as ro  # noqa: E402

fail = 0


def check(label, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'ok  ' if ok else 'FAIL'} {label:<54} {got}")
    if not ok:
        print(f"     wanted {want}")


def main():
    path = os.environ.get("FF1_ROM")
    if not path or not os.path.exists(path):
        print("SKIP  set FF1_ROM to a Final Fantasy cartridge to run this")
        return 0
    rom = open(path, "rb").read()
    reader = entrance_graph.Rom(path)
    graph = entrance_graph.Graph(reader)
    nov = not ro.caravan(rom)
    board = ("locations/NOverworld/overworld.json" if nov
             else "locations/overworld.json")
    doc = json.load(open(os.path.join(PACK, board)))
    tiles = regen_maps.marker_tiles(rom, board)

    placed, unplaced, anchors = op.resolve(rom, reader, graph, doc, tiles)
    pins = [name for name, _ in op.pin_names(doc)]
    print(f"-- {os.path.basename(path)}: {len(pins)} pins on the overworld art")

    ffr = extract_chests.standard_map_bank(rom) == 0x14
    print(f"     ({'an FFR seed' if ffr else 'a stock cartridge'}, "
          f"{'No-Overworld' if nov else 'standard'})")

    # A No-Overworld cartridge really has neither a caravan nor an airship
    # desert, and saying so is the answer. On a stock cartridge the staircase
    # walk has no table, so the pins behind one go with them.
    expected_short = {"Ryukahn Desert", "I: Shop Item"} if nov else set()
    got_short = {n for n, _ in unplaced}
    if ffr:
        check("everything resolved but what this cartridge lacks",
              got_short, expected_short)
    else:
        check("what is missing is missing for a reason this run can name",
              sorted({why.split(" map(s)")[0] for n, why in unplaced
                      if n not in expected_short}),
              ["no door reaches"])
        check("  and the ones it can name are the routed ones",
              got_short >= expected_short, True)
    check("and the rest are placed", len(placed) + len(unplaced), len(pins))

    doors = op.door_cells(reader)
    on_a_door = set(doors.values())
    props = ro.props(rom)
    rows = None

    def special(where, mask):
        nonlocal rows
        if rows is None:
            import overworld_reach
            rows = overworld_reach.decompress_ow(rom)
        tile = rows[where[1]][where[0]]
        return props[tile * 2] & ro.OWTP_SPEC_MASK == mask

    # Ryukahn Desert is the middle of a 49-tile field rather than a door, and
    # the caravan is a shop rather than a place, so both are exempt by name.
    by_property = {n for n in placed
                   if (n[3:] if n.startswith("I: ") else n) in op.BY_PROPERTY}
    off_door = sorted(n for n, w in anchors.items()
                      if n not in by_property and w not in on_a_door)
    check("every other pin resolves to a door", off_door, [])

    # Several pins share a door -- ToFR enters through the Temple of Fiends,
    # and on a No-Overworld cartridge nine stub doors carry everything -- so a
    # pin is drawn on its door or in the column directly above it. Anywhere
    # else is a position nothing derived.
    strayed = sorted(n for n, w in placed.items()
                     if w[0] != anchors[n][0] or w[1] > anchors[n][1])
    check("and is drawn on it or in the column above it", strayed, [])

    if not nov and ffr:
        cardia = sorted(w for n, w in anchors.items() if n.startswith("Cardia"))
        check("the three Cardia pins are three islands",
              len(cardia), len(set(cardia)))
        check("  and each is a door", [w for w in cardia if w not in on_a_door], [])
        check("I: Shop Item is on the caravan",
              special(placed["I: Shop Item"], ro.OWTP_SPEC_CARAVAN), True)
        check("Ryukahn Desert is on the floater's desert",
              special(placed["Ryukahn Desert"], op.OWTP_SPEC_FLOATER), True)

    check("no two pins share a tile",
          len(set(placed.values())), len(placed))

    # The mirror is what puts a pin on the incentive slots that hold no chest
    # of their own, so it has to reach further down the tree than the pins do.
    mirror = op.mirror_of(doc, placed)
    check("the mirror covers every pin", set(placed) <= set(mirror), True)
    check("and more of the tree than just the pins", len(mirror) > len(placed), True)

    print("")
    if fail:
        print(f"{fail} FAILED")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
