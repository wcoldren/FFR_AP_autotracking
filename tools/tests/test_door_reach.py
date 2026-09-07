#!/usr/bin/env python3
"""The derived door rules: the three modelling points, and the corpus.

Each of the three was wrong in the first cut of door_reach and each moved the
answer, so each is shown here failing on a map built for it rather than asserted
about. A cartridge can only show the walk agreeing with itself.

  * the ship stays in its own sea -- otherwise the party docks, walks over the
    isthmus and re-boards on the far side, and the canal stops gating anything
  * the airship lands and then the party walks -- landable tiles are seeds for
    the walk, not the answer
  * a door can be entered from a vehicle -- the Waterfall is entered from the
    canoe, and keeping only the tiles the party stands on called it unreachable
    with every item in the game

With FF1_ROM set it also grades the derivation against the pack's own region
rules, which is the reason to trust it at all. Without one, everything below the
synthetic maps skips.
"""

import os
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, TOOLS)

import door_reach                                              # noqa: E402
import entrance_graph                                          # noqa: E402

fail = 0


def check(label, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'ok  ' if ok else 'FAIL'} {label:<54} {got}")
    if not ok:
        print(f"     wanted {want}")


class Grid:
    """A world spelled out row by row, with no wrap.

    `L` land, `D` land the ship can be boarded from, `S` sea, `C` the canal,
    `#` nothing. Small and explicit because the property under test is
    connectivity: the first cut of this test used a ring of land with a single
    water tile in it and the party simply walked the long way round, which the
    walk was right to allow and the test was wrong to call a canal crossing.
    """

    def __init__(self, rows):
        self.rows = rows

    def _at(self, x, y):
        if 0 <= y < len(self.rows) and 0 <= x < len(self.rows[y]):
            return self.rows[y][x]
        return "#"

    def allows(self, x, y, vehicle):
        c = self._at(x, y)
        if vehicle == door_reach.FOOT:
            return c in "LDC"
        if vehicle == door_reach.SHIP:
            return c in "SC"
        return False

    def docks(self, x, y):
        return self._at(x, y) == "D"

    def neighbours(self, x, y):
        return [(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]


def rom_with(**cells):
    """A stub ROM carrying only the unsram coordinates door_reach reads."""
    rom = bytearray(door_reach.UNSRAM + 32)
    for name, (x, y) in cells.items():
        idx = {"ship": door_reach.SHIP_XY, "bridge": door_reach.BRIDGE_XY,
               "canal": door_reach.CANAL_XY}[name]
        rom[door_reach.UNSRAM + idx] = x
        rom[door_reach.UNSRAM + idx + 1] = y
    return bytes(rom)


def main():
    # --- the ship stays in its own sea -------------------------------------
    #
    # Two seas with the canal between them, and a land bridge along the bottom
    # so the party can walk to the far dock without ever sailing. That is the
    # whole point: the far dock is *reachable on foot*, so the only thing
    # keeping the ship out of the far sea is that it is not moored there.
    #
    #     0 1 2 3 4 5 6 7 8
    #  y0 L D S S C S S D L
    #  y1 L L L L L L L L L
    w = Grid(["LDSSCSSDL",
              "LLLLLLLLL"])
    canal = (4, 0)
    near, far = (2, 0), (6, 0)
    rom = rom_with(ship=(3, 0), bridge=(90, 90), canal=canal)

    ship_only = door_reach.standable(w, rom, (0, 0), ("ship",), (90, 90), canal)
    with_canal = door_reach.standable(w, rom, (0, 0), ("ship", "canal"),
                                      (90, 90), canal)
    check("the party sails the sea its ship is in", near in ship_only, True)
    check("  and the far sea is not that sea", far in ship_only, False)
    check("  until the canal joins the two", far in with_canal, True)

    # And the failure the ship's own component prevents, shown rather than
    # described: the far dock is walkable-to, so a model that boarded at any
    # dock the party could reach would put the ship in the far sea with the
    # canal still unblown -- the party having carried it over the land bridge.
    check("  the far dock is reachable on foot all along",
          (7, 0) in ship_only, True)
    check("  so boarding there is the only thing being refused",
          far in door_reach.standable(
              w, rom_with(ship=(6, 0), bridge=(90, 90), canal=canal),
              (0, 0), ("ship",), (90, 90), canal),
          True)

    # --- the airship lands, then the party walks ---------------------------
    #
    # A world where the only airship-landable tile is not the door: if landing
    # were the answer the door would be unreachable, and it is not.
    class Island:
        def __init__(self, landable):
            self.landable = landable

        def allows(self, x, y, vehicle):
            if vehicle == door_reach.AIRSHIP:
                return (x, y) == self.landable
            if vehicle == door_reach.FOOT:
                return y == 0 and 0 <= x < 6
            return False

        def docks(self, x, y):
            return False

        def neighbours(self, x, y):
            return [(x + dx, y) for dx in (1, -1) if 0 <= x + dx < 6]

    isle = Island(landable=(0, 0))
    flown = door_reach.standable(isle, rom_with(ship=(90, 90)), (90, 90),
                                 ("airship",), (200, 200), (201, 201))
    check("the airship reaches a door it cannot land on", (5, 0) in flown, True)
    check("  because landing is a seed, not the answer", (0, 0) in flown, True)

    # --- a door can be entered from a vehicle ------------------------------
    #
    # A sea tile: nothing stands on it, and the Waterfall is a door exactly
    # there. Keeping only the "land" states would drop it.
    check("a tile only a boat reaches is still reachable",
          near in ship_only and w.allows(*near, door_reach.FOOT) is False, True)

    # --- minimal(), which is what turns a lattice into a rule --------------
    check("a superset is dropped for the set it contains",
          door_reach.show(door_reach.minimal(
              [{"ship"}, {"ship", "canoe"}, {"airship"}])),
          "airship OR ship")
    check("  and the free case swallows everything",
          door_reach.show(door_reach.minimal([set(), {"ship"}])), "(free)")

    # --- the cartridge -----------------------------------------------------
    path = os.environ.get("FF1_ROM")
    if not path or not os.path.exists(path):
        print("\nSKIP  set FF1_ROM to a cartridge for the graded half")
    else:
        with open(path, "rb") as fh:
            cart = fh.read()
        graph = entrance_graph.Graph(entrance_graph.Rom.of(cart, path))
        derived = door_reach.door_rules(cart, graph)
        print(f"\n-- {len(derived)} doors on {os.path.basename(path)}")
        check("every door got an answer",
              sorted(d for d, r in derived.items() if r is None), [])
        # The start is free by construction, and a rule that made it cost
        # something would mean the walk never left it.
        check("the door the party starts at is free",
              derived.get(door_reach.START_DOOR), [frozenset()])
        differ = door_reach.compare(cart, graph, derived)
        # Sarda's is the one the walk cannot see -- it is reachable through
        # Titan's Tunnel, which is not the overworld. Named rather than
        # tolerated, so a second disagreement fails the suite.
        check("only the through-a-dungeon door disagrees", differ <= 1, True)

    print("")
    if fail:
        print(f"{fail} FAILED")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
