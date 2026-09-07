#!/usr/bin/env python3
"""scripts/map_names.lua says what tools/entrance_graph.py says.

The pack names a map when the badge on an entrance pin has to say where a door
came out and no tab claims that map id. That name is the cartridge's, so the
list belongs to entrance_graph -- but the pack cannot import Python, and a
regen cannot write this one: it is not a fact about a seed. FFR shuffles which
map a door leads to and never renames a map, so the table is committed and this
is what stops the copy drifting.

Reads no cartridge.
"""

import os
import re
import sys

TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import entrance_graph  # noqa: E402

fail = 0


def check(label, got, want):
    global fail
    ok = got == want
    if not ok:
        fail += 1
    print(f"{'ok  ' if ok else 'FAIL'} {label:<52} {got}")


def main():
    with open(os.path.join(PACK, "scripts", "map_names.lua")) as fh:
        src = fh.read()
    table = {int(k): v
             for k, v in re.findall(r'\[(-?\d+)\] = "([^"]+)"', src)}

    check("every map the cartridge has is named",
          sorted(set(range(entrance_graph.MAP_COUNT)) - set(table)), [])
    wrong = [i for i in range(entrance_graph.MAP_COUNT)
             if table.get(i) != entrance_graph.MAP_NAMES[i]]
    check("  and named what entrance_graph names it", wrong, [])

    # The overworld is not one of the cartridge's maps and needs a name anyway:
    # ff1/edges reports it as -1, and a badge reading "->" and nothing is the
    # failure this table exists to remove.
    check("the overworld is named too", table.get(-1), "Overworld")
    check("and nothing else is",
          sorted(set(table) - set(range(entrance_graph.MAP_COUNT)) - {-1}), [])

    print("")
    if fail:
        print(f"{fail} FAILED")
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
