#!/usr/bin/env python3
"""Draw the chest-slot icons for the Locations grid, and the Titan's own cell.

    python3 tools/make_slot_icons.py <a cartridge>
    python3 tools/make_slot_icons.py <a cartridge> --check

Rows 3 and 4 of `shared_locations_grid` (`layouts/shared.json`) are the eleven
incentive slots that are a *chest*, and until this was written nine of them
were drawn as the creature you meet near the chest -- the Vampire for the Earth
Cave, a mermaid for the Sea Shrine, the Titan himself for his Trove. Rows 1 and
2 are the slots that are a person, drawn as that person. So the grid already
made the split and the pictures were the one thing out of step with it: a
player reading row 3 was told to look for people. `docs/IDEAS.md`, "The icon
half is a separate change", is the design this implements.

Each icon is the creature or key the cell already showed, with a chest badge
in its bottom-right corner saying what the cell is:

    figure  at twice its size, filling the 32-pixel cell:
              the seven plain dungeons   the creature the cell used to be,
                                         which is the mark a player already
                                         reads as that place
              the two locked slots       the Mystic Key
              Titan's Trove, Cardia      the Titan and Bahamut, lifted off the
                                         cartridge the way the pins' sprites
                                         are
    badge   the chest tile off the slot's own floor, drawn in that floor's
            inside palette, at its own 16-pixel size

**Which is on top was decided by looking, not by the design.** `docs/IDEAS.md`
asked for a chest carrying the area's mark, and that was drawn first: the
chest at 2x with the figure at 1x in its corner. It read as a row of chests,
which is what it was for, and it read as a row of *identical* chests the
moment the cells were greyed -- and greyed is a hosted toggle's resting state,
since a slot is dim until its check clears. Eleven same-shaped cells whose
only difference is a half-brightness corner smudge is a board nobody can read
at a glance. The other way round keeps the silhouettes a player already tells
apart, in both states, and the chest badge does the one job the design
wanted: it says this is a chest. It is also the composition the pack already
ships for Cardia (`cardiaIncentive.png`, Bahamut beside two chests), so it is
closer to the pack's own vocabulary rather than farther. The first cut is in
`STATUS-2.md` with the preview that decided it.

**The badge comes off the cartridge and is the same on every one.** A chest is
a map tile whose property byte says `TP_SPEC_TREASURE`; every such tile in a
tileset draws the same art and differs only in which treasure it opens, so the
first one found on the floor is the floor's chest. It is drawn in the *inside*
palette because a chest is always a room cell -- outdoors the same tile is the
roof slab the room hides under, on every floor measured, and nobody has seen a
chest look like that. The tile is vanilla art, byte-identical across every
cartridge this was run on, which is what lets it be committed rather than
regenerated (`README.md`, the single-sprite exception the door icons already
use). The tile's index-0 pixels -- the room floor -- are left transparent, so
the badge sits on the figure rather than in a black box.

**The figures are read, not redrawn.** The seven creature icons are inherited
2x pixel art (every one an exact nearest-neighbour double in colour: measured,
zero non-uniform 2x2 blocks across all seven), so they are read back to 1x
losslessly and redrawn at 2x, and they become the inputs to this writer rather
than icons of their own. The key is `images/items/key.png`, the same way. The
Titan and Bahamut come off the cartridge through `sprites.sprite_rgb`, in the
sprite palette of the map each stands on. The Titan's own cell in row 2 is
rewritten from the same lift with no badge: the `titan.png` it replaces was
the one location icon on the board that was not pixel art at all -- 303
colours, a filtered upscale -- and it was also serving as the Trove's picture,
which is the duplicate this change removes. The Trove is now the Titan with a
chest at his feet, and the row above him is the Titan alone.

What this deliberately does not touch: `earth.png` stays, because it is the
Vampire and the Bosses row is where a Vampire belongs; `shopItem.png` stays,
because that slot is a shop rather than a chest and the design says so; and
the `*IsIncentive` flags follow their slots, so a flag and the slot it speaks
for keep wearing one picture.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import entrance_graph  # noqa: E402
import extract_npcs  # noqa: E402
import pngio  # noqa: E402
import regen_maps  # noqa: E402
import render_maps  # noqa: E402
import sprites  # noqa: E402

TILE = render_maps.TILE_PX          # 16: a map tile, and a map-object sprite
SCALE = 2                           # the cell is 32; a figure at 2x fills it
SIZE = TILE * SCALE

OUT_DIR = "images/locations"
TITAN_IMG = OUT_DIR + "/titan.png"

# slot code -> (the map whose chest tile is the badge, the figure).
# A figure is ("png", pack path) for an inherited 2x icon, or ("npc", code)
# for a map object lifted off the cartridge. The map is the first floor of
# that dungeon carrying a chest on every cartridge, which is not always its
# first floor: Marsh Cave B1, Castle of Ordeals 1F and Gurgu Volcano B1 have
# none. Cardia's badge is Cardia's own chest rather than Bahamut's Cave's,
# because that cave has chests only on a seed that rolled `MapDragonsHoard`
# and the oracle cartridges refused it. Ids are `render_maps.MAP_FILES`.
SLOTS = {
    "marsh":           (27, ("png", "images/locations/marsh.png")),
    "marshLocked":     (27, ("png", "images/items/key.png")),
    "coneriaLocked":   (8,  ("png", "images/items/key.png")),
    "iceCave":         (15, ("png", "images/locations/iceCave.png")),
    "ordeals":         (25, ("png", "images/locations/ordeals.png")),
    "titansTrove":     (60, ("npc", "titan")),
    "cardiaIncentive": (16, ("npc", "bahamut")),
    "earth":           (13, ("png", "images/locations/earth.png")),
    "volcano":         (33, ("png", "images/locations/redD.png")),
    "sea":             (46, ("png", "images/locations/seaShrine.png")),
    "sky":             (47, ("png", "images/locations/skyPalace.png")),
}


def slot_img(code):
    """The pack path an item points at for one slot."""
    return f"{OUT_DIR}/chest_{code}.png"


def chest_tile(rom, graph, map_id):
    """The floor's chest as a 16x16 block of (r, g, b) or None.

    The tile is found by its property rather than by an id, the way the door
    icon finds the locked door: the first tile the floor calls
    `TP_SPEC_TREASURE`. Drawn by hand here rather than through
    `render_maps.tileset_art` because that resolves every pixel to a colour and
    this needs to know which ones are index 0, the room floor, to leave
    transparent.
    """
    tiles, props, _ = graph.grid(map_id)
    tile = next((tiles[p] for p, byte in enumerate(props)
                 if byte & entrance_graph.TP_SPEC_MASK
                 == entrance_graph.TP_SPEC_TREASURE), None)
    if tile is None:
        return None
    tileset = rom[render_maps.TILESET_LUT + map_id]
    palettes = render_maps.map_palettes(rom, map_id, inside=True)
    attr = rom[render_maps.ATTR_BASE + 0x80 * tileset + tile]
    pal = palettes[attr & 3]
    chr_base = render_maps.CHR_BASE + (tileset << 11)
    block = [[None] * TILE for _ in range(TILE)]
    for n, (ox, oy) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
        quad = rom[render_maps.QUAD_BASE + 0x80 * n + 0x200 * tileset + tile]
        off = chr_base + quad * 16
        for i, v in enumerate(render_maps.decode_ppu(rom[off:off + 16])):
            if v:
                block[oy + (i >> 3)][ox + (i & 7)] = render_maps.NES_PALETTE[pal[v]]
    return block


def halved(path):
    """A 2x RGBA icon back at 1x, as rows of (r, g, b) or None.

    Every source is an exact nearest-neighbour double in colour, so the
    top-left pixel of each 2x2 block is the whole block; a source that is not
    would come out subtly wrong, and `self_check` refuses one. Alpha is read
    off the same pixel. One source is not a double in alpha: `earth.png`
    carries a stray opaque black sliver two pixels wide and one high at its
    left edge on row 10, over a transparent row 11. Reading the top-left pixel
    keeps it as one black pixel on the Vampire's edge at 1x, which is what the
    2x icon shows too, and the check below looks at colour so that one stray
    does not read as the art being wrong.
    """
    w, h, rgba = pngio.read_rgba(os.path.join(PACK, path))
    out = []
    for y in range(0, h - 1, 2):
        row = []
        for x in range(0, w - 1, 2):
            i = (y * w + x) * 4
            row.append(None if rgba[i + 3] < 128 else tuple(rgba[i:i + 3]))
        out.append(row)
    return out


def is_doubled(path):
    """Whether every 2x2 block of the icon is one colour where it is opaque."""
    w, h, rgba = pngio.read_rgba(os.path.join(PACK, path))

    def px(x, y):
        i = (y * w + x) * 4
        return None if rgba[i + 3] < 128 else bytes(rgba[i:i + 3])
    for y in range(0, h - 1, 2):
        for x in range(0, w - 1, 2):
            seen = {c for c in (px(x, y), px(x + 1, y), px(x, y + 1), px(x + 1, y + 1))
                    if c is not None}
            if len(seen) > 1:
                return False
    return True


def npc_sprite(rom, code):
    """A tracked NPC's sprite at 1x, in the palette of the map he stands on."""
    obj = next(o for o, c in extract_npcs.WANTED.items() if c == code)
    place = extract_npcs.extract(rom)[code][0]
    gfx = sprites.sprite_ids(rom)[obj]
    return sprites.sprite_rgb(rom, gfx, place["map_id"])


def figure(rom, spec):
    """The slot's figure at 1x, as rows of (r, g, b) or None."""
    kind, ref = spec
    return halved(ref) if kind == "png" else npc_sprite(rom, ref)


def compose(fig, badge):
    """The figure at SCALE, centred, with the badge over its bottom-right.

    A figure wider or taller than the cell -- the mermaid is 18 tiles of
    2x art -- is centred and the edge clipped, which is what the inherited
    icon already does in a 32-pixel cell.
    """
    out = bytearray(SIZE * SIZE * 4)

    def put(x, y, rgb):
        if 0 <= x < SIZE and 0 <= y < SIZE:
            i = (y * SIZE + x) * 4
            out[i:i + 3] = bytes(rgb)
            out[i + 3] = 255
    ox = (SIZE - len(fig[0]) * SCALE) // 2
    oy = (SIZE - len(fig) * SCALE) // 2
    for y, row in enumerate(fig):
        for x, rgb in enumerate(row):
            if rgb is not None:
                for dy in range(SCALE):
                    for dx in range(SCALE):
                        put(ox + x * SCALE + dx, oy + y * SCALE + dy, rgb)
    if badge:
        for y, row in enumerate(badge):
            for x, rgb in enumerate(row):
                if rgb is not None:
                    put(SIZE - TILE + x, SIZE - TILE + y, rgb)
    return out


def icons(rom, graph):
    """{pack path: PNG bytes} for every slot, and the Titan's cell."""
    out = {}
    for code, (map_id, spec) in SLOTS.items():
        badge = chest_tile(rom, graph, map_id)
        if badge is None:
            raise ValueError(f"map {map_id} ({render_maps.MAP_FILES[map_id]}) "
                             f"has no chest tile to draw for {code}")
        out[slot_img(code)] = regen_maps.encode_rgba(
            SIZE, SIZE, bytes(compose(figure(rom, spec), badge)))
    out[TITAN_IMG] = regen_maps.encode_rgba(
        SIZE, SIZE, bytes(compose(npc_sprite(rom, "titan"), None)))
    return out


def self_check(rom, graph):
    """What the docstring claims, checked on the cartridge in hand.

    Returns a list of problems; empty is a pass. Three claims: every 2x source
    is an exact double in colour, every slot's floor has a chest, and every
    chest tile on that floor draws the same art -- which is what makes "the
    first one" the floor's chest rather than one of several.
    """
    bad = []
    for code, (map_id, (kind, ref)) in SLOTS.items():
        if kind == "png" and not is_doubled(ref):
            bad.append(f"{ref} is not an exact 2x double; reading it at 1x loses pixels")
        tiles, props, _ = graph.grid(map_id)
        ids = {tiles[p] for p, byte in enumerate(props)
               if byte & entrance_graph.TP_SPEC_MASK == entrance_graph.TP_SPEC_TREASURE}
        if not ids:
            bad.append(f"{code}: map {map_id} carries no chest tile")
            continue
        tileset = rom[render_maps.TILESET_LUT + map_id]
        art = render_maps.tileset_art(
            rom, tileset, render_maps.map_palettes(rom, map_id, inside=True))
        if len({str(art[t]) for t in ids}) != 1:
            bad.append(f"{code}: map {map_id}'s {len(ids)} chest tiles do not all "
                       "draw the same art, so 'the first one' is a choice")
    return bad


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    args = [a for a in argv if not a.startswith("-")]
    check = "--check" in argv
    if len(args) != 1:
        print(__doc__.strip().splitlines()[0])
        print("\nusage: make_slot_icons.py <a cartridge> [--check]")
        return 2
    rom = open(args[0], "rb").read()
    graph = entrance_graph.Graph(entrance_graph.Rom(args[0]))
    problems = self_check(rom, graph)
    if problems:
        for p in problems:
            print("FAILED:", p)
        return 1
    built = icons(rom, graph)
    stale = []
    for rel, data in sorted(built.items()):
        path = os.path.join(PACK, rel)
        have = open(path, "rb").read() if os.path.exists(path) else None
        if have == data:
            continue
        stale.append(rel)
        if not check:
            with open(path, "wb") as fh:
                fh.write(data)
            print("wrote", rel)
    if check:
        for rel in stale:
            print("differs:", rel)
        if stale:
            return 1
        print(f"all {len(built)} icons match")
    elif not stale:
        print(f"all {len(built)} icons already current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
