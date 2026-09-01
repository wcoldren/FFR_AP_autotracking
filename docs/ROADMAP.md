# What is next, in order

Forward-only. Finished work lives in `STATUS.md`; defects in `docs/ISSUES.md`;
unscoped ideas in `docs/IDEAS.md`. This file says what gets built next and why,
ordered by what a player sees.

The triage rule, from 2026-08-30: **does it change a colour, add a box, or save
a click?** If yes it is product and goes in sections 1–4. If no it is tooling
and goes in 5, where it earns its place by keeping 1–4 true.

**Amended 2026-09-01, when section 1 closed.** The rule sorts tooling last by
construction, and that was right while section 1 was open. It is not now. Every
section-1 close cost one hand-rolled cartridge, one hand-written rule and one
grading run, and that is the standing per-flag price at the next FFR version
bump — so the machinery that lowers it, all of which sits in section 5, stops
being what comes after the product work. Concretely: **nothing today notices a
new FFR flag.** Section 5's first two bullets are what keep section 1 closed,
and they come before section 2.

**Both closed 2026-09-01**, and section 2 is what comes next. What they left
behind is four flags filed `unjudged` — named in section 5 rather than here,
because none is known to move a pin yet.

The parity target for every rule is FFR's `SanityCheckerV2` + `SCLogic`, with
the Archipelago export as the graded truth table. `docs/FLAG_COVERAGE.md` is the
table of every flag that logic consults and how the pack models it.

## 1. Colours that are wrong on real seeds

**Closed 2026-09-01, and left standing rather than deleted.** Every bullet below
is answered; the section is kept because each one records what the answer cost
and how it was reached, and because "closed" is a claim that should be readable
next to its evidence. The next thing that makes a pin lie goes here, under the
same rule.

Each item here was a pin that lied on a seed someone could roll. Each
wants: a code, the affected `access_rules` alternatives, and **one oracle seed
rolled with the flag on** so `check_logic --ap-rules` grades the branch. A rule
without its oracle seed is a hand transcription, which is what section 5 is
meant to end.

Two of the answers below are **strict** rather than graded, and the difference
matters: `ShuffleObjectiveNPCs` and the Cardia roll are permutations chosen at
generation that no file the pack can read records, so the pack deliberately
disagrees with FFR there instead of agreeing with it. Both are waived by name in
`check_logic` so the disagreement stays printed.

- **No flags without a code are left. Closed 2026-09-01.** `MapAirshipHike` and
  `MapCardiaLandBridge` were the last two; both are 4.9.7-only, both were rolled
  on their own cartridge, and both graded the branch outright — 90 of 224
  agreeing before and 224 of 224 after on `airship497`, 177 of 223 before and
  223 of 223 after on `landbridge497`. `ToFRMode` and `ChaosRush` landed
  2026-08-31; `ExitToFR` is decided against rather than pending, because it
  writes an exit portal and nothing else and this pack does not model points of
  no return — it sits in `NOT_MODELLED`, where a flag with no code can be told
  apart from one nobody has got to.

  Running the verify pair on 2026-09-01 put one of them back on the list.
  `IsFloaterRemoved` moves no pin — it is computed rather than stored, and its
  one read inside `FF1Lib/Sanity/` relaxes the completion test rather than any
  location's rule. **`ShuffleObjectiveNPCs` does move pins**, and is the bullet
  below.

  `NoTail` and `ShipDrydock` mark out both ends of the rule above. `NoTail`'s
  oracle seed proved the flag rewrites no exported rule at all, so the seed
  graded the branch by showing there was nothing there to grade — the code was
  still needed, because a `check_logic` pass is not evidence a pack-only cell is
  honest. `ShipDrydock` is the other end: it rewrites 51 exported rules and the
  pack was showing 53 locations green that FFR calls unreachable, so its
  cartridge graded the branch outright, 170 of 223 before and 223 of 223 after.
  The three Temple of Fiends flags are `NoTail`'s case again, but by
  construction rather than by accident: `Archipelago.cs:93` drops every ToFR
  location from the pool, so no cartridge rolled for one of them can grade
  anything. Their evidence is the derived walk instead — `oracle-4.9.2/nov`
  rolls `ToFRMode 2` and derives all seven ToFR chests as `[["orbs"]]`, which
  the pack contradicted until now. All of them are in
  `docs/FLAG_COVERAGE.md`; the cartridges are in `docs/ORACLE.md`.
- **`ShuffleObjectiveNPCs`. Closed strictly 2026-09-01.** It permutes Bahamut,
  Dr Unne and the Elf Doctor across their three homes (`NPCs.cs:277`), and on
  `objnpc497` Bahamut and Unne swapped outright — so `bahamut` was held behind
  the airship while Bahamut stood in Melmond, and `slabTranslated` read
  reachable while Unne sat behind the airship. FFR's export does not notice, so
  the pack scored 224 of 224 on a seed it was wrong about: the `NoTail` case.

  With the flag on, the two cells that move now ask for all three homes at
  once, which collapses to Bahamut's Cave. `$noObjectiveShuffle` is the guard.
  This is the weaker kind of close — the pack deliberately disagrees with FFR
  on a shuffled seed rather than agreeing with it — and the divergence is in
  `check_logic`'s `WAIVED` table so it stays printed.
- **Gaia. Closed 2026-09-01.** The two tabs disagreed about how to reach it and
  the oracle said which: the dungeon tree's northern-docks route was missing
  `hwyOrdeals` and opened Gaia on a seed FFR does not. Two cartridges one flag
  apart settled it — `gaia497` and `gaiahwy497` in `docs/ORACLE.md`. The
  `fairy` waiver in `tests/test_maps.lua` went with it.
- **The two rolls the bridge should read, not guess at.** Both are permutations
  chosen at generation that reach neither the flag string nor the spoiler, and
  both are answered today by being deliberately strict. They want one feature
  between them, not two.

  The **Cardia roll** is the gateway permutation (`MetroidVaniaMap.cs:726`); the
  bridge publishes `ff1/gateways` next to `ff1/flags` and the rule reads it. The
  **objective-NPC roll** is the same shape one flag along, and
  `tools/extract_npcs.py` already knows how to find it — it is what measured the
  Bahamut/Unne swap in the first place. `regen_maps.py` reads the cartridge per
  seed already; the live bridge does not publish NPC positions.

  Until then both stay strict, which costs six Cardia Forest locations on a
  No-Overworld seed and the Elf Prince plus Dr Unne on a shuffled one.
- **Variant from `GameMode`. Closed 2026-09-01, and the ambitious half is
  refused rather than deferred.** Auto-selecting the variant is not expressible:
  `Tracker.ActiveVariantUID` is read-only from Lua and raises if written
  (PopTracker `core/tracker.cpp:747-749`), and `Pack::setVariant` is called once
  from the load path (`poptracker.cpp:1202`). There is no runtime path to it, so
  this is not something to come back to.

  What landed is the fallback this bullet named: a third warning light,
  `modeMismatch`, beside the unread-flags and stale-art triangles. It reports
  the mode and the goal together rather than in a chain, because a seed can be
  wrong on both at once. It also fixed a warning that fired on seeds that were
  fine — the old line warned on any non-zero `GameMode`, which meant every
  No-Overworld seed loaded into the No-Overworld variant it belongs in.

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
  (`ISSUES.md:170`, `:542`). That is a decision, and it is taken here rather
  than left as a gap somebody re-opens.

  What Titan still wants is **a fresh hosted code**, because `titan` is spent:
  `items/items.json:174` gives it to `Ruby` stage 2. `unne` has the identical
  clash at `:202` (`slab,slabTranslated,unne`), which is worth knowing so it is
  not rediscovered as a second problem if the Unne decision is ever revisited.
  Bridge-only either way — neither is an Archipelago location.
- **`shopItem` has no incentive toggle because FFR has no such flag.** This
  bullet used to read as missing wiring. It is not: there is no
  `IncentivizeShopItem` anywhere in the 4-9-7 schema, and
  `docs/FLAG_COVERAGE.md:222` records `Shop Item` as tracking where the shop
  landed — roll noise, not a flag. Nothing to map, so the honest close is to say
  so on the board's Map Key rather than to build a toggle.

  **The real defect on that pin is a different one and is already filed**:
  `I: Shop Item` carries no access rule at all, so it is green on a seed that
  put it behind a vehicle, and `check_logic` cannot even grade it —
  `docs/ISSUES.md:437`. That is the entry to work from.
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
  missing extra: the pair that shipped is named wrong.** "Optimal Route" means
  the walk through a floor collecting *nothing*, and "for loot" already implies
  the key rather than needing a lane of its own. What is drawn today is one loot
  lane in two halves. `IDEAS.md` has the correction and what it costs to fix.
  Also open: a loot lane still walks to a linked chest whose twin it would have
  collected on an earlier floor, which needs a run-wide order the router has
  no notion of.

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
  resolve them against, and `tools/regen_maps.py:1315` gives `nov` mode no
  overworld render *by design* — "a No-Overworld cartridge gets no overworld
  render, so there is nothing to resolve, stamp or measure". Until this lands
  those 28 pins stay hand-placed pixels on a JPEG. Section 2 listed the sheet as
  next while its blocker sat here, which is the inversion this move fixes.

  **The `nerrick` slot is splittable and need not wait.** It is a real
  Archipelago location on this mode and both dungeon trees carry it. One slot,
  not two — `airship`'s absence is correct and is not to be re-derived as a pair
  (`docs/ISSUES.md:573`). Adding it against the existing JPEG is a hand edit
  plus bumping the nov count 20 → 21 in `SHEET_RULED`,
  `tests/test_pins.lua:146`.
- **Boss names in the Map Key**, from the formation ids already in hand.

## 5. Tooling that keeps 1–4 true

**The first two bullets come before section 2**, per the amended triage rule at
the top of this file. They are what keeps section 1 from decaying, and nothing
else on this page does that.

- **The flag-coverage test. Closed 2026-09-01.**
  `tools/tests/test_flag_coverage.py` runs the two greps `docs/FLAG_COVERAGE.md`
  publishes against the vendored 4.9.7 checkout and fails when a flag they find
  is named nowhere in `flag_mapping.lua`. **54 consulted, 24 named before it, 54
  after.** A flag FFR adds is a failing test now rather than a habit.

  The figures this bullet predicted held exactly — 54 distinct names, 11 absent
  from `FLAG_COVERAGE.md` — with one correction. **It is 30 unnamed, not 31.**
  The difference is `GameMode`, which is read as `flags.GameMode` and is a
  quoted literal nowhere, so a grep calls it unnamed and the structural pass
  correctly calls it named. Reading structurally also closes the hole the other
  way: a name left in a commented-out entry satisfies a grep and models nothing,
  which is this pack's oldest failure shape, and the test demonstrates that case
  rather than asserting about it.

  **Writing the thirty reasons was the work, as predicted, and five of them
  could not honestly be written.** `NOT_MODELLED` entries carry a `status` from
  the key `FLAG_COVERAGE.md` already publishes — ram 7, variant 1, noise 8,
  unmodellable 6, decided 4, unjudged 5, thirty-one in all because `ExitToFR`
  was already there — and `unjudged` is the one that matters. A list padded to
  make the test pass is the test not existing, so `NPCItems`, `NPCSwatter`,
  `FiendsRefights`, `ShortToFRFiendsRefights` and `LefeinSuperStore` say they
  are unmeasured and name the measurement that would settle them. **Those five
  are the open work this bullet leaves behind**, and they are section-1
  candidates if any of them turns out to move a pin.

  `LefeinSuperStore` joined them on review rather than on the first pass, and it
  is the one worth naming. It was filed `noise` — "a shop edit" — on the
  strength of the word *store* in its name. Its only use is `ApplyMapMods`,
  reached only from `NoOverworld()`, where it picks between two sets of tile
  writes to `MapIndex.Lefein`: different wall edges, and a blob called
  `lefeinNonteleport`. That is walls and a teleport tile in a town the
  hand-authored 75-link table was derived from with the flag off. The reason
  cited the call site and did not read it.

  The two refight flags were the argument for building this and are now the
  first thing it produced. `FLAG_COVERAGE.md` had never listed either, having
  been compiled by hand out of the files it was compiled from.

- **Pin the FFR revision. Closed 2026-09-01.** `tools/tests/test_ffr_pin.py`
  holds the chain that was true and enforced nowhere: the schema's `build_sha`,
  the `pinned_commit` in `pins.yaml`, and the SHA stamped into `FFRVersion.cs`
  on the worktree. Three links, but only two independent sources — `git_sha()`
  derives `build_sha` from the stamp, so those two are one value read twice,
  and the term that can actually drift is the hand-typed pin. The base is
  resolved rather than compared, as this bullet asked — both worktrees sit
  exactly two local commits above their pin, so a HEAD comparison fails on a
  tree that is right.

  **It found the loose link on the way.** `gen_schema.py` derived `build_sha`
  from `git rev-parse HEAD`, which on those worktrees is not the commit the
  cartridges claim: regenerating 4-9-7 wrote `b4ec325` where every oracle ROM
  says `1f31434`, and the proof loop then failed against all of them. Loud
  rather than silent, so nothing shipped wrong — but it put the fault in the
  checker rather than the tree, and made "a new version is one command" untrue
  for the two trees where it matters most. It reads the stamp now, with HEAD as
  the fallback for an unstamped checkout.

  **One of its rows did not demonstrate what it claimed**, found on review.
  "A pin from the wrong FFR version is not an ancestor" was a conjunction of
  ancestry and the stamp, and only the stamp ever fired: 4.9.2's release commit
  genuinely *is* an ancestor of the 4.9.7 worktree, so a 4.9.7 tree rewound to
  4.9.2 would have passed the ancestry half. The two terms bite in opposite
  directions and are separate rows now. Same lesson as the gate rows: a
  conjunction that comes out false is not a demonstration of either conjunct.

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
- ~~**More oracle seeds.**~~ **Obsolete 2026-09-01.** This said "two flagsets is
  thin" and predates the 4-9-7 corpus. There are twenty cartridges now, five at
  4.9.2 and fifteen at 4.9.7, all inventoried in `docs/ORACLE.md`. What is still
  ungraded is not a seed-count problem and is named elsewhere: the three ToFR
  flags the export cannot see, `Shop Item`, and the two permutation rolls closed
  strictly rather than graded.
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

## Branch queue

Where things stand on the day this was written. `git log trunk..` is what
actually says where a branch is.

- `trunk` is **level with `origin/trunk`**, as of 2026-09-01.
  `noverworld-logic`, `visibility-toggles`, `route-lanes` and `flags-real-seeds`
  are all merged. Nothing is in flight. No number here on purpose: `00dffd4`
  took a count out of this section for going wrong twice, and the one that
  briefly replaced it went wrong inside the commit that wrote it —
  `git rev-list --count origin/trunk..trunk` is the answer.

  This bullet said "ahead of `origin/trunk` and unpushed" for the rest of the
  day after the push. That is the third time in three days a line in this
  section has been wrong about where a branch stands, in both directions, and
  the entry below already draws the lesson: **say it on the day it happens.**
  The standing count is now zero rather than a number, which is the one form of
  this sentence that does not rot.
- **`flags-real-seeds` merged 2026-09-01**, and was the whole of section 1: the
  `ChaosRush` and `ToFRMode` codes and the `ExitToFR` decision, then
  `MapAirshipHike` and `MapCardiaLandBridge` graded on a cartridge each, the two
  verify flags answered, `ShuffleObjectiveNPCs` closed strictly, Gaia settled
  against FFR, the mode-mismatch light, and the flags grid on the variants that
  had none. Section 1 has no open bullets left.

  **The review gate has run**, in a fresh context at high effort on 2026-09-01,
  and every finding is addressed and committed — seven commits,
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
