# Where this pack is

Working notes on what is built, what is next, and what is known to be wrong.
`README.md` says how to use the pack; this says what state it is in.

Last updated 2026-08-29.

> The NOverworld variants are the current focus and are further behind than the
> rest of this document implies. They have their own section below.

## Working today

- Two autotracking feeds, reconciled rather than merged: Archipelago over the
  wire, and a Mesen Lua bridge that mirrors `$6000-$62FF` over UAT. Either alone
  or both at once. `scripts/autotracking/reconcile.lua` takes the union and
  preserves hand clears.
- Chests, NPC and event flags, orbs, key items and every turn-in stage, vehicles,
  shard count, seed-swap detection, and a Resync button.
- A run clock drawn on the emulator's screen, counted in frames so it pauses
  when emulation does, kept per cartridge across a power cycle.
- The flags grid configures itself from the FFR flag string stamped in the ROM.
  Schemas ship for FFR 4-9-7 and 4-9-2; a seed on any other version lights the
  unread-flags warning in the grid rather than letting the defaults pass as the
  seed's own settings.
- A Bosses row for the five fights that have a real signal: Garland, the
  Vampire, Astos, Bikke and Chaos.
- Both overworld tabs show every slot there is. A slot the seed did not
  incentivize reports `AccessibilityLevel.Inspect` and draws blue instead of
  having its pin dropped, and a slot the seed did incentivize gets a gold
  `Highlight.Priority` ring on both tabs. Green still means reachable and red
  still means not: Inspect only sets `inspectOnly`, so a slot that is both
  skipped and out of logic comes out red.
- An `Overworld Tab` item that cycles Auto / Incentive / Full. Auto reads the
  Archipelago pool where there is one and the cartridge otherwise — `ShardHunt`
  or `ChestsKeyItems` and it lands on the full map. A bridge-only shard hunt
  used to land on the incentive map, which hid nearly every check it had.
- The Chaos kill read out of the battle engine — a battle running (`$60FC`),
  Chaos's formation in `btlformation` (`$6A`), `btl_result` (`$6B86`) set to
  `$FF` — rather than off `$62FE` bit 0x02, which FFR only writes on an
  Archipelago seed. It is the same instant the Archipelago patch sets its bit,
  so no seed's split moved. Feeds the run clock, the `chaos`/`clock` lines in
  `ffr_times.log`, and `ff1/goal`, which the pack now reads for
  `LOCATION_MAPPING[766]`.
- Map tabs follow the player. 36 of 53 dungeon maps are calibrated and carry
  per-chest markers.
- Offline tools that read a cartridge directly: the flag decoder, an
  entrance/floor shuffle reader and router, an HTML door map, an overworld
  reachability walk, and a logic checker that diffs the pack's access rules
  against FFR's own spoiler. The map-reading half of that was wrong until
  2026-08-29 — see "Read the maps from the bank FFR actually puts them in"
  below.
- `tests/run.sh` — 13 Lua suites, no emulator or ROM needed.

## Read the maps from the bank FFR actually puts them in

Fixed 2026-08-29, commit `3697da4`. Recorded here because the tools it touches
were listed as working for weeks while returning invented answers.

`tools/extract_chests.py` decompressed standard maps from bank `$04`. Every FFR
seed moves all 61 of them to bank `$14` and repoints the engine's two
`#BANK_STANDARDMAPS` constants — `StandardMaps.Write()`, called unconditionally
from `Randomize.cs:466` whatever the flags say. Banks 4-7 keep their untouched
vanilla copies, so reading there did not fail: it returned a complete,
confident, vanilla topology for a cartridge that plays nothing like it. On a
No-Overworld seed that came out as 11 floor links where the cartridge has 146,
and the 11 were genuine vanilla stairs, so nothing looked wrong.

`standard_map_bank()` now reads the constant at `$1F:D127` and falls back to
`$04` only for a stock 16-bank image. `--self-check` gained the two invariants
that would have caught it: the bank read must match the mirror constant at
`$1F:D145` and must not be the vanilla bank on an FFR cartridge, and a
No-Overworld entry map must have a staircase. Both fail on a reintroduced bug.

The lesson worth keeping: the cheap oracle — *with all key items, every map
must be reachable from the doors* — was already written down and simply never
run. Run it before believing any routing output.

## Next

1. **The NOverworld overhaul.** Its own section below; this is the focus.
2. **Door-map click-through.** `tools/doormap.py` gets a focus panel and real
   `#map-<id>` anchors driven by `hashchange`, so the shuffled dungeon can be
   walked by clicking instead of scrolled. One file, no pack risk. Worth more
   now that it reads real topology.

## The NOverworld variants

Triaged 2026-08-29 against FFR's own source and a live No-Overworld cartridge
(`GameMode 2`, FFR 4-9-2, seed `F258553F`). What the mode *is* is now settled;
what the pack should become is the open question.

### What FFR's No-Overworld actually does

All of it is `FF1Lib/MetroidVaniaMap.cs`, entry `FF1Rom.NoOverworld()` at :47.

- The overworld is **not removed** — it is swapped for `nooverworld.ffm`, an
  ocean stub with nine one-tile pads around `x 96-110, y 154-162`: the eight
  towns plus Coneria Castle. Confirmed off the cartridge: of 32 entrance rows,
  only those nine have a tile on the map.
- Everything else is connected by a **hand-authored table of 75 teleporters**,
  ids `0x41-0x8B`, at `:458-776`. All 61 maps are used; none is dropped.
- **Deterministic apart from three things**: the three Cardia/Bahamut one-way
  gateways are permuted across Waterfall / Ice Cave B1 / Gaia (`:726`), the
  Waterfall stair positions, and which ToFR chest ids the two bonus chests
  reuse. None of it reaches the spoiler log, so the cartridge is the only
  source. On the duck seed, Bahamut is behind Gaia.
- **FLOATER is renamed SIGIL and CANOE is renamed MARK**, and both become
  stair-blocking NPCs rather than vehicles. Ship and bridge are free. The other
  gates are CROWN, CHIME (Gaia to Mirage), TNT (Nerrick's tunnel) and KEY.
- The full shuffle runs only with `Entrances` or `Towns` set; the stock preset
  ships both off, so a default seed uses the fixed table.

### Where the pack stands against that

- ~~**Both map variants define exactly one tab.**~~ Fixed, commit `17c423d`.
  The dungeon tree moved to `layouts/shared.json` as three `shared_*_tabs` keys
  and all four map layouts reference it, so the NOverworld pair gained 51 maps
  and standard/shardHunt stopped carrying a byte-identical copy each. Expanding
  the references reproduces their previous trees exactly. The 282 markers in
  `locations/overworld.json` now have somewhere to draw, and `maptab.lua`
  follows the player into a dungeon on these variants too.
- **The one image cannot carry markers.** `images/maps/nooverworldmap.jpg` is
  upstream art (Photoshop, 2021, mikesrpgcenter watermarks) added in the "Add
  files via upload" commits. It is 3096x2816, but Coneria Castle occupies about
  300x330 of it against 1074x605 for the pack's own `con_castle.png` — roughly
  28% the linear size, JPEG-ringed, on nearest-neighbour-upscaled source. With
  `location_size: 80` a single pin covers about 27% of that castle's width.
  Re-encoding cannot help; the source pixels are not there.
- **The logic is the standard-overworld logic.** `scripts/logic.lua` branches on
  `shardHunt` and nothing else, and access rules come from the shared
  `locations/overworld.json`, so a No-Overworld seed is gated on vanilla
  ship/canoe/canal/floater reachability — for a mode with no overworld, whose
  canoe and floater are not vehicles at all.
- **Mode detection already works and drives nothing.** `flag_mapping.lua:246`
  reads `GameMode` and prints a warning.

### The shape of the fix, not yet a plan

The poster tries to be a connection diagram and a marker surface at once and is
poor at both. Splitting those is the move, and only the first half is settled:

- **Marker surface** — done, above: the dungeon maps the pack already ships,
  carrying the markers that were already placed.
- **Connection diagram** — a hand-drawn pseudo-overworld: one map arranging the
  areas geographically with the fixed links as roads, in the pack's own art
  style rather than the poster's screenshots. Not started.

  A static map is the right shape because the topology is fixed, and that is
  now checked rather than assumed. Three No-Overworld seeds generated at
  different seeds carry 157 links each, and the only differences between them
  are the Gaia gateway's destination and where the two Waterfall staircases
  sit — the two things `MetroidVaniaMap.cs` rolls. The other ~154 links are
  identical across every seed, so they can be drawn once. The three
  Cardia/Bahamut gateways want a `?` rather than a destination.

  PopTracker map tabs are a static image plus pin coordinates — there is no
  drawing surface — so anything generated per seed belongs in `tools/doormap.py`,
  not the pack. Deriving the pin coordinates from the same layout that renders
  the art is the thing worth insisting on: hand-placed pins are what let the
  poster's markers drift off its art in the first place.

Open questions before any of it: does the logic need a No-Overworld branch (the
75-link table is fixed, so it *can* be modelled), and should the variant be
auto-selected from `GameMode` rather than picked by hand.

## Designed, not started

- **Entrance markers.** The data half is done: `tools/entrance_graph.py` reads
  the whole shuffle off the cartridge. The display half is designed end to end —
  the bridge watches party position (`ow_scroll` `$27/$28`, `sm_scroll`
  `$29/$2A`, the party is always 7 tiles in) and publishes an edge log, so the
  pack learns the permutation by observation and reveal-on-visit cannot spoil.
  The 0.32.0 floor it wanted is in the manifest already. Staged; the first
  useful increment is the log plus a console print.
- **Trap tiles on the map tabs.** FFR randomizes them and the tracker does not
  show them. Shares its whole tile-to-pixel path with entrance markers, on a
  much smaller blast radius.

## Known wrong

- **Titan has no box.** The code `titan` is already taken by `ruby` stage 2, so
  a Locations-grid cell needs a new hosted toggle under a different code. It
  would be a bridge-only cell: Titan is not an AP location either (see below).
- **17 maps have no markers.** 16 are uncalibrated; `ConeriaCastle2F` is a
  calibration alias away from working.
- **The incentive defaults are still a guess** on a version with no schema.
  The warning light says so, but the toggles themselves stay on whatever
  `scripts/init.lua:73-90` set. They cannot simply be cleared: an
  Archipelago-only player never receives a flag string at all, since only the
  bridge publishes one, so an empty default board would be wrong for every AP
  session. The guess is more visible than it was: it now decides which pins are
  gold and which are blue, rather than which ones exist.
- **`hide unreachable locations` still hides a skipped slot that is out of
  logic.** PopTracker drops an unreachable pin before anything gets to say it is
  blue, and red outranks blue by design. Nothing to do in the pack; worth
  knowing if that setting is on.
- **`shopItem`** is the one Locations-grid cell with no incentive toggle behind
  it and no FFR flag mapped to it, so it is never blue and never gold.
- **`locations/NOverworld/incentives.json` has no marker validation.**
  `tests/test_maps.lua` walks the standard tree and the board, not that one, so
  a marker off its art there would not be caught. `tests/test_incentives.lua`
  covers its rules and its slot table, which is the half this change touched.

## What Archipelago can and cannot tell the tracker

Worth writing down, because "bring AP to parity with the bridge" sounds like
pack work and is not. The AP feed carries checked locations in the multiworld
pool and items received, and nothing else: `worlds/ff1/__init__.py:123`'s
`fill_slot_data` returns an empty dict. So chests outside the pool, orbs lit,
turn-in stages, the current map, the seed's flags, the cartridge's identity and
the run clock are all unavailable over AP by construction, not by omission here.
Closing that gap means changing the Archipelago world, not this pack. The
reconcile core already does the right thing with what exists — takes the union
of both feeds and lets either run alone.

The traffic used to run the other way in exactly one place — the Chaos goal
flag, which only an AP seed carries. It no longer does: the bridge reads the
kill out of the battle engine, so a solo seed reports the goal too.

**Eight NPCs are not AP locations at all.** This used to be filed under "known
wrong" as missing `LOCATION_MAPPING` rows for Garland (514), Dr Unne (523) and
Bahamut (526). Adding rows for them would map to ids the server never sends. An
AP location id is `512 + ObjectId` (`FF1Lib/Items.cs`), and
`worlds/ff1/data/locations.json` — identical in all three vendored Archipelago
clones — holds exactly fourteen ids above 510:

    513 King        516 Bikke     518 Elf Prince   519 Astos
    520 Nerrick     521 Smith     522 Matoya       525 Sarda
    527 Lefein      529 CubeBot   530 Princess     531 Fairy
    533 Canoe Sage  767 Shop Item

The gaps are the NPCs that hold no shuffled item: Garland (514), Princess1
(515), ElfDoc (517), Unne (523), Vampire (524), Bahamut (526), SubEngineer
(528) and Titan (532). Lighting them from RAM only is correct, not a hole.

## Open questions

- `smith $6209` reads `0x05` and `fairy $6213` reads `0x04` on a live seed —
  both have the chest bit set with the event bit clear, while their rules test
  `0x02`/`0x03`. Probably fine, since that is chest `$09`/`$13` rather than the
  NPC. Unproven; one before/after read across a turn-in settles it.
- The four Fiends and the ToFR refights cannot be autotracked at all. They are
  spiked battle tiles that write no flag in vanilla or FFR, and the orb byte —
  set by stepping on the altar, not by the kill — is the only proxy. Any box for
  them would be manual-click forever.
