# Where this pack is

The working log: what was built, why, and what each decision cost. Kept as a
narrative so a fresh session can pick a thread up cold -- the measurements are
here, and so is the reasoning that was tried and rejected.

Last updated 2026-08-30.

If you are looking for something specific, it is probably not in here. This is
the log; the settled half was lifted out of it into `docs/`, and `docs/README.md`
says which page holds what. To use the tracker rather than read about it, the
root `README.md` is the whole story.

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
- `tools/regen_maps.py --verify` — not part of either suite, because it asks
  about this machine's PopTracker install rather than about the code. Run it
  when the tracker looks wrong: it says whether the installed override predates
  the checkout, which is a failure with no visible symptom. `docs/ISSUES.md`.

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

**`docs/ROADMAP.md` is the ordered list.** In short: the No-Overworld logic
branch first, because those variants currently colour every pin with rules that
do not describe the seed; then visibility toggles, because the map work after it
adds pin sets that need an off switch; then the No-Overworld map surface itself.

The gate half of the logic branch is already done and verified on a real
cartridge -- the router stops at the gate NPCs. What is left there is the pack
acting on it.

Unless a section names another cartridge, `F258553F` is the seed its
measurements were taken against. `docs/ORACLE.md` is the inventory.

## The NOverworld variants

Triaged 2026-08-29 against FFR's own source and a live No-Overworld cartridge
(`GameMode 2`, FFR 4-9-2, seed `F258553F`). What the mode *is* is now settled;
what the pack should become is the open question.

### What FFR's No-Overworld actually does

Settled, and moved to `docs/NOVERWORLD.md`: the ocean stub with nine pads,
the 75-teleporter table, the four gate routines and what each wants, and the
two renamed items -- SIGIL is the Floater, MARK is the Earth Orb.

The sections below are the log of how that was found and what it cost.

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

## The No-Overworld rules, derived rather than substituted

Written 2026-08-30. `tools/noverworld_rules.py` reads a cartridge and emits the
access rules a No-Overworld seed actually has.

**The plan this replaced was wrong, and measuring is what said so.** The
intended fix was a substitution: make `ship` and `bridge` read as free in the
mode and leave the rules otherwise alone, so one rule set could serve both
variants. Then the cartridge was asked. **45 of 61 maps are reachable
empty-handed** on seed `F258553F`, and the Canoe adds two. The mode's gating is
per floor, not per vehicle. A substitution can delete false reds and cannot add
a single true one, so it would have traded one wrong board for a differently
wrong board.

**Tiles, not maps, and that is the whole tool.** `reachable_maps` answers "can
you enter this floor". A gate NPC or a locked door cuts a floor in half -- you
walk into Castle Ordeals 1F freely and the half holding the chests is behind a
SIGIL barrier. Asked per map, four of the ten key items look irrelevant:

    floater  crown  chime  tnt      change no map's reachability at all

Asked per tile, `key` alone opens 610. `reachable_tiles` is the same fixed point
`reachable_maps` runs, keeping the floor walk instead of discarding it.

**Minimal sets over the whole lattice, not one probe per item.** `floater` and
`crown` each open zero tiles on their own, so a per-item probe would drop both;
an item that opens nothing alone can still be half of a pair. 1024 walks, about
70 seconds. (4096 walks in about 57 since the memo, 2026-08-30.)

What seed `F258553F` derives, over all 249 locations, none refusing:

    167  free          34  cube          28  key          11  rod          9  canoe

Every rule is a single item. No conjunction appears anywhere, which is worth
knowing before building machinery to express one.

**Two bugs, both the same shape as the bank bug: a confident wrong answer.**

- *A chest is never stood on.* `walkable()` returns False for
  `TP_SPEC_TREASURE` because the engine does -- you open a chest by bumping it
  from the side, like talking to an NPC. The first version asked whether the
  party could occupy the chest's own tile, which is never true, and reported
  241 of 249 locations unreachable on a cartridge where most of the board is
  open from the start. It did not crash and every number it printed was
  internally consistent.
- *The kind cannot be guessed from the name.* `marker_tiles` is keyed by node
  name (`Dwarf Cave Smith`) and `npc_positions.json` by item code (`smith`), and
  nothing maps one to the other. Mangling the name matched none of them, so all
  eight NPCs went down the chest path. `test_noverworld_rules.py` asserts the
  count is exactly eight.

### Three chests, and the edge the walk would not cross

The derivation could not resolve three locations: `Sea Shrine Mermaids 4`,
`Mermaids 5` and `Sea Incentive`, all on SeaShrineB1 at (25-27, 4). They sat
against an 85-tile pocket, and three independent checks agreed it was sealed --
the whole boundary unwalkable holding every item, no teleport tile inside it,
and of every teleport on the cartridge arriving on that floor exactly one, from
SeaShrineB2 to (12, 26), well outside. Ten of the twelve Mermaid chests were
fine, which made a sealed pocket look like a cartridge quirk rather than a bug.

All three checks were answering the wrong question. **A standard map is a
torus.** A play observation said the vanilla route is to leave by the top left
and come back in at the top right, and the engine agrees in its own comment:
`SMMove_Right` adds one to `sm_scroll_x` and masks `AND #$3F` -- "and wrap at 64
tiles" (`bank_0F.asm:3070`) -- with the other three directions doing the same on
their axis. `floor_walk` and `reachable_teleports` stopped at 0 and 63.

Fixed 2026-08-30. SeaShrineB1 goes 526 reachable tiles to **611**, exactly the
85 the pocket held; the derivation goes from 246 resolved with 3 refusing to
**249 with none**. Across the cartridge it is +141 tiles, so the pocket is most
of what was missing but not all.

What makes this worth keeping is how well it hid. Wrapping adds tiles rather
than maps, so the all-items oracle still said 54 of 61 before and after -- the
cheapest and most trusted check in the tree could not see it, and neither could
any of the eight tool suites. Nothing errored. Every number was internally
consistent. It took someone who had walked the room.

That is the fourth time here that a complete, confident, wrong answer survived
because nothing asked the engine: the map bank, the talk table, the chest tile,
and now the map edge. The pattern is the same every time -- a plausible answer
from the wrong source outlives a check that never runs, and the fix is always
one line of assembly that was there all along.

`test_noverworld_rules.py` asserts the three chests directly, so the bounded
walk cannot come back quietly.

## The NPCs the walk could reach and could not rob

Written 2026-08-30. The derivation now agrees with FFR on every comparable
location: **226 of 226**, up from 216 of 218, with nothing left unresolved.

**Corrected 2026-08-30, later the same day.** That sentence is true and says far
less than it sounds like. Most of those comparisons are granted rather than
made: `offvocab_items()` hands the items the sweep cannot express to both sides,
and on the committed corpus that is **164 of 222**, concentrated in oxyale
(x129) and ruby (x32). Read `docs/ORACLE.md`, "What these figures do not cover".
The cause is not a vocabulary limit -- three rows are missing from
`GATED_OBJECTS` -- see `docs/ISSUES.md`.

**All three rows landed the same day**, and the grant is 5 of 226 now. The
figure to quote for this section is **226 compared, 225 agree, 1 divergent**,
with 221 genuinely compared -- see "Five object gates, twelve items, and one
divergence that had been hiding" at the end of this file.

Two defects, and they turned out to share a join.

**Six locations FFR pools had no derived rule at all** -- Coneria Castle's King
and Sara, Crescent Lake's Sages, the Elf Prince, Waterfall's Robot and Lefein.
The reason was dull once looked at: `extract_npcs.WANTED` listed fourteen object
ids and none of those six. Ask the object table for their ids and every one is
there, on both seeds, standing on the map its location node is named for. The
ids are AP location id minus 512, which is how FF1Lib numbers an NPC location --
worth leaning on, because the disassembly does not name four of them at all
($01, $0F, $11, $15), the same gap `NPC_IDS` already carries for the Elf Doctor.
$0F is not placed on a vanilla cartridge; FFR is what puts a Lefein object on a
map.

**And the positions came off the wrong cartridge.** `npc_positions.json`
reproduces the vanilla ROM exactly, and `extract_npcs.py` said so on the grounds
that FFR randomizes what an NPC gives you and not where it stands. Measured, that
is false:

    titan     vanilla (60,8,7)    both FFR seeds (60,4,8)
    nerrick   vanilla (19,16,45)  the No-Overworld seed (19,15,47)

So No-Overworld rules were being derived from vanilla tiles. Fifth time in this
file: a plausible source, a confident answer, nothing asking the cartridge. The
walk now reads the seed. `npc_positions.json` stays as the vanilla reference and
the test asserts the two disagree wherever the cartridge moves someone -- an
assertion that would have failed the moment the claim did.

### The trade is data, not a talk routine to disassemble

This document expected Astos to be the hard half: `docs/ISSUES.md` said his Crown
requirement "lives in a vanilla talk routine nothing here reads yet", so closing
it meant reading item checks out of assembly. That was the wrong guess about
where the answer lives.

FFR keeps it as data. `NPCs.cs` rebuilds the talk table as $D0 six-byte records
-- three dialogue ids, the item given, the item **required**, a battle id -- and
moves them into the bank it moved the jump table to. The requirement byte is an
offset into the `items` array in save RAM, so 2 is the Crown.

**The byte alone is not the answer, and the Elf Prince is why.** His byte reads
5, the Mystic Key, and that is the item he *gives*; his script never looks at it.
A reader that trusted the table would have gated the key on holding the key --
another complete, confident, wrong answer, and this one was sitting right next to
the two the reader was written for.

So an object is read as gated only where two sources agree. Either its routine
indexes the byte itself,

    LDX tmp+4 / BEQ / LDA items,X          A6 74 / F0 05 / BD 20 60

which is FFR's generic trade routine and covers the Elf Doctor, Astos, the Smith,
Matoya and Dr Unne; or the routine loads that exact item's address directly and
the byte names the same item, which is Nerrick and Titan. `MetroidVaniaMap.cs`
leaves Nerrick the older routine, so he hardcodes the TNT where the others index.

Seven objects, identical on all three FFR cartridges here, standard and
No-Overworld alike, with the Elf Prince correctly among the two whose byte is set
and unread. A stock image has four-byte records and no requirement byte at all,
and the reader returns None there rather than reading six-byte records out of
wherever $BA00 lands. `--trades` reports it; `--self-check` cross-checks it
against `gate_objects`, which reads the same table for a different reason.

### What it measured

On a 4.9.2 oracle cartridge built for the purpose, with `Spoilers`,
`Archipelago` and the four pool flags on:

    derived rules       254   (was 249)   0 unreachable
    compared            226   (was 218)   226 agree, 0 divergent
    no derived rule       0   (was 6)

That run's derived output was never committed. Re-running against the corpus
files as they stand gives 254 derived and 222 compared, of which 164 are granted
away -- so 58 are really compared. `docs/ORACLE.md` carries both figures.

and the standard-mode baseline that validates the whole harness is unmoved at
**225 checked, 225 agree, 0 divergences**. The derivation's two pinned numbers
did not move either -- 54 of 61 maps with every item, 22 empty-handed -- which is
what says the trades add a requirement without disturbing the walk.

The rules gained `tnt` for Nerrick, `crown` for Astos, `adamant` for the Smith
and `crystal` for Matoya. The last two are worth noticing: adamant and crystal
are outside the ten items the sweep varies, so this is the first thing in the
tree that can state a requirement the sweep cannot express. What is still out of
reach is those same items used as access rules rather than trades -- 129 uses of
Oxyale on that cartridge, 32 of the Ruby.

A trade ANDs into every alternative rather than adding one. A node hosting more
than one NPC where any of them trades exits rather than gating the others on an
item they never asked for: rules are per location and `check_logic` fans them to
the sections, so there is no way to say it for one section only. Nothing in the
tree does that today -- Coneria Castle holds the King and Sara and neither
trades.

## The Ordeals incentive lost its Crown, and nothing was comparing

Found 2026-08-30 while diffing what the tracker loads against upstream's
`9ed47a4`. `locations/overworld.json` gates the Castle of Ordeals incentive on
nothing; `locations/incentives.json` gates the same slot on
`earlyOrdeals` or `crown`. Same check, two tabs, two answers.

It went in `3ec131d` ("Split the calibrated dungeons into per-chest markers"):
that slot's section moved into a child location and its `access_rules` did not
follow. Every other split child kept its rule, which is why nothing looked
wrong — `Coneria Castle Chests 1` carries `["key"]` on the child node exactly as
intended.

**Measured before calling it live.** On both standard duck seeds, walking with
every item against every item *minus the Crown* reaches an identical tile set —
35339 tiles on `C189A0EF`, 35319 on `2CCBA52F`, delta 0 — so nothing on either
cartridge actually sits behind a Crown tile and no pin changed colour. The rule
was still gone, and would matter on a seed where that door gates something. The
Crown-gated tiles do exist: two on Ordeals 2F and one on 3F on one seed, three on
2F on the other.

**Two checks, because one of them could not have seen it.** `test_maps.lua`
check 6 compares the standard and No-Overworld dungeon trees, and it builds its
shape from *sections* — so a rule on a split child's node was outside it
entirely. The shape now carries the node's own `access_rules` too. Check 7 is
new and compares the incentive tree against the dungeon tree slot by slot: 29 of
the 30 shared slots have to agree.

The thirtieth is waived by name and filed in `docs/ISSUES.md`. Gaia's
northern-docks route carries `hwyOrdeals` on the incentive poster and not in the
dungeon tree, identically in upstream and here, so it is older than any of this
work; which one is right is not answerable from the location files, and changing
a standard-mode rule on a guess is the thing this pack keeps learning not to do.

Both checks were shown to fail before they were believed: reverting the rule
fails check 7, and restoring it to only one tree fails check 6.

**Then the check itself was reviewed, and three of its four holes were the
same mistake as the defect it was written for: something that looked compared
and was not.** It keyed slots by `hosted_item`, but `cardiaIncentive` is hosted
twice in each tree -- Bahamut's Cave behind the ship route, Cardia Forest behind
the airship -- so last write won and one of the two pairs was never looked at; a
bogus rule on the Bahamut's-Cave copy left the suite green. It skipped any slot
the dungeon tree did not host, so renaming a `hosted_item` -- exactly what
unlinks an incentive marker -- took the report from 29 slots to 28 and passed.
And check 6's new node-rule field joined alternatives with `","`, the character
that already separates the ANDed codes inside one, so `["a,b"]` and `["a","b"]`
-- an AND and an OR -- produced the same string, in the field added to make rule
drift visible. Slots are now compared as sorted multisets, the four orb-lit
poster-only slots are named the way `fairy` is and anything else missing fails,
and both concatenations use `" OR "`. Each fix was shown to catch a mutation the
old check passed.

**A fourth hole surfaced later, and it was the exemption rather than the
algorithm.** Check 7 ran on the standard pair only; the No-Overworld pair was
skipped by name, because its incentive sheet was hand-authored against
upstream's poster and disagreed about twenty slots anyway. When the mode guards
went in they went into `locations/incentives.json`, which the two NoMap variants
load -- and the two *map* variants load `locations/NOverworld/incentives.json`,
which kept the old geography. Twenty-two slots then disagreed between the two
sheets, in a new way, and the only check that would have said so was off for
exactly that pair. The rules are the standard sheet's now and check 7 runs over
both pairs; what stays hand-authored is where the pins sit, which check 7 does
not read. An exemption written around a known defect is a place a new one fits.

The fourth is latent and worth writing down rather than fixing quietly: `canon`
treated a rule as unconstrained only when *every* alternative emptied out, but
in PopTracker an OR with one unconditional branch is unconditional. No rule
here reaches it today -- every `^$incentiveSlot` term sits either alone in its
list or in all of them -- so it was a false FAIL waiting on the next incentive
rule, not a miss.

## Chests that share a treasure index, and the rule that follows

Measured 2026-08-30, after noticing on the tracker that opening one chest greys
several squares at once.

**Six treasure indices are placed on more than one tile, and that is vanilla.**
Reading the chest table off a stock `Final Fantasy (USA).nes`: 241 indices, six
of them on more than one tile, ten extra placements.

    index  25   3 tiles   marshB2
    index  26   2 tiles   marshB2
    index  29   3 tiles   marshB3
    index  92   4 tiles   volcB4 + volcB5 x3
    index 101   2 tiles   volcB4
    index 123   2 tiles   ordeals2F + ordeals3F

Every one is in a look-alike-room area -- the Marsh Cave, the Volcano's Agama
rooms, the Castle of Ordeals maze. A chest in this engine is a map tile carrying
a treasure index and the open flag is set per index, so duplicated tiles clear
together of necessity. Whether that was designed or fell out of copy-pasting
room layouts is not decidable from the ROM, and the tile data cannot tell the
two apart; what is certain is that it predates FFR and this pack. FFR then adds
more of its own, seed by seed, which is the ToFR half and is in
`docs/NOVERWORLD.md`.

**The derivation ORs the tiles, and the OR is load-bearing.** `derive()` unions
the per-tile rule sets, drops tiles the walk cannot reach rather than failing
the location, and dedupes so four chests in one room do not ship as "(free) OR
(free) OR (free)". Fifteen locations resolve to more than one tile on
`F258553F`. Two of them are what says the union is doing work rather than
agreeing with itself:

    Dwarf Cave Dwarf Armory 5   cardia UNREACHABLE | dwarves key
                                -> ships key
    ToFR Kary Floor 2           canoe,floater OR chime,floater
                                | UNREACHABLE | (free)
                                -> ships (free)

An AND would demand the Floater for the second. It ships free, which is right:
opening any one copy clears the lot, so the party needs only the easiest.

**A retraction, so it is not cited again.** A first pass at checking this
printed an "if it ANDed instead" column beside each location and it agreed with
the shipped rule everywhere, which looked like confirmation. It was computed
over the already-filtered live-tile list, so it reproduced the OR answer by
construction and could not have disagreed. It is evidence of nothing. The claim
rests on the per-tile rules above instead, where the tiles genuinely differ.

Nothing tests the multi-tile OR. It rests on a comment in `derive()` and on
these measurements.

## Ideas from playing on the rendered maps

Moved to `docs/IDEAS.md` -- towns as rooms, following the party into a
floor, insets, and routes drawn on the map, each with what is already known
about it.

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

**And 13 was not the number.** `regen_maps.py` computes it instead of anyone
counting by hand. It came out **3 pins on a standard seed** (`C189A0EF`) --
Dwarf Cave Smith and Nerrick on `dwarves`, Sarda on `sarda` -- and **2 on the
No-Overworld one** (`F258553F`), which does not draw Nerrick's sprite at all.
The list this sentence used to carry was the standard seed's three against the
No-Overworld seed's count. Seven object tiles did coincide with a *marker
tile*, but Pravoka, Gaia, North West Castle, Matoya's Cave and Bahamut's Cave
carried their pins on the **overworld** map only and had none on their own art,
so no sprite of theirs could be covered. Counting tiles instead of pins is what
produced the larger figure. Those five have pins now -- see below -- and the
count is 8 on a standard seed and 7 on the No-Overworld one.

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


### The five NPCs with no pin of their own, and what a diamond means

Raised 2026-08-29 looking at the result -- it felt like there should be more
diamonds, and what one signified was unclear. Both halves were fair. Fixed the
same day, and the count that framed the question was wrong in the same breath.

**A diamond is not a category.** Square and diamond are the same size, the same
centre, the same state colours and the same click target; the only difference is
that `drawRect` fills the whole tile and `drawDiamond` fills the inscribed
diamond, leaving the four corner triangles unpainted. Nothing in the pack tells
a player that, so the shape means "there is a sprite under here, let it breathe"
and nothing more.

**Three was the wrong number, and the reason was a gap elsewhere.** The pin
marks the NPC and the sprite *is* that NPC, so every NPC pin on redrawn art is a
diamond by construction. Only three came out that way because the other five
had no pin on their own art at all: Astos, Matoya, Bikke, the Fairy and Bahamut
carried `map_locations` on the `overworld` map only -- the pin on the town or
cave that holds them -- and `place_locations` only ever rebuilt a node that
already had a marker on a redrawn map. A node with none was never given one, so
those five were never lost, they were never gained.

**Not fourteen, eight.** This section used to say the count would go from 3 to
14 once the gap was closed. It does not: `npc_positions.json` holds fourteen
NPCs, but six of them -- Unne, Titan and the four fiends -- host no section
anywhere in the location tree, so there is no location for a pin to belong to.
Adding boxes for them is a separate decision and a bad one on today's evidence:
none holds a shuffled item, the fiends write no flag that could be autotracked
at all, and `titan` as a code is already taken by `ruby` stage 2. Eight NPCs
have a node; eight now have a pin. On a standard seed all eight are diamonds.

Three things had to be true for the pin to be right, and each was its own fix.

**A pin has to mean one thing.** A map marker's state is per *location*, not per
section: `TrackerView::CalculateLocationState` walks every section of the node
and ORs them, refs resolved (`trackerview.cpp:1170-1218`). Astos, Matoya and
Bahamut each shared a node with other checks -- North West Castle's three
chests, Matoya's Cave's three, the Cardia hoard -- so a pin dropped on Astos's
tile would have sat on Astos and reported the chests. Each is now its own child
location, which is the shape `Dwarf Cave Smith` and `Dwarf Cave Nerrick` already
had; the parent keeps its overworld pin and mirrors the child as a ref section,
and a child with no `access_rules` of its own inherits the parent's exactly
(`location.cpp:103-134`), so the logic is unchanged.

**The join could not be the Archipelago pool.** `marker_tiles` resolved NPCs
through `location_mapping.lua`, which only names locations the multiworld has an
id for -- and Bahamut is one of the eight NPCs with no AP id at all. It reads
`hosted_item` out of the location tree now. Same codes, same table, wider door:
chests still join by AP id, because that is what a chest index is.

**A pin only goes where the party can stand.** `npc_positions.json` holds
fifteen placements for those fourteen NPCs, and one of them is not in a map.
Ice Cave B1 carries a second `OBJID_FAIRY` at (47,30), out in the black beyond
the cave -- `game_flags + OBJID_FAIRY` is one global flag and `ShowMapObject`
reveals every copy, so the cartridge treats it as the same fairy, but it stands
on a cell the edge flood reaches and no party can walk up to it. The renderer
draws it and the crop deliberately keeps it in frame; a *pin* there would be a
pin in the void. `stands_on_map` runs the same flood `content_box` crops by, and
exactly one of the fifteen fails it.

**What a diamond means is still open, and now at the count that decides it.**
At three pins a diamond read as an exception. At eight it is every NPC pin there
is, which makes the shape a category whether or not it was meant as one --
especially once the trapezoid arrives meaning "entrance". Two ways to settle it:
say so out loud and let diamond mean "NPC", or leave shape alone and move the
*sprite* off-centre within its tile so a square pin stops covering it. The first
is free and is what the output already looks like.

**The shipped hand-drawn art did not get these pins**, and that is deliberate.
The transform reproduces the three markers DarkmoonEX drew to the pixel --
Sarda (58,56), the Smith (140,70), Nerrick (284,758) -- and matoya lands exactly
on her sprite. `nw_castle` does not: he draws Astos one tile above the cell the
cartridge places him on, sitting in a throne the map data does not have there.
The chest markers on that map are right, so it is the drawing and not the
calibration. A pin a tile off its sprite reads as a bug, and the pack has
already decided hand-art marker work only benefits a player who never runs
`regen_maps.py`, so these pins are built onto rendered art only.

### The pins read the seed, and four nodes were split so they could

Written 2026-08-30. The derivation started reading NPC positions off the
cartridge on 2026-08-30; the pins did not come with it, and that gap was its own
entry in `docs/ISSUES.md` for a day. `marker_tiles` resolved every NPC through
`tools/npc_positions.json`, the committed vanilla snapshot, on a claim its own
docstring made -- that FFR randomizes what an NPC gives you and not where it
stands. It moves them:

    titan     vanilla (60,8,7)    every FFR seed measured (60,4,8)
    nerrick   vanilla (19,16,45)  both No-Overworld seeds (19,15,47)

Five cartridges checked -- vanilla, the standard oracle, both No-Overworld
seeds and the shard-hunt one. Of the fourteen codes the snapshot holds, twelve
are identical everywhere, `titan` moves on every FFR seed and `nerrick` on the
No-Overworld ones. So the standard tabs were right by luck and a No-Overworld
regen drew Nerrick's pin two rows off the sprite it marks.

**The fix is one line each in four places** -- `marker_tiles`, the crop guard in
`regen_maps.main`, `render_maps.self_check` and `test_crop` all take
`extract_npcs.extract(rom)` now, the shape `noverworld_rules.placements()`
already used. `tools/npc_positions.json` is out of `INPUT_FILES`, replaced by
`tools/extract_npcs.py`: what decides the output is the WANTED table plus the
cartridge, and the ROM's sha already covers the second half.

**The file stays, and the reason is that Lua has no cartridge.**
`tests/test_maps.lua` reads it twice -- check 4c reproduces the three shipped
hand-art pins to the pixel, and check 4d reproduces the three
`map_calibration.json` entries solved from a fiend's tile on `earthB5`, `sarda`
and `seaB5`, floors with no chest for the centroid solver to work from. Both are
statements about a *vanilla* cartridge and neither is derivable in the test that
makes them. `test_npc_pins` still asserts the snapshot's fourteen codes by name,
retitled to say what it now anchors.

**Six NPCs gained a pin, and four gained a node first.** `king`, `sara`,
`elfprince`, `robot`, `sages` and `lefein` got derived rules in the previous
pass and were never in the snapshot, so switching the source hands them tiles.
Four of them hosted on `Coneria Castle`, `Elf Castle` and `Waterfall`, which
also carry those dungeons' chests -- and a marker's state is per *location*, ORed
over every section (`trackerview.cpp:1170-1218`), so the King's pin would have
sat on the King and reported the castle. Each is now its own child location with
the parent mirroring it as a `ref`, which is the shape Astos, Matoya and Bahamut
were split into first; a child with no `access_rules` of its own inherits the
parent's exactly, so `check_logic.load_pack_rules` reports the same chain for
all four. `Crescent Lake` and `Lefein` already hosted alone and were left as
they were.

Four section paths moved with them, in `location_mapping.lua`,
`incentive_slots.lua`, `test_incentives.lua` and one `check_logic.WAIVED` key --
`Inner Sea/Coneria Castle/Sara` is now
`Inner Sea/Coneria Castle/Coneria Castle Sara/Sara`. A waiver that stops
matching does not error, it prints as a divergence, so the standard baseline is
what says that one landed.

Measured on the 4.9.2 oracle corpus:

- Dungeon markers **259 -> 265** on the standard cartridge and **269 -> 275** on
  the No-Overworld one, which is the six new pins and nothing else; nothing was
  left unplaceable either way.
- Diamonds **14 on both**, up from 8 standard and 7 No-Overworld. All fourteen
  NPC pins now land on a drawn sprite -- including Nerrick's on the No-Overworld
  seed, which is the same fact as the two-row move seen from the other side: the
  old pin did not collide because it was not on him.
- `check_logic` on the standard cartridge: **225 checked, 225 agree, 0
  divergent**, unmoved.
- `check_logic --derived` on the No-Overworld cartridge: **226 comparable, 226
  agree, 0 divergent**, unmoved -- though 164 of those are granted rather than
  compared, which nothing here said at the time, and one of the 226 turned out
  to be a real divergence once the grant was lifted -- and **0 fanned**, where `Coneria Castle`
  exposed two sections before, so its derived rule reached both the King and
  Sara. That is the over-reach `derive()` hard-exits on when a trade is
  involved; neither of those two trades, so it had stayed a latent one.
- The six that keep no box -- Unne, Titan and the four fiends -- were looked at
  again in the same pass and left alone. None holds a shuffled item, the fiends
  write no flag that could be autotracked, and `titan` as a code is taken by
  `ruby` stage 2. Fourteen of the twenty objects `WANTED` reads have a pin.

What a diamond means is still open, and the count that framed the question has
moved again: at fourteen it is every NPC pin on both modes.


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
it cyan, and called it a defect. The judgement came back that waterfall renders
correctly, and that is right: the black there is largely DarkmoonEX's
**annotation panel** -- the `1 2 3 4 5 6` chest numbering, the trap-tile key
and an NPC drawn into the room's dead space -- not the map's floor. The
reference art is a specification *and* a drawing, and the two have to be told
apart before a difference counts as evidence.

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
count alone. A look at the render said otherwise, and it was correct: the cave
is entirely indoors, so nearly all of it *is* one room in the engine's terms,
and what was
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

**The boxes are looser than one speck, and the towns show it worst.** Noticed
2026-08-29 while playing on the rendered tabs: some village maps keep stray
non-void tiles out at the boundary and the frame stays open around them.
Measured on seed `F258553F`, counting rows and columns *inside* the crop that
are entirely backdrop:

    sky4F           22 blank cols, 26 blank rows
    con_castle      35 blank cols
    elf_castle      31 blank rows
    crescent_lake   23 blank rows   (town)
    melmond         21 blank rows   (town)
    lefein          16 blank rows   (town)
    iceB3           19 blank cols

`con_castle` is the clearest: the castle ends around column 27 and a detached
wall sliver out at the right edge holds the box 35 columns wider than the map,
so more than half the tab is empty field. This is the Matoya speck again at a
size that actually costs the tab, and the towns have it because their warp-out
field is not one uniform tile everywhere.

Not fixed, and deliberately not fixed by adding a third proxy -- walkability and
size were both tried and rejected for the speck, and inventing another filter is
how the room-floor rule went wrong twice. The shape of a real answer is probably
the same one the room work landed on: ask what the region is connected to rather
than what its tiles look like. Insets (below) would also dissolve it, by laying
disjoint components out separately instead of framing their union.

**A Map Key band is reserved, not drawn.** Trap letters derive: enumerate the
fixed-formation trap tiles (`TP_SPEC_BATTLE`, byte 1 not the random marker) over
all eight tilesets in order and label them A, B, C. On a *vanilla* cartridge
that reproduced the shipped art exactly -- `earthB1` came out `{G,H,I}` and
`volcB4` `{M,N}`, and `volcB1`'s bare `A` correctly is not a trap mark.
(**Historical.** That agreement is what pinned the enumeration base, and it did
its job; the scheme it verified has been replaced, because numbering by
`(tileset, tile)` gives one formation two labels -- see above. What replaced it
is `trap_marks()`, keyed to the formation and handed out only to formations that
stand on a map, and it lands **one place behind** the art rather than on it:
`earthB1` is `{F,G,H}` and `volcB4` `{L,M}`. The one place is formation `$00`,
five fixed tileset entries that no map places, which the art counted and this
does not. The base is unaffected: what changed is the key, not where the tiles
are read from.) 23 of
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

Moved to `docs/ISSUES.md`, with the open questions.

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

## The oracle ran, and the walk was starting in nine places at once

The derivation shipped with its own gate written into its commit message: the
rules are emitted, applying them is a separate change, and `check_logic.py`
against FFR's own logic is what should decide. That check had never run. It has
now. It failed, it named one cause, and the rules agree with FFR on 216 of 218
comparable locations once that cause is fixed.

**Getting a ground truth at all was most of the work.** `check_logic` needs an
FFR spoiler or an Archipelago export beside the cartridge, and not one of the
four seeds on disk carries either. The reference seed `F258553F` cannot be given
one retroactively: `Spoilers` and `Archipelago` are both encodable properties, so
flipping either changes the flag string and therefore the seed. The way through
is to generate the cartridges locally, with their ground truth attached.

That needs the *right* randomizer. The vendored checkout is 4.9.8 with an
unstamped `FFRVersion.Sha`, and only 4-9-2 and 4-9-7 schemas are committed — a
4.9.8 cartridge would not decode at all, and `game_mode()` reads through that
decoder, so even the derivation would refuse it. The 4.9.2 release commit
`01272d4` is in the checkout, and its seven-character SHA is what
`schemas/4-9-2.json` records. Building a worktree at that commit with the SHA
stamped in gives a randomizer whose output the committed schema reads.

**Regenerating the reference seed is the determinism proof, and it half-passes,
which is the interesting part.** `--import F258553F_<on-cart flag string>`
re-emits that flag string character for character, and the derived rules come
back identical — 249 placed, 0 unreachable, 167 free / 34 cube / 28 key / 11 rod
/ 9 canoe, the numbers recorded above. But the ROM differs in 25540 bytes. They
are all CHR banks, credits, dialogue and menu text; bank `$14` is untouched, both
cartridges self-check to the same 32365 teleport tiles, the same 157 staircases
and the same four gate routines. That is `Preferences` — cosmetics the web UI
sets and the CLI defaults — not logic. Worth writing down because "not
byte-identical" reads like a failure and is not one here.

**What the check found.** With `Spoilers`, `Archipelago` and the four Archipelago
pool flags on, FFR writes rules for 225 locations instead of the key items alone
— the pool flags are the lever on coverage, and ToFR is excluded from the pool
unconditionally (`Archipelago.cs:93`), so those chests can never have an FFR
rule.

    derived rules         249   (0 unreachable)
      resolved            249   (0 fanned, 0 ambiguous, 0 unmatched)
    FFR rules joined      224   (1 unmappable, 20 duplicate claims collapsed)
    compared              218   52 agree, 166 divergent in 13 shapes
      no derived rule       6   FFR pools it, placements() found no tile

Every one of the 166 is permissive: the derivation opens a location FFR holds
closed. **Not one is strict**, so the walk never closes something FFR opens —
which is what said the failure was one-sided and structural rather than noisy,
and is what made it worth chasing to a single cause.

**The cause is where the walk begins, and it is not what it first looked
like.** The early reading was that the other eight pads sit across water and FFR
gates them on the airship. Measuring killed that: every pad on the stub carries
tile property `0x0E` — walkable on foot, refused to the canoe, the ship *and*
the airship — and none of them is a dock. Nothing sails or flies between pads,
and the Floater is not a vehicle in this mode at all. It is a key item four gate
NPCs check while standing in corridors. All travel is the teleporter table.

What is actually wrong is simpler. `reachable_tiles` seeded from everything
`Graph.starts()` returns, and that method answers a question about the *table* —
which entrances have a tile on the overworld — not about the player. The party
begins on one pad and cannot leave it:

    empty-handed from all 9 pads          45 maps, 24760 tiles
    empty-handed from the start pad       22 maps, 10257 tiles
    every item, either way                54 maps, 31049 tiles

FFR calls 21 locations free. The derivation called 167. That the all-items count
does not move is the invariant worth keeping — gates must not change it.

**The fix reads the start off the cartridge.** FFR writes the starting position
at bank `$00:$B010` (`MetroidVaniaMap.cs:93`) as the scroll origin, seven tiles
short of the party; `SCCoords` is built from the same pair as `(x + 7, y + 7)`,
which is what says the seven is a convention and not a coincidence. That gives
`(104, 160)`, whose foot landmass is an eight-tile platform holding exactly one
door — Coneria Castle. `start_doors()` walks the stub with `overworld_reach`
granting the canoe, the most generous traversal available, and reports rather
than assumes if a vehicle ever does reach a second pad.

Re-derived, the shape changes as well as the counts — conjunctions appear, where
before every rule was a single item:

     52  canoe OR chime,floater          51  (free)
     49  canoe,floater OR chime,floater  34  canoe,cube,floater OR chime,cube,floater
     27  key                             15  floater
     11  rod                              9  canoe
      1  canoe,floater,key OR chime,floater,key

**Against FFR: 216 of 218 agree, 2 divergent.** The two are Nerrick and Astos,
who want the TNT and the Crown handed over before they give anything up. The
walk asks whether the party can stand beside an NPC, which is not the question
of whether they can obtain what it holds. Those, and the six NPC locations
`placements()` resolves no tile for, are one remaining pass.

**The result carries to the reference seed.** The oracle cartridge is not
`F258553F` — it has the Archipelago and Spoilers flags on, so it is a different
flag string and a different seed. Deriving from both with the fixed walk gives
**identical rule sets**, all 249, which is what says the 216-of-218 verdict
covers the seed every measurement in this file was taken against, even though
that seed carries no ground truth of its own to check against directly.

**A bug in the checker, found by the fix not moving enough.** The first re-run
came back 156 divergent against 166, which was far too small a change for a
correction that had halved the empty-handed reach. `compare()` builds its FFR
verdict from `held` alone, so the off-vocabulary items were being pinned into
`pinned` — which reaches the pack side only — and went on being varied and
required on FFR's side. They now go to both sides and drop out of the variables.
Corrected, the same two rule sets read 84/134 before the seeding fix and 216/2
after. The lesson is the one this file keeps relearning: the number that did not
move as much as it should have was the finding, not a rounding.

**Three things the check cannot settle.** Seven of FFR's requirement items —
Oxyale, Ruby, Slab, Herb, Adamant, Bottle, Crystal — are outside the ten the
sweep varies; 121 uses of Oxyale on the reference seed `F258553F` (the oracle
cartridge carries 129). **"Game rules rather than tile blockers" was wrong about
two of them**: Oxyale and the Ruby are map objects standing on chokepoint tiles,
`Sanity/SCMap.cs:167-186`, and the walk simply has no `GATED_OBJECTS` row for
them — see `docs/ISSUES.md`. The genuinely non-graph five are the trades.
**Both rows landed on 2026-08-30 and the sweep varies twelve items now**, so the
count outside it is five and "a derived rule set will never state an Oxyale
requirement", below, is historical -- it states one at 143 locations on `nov`. Skipping those locations was tried first and hides real
over-reach, because FFR's rule is an OR and a clause can sit entirely inside the
swept vocabulary. Granting the off-vocabulary items for free instead makes FFR as
permissive as it can be, so a surviving divergence cannot be blamed on the gap —
a fair test, but not a fix, and a derived rule set will never state an Oxyale
requirement. Six pooled locations resolve to no tile at all. And agreement here
would mean the derivation matches *FFR's model of the cartridge*, not the
cartridge.

**The standard-mode baseline is clean and is what validates the harness.** The
pack's existing hand-written rules against the same seed at `GameMode 0`: 225
checked, 225 agree, 0 divergences, with no achievability pruning in play. If the
parse, the join or the comparison were broken, 225 of 225 would not agree.

Two traps in the adapter itself, both caught before they could produce a number.
A free rule written the obvious way — `",".join([])` — evaluates to False, which
would have reported all 167 free locations as stricter than FFR and looked like
the derivation collapsing. And `trustworthy` demands vehicle placements that are
in `pinned` on neither cartridge, so a derived run would have printed its
findings and then reported zero divergences. Both are asserted in
`tools/tests/test_check_logic.py`.

## Seven crops, two causes, and a letter that means two things

Seven maps were flagged by eye as badly cropped. Measured over all 61 maps of the
std and nov oracle cartridges, they are **two mechanisms, and the fix count is
two rather than seven**.

**The seam.** A standard map wraps at 64 tiles -- `AND #$3F`, which
`entrance_graph.floor_walk` has modelled all along -- and `render_maps.content_box`
does not. It takes an axis-aligned bounding box in un-rotated coordinates, so a
map whose content straddles column 0 or row 0 gets framed across the void between
its halves:

    con_castle      64x35 -> 31x35   content cols 62-63 + 0-26, 35 blank between
    crescent_lake   52x64 -> 53x43   content rows 58-63 + 0-34
    melmond         45x64 -> 45x46   content rows 51-63 + 0-30
    elf_castle      28x64 -> 29x35   content row 63 + 0-31, wrapped by one row

**Both cartridges give identical numbers**, which is the useful part: the wrap is
a property of the map and not of the seed, so the No-Overworld audit that looked
like it might be needed is not. Two of the by-eye guesses were backwards --
Melmond was called plain over-crop and is a wrap; Sea Shrine B1 was called a wrap
and has no empty column anywhere.

That retracts a cause, not a number. `docs/ISSUES.md` attributed `con_castle`'s
35 blank columns to "stray detached tiles out near the boundary"; the 35 is
right and the tiles are not it. The original diagnosis survives for the residue
-- `onrac`, `lefein` and `seaB1` really are held open by a one-to-three-cell
sliver spanning the full width, and `iceB2`, `iceB3` and `sky4F` are multi-lobe
maps where rotating would put the left half on the right. Those six go to the
insets idea, which predicted them.

**The letters mean two things at once.** `trap_letters()` numbers by
`(tileset, tile)` enumeration order rather than by the formation the tile spawns.
Two consequences, and the second is the one that matters:

- 38 distinct labels on the std cartridge, so everything past index 25 becomes
  AA..AL. Seven maps carry a two-character label; `tofrChaos` reads AG AH AI AJ
  across eight tiles in a row. That is the clutter that got noticed.
- **Three formations are drawn under two different letters each.** On std,
  formation `$10` is G on `earthB1` and W on `marshB3`; `$1C` is AA and AG; `$4A`
  is V and X. Same on nov, three again. So the label does not identify the
  encounter, which is what a label on a fixed-formation tile is for.

The second was not what anyone was looking for. It surfaced only because the
question asked was whether the same enemies on two maps *should* share a mark --
the answer being yes, and the measurement then showing that today they sometimes
do not. The reflex fix, re-lettering per map, would have entrenched it.

Keying the mark to the formation closes both. **32 formations actually stand on a
map** (31 on nov), against 35 single glyphs available in `0-9A-Z` once `O` is
dropped -- and `O` is dropped because `tools/font.py` already asserts that `0` and
`O` are the same glyph in the cartridge's font, which is exactly the kind of trap
that alphabet would otherwise have walked into.

Two recorded claims do not survive this and are updated rather than left:
`test_crop.py:179` and `:195` assert `volcB4` is `{M,N}` on named tiles, and the
"reproduces the shipped art exactly" finding below.

**Landed, and the numbers it came out at.** `trap_marks()` keys to the formation
and `standing_formations()` supplies the order. Measured over five cartridges --
vanilla, the std, nov, nov2 and shard oracles -- **every mark is a single glyph
on all five**, and no formation carries two marks and no mark stands for two
formations on any of them. Formations standing on a map: 32 vanilla, 32 std, 31
nov, 32 nov2, 31 shard, against 35 available. The two-character fallback is
written and no measured cartridge reaches it; it is there because a reused mark
is a map that lies about which fight is on a tile, which is worse than a label
too wide for one.

The clutter went with it. `seaB4` read `AB AC AD AE` and now reads `0 1 Y Z`;
`earthB1` and `marshB3` both read `G` for formation `$10`, which is the same
fight and now says so.

What this cost is the exact agreement with the art, and the cost is one place
rather than an unknown. `test_crop.py` asserts the shift **and names its cause**
-- that formation `$00` is fixed, is in the tileset tables five times, and
stands on no map -- so the check still says something about the derivation
instead of merely pinning today's output.

**Linked chests, measured while the chest data was open.** Six chest indices sit
on more than one tile on std and **fourteen on nov** -- Short ToFR duplicates
indices onto `tofrChaos`. Four same-map groups on both (`25`, `26` on `marshB2`,
`29` on `marshB3`, `101` on `volcB4`); two cross-map on std against ten on nov.
Seed-dependent, so any annotation derives per cartridge.

## Five object gates, twelve items, and one divergence that had been hiding

Written 2026-08-30. `Sanity/SCMap.cs:167-186` gates five object ids by tile in
one switch, and the walk modelled three: the Rod and Lute plates, and the Black
Orb once it was read per cartridge. The last two -- SubEngineer `0x10` wanting
the Oxyale, Titan `0x14` wanting the Ruby -- went in with the vocabulary that
carries them, because they could not go in without it. A `GATED_OBJECTS` row
whose item the sweep cannot hold blocks that tile in *every* subset, so
everything behind it derives as unreachable rather than gated, and the rules
come out saying nothing instead of saying the wrong thing loudly.

**The two are not equally legible on the cartridge, and the reader says so
rather than flattening them.** Titan's requirement byte is set --
`NPCs.cs` assigns him `Item.Ruby = 9` -- and his routine opens `AD 29 60`, LDA
item_ruby, so `talk_item_requirements()` already answered for him: the byte and
the code naming the same item, which is the two-sources-agree discipline that
function exists for. SubEngineer's byte is `0x00`. Nothing assigns him one, so
there is no second source at all and the only signal is `AD 30 60` in the body.
With one source carrying the answer the shape is pinned hard instead: the body
must name exactly one address in the `items` array, and two or none is a refusal.
`items + $11` is excluded from that scan on purpose -- it is item_canoe's
address and also where FFR's `ShiftEarthOrbDown` puts the Earth Orb, so a body
naming it means two different things and the scan cannot tell which. The
requirement byte has no such problem, being an index FFR writes, so only the
scan drops it.

Verified on five cartridges -- vanilla and all four oracle seeds -- and all five
read `{$10: oxyale, $14: ruby}`. On vanilla that is the body scan doing the work
for both, since a stock image has no requirement table at all.

**Each row demonstrates a failure, per the working rule.** On `std`, holding
every item but the one: the sub engineer closes 32 locations across the five Sea
Shrine floors, the Titan the 4 in his tunnel. On `nov` the Titan closes the same
4, and the sub engineer closes nothing at that level -- with everything else in
hand the Sea Shrine has another way in. So his demonstration is one subset down:
holding `chime,floater`, his row closes 59 locations across Crescent Lake, the
Ice Cave and all five Volcano floors. Which is FFR's own shape for those
locations, `(Chime AND Oxyale AND Sigil) OR (Mark)`, arrived at by walking the
cartridge rather than by transcribing the export.

**The sweep is 2^12 and got faster.** 4096 subsets in about 57 seconds against
1024 in about 85, because `floor_walk` and `reachable_teleports` are memoized on
`(map, arrival, the part of the held set that floor consults)`. 42 of the 61
floors on vanilla consult no item at all and are walked once for the whole
sweep. The filed design memoized only `floor_walk`; `reachable_tiles` calls both,
so that would have been half a memo.

Those two numbers are different runs, though, and the honest measurement is an
A/B on one build: memo off, `nov` costs 77.5 ms a subset against 14.0 with it,
so the sweep would be about 318 seconds rather than 57. **About 5.5x**, and the
old pre-memo rate -- 85 seconds for 1024, so 83 ms a subset -- lands on the
unmemoized side of that, which is what says the memo is doing the difference
rather than the vocabulary change. Only about 4x of it is reuse inside a single
`reachable_tiles` fixed point; the rest is the cache saturating across the
sweep, since the whole lattice produces about 188 distinct walks. Method is in
`docs/IDEAS.md`, and the switch is the `NoMemo` subclass in
`tools/tests/test_memo_walk.py`.

The key is the whole risk -- one that omits an item the walk consults hands back
another subset's reachability with nothing failing -- so `test_memo_walk.py`
guards it twice. The cheap guard runs every time and is still exhaustive: a walk
reads the held set in exactly two places, so if neither `walkable()` on any of a
map's property bytes nor `blocking_objects()` on its objects can tell `have` from
the trimmed key, over all 61 maps and all 4096 subsets, then no walk can. The
expensive one compares memoized against unmemoized tile for tile over the whole
lattice; it runs on `FF1_SLOW=1` and passed on `nov`, 4096 of 4096.

**What it bought is on the measurement.** `offvocab_items()` hands both sides
every item the sweep cannot express, and Oxyale and the Ruby were 161 of the 164
grants on `nov`. The grant is 5 now -- Herb, Adamant, Bottle, Crystal, Slab, one
each -- so `nov` goes from 58 genuinely compared to **221 of 226**, and `nov2`
from 64 to 219. Independent support for the pack's own No-Overworld rules goes
from **63 of 226 to 215**: the sweep derives a rule for every compared location,
agrees with FFR at 225 of them, and never parts company with the pack's rule
where the pack agrees with FFR.

The two baselines did not move -- std 225/225, shard 229/229 -- which is what
says the new rows describe the cartridge rather than the mode.

**And one thing surfaced that the grant had been hiding.** Lefein is the only
`--derived` divergence left, on both No-Overworld cartridges. FFR wants
`(Tnt OR Ruby OR Canoe) AND Floater AND Slab`; the derivation says `floater`.
Both are right about the geography: Lefein town is two teleports from the start
-- Coneria Castle 1F `(2,8)`, behind the SIGIL barrier, to Waterfall `(57,56)`,
then Waterfall `(25,28)` to Lefein -- and FFR agrees, wanting only `Sigil` for
the Waterfall chests. The extra term is the requirement for reaching *Melmond*,
because the Lefein man wants the Slab translated and `SCLogic.cs:555-557`
resolves an NPC gated on the Unne flag to Dr Unne's own reachability.

That is a requirement naming another location, and the sweep's vocabulary is
items -- no amount of widening reaches it. Filed rather than patched, in
`docs/ISSUES.md`, where it is the strongest argument yet for the propagating
solver in `docs/IDEAS.md`. It also showed up a rationale that had gone stale:
`check_logic.WAIVED` said the pack is stricter at Lefein "because Unne is
reachable whenever Lefein is", which holds on a standard overworld and does not
hold here. Corrected in the review commit below -- what the waiver concludes was
right on both worlds, and only the reason it gave was wrong on one.

## What the review of the object-gate branch found

Written 2026-08-30. A full review of `trunk..object-gates` returned four
findings. All four held up against the files and all four are fixed rather
than waived. Two were real, one was latent, one was arithmetic in a doc.

**The gate reader could name an item the sweep never varies.**
`object_gate_items()` returns whatever the cartridge names, and `ITEM_RAM` has
seventeen entries against `ITEM_NAMES`' twelve. A row naming one of the other
five blocks that chokepoint in *every* subset, so everything behind it derives
as unreachable rather than gated -- which is the invariant this very commit
states on three pages and enforced nowhere. Shown by rewriting the sub
engineer's body to `LDA item_bottle`: the reader returned `{$10: bottle}` and
his tile stayed blocked while holding all twelve swept items. It refuses now,
which is the same refusal `black_orb_item()` makes on a shard count it cannot
express. Inert on the corpus -- all five cartridges still read
`{$10: oxyale, $14: ruby}` -- and that is the point: the reason this is a reader
at all is that a cartridge is free to reassign the routine.

**The Lefein waiver was stating a reason where it was false.** `WAIVED` is
suppressed in `--derived` mode but not per cartridge, so it fires on the
`--ap-rules` run for both No-Overworld cartridges, carrying "because Unne is
reachable whenever Lefein is" onto a world where the Waterfall route reaches
Lefein without going near Melmond. The conclusion survives the correction:
`SCLogic.cs:555-557` resolves an NPC gated on the Unne flag to Unne's own
reachability, and on No-Overworld that resolution *is* the `Tnt OR Ruby OR
Canoe` term, so FFR's rule does require standing where the translation happens
and the step the pack shows is still always takeable. So the fix is the
rationale, not the waiver: clearing it instead would report Lefein as a
divergence on every cartridge, standard included. Figures unmoved -- `nov` 226
checked / 220 agree, `std` 225/225.

**The walk caches were invalidated by one of their two inputs.** Assigning
`gated_objects` throws them away; `floor_items()` also reads the map's tile
properties, so a caller that patches `rom.data` and empties `grids` alone gets a
stale memo silently. Both tests that patch a cartridge do clear both -- but only
because they happen to write them in one statement, and a memo whose correctness
rests on the order of a tuple assignment is one line from being wrong. `grids`
is a property with the same setter now.

**And `docs/IDEAS.md` said "seven further items" over a list of five.** Seven
was the count before this commit, when Oxyale and the Ruby were still in it.

## What the review of the visibility-toggle branch found

Written 2026-08-30. A full review of `trunk...visibility-toggles` returned six
findings, all low. All six held up against the files and all six are fixed
rather than waived. None was a correctness bug in the Lua or the layouts; the
review checked the load-bearing citations against the vendored PopTracker and
the doc greps against the pack, and those held.

**The icons were sized against the wrong greyscale.** `make_toggle_icons.py`
draws only the "on" image and lets PopTracker grey the off state, and its
docstring described that filter as 0% saturation and 67% brightness -- which is
PopTracker's *default* `grey`. This pack overrides it: `settings.json` sets
`disabled_image_filter` to `grayscale, dim`, and `dim` is a flat halving
(`imagefilter.cpp:78-81`), applied after a greyscale taken at full value rather
than at two thirds. So the off state is a third darker than the docstring's
model. Measured through the real filter: GROUND 24/24/28 -> 12, GLYPH 188 -> 94,
blue -> 61, gold -> 78. The glyph shapes hold at 94 on 12; the gold ring at 78
against a 94 glyph has stopped being gold, which makes `showIncentiveRings` the
one of the four most likely to need a drawn "off" image. Written down in the
docstring rather than acted on, because that is a look-at-it decision.

**The writer had a `--check` mode and nothing ran it.** Editing `GLYPH` or a
shape function left the committed PNGs stale with both suites green -- the
mirror of the rule this repo states elsewhere, that a check which cannot fail is
worth nothing. `tools/tests/test_toggle_icons.py` runs it now, and carries a
second guard for the three icons that were shipped with no item, no layout cell
and no Lua naming them: they are drawn ahead of the pins they switch, so the
test holds that list and fails both if one is wired up without leaving it and if
a fourth goes unreferenced. Both directions were demonstrated before the test
was kept, and so was a deleted image.

**The stale-override trap this branch filed had no detection.** Fixed with
`regen_maps.py --verify`, which reads the `inputs` fingerprint already in
`.regen_cache.json` -- no cartridge, no rendering, milliseconds. It found this
machine's override stale on its first run. Deliberately not in either suite:
that would make a red suite out of a fact about the developer's PopTracker
install. What stays open is detection at tracker load, which the pack cannot do
-- PopTracker's Lua has no layout query and no file read -- so it wants a
`getLayout` warning upstream. `docs/ISSUES.md` and `docs/IDEAS.md` both say so.

The two smallest: `wantRings()`'s comment described the three pin toggles as
rules that exist, and `restrict_visibility_rules` appears nowhere under
`locations/`; and three doc lines had been left at 102, 110 and 113 characters
after text was removed without re-wrapping.

## Four names that have drifted off what they describe

Moved to `docs/IDEAS.md`. One of the four is answered by that move: this
file stays a working log and the defect list lives in `docs/ISSUES.md`.

## Open questions

Moved to `docs/ISSUES.md`.
