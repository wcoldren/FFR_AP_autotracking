# What is next, in order

This file says what gets built next and why, ordered by what a player sees.
Defects live in `docs/ISSUES.md`, unscoped ideas in `docs/IDEAS.md`, the
narrative in the `STATUS` log.

**Forward-only means ordered by what is next, not that finished work vanishes
from here.** A closed item stays, dated, shrunk to its conclusion and a pointer
to where its evidence lives; it leaves the page when the section it sits in is
superseded. Deleting a close outright is the failure this page keeps hitting
from the other side — nothing re-reads a line once it is written, so an item
that goes quiet outlives its own answer.

**Compacted 2026-09-04.** The closes had grown to 299 lines against 145 open,
with sections 1 and 5 holding 265 lines between them for two open bullets — so
the page that says what is next could not be read for what is next. The
shrink-to-a-conclusion half of the rule above had never been applied: each close
carried the narrative `STATUS-2.md` owns and the figures `ORACLE.md` owns, which
is a third copy of both and the copy here is the one that goes stale. Nothing
was deleted. Each close is now its conclusion, its date and a pointer, open
bullets sort above closed ones inside each section, and the open set is indexed
below. **Every section keeps its number**, because nine places outside this file
cite them by number — `scripts/autotracking/flag_mapping.lua` and
`tests/test_maps.lua` among them — and renumbering to tidy a page is how a
pointer stops resolving.

**A close cannot carry an open finding. Added 2026-09-04**, from an audit of
every open item on this page and in `docs/ISSUES.md` against the tree. §1's
incentive-conjunction close ended by naming one finding it did not fix — a gold
ring on a check the seed does not have — and that is the only place this page
mentions it. An open defect hanging off a closed bullet is invisible by
construction: it is not in the index below, so nobody reading the plan for what
is next will see it. A close now shrinks to its conclusion and *spawns* a row;
it does not keep custody of what it left behind.

The same audit found live defects with no bullet here at all, which is a
different failure and not one the triage rule catches: defects belong to
`docs/ISSUES.md` by design, and the cost is that the plan cannot see them. The
second table below indexes them. It carries a line each and a pointer, never the
prose — that page owns them, this one only has to make them findable.

The triage rule, from 2026-08-30: **does it change a colour, add a box, or save
a click?** If yes it is product and goes in sections 1-4. If no it is tooling
and goes in 5, where it earns its place by keeping 1-4 true. **The section
order is historical rather than a priority**, amended 2026-09-01 when sections 1
and 5's first two bullets all closed: the rule sorts tooling last by
construction, which was right while section 1 was open and is not now.

The parity target for every rule is FFR's `SanityCheckerV2` + `SCLogic`, with
the Archipelago export as the graded truth table. `docs/FLAG_COVERAGE.md` is the
table of every flag that logic consults and how the pack models it;
`docs/ORACLE.md` holds the cartridges and every grading figure.

## Open work, at a glance

Every open bullet on this page, in section order. The section says what kind of
work it is, not how much it matters.

| | |
|---|---|
| §3 | Whether Inspect survives `hide unreachable locations` |
| §3 | Warn once when a stale override shadows pack edits |
| §3 | Room-level zoom, after the towns |
| §4 | The lanes still to draw: the ported drafts, the by-eye pass, the run-wide order |
| §4 | A traversal lane on the maps with no chest |
| §4 | The No-Overworld map surface, and the incentive sheet behind it |
| §4 | Boss names in the Map Key |
| §5 | Three flags filed `unjudged` |
| §5 | Port from the export — blocked on a provenance decision |
| §5 | Two location trees, one rule set |

**Defects the register owns.** Open entries in `docs/ISSUES.md` that are work
someone could pick up, listed so the plan can see them; that page holds the
evidence and the history. It writes its entries as bullets rather than headings,
so there is no anchor to link to and the wording has to be the link: **each row
opens with the entry's own first words**, and grepping that phrase lands on the
entry. Anything after an em dash is this page's gloss rather than the
register's. Rewording either end is how a row stops resolving, which
`tools/tests/test_docs.py` now catches.

| | |
|---|---|
| doors | A door that lands on the floor it left does not mark itself — the bridge notices a door by a change of map, and a same-floor link is not one |
| doors | A pin missing from art that was drawn, wherever two rules derive the same content separately — one instance fixed, the sweep open |
| blocked | The derivation cannot say "reach another location", and Lefein is where that shows — the last `--derived` divergence. Wants the requirements solver in `docs/IDEAS.md`, so it is filed rather than small |
| maps | Crop boxes are looser than the map on several tabs — two causes, not one |
| maps | A room bigger than the guard stays shut — Mirage Tower 1F is 458 cells against `ROOM_MAX_CELLS` at 256, and raising it wants a measurement of what else opens |
| maps | The Map Key drops a font scale on the narrowest maps that carry a lane |
| lanes | A lane file's `region` is an index the digest does not guard |
| lanes | A stop at a chest re-orients for free, and nothing says whether it should |
| tests | Nothing tests the multi-tile OR in `derive()` |
| maps | The committed location-to-map table under-reports against a regen override — the tab is unaffected, since that comes from `MAP_VALUE`, which a regen does rewrite |
| board | The No-Overworld incentive poster is missing one slot, not two — of `nerrick` and `airship`, only `nerrick` is |
| board | The incentive defaults are still a guess on a version with no schema |
| board | The gold ring stops being gold once this pack's off filter has had it — `showIncentiveRings` may want a drawn "off" image |
| docs | `ChestsKeyItems` is a seven-chest flag, and the pack describes it as a general one — `maptab.lua:65-66` is the gloss |
| docs | The standard-seed reachability oracle is stated without its precondition |
| unproven | `smith $6209` reads `0x05` and `fairy $6213` reads `0x04` — the chest bit set where their rules test the event bit |
| upstream | A pinned control cannot survive Reset, and no pack-side change can make it — `Entrance Pins` and `Overworld Tab` start on Auto every launch |

Two more sit under a section above rather than here, because a bullet already
owns them: the No-Overworld overworld row and its 29 unrestamped pins is part of
§4's map surface, and the two dungeon trees being byte-identical — so
`test_maps.lua` check 6 cannot fail — is §5's.

## 1. Colours that are wrong on real seeds

Each item here is a pin that lied on a seed someone could roll. Each wants a
code, the affected `access_rules` alternatives, and **one oracle seed rolled
with the flag on** so `check_logic --ap-rules` grades the branch. A rule without
its oracle seed is a hand transcription, which is what section 5 is meant to end.

**Nothing here is open.** The last of it, the two rolls, closed 2026-09-05.

**Closed.**

- **The two rolls the bridge should read, not guess at. Closed 2026-09-05**, as
  one feature rather than two, which is what this bullet asked for. Both are
  permutations chosen at generation that reach neither the flag string nor the
  spoiler: the Cardia gateway permutation (`MetroidVaniaMap.cs:726`) and
  `ShuffleObjectiveNPCs`. The bridge reads both off PRG ROM and publishes
  `ff1/rolls`, one key with two fields; `tools/entrance_graph.py --rolls` is the
  same read offline, and `check_logic` reads it too, so the rules are graded on
  the seed in front of them.

  What it bought, measured: the six Cardia Forest locations agree on all four
  No-Overworld cartridges, `novhoard` gained the hoard's own route as well, and
  the Elf Prince's `WAIVED` row came off `objnpc497`. Bahamut's Cave was fixed
  in the other direction — it had one No-Overworld alternative, the Floater,
  which is too weak on a seed whose Ice Cave gateway leads there.

  Two things stayed strict on purpose, and `docs/ISSUES.md` has both: an NPC
  rolled into the third home, and everything on a session with no cartridge to
  read. `STATUS-2.md`, "The bridge reads the two rolls, and the rules stop
  guessing", has the build, the two measurements that made it small and the
  object the scoping named wrong.

- **Every flag that made a pin lie has a code or a recorded decision. Closed
  2026-09-01**, the last two — `MapAirshipHike` and `MapCardiaLandBridge` —
  graded on a cartridge each. Per-flag rows in `docs/FLAG_COVERAGE.md`,
  cartridges and before/after figures in `docs/ORACLE.md`.

- **A standard-world route the Cardia islands were missing. Closed 2026-09-01**,
  before it was diagnosed: the islands carried one route where Bahamut's Cave
  carried two, so pins beside a reachable Hoard stayed red. The entry is in
  `docs/ISSUES.md` and the cartridge is `hoarddockhike497`. The lesson is about
  the corpus rather than the rule — the flag *pair* had a cartridge each and the
  combination someone actually rolled had none, and a rule graded on each of two
  flags separately is not thereby graded on both.

- **Three closes are strict or declined rather than graded, and the difference
  matters.** `ShuffleObjectiveNPCs` and the Cardia roll are the permutations in
  the open bullet above: the pack deliberately disagrees with FFR there instead
  of agreeing with it, and both are waived by name in `check_logic` so the
  disagreement stays printed. `ExitToFR` is the third kind — decided against
  rather than pending, because it writes an exit portal and nothing else and
  this pack does not model points of no return. It sits in `NOT_MODELLED`, where
  a flag with no code can be told apart from one nobody has got to.

- **Seven incentive slots rang gold on seeds FFR did not incentivize them on.
  Closed 2026-09-03**, opened the same day by the first use of the export diff.
  FFR computes both conditions rather than storing them; the pack modelled one
  conjunct of each. `npcItems` and `npcFetchItems` now have codes and are ANDed
  into every alternative of the sections they speak for, and the caravan slot
  got `visibility_rules` instead, so it is not a check on that seed rather than
  an unringed one. Dr Unne, whom FFR never incentivizes at all, lost his slot
  rather than being re-gated.

  **What was actually missing was a grader**, and that is the part worth
  carrying forward: `check_logic` grades access rules against reachability, the
  rings answer to `priority_locations`, and nothing compared the two.
  `tools/tests/test_incentive_conjunction.py` closes that.
  `docs/ISSUES.md` has the entry. The one finding it turned up that no
  conjunction fixes — a chest `notail` names differently — is the close below,
  not a sentence here.

- **A slot rang for a location the seed does not have. Closed 2026-09-05**, by
  asking Archipelago instead of the flag string. FFR builds the export's
  location list out of the placement rather than the map, so which chest ids a
  seed carries moves with the roll and no flag predicts it — but the pool is
  stated outright at connect, and the pack has read it since the overworld-tab
  work. A ring now wants the flags *and* the seed to have the location, joined
  through the hosted item code that every slot row and every `LOCATION_MAPPING`
  id already carry. It fails open wherever no pool was stated, so a bridge-only
  session rings exactly as it did. The oracle seed is `notail`, where FFR's
  `priority_locations` is 20 entries against `std`'s 21 and the Sea Shrine is
  the missing one. `docs/ISSUES.md`, "A slot can ring for a location the seed
  does not have".

## 2. Boxes that do not exist

Things a bridge-only player checks that the board has no cell for.

**Nothing here is open.** The last of it, the three ToFR calibration offsets,
closed 2026-09-06.

**Closed.**

- **ToFR floor modelling. Closed 2026-09-06**, four halves in four days: the
  rules, the per-mode read, the pins that know the mode, and the offsets that
  let the hand art carry them.

  **The rules now distinguish the rooms from the gauntlet, 2026-09-05.** The
  whole gate used to sit on the `ToFR` node where a child could not widen it,
  and the two Lute Plate rooms are in front of the lute plate rather than
  behind it, so they were red on every Long and Mid seed — 31 of the 37
  cartridges on this machine. The node keeps `$canBreakOrb` and the five chests
  past the plate carry the rest themselves. `docs/ISSUES.md`, "Two ToFR chests
  were held red on every standard seed".

  **And each mode has been read, 2026-09-05.** `tofr_diff.py --dump` walks one
  cartridge instead of comparing two, because the diff refuses across modes on
  purpose. Long wires eight floors, Mid six, Short one; no mode erases a chest
  tile, so five of the seven indices sit on two tiles on Mid and all seven do
  on Short; and membership is stable within a mode across all 37 cartridges.
  `docs/ORACLE.md`, "What each mode builds".

  **And the pins now know the mode, 2026-09-06.** `ToFR Mode` is one item with
  three stages rather than a switch per mode, so the mode cannot contradict
  itself, and stage 0 — no cartridge read, or a flag string that says Random
  without resolving it — draws every mode's pin, which is what the board did
  before it could tell the modes apart. Each chest names the floor its mode
  puts it on. `tofrChaos` is calibrated to (13,13), solved from the room's
  extent because `ShortToFR` lays its seven chests onto art that predates them
  and there is no centroid to fit. And `regen_maps.py` drops the copies a
  cartridge lays and never wires, so a Mid regen no longer draws two markers on
  `ToFR 3F`.

  **And the last three offsets landed 2026-09-06, from a landmark rather than a
  heuristic.** `tofr1F` is (27,20), `tofrEarth` (13,18) and `tofrWater` (22,22),
  and the five pins that were waiting on them are in both dungeon trees: Mid
  draws its ten rather than five, which is the count that says this closed. Every
  Temple floor but 1F, 2F and Chaos carries exactly one fixed-formation battle
  tile — the fiend — at the same ROM coordinates on all five cartridges measured
  here including vanilla, and the art draws a boss plate on it; the offset is
  the difference between the two. 1F has no fiend and was anchored on its temple
  outline instead, cross-checked against the four corner stair glyphs.
  `tools/tests/test_calibration.py` re-derives both correspondences and fails on
  a one-pixel drift in either end.

  The room-extent rule had proposed `tofrEarth` correctly and `tofrWater` at
  (31,22), which is the Map Key panel rather than the room — that is what a
  content box does with furniture, and why the landmark is the better anchor
  where there is one. Five ways of finding an offset without a person looking
  have now been tried and written up as failures in
  `tools/map_calibration.json`, because the next person to want one will reach
  for them: edge energy over the image, edge energy restricted to the room,
  saturated-sprite centroids, the ROM wall mask correlated against per-tile
  brightness, and scoring an offset by void-tile agreement — the last two are
  the tempting ones, and both score high on a grid that is demonstrably wrong.

- **Re-cut 2026-09-01.** This section listed six bullets and read as six jobs.
  Three were already argued against in `docs/ISSUES.md` and are decisions rather
  than builds; one asked for rules that already exist; and the **No-Overworld
  incentive sheet moved to section 4**, behind the map surface it cannot be
  built without.

- **Titan has his cell; the other five stay declined. Done 2026-09-02.**
  Titan being fed is autotracked off `$6214`, so his box lights itself. Unne
  holds no shuffled item and the four fiends are spiked battle tiles that write
  no flag in vanilla or FFR, so all five would be manual-click forever
  (`docs/ISSUES.md`, "Five NPCs the cartridge places have no box anywhere").

  **The obstacle was a name, and the fix is the reusable part.** The NPC-pin
  join is keyed on the hosted code *being* what `extract_npcs.WANTED` calls
  object `$14`, so a section hosting anything else gets no pin, no object-gate id
  and no `npc` classification, and falls through silently in three tools at once.
  Freeing the name was cheaper than working around the clash: `Ruby` stage 2
  carries `rubyDone` and the cell hosts `titan`. `unne` has the identical clash
  at `items/items.json:202` and would resolve the same way.

  **Where the gate bites, measured across five cartridges:** both modes, not
  No-Overworld only. Every access rule on Titan's Trove already requires `ruby`
  on both trees, and so does Sarda's Cave, so on a seed that incentivized the
  Trove the slot behind him is a key item either way.

- **`shopItem` carries the free-NPC incentive flag now. Done 2026-09-03**, and
  reopened 2026-09-02 to get there. It first closed on the claim that FFR has no
  such flag, and that was wrong in the expensive direction: the flag is
  *computed*, not absent. `FlagsCompute.cs:217` makes `IncentivizeCaravan` the
  conjunction of `NPCItems` and `IncentivizeFreeNPCs`, and `PlacementContext.cs`
  puts the caravan shop into the incentive pool when it is true. The slot now
  carries the same `^$incentiveSlot|npcsAreIncentive` rule the six free-NPC
  slots do, in both incentive trees and in `scripts/incentive_slots.lua`.

  **Searching a flag schema for a name containing "shop" was always going to
  come back empty, and reporting that absence as FFR's answer was the mistake.**
  The pack's own `scripts/autotracking/flag_mapping.lua` already named the flag
  — FFR calls it "Main NPCs" — in the header comment of the file being searched.

  What survives unchanged: the pin clears itself, and the slot's *content* is
  roll noise even with the flag on. The slot's incentive status is a flag; what
  lands in it is the roll. Conflating those is what let the bullet close the
  first time. `docs/ISSUES.md`, "The `I: Shop Item` pin ignores the flag that
  governs it".

## 3. Clicks and confusion

- **The regen's execution half. Landed 2026-09-05, narrowed and guarded
  2026-09-07**: `tools/regen_maps.py --refresh` redraws every mode `--verify`
  calls stale, reading that mode's cartridge, `--npcs`, `--lanes`, `--retrace`
  and marker size back out of the cache rather than asking for them again, so
  the remedy is run rather than reconstructed by hand, and `--mode` narrows it
  to the one mode somebody is sitting down to play. It refuses where it would
  have to guess: a mode whose cartridge moved is reported and skipped with the
  exit status left at 1, and a mode whose art was drawn on another branch is
  refused by `branch_block`, the one copy of that comparison, which every path
  that draws asks. A refusal exits 3 rather than 1, so a caller can tell "you
  are on the wrong branch" from "the render broke". The detection half landed
  2026-08-31 (`STATUS.md`, "The art on disk now says what it was drawn for").
  `docs/ISSUES.md`, "A stale override silently shadows pack edits", holds both
  halves and the reason the gate itself stays read-only.
- **Room-level zoom.** The towns half landed 2026-08-31 (`STATUS.md`, "The towns
  got tabs the party can walk into"): `regen_maps.py` writes its own
  `mapValues.lua` into the override, so the tree that has the town art is the
  tree that names it. What is left is `UiHint("Zoom <map>")` and `UiHint("Pan
  <map>")`, per `docs/IDEAS.md`.
- **`hide unreachable locations` swallows skipped slots.** Decide whether
  Inspect should survive it.
- **What a diamond means. Answered 2026-09-04**: a union — a diamond means "a
  sprite check or an incentive slot", and the shape no longer reads backwards to
  "there is a sprite here". Written up for players in `README.md`, "What the pin
  shapes mean", rather than in the Map Key this bullet asked for, because the Map
  Key is rendered art and shape rows would move every marker on every map.
  `docs/ISSUES.md`, "What a diamond means", holds the reasoning.
- **A hint names a location the board cannot find. Closed 2026-09-09.**
  Archipelago's names and this pack's are two vocabularies that disagree on 254
  of the 255 they share, and neither wanted renaming: AP's read as route jargon
  plus a floor label, the pack's say where the thing is on the drawn floor, and
  on a map board the second is the one that helps. The defect was the 81 that
  end in a number that disagrees, several of them transposed -- AP's `Northwest
  Castle - Treasury 2` is this pack's `North West Castle Chests 3` while AP's
  `Treasury 3` is the pack's `Chests 2`, so matching by eye lands on the wrong
  chest with nothing to say so.

  What answers it is the correspondence stated outright, on every check and on
  every hint, with the tab beside it. The pins a hint names light in the hint's
  own colour and stay lit while it stands. `docs/ISSUES.md`, "A hint names a
  location the board cannot find", has the build and what it left behind;
  `STATUS-2.md`, "The hints say where they land", has the reasoning.

  **The scout handler was the wrong channel**, which is the part worth not
  re-deriving: `AddScoutHandler` fires on replies to scouts the pack itself
  asked for, and `LocationScouts` is refused unless the manifest carries
  `apmanual` or `aphintgame` -- flags that let a pack create hints rather than
  read them. Hints reach an ordinary client through data storage, under
  `_read_hints_<team>_<slot>`, which is the key Archipelago's own client
  watches. The two handlers this pack had registered and never subscribed
  anything to are the channel now.

  **It does not tab there**, which is where this bullet's own sketch was wrong.
  `activateMapTab` follows the party on every floor change, so a tab moved by an
  arriving hint is both intrusive mid-play and taken back at the next change.

- **Twelve Deep Dungeon locations are in no mapping.** The AP world carries 267
  locations to the randomizer's 255; the twelve extra are Deep Dungeon
  (`DeepDungeon29B_Chest146` and friends, ids 401-404 and 443-451), and
  `LOCATION_MAPPING` has none of them. On a Deep Dungeon seed those checks
  arrive and land nowhere on the board. Worth knowing before deciding whether
  the mode is in scope at all -- and those twelve are also the only entries in
  that file that do not follow the randomizer's player-facing naming, so if
  anything there wants renaming it is them rather than the 255.
- **Stale user-override shadowing pack edits.** Warn once.

## 4. Maps

- **Entrance markers.** On a shuffled seed the hand art's exits are wrong, so
  these are the top map item for a No-Overworld or entrance-rando player.

  **The overworld doors landed 2026-09-04**: 30 trapezoid pins on a standard
  cartridge, one per door, drawn on regenerated art only and switched by the
  three-stage `Entrance Pins` control. A door's *position* is not shuffled, so
  that half is cartridge-invariant and spoils nothing.

  **The dungeon floor links landed the same day**: 148 staircases, holes and
  floor doors on the standard oracle, 190 on the No-Overworld one, in the same
  group and under the same switch. Same-floor links are kept -- every one of
  them in the game is a warp pad on Castle of Ordeals 2F, 15 on both cartridge
  kinds -- because they are the same kind of tile as a real link and a player
  wants to know. So is the way out of a floor, which is a `warp` tile and was
  dropped with the town borders until the cluster-and-content rule told the two
  apart; `STATUS-2.md`, "And the staircases with them", has the measurement.
  Left:

  **The observation channel landed 2026-09-06.** The bridge reads the party's
  tile off `$27/$28` and `$29/$2A`, notices a map change between two trusted
  scans, and publishes `ff1/edges` -- a log of doors somebody has actually
  walked through. The pack marks the pin standing on the departure tile, so the
  open-door icon means what it always said and is no longer a click. Nothing
  reads a teleport table on the tracker's side of the wire, which is the point:
  reveal-on-visit cannot spoil a seed. `entrance_graph --grade` is the
  independent reading that says the channel is right, and the corpus gained
  `entrances`, the only cartridge in it whose doors move. `STATUS-2.md`, "The
  doors open themselves now", has it.

  **And the destination has a name on it, 2026-09-07**, which closes this item.
  Each pin hosts an item whose `BadgeText` reads `->Marsh Cave B1`, a left-click
  tabs to where the door came out and a right-click to what leads here, with the
  far pin lit gold while you find it. The destination was already in the record
  and thrown away -- an `ff1/edges` line is six fields -- so nothing new is read
  off the cartridge and the badge is still the party's own walk.

  One of the two notes carried over from palex00's pack turned out to be wrong
  here and is worth not re-deriving: **the hosted item must provide its code
  unconditionally**. `locationsection.cpp:236-249` clears a section only when
  its items are cleared *and* every hosted code has a provider, so tying the
  provide to the reveal would hold the pin open and take the hand-click clear
  away with it. This pack already has a state channel for a door; the badge is
  text. `STATUS-2.md`, "The doors say where they went".
- **Naming an entrance for what it is, not where it stands. Done 2026-09-07.**
  A pin was called `Entrance: SeaShrineB3 49,37`, so the floor this bullet
  named was seven pins a player had to read as coordinates -- six staircases and
  a well, which is the count on `std497` rather than the six written here
  before. It is now `Entrance: SeaShrineB3 NE Upstairs`, and the reading it asked
  for
  first came back mixed: FFR carries three tables that could name a floor link
  and only two of them describe the door's own end.

  `ExitTeleportIndex` does, and is used -- Titan's Tunnel splits into
  `ExitTitanEast` and `ExitTitanWest`. `TeleporterGraphic` does, through
  `TeleportTilesGraphics`, which is FFR's table for *drawing* the teleporters it
  invents and read backwards classifies the ones already on a cartridge: that is
  where `Upstairs`, `Hole` and `Well` come from, and it is what keeps the noun
  from being a guess about tile ids. **`TeleportIndex` does not, and is
  deliberately unused** -- its 64 names are a teleport's vanilla *destination*
  (`MarshCaveTop`, `EarthCaveVampire`), so a pin wearing one would claim a
  destination on a seed that had moved it. That is the constraint below, and it
  is the whole reason the obvious table is the wrong one.

  The rest is the frame the tab draws: where a link sits in it, and a number
  where two of the same thing share a corner. Measured across 45 cartridges,
  6,899 pins, no two names colliding and none falling back to coordinates.
  `STATUS-2.md`, "The doors are named for what they are".

  The two constraints it inherited both held. A name shows in the location list,
  so it describes the door's own end. And the badge already carries the
  destination once walked, so this was only ever about telling two staircases on
  one floor apart -- which is why a vocabulary that names 122 of 149 pins was
  enough and the 27 it misses lose a noun rather than a name.

  palex00's Crystal pack was the prompt and turned out not to be the model: his
  are hand-authored in a registry, and none of these are typed out.
- **The lanes still to draw.** Three things, in the order they cost a player
  something:

  **Every floor with a lane file now has a No-Overworld entry, as of
  2026-09-05.** Narrowing the layout digest on 2026-09-04 handed back the floors
  tile-identical to their standard twins, and `tools/port_lanes.py` carried the
  rest across the same day (`docs/ISSUES.md`, "The layout digest refuses a floor
  over which enemies a trap tile spawns"); the floors it refused were authored
  by hand over the two days after. Ask the tool rather than this page for the
  tally -- `tools/port_lanes.py --from <std> --to <nov>` writes nothing without
  `--apply` and prints the count either way, which is the same reason the
  ported-draft figure below is not citable. The carry is **verbatim** and has to
  stay that way: dropping the `at` hints from `arrival` and `exit` stops
  collapses a route lane to the cheapest pair of ends the floor offers, on 23 of
  them.

  **The ported ones are drafts, not finished lanes.** Each is the standard route
  replayed on a floor whose walls have moved, so it is legal and may still be
  silly — a corridor that was the short way round on one cartridge can be the
  long way on another. Reviewing them in `tools/lane_edit.py` is the open work,
  and it is looking rather than drawing. Each carries `"ported": true` and
  `lane_edit` clears it on save, so how many are left is a question for the
  files rather than for this paragraph: 32 when they were carried across, 26 on
  2026-09-04, 14 after the 2026-09-05 pass. That figure is here so a reader
  knows roughly what is left before
  running the grep, not so it can be cited — a count in prose beside a count in
  the files is the one that goes stale.

  **The ten that refused the carry were authored by hand 2026-09-04**, in "Author
  the ten No-Overworld floors that refused, and review six of the drafts". They
  refused for three different reasons -- six towns plus `tofr1F` lost the
  arrival outright, `elf_castle` and `nw_castle` kept an arrival they could not
  walk from, and `bahamutB2` failed on a chest index -- and none of the three
  was a copying problem: the arrivals are No-Overworld sealing and re-stamping
  town entrances, which wants a cartridge in front of you.
  `bahamutB2` is the odd one and worth knowing about: its standard twin carries
  a loot round, and the No-Overworld floor carries a route lane instead, so the
  two cartridges draw that floor differently on purpose.
  `tools/tests/test_port_lanes.py` walks the pairing.

  **Authoring a floor is per cartridge, and a fresh standard roll is where that
  bites.** A lane resolves through `lane_file.digest`, so a layout the files
  have no entry for draws nothing and says nothing. Towns are the worst affected
  because their layouts move most: measured across 14 cartridges on 2026-09-05,
  resolution runs 47 to 57 of 57, `gaia` fails on 11 of the 14, and one standard
  roll loses six of its seven towns. That is what "Author route lanes for seven
  more floors" was for -- seven layouts on one new weekly cartridge -- and it is
  a recurring cost per cartridge rather than a pass that ends.

  **The by-eye pass against DarkmoonEX's 58 drawn images has not started.** The
  reference is the acceptance test, not the input: his lanes are drawn on
  vanilla layouts and the regenerated art exists for the seeds where the layout
  is not vanilla — the same trap the trap-tile letters fell into
  (`docs/ISSUES.md`, "Our trap letters are not DarkmoonEX's"). Walk them one at
  a time recording agree or disagree-and-why; a disagreement is either a bug in
  the cost function or a judgement of his that is not in the published rule, and
  only the second kind needs transcribing.

  **A loot lane still walks to a linked chest whose twin an earlier floor would
  have cleared**, which needs a run-wide order the router has no notion of.
- **A traversal lane on the maps with no chest.** `plan()` returns `None` on an
  empty `chest_groups`, which was right when every lane was a loot round and is
  not now: the other 23 maps have a walk through them. Cheap, and deferred off
  the editor branch only because it moves all 61 images.
- **The No-Overworld map surface, and the incentive sheet that waits on it.**
  The connection diagram — a hand-drawn pseudo-overworld with the fixed links as
  roads. The topology is measured and stable.

  **The incentive sheet moved here from section 2 on 2026-09-01, because it
  cannot be built before this is.** Deriving its 28 pins needs a surface to
  resolve them against, and `regen_maps.py` gives `nov` mode no overworld render
  *by design*. Until this lands those 28 pins stay hand-placed pixels on a JPEG.

  **The `nerrick` slot is splittable and need not wait.** It is a real
  Archipelago location on this mode and both dungeon trees carry it. One slot,
  not two — `airship`'s absence is correct and is not to be re-derived as a pair
  (`docs/ISSUES.md`, "The No-Overworld incentive poster is missing one slot, not
  two"). Adding it against the existing JPEG is a hand edit plus bumping the nov
  count 20 → 21 in `SHEET_RULED`, `tests/test_pins.lua:160`.
- **Boss names in the Map Key**, from the formation ids already in hand.

**Closed.**

- **Routes on regenerated maps. Built 2026-08-31, authored 2026-09-04.**
  `tools/lane.py` routes and `render_maps.draw_lanes` draws, baked at render
  time because the PopTracker tab is a static image. `tools/lane_edit.py` serves
  a page on loopback where a person clicks the stops and the router fills in the
  walking between them; stops are typed so a lane outlives the seed it was drawn
  on, and `tools/lanes/<map>.json` carries a digest of the floor that refuses to
  draw on a floor it was not drawn for. 57 files, 102 lanes, merged into `trunk`
  on 2026-09-04. Whether a floor's loop is worth collapsing is recorded per
  floor: seventeen carry `retrace: true`. `STATUS-2.md` has the build, from "The
  route lanes are named for what they are, and a person draws them now" onward.

  **Why an editor rather than a better solver.** A solver cannot know which
  chests are worth the detour on a given seed, nor which to visit first, and a
  map with no chest got no lane at all — none of which is a tuning problem. The
  router stays exactly as it is and becomes the pathing primitive.
  `tools/lane.py` and `tools/lane_edit.py` both cite this by name.

  **The naming fix landed with it**, because an editor that authored into the
  wrong vocabulary would have had to be re-authored: the traversal lane is
  arrival to the nearest exit opening nothing, and the loot lane holds the
  floor's items from the start. The Map Key drew those as "Optimal Route" and
  "Optimal Route for Loot" until 2026-09-05 and now draws `Route` and `Route
  for Loot` -- the meanings are the ones authored against either way, and
  `docs/IDEAS.md` has what the naming cost and why the adjective went.

  **The spoiler question is settled: a lane ends at the nearest exit.** Most
  chest-bearing maps have several on both duck cartridges, and the lane finishes
  at whichever is closest, which the shuffle has no bearing on. It says "there
  is a way out here", which the art already drew, and not "this is the way
  onward".

## 5. Tooling that keeps 1–4 true

- **Three flags are filed `unjudged`, and that is the open work.**
  `NPCSwatter`, `FiendsRefights` and `ShortToFRFiendsRefights`. Each says why it
  is unsettled and names the measurement that would settle it, rather than
  borrowing a neighbour's reason, and each is waiting on a cartridge nobody has
  rolled. A list padded to make the test pass is the test not existing. Each is
  a section-1 candidate if it turns out to move a pin.

  **The count belongs on one page and this is not it.** This line said five
  while `flag_mapping.lua` held three and `docs/FLAG_COVERAGE.md` printed three,
  because three entries left the list within hours of each other and this copy
  subtracted one of them. That page carries the tally
  `tools/tests/test_flag_coverage.py` reads; a count stated in two places with a
  test on one of them drifts on the other.
- **Port from the export.** A script that reads FFR's Archipelago export and
  emits the `$`-guarded `access_rules`, replacing hand transcription. One export
  per FFR version, not per seed.

  **Blocked on a decision, not on effort.** Compiling makes the oracle and the
  rules the same object, so `check_logic` stops being an independent check and
  the cartridge sweep — 215 of `nov`'s 226 — becomes the only independent
  reading left. `docs/IDEAS.md` ("Solve the requirements instead of sampling
  them") has both sides with the figures attached. **It is a judgement about
  provenance rather than a technical question, so it gets taken deliberately, in
  its own session, against one stated criterion: is the cartridge sweep alone
  enough cover?** Nothing here gets built before that.
- **Two location trees, one rule set.** `isNoOverworld()` landed, and **the
  byte-identical claim is true of the overworld pair only** —
  `locations/overworld.json` and `locations/NOverworld/overworld.json` share an
  md5, but the two incentive sheets genuinely differ, by 241 lines, with
  different region names and a different node structure. So this is one file
  pair, not two.

  Either collapse that pair or make `test_maps.lua` check 6 able to fail (a
  deliberately diverged fixture); check 6 compares only the overworld pair, so
  today it cannot fail for any reason. Decide alongside the section 4 map
  surface, since a differently-cropped No-Overworld dungeon tree is the one
  reason to keep two.

**Closed.**

- **The flag-coverage test. Closed 2026-09-01.**
  `tools/tests/test_flag_coverage.py` fails when FFR grows a flag nothing in
  `flag_mapping.lua` models. It reads structurally rather than by grep, which
  closes the hole a grep leaves in both directions: `GameMode` is a quoted
  literal nowhere, and a name left in a commented-out entry satisfies a grep
  while modelling nothing — this pack's oldest failure shape, which the test
  demonstrates rather than asserts about. Counts and the `NOT_MODELLED` tally
  are `docs/FLAG_COVERAGE.md`, "Keeping this current".
- **Pin the FFR revision. Closed 2026-09-01.** `tools/tests/test_ffr_pin.py`
  holds the chain that was true and enforced nowhere: the schema's `build_sha`,
  the `pinned_commit` in `pins.yaml`, and the SHA stamped into `FFRVersion.cs`.
  It found the loose link on the way — `gen_schema.py` derived `build_sha` from
  `git rev-parse HEAD`, which on the pinned worktrees is not the commit the
  cartridges claim, so it reads the stamp now. The review drew the lesson: a
  conjunction that comes out false demonstrates neither conjunct.
- **The lane editor. Closed 2026-09-03.** `tools/lane_edit.py`, filed here
  rather than in section 4 because what it keeps true is that a drawn route is a
  person's judgement rather than a solver's guess. Two things earn its place:
  the page has no pathfinder of its own, so what it draws is what the bake
  draws, and it re-walks every lane server-side before writing, so it cannot
  author a file `regen_maps` will then refuse.
- **An export-vs-export diff. Built 2026-09-03.** `tools/export_diff.py` rolls
  two cartridges one flag apart, diffs the exports and attributes the moved
  rules to the flag — which is how every flag row in `docs/ORACLE.md` was
  produced, about fifteen times, by hand. It compiles nothing, so it costs none
  of the independence the bullet above would.

  **The scope was one assumption short, and the corpus said so.** "One flag
  apart holds everything but the flag still" is true of the rules and true of
  the pool only by count, because a flag moves the RNG stream. A differ that
  counted that churn would have found something for every flag including the one
  that found nothing, which is the shape of a tool that looks like it works. The
  pool difference is printed under its own heading and not counted — but a flag
  that changes the pool's *shape* removes locations for real, so the tool
  crosses the pool difference with `priority_locations` and marks a name that
  left both. `docs/ORACLE.md`, "Diffing the corpus, and what one flag apart does
  not hold still".
- **`check_logic`'s default `--ff1-world` was wrong and failed silently. Closed
  2026-09-03.** `ap_location_paths` defaulted one directory short, hit `return
  {}`, and reported every location unmapped as a cheerful zero — the failure
  this tool can least afford, a zero reading as agreement. The default now
  resolves 255 locations where it resolved none, and a `--ff1-world` given
  explicitly and not found refuses instead of skipping. The default still being
  absent is still a skip, because a machine with no Archipelago checkout is an
  ordinary condition.
- ~~**More oracle seeds.**~~ **Obsolete 2026-09-01.** It said "two flagsets is
  thin" and predates the 4-9-7 corpus; `docs/ORACLE.md` has the inventory. What
  is still ungraded is not a seed-count problem and is named elsewhere: the
  three ToFR flags the export cannot see, `Shop Item`, and the two permutation
  rolls closed strictly rather than graded.

## Frozen

Stated once so nobody re-derives them.

- **`tools/noverworld_rules.py`** is frozen. It did its job — it disproved the
  substitution plan and gave the No-Overworld rules an independent reading. Its
  remaining gaps (`docs/ORACLE.md`, the eleven) are properties of the tool, not
  the pack; the shipped rules are graded against the export, which is the
  correctness criterion. Keep it runnable; stop closing its gaps.
- **Compile-from-export** is absorbed into section 5, where it now carries its
  blocking decision, that decision's owner and the criterion it turns on.
- **Names that have drifted** and **the four `NoMap` variants** stay in
  `docs/IDEAS.md` until there is a user to ask.

## What each branch landed

**This section no longer says where any branch stands, because it could not be
kept true.** It carried a standing status line that was wrong about a branch
four times in four days, in both directions — claiming unpushed work that was
pushed and pushed work that was not — and twice carried a commit count that went
wrong, once inside the commit that wrote it. A line nothing re-reads outlives
its subject.

Ask git instead. `git log trunk..<branch>` says whether a branch has anything
left in it; `git rev-list --count origin/trunk..trunk` says how far ahead trunk
is; `git fetch` first, because a merge done on GitHub outside a session makes a
local count a lie.

What stays is the record of what each merged branch was for, dated on the day it
merged. That is a fact about the past and cannot go stale.

**This list is not every branch, and does not try to be.** It holds the ones
that closed a whole section. The others are recorded where their conclusions
live, in the `STATUS` log and the docs page that owns each, and `git log
--merges` lists them in order — a duplicate here would be the copy that goes
stale.

- **`flag-coverage` merged 2026-09-01**, and was the whole of section 5's first
  two bullets: `test_flag_coverage.py` and `test_ffr_pin.py`. The review gate
  ran and every finding is committed; it found a coverage row that did not
  demonstrate the term it named — a conjunction of ancestry and the stamp, of
  which only the stamp ever fired. The two terms are separate rows now.
- **`flags-real-seeds` merged 2026-09-01**, and was the whole of section 1: the
  `ChaosRush` and `ToFRMode` codes, the `ExitToFR` decision, `MapAirshipHike`
  and `MapCardiaLandBridge` graded on a cartridge each, the two verify flags,
  `ShuffleObjectiveNPCs` closed strictly, Gaia settled against FFR, the
  mode-mismatch light, and the flags grid on the variants that had none.

  **The review gate ran on 2026-09-01** and every finding is committed. It found
  a real hole the oracle structurally could not see — Bahamut's Cave never got
  the `airshipHike` or `cardiaLandBridge` alternatives, because FFR's export has
  no Bahamut location to grade against — and it was also wrong once in the
  direction that would have deleted a correct route, which the cartridge
  settled. Seven more 4.9.7 cartridges came out of answering it.
- **`export-diff` merged 2026-09-03**: `tools/export_diff.py` plus the two
  section-1 findings it immediately produced. The review gate ran twice, six
  findings then nine. The first pass found the pool heading hiding this branch's
  own second finding — `NPCItems` off deletes the caravan slot, and the tool was
  calling that gold moving between chests.
- **`lane-editor` merged 2026-09-04**, and was section 4's route work: the
  editor, the 57 authored lane files, the three-pixel line, the arrowhead
  nudge, and the per-floor retrace flag. The review gate ran twice, eleven
  findings then nine, all fixed rather than waived. The standard art moved to
  `duck-weekly-0831-v2` with it, because a lane file refuses the cartridge it
  was not drawn on and only ten of the 57 resolved on the old one.
