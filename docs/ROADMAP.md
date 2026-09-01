# What is next, in order

Forward-only. Finished work lives in `STATUS.md`; defects in `docs/ISSUES.md`;
unscoped ideas in `docs/IDEAS.md`. This file says what gets built next and why,
ordered by what a player sees.

The triage rule, from 2026-08-30: **does it change a colour, add a box, or save
a click?** If yes it is product and goes in sections 1–4. If no it is tooling
and goes in 5, where it earns its place by keeping 1–4 true.

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

Things a bridge-only player checks that the board has no cell for. Several
share work with section 1, which is why they come second and not later.

- **Titan.** Code clash with `ruby` stage 2; needs its own hosted toggle.
- **The four fiends and the ToFR refights.** Tiles already read off the
  cartridge (`extract_npcs.WANTED`, `render_maps.fixed_formations()`); missing a
  location node each. Their placement moves with `ToFRMode`, so build this on
  the `ToFRMode` rules from section 1.
- **Unne.** Holds no shuffled item, so a manual cell — decide and do it, or
  write down that it stays off. Same decision for the other unpinned NPCs.
- **`shopItem`.** The one Locations-grid cell with no incentive toggle behind it.
- **The No-Overworld incentive sheet.** Derive the 28 pin positions from the
  cartridge; the missing Nerrick slot (`ISSUES.md:436`, one slot not two) comes
  with it.
- **ToFR rules at all.** The AP export drops ToFR, so nothing grades them.
  `tofr_diff.py` is the only check; the rules themselves are unwritten.

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
- **The No-Overworld map surface.** The connection diagram — a hand-drawn
  pseudo-overworld with the fixed links as roads. Unchanged from the earlier
  plan; the topology is measured and stable.
- **Boss names in the Map Key**, from the formation ids already in hand.

## 5. Tooling that keeps 1–4 true

- **Port from the export.** A script that reads FFR's Archipelago export and
  emits the `$`-guarded `access_rules`, replacing hand transcription. One export
  per FFR version, not per seed. This is the thing that keeps the pack in step
  when FFR changes.
- **The flag-coverage test.** The flags the logic consults are a grep over
  `IVictoryConditionFlags`, `OverworldMap.cs`, `NPCs.cs`, `MetroidVaniaMap.cs`,
  `TempleOfFiends.cs`. Fail when one appears that is in neither
  `flag_mapping.lua` nor an explicit not-modelled list.
- **Pin the FFR revision.** The schemas carry a build SHA; the rules should
  say which revision they were graded against, and the greps above should run
  against that revision, vendored or fetched. `FLAG_COVERAGE.md` was compiled
  against trunk `0f91e97` because the 4-9-7 schema's build SHA `1f31434` was
  not reachable; re-run its greps once pinned.
- **More oracle seeds.** Two flagsets is thin for a pack with a dozen
  flag-driven codes. One per branch claimed in section 1.
- **Two location trees, one rule set.** `isNoOverworld()` landed; the trees are
  still byte-identical copies. Either collapse them or make `test_maps.lua`
  check 6 able to fail (a deliberately diverged fixture). Decide alongside the
  section 4 map surface, since a differently-cropped No-Overworld dungeon tree
  is the one reason to keep two.

## Frozen

Stated once so nobody re-derives them.

- **`tools/noverworld_rules.py`** is frozen. It did its job — it disproved the
  substitution plan and gave the No-Overworld rules an independent reading. Its
  remaining gaps (`docs/ORACLE.md`, the eleven) are properties of the tool, not
  the pack; the shipped rules are graded against the export, which is the
  correctness criterion. Keep it runnable; stop closing its gaps.
- **Compile-from-export** is absorbed into section 5.
- **Names that have drifted** and **the four `NoMap` variants** stay in
  `IDEAS.md` until there is a user to ask.

## Branch queue

Where things stand on the day this was written. `git log trunk..` is what
actually says where a branch is.

- `trunk` carries the route-lane work and is **ten commits ahead of
  `origin/trunk`**, unpushed, as of 2026-09-01. `noverworld-logic`,
  `visibility-toggles` and `route-lanes` are merged.
- **`flags-real-seeds` is in flight**, and it is now the whole of section 1:
  the `ChaosRush` and `ToFRMode` codes and the `ExitToFR` decision, then
  `MapAirshipHike` and `MapCardiaLandBridge` graded on a cartridge each, the two
  verify flags answered, `ShuffleObjectiveNPCs` closed strictly, Gaia settled
  against FFR, the mode-mismatch light, and the flags grid on the variants that
  had none. Section 1 has no open bullets left. **The review gate has not run on
  it yet**, and it wants a fresh-context session before it merges.
