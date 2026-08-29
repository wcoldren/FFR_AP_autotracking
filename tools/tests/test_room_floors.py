"""A room floor gets filled; a cave floor does not.

Unroofing resolves a room's furniture and leaves the floor between it blank,
because that tile is flat in both palettes -- so render_maps fills it with the
corridor outside. The filling is a deliberate substitution, which is exactly
why it needs guards: flatness alone also describes a cave floor, and Ice Cave
B1 has 3177 walkable cells that draw one colour. The guards are what this
tests, not the appearance.

Set FF1_ROM to a cartridge; without one this skips.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import entrance_graph as eg                                    # noqa: E402
import render_maps as rm                                       # noqa: E402


def pieces(rom, map_id):
    """The inputs room_floors works from, and its answer."""
    base = rm.map_data_base(rom)
    ptr = int.from_bytes(rom[base + map_id * 2:base + map_id * 2 + 2], "little")
    tiles = rm.decompress_map(rom, base + ptr)
    ts = rom[rm.TILESET_LUT + map_id]
    art = rm.tileset_art(rom, ts, rm.map_palettes(rom, map_id, False))
    open_art = rm.tileset_art(rom, ts, rm.map_palettes(rom, map_id, True))
    rooms = rm.room_cells(rom, map_id, tiles)
    return tiles, art, open_art, rooms, rm.room_floors(
        rom, map_id, tiles, rooms, art, open_art)


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

    filled = big_skipped = 0
    not_walkable = still_flat = orphan = oversized = []
    for map_id in range(rm.MAP_COUNT):
        tiles, art, open_art, rooms, fill = pieces(rom, map_id)
        _, props = eg.tile_properties(rom, map_id)
        filled += len(fill)

        # Everything filled has to be floor you can stand on, and has to draw
        # something afterwards -- filling blank with blank is not a fill.
        not_walkable += [(map_id, rc) for rc in fill
                         if not eg.walkable(props[rc[0] * rm.MAP_DIM + rc[1]], set())]
        still_flat += [(map_id, rc) for rc, t in fill.items()
                       if rm.flat_art(art[t])]

        # Every filled component is small and belongs to a room.
        for comp in components(set(fill)):
            if len(comp) > rm.ROOM_MAX_CELLS:
                oversized.append((map_id, len(comp)))
            if not any((r + dr, c + dc) in rooms for r, c in comp
                       for dr, dc in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1))):
                orphan.append((map_id, len(comp)))

        # And the guard has teeth: a flat walkable region too big to be a room
        # exists and is left alone.
        blank = set()
        for i, t in enumerate(tiles):
            r, c = divmod(i, rm.MAP_DIM)
            here = open_art if (r, c) in rooms else art
            if rm.flat_art(here[t & 0x7F]) and eg.walkable(props[i], set()):
                blank.add((r, c))
        for comp in components(blank):
            if len(comp) > rm.ROOM_MAX_CELLS:
                big_skipped += 1
                if any(rc in fill for rc in comp):
                    fails.append(f"map {map_id}: a {len(comp)}-cell flat region "
                                 "was filled; that is a cave floor, not a room")

    check("every filled cell is walkable", not_walkable, [])
    check("every fill tile actually draws something", still_flat, [])
    check("no filled region is bigger than a room", oversized, [])
    check("every filled region belongs to a room", orphan, [])
    print(f"     ({filled} cells filled; {big_skipped} oversized flat regions "
          "left alone)")
    check("something was filled at all", filled > 0, True)
    check("and something was deliberately not", big_skipped > 0, True)

    # Without unroof there are no rooms, so there is nothing to fill and the
    # image must be exactly what it was before any of this existed.
    same = all(rm.render(rom, m)[2] == rm.render(rom, m, unroof=False)[2]
               for m in (0, 8, 15))
    check("a roofed render is untouched", same, True)

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
