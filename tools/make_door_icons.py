#!/usr/bin/env python3
"""Write the two door icons the entrance tooltips use.

    python3 tools/make_door_icons.py <a cartridge>
    python3 tools/make_door_icons.py <a cartridge> --check

An entrance pin's marker is a shape and a state colour and nothing else --
`mapwidget.cpp:352` paints a diamond, a trapezoid or a rect and has no path to
an image -- so the only picture a pin can carry is the tooltip's, which is
`chest_unopened_img` / `chest_opened_img`. Set neither and PopTracker draws its
built-in chest, which is what an entrance was showing.

**These are committed rather than written by a regen, and `Pack::hasFile` is
why.** `regen_maps.py` writes into the user-override, and `Pack::ReadFile`
consults it -- but `MakeLocationIcon` asks `hasFile` first
(`maptooltip.cpp:214`) and `Pack::hasFile` (`pack.cpp:200`) looks only in the
zip or the pack directory. A file that exists only in the override fails that
test and falls back to the chest, silently, with the override in place and
every other overridden file being served. So a section image has to be in the
pack.

That is allowed, and it is the one kind of cartridge art that is: `README.md`
says whole maps stay out of git but "single sprites are a deliberate exception
... icons made that way may ship here". These are the first. The door is not
rolled per seed -- it is vanilla tile art, the same on every cartridge -- so
committing it costs a reader nothing and spares them a regen to see a door.

The tile is found by its own property rather than by an id: the first tile any
drawn map calls `TP_SPEC_LOCKED`, the door the Mystic Key opens
(`bank_0F.asm:3470`). It comes out $3B in every tileset that has one on all four
measured cartridges, with Coneria Castle always the first map to carry one, but
reading the property is what makes that a measurement instead of two numbers
typed in here.

**The shut state is dimmed rather than drawn.** A locked door and an unlocked
one are the same tile in this game, which is the cartridge's answer and not a
corner cut, so there is no second sprite to lift. The transform is not a number
picked by eye either: `settings.json` sets `disabled_image_filter` to
`grayscale, dim`, so every other off image in this pack is an average greyscale
at half brightness (`imagefilter.cpp:66-81`). The same is baked in here, because
a section image is a raw path and img_mods are not applied to one
(`maptooltip.cpp:228`, "TODO: +img_mods") -- PopTracker will not do it for us.
Baking the pack's own filter means an unvisited door looks like every other
thing this pack draws as not-yet.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import entrance_graph  # noqa: E402
import overworld_pins  # noqa: E402
import regen_maps  # noqa: E402
import render_maps  # noqa: E402

# The tooltip scales what it is handed, so this is only about having pixels to
# scale from. Four is the largest whole multiple that still reads as the NES
# tile it is rather than as a blur.
SCALE = 4


def locked_tile(rom, graph):
    """(map_id, tile id) of the first locked door any drawn map carries."""
    for map_id in sorted(render_maps.MAP_FILES):
        tiles, props, _ = graph.grid(map_id)
        for pos, byte in enumerate(props):
            if byte & entrance_graph.TP_SPEC_MASK == entrance_graph.TP_SPEC_LOCKED:
                return map_id, tiles[pos]
    return None


def icons(rom, graph):
    """{pack path: PNG bytes} -- the open door and the shut one."""
    found = locked_tile(rom, graph)
    if found is None:
        return None
    map_id, tile = found
    # The inside palette: a door is something you are standing indoors to look
    # at, and the outdoor one paints this tile in the roof colours.
    art = render_maps.tileset_art(
        rom, rom[render_maps.TILESET_LUT + map_id],
        render_maps.map_palettes(rom, map_id, True))[tile]
    shut = [[_disabled(px) for px in row] for row in art]
    return {overworld_pins.DOOR_OPEN_IMG: _png(art),
            overworld_pins.DOOR_SHUT_IMG: _png(shut)}


def _disabled(px):
    """`grayscale, dim` -- what this pack's settings.json does to an off image."""
    grey = sum(px) // 3
    return (grey // 2,) * 3


def _png(block):
    """A 16x16 block of (r, g, b) as a PNG, SCALE times bigger."""
    out = bytearray()
    for row in block:
        line = bytearray()
        for px in row:
            line += bytes(px) * SCALE
        out += line * SCALE
    return regen_maps.encode(len(block) * SCALE, len(block) * SCALE, bytes(out))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    check = "--check" in sys.argv[1:]
    if len(args) != 1:
        print(__doc__.strip().splitlines()[0])
        print("\nusage: make_door_icons.py <a cartridge> [--check]")
        return 2
    rom = open(args[0], "rb").read()
    built = icons(rom, entrance_graph.Graph(entrance_graph.Rom(args[0])))
    if built is None:
        print("FAILED: no map on this cartridge has a locked door, so there is "
              "no door tile to draw.")
        return 1
    stale = []
    for rel, data in sorted(built.items()):
        path = os.path.join(PACK, rel)
        have = open(path, "rb").read() if os.path.exists(path) else None
        if have == data:
            continue
        stale.append(rel)
        if not check:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
    if check:
        if stale:
            print("FAILED: not what this writer draws: " + ", ".join(stale))
            return 1
        print(f"the {len(built)} door icons are what this writer draws")
        return 0
    print(f"wrote {len(stale)} of {len(built)} door icons"
          + (": " + ", ".join(stale) if stale else " (all current)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
