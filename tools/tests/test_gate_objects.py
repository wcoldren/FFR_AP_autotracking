"""The No-Overworld gate NPCs have to block a step, and only on that mode.

Set FF1_ROM to a cartridge. A real No-Overworld seed is tested as it is; any
other image -- vanilla or an FFR seed of any mode -- gets a gate layout
synthesised into whichever talk jump table that cartridge actually uses, so the
test is useful on the vanilla cartridge this repo can assume and stronger on a
seed. Without FF1_ROM it skips rather than passing quietly.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import entrance_graph as eg                                    # noqa: E402

# Four addresses that no vanilla routine uses, one per gated item.
FAKE = {"floater": 0x9C00, "canoe": 0x9C10, "chime": 0x9C20, "tnt": 0x9C30}


def graph(path, gated):
    """A Graph on this cartridge, optionally with a gate layout written in.

    The synthesised layout has to go in the table the reader actually reads,
    which is not a constant: FFR moves the talk jump table out of $0E:90D3 and
    into $11:8000, and leaves a complete, well-formed, vanilla copy behind at
    the old address (Dialogues.cs:137 bulk-copies the region). Writing to the
    old one on an FFR cartridge therefore does not fail -- it writes somewhere
    nothing reads, and the gates come back unset.

    That is what made this test fail on every FFR standard seed while passing
    on the vanilla image and on a real No-Overworld one: the two cases where
    the vanilla address happens to be the live one, or where nothing had to be
    written at all. Ask talk_routine_bank, the same way the code under test
    does.
    """
    rom = eg.Rom(path)
    rom.data = bytearray(rom.data)
    if gated:
        where = eg.talk_routine_bank(rom.data)
        if where is None:
            return None
        base = eg.bank_off(*where)
        for oid, item in eg.NOVERWORLD_GATES.items():
            rom.data[base + oid * 2:base + oid * 2 + 2] = FAKE[item].to_bytes(2, "little")
    return eg.Graph(rom)


def main():
    path = os.environ.get("FF1_ROM")
    if not path or not os.path.exists(path):
        print("SKIP  set FF1_ROM to a Final Fantasy cartridge to run this")
        return 0

    native = graph(path, False)
    real = native.gates is not None
    # A real seed needs no help; anything else gets the layout written in, and
    # then also has to prove it blocked nothing before that.
    noow = native if real else graph(path, True)
    stock = None if real else native
    if noow is None:
        print("SKIP  this image has no readable talk jump table, so a gate "
              "layout cannot be written into it")
        return 0
    print(f"({'a real No-Overworld seed' if real else 'gate layout synthesised'})")
    fails = []

    def check(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")
        print(f"{'ok  ' if got == want else 'FAIL'} {label}")

    if stock is not None:
        check("a stock cartridge reports no gate layout", stock.gates, None)
        check("stock blocks the Rod and the Lute and nothing else",
              stock.gated_objects, dict(eg.GATED_OBJECTS))
    check("the gate layout is read back off the talk table",
          noow.gates, dict(eg.NOVERWORLD_GATES))
    check("the Rod and the Lute survive alongside the gates",
          {k: v for k, v in noow.gated_objects.items() if k in eg.GATED_OBJECTS},
          dict(eg.GATED_OBJECTS))

    placed = {}
    for m in range(eg.MAP_COUNT):
        for oid, x, y in noow.objects(m):
            if oid in eg.NOVERWORLD_GATES:
                placed.setdefault(oid, []).append((m, x, y))
    check("all eight gate objects stand somewhere", len(placed), 8)

    for oid, spots in sorted(placed.items()):
        item, (m, x, y) = eg.NOVERWORLD_GATES[oid], spots[0]
        name = f"${oid:02X} {eg.GATE_OBJ_NAMES[oid]}"
        check(f"{name} blocks its tile empty-handed",
              (x, y) in noow.blocking_objects(m, set()), True)
        check(f"{name} steps aside once you hold the {item}",
              (x, y) in noow.blocking_objects(m, {item}), False)
        if stock is not None:
            check(f"{name} blocks nothing on a stock cartridge",
                  (x, y) in stock.blocking_objects(m, set()), False)

    # Holding everything must leave the reachable set exactly where it was:
    # a gate that changes that answer is over-blocking, not gating.
    if real:
        with_gates = noow.reachable_maps(set(eg.ITEM_NAMES))
        noow.gated_objects, noow.grids = dict(eg.GATED_OBJECTS), {}
        check("gates change nothing once you hold every item",
              noow.reachable_maps(set(eg.ITEM_NAMES)), with_gates)

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
