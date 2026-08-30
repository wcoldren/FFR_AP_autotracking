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
- Map tabs follow the player. On the shipped hand-drawn art, 36 of 53 dungeon
  maps are calibrated and carry per-chest markers; on art redrawn from a
  cartridge, all 61 do, because those markers are built from the ROM's own
  chest tiles rather than moved from a hand-solved pixel.
- Redrawn maps are cropped to the part of each floor that is actually map and
  filed by the cartridge's game mode, so a standard tracker and a No-Overworld
  one each show their own set. `tools/regen_maps.py` keeps both in one override
  tree.
- Offline tools that read a cartridge directly: the flag decoder, an
  entrance/floor shuffle reader and router, an HTML door map, an overworld
  reachability walk, a map renderer that can draw the NPCs standing on a map,
  and a logic checker that diffs the pack's access rules against FFR's own
  spoiler. The map-reading half of that was wrong until
  2026-08-29 — see "Read the maps from the bank FFR actually puts them in"
  below.
- The door map is walkable by clicking. Every floor name on the page is a
  `#map-<id>` link, and a focus panel driven by `hashchange` lists that floor's
  ways in and staircases on, so you follow the shuffle a room at a time instead
  of scrolling two tables; Back retraces. Works the same on a No-Overworld
  cartridge, which is the point — the mode shuffles through the same teleport
  tables the page already reads.
- An all-items reachability oracle in `entrance_graph.py --self-check`: holding
  every item, all 61 maps must be reachable from the doors. A theorem on
  No-Overworld and only there, since `MetroidVaniaMap.cs` connects all 61 and
  drops none, so a map the walk cannot find is the tool's own fault. It is the
  cheapest test of the whole routing stack -- map decompression, tile
  properties, both teleport tables, the doors and the gates all have to be right
  at once. Written down after the bank bug below and never run until now -- and
  it earned itself immediately, by failing on its own stated invariant. See
  "The gauntlet the mode skips" below.
- `tests/run.sh` — 13 Lua suites, no emulator or ROM needed. `tools/tests/run.sh`
  — the cartridge-reading tools' own tests, Python and nothing else; the ones
  that need a cartridge skip unless `FF1_ROM` points at one.

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

## Three things the door map was wrong about

Found 2026-08-29 while working out what a per-floor view of the shuffle would
have to say. All three were survivable only while the same facts stayed spread
across two tables and nothing had to state a single floor's ways in and ways on
out loud.

- **It counted 30 doors on a cartridge with 9.** The live/unchanged counts
  filtered on FFR's spare pair (30, 31) rather than asking `Graph.starts()`
  which rows are entrances. No-Overworld swaps the overworld for an ocean stub
  with nine pads, so 23 rows keep an ordinary map byte and no tile anywhere; the
  page counted them as doors. It now asks `starts()` — the same rule the router
  uses — and tags the other 23 *not on the map*.
- **A gated staircase was invisible.** The walk only ever listed links it could
  take, so every floor behind the Rod plate or a locked door looked like a dead
  end rather than a floor with a locked half. All the staircases on every floor
  you can stand on are listed now, the unwalkable ones marked `gated`.
- **Two staircases were the tile under your feet.** `reachable_teleports` drops
  the tile it starts on — correct, since stepping onto a teleport is what takes
  you off the floor — so Coneria Castle 2F's way down and Ice Cave B1's hole to
  B3 came out gated on every seed. You can step off and back on; they report
  0 steps.

The page also had no `<meta charset>`, so its em dashes and arrows mojibaked in
any browser that opened it as a local file — which is how it is meant to be read.

Checked by re-deriving the whole page from the cartridge and diffing it against
what the page claims: live doors against `starts()`, the staircase set tile by
tile against `teleports()`, every destination and landing against the teleport
tables, and every `#map-<id>` the page can emit against the map table. Four
cartridges including the No-Overworld one, all clean.

## Next

1. **The NOverworld overhaul.** Its own section below; this is the focus. The
   gate half of the logic branch is done and verified on a real cartridge -- the
   router stops at the gate NPCs now. What is left is deriving the No-Overworld
   pseudo-map's own pins -- the 28 in `locations/NOverworld/incentives.json`,
   which sit on `nooverworldmap.jpg` -- from the cartridge rather than
   hand-authoring them.

   This used to name `locations/NOverworld/overworld.json`, which did not exist
   then and now exists meaning something else entirely: the No-Overworld copy of
   the *dungeon* tree, generated by `regen_maps.py`. Nothing about that file is
   hand-authored or outstanding.

   Seeds live in `~/Downloads/FFR_duck_10*/`; `F258553F` is the one every
   measurement in this document was taken against. `FF1_ROM` points the tool
   tests at a cartridge, and they are strictly stronger with a real seed than
   with the vanilla image.

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
  ids `0x41-0x8B`, at `:458-776`. 54 of the 61 maps are wired into it. The other
  seven are the Temple of Fiends Revisited gauntlet, and they are genuinely
  dropped -- see below. This document said "all 61, none dropped" until
  2026-08-29, when the reachability oracle was run for the first time.
- **Deterministic apart from three things**: the three Cardia/Bahamut one-way
  gateways are permuted across Waterfall / Ice Cave B1 / Gaia (`:726`), the
  Waterfall stair positions, and which ToFR chest ids the two bonus chests
  reuse. None of it reaches the spoiler log, so the cartridge is the only
  source. On the duck seed, Bahamut is behind Gaia.
- **The gates are NPCs standing in corridors**, and FFR's own logic model says
  which item each wants — `Sanity/SCMap.cs:218-226`, the authority worth using
  over the dialogue, which is deliberately misleading. `NoOW_Floater` (three
  barrier NPCs, on Coneria Castle 1F, Castle Ordeals 1F and Ice Cave B1) wants
  **Floater**; `NoOW_Canoe` (Crescent Lake, Elfland Castle, Castle Ordeals 1F)
  wants **Canoe**; `NoOW_Chime` (the Gaia robot, Gaia to Mirage) wants
  **Chime**; `Talk_Nerrick` wants **TNT**. CROWN and KEY gate tiles as usual.
  Ship and bridge are free.

  The renames are cosmetic and only two items get one: `ItemsText[Floater] =
  "SIGIL"` and `ItemsText[EarthOrb] = "MARK"` (`:844`). So SIGIL is the Floater,
  but **MARK is the Earth Orb, not the Canoe** — this document said otherwise
  until 2026-08-29. The Canoe NPCs' dialogue talks about "Lukahn's mark" and
  that is flavour; the item their routine checks is the Canoe. Nothing here is
  a new tracker code: the pack already tracks every one of these gates.
- The full shuffle runs only with `Entrances` or `Towns` set; the stock preset
  ships both off, so a default seed uses the fixed table.

### The gauntlet the mode skips

Found 2026-08-29, the first time the all-items reachability oracle was run
against a cartridge. It failed, and it was right to: seven maps cannot be
reached from the doors holding every item -- the Temple of Fiends Revisited
floors 1F, 2F, 3F, Earth, Fire, Water and Air.

Not a bug in the walk. The cartridge really does orphan them:

- On a **vanilla** cartridge `TempleOfFiends (20,17)` carries both a
  `TP_SPEC_4ORBS` special and a normal teleport. That pair is the time warp:
  the special gates the step on the four Orbs, the teleport moves you.
- On a **No-Overworld** seed the special is **stripped** and the teleport points
  straight at `TempleOfFiendsRevisitedChaos`. The mode skips the gauntlet and
  drops you at the Chaos fight.
- Nothing else on the cartridge teleports into those seven, of any teleport
  kind, and `MetroidVaniaMap.cs` gives them a backdrop (`:942-948`) and a
  tileset (`:1108-1114`) but no entry in its teleporter table. The chain runs
  1F -> Earth -> Fire -> Water -> Air -> Chaos and 1F -> 2F -> 3F, all of it
  flowing toward Chaos, with no way in.

So the oracle's invariant was wrong as first written, not the cartridge. It now
excepts those seven by name and checks the reason instead of waving it through:
Chaos's own room still has to be reachable, since the shortcut is what makes the
seven unreachable. A seed that wires the gauntlet up passes too -- an excepted
map being reachable was never the failure.

Worth keeping: the oracle's first real run corrected a claim this document had
been making for weeks. Cheap tests of stated invariants find the invariants that
were never true.

### Version drift, and why it is not the thing to worry about

Measured 2026-08-29 rather than guessed, because all of this is being built
against 4.9.2 (the practice seed) while the tournament runs 4.9.7.

Diffing the vendored FFR from the commit that first stamped 4.9.2 (`371e38ed`,
Nov 2025) to 4.9.8 (May 2026) — six releases — the whole No-Overworld surface
moved by **one line**:

    FF1Lib/MetroidVaniaMap.cs | 3 ++-
    FF1Lib/Sanity/SCMap.cs        unchanged
    FF1Lib/Teleporters.cs         unchanged
    FF1Lib/StandardMaps.cs        unchanged
    FF1Lib/Enums.cs               unchanged

and the line is `ApplyMapMods(..., LefeinSuperStore && ShopKillMode == None)` —
a shop flag, not topology. The 75-link table, the gate NPCs and the map indices
did not move at all.

So the volatile surface is the **flag string**, not the maps, and that already
has its mechanism: `tools/ffr_flags/gen_schema.py` regenerates a version's
schema from an FF1Lib checkout plus a real ROM, writing both
`schemas/<v>.json` and `scripts/flags/schema_<v>.lua`, and proves itself — the
decode has to end exactly on the build SHA with nothing left over. Schemas ship
for 4-9-2 and 4-9-7; anything else lights the unread-flags warning rather than
passing defaults off as the seed's settings. A 4.9.9 seed is one command.

The conclusion for the work below: **derive from the cartridge, transcribe
nothing from C#.** A derived rule set re-derives on a new version. That is the
version-proofing, and it is worth more than any amount of tracking upstream.

### The drift measurement, run rather than reasoned

Checked 2026-08-29 by generating a 4.9.8 No-Overworld seed and reading it with
the same tools. The vendored FF1Randomizer is 4.9.8, `FF1R/Commands/Generate.cs`
is a working CLI, and `FF1Blazorizer/wwwroot/presets/NOverworld.json` carries
`GameMode: 2` with Entrances, Towns and Floors all off -- the same settings the
4.9.2 practice seed was rolled with. So the two are directly comparable:

    4.9.2  F258553F   stairs=157  gates=8  empty-handed=45/61  links=124  walkable=117  all-items=54/61
    4.9.8  F2585540   stairs=157  gates=8  empty-handed=45/61  links=124  walkable=117  all-items=54/61

Identical, across six releases *and* a different seed. The ToFR finding holds on
both. That is the "derive from the cartridge, transcribe nothing" bet paying
out: nothing in the topology, the gate NPCs or the routing moved.

The flag string did move, which is the other half of the same story -- 4.9.8
adds `Tracker`, `ShowGoMode`, `ShowReminders`, `NoTristateSpoilers` and
`OrbGraphicsInResourcePack`, and drops `AfterHits` and `StartOfHits`: 568
properties to 571. A 4.9.8 seed genuinely cannot be read with the 4-9-7 schema.
`gen_schema.py` regenerated it in one command and self-verified, so the "a new
version is one command" claim holds too.

**No 4-9-8 schema is committed, deliberately.** upstream/master is 4.9.7;
4.9.8 is upstream/dev and unreleased. A schema records the build SHA it was
proved against and `ffr_flags.py:102` refuses on mismatch, so one keyed to a
local fork build would never match a real 4.9.8 seed -- it would be dead weight
that reads as support. Regenerate from the release checkout when 4.9.8 ships.

Two things worth knowing for anyone repeating this. A locally built FFR stamps
`beta-SHA`, not a version, because `FFRVersion.cs` has `Sha` and `Branch` as
placeholders that only FFR's own deploy substitutes; set `Branch = "master"` and
`Sha` to the checkout's HEAD to get a cartridge that stamps `4-9-8`. And the
fork the clone sits on (`ap-item-text`) does not touch `FF1Lib/Flags.cs`, so the
flag layout it produces is upstream's.

### Where the pack stands against that

- ~~**Both map variants define exactly one tab.**~~ Fixed, commit `17c423d`.
  The dungeon tree moved to `layouts/shared.json` as three `shared_*_tabs` keys
  and all four map layouts reference it, so the NOverworld pair gained 51 maps
  and standard/shardHunt stopped carrying a byte-identical copy each. Expanding
  the references reproduces their previous trees exactly. The 282 markers in
  `locations/overworld.json` now have somewhere to draw, and `maptab.lua`
  follows the player into a dungeon on these variants too.
- **Maps can be drawn from the cartridge.** `tools/render_maps.py`, added
  2026-08-29, renders all 61 standard maps out of a ROM using the game's own
  tile art — CHR, tilesets and per-map palettes, in pure Python, no .NET and no
  extra dependency. It draws the *seed's* map, so the sealed walls, the 75 new
  staircases and both of the rooms No-Overworld builds inside Coneria Castle all
  appear, and it renders the eight towns the pack has never had art for. Every
  image is 64 tiles at 16 pixels, so tile *n* is pixel *16n* exactly and
  calibration stops being a thing that gets eyeballed. All 61 come to 2.3 MB,
  against 3.0 MB for the 53 screenshots shipping now.

  Nothing is committed from it: run it against your own cartridge. That keeps
  ROM-derived art out of the repo and is also the more correct option, since
  Waterfall's two staircases are rolled per seed.

- **And the swap is one command.** `tools/regen_maps.py FFR_seed.nes` renders
  the 61 maps, moves all 254 dungeon markers onto them, and writes maps.json
  entries and tabs for the ten maps the pack has no art for -- into PopTracker's
  `user-override/ff1_rando_ap/`, not the checkout, so the repo keeps shipping
  the screenshots and `--clean` puts it back. Every moved marker is checked
  against the cartridge's own chest tiles and `npc_positions.json` before
  anything is written. It caches: a second run on the same cartridge does
  nothing, and a new seed rewrites only the maps whose pixels differ -- 26 of 66
  files between two No-Overworld seeds.

  What this does *not* give you is the shuffle. Of the 56 maps carrying a
  staircase on seed `F258553F`, 21 draw differently from vanilla -- the sealed
  town walls and the new rooms. The rest are teleporters stamped on tiles that
  already looked like that, which no amount of redrawing will reveal. Those want
  the entrance markers below.

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
  canoe and floater are not vehicles at all. Counted: of the distinct rules in
  that file, roughly thirty are overworld geography — `ship`, `canoe`, `canal`,
  `airship`, `bridge`, `northernDocks`, `lefeinBridge`, `hwyOrdeals`,
  `gaiaMountain`, `melmondRiver`, `luffyDock`, `cardiaDock` — and mean nothing
  in a mode where ship and bridge are free.

  **The gates are readable off the cartridge now**, which is the half of a
  No-Overworld branch that had to come first. `entrance_graph.py --gates` reads
  the talk routine each object runs and reports which of the eight gate NPCs
  wants which item; `noverworld_gate_items()` is the same thing as a library
  call. It refuses to answer unless the eight sort into four routines wanting
  four items, so a standard cartridge says "no gate layout" rather than
  inventing one. Every gate is an item the pack already tracks — the mode needs
  new topology, not new codes.

  **And the router now stops at them.** `Graph.blocking_objects` blocked the Rod
  and Lute objects and nothing else, so it walked straight through a SIGIL
  barrier; it now also blocks whatever the cartridge's own talk table says is a
  gate. This is not an approximation of the mode. FFR routes its own seeds the
  same way: `Sanity/SCMap.cs:218-226` stamps `SCBitFlags.Floater`, `.Chime` or
  `.Canoe` onto the tile the NPC stands on, and :214 stamps `.Tnt` onto
  Nerrick's, which is the same shape as a Rod tile.

  The object-to-item map is read, not transcribed. `noverworld_gate_items()`
  settles which four routines are gates and what each wants; `gate_objects()`
  then asks the talk table which objects run them, so an object FFR hands a gate
  routine gets blocked whether or not it is one of the eight named here. On any
  other cartridge it returns None and the blocking set is what it always was.

  `--have` learned the four items, and takes `sigil` for the Floater, since that
  is the name on the item screen.

  **Verified on seed `F258553F`** (2026-08-29). The talk table reads at
  `$11:$8000`, all four routines sort, and the eight objects stand where
  `MetroidVaniaMap.cs`'s `SetNpc` calls put them -- `LefeinMan6` on Ice Cave B1,
  `LefeinMan10` on Castle Ordeals 1F, not the Lefein of a stock cartridge.

  What it changed on that seed: maps open empty-handed 47 -> **45**, and floor
  links called walkable 135 -> **117**. Eighteen staircases were being reported
  as walkable that a SIGIL, Canoe or Chime barrier actually blocks. The
  all-items reachable count is **54 before and after**, which is the check worth
  keeping: gates must not move that answer, because holding every item opens
  every gate. `test_gate_objects.py` asserts it, and tests a real seed as it is
  rather than synthesising a layout when FF1_ROM names one.

  One thing found on the way and deliberately left alone: `Talk_Nerrick` is the
  *vanilla* routine -- `MetroidVaniaMap.cs:833-834` leaves the `NoOW_Nerrick`
  assignment commented out -- and `SCMap.cs:214` gates it on TNT for every mode.
  So a standard cartridge's router walks through Nerrick too. Changing that
  moves standard-mode answers and belongs in its own pass.
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

## Ideas from playing on the rendered maps, not yet scoped

Raised 2026-08-29 after the first session on cartridge-drawn art. Recorded with
whatever is already known about each, so scoping does not start from scratch.
Nothing here is designed yet and the order below is not a plan.

- **Show the towns when you walk into one.** The first step, and the one the
  rest lean on. No-Overworld gives every town staircases, so a town is a room
  you route through -- but `MAP_VALUE` still calls maps 0-7 "Overworld" and
  `maptab.lua` sends you to the overworld tab. The tabs themselves exist, but
  only in `regen_maps.py`'s override, because the pack has no town art to put
  in them. So `MAP_VALUE` cannot simply name them: the base pack would then
  point at tabs it does not have, and `test_maptab.lua` would fail for the right
  reason. Whatever the answer is -- mode-aware `MAP_VALUE`, an override that
  ships its own `mapValues.lua`, town art committed after all -- it has to keep
  the standard variants pointing at the overworld.

- **Frame the map on where you are.** The tab shows a whole 64x64 map at one
  zoom and never moves. Two separate things:

  *Crop.* **Done 2026-08-29** -- see "Cropped to the map, filed by mode" below.

  *Follow.* PopTracker takes `Tracker:UiHint("Zoom <map>", "2.5")` and
  `Tracker:UiHint("Pan <map>", "x,y")` per map (trackerview.cpp:940-956) -- only
  since 0.34.0, which is part of why the manifest floor moved to 0.35.1. And
  the pack already drives `UiHint("ActivateTab", ...)` from `maptab.lua`. The
  bridge reads the party's position for the entrance-marker work below
  (`sm_scroll` `$29/$2A`, party always 7 tiles in). So following the party into
  the room it entered needs no new art and no new data -- it is the same hint
  channel that already switches the tab.

- **Insets, the way the hand art does them.** Three shipped maps are composites
  of disjoint pieces at unrelated offsets: `cardia` in 3 regions, `marshB2` and
  `seaB3` in 2. The calibration format already carries that, and `make_markers`
  already reads it, so a renderer that split a map into connected components and
  laid them out would reproduce the effect and also fix any map whose used area
  is two far-apart rooms with dead space between.

- **Routes drawn on the map.** Wanted in two flavours -- shortest to the exit,
  and one that collects the loot on the way -- and eventually per-map custom
  routes for towns, where the useful stops are shops and NPCs rather than
  chests. `entrance_graph.py` has the graph between maps; a route *within* a
  map is a different problem and would want walkability per tile, which
  `lut_OWTileset` gives for the overworld and the tileset property tables give
  for standard maps. Worth settling first whether the drawing surface is the
  PopTracker tab (a static image, so the route has to be baked into the art at
  render time) or `tools/doormap.py` (free to draw anything, but not in front of
  you while you play).

## Designed, not started

- **Entrance markers.** The data half is done: `tools/entrance_graph.py` reads
  the whole shuffle off the cartridge. The display half is designed end to end —
  the bridge watches party position (`ow_scroll` `$27/$28`, `sm_scroll`
  `$29/$2A`, the party is always 7 tiles in) and publishes an edge log, so the
  pack learns the permutation by observation and reveal-on-visit cannot spoil.
  The 0.32.0 floor it wanted is in the manifest already. Staged; the first
  useful increment is the log plus a console print.
- ~~**Trap tiles on the map tabs.**~~ Done 2026-08-29 -- see "The letters are
  drawn, in the cartridge's own font". It did share its tile-to-pixel path with
  the entrance markers still to come, and it found the font that any later
  annotation can now use.

## Sprites on the map

Finished 2026-08-29. The gate NPCs draw where they stand:
`tools/render_maps.py ROM --map 11 --objects` puts the SIGIL barrier in the
corridor on Castle Ordeals 1F instead of leaving it a line of `--gates` output.
`tools/sprites.py` is the library and the CLI; `tools/tests/test_sprites.py`
runs in `tools/tests/run.sh`.

The half that was open -- the sheet origin -- came from the engine's own path,
`LoadMapObjCHR` at `bank_0F.asm:$E99E`, not from sliding offsets. The graphic
id is added to the **high** byte of a pointer, so it is a page index: art for
graphic *g* is the $100 bytes (16 tiles) at `lut_MapObjCHR + g * $100`, and
`Constants.inc` puts `lut_MapObjCHR` at **$A200 in bank $02** -- not the
$9010 this document named, which is the player mapman art one band lower.

What makes that a derivation rather than another guess is that bank $02 turns
out to have no gap for a base to slide into. Three engine constants that know
nothing about each other meet exactly:

    $8000  LoadOWBGCHR          16 pages, the overworld's background tiles
    $9000  LoadPlayerMapmanCHR  12 pages, $9x00 where x is the lead's class
    $9C00  LoadOWObjectCHR       6 pages, ship / canoe / airship / bridge/canal
    $A200  lut_MapObjCHR        30 pages, one per ObjectSprites entry, ending
                                at $C000 -- where render_maps.py already reads
                                the background tileset CHR

12 + 6 pages from $9000 lands on $A200; 30 pages from $A200 lands on $C000.
Move the base a page either way and one of them breaks, which is the guard the
eyeballed origin never had. It is asserted at import and restated by
`--self-check`.

**The `0xF4` clue explained itself on the way.** Because the add lands on the
high byte and the carry out is dropped, a graphic id above the 30-entry enum
wraps the pointer into the rest of the bank -- deliberately. `$A2 + $F4 = $196`
truncates to `$96`, so `MIAB.cs:451` is drawing Chaos as the **Knight's
mapman**; `Party.cs:581`'s `0xEE-0xF9` are the twelve class mapmen at
`$9000-$9B00`, in class order. So the byte is neither a slot index nor a tile
number: it is a page, and the ids outside the enum are a door FFR walks
through. `sprites.py` names and draws those too.

**Tiles and palettes, both read the same way.** `DrawMapObject`'s four
construction tables (`bank_0F.asm:$E7AB`) spend a sprite's 16 tiles as four 2x2
poses -- down, up, left, left-walking -- each row-major, which is the reading
the earlier note had right. Facing right is facing left with every tile
flipped, so there is no right-facing art to look for. The tables' attribute
bytes are `$02` on the top row and `$03` on the bottom: **sprite palettes 2 and
3**, which live at **+$10** in the map's $30-byte palette block, between the
four outdoor BG palettes and the four "inside" ones `render_maps.py` reads at
+$20.

That offset is checked rather than assumed, by a coincidence that cannot
survive being wrong. `LoadMapPalettes` (`$D8AB`) copies all $30 bytes and then
overwrites `cur_pal+$12` and `+$16` with the lead character's mapman colours --
sprite palettes 0 and 1, the player's. Those two bytes are the only ones in the
whole block that are byte-identical on all 61 maps, because the engine always
replaces them. Palettes 2 and 3 vary map by map, and are blank on exactly the
maps that place no objects -- two unrelated tables agreeing. `--self-check`
tests all of that, and the test rejects the region read at +$00, +$08 and +$20.

Verified on seed `F258553F` plus two more FFR seeds and a vanilla cartridge:
0 problems, 182 placed objects. The three floater gates come back `Orb` and the
chime gate `Robot`, which is what `MetroidVaniaMap.cs:782-829` assigns them,
with neither side transcribed into the other.

**In the pack's own tabs too**, behind `regen_maps.py --npcs none|gates|all`
(default `none`, so nothing changes for anyone who does not ask). A flag rather
than a branch because the output lives in PopTracker's user-override tree,
which is not in git: a branch would mean a checkout plus a full regen to
compare, where the flag is one command and the cache rewrites only the maps
whose pixels differ. `--npcs` is part of the cache key, so switching modes
actually redraws.

### The pin does not let the sprite through, and now says so

Corrected 2026-08-29. This section used to say 289 objects are placed and **13
of them stand on a tile that already carries a marker pin**, and that "PopTracker
draws pins over the image, so the sprite becomes context behind the pin rather
than anything lost". Both halves were wrong, and the second one is why the first
was never checked.

**A pin is opaque.** `drawRect` fills the marker's interior with a solid state
colour (`uilib/drawhelper.cpp:15-56`; `StateColors` at `mapwidget.cpp:13-23`
carry no alpha), and `MARKER_SIZE` is `TILE_PX` -- exactly one tile, exactly a
sprite's size. Nothing reads behind it. A sprite under a square pin is not
context, it is invisible.

**And 13 was not the number.** `regen_maps.py` now computes it instead of anyone
counting by hand: **3 pins on a standard seed** (`C189A0EF`) and **2 on the
No-Overworld one** (`F258553F`) -- Dwarf Cave Smith and Nerrick on `dwarves`,
Sarda on `sarda`. Seven object tiles do coincide with a *marker tile*, but
Pravoka, Gaia, North West Castle and Matoya's Cave carry their pins on the
**overworld** map only and have none on their own art, so no sprite of theirs is
ever covered. Counting tiles instead of pins is what produced the larger figure.

**What is done about it**: a pin that lands on a drawn sprite is emitted as a
`diamond` rather than the default rect. `drawDiamond` is real vertex geometry, so
the tile's four corners stay unpainted and the sprite reads around the pin. Same
size, same centre, so the pin still marks its own tile and nothing moves. Per-pin
`shape` is supported from 0.26.2 against a manifest floor of 0.35.1, and diamond
does not clash with the trapezoid reserved for entrance pins.

The eight gate NPCs collide with nothing at all, which is what made
`--npcs gates` the conservative option: they are the ones with no marker of their
own. With the diamonds in, `--npcs all` no longer costs a hidden sprite, so the
conservative option is less needed than it was.



## The room floor was a hole, and the cartridge already knew

Found 2026-08-29 by looking at the unroofed maps in PopTracker: rooms came out
as white voids with the furniture floating in them, and an NPC drawn there
looked pasted on.

The first fix substituted the corridor floor into the blank cells, choosing the
tile by a vote over a six-tile radius. It looked better and it was the wrong
mechanism -- a guess, where the cartridge had the answer. Replaced the same day.

**Ask the rendered tile whether it is blank, not the palette.** `roof_palettes`
tested whether a sub-palette's three non-background colours were equal, which
finds a room's *furniture* and not the floor between it. Coneria Castle 1F's
room floor is tile `$04` on sub-palette 1 -- `0F 30 30 10`, not a flat palette --
yet every pixel of that tile is `$30`, so outdoors it draws flat white. It was
never a roof cell, so unroofing never touched it.

The tile itself settles it: `$04` draws **flat white outdoors and flat black
inside**. That is exactly what the shipped hand-drawn art shows -- DarkmoonEX's
`con_castle.png` draws both throne rooms as black floor with orange furniture,
and `marshB1.png` does the same. So there is nothing to invent and no substitute
to choose. Swap the cell to the inside palette and the cartridge draws the room.

`hidden_cells()` replaces `roof_palettes` + `room_cells` + `room_floors`, and
runs **both** tests, each size-guarded on its own components, then unions them.
Neither may define a region alone, and the two ways that goes wrong were both
found by asking that question -- *closer to the original maps, or farther?*

- **Art test alone** admits enough extra cells that separate rooms merge into
  one region, which then fails the size guard and closes rooms the palette test
  had open. Temple of Fiends Air went 241 cells -> 1. Five maps regressed.
- **Palette seed, then flood through art-blank cells** runs away, because a room
  can touch a wall that is also art-blank.

6360 cells on the union, no map opening less than the palette test alone, and
**zero walkable cells left drawing flat white** -- which is the measurable form
of "closer to the shipped art", since DarkmoonEX never draws one.
`test_room_floors.py` asserts both directions: the white-void count and
"every room the sub-palette finds stays open".

### Still open: a room bigger than the guard

Mirage Tower 1F's interior is **458 cells** -- rows 3-26, cols 4-27, 338 of them
walkable, drawing flat orange outdoors and pillars inside. It is a real room and
the shipped `mirage1F.png` draws it open with its eight chests. `ROOM_MAX_CELLS`
is 256, so it stays shut. This is not a regression -- it was shut before any of
this work too -- but it is visible now that everything around it opened.

Raising the cap is not the answer: the same test finds Waterfall's 1820-cell
floor, Volcano B3's 2102 and B4's 2650, which are open floor and must stay
closed. Three discriminators were tried and all three failed:

- **walkability** -- the big palette components are 100% walkable too; they are
  the out-of-bounds backdrop;
- **door adjacency** (`TP_SPEC_DOOR`/`LOCKED`/`CLOSEROOM` on the boundary) --
  no blank region touches one, including regions that certainly are rooms;
- **size**, which is the knob we already have and which cannot separate 458
  from 389.

**The engine's own answer, read rather than guessed at** (2026-08-29). `inroom`
is a *single global byte* at `$0D`. Stepping on a door tile sets it
(`SMMove_Door`, `bank_0F.asm:3486`); stepping on a close-room tile clears it
(`:3430`); and while it is set the **entire** background palette comes from
`inroom_pal` (`:5879-5883`). The engine has no per-cell notion of a room at all
-- it never shows a room open and the outside closed at the same time. Unroofing
is our invention, so there is no per-cell logic to borrow.

But the *transition* is tile-driven, and that is derivable: a room is what you
can walk to from a door tile without crossing a close-room tile. Flooding that
way separates room from open floor where every proxy failed:

    map           doors  close   flood      the size guard said
    mirage1F        2      2      353 cells   458, rejected -- its interior
    waterfall       1      1       13         1820, rejected -- correctly
    volcB4          6      6       87         2650, rejected -- correctly
    con_castle      6      6       50         44 opened

**Why no property of a tile can settle this.** Waterfall's room floor is tile
`$46` on sub-palette 1: flat cyan outdoors, flat black inside -- structurally
identical to Coneria Castle's `$04`. And `$46` is *also the open water outside
the room*, 1820 cells of it across the map. The same tile, the same two bytes,
is room floor in one place and outdoors in another. So flatness, walkability and
size are all being asked a question the tile cannot answer; only the room
boundary can, which is what the door flood reads.

A caution about the comparison itself, learned by getting it wrong here. I read
the shipped `waterfall.png` as showing that room's floor black where ours draws
it cyan, and called it a defect. The judgement came back that waterfall
renders correctly, and that is right: the black there is largely DarkmoonEX's **annotation
panel** -- the `1 2 3 4 5 6` chest numbering, the trap-tile key and an NPC drawn
into the room's dead space -- not the map's floor. The reference art is a
specification *and* a drawing, and the two have to be told apart before a
difference counts as evidence.

The guess that ToFR Air's 241 cells were teleporters is out: 240 of them are
tile `$3F`, pure black under *both* palettes -- out-of-bounds void, so opening
them is a visual no-op. Of the 2545 cells the union opens and the flood does
not, 869 are invisible in exactly this way; the 1676 that are visible are led by
Waterfall's water.

**Swapped in 2026-08-29**, unioned with the two tests above rather than
replacing them, and grown into the wall the room is enclosed by -- `inroom` is
global, so standing in a room the engine draws the whole screen from
`inroom_pal`, walls included, and the shipped art follows it. Growth crosses
only cells that are not walkable and that draw differently under the two
palettes: not-walkable stops it running out across the floor, and
drawing-differently stops it at the out-of-bounds void. 35363 cells, zero white
voids, every suite green on three seeds and the vanilla cartridge.

**A large fraction opened is not evidence of a leak.** Growth opens 3695 of
Dwarf Cave's 4096 cells, and this document called that a runaway on the cell
count alone. A look at the render said otherwise, and it was correct: the cave is entirely
indoors, so nearly all of it *is* one room in the engine's terms, and what was
still wrong there was the opposite -- its interior walls drawing as roof. Twice
in one session a proxy metric condemned output that the reference art vindicated.
See [[closer-or-farther-from-the-reference]] in memory.

**Still not subsumed:** On 49 maps the
current union opens cells the flood does not -- Temple of Fiends Air 241,
Waterfall 370 -- and ToFR Air has exactly one door tile, so its 241 cells are
something other than a door-room. Understand what before replacing the rule.
Doors and close-room tiles pair 1:1 on every map checked, which is a good sign
the reading is right.

The lesson worth keeping is the same one the map-bank bug taught: the wrong
mechanism produced a *better-looking* result than the bug, which is exactly why
it survived a look. What caught it was reading the shipped art as a
specification instead of as a coordinate surface.

## Cropped to the map, filed by mode

Both landed 2026-08-29, as one change, because they are the same piece of
plumbing: a crop is a per-map offset, a mode is a per-map path, and every
dungeon marker's pixel depends on both.

**The crop.** A 64x64 render is mostly not map -- the filler is one tile
repeated, the out-of-bounds void in a dungeon and the warp-out field around a
town. `content_box()` floods that tile inward from the edge of the grid and
takes the bounding box of what the flood cannot reach, padded a tile. Mean 48%
of the grid survives. Mirage Tower 1F stops being a 33x33 corner of a
1024x1024 image.

Flooding rather than testing `tile == filler` is the point. Waterfall's `$46`
is the open water outside the map *and* the room floor inside it -- the same
tile, the same two property bytes -- which is the fact that defeated every
per-tile test the room work tried. The wall stops a flood; it does not stop a
comparison.

**The hand-drawn art is what says the rule is right.** On the 30 maps
`map_calibration.json` covers, the derived box lands within one tile of the box
DarkmoonEX drew on 22 of them and exactly on `tofrAir`. Nothing was tuned to
make that happen: the rule knows only the border tile. The rendered images come
out the size of the drawn ones -- `con_castle` 1024x560 against 1074x605,
`nw_castle` 528x512 against 544x442, `mirage1F` 528x544 against 545x580.

The guard is that the box cuts nothing off: every chest tile, every NORM/EXIT
teleport and every tracked NPC has to survive it. Zero violations on three FFR
seeds, a fourth, and a vanilla cartridge. WARP teleports are excluded because
they *are* the filler -- 30875 of them on one cartridge, the field that
surrounds every town. The Ice Cave B1 fairy is what gives the guard teeth: it
stands on a cell the flood reaches, so only the box keeps it.

**One map is knowingly loose.** Matoya's Cave carries four cells of tile `$0B`
at (20-23,13), detached, out in the void -- vanilla map data, present on any
ordinary seed, removed only by No-Overworld's rebuild. They stretch the box
seven columns past where the art stops. No filter was added: the speck is fully
walkable while `sky4F`'s six real 88-cell platforms are not walkable at all, and
it is 4 cells where `iceB3`'s genuine second region is 41, so neither
walkability nor size separates junk from content. Inventing a third proxy is
how the room-floor rule went wrong twice.

**A Map Key band is reserved, not drawn.** Trap letters derive: enumerate the
fixed-formation trap tiles (`TP_SPEC_BATTLE`, byte 1 not the random marker) over
all eight tilesets in order and label them A, B, C. On a *vanilla* cartridge
that reproduces the shipped art exactly -- `earthB1` comes out `{G,H,I}` and
`volcB4` `{M,N}`, and `volcB1`'s bare `A` correctly is not a trap letter. 23 of
61 maps use one and no map uses more than four, so the band below the map is
small and bounded. Which branch decides byte 1 is read rather than assumed:
`SMMove_Battle`'s `BPL` sits at 0x0DC5 in the fixed bank, `$10` on a vanilla
image and `$D0` on an FFR one.

**Filed by mode.** A No-Overworld cartridge and a standard one disagree about
34 to 39 of the 61 maps; two standard seeds still disagree about 2 to 7 (the
Ordeals floor shuffle, the ToFR shuffle, Gaia). The override tree used to hold
one set with no record of which cartridge drew it, so a standard tracker showed
No-Overworld staircases. Art now goes to `images/maps/std/` or
`images/maps/nov/` by the cartridge's own `GameMode`, with a `maps.json` naming
the first and a `NOverworldMaps.json` naming the second -- the mechanism the
single "incentives" row already proved, at full size. A mode never rendered
falls back to the pack's own art rather than to the other mode's. An unreadable
mode stops the run instead of guessing, because art filed wrong looks
completely normal and is wrong about every staircase.

**Markers are built forward now.** `remap_locations()` used to take each
committed marker's pixel, invert it through `map_calibration.json` to recover a
tile, and re-emit it. That inversion is why redrawing depended on hand-solved
offsets at all, and with it the two things that have blocked entrance markers
and the missing tabs: the sixteen uncalibrated maps, and the composites whose
image holds different tiles than their `rom_map_id` names. `place_locations()`
builds from the cartridge's own chest tiles plus `npc_positions.json`, joined to
the tree through `location_mapping.lua` (AP id below 512 is chest `id - 256`).
Both blockers are gone by construction -- a position that was never a pixel
cannot need a pixel-to-tile rule.

It also reads the seed rather than a snapshot, and that showed up immediately:
on an ordinary seed the ToFR shuffle places five chest ids on a *second* floor
apiece, which `chest_positions.json` (vanilla-derived) never knew. `tofr1F` and
`tofrWater` now carry markers where they had none. 239 of the 244 marker-bearing
locations reproduce their committed tiles exactly; those five are the difference.

Because the crop makes the same tile a different pixel in each set, the dungeon
tree splits too: `locations/NOverworld/overworld.json` is a real file now, which
is the slot `init.lua` used to load and that had never existed.
`tests/test_maps.lua` check 6 compares the two trees location by location, so
they cannot drift apart -- two files meant to agree and never compared is
exactly how the missing one survived.

**Upgrading an override written before this.** The v1 layout put all 61 images
at `images/maps/<name>.png` and had no `locations/NOverworld/overworld.json`, so
once `init.lua` started asking for that file the No-Overworld variants fell back
to the pack's hand-art coordinates and drew every box off its chest. `load_cache`
returned `None` on a version mismatch, which meant those files were never
overwritten either. It now reads an older cache anyway and clears the files it
lists -- only files this tool recorded writing. Re-running `regen_maps.py` is
the whole upgrade.

**The marker boxes had to shrink with it.** `location_size` is in image pixels
and the pack's 24 comes from the hand-drawn art, which PopTracker shows at
roughly its drawn size. A cropped render is a third of the area it was, so it
gets scaled up and the box scales with it -- the same fraction of a tile, twice
the pixels on screen. Rendered maps now use 16, which is exactly one tile and so
outlines the tile the chest is on and nothing more, with a 2px border.
`--marker-size` and `--marker-border` tune it, and both are part of the cache
key so changing them actually rewrites. Hand-drawn art keeps its 24.

**The fallback is easy to mistake for a failure.** Render only one mode and the
other mode's variants show the pack's hand-drawn art -- which looks exactly like
the tool having done nothing, and did on the first upgrade run. `regen_maps.py`
now ends by saying what each tracker variant will open, so the answer is not
"recognise a staircase". Two seams while only one mode is rendered: the nine
maps with no hand art at all (the towns, Coneria Castle 2F, Bahamut's Lair B2)
have nothing to fall back *to*, so they keep whatever `maps.json` gave them --
the other mode's art -- and the dungeon markers come from the repo's committed
tree, which is placed for the hand art. Both disappear the moment that mode is
rendered, and there is no third option: PopTracker has no way to unregister a
map, so those nine either point at the other mode's art or at nothing.

**The one number both halves depend on** is the crop box: the art is drawn from
it and every marker is measured from it. It is computed once in `main()` and
handed to both, and the produced image's actual size is checked against what the
markers assume before anything is written. If the renderer ever starts padding
or centring differently, that is where it surfaces -- not as boxes sitting
beside their chests in PopTracker. `test_crop.py` asserts the same formula from
the other side.

**Still open here.** `maptab.lua` still sends maps 0-7 to the overworld tab, so
it will not follow you into a town even though the town tabs now exist. The band
is no longer empty -- see "The letters are drawn, in the cartridge's own font".

**Found on the way, and fixed.** `tools/tests/test_gate_objects.py` failed
against any *standard* FFR cartridge. Not for the reason it looked like -- the
test already synthesises a gate layout for a cartridge that has none -- but
because it wrote that layout to the **vanilla** talk jump table at `$0E:90D3`
while the reader asks `talk_routine_bank()`, which on an FFR cartridge answers
`$11:8000`. FFR leaves a complete, well-formed, vanilla copy behind at the old
address (`Dialogues.cs:137` bulk-copies the region), so the write did not fail:
it landed somewhere nothing reads. The same shape as the standard maps left
behind in bank `$04`, and the third time that pattern has bitten in this tree.

It passed on the vanilla image and on a real No-Overworld seed -- the two cases
where the vanilla address happens to be the live one, or where nothing had to be
written at all -- which is exactly why it went unnoticed. It now asks
`talk_routine_bank()` the way the code under test does, and all five cartridges
here pass, with the standard seeds genuinely exercised rather than skipped.

## The letters are drawn, in the cartridge's own font

Finished 2026-08-29, phase 3 of the rendered-map order. The reserved band now
carries a `Map Key`, and every fixed-formation trap tile is lettered where it
stands.

**The font is read, not drawn.** There is no Pillow in these tools and there is
now no hand-made bitmap font either. `LoadMenuCHR` (`bank_0F.asm:9856-9863`)
swaps in `BANK_MENUCHR` -- `$09`, `Constants.inc:84` -- points at `$8800` and
loads `LDX #8` rows to PPU `$0800`; `CHRLoad`'s own header says a row is 16
tiles (`bank_0F.asm:9797`). So the menu CHR is the `$800` bytes at `$09:8800`,
128 tiles, the first 62 of which are `0-9`, `A-Z`, `a-z` in that order.

What makes the base a derivation rather than a slid offset is that two sources
that know nothing about each other give the same numbers. `LoadMenuCHR` writes
the art to PPU `$0800`, so its first tile is background tile `$80`; FFR's own
encoding table independently says the byte that prints `0` is `$80`, `A` is
`$8A` and `a` is `$A4` (`FF1Lib/FF1Text.cs:174,184,210`). Those are exactly
`TEXT_BASE + CHARS.index(ch)`, and `tools/font.py` asserts all seven at import.
`test_font.py` adds the negative half: a base one tile or one row out has to be
*rejected*, not merely look worse.

`0` and `O` are one glyph in this font. That is the font's own property, not a
bad base, and it is asserted as such so nobody tightens the check into "all 62
must be distinct" and breaks it.

Verified on six cartridges -- vanilla, three duck seeds and two more -- 0
problems each.

### Our letters are not DarkmoonEX's, and cannot be

Settled 2026-08-29 by reading the FFR wiki's Appendix D in a browser -- it is a
single-page app and serves nothing to a plain fetch. The page is DarkmoonEX's
own, last edited 03/2026, so it is the current form of the same maps this repo
ships an older copy of.

The previous note here said sets matched and left the ordering open. The wiki
closes it, and the answer is that there is nothing to match.

**Our labelling diverges, and the art is self-consistent.** On `earthB1` the
wiki draws the wall cluster as `IHH / HIH / II / HH / II / HH / II / HIH / IHH`
-- nine rows, structurally identical to ours tile for tile, with `G` and `I`
swapped -- and puts `G` on the three singleton tiles. `Earth B2`'s key then says
`Trap Tile G` for the very tile we call `I`, so the art agrees with itself
across two maps and it is ours that differs. `Volcano B5` (which the pack ships
as `volcB4.png`) agrees with ours exactly: `M` on tile `$23`, `N` on `$2F`.

**No sort key produces both.** The art requires tileset 2 to run
`$1D, $1C, $1B, ..., $23, $2F` -- the first three descending, everything after
ascending. All nine of those tiles carry byte 0 `$0A`, so the property byte
cannot be the key, and their formation ids (`$21, $1F, $1E, ... $28, $29`) do
not sort into that order in either direction. Tile id, formation id and map
reading order were each checked against both maps; each fits one and breaks the
other.

**Because they are hand-assigned, not computed.** `waterfall`'s key reads
`Trap Tile BB`, which is a sequence that went `A`...`Z` and then started
doubling -- a person keeping a list as they drew dungeon after dungeon, giving
Earth Cave `G H I` and Gurgu Volcano `M N` as contiguous per-dungeon blocks.
There is no rule in the cartridge to recover.

**And matching them would be wrong anyway.** DarkmoonEX's letters describe
*vanilla*. FFR changes which trap tiles carry a fixed formation, so on the duck
standard seed `earthB1` derives `F G H` where vanilla gives `G H I` -- his
labels do not describe that cartridge at all. Ours are read from the cartridge
in front of you and are therefore right for it, which is the property that
matters for a tracker rendering that seed's own art. The key drawn on a map
always lists the letters drawn on that map, so the image is never
self-contradictory.

What this costs: our `G` is not necessarily his `G`, so a letter is not a shared
vocabulary between our art and his guide. Worth knowing before quoting one at
another player. `test_crop.py` asserts `volcB4`'s assignment per tile rather
than per set, which is the case where the two do coincide.

## One fingerprint for two modes marked the other one current

Found 2026-08-29 while rendering the Map Key into both trees: the No-Overworld
run said `nothing to do` immediately after the standard run, and its band was
still a flat slab of backdrop.

`.regen_cache.json` kept `inputs` -- the fingerprint of the pack and these tools
-- once for the whole tree, while `rom`, `npcs` and `marker` were already per
mode. So regenerating either mode stamped the new fingerprint over both. The
other mode's art stayed on disk exactly as the older tools drew it, and its next
run compared that shared fingerprint, found it current, and did nothing. Every
change to the renderer since the modes split has had this hole; it only became
visible because this one changes pixels in a place easy to test (`the band is
one colour` versus `three`).

`inputs` now lives in each mode's slot, for the same reason `rom` does. The
version was deliberately **not** bumped: `load_cache` treats a version change as
"clear every file the old cache lists", which would delete the other mode's art
and not redraw it. A cache written before this simply has no per-mode
fingerprint, so that mode reads as stale and redraws once, which is the right
answer for it.


## Known wrong

- **Titan has no box.** The code `titan` is already taken by `ruby` stage 2, so
  a Locations-grid cell needs a new hosted toggle under a different code. It
  would be a bridge-only cell: Titan is not an AP location either (see below).
- **17 maps have no markers on the shipped hand-drawn art.** 16 were never
  calibrated and `ConeriaCastle2F` is a composite the schema cannot address.
  This is now a limit of that art only: markers on redrawn art are built from
  the cartridge and every map has them. Solving the 16 offsets by hand would
  only benefit a player who never runs `regen_maps.py`.
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
- ~~**`locations/NOverworld/incentives.json` has no marker validation.**~~ Fixed
  2026-08-29: `tests/test_maps.lua` walks all four location files now, so a
  marker off its art there is caught like any other.
- **Our trap letters are not DarkmoonEX's**, and by design -- his are
  hand-assigned for vanilla and do not describe an FFR seed. Ours are per
  cartridge and self-consistent per map. Only cross-referencing a letter
  against his guide is unsafe. See "Our letters are not DarkmoonEX's" above.
- **Four NPC locations have no pin on their own art.** Pravoka, Gaia, North West
  Castle and Matoya's Cave carry `map_locations` on the `overworld` map only, so
  their town and cave tabs show no marker for them even though the cartridge
  says exactly which tile each stands on. `place_locations` only rebuilds a
  node that already had a marker on a redrawn map, so these were never gained
  rather than being lost.

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
