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

Each item here is a pin that lies today on a seed someone could roll. Each
wants: a code, the affected `access_rules` alternatives, and **one oracle seed
rolled with the flag on** so `check_logic --ap-rules` grades the branch. A rule
without its oracle seed is a hand transcription, which is what section 5 is
meant to end.

- **The five flags with no code.** `MapAirshipHike`, `MapCardiaLandBridge`,
  `ToFRMode`, `ChaosRush`, `ExitToFR`. Two to verify before deciding:
  `IsFloaterRemoved`, `ShuffleObjectiveNPCs`. `NoTail` and `ShipDrydock` are
  done, and between them they mark out both ends of the rule above. `NoTail`'s
  oracle seed proved the flag rewrites no exported rule at all, so the seed
  graded the branch by showing there was nothing there to grade — the code was
  still needed, because a `check_logic` pass is not evidence a pack-only cell is
  honest. `ShipDrydock` is the other end: it rewrites 51 exported rules and the
  pack was showing 53 locations green that FFR calls unreachable, so its
  cartridge graded the branch outright, 170 of 223 before and 223 of 223 after.
  Both are in `docs/FLAG_COVERAGE.md`; the two cartridges that isolate the
  second are in `docs/ORACLE.md`.
- **Gaia.** The two tabs disagree about how to reach it (`ISSUES.md`). One is
  wrong; the oracle says which.
- **The Cardia roll.** The gateway permutation is rolled per seed and reaches
  neither the flag string nor the spoiler log (`MetroidVaniaMap.cs:726`). The
  bridge publishes `ff1/gateways` next to `ff1/flags`, the rule reads it. Until
  then the pack stays deliberately strict there.
- **Variant from `GameMode`.** A No-Overworld seed loaded into a standard
  variant colours every pin wrong and only prints a warning. Mode detection
  exists; act on it, or at least light the grid the way unread flags do.

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
  bridge can detect it (`IDEAS.md`, "Notice when the drawn maps…"); build
  detection first, execution second.
- **Follow the party into towns and rooms.** Auto-tab exists; extend it to the
  No-Overworld towns and to the room-level zoom.
- **`hide unreachable locations` swallows skipped slots.** Decide whether
  Inspect should survive it.
- **What a diamond means.** Settle it and put it in the Map Key.
- **Stale user-override shadowing pack edits.** Warn once.

## 4. Maps

- **Entrance markers.** On a shuffled seed the hand art's exits are wrong, so
  these are the top map item for a No-Overworld or entrance-rando player; the
  design is in `STATUS.md`, "Designed, not started". First increment is the
  bridge's edge log plus a console print, display half after. Routes need the
  same log to know which door leads where, which is why this comes first.
- **Routes on regenerated maps.** The shipped hand art already carries
  DarkmoonEX's lanes; the regenerated art — the only art a No-Overworld player
  can trust — has none. Two flavours (shortest, with-loot), one colour per lane
  across all 61, key in the Map Key band. Baked at render time in `regen_maps`;
  the PopTracker tab is a static image. Objective function is in `IDEAS.md`.
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

- `trunk` is level with `origin/trunk` and clean as of 2026-08-30. `noverworld-logic`
  and `visibility-toggles` are merged.
- Nothing is in flight.
