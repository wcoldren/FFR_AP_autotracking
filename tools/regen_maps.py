#!/usr/bin/env python3
"""Redraw the pack's dungeon maps from your own cartridge, without touching it.

The pack ships DarkmoonEX's hand-drawn maps. They are vanilla maps: right for a
vanilla layout, silent about anything the seed changed. A No-Overworld seed
seals every town's outer wall, stamps 75 new staircases across 34 maps and
builds two rooms inside Coneria Castle, none of which the shipped art has. So
the tabs show the right rooms with the wrong exits.

render_maps.py draws the seed's own maps out of the ROM. What it cannot do on
its own is put them in front of PopTracker, because swapping the art is not a
file copy:

  * every marker is a pixel in one particular image, and the rendered images
    are cropped to what each map uses, so none of the shipped coordinates
    survive the swap;
  * ten of the 61 maps -- the eight towns, Coneria Castle 2F and Bahamut's Lair
    B2 -- have no image in the pack at all, so they have no maps.json entry and
    no tab;
  * and the art is a property of one cartridge. A No-Overworld seed and a
    standard one disagree about 34 to 39 of the 61 maps, so a single set of
    images cannot serve both variants.

This does all of it as one piece, and writes none of it into the repo. Output
goes to PopTracker's user-override tree, which Pack::ReadFile consults ahead of
the pack for every file it loads, images included (pack.cpp:226-243, and
getImage at :445 goes through the same call). So the checkout keeps shipping the
hand-drawn maps, ROM-derived art never lands in git, and removing the override
directory puts everything back.

    tools/regen_maps.py FFR_seed.nes
    tools/regen_maps.py --verify        # is the installed override current?

The cartridge's own GameMode decides which set its art joins -- images/maps/std
or images/maps/nov -- and the two live side by side, each with its own
maps.json index and its own copy of the dungeon location tree. Render one of
each and a standard tracker and a No-Overworld one each show their own maps.
Render neither and the pack's hand-drawn art is still there.

Markers are built forward, from the cartridge's own chest and NPC tiles, rather
than moved from where the hand-drawn art put them. That is what lets a map with
no hand-solved calibration entry carry markers at all -- sixteen maps had none
-- and it means a seed that moves a chest or an NPC moves its marker. On an
ordinary seed the ToFR shuffle puts five chests on a second floor apiece, and
those floors now have pins where they never had any; on a No-Overworld one FFR
moves Nerrick two rows, and his pin goes with him.

An override outlives the checkout that wrote it, and that is the sharp edge
here: PopTracker serves it ahead of the pack, so an edit to
`layouts/shared.json` or a location file has no effect at all until the regen is
re-run, and a layout key the override predates draws an empty group with no
warning anywhere. `--verify` answers that in milliseconds without a cartridge;
`docs/ISSUES.md` has the case that prompted it.

Re-running is cheap: it hashes the ROM and its own inputs, and if nothing moved
it does no work at all. When the ROM does change, only the files whose bytes
actually differ get rewritten -- two seeds of the same mode share most of their
art, and No-Overworld rolls only the Gaia gateway and the Waterfall stairs.

Deliberately not done here: MAP_VALUE still calls maps 0-7 "Overworld", so
maptab.lua will not follow you into a town. The town tabs exist and can be
clicked; auto-switching needs a mode-aware MAP_VALUE, which is a pack change
rather than a per-cartridge one.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import entrance_graph
import extract_chests
import extract_npcs
import make_markers
import pin_visibility
import pngio
import render_maps
import split_locations
import sprites

TILE_PX = render_maps.TILE_PX
CACHE_NAME = ".regen_cache.json"
CACHE_VERSION = 2

# Which set of art a cartridge belongs in. A No-Overworld seed and a standard
# one disagree about 34 to 39 of the 61 maps -- it seals every town's outer wall
# and stamps 75 new staircases -- so one tree of art cannot serve both, and the
# tree used to hold whichever was rendered last whatever variant you opened.
# Two standard seeds still differ on 2 to 7 maps (the Ordeals floor shuffle, the
# ToFR shuffle, Gaia), so this is the dominant axis and not the only one.
MODE_DIRS = {"std": "standard", "nov": "No-Overworld"}

# Everything whose content decides what gets written. A change to any of them
# invalidates the cache the same way a new cartridge does.
INPUT_FILES = [
    "tools/regen_maps.py",
    "tools/render_maps.py",
    "tools/sprites.py",
    "tools/entrance_graph.py",
    "tools/extract_chests.py",
    "tools/extract_npcs.py",
    "tools/make_markers.py",
    "tools/pin_visibility.py",
    "tools/incentive_slots.py",
    "tools/split_locations.py",
    "tools/pngio.py",
    "tools/map_calibration.json",
    "maps/maps.json",
    "layouts/shared.json",
    "locations/overworld.json",
    "locations/NOverworld/overworld.json",
    "locations/incentives.json",
    "locations/NOverworld/incentives.json",
    "maps/NOverworldMaps.json",
    "scripts/autotracking/location_mapping.lua",
]

# Every map this redraws. A marker on one of these needs a calibration entry
# to be moved; a marker on anything else -- the overworld, the incentive sheet --
# sits on art this does not touch.
REDRAWN = set(render_maps.MAP_FILES.values())

# The two maps the pack draws as one composite each. Rendered separately they
# are two images, so the tab that held one now holds both side by side --
# trackerview.cpp:902 docks a tab's maps when there is more than one.
COMPANION_TABS = {
    "Coneria Castle": ["con_castle", "con_castle2F"],
    "Bahamut's Lair": ["bahamut", "bahamutB2"],
}

# No-Overworld turns these into real rooms with chests and stairs. The pack has
# never had art for them, so they get a tab group of their own.
TOWN_TABS = [
    ("Coneria", "coneria_town"), ("Pravoka", "pravoka"),
    ("Elfland", "elfland"), ("Melmond", "melmond"),
    ("Crescent Lake", "crescent_lake"), ("Gaia", "gaia"),
    ("Onrac", "onrac"), ("Lefein", "lefein"),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pack_uid():
    with open(os.path.join(PACK, "manifest.json")) as f:
        return json.load(f)["package_uid"]


def default_out():
    return os.path.join(os.path.expanduser("~"), "PopTracker", "user-override",
                        pack_uid())


def lenient(path):
    """The pack's JSON has trailing commas in places; PopTracker tolerates them."""
    with open(path) as f:
        return json.loads(re.sub(r",(\s*[}\]])", r"\1", f.read()))


def inputs_fingerprint():
    h = hashlib.sha256()
    for rel in INPUT_FILES:
        h.update(rel.encode())
        with open(os.path.join(PACK, rel), "rb") as f:
            h.update(f.read())
    return h.hexdigest()


# ---------------------------------------------------------------- calibration

def crops(rom):
    """{map name: render_maps.Crop} -- what each rendered image covers.

    Cropping is what turns a tab from a postage stamp in an empty field into
    the map: a mean 48% of the grid survives, and Mirage Tower 1F goes from a
    33x33 corner of 64x64 to filling its frame. See render_maps.content_crop
    for where the box comes from, why the hand-drawn art is what says it is
    right, and what the slide on a map drawn across the join is for.
    """
    return {name: render_maps.content_crop(render_maps.map_tiles(rom, map_id))
            for map_id, name in render_maps.MAP_FILES.items()}


def legend_rows(rom, crops_=None):
    """{map name: rows of backdrop reserved below it for a Map Key}."""
    marks = render_maps.trap_marks(rom)
    out = {}
    for map_id, name in render_maps.MAP_FILES.items():
        used = render_maps.map_trap_marks(
            rom, map_id, render_maps.map_tiles(rom, map_id), marks)
        out[name] = render_maps.legend_rows_for(len(set(used.values())))
    return out


def _axis_regions(shift, origin, span):
    """[(lo, hi, offset)] -- one piece per straight run of a shifted axis.

    `region_for` picks a region by tile coordinate and the marker is then a
    linear offset from it, so an axis the grid slid on needs one region per
    piece: tile `n` draws at `((n + shift) mod 64 - origin) * span`, which is
    two straight lines with the join between them. Unshifted it is one line and
    one unbounded region, which is what every map had before and what all but
    the handful drawn across the join still get.
    """
    if not shift:
        return [(None, None, -origin * span)]
    return [(0, render_maps.MAP_DIM - 1 - shift, (shift - origin) * span),
            (render_maps.MAP_DIM - shift, render_maps.MAP_DIM - 1,
             (shift - render_maps.MAP_DIM - origin) * span)]


def rendered_calibration(rom, crops_):
    """The calibration the rendered art needs, as a map_calibration.json.

    Uncropped this was nothing at all -- every image 64 tiles at TILE_PX, tile
    n at pixel TILE_PX * n. Cropped it is one number per axis per map: the box
    the render starts at. Still derived rather than eyeballed, which is the
    difference that matters -- the hand-solved offsets in
    tools/map_calibration.json are what a marker can drift away from.

    It is no longer always one region. A map drawn across the grid's join is
    boxed after a slide (render_maps.content_crop), and the slide is a jump
    rather than an offset, so such a map comes back as two regions per slid
    axis -- four if it slid on both, which none of the measured cartridges do.
    That is the whole cost of the rotation on this side: the file format
    already carried per-region `cols` and `rows` bounds and nothing else
    changes. Maps that did not slide are emitted exactly as they were, one
    unbounded region, so their markers do not move.

    The Map Key band hangs below the map, so it does not enter here.
    """
    out = {}
    for map_id, name in render_maps.MAP_FILES.items():
        crop = crops_[name]
        (c0, _, r0, _), (sx, sy) = crop.box, crop.shift
        regions = []
        for clo, chi, ox in _axis_regions(sx, c0, TILE_PX):
            for rlo, rhi, oy in _axis_regions(sy, r0, TILE_PX):
                region = {"offset_x": ox, "offset_y": oy}
                if clo is not None:
                    region["cols"] = [clo, chi]
                if rlo is not None:
                    region["rows"] = [rlo, rhi]
                regions.append(region)
        out[name] = {"rom_map_id": map_id, "tile_px": TILE_PX,
                     "regions": regions}
    return out


# ------------------------------------------------------------------- contents

def mode_of(rom, path, override=None):
    """'std' or 'nov' -- which set of art this cartridge belongs in.

    Read from the cartridge's own GameMode rather than asked of the user, and
    an answer this does not understand stops the run instead of guessing. The
    cost of guessing is silent: art filed under the wrong mode looks completely
    normal and is wrong about every staircase.

    A vanilla cartridge carries no FFR flag block at all, so it has no mode to
    read; --mode is for that case.
    """
    if override:
        return override
    mode, why = entrance_graph.game_mode(entrance_graph.Rom.of(rom, path))
    if mode == entrance_graph.GAME_MODE_NOVERWORLD:
        return "nov"
    if mode == 0:
        return "std"
    if mode is None:
        sys.exit(f"cannot read this cartridge's GameMode ({why}), so there is "
                 "no way to know which set of art it belongs in. Pass "
                 "--mode std or --mode nov to say.")
    sys.exit(f"GameMode {mode} is neither standard (0) nor No-Overworld "
             f"({entrance_graph.GAME_MODE_NOVERWORLD}); pass --mode to say "
             "which set of art it belongs in.")


def build_images(rom, mode, crops_, rows, graph=None, only=None,
                 marks=None):
    """-> {relpath: (w, h, rgb)} for all 61 maps, rooms drawn open.

    Unroofed, because a tracker map is read rather than walked. In the game a
    room is a white slab until you step through its door; on a map you are
    consulting to decide where to go, that slab is hiding the very thing you
    are looking for -- all six of Coneria Castle 1F's chests sit under one.

    With a graph, the map's NPCs are drawn on the tiles they stand on; `only`
    narrows that to some of them. A sprite is 16x16 on art whose markers are
    placed to the tile, so the two share pixels and PopTracker draws its pins
    on top -- which is the whole trade-off between --npcs gates and --npcs all.

    Drawing them is the default. It was `none`, on the reasoning that a sprite
    under a pin is clutter; looked at on a real regen the opposite is true --
    the townspeople, the orbs and the bats are what make a town read as a town,
    and the pin collision is already handled by emitting a diamond on a sprite
    cell rather than an opaque square. `--npcs none` is still there for anyone
    who wants the bare tiles.
    """
    out = {}
    for map_id, name in render_maps.MAP_FILES.items():
        out[f"images/maps/{mode}/{name}.png"] = render_maps.render(
            rom, map_id, unroof=True, graph=graph, only=only,
            crop=crops_[name], legend_rows=rows[name], marks=marks)
    return out


# A chest occupies exactly one tile, so the marker is sized to a tile -- but to
# the *inside* of one, a pixel short on each edge, and the pixel is the whole
# point. At exactly TILE_PX a box has no gap to the box beside it: Waterfall's
# six chests stand in a row and drew as one green bar with dividers in it
# rather than as six markers, which is the opposite of what a marker is for.
# Dwarf Cave, Coneria Castle, Ordeals 3F and the Sea Shrine all carry runs like
# it. A pixel of the map showing between two boxes is what separates them.
#
# The same pixel separates a box from a trap mark, which since the marks were
# keyed to the formation is one glyph filling one tile. Outline and glyph
# touching at the tile edge read as one object.
#
# The old rationale for TILE_PX was that the box should outline the chest's
# tile "and nothing more". That still holds and is what rules out going
# further: rendered at 12, the border cuts into the chest sprite it is meant to
# be outlining. 14 is one tile less a pixel a side -- the smallest change that
# buys the gap, and the largest that still leaves the chest whole.
#
# The pack's own 24 comes from the hand-drawn art, where it reads fine because
# those images are shown at roughly their drawn size; cropped renders are a
# third of the area they were, so PopTracker scales them up and a box scales
# with them. Same fraction of a tile, twice the pixels on screen.
MARKER_SIZE = render_maps.TILE_PX - 2
MARKER_BORDER = 2


def build_maps_json(have, size=MARKER_SIZE, border=MARKER_BORDER):
    """The pack's maps.json, pointed at the standard set of rendered art.

    The overworld and incentive entries keep the pack's own art and sizes --
    this changes the dungeon maps and nothing else. location_size is in image
    pixels and a tile is still 16 of them however the image is cropped, so one
    size still fits all of them.

    With no standard set rendered yet, the pack's own hand-drawn art is left
    exactly where it is and no new names are added: a tab pointing at an image
    that is not there is worse than no tab.
    """
    entries = lenient(os.path.join(PACK, "maps", "maps.json"))
    if "std" not in have:
        return entries
    by_name = {e["name"]: e for e in entries}
    order = [e["name"] for e in entries]
    for name in render_maps.MAP_FILES.values():
        e = by_name.setdefault(name, {"name": name})
        if name not in order:
            order.append(name)
        e["img"] = f"images/maps/std/{name}.png"
        e["location_size"] = size
        e["location_border_thickness"] = border
    return [by_name[n] for n in order]


def build_noverworld_maps_json(have, size=MARKER_SIZE, border=MARKER_BORDER):
    """NOverworldMaps.json, which the No-Overworld variants load second.

    scripts/init.lua loads maps.json and then this, and PopTracker lets the
    later entry win -- which is how one "incentives" row already swaps the
    overworld art for those two variants. The same mechanism at full size gives
    them their own 61 dungeon maps, so a No-Overworld seed's extra staircases
    stop appearing on a standard tracker and the reverse.

    When no No-Overworld set has been rendered, this puts back the pack's own
    hand-drawn art for every map that has some, rather than leaving those
    variants looking at the standard cartridge's art. The nine maps the pack
    has no art for -- the towns, Coneria Castle 2F, Bahamut's Lair B2 -- have
    nothing to put back, so they keep whatever maps.json gave them.
    """
    entries = lenient(os.path.join(PACK, "maps", "NOverworldMaps.json"))
    by_name = {e["name"]: e for e in entries}
    order = [e["name"] for e in entries]
    shipped = {e["name"]: e for e in lenient(os.path.join(PACK, "maps", "maps.json"))}
    for name in render_maps.MAP_FILES.values():
        if "nov" not in have and name not in shipped:
            continue
        e = by_name.setdefault(name, {"name": name})
        if name not in order:
            order.append(name)
        e["img"] = (f"images/maps/nov/{name}.png" if "nov" in have
                    else shipped[name]["img"])
        # Hand-drawn art keeps the size it was drawn for; only rendered art is
        # scaled up by the crop.
        e["location_size"] = size if "nov" in have else 24
        e["location_border_thickness"] = border if "nov" in have else 3
    return [by_name[n] for n in order]


def stands_on_map(rom, map_id, col, row, cache=None):
    """Is (col, row) somewhere the player can be, rather than backdrop?

    The same flood content_crop crops by: a cell the edge flood reaches is the
    filler around the map, not the map. Objects are not all placed inside it.
    The Ice Cave B1 fairy stands at (47,30) on a cell the flood reaches -- a
    leftover copy of the Gaia object in the black outside the cave, which the
    renderer draws (and the crop keeps in frame) but which no party can walk
    up to. A marker there would be a pin in the void.

    One NPC placement out of the fifteen the pack tracks fails this, and it is
    that one; the other fourteen are all inside their map's content. The NPCs
    are only where the evidence comes from, though -- marker_tiles asks this of
    every placement it resolves, chests included, which is why marker_tiles
    reports what it dropped rather than just dropping it.

    `cache` is {map_id: outside cells}, passed in rather than kept here: the
    answer is a property of one cartridge, and a cache that outlived the `rom`
    it was flooded from would answer the next one's questions with the last
    one's map.
    """
    if cache is None:
        cache = {}
    if map_id not in cache:
        tiles = render_maps.map_tiles(rom, map_id)
        tile, _ = render_maps.backdrop_tile(tiles)
        cache[map_id] = render_maps.outside_cells(tiles, tile)
    return (col, row) not in cache[map_id]


def marker_tiles(rom, locations, dropped=None):
    """{location name: [(map_id, col, row)]} for every marker on a dungeon map.

    Forward, out of the cartridge, rather than by inverting the pixel the
    hand-drawn art happened to put a marker at. That inversion is what made
    tools/map_calibration.json a dependency of redrawing at all, and with it
    the two things that have blocked this work: the sixteen maps nobody ever
    solved an offset for, and the composites whose image holds a different set
    of tiles than the rom_map_id on its entry names. Neither can matter to a
    marker whose position was never a pixel in the first place.

    Chests join through scripts/autotracking/location_mapping.lua, which names
    an AP id for every location in the multiworld pool; the chest index is
    id - 256 (FF1Lib/Items.cs). All 254 dungeon chest markers in the shipped
    tree resolve through it and every one agrees with
    tools/marker_positions.json, which is what says the join is the right one.

    NPCs join through `hosted_item` in the location tree instead, because the
    AP pool is not the whole board. Several of the NPCs the cartridge places
    carry no shuffled item and so have no AP id at all -- Bahamut is one -- and
    reading the tree covers every NPC the pack actually tracks rather than only
    the ones Archipelago knows about. The codes are extract_npcs.WANTED's
    values, and location_mapping.lua's third field is that code too, so this is
    the same join by a wider door.

    Both kinds of tile come from the cartridge, so a seed that moves one moves
    its marker with it. This used to read NPC tiles out of npc_positions.json
    on the grounds that FFR randomizes what an NPC gives you and not where it
    stands. Measured 2026-08-30, that is false -- MetroidVaniaMap.cs moves
    people, titan by (60,8,7) -> (60,4,8) on an ordinary seed and nerrick by
    (19,16,45) -> (19,15,47) on a No-Overworld one -- so a No-Overworld regen
    drew Nerrick's pin two rows off the sprite it marks. noverworld_rules
    .placements() stopped reading that file first; this is the pin half.

    npc_positions.json survives as the vanilla snapshot tests/test_maps.lua
    reads, because Lua has no cartridge: it reproduces the three shipped
    hand-art pins and the three map_calibration.json entries derived from a
    fiend's tile, on floors that hold no chest to calibrate from.

    `dropped`, if given, collects (name, kind, map_id, col, row) for every
    placement stands_on_map rejected. Filtering silently would be a marker that
    quietly disappears, which place_locations already refuses to do: a node
    resolving to several tiles -- the Marsh Cave and ToFR floors, Ordeals
    Chests 2 -- stays placeable after losing one, so the loss reaches nothing
    downstream that could notice it. The caller decides what to make of each
    kind; today exactly one NPC placement is rejected and no chest is.
    """
    ids = split_locations.load_mapping(limit=512)
    chests, _ = extract_chests.extract(rom)
    npcs = extract_npcs.extract(rom)

    out = {}
    outside = {}

    def add(name, kind, places):
        for q in places:
            cell = (q["map_id"], q["tile_col"], q["tile_row"])
            if stands_on_map(rom, *cell, cache=outside):
                out.setdefault(name, []).append(cell)
            elif dropped is not None:
                dropped.append((name, kind) + cell)

    for ap, (path, _) in sorted(ids.items()):
        places = chests.get(ap - 256)
        if places:
            add(split_locations.leaf_of(path), "chest", places)

    def walk(nodes):
        for n in nodes:
            if not isinstance(n, dict):
                continue
            for sec in n.get("sections") or []:
                places = npcs.get(sec.get("hosted_item"))
                if places:
                    add(n.get("name"), "NPC", places)
            walk(n.get("children") or [])

    walk(lenient(os.path.join(PACK, locations)))
    return {k: v for k, v in out.items() if v}


def place_locations(cal, tiles_by_name, path, sprite_cells=None):
    """-> (new document, placed, unmoved, unplaceable, shaded).

    Every marker on a map this redraws is rebuilt from the tile its chest or
    NPC actually sits on. Markers on the overworld and the incentive sheet are
    left exactly as they are: that art does not change.

    A location that carries a dungeon marker and resolves to no tile cannot be
    placed and is reported rather than dropped -- a marker that quietly
    disappears is worse than one that stops the run.

    A location that resolves to a tile and carries *no* dungeon marker gets one
    built. That is not a rebuild but a gain, and it is where the tracked NPCs
    live: the pack put Astos, Matoya, Bikke, the Fairy and Bahamut on the
    overworld pin of the town or cave that holds them and never on the tab for
    the map itself, so five NPCs the cartridge places to the tile had no pin
    standing on them. Only three did -- Nerrick, the Smith and Sarda -- which
    is why only three pins ever came out as diamonds. Nothing here decides
    which nodes those are: a node gains a marker exactly when the cartridge
    resolves it to a tile. The incentive sheet, whose pins live on one
    hand-drawn image rather than on a map, is handed no tiles at all and so
    passes through untouched -- see the call site for why that is done by
    handing it nothing rather than by trusting that none of its names collide.

    `sprite_cells` is {map_id: {(col, row)}} for the tiles --npcs draws a
    sprite on. A pin landing on one is emitted as a diamond and reported as
    `shaded`, because PopTracker's rect pin is opaque and exactly one tile:
    drawRect fills its interior with a solid state colour (uilib/drawhelper.c
    :15-56, and StateColors carry no alpha), so a square pin hides the whole
    sprite it sits on. A diamond of the same size leaves the tile's four
    corners unpainted, which is what lets the sprite read behind the pin.
    Sized and centred exactly as before, so the pin still marks its own tile.
    """
    doc = lenient(os.path.join(PACK, path))
    by_rom = {}
    for name, entry in cal.items():
        by_rom.setdefault(entry["rom_map_id"], []).append((name, entry))
    placed = unmoved = 0
    unplaceable = []
    shaded = []

    def pixels(map_id, col, row):
        for name, entry in by_rom.get(map_id, []):
            region = make_markers.region_for(entry, col, row)
            if region is None:
                continue
            half = entry["tile_px"] // 2
            ml = {"map": name,
                  "x": region["offset_x"] + col * entry["tile_px"] + half,
                  "y": region["offset_y"] + row * entry["tile_px"] + half}
            if (col, row) in (sprite_cells or {}).get(map_id, ()):
                ml["shape"] = "diamond"
            return ml
        return None

    def walk(nodes):
        nonlocal placed, unmoved
        for n in nodes:
            if not isinstance(n, dict):
                continue
            name = n.get("name")
            marks = n.get("map_locations") or []
            keep = [ml for ml in marks if ml.get("map") not in REDRAWN]
            unmoved += len(keep)
            tiles = tiles_by_name.get(name, ())
            if tiles or len(keep) != len(marks):
                fresh = [pixels(*t) for t in tiles]
                if not fresh or None in fresh:
                    stale = marks[0] if marks else {}
                    unplaceable.append((name, stale.get("map"),
                                        stale.get("x"), stale.get("y")))
                else:
                    n["map_locations"] = keep + fresh
                    placed += len(fresh)
                    shaded.extend((name, ml["map"]) for ml in fresh
                                  if ml.get("shape") == "diamond")
            walk(n.get("children") or [])

    walk(doc)
    return doc, placed, unmoved, unplaceable, shaded


def map_block(content):
    """A tab's {"type": "map"} block, or None.

    shared.json writes some tabs' content bare and some wrapped in a list --
    every top-level tab uses the list form, and the nested ones a bare dict --
    so anything reaching for a tab's maps has to take both.
    """
    if isinstance(content, dict):
        return content if content.get("type") == "map" else None
    if isinstance(content, list):
        for v in content:
            if isinstance(v, dict) and v.get("type") == "map":
                return v
    return None


def build_layouts():
    """shared.json with the ten maps the pack has no tab for."""
    doc = lenient(os.path.join(PACK, "layouts", "shared.json"))
    docked = set()

    def retitle(node):
        """Give the two composite tabs their second floor."""
        if not isinstance(node, (dict, list)):
            return
        if isinstance(node, list):
            for v in node:
                retitle(v)
            return
        for tab in node.get("tabs") or []:
            maps = COMPANION_TABS.get(tab.get("title"))
            block = map_block(tab.get("content")) if maps else None
            if block is not None:
                block["maps"] = list(maps)
                docked.add(tab["title"])
            retitle(tab.get("content"))
        for v in node.values():
            retitle(v)

    retitle(doc)
    missing = sorted(set(COMPANION_TABS) - docked)
    if missing:
        # Failing quietly here is what left con_castle2F rendered, registered in
        # maps.json and reachable from no tab at all, so this is fatal.
        sys.exit("no map tab in layouts/shared.json for: " + ", ".join(missing))
    towns = {
        "title": "Towns",
        "content": {
            "type": "tabbed",
            "tabs": [{"title": t, "content": {"type": "map", "maps": [m]}}
                     for t, m in TOWN_TABS],
        },
    }
    tabs = doc["shared_other_tabs"]["tabs"]
    doc["shared_other_tabs"]["tabs"] = [t for t in tabs
                                        if t.get("title") != "Towns"] + [towns]
    return doc


# ---------------------------------------------------------------------- cache

def load_cache(out_dir):
    """-> (cache for this version or None, cache from an older version or None).

    An override written by an older version of this tool is not just useless,
    it is actively wrong: its files sit at paths nothing here writes any more,
    so nothing overwrites them and PopTracker goes on reading them. The v1
    layout put all 61 images at images/maps/<name>.png and had no
    locations/NOverworld/overworld.json at all, so after the split the
    No-Overworld variants fell back to the pack's own hand-art coordinates and
    drew every box off its chest. Returning the old cache is what lets those
    files be cleared rather than left behind.
    """
    try:
        with open(os.path.join(out_dir, CACHE_NAME)) as f:
            cache = json.load(f)
    except (OSError, ValueError):
        return None, None
    if cache.get("version") == CACHE_VERSION:
        return cache, None
    return None, cache


def outputs_intact(out_dir, cache):
    """Every file the last run wrote is still there with the bytes it wrote.

    Without this, deleting an image by hand would leave a cache saying the work
    was already done, and the tab would come up blank with nothing to say why.
    """
    for rel, want in cache.get("outputs", {}).items():
        try:
            with open(os.path.join(out_dir, rel), "rb") as f:
                if sha(f.read()) != want:
                    return False
        except OSError:
            return False
    return True


def verify(out_dir):
    """-> 0 if the installed override still matches this checkout, 1 if not.

    The half of the stale-override problem that fails quietly is the layout
    one. `Pack::ReadFile` serves the override ahead of the checkout, and
    `Tracker::getLayout` answers an unknown key with `blankLayoutNode`
    (tracker.cpp:791-794) and no warning -- so a `{"type": "layout", "key":
    ...}` added to the repo while an older override is installed renders an
    empty group. Nothing in the tracker says a word. Adding
    `shared_display_grid` to layouts/shared.json did exactly that on
    2026-08-30.

    The comparison it needs was already sitting in the cache: `inputs` is a
    sha256 over INPUT_FILES, which lists layouts/shared.json and all four
    location files, so it already moves on precisely that edit. This is the
    thing that reads it. No cartridge and no rendering -- it hashes the
    checkout's own files and reads the cache -- so it costs milliseconds where
    a regen costs about six seconds per cartridge.

    Not in either test suite, on purpose: both are documented as needing
    nothing outside the checkout, and this asks about the machine's PopTracker
    install. A developer with a stale override would get a red suite for
    something no commit can fix. docs/ISSUES.md says when to run it.

    Silent on a machine with no override, because that is not a stale one: the
    pack ships its hand-drawn art and the tracker is right to serve it.
    """
    if not os.path.isdir(out_dir):
        print(f"no override installed at {out_dir}; the pack's own art is what "
              "the tracker will serve")
        return 0
    cache, stale = load_cache(out_dir)
    if stale:
        print(f"{out_dir} was written by an older version of this tool "
              f"(cache v{stale.get('version')}) -- re-run without --verify")
        return 1
    if not cache:
        print(f"{out_dir} exists but holds no {CACHE_NAME}; nothing here can "
              "say what it was built from")
        return 1

    inputs_sha = inputs_fingerprint()
    bad = [MODE_DIRS[m] for m, was in sorted(cache.get("modes", {}).items())
           if was.get("inputs") != inputs_sha]
    if bad:
        print("the pack changed since this override was written, so the "
              "tracker is serving the older copy of every file in INPUT_FILES "
              "-- layouts included, where a key it predates renders an empty "
              "group with no warning")
        for name in bad:
            print(f"  stale: {name}")
    if not outputs_intact(out_dir, cache):
        print("and files the last run wrote have been changed or removed")
        bad = bad or ["outputs"]
    if bad:
        print("re-run tools/regen_maps.py <cartridge> once per affected mode, "
              "or --clean to drop the override entirely")
        return 1
    modes, outs = len(cache.get("modes", {})), len(cache["outputs"])
    print(f"{out_dir} is current with this checkout "
          f"({modes} mode(s), {outs} files)")
    return 0


# ----------------------------------------------------------------------- main

def write_if_changed(out_dir, rel, data, dry_run):
    """-> True if the file was written. Unchanged files keep their mtime."""
    path = os.path.join(out_dir, rel)
    try:
        with open(path, "rb") as f:
            if f.read() == data:
                return False
    except OSError:
        pass
    if not dry_run:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    return True


def encode(w, h, rgb):
    """PNG bytes for a rendered map. pngio writes to a path, so this goes
    through a temporary one rather than reimplementing the encoder.

    That temporary lives outside the override tree, so --dry-run creates
    nothing there and a run killed mid-render leaves no .tmp beside the art.
    """
    fd, tmp = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        pngio.write_rgb(tmp, w, h, rgb)
        with open(tmp, "rb") as f:
            return f.read()
    finally:
        os.remove(tmp)


def main():
    ap = argparse.ArgumentParser(
        description="Redraw the pack's dungeon maps from a cartridge, into "
                    "PopTracker's user-override tree.")
    ap.add_argument("rom", nargs="?", help="the cartridge to draw from; not "
                                          "needed by --verify or --clean")
    ap.add_argument("-o", "--out", help="override directory "
                                        "(default: ~/PopTracker/user-override/<uid>)")
    ap.add_argument("--mode", choices=tuple(MODE_DIRS),
                    help="file the art as std or nov rather than reading the "
                         "cartridge's GameMode (a vanilla image has none)")
    ap.add_argument("--marker-size", type=int, default=MARKER_SIZE,
                    metavar="PX",
                    help=f"marker box on a rendered map, in image pixels "
                         f"(default {MARKER_SIZE}, a tile less a pixel a side "
                         "so adjacent markers do not merge; the pack's "
                         "hand-drawn art uses 24)")
    ap.add_argument("--marker-border", type=int, default=MARKER_BORDER,
                    metavar="PX", help=f"its border (default {MARKER_BORDER})")
    ap.add_argument("--npcs", choices=("none", "gates", "all"), default="all",
                    help="draw map objects on the art: every NPC (default), "
                         "just the No-Overworld gate NPCs, or none. The "
                         "townspeople, orbs and bats are what make a town read "
                         "as a town; --npcs none suppresses them, and --npcs "
                         "gates keeps only the NPCs that stand in a doorway")
    ap.add_argument("--force", action="store_true",
                    help="regenerate even if nothing changed")
    ap.add_argument("--dry-run", action="store_true",
                    help="say what would change, write nothing")
    ap.add_argument("--clean", action="store_true",
                    help="remove the override directory and exit")
    ap.add_argument("--verify", action="store_true",
                    help="exit 1 if the installed override predates this "
                         "checkout; reads no cartridge and draws nothing")
    args = ap.parse_args()

    out_dir = args.out or default_out()

    if args.clean:
        if not os.path.isdir(out_dir):
            print(f"nothing to remove at {out_dir}")
        elif args.dry_run:
            print(f"would remove {out_dir}")
        else:
            shutil.rmtree(out_dir)
            print(f"removed {out_dir}")
        return 0

    if args.verify:
        return verify(out_dir)

    if not args.rom:
        ap.error("a cartridge is required unless --verify or --clean")

    with open(args.rom, "rb") as f:
        rom = f.read()
    if rom[:4] != b"NES\x1a":
        sys.exit("not an iNES ROM")

    mode = mode_of(rom, args.rom, args.mode)
    print(f"this cartridge is a {MODE_DIRS[mode]} seed; its art goes in "
          f"images/maps/{mode}/")

    rom_sha = sha(rom)
    inputs_sha = inputs_fingerprint()
    cache, stale = load_cache(out_dir)
    if stale:
        print(f"this override was written by an older version of this tool "
              f"(cache v{stale.get('version')}); its files are at paths nothing "
              "writes any more and will be cleared")
    # One slot per mode, so rendering a No-Overworld cartridge does not throw
    # away the standard set. `outputs` spans both, because the two index files
    # and the layouts are shared and either run rewrites them.
    #
    # `inputs` is per mode for the same reason `rom` is. It used to be one key
    # for the whole tree, which meant regenerating either mode stamped the new
    # fingerprint over both: the other mode's art stayed on disk as the old
    # tools drew it, and the next run of that mode said "nothing to do". A
    # cache written before this has no per-mode fingerprint, so it reads as
    # stale and that mode redraws once -- which is the right answer for it.
    was = (cache or {}).get("modes", {}).get(mode, {})
    if (not args.force and cache
            and was.get("rom") == rom_sha
            and was.get("inputs") == inputs_sha
            and was.get("npcs", "none") == args.npcs
            and was.get("marker") == [args.marker_size, args.marker_border]
            and outputs_intact(out_dir, cache)):
        print(f"up to date: {len(cache['outputs'])} files in {out_dir}")
        print("nothing to do (--force to regenerate anyway)")
        return 0

    if was and was.get("rom") != rom_sha:
        print(f"the {MODE_DIRS[mode]} cartridge changed since the last run")
    elif cache and not was:
        print(f"no {MODE_DIRS[mode]} art has been rendered here yet")
    elif was and was.get("inputs") != inputs_sha:
        print(f"the pack or these tools changed since the {MODE_DIRS[mode]} "
              "art was last drawn")
    elif was and was.get("npcs", "none") != args.npcs:
        print(f"--npcs changed from {was.get('npcs', 'none')} to {args.npcs} "
              "since the last run")

    bank = extract_chests.standard_map_bank(rom)
    print(f"reading standard maps from bank ${bank:02X}")

    graph = only = None
    if args.npcs != "none":
        graph = entrance_graph.Graph(entrance_graph.Rom.of(rom, args.rom))
        if args.npcs == "gates":
            # gate_objects returns None off No-Overworld, and an empty set
            # would silently draw nothing -- say so instead.
            if not graph.gates:
                print("--npcs gates: this cartridge has no gate layout, so "
                      "there are no gate NPCs to draw")
                graph = None
            else:
                only = set(graph.gates)
                print(f"drawing {len(only)} gate NPCs")
        else:
            drawn = sum(len(graph.objects(m)) for m in render_maps.MAP_FILES)
            print(f"drawing all {drawn} map objects")

    # The crop box is the one number both halves of this depend on: the art is
    # drawn from it and every marker's pixel is measured from it. Computed once,
    # here, and handed to both -- two calls that could drift apart is the shape
    # of bug that puts a box next to its chest instead of on it.
    crops_ = crops(rom)
    rows = legend_rows(rom)

    files = {}

    # 1. the art, cropped to what each map actually uses and filed by mode
    art = build_images(rom, mode, crops_, rows, graph, only,
                       render_maps.trap_marks(rom))
    sizes = {name: (crops_[name].size[0] * TILE_PX,
                    (crops_[name].size[1] + rows[name]) * TILE_PX)
             for name in render_maps.MAP_FILES.values()}
    mismatched = [(name, art[f"images/maps/{mode}/{name}.png"][:2], sizes[name])
                  for name in render_maps.MAP_FILES.values()
                  if art[f"images/maps/{mode}/{name}.png"][:2] != sizes[name]]
    if mismatched:
        # If the renderer ever starts padding, centring or scaling differently,
        # this is where it shows up -- before the markers are written, rather
        # than as boxes sitting off their chests in PopTracker.
        print("\nFAILED: the art is not the size the marker coordinates assume. "
              "The renderer and the crop box have gone out of step:")
        for name, got, want in mismatched[:10]:
            print(f"  {name}: image is {got[0]}x{got[1]}, markers are placed "
                  f"for {want[0]}x{want[1]}")
        print("\nnothing was written.")
        return 1
    for rel, (w, h, rgb) in art.items():
        files[rel] = encode(w, h, rgb)

    # 2. the markers, built from the cartridge onto it
    cal = rendered_calibration(rom, crops_)
    dungeon_locations = ("locations/overworld.json" if mode == "std"
                         else "locations/NOverworld/overworld.json")
    incentive_locations = ("locations/incentives.json" if mode == "std"
                           else "locations/NOverworld/incentives.json")
    dropped = []
    tiles_by_name = marker_tiles(rom, dungeon_locations, dropped)
    # Which tiles end up under a sprite, so a pin landing on one can be drawn
    # as a diamond instead of a square that hides it. Empty when --npcs none,
    # which is why nothing changes shape unless sprites are actually drawn.
    sprite_cells = {}
    if graph is not None:
        sprite_cells = {map_id: sprites.drawn_cells(rom, graph, map_id, only)
                        for map_id in render_maps.MAP_FILES}
    placed = unmoved = 0
    unplaceable = []
    shaded = []
    # The incentive sheet is handed no tiles rather than handed the board's and
    # trusted not to match any: tiles_by_name is keyed by bare node name, and
    # `I: Shop Item` is already a node name in both documents. If a board node
    # ever resolved to a tile under a name the sheet also uses, the sheet's
    # node would silently gain a dungeon-map pin on art it does not show.
    for rel, tiles in ((dungeon_locations, tiles_by_name),
                       (incentive_locations, {})):
        doc, pl, un, bad, shade = place_locations(cal, tiles, rel,
                                                  sprite_cells)
        # The same rules the committed tree carries, from the same function.
        # place_locations keeps only the pins whose map it does not redraw and
        # rebuilds the rest from tiles, so every dungeon rule the pack ships
        # would be dropped here otherwise -- and the toggles would go quiet on
        # exactly the seeds an override exists for. Stamping rather than
        # preserving is also what gives the pins this cartridge newly places --
        # Astos, Matoya, Bikke, the Fairy, Bahamut -- their rule on arrival.
        pin_visibility.stamp(doc)
        files[rel] = (json.dumps(doc, indent=4) + "\n").encode()
        placed += pl
        unmoved += un
        shaded += shade
        unplaceable += bad

    # 3. the crop has to have cut nothing off. This is the guard on the whole
    # step: the box comes from one flood, and the way a flood goes wrong is by
    # reaching somewhere it should not, which shows up here as a chest or a
    # staircase or a tracked NPC outside the frame.
    npc_cells = {}
    for name, places in extract_npcs.extract(rom).items():
        for q in places:
            npc_cells.setdefault(q["map_id"], []).append(
                (f"npc {name}", q["tile_col"], q["tile_row"]))
    cut = []
    box_graph = graph or entrance_graph.Graph(entrance_graph.Rom.of(rom, args.rom))
    for map_id, name in render_maps.MAP_FILES.items():
        cut += [(f"{what} on {name}", name, cell[0], cell[1])
                for what, cell in render_maps.crop_violations(
                    rom, map_id, render_maps.map_tiles(rom, map_id),
                    crops_[name], box_graph, npc_cells.get(map_id, ()))]

    # And every marker has to land inside the image it names, with room for the
    # 24px box PopTracker draws around it -- tests/test_maps.lua checks exactly
    # this for the shipped art, and the crop is what could newly break it.
    stray = []
    for rel in (dungeon_locations,):
        def walk(nodes):
            for n in nodes:
                if not isinstance(n, dict):
                    continue
                for ml in n.get("map_locations") or []:
                    if ml.get("map") not in sizes:
                        continue
                    w, h = sizes[ml["map"]]
                    half = args.marker_size // 2
                    if not (half <= ml["x"] <= w - half
                            and half <= ml["y"] <= h - half):
                        stray.append((n.get("name"), ml["map"], ml["x"], ml["y"]))
                walk(n.get("children") or [])
        walk(json.loads(files[rel]))

    # 4. the maps and tabs the new art needs. Both index files are rebuilt from
    # whichever mode sets are actually on disk, so a mode never rendered here
    # falls back to the pack's own art rather than to the other mode's.
    have = {mode}
    for other in MODE_DIRS:
        if other != mode and os.path.isdir(os.path.join(out_dir, "images", "maps", other)):
            have.add(other)
    files["maps/maps.json"] = (json.dumps(
        build_maps_json(have, args.marker_size, args.marker_border),
        indent=4) + "\n").encode()
    files["maps/NOverworldMaps.json"] = (json.dumps(
        build_noverworld_maps_json(have, args.marker_size, args.marker_border),
        indent=4) + "\n").encode()
    files["layouts/shared.json"] = (json.dumps(build_layouts(), indent=4) + "\n").encode()

    def report(what, rows):
        print(f"\nFAILED: {len(rows)} {what}:")
        for name, m, x, y in rows[:10]:
            print(f"  {name} on {m} at {x},{y}")
        if len(rows) > 10:
            print(f"  ... and {len(rows) - 10} more")

    # A chest rejected as backdrop would be a real AP location with nowhere to
    # pin it, and both answers are wrong on their own -- a pin in the void, or a
    # check missing from the tracker -- so the run stops rather than choosing
    # quietly.
    #
    # It cannot fire today, and that is structural rather than lucky.
    # stands_on_map rejects a cell only if outside_cells reached it, and
    # outside_cells floods on tile id equal to the map's backdrop
    # (render_maps.py:438). A chest cell carries a treasure tile, never the
    # border filler, so no chest is ever rejected -- 0 of 251 on the reference
    # cartridge, and no seed can change that while the flood keys on tile id.
    # The NPC half does fire, because an object is drawn over whatever cell it
    # stands on and the Ice Cave B1 fairy stands on backdrop.
    #
    # Kept as a tripwire on that reasoning, not as live protection: if the flood
    # ever grows a second rule, this is where a chest would fall through.
    voided = [(f"chest {name}", render_maps.MAP_FILES.get(map_id, map_id),
               f"tile {col}", row)
              for name, kind, map_id, col, row in dropped if kind == "chest"]

    if unplaceable:
        report("locations carry a marker on a redrawn map but resolve to no "
               "tile, so there is nothing to place them from", unplaceable)
    if voided:
        report("chests sit on a cell the edge flood reaches, so they are "
               "backdrop rather than map and there is nowhere to pin them",
               voided)
    if cut:
        report("things the crop would cut off the edge of their map", cut)
    if stray:
        report("markers land outside the image they name", stray)
    if unplaceable or voided or cut or stray:
        print("\nnothing was written.")
        return 1

    # Clear an older layout's files before writing, so nothing is left behind
    # for PopTracker to keep reading. Only files this tool recorded writing are
    # touched -- never anything the user put there.
    removed = []
    for rel in sorted((stale or {}).get("outputs", {})):
        if rel in files:
            continue
        path = os.path.join(out_dir, rel)
        if os.path.exists(path):
            removed.append(rel)
            if not args.dry_run:
                os.remove(path)

    changed = [rel for rel in sorted(files)
               if write_if_changed(out_dir, rel, files[rel], args.dry_run)]

    if not args.dry_run:
        modes = dict((cache or {}).get("modes", {}))
        modes[mode] = {"rom": rom_sha, "npcs": args.npcs,
                       "inputs": inputs_sha,
                       "marker": [args.marker_size, args.marker_border]}
        outputs = dict((cache or {}).get("outputs", {}))
        outputs.update({rel: sha(data) for rel, data in files.items()})
        with open(os.path.join(out_dir, CACHE_NAME), "w") as f:
            json.dump({"version": CACHE_VERSION, "inputs": inputs_sha,
                       "modes": modes,
                       "outputs": dict(sorted(outputs.items()))}, f, indent=1)

    verb = "would write" if args.dry_run else "wrote"
    print(f"\n{verb} {len(changed)} of {len(files)} files to {out_dir}")
    if removed:
        print(f"  {'would remove' if args.dry_run else 'removed'} "
              f"{len(removed)} left by the older layout")
    print(f"  {placed} markers built from the cartridge onto the {MODE_DIRS[mode]} "
          "art, each on the chest or NPC tile the ROM puts it on")
    print(f"  {unmoved} left alone (the overworld and incentive maps are not "
          "redrawn, so their markers keep the pack's pixels)")
    # Expected -- the Ice Cave B1 fairy is a copy of the Gaia object in the
    # black outside the cave -- but said out loud, so a second one appearing
    # is a number that changed rather than a pin nobody missed.
    for name, kind, map_id, col, row in dropped:
        print(f"  {name}'s {kind} placement on "
              f"{render_maps.MAP_FILES.get(map_id, map_id)} at {col},{row} is "
              "outside the map's content and gets no pin")
    if graph is not None:
        # Counted rather than eyeballed: a square pin is opaque and exactly one
        # tile, so every one of these would have hidden the sprite it sits on.
        print(f"  {len(shaded)} of them share a tile with a drawn sprite and "
              "are diamonds, so the sprite reads at the tile's corners")
        for name, m in sorted(shaded)[:10]:
            print(f"    {name} on {m}")
        if len(shaded) > 10:
            print(f"    ... and {len(shaded) - 10} more")
    kept = sum(c.size[0] * c.size[1] for c in crops_.values())
    print(f"  cropped to a mean {kept / len(crops_) / 4096 * 100:.0f}% of the "
          f"64x64 grid; {sum(1 for r in rows.values() if r)} maps reserve a "
          "Map Key band")
    # Say what each tracker variant will actually open, because "which art am I
    # looking at" is otherwise a question you can only answer by recognising a
    # staircase. A mode with no set here falls back to the pack's hand-drawn
    # art, which is easy to mistake for the tool having done nothing.
    print("  what each variant will show:")
    for m, variants in (("std", "Standard / Shard Hunt Map Tracker"),
                        ("nov", "NOverworld / NOverworld Shard Hunt Map Tracker")):
        if m in have:
            print(f"    {variants}: images/maps/{m}/, drawn from a "
                  f"{MODE_DIRS[m]} cartridge")
        else:
            print(f"    {variants}: the pack's hand-drawn art -- no "
                  f"{MODE_DIRS[m]} cartridge has been rendered here. Run this "
                  f"on one to fill it in.")
    if changed and len(changed) < len(files):
        print("  changed: " + ", ".join(changed[:8])
              + (" ..." if len(changed) > 8 else ""))
    if not args.dry_run:
        print("\nRestart PopTracker to pick it up. `--clean` puts the pack back.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
