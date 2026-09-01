# What is next, in order

This file says what gets built next and why, ordered by what a player sees.

**Forward-only means ordered by what is next, not that finished work vanishes
from here.** A closed item stays, dated, shrunk to its conclusion and a pointer
to where its evidence lives; it leaves the page when the section it sits in is
superseded. Deleting a close outright is the failure this page keeps hitting
from the other side — nothing re-reads a line once it is written, so an item
that goes quiet outlives its own answer. Defects live in `docs/ISSUES.md`,
unscoped ideas in `docs/IDEAS.md`, the narrative in the `STATUS` log.

The triage rule, from 2026-08-30: **does it change a colour, add a box, or save
a click?** If yes it is product and goes in sections 1-4. If no it is tooling
and goes in 5, where it earns its place by keeping 1-4 true. **Amended
2026-09-01, when sections 1 and 5's first two bullets all closed**: the rule
sorts tooling last by construction, which was right while section 1 was open and
is not now. Every section-1 close cost one hand-rolled cartridge, one
hand-written rule and one grading run, and that is the standing per-flag price
at the next FFR version bump. Section 2 is what comes next.

The parity target for every rule is FFR's `SanityCheckerV2` + `SCLogic`, with
the Archipelago export as the graded truth table. `docs/FLAG_COVERAGE.md` is the
table of every flag that logic consults and how the pack models it;
`docs/ORACLE.md` holds the cartridges and every grading figure.

## 1. Colours that are wrong on real seeds

Each item here is a pin that lied on a seed someone could roll. Each wants a
code, the affected `access_rules` alternatives, and **one oracle seed rolled
with the flag on** so `check_logic --ap-rules` grades the branch. A rule without
its oracle seed is a hand transcription, which is what section 5 is meant to end.

**Closed 2026-09-01.** Every flag that made a pin lie now has a code or a
recorded decision, and the last two — `MapAirshipHike` and `MapCardiaLandBridge`
— were graded on a cartridge each. The per-flag rows are `docs/FLAG_COVERAGE.md`;
the cartridges and their before/after figures are `docs/ORACLE.md`; how each was
found is `STATUS.md`. The next thing that makes a pin lie goes here, under the
rule above.

Two of the closes are **strict** rather than graded, and the difference matters.
`ShuffleObjectiveNPCs` and the Cardia roll are permutations chosen at generation
that no file the pack can read records, so the pack deliberately disagrees with
FFR there instead of agreeing with it. Both are waived by name in `check_logic`
so the disagreement stays printed. `ExitToFR` is a third kind: decided against
rather than pending, because it writes an exit portal and nothing else and this
pack does not model points of no return. It sits in `NOT_MODELLED`, where a flag
with no code can be told apart from one nobody has got to.

- **The two rolls the bridge should read, not guess at.** The one open item left
  in this section. Both are permutations chosen at generation that reach neither
  the flag string nor the spoiler, and both are answered today by being
  deliberately strict. They want one feature between them, not two.

  The **Cardia roll** is the gateway permutation (`MetroidVaniaMap.cs:726`); the
  bridge would publish `ff1/gateways` next to `ff1/flags` and the rule reads it.
  The **objective-NPC roll** is the same shape one flag along, and
  `tools/extract_npcs.py` already knows how to find it — it is what measured the
  Bahamut/Unne swap in the first place. `regen_maps.py` reads the cartridge per
  seed already; the live bridge does not publish NPC positions.

  Until then both stay strict, which costs six Cardia Forest locations on a
  No-Overworld seed and the Elf Prince plus Dr Unne on a shuffled one.


## 2. Boxes that do not exist

Things a bridge-only player checks that the board has no cell for.

**Re-cut 2026-09-01.** This section used to list six bullets and read as six
jobs. Three of them were already argued against in `docs/ISSUES.md` and are
decisions rather than builds; one is blocked on a section-4 item and has moved
there; and one asks for rules that already exist. What follows is what is
actually left.

- **The six NPCs with no box are one list, and the answer is Titan only.**
  `tools/tests/test_npc_pins.py:90` is the list — `kraken`, `lich`, `marilith`,
  `tiamat`, `titan`, `unne` — and it was three separate bullets here until now.
  **Titan gets a cell; the other five are declined.** The distinguishing fact is
  a signal: Titan being fed is already autotracked at
  `scripts/autotracking/ram_mapping.lua:119` (`ruby` stage 1, `$6214`), so his
  box would light itself. Unne holds no shuffled item and the four fiends are
  spiked battle tiles that write no flag in vanilla or FFR — the orb byte is set
  by the altar, not the kill — so all five would be manual-click forever
  (`ISSUES.md`, "Six NPCs the cartridge places have no box anywhere" and "The
  four Fiends and the ToFR refights cannot be autotracked at all"). That is a decision, and it is taken here rather
  than left as a gap somebody re-opens.

  What Titan still wants is **a fresh hosted code**, because `titan` is spent:
  `items/items.json:174` gives it to `Ruby` stage 2. `unne` has the identical
  clash at `:202` (`slab,slabTranslated,unne`), which is worth knowing so it is
  not rediscovered as a second problem if the Unne decision is ever revisited.
  Bridge-only either way — neither is an Archipelago location.
- **`shopItem` has no incentive toggle because FFR has no such flag.** This
  bullet used to read as missing wiring. It is not: there is no
  `IncentivizeShopItem` anywhere in the 4-9-7 schema, and
  `docs/FLAG_COVERAGE.md` records `Shop Item` as tracking where the shop landed — roll noise, not a flag. Nothing to map, so the honest close is to say
  so on the board's Map Key rather than to build a toggle.

  **The real defect on that pin is a different one and is already filed**:
  `I: Shop Item` carries no access rule at all, so it is green on a seed that
  put it behind a vehicle, and `check_logic` cannot even grade it —
  `docs/ISSUES.md`, "`I: Shop Item` carries no rule at all". That is the entry
  to work from.
- **ToFR floor modelling.** The rules are *not* unwritten, which is what this
  bullet used to claim: `locations/overworld.json:410` carries three
  alternatives on the `ToFR` node and the seven chests inherit them. What is
  unwritten is the *floors* — Mid ToFR deletes 2F and 3F outright and the tree
  does not know, and nothing distinguishes the Lute Plate rooms or the Kary
  floors from the entrance. The AP export drops ToFR unconditionally, so
  `tofr_diff.py` stays the only check and any change here needs its own measured
  cartridge pair.
- **The No-Overworld incentive sheet has moved to section 4**, behind the map
  surface it cannot be built without. The `nerrick` slot is splittable out of it
  and is described there.

## 3. Clicks and confusion

- **Notice when the drawn maps are for another cartridge.** A regenerated set
  from the last seed under this seed's pins is worse than the hand art. The
  detection half landed 2026-08-31 (`STATUS.md`, "The art on disk now says what
  it was drawn for"): `regen_maps.py` writes `.regen_stamp`, the bridge compares
  it against the cartridge and publishes `ff1/art`, and the `artStale` light
  says so on the board. Left: the execution half, which no longer gates on a
  measurement now that `os.execute` is known to run and detach.
- **Follow the party into rooms.** The towns half landed 2026-08-31 (`STATUS.md`,
  "The towns got tabs the party can walk into"): `regen_maps.py` writes its own
  `mapValues.lua` into the override, so the tree that has the town art is the
  tree that names it. What is left is the room-level zoom -- `UiHint("Zoom
  <map>")` and `UiHint("Pan <map>")`, per `IDEAS.md`.
- **`hide unreachable locations` swallows skipped slots.** Decide whether
  Inspect should survive it.
- **What a diamond means.** Settle it and put it in the Map Key.
- **Stale user-override shadowing pack edits.** Warn once.

## 4. Maps

- **Entrance markers.** On a shuffled seed the hand art's exits are wrong, so
  these are the top map item for a No-Overworld or entrance-rando player; the
  design is in `STATUS.md`, "Designed, not started". First increment is the
  bridge's edge log plus a console print, display half after.
- **Routes on regenerated maps — built, and off by default (2026-08-31).**
  `tools/lane.py` routes it and `render_maps.draw_lanes` draws it, baked at
  render time in `regen_maps` because the PopTracker tab is a static image.
  One colour per lane with the key in the Map Key band. `STATUS.md`, "The route
  to walk is drawn on the map".

  **`--lanes` now defaults to `none`, and the next step is an editor rather
  than a better solver.** Three things say the derived lane is the wrong
  product: a map with no chest gets no lane at all (`lane.plan` returns `None`
  on an empty `chest_groups`, so only the 38 chest-bearing maps of the 61 get
  one on the standard duck cartridge, and 37 on the No-Overworld one); the cost
  model is four constants and has no notion of which chests are worth the
  detour on a given seed, nor of visiting this one before that one; and the
  pair that shipped is named wrong. None of those is a tuning problem. A solver
  cannot know which chests are worth taking, so the route wants a person in the
  loop: an editor that takes clicked anchors and waypoints and lets
  `lane.Floor` fill in the walking between them. The router stays exactly as it
  is — it becomes the pathing primitive instead of the whole feature.

  **The spoiler question is settled: a lane ends at the nearest exit.** On both
  duck cartridges most chest-bearing maps have several — 33 of 38 standard, 34
  of 37 No-Overworld — and the lane finishes at whichever is closest, which the
  shuffle has no bearing on. It says "there is a way out here", which the art
  already drew, and not "this is the way onward". Stopping at the last chest
  instead would drop a goal the published objective names beside treasure.

  **What is left is the shortest-to-the-exit flavour, and it is more than a
  missing extra: the pair that shipped is named wrong**, so the genuinely useful
  traversal lane does not exist anywhere in the tracker. `IDEAS.md` has the
  correction, what each name should mean and what it costs to fix. Also open: a
  loot lane still walks to a linked chest whose twin it would have collected on
  an earlier floor, which needs a run-wide order the router has no notion of.

  **The by-eye pass is the other half.**
  The reference is the acceptance test, not the input: DarkmoonEX's lanes are
  drawn on vanilla layouts and the regenerated art exists for the seeds where
  the layout is not vanilla — the same trap the trap-tile letters fell into
  (`ISSUES.md`, "Our trap letters are not DarkmoonEX's"). His 58 drawn images
  want walking one at a time, recording agree or disagree-and-why; a
  disagreement is either a bug in the cost function or a judgement of his that
  is not in the published rule, and only the second kind needs transcribing.
- **The No-Overworld map surface, and the incentive sheet that waits on it.**
  The connection diagram — a hand-drawn pseudo-overworld with the fixed links as
  roads. Unchanged from the earlier plan; the topology is measured and stable.

  **The incentive sheet moved here from section 2 on 2026-09-01, because it
  cannot be built before this is.** Deriving its 28 pins needs a surface to
  resolve them against, and `regen_maps.py`'s `main` gives `nov` mode no
  overworld render *by design* — "a No-Overworld cartridge gets no overworld
  render, so there is nothing to resolve, stamp or measure". Until this lands
  those 28 pins stay hand-placed pixels on a JPEG. Section 2 listed the sheet as
  next while its blocker sat here, which is the inversion this move fixes.

  **The `nerrick` slot is splittable and need not wait.** It is a real
  Archipelago location on this mode and both dungeon trees carry it. One slot,
  not two — `airship`'s absence is correct and is not to be re-derived as a pair
  (`docs/ISSUES.md`, "The No-Overworld incentive poster is missing one slot,
  not two"). Adding it against the existing JPEG is a hand edit
  plus bumping the nov count 20 → 21 in `SHEET_RULED`,
  `tests/test_pins.lua:146`.
- **Boss names in the Map Key**, from the formation ids already in hand.

## 5. Tooling that keeps 1–4 true

**Section 5's first two bullets closed 2026-09-01** and are the two dated
closes below. What stops section 1 decaying is now a test rather than a habit,
and section 2 is what comes next.

- **The flag-coverage test. Closed 2026-09-01.**
  `tools/tests/test_flag_coverage.py` fails when FFR grows a flag nothing in
  `flag_mapping.lua` models. It reads structurally rather than by grep, which
  closes the hole a grep leaves in both directions: `GameMode` is a quoted
  literal nowhere and a grep calls it unnamed, and a name left in a
  commented-out entry satisfies a grep while modelling nothing — this pack's
  oldest failure shape, which the test demonstrates rather than asserts about.
  The counts and the `NOT_MODELLED` status tally are `docs/FLAG_COVERAGE.md`,
  "Keeping this current".

- **Five flags are filed `unjudged`, and that is the open work.** `NPCItems`,
  `NPCSwatter`, `FiendsRefights`, `ShortToFRFiendsRefights` and
  `LefeinSuperStore` say they are unmeasured and name the measurement that
  would settle them, rather than borrowing a neighbour's reason. A list padded
  to make the test pass is the test not existing. Each is a section-1 candidate
  if it turns out to move a pin.

  **`LefeinSuperStore` is the live one.** It was filed `noise` — "a shop edit" —
  on the strength of the word *store* in its name. Its only use is
  `ApplyMapMods`, reached only from `NoOverworld()`, where it picks between two
  sets of tile writes to `MapIndex.Lefein`: different wall edges, and a blob
  called `lefeinNonteleport`. That is walls and a teleport tile in a town the
  hand-authored 75-link table was derived from with the flag off, and nobody has
  walked it. The reason cited the call site and did not read it.

  The two refight flags are the argument for building the test above, and were
  the first thing it produced — `FLAG_COVERAGE.md` had never listed either,
  having been compiled by hand out of the files it was compiled from.

- **Pin the FFR revision. Closed 2026-09-01.** `tools/tests/test_ffr_pin.py`
  holds the chain that was true and enforced nowhere: the schema's `build_sha`,
  the `pinned_commit` in `pins.yaml`, and the SHA stamped into `FFRVersion.cs`.
  It found the loose link on the way — `gen_schema.py` derived `build_sha` from
  `git rev-parse HEAD`, which on the pinned worktrees is not the commit the
  cartridges claim, so it reads the stamp now. `STATUS.md`, "Nothing noticed a
  new FFR flag, and now something does", has both, and the lesson the review
  drew from its one bad row: a conjunction that comes out false demonstrates
  neither conjunct.


- **An export-vs-export diff, `tools/export_diff.py`.** Roll two cartridges one
  flag apart, diff the exports, attribute the moved rules to the flag — which is
  how every flag row in `docs/ORACLE.md` was produced, about fifteen times, by
  hand and with no committed tool. `check_logic.parse_ap_rules` already reads
  both export shapes and all 227 of `std497`'s export rules resolve to a pack
  section path, so the address book is complete and tested; the differ is small
  on top of it.

  It is also the honest half of the bullet below, available without deciding
  it: attributing a rule change to a flag **compiles nothing**, so it costs none
  of the independence that compiling would.
- **`check_logic`'s default `--ff1-world` is wrong and fails silently.**
  `ap_location_paths` (`tools/check_logic.py:656`) defaults to
  `<pack>/../Archipelago/worlds/ff1`, which resolves to
  `vendor/ff1/Archipelago/worlds/ff1` and does not exist; the world is two
  levels up at `vendor/Archipelago/worlds/ff1`. The missing path hits
  `return {}`, so every location reports unmapped and the run gives a cheerful
  zero. `docs/ORACLE.md` records the workaround — "`--ff1-world` is
  load-bearing" — and this is the cause it works around. It should refuse
  rather than return an empty dict.
- **Port from the export.** A script that reads FFR's Archipelago export and
  emits the `$`-guarded `access_rules`, replacing hand transcription. One export
  per FFR version, not per seed.

  **This one is blocked on a decision, not on effort.** Compiling makes the
  oracle and the rules the same object, so
  `check_logic` stops being an independent check and the cartridge sweep — 215
  of `nov`'s 226 — becomes the only independent reading left. That is a question
  about provenance, and `docs/IDEAS.md` ("Solve the requirements instead of
  sampling them") has both sides of it with the figures attached. **It is a
  judgement about provenance rather than a technical question, so it gets taken
  deliberately, in its own session, against one stated criterion: is the
  cartridge sweep alone enough cover?** Nothing here gets built before that; the
  export diff above is what to build meanwhile.
- ~~**More oracle seeds.**~~ **Obsolete 2026-09-01.** It said "two flagsets is
  thin" and predates the 4-9-7 corpus; `docs/ORACLE.md` has the inventory. What
  is still ungraded is not a seed-count problem and is named elsewhere: the
  three ToFR flags the export cannot see, `Shop Item`, and the two permutation
  rolls closed strictly rather than graded.
- **Two location trees, one rule set.** `isNoOverworld()` landed. **The
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
  `IDEAS.md` until there is a user to ask.

## What each branch landed

**This section no longer says where any branch stands, because it could not be
kept true.** It carried a standing status line that was wrong about a branch
four times in four days, in both directions — claiming unpushed work that was
pushed and pushed work that was not — and twice carried a commit count that went
wrong, once inside the commit that wrote it. A line nothing re-reads outlives
its subject, and this page has documented that failure about `ISSUES.md` while
reproducing it here.

Ask git instead. `git log trunk..<branch>` says whether a branch has anything
left in it; `git rev-list --count origin/trunk..trunk` says how far ahead trunk
is; `git fetch` first, because a merge done on GitHub outside a session makes a
local count a lie.

What stays is the record of what each merged branch was for, dated on the day it
merged. That is a fact about the past and cannot go stale.
- **`flag-coverage` merged 2026-09-01**, and was the whole of section 5's
  first two bullets: `test_flag_coverage.py`, which fails when FFR grows a flag
  nothing here models, and `test_ffr_pin.py`, which holds the schemas to the
  revision the workspace pins. Nine commits, `83f97d4..8331b33`.

  **The review gate ran on it**, and every finding is committed —
  `1dbcf4f..9148fdd`. It found a coverage row that did not demonstrate the term
  it named: "a pin from the wrong FFR version is not an ancestor" was a
  conjunction of ancestry and the stamp, and only the stamp ever fired. Same
  lesson as the gate rows, and the two terms are separate rows now.

  **What it leaves behind is five flags filed `unjudged`**, in section 5.

- **`flags-real-seeds` merged 2026-09-01**, and was the whole of section 1: the
  `ChaosRush` and `ToFRMode` codes and the `ExitToFR` decision, then
  `MapAirshipHike` and `MapCardiaLandBridge` graded on a cartridge each, the two
  verify flags answered, `ShuffleObjectiveNPCs` closed strictly, Gaia settled
  against FFR, the mode-mismatch light, and the flags grid on the variants that
  had none. Section 1 has no open bullets left.

  **The review gate has run** on 2026-09-01, and every finding is addressed
  and committed — seven commits,
  `52ba9d5..7371acf`. It found a real hole the oracle structurally could not see
  (Bahamut's Cave never got the `airshipHike` or `cardiaLandBridge`
  alternatives, because FFR's export has no Bahamut location to grade against),
  and it was also wrong once in the direction that would have deleted a correct
  route, which the cartridge settled. Seven more 4.9.7 cartridges came out of
  answering it.

  This entry said "the review gate has not run on it yet" for a day after it
  had, which is the same way a closed `ISSUES.md` entry goes stale: nothing
  re-reads a line once it is written. Say the gate ran on the day it runs, and
  say a branch merged on the day it merges — this line went stale twice in two
  days, in both directions.
