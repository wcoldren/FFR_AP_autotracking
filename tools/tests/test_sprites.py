"""A map object has to wear the sprite the cartridge says it wears.

Set FF1_ROM to a cartridge; without one this skips rather than passing quietly.
Any Final Fantasy image exercises most of it, and a No-Overworld seed exercises
the rest -- the three floater gates have to come out Orbs and the chime gate a
Robot, which is what MetroidVaniaMap.cs:782-829 assigns them, read back off the
cartridge without either side being transcribed into the other.

The negative cases matter more than the positive ones here. The sprite hunt
went wrong once by sliding an offset until the picture looked plausible, and
the shape of that mistake is that everything still renders. So the perturbed
cases below check that a base one page out and a palette region one quarter out
are actually rejected, rather than trusting that they would be.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import entrance_graph as eg                                    # noqa: E402
import render_maps                                             # noqa: E402
import sprites                                                 # noqa: E402

# MetroidVaniaMap.cs:782-829. Only on a No-Overworld cartridge.
NOOW_SPRITES = {0x22: "Orb", 0xC1: "Orb", 0xC5: "Orb", 0xB0: "Robot"}


def quiet(fn, *args):
    """Run something that prints, and give back just whether it passed."""
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args)


def main():
    path = os.environ.get("FF1_ROM")
    if not path or not os.path.exists(path):
        print("SKIP  set FF1_ROM to a Final Fantasy cartridge to run this")
        return 0

    with open(path, "rb") as f:
        rom = f.read()
    graph = eg.Graph(eg.Rom.of(rom, path))
    ids = sprites.sprite_ids(rom)
    noow = graph.gates is not None
    print(f"({'a real No-Overworld seed' if noow else 'not a No-Overworld seed'})")
    fails = []

    def check(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")
        print(f"{'ok  ' if got == want else 'FAIL'} {label}")

    check("the cartridge's own invariants hold",
          quiet(sprites.self_check, rom, graph), True)

    # The base is pinned by three engine constants meeting, so a slid base has
    # to break at least one of them. Restated here rather than left to the
    # import-time asserts, because the point is that they have teeth.
    for delta in (-1, 1):
        base = sprites.MAPOBJ_CHR + delta * sprites.SPRITE_BYTES
        n, pages = len(sprites.SPRITE_NAMES), len(sprites.CLASS_NAMES)
        meets = (sprites.MAPMAN_CHR
                 + (pages + sprites.OW_OBJECT_PAGES) * sprites.SPRITE_BYTES == base
                 and base + n * sprites.SPRITE_BYTES == sprites.BANK_WINDOW[1])
        check(f"a base {delta:+d} page from ${sprites.MAPOBJ_CHR:04X} does not fit "
              "the bank", meets, False)

    # Palettes 0-1 are the player's and identical on every map; 2-3 are the
    # objects' and are not. Read the block a quarter out either way and that
    # distinction inverts or collapses, so the check has to reject it.
    real = sprites.PALETTE_SPRITE
    for off in (0x00, 0x08, 0x20):
        sprites.PALETTE_SPRITE = off
        check(f"the palette region at +${off:02X} is rejected",
              quiet(sprites.self_check, rom, graph), False)
    sprites.PALETTE_SPRITE = real
    check("and +$10 is still accepted afterwards",
          quiet(sprites.self_check, rom, graph), True)

    # Every graphic id a map actually uses names a sprite; unnamed ones exist
    # (see chr_page) but no stock or No-Overworld cartridge places them.
    placed = {oid for m in range(render_maps.MAP_COUNT)
              for oid, _, _ in graph.objects(m)}
    check("every placed object wears one of the 30 named sprites",
          sorted({ids[o] for o in placed if ids[o] >= len(sprites.SPRITE_NAMES)}),
          [])

    # The out-of-enum ids FFR really does set have to resolve, not crash: $F4
    # is the Knight's mapman and $EE-$F9 are the twelve classes in order.
    check("graphic $F4 is the Knight's mapman (MIAB.cs:451)",
          sprites.sprite_name(0xF4), "KnightMapman")
    check("graphics $EE-$F9 are the twelve classes (Party.cs:581)",
          [sprites.sprite_name(g) for g in range(0xEE, 0xFA)],
          [c + "Mapman" for c in sprites.CLASS_NAMES])
    check("and $F4's art is readable",
          sprites.sprite_pixels(rom, 0xF4) is not None, True)

    if noow:
        check("the No-Overworld gate NPCs wear the sprites FFR gives them",
              {o: sprites.sprite_name(ids[o]) for o in NOOW_SPRITES}, NOOW_SPRITES)
        check("every gate NPC has art",
              [o for o in graph.gates if sprites.sprite_pixels(rom, ids[o]) is None],
              [])

    # And the drawing lands where the object stands. Render one map with and
    # without objects: the tiles differing have to be exactly the tiles the
    # objects occupy, give or take a sprite that happens to match the floor.
    busy = max(range(render_maps.MAP_COUNT), key=lambda m: len(graph.objects(m)))
    side, _, plain = render_maps.render(rom, busy)
    _, _, drawn = render_maps.render(rom, busy, graph=graph)
    moved = {(i // 3 % side // render_maps.TILE_PX,
              i // 3 // side // render_maps.TILE_PX)
             for i in range(len(plain)) if plain[i] != drawn[i]}
    stand = {(x, y) for _, x, y in graph.objects(busy)}
    check(f"objects on map {busy} draw only on their own tiles",
          moved - stand, set())
    check(f"and every object on map {busy} draws something",
          len(moved), len(stand))

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
