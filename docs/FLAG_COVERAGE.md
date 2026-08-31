# Flag coverage: what FFR's logic consults vs what the pack models

Recompiled 2026-08-31 against this pack's `trunk` (4441d8c) and three FFR
revisions: the 4.9.2 release `01272d4`, which the oracle corpus is built from;
the 4.9.7 release `1f31434`, which `tools/ffr_flags/schemas/4-9-7.json` records
as its build; and 4.9.8 development head. `1f31434` is reachable in the clone
now, so section A is grepped at the schema build rather than near it.

**Which revision you grep changes the answer**, and it changes it for three of
the flags this page calls missing. See "Missing rows" at the bottom.

The parity target is `SanityCheckerV2` + `SCLogic`. Two things about how it reads
flags shape this whole table:

1. **It consults exactly ten flags directly**, all through
   `IVictoryConditionFlags` (`Interfaces.cs:171-190`). The interface *declares*
   seventeen; `FF1Lib/Sanity/` names ten, and the same ten at 4.9.2, 4.9.7 and
   4.9.8. A declaration is not a read, which is what section A' is for.
2. **Everything else reaches it through the ROM data.** `MapOpenProgression` edits
   overworld tiles; `EarlyKing` rewrites the King's talk routine; the checker walks
   the edited result and never sees the flag. The pack has no walk, so each of
   those has to become a code the rules can name. That is why the pack needs
   more flag codes than the checker does, not fewer.

`grep -ohE 'victoryConditions\.[A-Za-z]+' FF1Lib/Sanity/*.cs` gives group A;
`grep -ohE '\bflags\.[A-Z][A-Za-z]+' FF1Lib/{OverworldMap,NPCs,MetroidVaniaMap,TempleOfFiends}.cs`
gives B–D. `FF1Lib/Tracker.cs` (FFR's in-game tracker) is a useful cross-check:
it reads `AirBoat ChaosRush DesertOfDeath EarlyKing EarlySage EarlySarda FreeAirship
FreeBridge FreeCanal FreeCanoe FreeShip GameMode NoFloater NoOverworld NoTail
OrbsRequiredCount OrbsRequiredMode ShardHunt ShipDrydock` — FFR's own opinion of
what a tracker needs.

Status key: **RAM** = effect is visible in `$6000-$62FF`, no code needed ·
**code** = a pack code exists and the rules use it · **variant** = handled by
choosing the tracker variant · **missing** = affects reachability, no code ·
**n/a** = affects placement or presentation only · **unmodellable** = changes
topology in a way no toggle can express.

## A. Consulted directly by SanityCheckerV2 (`IVictoryConditionFlags`)

Ten names, and this is all of them:

    grep -ohE 'victoryConditions\.[A-Za-z]+' FF1Lib/Sanity/*.cs | sort -u

| FFR flag | Effect on logic | Pack | Status |
|---|---|---|---|
| `IsBridgeFree` | Bridge in starting inventory | `bridge` from `$6008` | RAM |
| `IsShipFree` | Ship in starting inventory | `ship` from `$6000` | RAM |
| `IsCanalFree` | Canal open at start | `canal` from `$600C` | RAM |
| `IsCanoeFree` | Canoe at start | `canoe` from inventory | RAM |
| `IsAirshipFree` | Airship at start | `floater` stage 2 from inventory | RAM |
| `FreeLute` | Lute at start | `lute` from inventory | RAM |
| `FreeRod` | Rod at start | `rod` from inventory | RAM |
| `IsFloaterRemoved` | Airship placed as an item; no Floater/desert step | `floater` progressive assumes Floater->Airship | probably RAM (airship byte lights stage 2); **verify** |
| `AirBoat` | Ship doubles as airship after Floater | `airBoat` progressive, rules use it | code |
| `GameMode` | Compared against `DeepDungeon` and nothing else (`SanityCheckerV2.cs:183,779`) | `isNoOverworld()` from variant UID | variant (warning printed on mismatch) |

The `GameMode` row reads differently once you look at its two call sites. The
checker branches on Deep Dungeon; it never asks whether the seed is
No-Overworld. A No-Overworld seed reaches it as a rewritten map, exactly like
the section B flags do. The pack does not track Deep Dungeon, so nothing in the
checker's use of `GameMode` bears on the pack at all.

## A'. Declared in `IVictoryConditionFlags`, never read in `FF1Lib/Sanity/`

The other seven. Each reaches the checker some other way, or not at all, and
which of those it is decides whether the pack needs a code.

| FFR flag | How it reaches the logic | Pack | Status |
|---|---|---|---|
| `FreeTail` | Starting inventory (`StartingItems.cs:62`) | `tail` from inventory | RAM |
| `NoTail` | Item-pool edit (`PlacementContext.cs:99,205`) and Bahamut's routine (`Bahamut.cs:20`) | `noTail` | code — the row is in section B |
| `ShardHunt` | Rewrites the Black Orb turn-in (`BlackOrb.cs:31-33`) and the pool (`ItemPlacement.cs:212`, `PlacementContext.cs:481`) | variant + `hasEnoughShards()` | variant |
| `NoOverworld` | Computed rather than stored (`FlagsCompute.cs:77`); rewrites the maps at `MetroidVaniaMap.cs:49` | `isNoOverworld()` from variant UID | variant |
| `DesertOfDeath` | Computed rather than stored (`FlagsCompute.cs:78`); applied at `Randomize.cs:160` | none | unmodellable; the warning that covers it is the `OwMapExchange` one |
| `OnlyRequireGameIsBeatable` | Placement leniency | — | n/a |
| `LooseExcludePlacedDungeons` | Placement | — | n/a |

**`DesertOfDeath` is not a game mode.** `GameModes` holds three values --
Standard, DeepDungeon, NoOverworld -- at 4.9.2 and 4.9.7 alike, and there is no
mode 3. Desert is `OwMapExchanges.Desert`, index 3 of a different enum, and
`FlagsCompute.cs:78` composes the two: `GameMode == Standard && OwMapExchange ==
Desert`. A Desert seed is warned about, but by `flag_mapping.lua:264`
(`OwMapExchange ~= 0`), not by the `GameMode ~= 0` line above it.

## B. Reach the checker through ROM edits — must be pack codes

### Overworld shape (`OverworldMap.cs`)

| FFR flag | Pack code | Status |
|---|---|---|
| `MapOpenProgression` | `progressionFlag` stage 1 (`openProgression`) | code |
| `MapOpenProgressionExtended` | `progressionFlag` stage 2 (`extendedOpen`) | code |
| `MapOpenProgressionDocks` | `northernDocks` | code |
| `MapAirshipDock` | `luffyDock` | code |
| `MapBahamutCardiaDock` | `cardiaDock` | code |
| `MapLefeinRiver` | `lefeinRiver` | code |
| `MapBridgeLefein` | `lefeinBridge` | code |
| `MapGaiaMountainPass` | `gaiaMountain` | code |
| `MapHighwayToOrdeals` | `hwyOrdeals` | code |
| `MapRiverToMelmond` | `melmondRiver` | code |
| `MapSardasForest` | `sardasForest` | code |
| `MapAirshipHike` | — | **missing**; 4.9.7+ only (also read by `EntrancesFloorsShuffle.cs`) |
| `MapCardiaLandBridge` | — | **missing**; 4.9.7+ only |
| `ShipDrydock` | — | **missing**; 4.9.7+ only. Measured: 52 exported rules change and the pack over-reports 53 locations (`docs/ORACLE.md`). `Tracker.cs` reads it, so FFR thinks a tracker needs it |
| `DisableOWMapModifications` | — | n/a (meta: disables all of the above) |

The last three arrive after 4.9.2 — `git grep` finds no mention of any of them
under `FF1Lib/` at `01272d4`, and `schema_4-9-2.lua` has no field for them
either. The eleven above them are in both schemas.

### NPC behaviour (`NPCs.cs`)

| FFR flag | Pack code | Status |
|---|---|---|
| `EarlyKing` | `earlyKing` | code |
| `EarlySarda` | `earlySarda` | code |
| `EarlySage` | `earlySage` | code |
| `NoTail` | `noTail` | code — declared in `IVictoryConditionFlags` and never read there; see section A' |
| `ShuffleObjectiveNPCs` | — | **check**: if it moves which NPC holds which objective, it moves logic |
| `NPCItems`, `ChestsKeyItems` | pool shape → `Overworld Tab` auto | n/a for reachability; affects which pins are checks |
| `NPCSwatter` | — | n/a |

### No-Overworld / entrance shuffle (`MetroidVaniaMap.cs`, `EntrancesFloorsShuffle.cs`)

| FFR flag | Pack code | Status |
|---|---|---|
| `EarlyOrdeals` | `earlyOrdeals` | code |
| `Entrances`, `Floors`, `Towns`, `EntrancesMixedWithTowns`, `IncludeConeria`, `AllowDeepCastles` | — | unmodellable by toggle; `regen_maps` reads the result off the cartridge |
| `OwMapExchange`, `OwShuffledAccess` | — | unmodellable; `flag_mapping` already warns |

## C. Goal and Temple of Fiends (`TempleOfFiends.cs`)

| FFR flag | Pack | Status |
|---|---|---|
| `OrbsRequiredCount`, `OrbsRequiredMode` | `logic.lua:153-154` reads `ffrFlag()` directly | code |
| `ShardCount` | `hasEnoughShards()` | code |
| `ToFRMode` | none; oracle notes the AP export drops ToFR anyway | **missing** — ToFR rules differ by mode |
| `ChaosRush` | none | **missing** — collapses ToFR to the Chaos fight |
| `ExitToFR` | none | **missing** — changes whether ToFR is a one-way trip |

## D. Placement-only (large group, all n/a for colours)

`Incentivize*` (~50 properties), `*IncentivePlacementType`, `Treasures`, `Shops`,
`RandomizeTreasure`, `WorldWealth`, `Guaranteed*`, `NoMasamune`, `NoXcalber`,
`SendMasamuneHome`, `ItemMagicMode`, `Etherizer`, `MermaidPrison`, `TitansTrove`.
These decide *what is where*, which the tracker must not know. The `Incentivize*`
and `TitansTrove` codes the pack does carry drive pin colour (blue/gold) and
whether Titan's Trove exists as a check — presentation, not reachability.

## Missing rows, in one place

Reachability flags with no pack code today:

1. `MapAirshipHike`
2. `MapCardiaLandBridge`
3. `ShipDrydock`
4. `ToFRMode`
5. `ChaosRush`
6. `ExitToFR`

`NoTail` was the seventh and is **done** — see the row in section B. Closing it
turned up the rule this page now applies throughout: **a flag being declared in
`IVictoryConditionFlags` does not mean `SanityCheckerV2` reads it.** Section A'
is what running that grep over the rest produced, and it moved seven rows out of
section A.

Each of the six wants a `TOGGLES`/`PROGRESSIVES` row in `flag_mapping.lua`, a
code in `items/flags.json`, the affected `access_rules` alternatives, and one
oracle seed rolled with the flag on so `check_logic` grades the branch. That is
six codes, not twenty-five, and none is a redesign.

**Rolling the seed can also show the branch is ungradeable, and that is a
result.** `NoTail`'s cartridge proved the flag rewrites no rule FFR hands
Archipelago — its export mentions the Tail nowhere and Bahamut is not an AP
location — so `check_logic` graded it 226/226 against rules that had not
changed. The pack still needed the code, because the lying cell is the pack's
own; the gate for it is `tests/test_flags.lua`, not the oracle.

### None of the six could be graded by the 4.9.2 corpus

That corpus is five 4.9.2 cartridges (`docs/ORACLE.md`). Against it the six
split in two, for reasons that have nothing to do with each other.

**Three do not exist at 4.9.2.** `ShipDrydock`, `MapAirshipHike` and
`MapCardiaLandBridge` are the section B rows marked 4.9.7+ above. A 4.9.2
cartridge cannot be rolled with a flag its build has never heard of, so no
amount of rolling against the present corpus reaches them.

**Three are Temple of Fiends flags, and the export never covers ToFR.**
`ToFRMode`, `ChaosRush` and `ExitToFR` are all present at 4.9.2, so a cartridge
*can* be rolled — but `archipelago/Archipelago.cs:93` drops every ToFR location
from the pool unconditionally, and ToFR appears zero times in all five existing
exports. Rolling one of these produces the `NoTail` outcome by construction
rather than by accident: an unchanged rule set graded against itself.

So the oracle-seed-per-branch step was never one more 4.9.2 cartridge for any of
the six.

**The 4.9.7 corpus exists now** and closes the first half: `std497` and
`drydock497`, one seed apart by a single flag value, at
`seeds/ff1/oracle-4.9.7/`. `ShipDrydock` turns out to have the export footprint
`NoTail` did not — it rewrites 52 of the 207 rules the two exports share, always
by taking the `Ship` alternative away, and the pack over-reports 53 locations as
reachable on such a seed today. `MapAirshipHike` and `MapCardiaLandBridge` are
rollable there too and have not been measured yet. Figures, mechanism and the
build deltas are in `docs/ORACLE.md`, "The second corpus: 4.9.7".

The three ToFR flags still want something other than the export;
`tools/tofr_diff.py` is the tool that covers ToFR by comparison instead.

Two to verify rather than add: `IsFloaterRemoved`, `ShuffleObjectiveNPCs`.

## Keeping this current

The list of flags the logic consults is a grep, so it can be a test. Vendor the
FFR revision the schemas are generated from, run the two greps above in
`tools/tests`, and fail when a flag appears in `OverworldMap.cs`, `NPCs.cs`,
`MetroidVaniaMap.cs`, `TempleOfFiends.cs` or `IVictoryConditionFlags` that is in
neither `flag_mapping.lua` nor an explicit `NOT_MODELLED` list. That turns
"follow updates to the logic engine" from a habit into a failing test on the
day FFR adds a flag.
