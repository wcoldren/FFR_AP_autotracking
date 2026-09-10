"""A tile the art draws, a rule calls a marker, and no marker stands on.

The register's entry "A pin missing from art that was drawn, wherever two rules
derive the same content separately" names the shape and asks for exactly this
walk. One instance reached a player before anything here noticed: Sea Shrine
B3's bottom-right room is a sealed thirteen-cell speck holding a staircase and
a warp, `render_maps.protected_cells` shields every teleport from the crop
except a warp, so the staircase kept the room and the art was drawn -- and then
`floor_exits` ran `drop_specks` with no `keep` of its own, dropped the room, and
took the warp's pin with it. On the seed it was found on that tile was the first
hop of the only chain to Kraken.

**The existing guard runs the other way.** `render_maps.crop_violations` asks
whether the crop cut off something the map points at. Nothing asked the mirror
-- the crop kept this, a rule calls it a marker, and no marker is there -- which
is the direction a stricter marker rule fails in, silently, on art that is
perfectly correct.

Three sets, from three places, which is what keeps this from being a tautology:

  * **drawn** is the render's own answer -- content_cells, drop_specks and
    content_crop, with the keep regen_maps.crop_keep builds. Asked, never
    reimplemented: a copy here would agree with itself and prove nothing.
  * **candidates** come off the cartridge's own tables -- extract_chests,
    extract_npcs, and each map's teleport table -- and not off any rule that
    decides what to mark. That independence is the whole test.
  * **marked** is what the pin rules actually emit: marker_tiles for chests and
    NPCs, entrance_members for staircases, holes and floor-exit warps.

Warps are the one candidate that needs a shape rather than a kind. A town's
outer border is warp-to-overworld -- 33,282 tiles on the standard oracle
against 99 real links -- so the candidate is a warp *cluster* of no more than
FLOOR_EXIT_CLUSTER, which is the structural half of what floor_exits decides.
The other half is which content it stands on, and that half is what disagreed.

**What the sweep must not report is named, not tolerated.** Five NPCs the
cartridge places have no box anywhere and that is a decision with its own
register entry; the ToFR chest copies a cartridge lays and never wires are
dropped on purpose, and marker_tiles says so through `dropped` rather than
quietly. Everything else is a finding.

**Two things it cannot see, so neither is read into a clean run.** It catches
two rules *disagreeing*, not both being wrong the same way: `drawn` and `marked`
both ask crop_keep, so a crop_keep that lost a room would take the pin and the
art together and this would report nothing. And the candidate set is the kinds
of tile this pack marks -- chests, tracked NPCs, links, warp doors -- so a rule
that loses something else loses it unwatched.

Set FF1_ROM or FF1_CORPUS to say where the cartridges are; without either this
skips. FF1_SLOW=1 sweeps every cartridge on the machine rather than the seed in
play plus the graded corpus.
"""
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import corpus  # noqa: E402
import entrance_graph  # noqa: E402
import extract_chests  # noqa: E402
import extract_npcs  # noqa: E402
import regen_maps  # noqa: E402
import render_maps  # noqa: E402
import split_locations  # noqa: E402

fails = []


def check(what, got, want):
    ok = got == want
    print(("ok   " if ok else "FAIL ") + what.ljust(58)
          + ("" if ok else f" {got!r}"))
    if not ok:
        fails.append(f"{what}: got {got!r}, want {want!r}")


# The five NPCs the cartridge places that no location tree hosts, so no marker
# is drawn for them and none should be. Named rather than counted, the way
# test_pin_visibility names the orb slots: a count going 5 -> 4 is a pin
# quietly disappearing and reads as this list being slightly stale, whereas a
# name leaving it is a question. docs/ISSUES.md, "Five NPCs the cartridge
# places have no box anywhere" -- the four fiends are spiked battle tiles that
# write no flag in vanilla or FFR, and Dr Unne holds no shuffled item, so a box
# for any of them would be manual-click forever.
NO_BOX_NPCS = ("lich", "marilith", "kraken", "tiamat", "unne")

# Which location tree a cartridge's pins come from. The same choice
# regen_maps.main makes; not mode_of, because that exits the process on a
# cartridge whose GameMode it cannot read and this walks whatever is on the
# machine, vanilla images included.
TREES = {"std": "locations/overworld.json",
         "nov": "locations/NOverworld/overworld.json"}


def mode_of(rom, path):
    """'std', 'nov', or None where the cartridge does not say."""
    mode, _why = entrance_graph.game_mode(entrance_graph.Rom.of(rom, path))
    if mode == entrance_graph.GAME_MODE_NOVERWORLD:
        return "nov"
    return "std" if mode == 0 else None


def npc_cells_by_code(rom):
    """{(map_id, col, row): code} for every NPC the extractor knows."""
    out = {}
    for code, places in extract_npcs.extract(rom).items():
        for q in places:
            out.setdefault((q["map_id"], q["tile_col"], q["tile_row"]), code)
    return out


def candidates(graph, rom):
    """{(map_id, col, row): kind} -- every tile some rule could call a marker.

    Off the cartridge's own tables, never off a marker rule. A chest tile is a
    chest tile whether or not anything drew a pin on it, and that is the point.
    """
    out = {}
    chests, _ = extract_chests.extract(rom)
    for idx, places in chests.items():
        for q in places:
            out[(q["map_id"], q["tile_col"], q["tile_row"])] = "chest"
    for cell, code in npc_cells_by_code(rom).items():
        out.setdefault(cell, "npc")
    for map_id in render_maps.MAP_FILES:
        tele = graph.teleports(map_id)
        for col, row, kind, _pay in tele:
            if kind in regen_maps.FLOOR_LINK_KINDS:
                out.setdefault((map_id, col, row), "link")
        warp = {(c, r) for c, r, k, _ in tele
                if k == entrance_graph.TP_TELE_WARP}
        for group in regen_maps._clusters(warp) if warp else ():
            if len(group) <= regen_maps.FLOOR_EXIT_CLUSTER:
                for cell in group:
                    out.setdefault((map_id,) + cell, "warp-door")
    return out


def sweep(path, floor_exits=None):
    """(findings, counts) for one cartridge.

    `floor_exits` replaces regen_maps.floor_exits for the run, which is how the
    demonstration below puts the defect back: a test that only ever sees the
    fixed tree cannot show that it would catch the broken one.
    """
    graph = entrance_graph.Graph(entrance_graph.Rom(path))
    rom = graph.rom.data
    mode = mode_of(rom, path)
    if mode is None:
        return None, None

    real = regen_maps.floor_exits
    if floor_exits is not None:
        regen_maps.floor_exits = floor_exits
    try:
        npc_cells = regen_maps.npc_cells_of(rom)
        dropped = []
        placed = regen_maps.marker_tiles(rom, TREES[mode], dropped=dropped,
                                         graph=graph)
        members = regen_maps.entrance_members(graph, npc_cells)

        marked = set()
        for cells in placed.values():
            marked.update(cells)
        for cells in members.values():
            marked.update(cells)

        # Deliberate drops, told apart by the reason marker_tiles recorded.
        # "stranded" is a ToFR chest copy the cartridge lays and never wires,
        # so the art draws it and nothing may mark it; "backdrop" already
        # fails stands_on_map below and is counted only to be reported.
        stranded = {d[2:5] for d in dropped if d[-1] == "stranded"}
        backdrop = [d for d in dropped if d[-1] == "backdrop"]

        by_code = npc_cells_by_code(rom)
        no_box = {cell for cell, code in by_code.items()
                  if code in NO_BOX_NPCS}

        cand = candidates(graph, rom)
        outside = {}
        findings = []
        for map_id in sorted(render_maps.MAP_FILES):
            here = {c: k for c, k in cand.items() if c[0] == map_id}
            if not here:
                continue
            tiles = graph.grid(map_id)[0]
            keep = regen_maps.crop_keep(graph, map_id,
                                        npc_cells.get(map_id, ()), tiles)
            drawn, _ = render_maps.drop_specks(
                render_maps.content_cells(tiles), keep)
            for cell, kind in sorted(here.items()):
                _m, col, row = cell
                if (col, row) not in drawn:
                    continue
                if not regen_maps.stands_on_map(rom, *cell, cache=outside):
                    continue
                if cell in marked or cell in stranded or cell in no_box:
                    continue
                findings.append((render_maps.MAP_FILES[map_id], kind, col, row))
        counts = {"mode": mode, "maps": len(render_maps.MAP_FILES),
                  "candidates": len(cand), "marked": len(marked),
                  "stranded": len(stranded), "backdrop": len(backdrop),
                  "no_box": len(no_box)}
        return findings, counts
    finally:
        regen_maps.floor_exits = real


def where_to_look():
    """The cartridges to sweep: the seed in play and the graded corpus.

    Every cartridge on the machine takes about a second each and there are
    dozens, so the default is the two this machine names outright and FF1_SLOW
    is the whole tree -- the same opt-in tools/tests/run.sh already documents
    for the floor-walk memo. corpus.search_roots deliberately folds FF1_CORPUS
    into FF1_ROM's tree when one contains the other, which is right for a
    caller that wants everything and wrong here, so the two are asked for
    separately.
    """
    if os.environ.get("FF1_SLOW"):
        return corpus.cartridges()
    out = []
    rom = os.environ.get("FF1_ROM")
    if rom and os.path.isfile(rom):
        out.append(os.path.abspath(rom))
    corp = os.environ.get("FF1_CORPUS")
    if corp and os.path.isdir(corp):
        out += corpus.cartridges([os.path.abspath(corp)])
    return sorted(set(out))


carts = where_to_look()
if not carts:
    print("skipped: neither FF1_ROM nor FF1_CORPUS says where cartridges live")
    sys.exit(0)

# --- the sweep itself
swept, kinds, unreadable = 0, Counter(), 0
by_mode = {}
for path in carts:
    findings, counts = sweep(path)
    if counts is None:
        unreadable += 1
        continue
    swept += 1
    kinds[counts["mode"]] += 1
    by_mode.setdefault(counts["mode"], path)
    check(f"{os.path.basename(path)[:36]:36s} ({counts['mode']}) draws no "
          "unmarked tile", findings, [])

check("and something was actually swept", swept > 0, True)
print(f"     {swept} cartridge(s): {kinds['std']} standard, {kinds['nov']} "
      f"No-Overworld, {len(render_maps.MAP_FILES)} maps each"
      + (f"; {unreadable} with no GameMode to read" if unreadable else ""))

# --- and it has to catch the defect it was written for
#
# The pre-crop_keep call, put back: floor_exits dropping specks with no `keep`
# of its own while the crop kept them on a staircase's account. A clean run
# above says nothing on its own -- a sweep that reports nothing because it looks
# at nothing reports exactly the same thing -- so the tree is broken on purpose
# and the tile the register names has to come back.
real = regen_maps.floor_exits
std, nov = by_mode.get("std"), by_mode.get("nov")
if std is None:
    print("     (no standard cartridge here, so the demonstration is skipped)")
else:
    findings, _ = sweep(std, floor_exits=lambda g, m, keep=(): real(g, m, ()))
    check("a floor_exits that ignores the crop's keep loses seaB3's warp",
          [f for f in findings if f[0] == "seaB3"],
          [("seaB3", "warp-door", 47, 39)])
    # The room is a standard-cartridge fact: No-Overworld has no such sealed
    # corner, so the same broken rule loses nothing there. Held so the row above
    # is read as "this cartridge, this room" and not as "any cartridge".
    if nov is not None:
        findings, _ = sweep(nov,
                            floor_exits=lambda g, m, keep=(): real(g, m, ()))
        check("and loses nothing on a No-Overworld cartridge, which has no "
              "such room", [f for f in findings if f[1] == "warp-door"], [])

for f in fails:
    print("     " + f)
print("ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
