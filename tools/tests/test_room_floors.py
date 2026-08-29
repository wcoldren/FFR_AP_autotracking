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
import entrance_graph as eg                                    # noqa: E402
import render_maps as rm                                       # noqa: E402

# NES $30, the colour a roof slab draws. The shipped hand-drawn maps never show
# a walkable cell in it: DarkmoonEX draws room floors dark with the furniture on
# them. So "walkable cells still drawing flat white" is the distance from the
# original art, and it is the number that has to go to zero.
ROOF_WHITE = (255, 255, 255)


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

        # Every opened cell has to be justified by one of the two tests: on a
        # roof sub-palette, or blank outdoors and different inside. Nothing is
        # opened for any other reason.
        roof = rm.roof_palettes(rom, map_id)
        tileset = rom[rm.TILESET_LUT + map_id]
        attrs = rom[rm.ATTR_BASE + 0x80 * tileset:
                    rm.ATTR_BASE + 0x80 * tileset + rm.TILES_PER_SET]
        for r, c in hidden:
            t = tiles[r * rm.MAP_DIM + c] & 0x7F
            by_palette = (attrs[t] & 3) in roof
            by_art = (rm.flat_art(art[t])
                      and rm._colours(art[t]) != rm._colours(open_art[t]))
            if not (by_palette or by_art):
                flat_after += 1
            # And opening a cell that draws identically either way is a no-op.
            if rm._colours(art[t]) == rm._colours(open_art[t]) and not by_palette:
                same_both += 1

        # The size guard binds each test's own components. Their union may be
        # larger where a room's floor abuts its furniture, which is the point.
        seeded = {(i // rm.MAP_DIM, i % rm.MAP_DIM) for i, t in enumerate(tiles)
                  if (attrs[t & 0x7F] & 3) in roof} if roof else set()
        blank = {(i // rm.MAP_DIM, i % rm.MAP_DIM) for i, t in enumerate(tiles)
                 if rm.flat_art(art[t & 0x7F])
                 and rm._colours(art[t & 0x7F]) != rm._colours(open_art[t & 0x7F])}
        # A cell in an oversized region may still be opened -- but only if the
        # *other* test justifies it on a small region of its own. Nothing is
        # opened on the strength of a mass too big to be a room.
        small = {}
        for tag, source in (("pal", seeded), ("art", blank)):
            small[tag] = {cell for comp in components(source)
                          if len(comp) <= rm.ROOM_MAX_CELLS for cell in comp}
        for cell in hidden:
            if cell not in small["pal"] and cell not in small["art"]:
                oversized += 1

        # The guard has teeth: regions that pass the art test but are too big
        # to be rooms exist, and are left alone.
        under = {(i // rm.MAP_DIM, i % rm.MAP_DIM) for i, t in enumerate(tiles)
                 if rm.flat_art(art[t & 0x7F])
                 and rm._colours(art[t & 0x7F]) != rm._colours(open_art[t & 0x7F])}
        for comp in components(under):
            if len(comp) > rm.ROOM_MAX_CELLS:
                big_skipped += 1
                # Mirage Tower 1F's outer wall is 458 such cells. A version that
                # flooded outward from a room absorbed the whole ring and redrew
                # it bright orange where the shipped art has dark red brick --
                # so this checks the wall is not opened *as a wall*, allowing
                # only cells the sub-palette independently calls a room.
                stray = [c for c in comp if c in hidden and c not in small["pal"]]
                if stray:
                    fails.append(f"map {map_id}: {len(stray)} cells of a "
                                 f"{len(comp)}-cell wall were opened")

    # The acceptance test, and the one worth stating in the terms the art does:
    # am I closer to the original maps or farther from them? Zero walkable
    # white voids is "as close as the shipped art", and it is checked rather
    # than eyeballed. An earlier rule scored zero here by closing whole rooms
    # instead of opening them, so the regression check below is its other half.
    voids = []
    for map_id in range(rm.MAP_COUNT):
        tiles = grid(rom, map_id)
        art, open_art = art_for(rom, map_id)
        hidden = rm.hidden_cells(rom, map_id, tiles, art, open_art)
        _, props = eg.tile_properties(rom, map_id)
        for i, t in enumerate(tiles):
            rc = (i // rm.MAP_DIM, i % rm.MAP_DIM)
            block = (open_art if rc in hidden else art)[t & 0x7F]
            if (rm.flat_art(block) and block[0][0] == ROOF_WHITE
                    and eg.walkable(props[i], set())):
                voids.append((map_id, rc))
    check("no walkable cell is left drawing a blank white slab", len(voids), 0)

    # And the other direction: the sub-palette test is the game's own mechanism,
    # so whatever it opens must stay open. Opening fewer cells than it does
    # means rooms were closed, which is farther from the art, not closer.
    closed = []
    for map_id in range(rm.MAP_COUNT):
        tiles = grid(rom, map_id)
        art, open_art = art_for(rom, map_id)
        roof = rm.roof_palettes(rom, map_id)
        if not roof:
            continue
        tileset = rom[rm.TILESET_LUT + map_id]
        attrs = rom[rm.ATTR_BASE + 0x80 * tileset:
                    rm.ATTR_BASE + 0x80 * tileset + rm.TILES_PER_SET]
        seeded = {(i // rm.MAP_DIM, i % rm.MAP_DIM) for i, t in enumerate(tiles)
                  if (attrs[t & 0x7F] & 3) in roof}
        want = {cell for comp in rm._components(seeded)
                if len(comp) <= rm.ROOM_MAX_CELLS for cell in comp}
        missing = want - rm.hidden_cells(rom, map_id, tiles, art, open_art)
        if missing:
            closed.append((map_id, len(missing)))
    check("every room the sub-palette finds stays open", closed, [])

    check("every opened cell is justified by one of the two tests", flat_after, 0)
    check("every opened cell draws differently inside", same_both, 0)
    check("no region bigger than a room was opened", oversized, 0)
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
