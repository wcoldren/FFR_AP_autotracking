"""A staircase under your feet is a way on, so the floor it lands on gets walked.

Needs no cartridge. The graph below is the shape the real bug had: Ice Cave B1's
hole to B3 sits on the tile you arrive on, and B3 is entered no other way, so a
sweep that ran once after the walk listed the hole and then never explored B3 --
B3's own staircases went missing and the empty-handed headline undercounted.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import doormap as dm                                           # noqa: E402
import entrance_graph as eg                                    # noqa: E402

TO_B3, TO_B4 = 100, 101        # teleport payload ids


class Cartridge:
    """1 = Ice Cave B1, 2 = B3 (only reached by the hole), 3 = B4."""
    norm_map = {TO_B3: 2, TO_B4: 3}
    norm_x = {TO_B3: 1, TO_B4: 7}
    norm_y = {TO_B3: 1, TO_B4: 7}
    entr_map = [1] + [0xFF] * 31
    entr_x = [5] + [0] * 31
    entr_y = [5] + [0] * 31
    doors = {0: [(10, 10)]}

    def starts(self):
        return [(0, 1, (5, 5))]

    def teleports(self, map_id):
        return {1: [(5, 5, eg.TP_TELE_NORM, TO_B3)],
                2: [(9, 9, eg.TP_TELE_NORM, TO_B4)],
                3: []}.get(map_id, [])

    def reachable_teleports(self, map_id, start, have):
        # Drops the tile you stand on, exactly as the real one does.
        return {(x, y): (kind, pay, 4)
                for x, y, kind, pay in self.teleports(map_id) if (x, y) != start}


def main():
    data = dm.build(Cartridge(), [])
    links = {(f["fromId"], f["x"], f["y"]): f for f in data["floors"]}
    reach = set(data["reachable"])
    fails = []

    def check(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")
        print(f"{'ok  ' if got == want else 'FAIL'} {label}")

    check("the hole under your feet is walkable, not gated",
          links.get((1, 5, 5), {}).get("steps", "missing"), 0)
    check("B3's own staircase is listed",
          links.get((2, 9, 9), {}).get("steps", "missing"), 4)
    check("B3 counts as reachable", 2 in reach, True)
    check("and so does what B3 leads to", 3 in reach, True)

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
