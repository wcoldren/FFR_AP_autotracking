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

**Which maps that is, now measured.** The seam-wrap half of the loose-crop entry
has its own fix on the roadmap; what is left for this idea is six maps, in two
shapes. `onrac`, `lefein` and `seaB1` have **no empty column anywhere** — a one-
to three-cell sliver spans the full width, so no bounding box can help and the
question is which components are worth framing at all. `iceB2` (8-column interior
gap), `iceB3` (18) and `sky4F` (six scattered gaps) are multi-lobe maps where a
rotation would actively make things worse by putting the left half on the right.
Add the three composites above and this idea covers nine maps.

The guard is already written: `render_maps.crop_violations` refuses a box that
cuts off a chest, a staircase or an exit, so "drop a component" has a test that
says when it went too far. What it cannot answer is the judgement — Onrac's river
is real map content and still not worth framing — so a size threshold here is a
decision to be defended, not tuned.

**Routes drawn on the map.** Wanted in two flavours — shortest to the exit, and
one that collects the loot on the way — and eventually per-map custom routes for
towns, where the useful stops are shops and NPCs rather than chests.
`entrance_graph.py` has the graph *between* maps; a route *within* a map is a
different problem and wants walkability per tile, which `lut_OWTileset` gives for
the overworld and the tileset property tables give for standard maps. Settle
first whether the drawing surface is the PopTracker tab (a static image, so the
route has to be baked in at render time) or `tools/doormap.py` (free to draw
anything, but not in front of you while you play).

The reference art both online and in the older guides already draws these lanes,
and is the thing to improve on rather than copy: **it is not consistent about
colour**, swapping cyan and purple between the optimised route and the with-loot
one from map to map. Ours should fix one colour per lane across all 61 and draw a
key on the map saying which is which — the Map Key band `render_maps` already
reserves is where that goes.

**"Optimal" needs an objective function, and it is not purely step count.**
Lowest step count first, but tie-broken toward **running into a wall rather than
turning in an open four-way**: holding a direction until the map stops you is
much easier to execute than counting tiles and turning on the right one. A route
that is two steps shorter and needs three counted turns is the worse route. Where
turning at a non-dead-end is genuinely necessary the route should still take it —
the preference is a tie-break, not a constraint.

Deriving is not the whole job either. A by-eye pass per map, flagging where a
better route exists than the reference draws, is expected to stay in the loop.

**Linked chests belong on the same drawing pass.** A chest index can sit on more
than one tile, so opening any one clears the lot, and nothing on the map says so
today. Measured 2026-08-30 on the oracle corpus — and the count is
**seed-dependent**, so it derives per cartridge rather than from a table:

- **6 multi-tile indices on std, 14 on nov.** The difference is Short ToFR, which
  duplicates indices onto `tofrChaos`.
- **Same-map groups, wanting a grey connecting line:** four, identical on both —
  `25` and `26` on `marshB2`, `29` on `marshB3`, `101` on `volcB4`.
- **Cross-map groups, wanting a badge or a circle rather than a line, because
  there is no line to draw:** two on std (`92` across volcB4+volcB5, `123` across
  ordeals2F+3F), ten on nov, including `254` across `cardia`, `tofr3F` and
  `tofrChaos`.

`extract_chests.extract()` already returns a *list* of placements per index for
exactly this reason, so the data needs no new ROM reading. Note the pin side has
bitten before: keying pins by map name collapses three `marshB3` pins into one,
so compare as multisets.

**Mark the hint givers.** Wanted as an annotation beside the sprite rather than a
PopTracker marker — a reminder of which NPC in a town has something to say, and
whether you have been to them. There is no flag for "talked to", so a pin would
be manual-click forever; drawing it into the art at render time sidesteps that
entirely, and it is the same mechanism the trap marks already use
(`font.draw_text` over the rendered tile). No location node, no autotracking
question.

What is already known, off FFR's own source rather than guessed:

- **The hint givers are a fixed set of eight**, one per town, written as a
  literal in `FF1Lib/NpcHints.cs:452` — ConeriaOldMan `52`, PravokaOldMan `64`,
  ElflandScholar1 `83`, MelmondOldMan2 `110`, CrescentSage11 `130`,
  OnracOldMan2 `154`, GaiaWitch `185`, LefeinMan12 `200`. They are not shuffled
  into the role. None is in `extract_npcs.WANTED` today, and adding them there is
  how their tiles get read.
- **Positions still have to come off the cartridge.** Turning hints on *moves*
  the Lefein one (`maps[MapIndex.Lefein].MapObjects.MoveNpc(0x0C, 0x0E, 0x15…)`),
  which is the same reason the NPC pins stopped reading `npc_positions.json`.
- **Whether the seed has hints at all is knowable.** `flags.HintsVillage` is in
  the decoded schema (`tools/ffr_flags/schemas/4-9-2.json:2255`) and already
  reaches the pack over the bridge.
- **The catch that decides the scope: there are no village hints on an
  Archipelago seed.** `NPCHints()` returns immediately when `flags.Archipelago`
  is set (`NpcHints.cs:427`), alongside DeepDungeon. So this annotation is a
  bridge/UAT-only feature by construction, and drawing it on an AP seed would be
  pointing at an NPC with nothing to say.

Unsettled: whether "have I visited this one" can be shown at all without a flag,
or whether the annotation is purely static and the visited-ness stays in the
player's head. The observation channel the entrance markers are designed around —
the bridge watching party position — is the only thing that could answer it, and
standing next to an NPC is not the same as having talked to them.

**Notice when the drawn maps are for a different cartridge.** Raised while
regenerating after a rules change: the override shadows the checkout, so a stale
override serves stale art *and* stale access rules, and nothing says so. The ask
was to trigger a regen from Lua on connect when the ROM differs from last time,
and keep the images otherwise.

**The caching half already exists.** `.regen_cache.json` records each mode's ROM
sha, the input fingerprint, `--npcs` and the marker geometry, and a second run on
the same cartridge prints `up to date: 129 files ... nothing to do`. So "keep the
images otherwise" is not work; only the trigger is.

**There are two mismatches to detect, not one.** The cartridge can change, which
is what this entry was raised about; the *pack* can also change under a fixed
cartridge, and that is the case that has actually bitten. `INPUT_FILES`
(`regen_maps.py:99-112`) lists `layouts/shared.json` and the four location files,
so the `inputs` fingerprint already moves the moment one is edited. That half is
done: `regen_maps.py --verify` compares it, reads no cartridge and exits 1
naming the stale modes. What it cannot do is fire at the moment it matters,
which is tracker load -- see below, and `docs/ISSUES.md`, "A stale override
silently shadows pack edits".

**The pack cannot be the trigger.** PopTracker's Lua exposes `Tracker` (items,
locations, maps, layouts, `ProviderCountForCode`, `FindObjectForCode`, `UiHint`,
`OpenLink`, `ActiveVariantUID`) and `ScriptHost` (the watches, `CreateLuaItem`,
frame handlers, `RunScriptAsync`/`RunStringAsync`) and nothing else --
`tests/pop_api.lua` is the transcribed surface. No `io`, no `os`. `RunScriptAsync`
runs *Lua*, not a shell command.

**The bridge could be**, mechanically: `ffr_uat_bridge.lua` already reads and
writes files (`EMU.readFile` / `writeFile` / `appendFile`) and already requires
Mesen's "Allow access to I/O and OS functions" for its sockets, so `os.execute`
is plausibly in reach. Two constraints on any version that actually runs one:

- **It has to be eager and detached.** Eager because the useful moment is the
  one where the cartridge is first seen -- on connect, or on the seed swap the
  bridge already detects -- not when someone notices the pins are wrong.
  Detached because a regen renders 61 maps; run inline on the emulator's script
  thread it stalls emulation for the duration.
- **The restart is irreducible.** PopTracker loads pack images at load time,
  which is why `regen_maps.py` signs off with "Restart PopTracker to pick it
  up". No amount of triggering removes that step, so an automatic regen buys
  the render, never the reload -- and a regen the player does not know happened,
  followed by a tracker still showing the old art, is worse than no regen.

**So the first version to build is detection.** The bridge reads
`.regen_cache.json`, compares it against the cartridge in the emulator, and
publishes a variable; the pack lights a warning cell the way `flagsUnread`
already does (`uat.lua:159-203` -- a LuaItem whose Icon appears only when there
is a reason). That fits inside both sandboxes, needs no new permission, and turns
a silent wrong-pins failure into a visible one.

**And then execution, which this page used to argue against.** The old conclusion
was "detection, not execution", on the grounds that a regen the player did not
know happened, followed by a tracker still showing the old art, is worse than no
regen at all. **That objection is answered by the warning cell itself**: once the
mismatch is on screen, the player knows both that the art is stale and that
something was done about it, and the detached regen means the new art is already
waiting by the time PopTracker is restarted. Superseded 2026-08-30 rather than
dropped, because the reasoning is still the reason the warning comes first.

What has *not* changed is the restart. PopTracker loads pack images at load time,
so an automatic regen buys the render and never the reload.

One precondition is still unmeasured and is step 0 of that branch: `os.execute`
is described above as "plausibly in reach" in Mesen's Lua, which is an inference
from the file and socket functions the bridge already uses, not a test. If it
turns out not to be reachable, the detection half ships and the execution half
does not.

One thing it needs first: the bridge has no sha256, so the cache has to record
something cheap to compare. The FFR seed string and flag string are already read
on both sides, so writing those into `.regen_cache.json` alongside the sha is the
enabling change.

## Bosses and trap tiles

The four fiends and the ToFR refights have no pins. Two separate problems wearing
one label, and neither needs new ROM reading:

- **The four fiends are map objects.** `extract_npcs.WANTED` already reads their
  tiles off the seed — lich on map 32, marilith 36, kraken 42, tiamat 51, and
  the same four in `tools/npc_positions.json`, which is the vanilla snapshot
  those numbers came from — and `tools/tests/test_npc_pins.py` lists them as
  deliberately unpinned. What is missing is a location node for a pin to belong
  to.
- **The refights and traps are `TP_SPEC_BATTLE` tiles.**
  `render_maps.fixed_formations()` already reads byte 1 of each — the formation
  id, which is *which boss spawns* — and `trap_marks()` then spends it on a
  mark rather than a name. Naming the boss is reading a field the code already
  has in hand, and since the marks became formation-keyed the mapping from mark
  to fight is one-to-one, so a Map Key row could carry the name directly.

Placement would reuse `regen_maps.place_locations()`, which builds a pin from a
tile: hand it more tiles and it emits more pins. A boss tile is not walkable, so
a pin on it wants offsetting by a tile — that is `± tile_px` in the same
transform, and there is precedent for the problem in the other direction (the
shipped art draws Astos one tile above the cell the cartridge places him on).

**ToFR is not one layout, and the bosses move with it.** `ToFRMode` is
`Long / Mid / Short / Random` (`FF1Lib/TempleOfFiends.cs:6-16`) and it changes
which floors exist and where the fiends stand:

- **Long** wires the whole gauntlet, 1F through 3F and the four elemental
  floors.
- **Mid** (`:138-153`) repoints 1F's left stairs straight at the Earth floor and
  blocks the passages to Stairs B, so **2F and 3F are not in the dungeon at
  all**. Both standard seeds here are Mid.
- **Short** collapses it further, and the fiends end up on the Chaos map.
  Measured on `F258553F`: `tofrChaos` carries **8 fixed-formation trap tiles in
  a row at y=9**, where both Mid seeds have none on that map.

`FiendsRefights` moves them again -- `None` writes `0x5C` over the four refight
tiles outright (`TempleOfFiends.cs:92-97`), and `TwoPaths` shuffles which floor
each staircase leads to.

So any boss annotation has to read the cartridge, never a vanilla table. The
good news is that the existing mechanism already does: `fixed_formations()`
enumerates fixed-formation tiles off the tileset property tables and
`map_trap_marks()` asks one map which of them it places, so both are
mode-correct by construction. The thing to avoid is hardcoding a floor list or a
tile position from vanilla.

Note the keying changed under this idea and in its favour. These used to be
`trap_letters()` / `map_trap_letters()`, keyed `(tileset, tile)`, which drew the
same fight as two different letters on two maps — useless for naming a boss.
They are keyed to the formation now, so a mark identifies a fight rather than a
position.

The blocker is unchanged and is in `docs/ISSUES.md`: none of them writes a flag,
so every such box is manual-click forever. Worth deciding whether that is
acceptable before drawing anything.

## On the derivation

**Memoize the floor walk. Built 2026-08-30.** Instrumenting a full 1024-subset
sweep on a No-Overworld cartridge said 99.8% of it was repeated work:

    floor_walk calls over the full sweep : 86464
    distinct (map, arrival) pairs        :   129
    distinct results across all of them  :   188

92 of the 129 pairs produced the same walk no matter what was held, and none
produced more than four distinct results, so 86464 calls were doing 188 walks'
worth of work.

The key could not be `have` wholesale — that is one distinct set per subset and
gives no reuse at all. It is `(map, arrival, stop_on_teleport, have & the items
this floor consults)`, with the floor's items found by scanning its tile
properties and objects for what `walkable()` and `gated_objects` actually
consult. On the vanilla cartridge 42 of the 61 floors consult nothing and are
walked once for the whole sweep; on the No-Overworld oracle it is 38. Both
`floor_walk` and `reachable_teleports` are memoized -- the filed design counted
only the first, and `reachable_tiles` calls both, so a memo on one is half a
memo.

The key was the entire risk: one that omits an item the walk consults returns
stale reachability silently, which is the failure class this tree has hit four
times. `tools/tests/test_memo_walk.py` guards it two ways. The cheap one is
exhaustive and runs every time: a walk reads `have` in exactly two places, so if
neither `walkable()` on any of a map's property bytes nor `blocking_objects()`
on its objects can tell `have` from the trimmed key, over every map and all 4096
subsets, then no walk can. The expensive one is the equivalence the entry
demanded -- every subset, memoized against unmemoized, tile for tile -- and runs
on `FF1_SLOW=1`; it passed on the `nov` cartridge over all 4096 subsets on
2026-08-30.

It does not move the exponent, and did not have to. The outer loop is still 2^n,
but the sweep went from 1024 subsets in about 85 seconds to 4096 in about 57 --
which is what made the SubEngineer and Titan rows affordable in the same commit.

That comparison is across two runs and folds the memo together with the
vocabulary widening, so this entry's own "no speedup is quoted here" is answered
properly by an A/B on one build instead. Measured on `nov` 2026-08-30, same
gates and same twelve items either way, the memo switched off by the `NoMemo`
subclass `tools/tests/test_memo_walk.py` already carries:

    memoized     14.0 ms/subset      57.2s for 4096   (the real sweep, timed)
    unmemoized   77.5 ms/subset     ~318s for 4096   (projected from 120)

**About 5.5x.** Projecting the unmemoized side is fair because it has no
cross-subset reuse by construction, and the rate holds across sample sizes --
79.1 ms at 40 subsets, 77.5 at 120. It also brackets the old pre-memo run from
the other side: 85 seconds for 1024 is 83 ms/subset, so the walk was costing
what it costs unmemoized now and the memo is doing essentially all of the
difference.

Within a single subset the memo is only about 4x -- 18.8 ms against 79.1 on a
40-subset sample, which is the reuse inside one `reachable_tiles` fixed point.
The rest comes from the cache saturating across the sweep: 38 of `nov`'s 61
floors consult no item at all, so they are walked once for all 4096 subsets
rather than 4096 times, and the whole lattice only ever produces about 188
distinct walks.

The five further items -- the Slab, the Herb, the Adamant, the Bottle and the
Crystal -- are trades rather than tiles, so they want the solver below rather
than more headroom. It was seven before this commit; Oxyale and the Ruby were
the two that turned out to be tiles after all.

**Solve the requirements instead of sampling them.** The sweep asks the walker
2^n times. FFR does not: `Sanity/SCLogic.cs` propagates `SCRequirements` bitflags
over the map it built, which is a fixpoint over the graph rather than a sweep
over the item lattice. Reachability here is monotone — holding more never closes
a route — so the same shape works: each tile carries an or-of-ands requirement,
minimised as it propagates, and the output is the expression directly rather than
a set of samples to minimise afterwards.

That is the only approach that survives the items the derivation currently cannot
express, and it emits the same shape `check_logic` already compares against. Two
things to hold on to when it is done: the sweep's agreement with FFR is
much weaker than it was once recorded as. Most comparisons used to grant the
disputed item to both sides -- 58 of 222 were really compared -- and closing the
SubEngineer and Titan gates took that to 221 of 226, so the sweep is now a real
check on the twelve-item vocabulary rather than the oracle it was called here.
What is left outside it is not a graph property at all: the trades, and the
requirements that name another *location* rather than an item -- Lefein wants
the Slab translated, which is Dr Unne's own reachability. That last shape is the
one the sampling approach cannot express at any vocabulary size, and it is the
strongest argument for the solver.

**FFR already runs that solver, and the oracle is its output -- which changes
what is worth building.** `SanityCheckerV2` builds the map, `SCLogic` propagates
`SCRequirements` over it, and `FF1Lib/archipelago/Archipelago.cs:205` serialises
the result as the export's `rules:` section: one entry per Archipelago location,
`List<List<string>>`, an or-of-ands of item names. That is the file
`tools/check_logic.py` already grades against. So the interesting option is not
writing a propagation pass. It is **compiling the pack's Lua rules from that
export** instead of hand-writing them or sampling them.

That dissolves the Lefein class outright rather than working around it.
`SCLogic.cs:555-557` resolves the translated Slab to `allNpcs[Unne]` restricted
by the Slab -- a requirement naming another location -- and by the time it
reaches the export it has been flattened to items, `(Tnt OR Ruby OR Canoe) AND
Floater AND Slab`. Nothing downstream has to express "reach another location",
because the solver already did.

**The class has two members, not one, and the second is the stronger
argument.** `SCLogic.cs:559-562` is `allNpcs[ElfDoc].Restrict(Herb)`, the same
shape, and the derivation gets the Elf Prince `(free)` where FFR says `(Herb)`.
Lefein at least reports itself as the one `--derived` divergence; the Elf Prince
passes as agreeing, because `herb` is off-vocabulary and `check_logic` grants it
to both sides. So the sampling approach is not merely unable to express this
shape -- it cannot currently see how often it is hitting it. Full write-up in
`docs/ISSUES.md`. The vocabulary is wider too: `nov`'s rules
mention fifteen distinct items, including `Mark` and `Sigil` (the renamed Canoe
and Floater), against the twelve `entrance_graph.ITEM_NAMES` sweeps, and all
five trades the sweep cannot hold -- Slab, Herb, Adamant, Bottle, Crystal -- are
in there.

Three things to settle before this is a plan rather than an idea.

- **The export is per-seed and the pack ships one rule set.** Not a new problem:
  158 of `nov`'s 226 pack-side rules were already transcribed from one seed's
  export, per the provenance table in `docs/ORACLE.md`. Compiling makes that
  dependence visible rather than introducing it, and gives it a test -- compile
  from two seeds at identical flags and diff. On No-Overworld the difference is
  likely small, since three seeds carry 157 links each and differ only in the
  Gaia gateway and the two Waterfall stairs. Under entrance rando it would not
  be.
- **`Orbs` is the one requirement flag the export drops.** `SCRequirements` has
  twenty flags; both `GetRule` overloads emit nineteen and neither emits `Orbs`
  (`0x0100`), so a location requiring it exports with an empty -- that is,
  free -- clause. It does not bite today, because the orb-gated floors are the
  Temple of Fiends Revisited and those are excluded from the Archipelago pool
  unconditionally. A compiler would inherit the hole in silence, so it needs a
  guard that refuses an empty clause it cannot account for.
- **`ExtSpoiler.cs` is the wrong source.** Its `WriteItemPlacementSpoiler` uses
  the same `GetRule` shape, but filters `logic.RewardSources` to incentive
  items, quest items and orbs, so the `.txt` carries requirements for a handful
  of slots rather than all of them. The yaml's `rules:` is over every reward
  source: 227 locations on `nov`, 226 on `std`, 230 on `shard`.

**And the argument against, which is the one to answer first.** The current
setup's whole value is that the two sides are independent -- rules written one
way, graded against an answer produced another way. Compiling makes the oracle
and the rules the same object, so they agree by construction and
`check_logic.py` stops being a check at all. What would replace it is the
cartridge sweep, which is the genuinely independent third reading and today
supports 215 of `nov`'s 226. Whether that is enough cover is the decision, and
it is a decision about provenance rather than an optimisation. It wants its own
session; `docs/ROADMAP.md` says so at the bottom rather than queueing it.

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

**What a new user gets without the emulator bridge, and what the pack claims
about its assets.** Raised 2026-08-30 while looking at the regenerated maps. The
facts, gathered rather than assumed, because most of the answer turns out to be
"this already works" and the rest is one thing the README does not say.

- **Mesen is the emulator feed, and only the emulator feed.** `bridge/` is one
  Lua script Mesen runs. Nothing else in the pack needs it.
- **Without it, the Archipelago feed still autotracks.** What it cannot see is
  already written down under "What each feed can see": chests outside the
  multiworld's pool, orbs lit, items turned in, and shards from lighting orbs.
  A plain FFR async has no AP server either, and that is the case the bridge
  exists for.
- **Manual tracking is what the four `NoMap` variants are**, and the four map
  variants work with no ROM and no emulator at all — they load the 53
  hand-drawn PNGs in `images/maps/`, which ship with the pack.
- **Those PNGs are the pack's only substantial shipped assets**, 12 MB of them,
  inherited from the pack this forked and credited in the README. The README's
  claim is that no ROM is included and that no art *derived from one* is either,
  and both hold: `regen_maps.py` writes only into PopTracker's user-override
  directory. The hand-drawn maps are a different thing and are not covered by
  that sentence, which is easy to misread as "no assets ship at all".
- **The Pins toggles are map-only, and that is correct rather than a gap.**
  Measured: the `Pins` group appears in `standard/tracker.json`,
  `shardHunt/tracker.json`, `NOverworld/tracker.json` and
  `NOverworld/shardsTracker.json` — the four map variants. A variant with no map
  tabs has no pins to switch off, so parity here would mean adding a control that
  does nothing.

So the bridge-less experience is fine and mostly documented. What is missing is
one sentence saying it: that the map tabs work out of the box on hand-drawn art,
that rendering them from your own cartridge is an optional upgrade, and that the
emulator feed is what the extra boxes need. Everything above is a README
paragraph rather than a feature.

The open question underneath is the one the `NoMap` entry above already names —
nobody knows whether anyone outside this repo runs the pack — and it is worth
answering before spending on either.
