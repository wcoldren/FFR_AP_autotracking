# Ideas, not yet scoped

Things worth doing that nobody has designed yet, each recorded with whatever is
already known about it so scoping does not start from scratch. Nothing here is a
commitment and the order means nothing — `docs/ROADMAP.md` is what is actually
next.

## On the maps

**Show the towns when you walk into one.** No-Overworld gives every town
staircases, so a town is a room you route through — but `MAP_VALUE` still calls
maps 0-7 "Overworld" and `maptab.lua` sends you to the overworld tab. The town
tabs exist, but only in `regen_maps.py`'s override, because the pack has no town
art to ship. So `MAP_VALUE` cannot simply name them: the base pack would point at
tabs it does not have and `test_maptab.lua` would fail for the right reason.
Whatever the answer is — mode-aware `MAP_VALUE`, an override shipping its own
`mapValues.lua`, town art committed after all — it has to keep the standard
variants pointing at the overworld.

**Follow the party into the room.** The tab shows a whole map at one zoom and
never moves. PopTracker takes `Tracker:UiHint("Zoom <map>", "2.5")` and
`UiHint("Pan <map>", "x,y")` per map, since 0.34.0 — which is part of why the
manifest floor is 0.35.1. The pack already drives `UiHint("ActivateTab", ...)`
from `maptab.lua`, and the bridge would be reading party position anyway for
entrance markers (`sm_scroll` `$29/$2A`, party always 7 tiles in). So this needs
no new art and no new data — it is the same hint channel that already switches
the tab.

**Insets, the way the hand art does them.** Three shipped maps are composites of
disjoint pieces at unrelated offsets: `cardia` in 3 regions, `marshB2` and
`seaB3` in 2. The calibration format already carries that and `make_markers`
already reads it, so a renderer that split a map into connected components and
laid them out would reproduce the effect — and would also dissolve the loose crop
boxes in `docs/ISSUES.md`, by laying disjoint components out separately instead
of framing their union.

**Routes drawn on the map.** Wanted in two flavours — shortest to the exit, and
one that collects the loot on the way — and eventually per-map custom routes for
towns, where the useful stops are shops and NPCs rather than chests.
`entrance_graph.py` has the graph *between* maps; a route *within* a map is a
different problem and wants walkability per tile, which `lut_OWTileset` gives for
the overworld and the tileset property tables give for standard maps. Settle
first whether the drawing surface is the PopTracker tab (a static image, so the
route has to be baked in at render time) or `tools/doormap.py` (free to draw
anything, but not in front of you while you play).

## Bosses and trap tiles

The four fiends and the ToFR refights have no pins. Two separate problems wearing
one label, and neither needs new ROM reading:

- **The four fiends are map objects.** `tools/npc_positions.json` already holds
  their exact tiles — lich on map 32, marilith 36, kraken 42, tiamat 51 — and
  `tools/tests/test_npc_pins.py` lists them as deliberately unpinned. What is
  missing is a location node for a pin to belong to.
- **The refights and traps are `TP_SPEC_BATTLE` tiles.**
  `render_maps.trap_letters()` already reads byte 1 of each — the formation id,
  which is *which boss spawns* — and then discards it in favour of a positional
  letter. Naming the boss is reading a field the code already has in hand.

Placement would reuse `regen_maps.place_locations()`, which builds a pin from a
tile: hand it more tiles and it emits more pins. A boss tile is not walkable, so
a pin on it wants offsetting by a tile — that is `± tile_px` in the same
transform, and there is precedent for the problem in the other direction (the
shipped art draws Astos one tile above the cell the cartridge places him on).

The blocker is unchanged and is in `docs/ISSUES.md`: none of them writes a flag,
so every such box is manual-click forever. Worth deciding whether that is
acceptable before drawing anything.

## Notes and hints

Wanted: somewhere to write down a hint — which orbs a seed requires, what an NPC
said — ideally auto-populated as checks resolve.

**PopTracker has no notes feature.** Layouts have a static `"text"` widget and
items can carry short overlay badges; there is no free-text input anywhere. So a
manual notes surface is not a pack-side thing to build.

What does exist is `Archipelago:LocationScouts(locations, sendAsHint)`, since
0.26.2, gated on an `aphintgame` flag in `manifest.json` that this pack does not
currently set. That is the real hint path, it needs no ROM tooling, and it is
Archipelago-only — which on this pack means it would cover the thinner of the two
feeds.

Tied to this: **which orbs a seed requires is deliberately not derived.**
`scripts/logic.lua` returns 4 whenever `OrbsRequiredMode` is non-zero, because
which orbs is rolled into the seed rather than the flag string. Reveal-on-
observation — the pack learning by watching the player, the way the entrance
markers are designed to — is the shape that would not spoil. Parked here until
there is a surface to show it on.

## Options UI, pass 2

`layouts/settings_popup.json` is a named layout PopTracker recognises: define it
and a gear button appears in the toolbar opening a pack-specific settings window.
The Crystal pack uses it for ~60 seed settings across two tabs. Worth doing once
there are enough visibility toggles to justify a panel; until then they fit in
the existing flags grid.

## Names that have drifted

None urgent, none decided. Grouped because they are the same kind of question — a
label chosen for what this was, still attached to what it has become.

**`package_version: "1.1b"`** is upstream's, and what is on `trunk` shares little
with the pack that carried it. PopTracker shows the string in the pack list and
uses it for nothing else — no update check, no compatibility gate — so any value
is safe, which makes the only question what a reader should learn from it.
Continuing upstream's numbering claims a lineage the tree no longer has; a fresh
scheme, or a date, says "this is a fork" more honestly. Whatever it becomes
should probably move the `author` line too, which credits five people for the
pack this started from.

**The repo is called `FFR_AP_autotracking`, and most of it is not AP.** The
Archipelago feed carries checked locations and items received and nothing else;
everything else comes off the cartridge over UAT. So the name points at the
thinner feed. Bringing AP to parity is not pack work at all — it means changing
`worlds/ff1` in Archipelago to publish slot data, a different repository and a
different review path. Worth being explicit about that split before any renaming,
because the name is the only place it currently reads as though this repo could
close the gap on its own.

**The four `NoMap` variants.** PopTracker's chooser lists eight entries, four of
them map-less. They are not the broadcast windows — every variant already loads a
broadcast layout of its own — they are full trackers whose main window has no map
tabs. So the chooser offers a one-in-eight chance of landing in a variant with no
maps, on a pack whose recent work is almost entirely maps. Against dropping them:
they are cheap, and they are what someone with a small screen or a second monitor
would pick. For dropping them: every layout and location change has to be sound
in both trees, and nobody here runs them. Deciding needs the one thing nobody
knows — whether anyone outside this repo uses the pack.
