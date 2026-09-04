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
| §1 | The two rolls the bridge should read, not guess at |
| §2 | ToFR floor modelling |
| §3 | Whether Inspect survives `hide unreachable locations` |
| §3 | What a diamond means |
| §3 | Warn once when a stale override shadows pack edits |
| §3 | Room-level zoom, after the towns |
| §3 | The regen's execution half, after the detection half |
| §4 | Entrance markers |
| §4 | The lanes still to draw: ten No-Overworld floors, 32 ported drafts, the by-eye pass, the run-wide order |
| §4 | A traversal lane on the maps with no chest |
| §4 | The No-Overworld map surface, and the incentive sheet behind it |
| §4 | Boss names in the Map Key |
| §5 | Three flags filed `unjudged` |
| §5 | Port from the export — blocked on a provenance decision |
| §5 | Two location trees, one rule set |

## 1. Colours that are wrong on real seeds

Each item here is a pin that lied on a seed someone could roll. Each wants a
code, the affected `access_rules` alternatives, and **one oracle seed rolled
with the flag on** so `check_logic --ap-rules` grades the branch. A rule without
its oracle seed is a hand transcription, which is what section 5 is meant to end.

- **The two rolls the bridge should read, not guess at.** Both are permutations
  chosen at generation that reach neither the flag string nor the spoiler, and
  both are answered today by being deliberately strict. They want one feature
  between them, not two.

  The **Cardia roll** is the gateway permutation (`MetroidVaniaMap.cs:726`); the
  bridge would publish `ff1/gateways` next to `ff1/flags` and the rule reads it.
  The **objective-NPC roll** is the same shape one flag along, and
  `tools/extract_npcs.py` already knows how to find it — it is what measured the
  Bahamut/Unne swap in the first place. `regen_maps.py` reads the cartridge per
  seed already; the live bridge does not publish NPC positions.

  Until then both stay strict, which costs six Cardia Forest locations on a
  No-Overworld seed and the Elf Prince plus Dr Unne on a shuffled one.

**Closed.**

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
  `docs/ISSUES.md` has the entry and the one further finding still open, which
  no conjunction fixes: a chest `notail` names differently.

## 2. Boxes that do not exist

Things a bridge-only player checks that the board has no cell for.

- **ToFR floor modelling.** The rules are *not* unwritten:
  `locations/overworld.json:410` carries three alternatives on the `ToFR` node
  and the seven chests inherit them. What is unwritten is the *floors* — Mid
  ToFR deletes 2F and 3F outright and the tree does not know, and nothing
  distinguishes the Lute Plate rooms or the Kary floors from the entrance. The
  AP export drops ToFR unconditionally, so `tofr_diff.py` stays the only check
  and any change here needs its own measured cartridge pair.

**Closed.**

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

- **The regen's execution half.** The detection half landed 2026-08-31
  (`STATUS.md`, "The art on disk now says what it was drawn for"):
  `regen_maps.py` writes `.regen_stamp`, the bridge compares it against the
  cartridge and publishes `ff1/art`, and the `artStale` light says so on the
  board. Left: running the regen, which no longer gates on a measurement now
  that `os.execute` is known to run and detach.
- **Room-level zoom.** The towns half landed 2026-08-31 (`STATUS.md`, "The towns
  got tabs the party can walk into"): `regen_maps.py` writes its own
  `mapValues.lua` into the override, so the tree that has the town art is the
  tree that names it. What is left is `UiHint("Zoom <map>")` and `UiHint("Pan
  <map>")`, per `docs/IDEAS.md`.
- **`hide unreachable locations` swallows skipped slots.** Decide whether
  Inspect should survive it.
- **What a diamond means.** Settle it and put it in the Map Key.
- **Stale user-override shadowing pack edits.** Warn once.

## 4. Maps

- **Entrance markers.** On a shuffled seed the hand art's exits are wrong, so
  these are the top map item for a No-Overworld or entrance-rando player; the
  design is in `STATUS.md`, "Designed, not started". First increment is the
  bridge's edge log plus a console print, display half after.
- **The lanes still to draw.** Three things, in the order they cost a player
  something:

  **No-Overworld has 47 of 57, and the ten left are authoring rather than
  copying.** Narrowing the layout digest on 2026-09-04 handed back the 15 floors
  tile-identical to their standard twins, and `tools/port_lanes.py` carried the
  other 32 across the same day (`docs/ISSUES.md`, "The layout digest refuses a
  floor over which enemies a trap tile spawns"). The carry is **verbatim** and
  has to stay that way: dropping the `at` hints from `arrival` and `exit` stops
  collapses a route lane to the cheapest pair of ends the floor offers, on 23 of
  them.

  **The 32 are drafts, not finished lanes.** Each is the standard route replayed
  on a floor whose walls have moved, so it is legal and may still be silly — a
  corridor that was the short way round on one cartridge can be the long way on
  another. Reviewing them in `tools/lane_edit.py` is the open work, and it is
  looking rather than drawing.

  **The ten that refuse are the authoring pass.** Six towns plus `tofr1F` lose
  the arrival outright; `elf_castle` and `nw_castle` keep an arrival they cannot
  walk from; `bahamutB2` fails on a chest index. The arrivals are No-Overworld
  sealing and re-stamping town entrances, so they want a cartridge in front of
  you rather than a copy. The same ten refuse on the nov oracle, which is the
  pairing `tools/tests/test_port_lanes.py` walks.

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
  count 20 → 21 in `SHEET_RULED`, `tests/test_pins.lua:153`.
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
  wrong vocabulary would have had to be re-authored: "Optimal Route" is the
  traversal lane, arrival to the nearest exit opening nothing, and "Optimal
  Route for Loot" holds the floor's items from the start. `docs/IDEAS.md` has
  what it cost.

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
