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


def and_form(path):
    """True when the Black Orb's routine is an AND chain over four addresses.

    Deliberately only the opcode skeleton: LDA abs then three AND abs. Which
    four addresses the chain names is what black_orb_item decides, so repeating
    that here would make the check agree with the code under test by
    construction -- which is the failure this replaced. A shard-hunt cartridge
    runs LDA/CMP and fails at the first AND.
    """
    rom = eg.Rom(path)
    routines = eg.talk_routines(rom)
    if routines is None or eg.BLACK_ORB_OBJ not in routines:
        return False
    where = eg.talk_routine_bank(rom.data)
    if where is None:
        return False
    body = rom.data[eg.bank_off(where[0], routines[eg.BLACK_ORB_OBJ]):][:12]
    if len(body) < 12:
        return False
    return body[0] == 0xAD and all(body[i] == 0x2D for i in (3, 6, 9))


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
        # The Black Orb is not part of the No-Overworld gate layout and is not
        # in GATED_OBJECTS either: it is read per cartridge, and a stock FFR
        # image carries it whenever its routine is the four-orb AND. So the
        # expectation is the plates plus that, not the plates alone.
        #
        # The expected value is decided here rather than taken from
        # black_orb_item on this same ROM. Sourcing it from the function under
        # test only pins that Graph copies whatever that function returned:
        # "rod", or None on a cartridge that does carry the AND form, would
        # both pass it. `and_form` reads the opcode skeleton instead -- an LDA
        # followed by three ANDs -- which is independent of the address sets
        # black_orb_item matches, the part most likely to be got wrong.
        # SubEngineer and Titan are id-keyed the same way, and their items are
        # constants of the game rather than of the seed -- SCMap.cs:167-186
        # stamps Oxyale on the one and Ruby on the other, and FF1 has done so
        # since 1987. Named here for that reason; that the *reader* gets them
        # off this cartridge rather than out of a table is checked below,
        # against the requirement byte and against synthesised bodies.
        want = dict(eg.GATED_OBJECTS)
        want[eg.NPC_IDS["subengineer"]] = "oxyale"
        want[eg.NPC_IDS["titan"]] = "ruby"
        if and_form(path):
            want[eg.BLACK_ORB_OBJ] = "orbs"
        check("stock blocks the plates, and the Black Orb where it applies",
              stock.gated_objects, want)
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

    # ---------------------------------------------------------- the Black Orb
    #
    # FFR moves the time warp's orb requirement off the tile and onto the NPC
    # (BlackOrb.cs:286), and what the NPC wants depends on the goal: the stock
    # routine ANDs the four orb bytes, a shard-hunt seed compares a count.
    # black_orb_item() has to answer "orbs" for the first and refuse the rest,
    # so the near-misses below are the half that matters -- a reader that says
    # "orbs" to anything would gate a shard seed on four orbs it never wants.
    def routine_says(body):
        rom = eg.Rom(path)
        rom.data = bytearray(rom.data)
        where = eg.talk_routine_bank(rom.data)
        addr = eg.talk_routines(rom)[eg.BLACK_ORB_OBJ]
        off = eg.bank_off(where[0], addr)
        rom.data[off:off + len(body)] = body
        return eg.black_orb_item(rom)

    def anded(*addrs):
        out = bytearray()
        for i, a in enumerate(addrs):
            out += bytes([0xAD if i == 0 else 0x2D, a & 0xFF, a >> 8])
        return bytes(out)

    check("four orb bytes, FFR order, read as orbs",
          routine_says(anded(0x6032, 0x6033, 0x6034, 0x6031)), "orbs")
    check("four orb bytes, vanilla order, read as orbs",
          routine_says(anded(0x6032, 0x6033, 0x6034, 0x6035)), "orbs")
    check("a shard count is refused",
          routine_says(bytes.fromhex("AD3560C91C300CA0CA209690")), None)
    check("three orb bytes and a repeat is refused",
          routine_says(anded(0x6032, 0x6033, 0x6034, 0x6034)), None)
    check("an AND of something that is not an orb is refused",
          routine_says(anded(0x6032, 0x6033, 0x6034, 0x6026)), None)
    # The near-miss that matters most, because the union of the two real forms
    # spans $6031..$6035 and "any four drawn from that" accepts this: three orb
    # bytes plus the shard counter. Reading it as "orbs" would install a shard
    # count as an orb gate, which is the one answer the sweep cannot hold.
    check("three orb bytes and the shard counter is refused",
          routine_says(anded(0x6031, 0x6032, 0x6033, 0x6035)), None)
    check("the other mixed four is refused too",
          routine_says(anded(0x6031, 0x6033, 0x6034, 0x6035)), None)

    # And the gate itself, where this cartridge carries the AND form: the warp
    # tile has to refuse a step empty-handed and allow one with the orbs.
    if eg.black_orb_item(eg.Rom(path)) == "orbs":
        g = eg.Graph(eg.Rom(path))
        spots = [(m, x, y) for m in range(eg.MAP_COUNT)
                 for oid, x, y in g.objects(m) if oid == eg.BLACK_ORB_OBJ]
        check("the Black Orb stands somewhere", len(spots) >= 1, True)
        for m, x, y in spots:
            check("the warp tile refuses a step empty-handed",
                  (x, y) in g.blocking_objects(m, set()), True)
            check("the warp tile opens once the orbs are lit",
                  (x, y) in g.blocking_objects(m, {"orbs"}), False)

    # --------------------------------- SubEngineer and Titan, gated by their id
    #
    # The last two of SCMap.cs:167-186's five object gates. Read off the
    # cartridge, and the two halves are read differently because the cartridge
    # makes them differently legible -- see object_gate_items. Both halves are
    # checked against something other than the function under test: Titan
    # against the requirement byte in FFR's own talk table, which is a field the
    # body scan never looks at, and SubEngineer against synthesised bodies whose
    # answer is decided here.
    gates = eg.object_gate_items(eg.Rom(path))
    reqs = eg.talk_requirement_bytes(eg.Rom(path))
    titan, engineer = eg.NPC_IDS["titan"], eg.NPC_IDS["subengineer"]

    # Titan: the byte says Item.Ruby (variables.inc item_ruby = items + $09) and
    # the routine loads that same address, so talk_item_requirements answers and
    # object_gate_items has only to carry it through. On a stock image there is
    # no requirement table at all, and then the body scan is the only path --
    # which is worth having run, so this asserts the answer either way.
    check("Titan wants the Ruby", gates.get(titan), "ruby")
    if reqs is not None:
        check("and FFR's own requirement byte says items + $09",
              reqs[titan], 0x09)
    check("the sub engineer wants the Oxyale", gates.get(engineer), "oxyale")
    if reqs is not None:
        # The half that makes the scan necessary rather than a second opinion.
        check("while the sub engineer's byte says nothing at all",
              reqs[engineer], 0x00)

    # The scan's shape, on bodies written here. One item address is the answer;
    # anything else is a refusal, because with the byte empty there is no second
    # source to break a tie.
    def scan_says(body):
        rom = eg.Rom(path)
        rom.data = bytearray(rom.data)
        where = eg.talk_routine_bank(rom.data)
        addr = eg.talk_routines(rom)[engineer]
        off = eg.bank_off(where[0], addr)
        # Blank the routine first: a shorter body would leave the real one's
        # `AD 30 60` trailing behind it and every case would read as oxyale.
        rom.data[off:off + 0x40] = b"\x60" * 0x40
        rom.data[off:off + len(body)] = body
        return eg.object_gate_items(rom).get(engineer)

    def lda(off):
        return bytes([0xAD, (eg.ITEMS + off) & 0xFF, (eg.ITEMS + off) >> 8])

    check("one item load names that item", scan_says(lda(0x10)), "oxyale")
    check("a different one names a different item", scan_says(lda(0x06)), "tnt")
    check("no item load at all is refused", scan_says(b"\xa5\x71\x60"), None)
    check("two item loads are refused", scan_says(lda(0x10) + lda(0x06)), None)
    # items + $11 is item_canoe's address and also where FFR's ShiftEarthOrbDown
    # puts the Earth Orb, so a body naming it means two different things and the
    # scan must not pick one. Reading it as the canoe would gate the Sea Shrine
    # on a vehicle the mode does not have.
    check("items + $11 is refused, being the canoe and the Earth Orb both",
          scan_says(lda(0x11)), None)
    check("and does not stop a real load beside it being read",
          scan_says(lda(0x11) + lda(0x10)), "oxyale")

    # And the gates themselves. Same shape as the Black Orb's: refuse a step
    # empty-handed, allow one with the item.
    g = eg.Graph(eg.Rom(path))
    for oid, item in sorted(gates.items()):
        spots = [(m, x, y) for m in range(eg.MAP_COUNT)
                 for o, x, y in g.objects(m) if o == oid]
        check(f"object ${oid:02X} stands somewhere", len(spots) >= 1, True)
        for m, x, y in spots:
            check(f"${oid:02X} blocks its tile empty-handed",
                  (x, y) in g.blocking_objects(m, set()), True)
            check(f"${oid:02X} steps aside once you hold the {item}",
                  (x, y) in g.blocking_objects(m, {item}), False)

    # The working rule: a gate row that closes nothing anywhere is either dead
    # code or evidence the enforcement is not wired.
    #
    # Asked of the floor rather than of the map list, because on a vanilla
    # cartridge the map list cannot answer: the Sea Shrine's entrance is an
    # overworld whirlpool tile, so Graph.starts() seeds the walk inside it and
    # every Sea Shrine floor is "reachable" whatever the engineer does. That is
    # a fact about seeding from all doors, not about the gate. The derivation
    # asks per tile for exactly this reason -- so does this. Walk in from each
    # side of the object and require that at least one side loses ground.
    for oid, item in sorted(gates.items()):
        have = set(eg.ITEM_NAMES) - {item}
        spots = [(m, x, y) for m in range(eg.MAP_COUNT)
                 for o, x, y in g.objects(m) if o == oid]
        shrank = False
        for m, x, y in spots:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                side = ((x + dx) % eg.MAP_DIM, (y + dy) % eg.MAP_DIM)
                gated = len(g.floor_walk(m, side, have))
                g.gated_objects = {k: v for k, v in g.gated_objects.items()
                                   if k != oid}
                loose = len(g.floor_walk(m, side, have))
                g.gated_objects = eg.Graph(eg.Rom(path)).gated_objects
                shrank = shrank or gated < loose
        check(f"${oid:02X} cuts its floor for a player without the {item}",
              shrank, True)

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
