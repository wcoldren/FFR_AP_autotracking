#!/usr/bin/env python3
"""The floor-walk memo, and the key that is the whole risk of having one.

`Graph.floor_walk` and `Graph.reachable_teleports` cache on
`(map, arrival, have & floor_items(map))`. A key that leaves out an item the
walk consults hands back another subset's reachability, silently, with nothing
failing -- which is the failure class this tree has hit repeatedly. So the key
is checked rather than reasoned about, and checked exhaustively.

Two guards, because they answer different halves:

  - **The key is sufficient, over the whole lattice.** A walk reads `have` in
    exactly two places -- `walkable()` on this map's tile property bytes, and
    `blocking_objects()` on its objects -- so if neither can tell `have` from
    `have & floor_items(map)`, for every map and every one of the 2^n subsets,
    then no walk can either. That is a proof rather than a sample, and it is
    cheap because it never walks.

  - **The sweep agrees end to end.** The expensive one: every subset, memoized
    against unmemoized, tile for tile, over the whole reachable set. It needs a
    No-Overworld cartridge and several minutes, so it runs on FF1_SLOW=1 and
    says so otherwise rather than passing quietly.

Set FF1_ROM to a cartridge. FF1_SLOW=1 adds the second guard.
"""
import itertools
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import entrance_graph as eg                                    # noqa: E402

fails = []


def ok(cond, label, got=""):
    print(f"{'ok  ' if cond else 'FAIL'} {label:62} {got}")
    if not cond:
        fails.append(label)


def main():
    path = os.environ.get("FF1_ROM")
    if not path or not os.path.exists(path):
        print("SKIP  set FF1_ROM to a Final Fantasy cartridge to run this")
        return 0

    rom = eg.Rom(path)
    g = eg.Graph(rom)
    items = sorted(eg.ITEM_NAMES)
    subsets = [frozenset(c) for n in range(len(items) + 1)
               for c in itertools.combinations(items, n)]
    ok(len(subsets) == 2 ** len(items),
       f"the lattice is all {2 ** len(items)} subsets of {len(items)} items",
       str(len(subsets)))

    # --- the key is sufficient -------------------------------------------
    #
    # Everything walkable() branches on that depends on `have`, per map: the
    # distinct property bytes it will ever be handed. Deduped because a 64x64
    # map has 4096 cells and at most a couple of dozen distinct bytes.
    bad_tile, bad_obj, empty = [], [], 0
    for m in range(eg.MAP_COUNT):
        floor = g.floor_items(m)
        if not floor:
            empty += 1
        _, p0, _ = g.grid(m)
        props = sorted(set(p0))
        for have in subsets:
            trimmed = have & floor
            for b0 in props:
                if eg.walkable(b0, have) != eg.walkable(b0, trimmed):
                    bad_tile.append((m, b0, sorted(have)))
            if g.blocking_objects(m, have) != g.blocking_objects(m, trimmed):
                bad_obj.append((m, sorted(have)))
    ok(not bad_tile,
       "no tile on any map can tell `have` from `have & floor_items`",
       str(bad_tile[:2]))
    ok(not bad_obj,
       "nor can any map's objects",
       str(bad_obj[:2]))
    # And the key has to be doing work rather than being `have` under another
    # name: most floors gate on nothing at all, which is what makes the memo
    # worth having.
    ok(empty > eg.MAP_COUNT // 2,
       "and most floors consult no item at all, so they walk once",
       f"{empty} of {eg.MAP_COUNT} maps")

    # --- assigning gated_objects throws the caches away -------------------
    #
    # The memo is keyed on items named by `gated_objects`, so replacing that
    # table invalidates every entry. test_gate_objects.py does exactly this to
    # prove the gates change something, and would otherwise be handed back the
    # gated walks it had already asked for.
    gates = eg.object_gate_items(rom)
    if gates:
        oid, item = sorted(gates.items())[0]
        spots = [(m, x, y) for m in range(eg.MAP_COUNT)
                 for o, x, y in g.objects(m) if o == oid]
        m, x, y = spots[0]
        side = ((x + 1) % eg.MAP_DIM, y)
        have = set(eg.ITEM_NAMES) - {item}
        warm = len(g.floor_walk(m, side, have))
        g.gated_objects = {k: v for k, v in g.gated_objects.items() if k != oid}
        ok(len(g.floor_walk(m, side, have)) != warm,
           f"dropping the ${oid:02X} row changes the walk it had just cached",
           f"{warm} tiles before")
        g.gated_objects = eg.Graph(rom).gated_objects
        ok(len(g.floor_walk(m, side, have)) == warm,
           "and putting it back restores the first answer")

    # --- the sweep agrees end to end --------------------------------------
    if not os.environ.get("FF1_SLOW"):
        print("SKIP  the full-lattice sweep comparison; set FF1_SLOW=1 to run"
              " it (minutes, and needs a No-Overworld cartridge)")
    else:
        sys.path.insert(0, HERE)
        import noverworld_rules as nr                          # noqa: E402
        if eg.game_mode(rom)[0] != eg.GAME_MODE_NOVERWORLD:
            print("SKIP  FF1_SLOW is set but FF1_ROM is not a No-Overworld"
                  " cartridge, and the sweep is that mode's")
        else:
            with open(path, "rb") as f:
                raw = f.read()
            seeds, _ = nr.start_doors(g, raw)

            class NoMemo(eg.Graph):
                """The same Graph with the caches emptied before every walk."""

                def floor_walk(self, *a, **k):
                    self._walks = {}
                    return eg.Graph.floor_walk(self, *a, **k)

                def reachable_teleports(self, *a, **k):
                    self._teleports = {}
                    return eg.Graph.reachable_teleports(self, *a, **k)

            plain = NoMemo(rom)
            fresh = eg.Graph(rom)
            differ = []
            for i, have in enumerate(subsets):
                if i % 64 == 0:
                    print(f"  {i}/{len(subsets)} subsets", end="\r",
                          file=sys.stderr)
                if nr.reachable_tiles(fresh, set(have), seeds) \
                        != nr.reachable_tiles(plain, set(have), seeds):
                    differ.append(sorted(have))
            print(" " * 40, end="\r", file=sys.stderr)
            ok(not differ,
               f"all {len(subsets)} subsets reach the same tiles either way",
               str(differ[:2]))

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
