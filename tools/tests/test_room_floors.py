"""A room opens; a cave floor does not.

Unroofing swaps the cells a roof covers to the map's inside palette, so the
room draws the way the game draws it when you are standing in it -- furniture
and floor together. The test is on the rule, not the appearance:

  * a hidden cell has to be blank outdoors and different inside, which is what
    separates a room floor from a cave floor. Coneria Castle 1F's tile $04
    draws flat white outdoors and flat black inside; Ice Cave B1's cave floor
    draws the same under both, and its 3177 walkable flat cells must never
    enter the running;
  * and the region has to be small, because a uniform rock wall is flat for the
    same reason a room is.

Set FF1_ROM to a cartridge; without one this skips.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import render_maps as rm                                       # noqa: E402


def art_for(rom, map_id):
    tileset = rom[rm.TILESET_LUT + map_id]
    return (rm.tileset_art(rom, tileset, rm.map_palettes(rom, map_id, False)),
            rm.tileset_art(rom, tileset, rm.map_palettes(rom, map_id, True)))


def grid(rom, map_id):
    base = rm.map_data_base(rom)
    ptr = int.from_bytes(rom[base + map_id * 2:base + map_id * 2 + 2], "little")
    return rm.decompress_map(rom, base + ptr)


def components(cells):
    seen, out = set(), []
    for start in cells:
        if start in seen:
            continue
        seen.add(start)
        stack, comp = [start], []
        while stack:
            r, c = stack.pop()
            comp.append((r, c))
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (r + dr, c + dc)
                if n in cells and n not in seen:
                    seen.add(n)
                    stack.append(n)
        out.append(comp)
    return out


def main():
    path = os.environ.get("FF1_ROM")
    if not path or not os.path.exists(path):
        print("SKIP  set FF1_ROM to a Final Fantasy cartridge to run this")
        return 0
    with open(path, "rb") as f:
        rom = f.read()
    fails = []

    def check(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")
        print(f"{'ok  ' if got == want else 'FAIL'} {label}")

    opened = big_skipped = flat_after = same_both = oversized = 0
    for map_id in range(rm.MAP_COUNT):
        tiles = grid(rom, map_id)
        art, open_art = art_for(rom, map_id)
        hidden = rm.hidden_cells(rom, map_id, tiles, art, open_art)
        opened += len(hidden)

        for r, c in hidden:
            t = tiles[r * rm.MAP_DIM + c] & 0x7F
            # It was blank before, and it is not the same afterwards -- opening
            # a cell that draws identically either way is a no-op that would
            # mean the test below has no teeth.
            if not rm.flat_art(art[t]):
                flat_after += 1
            if rm._colours(art[t]) == rm._colours(open_art[t]):
                same_both += 1

        for comp in components(hidden):
            if len(comp) > rm.ROOM_MAX_CELLS:
                oversized += 1

        # The guard has teeth: regions that pass the art test but are too big
        # to be rooms exist, and are left alone.
        under = {(i // rm.MAP_DIM, i % rm.MAP_DIM) for i, t in enumerate(tiles)
                 if rm.flat_art(art[t & 0x7F])
                 and rm._colours(art[t & 0x7F]) != rm._colours(open_art[t & 0x7F])}
        for comp in components(under):
            if len(comp) > rm.ROOM_MAX_CELLS:
                big_skipped += 1
                if any(cell in hidden for cell in comp):
                    fails.append(f"map {map_id}: a {len(comp)}-cell flat region "
                                 "was opened; that is a wall, not a room")

    check("every opened cell was blank outdoors", flat_after, 0)
    check("every opened cell draws differently inside", same_both, 0)
    check("no opened region is bigger than a room", oversized, 0)
    print(f"     ({opened} cells opened; {big_skipped} oversized flat regions "
          "left alone)")
    check("something was opened at all", opened > 0, True)
    check("and something was deliberately not", big_skipped > 0, True)

    # Coneria Castle 1F's room floor is the case the palette-based rule missed:
    # tile $04, flat white outdoors, flat black inside. If it is not opened the
    # rooms are holes again.
    art, open_art = art_for(rom, 8)
    check("con_castle tile $04 is blank outdoors", rm.flat_art(art[0x04]), True)
    check("and draws something else inside",
          rm._colours(art[0x04]) != rm._colours(open_art[0x04]), True)
    tiles = grid(rom, 8)
    hidden = rm.hidden_cells(rom, 8, tiles, art, open_art)
    floor = {(i // rm.MAP_DIM, i % rm.MAP_DIM) for i, t in enumerate(tiles)
             if (t & 0x7F) == 0x04}
    check("and every one of its cells is opened", floor - hidden, set())

    # Without unroof there are no rooms, so a roofed render must be exactly what
    # it always was -- render_maps.py --check compares against FF1R on that path.
    same = all(rm.render(rom, m)[2] == rm.render(rom, m, unroof=False)[2]
               for m in (0, 8, 15))
    check("a roofed render is untouched", same, True)

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
