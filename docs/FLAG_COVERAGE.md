# Flag coverage: what FFR's logic consults vs what the pack models

Compiled 2026-08-30 against `wcoldren/FFR_AP_autotracking` `trunk` (d0b7367) and
`FiendsOfTheElements/FF1Randomizer` at `0f91e97` (2026-08-24). The 4-9-7 schema's
build SHA `1f31434` was not reachable in a 2000-commit clone, so the FFR side is
trunk head, not the schema build; re-run the greps below when pinning.

The parity target is `SanityCheckerV2` + `SCLogic`. Two things about how it reads
flags shape this whole table:

1. **It consults only ~16 flags directly**, all through `IVictoryConditionFlags`
   (`Interfaces.cs:171-190`). These are the "free X" and mode flags.
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

| FFR flag | Effect on logic | Pack | Status |
|---|---|---|---|
| `IsBridgeFree` / `FreeBridge` | Bridge in starting inventory | `bridge` from `$6008` | RAM |
| `IsShipFree` / `FreeShip` | Ship in starting inventory | `ship` from `$6000` | RAM |
| `IsCanalFree` / `FreeCanal` | Canal open at start | `canal` from `$600C` | RAM |
| `IsCanoeFree` / `FreeCanoe` | Canoe at start | `canoe` from inventory | RAM |
| `IsAirshipFree` / `FreeAirship` | Airship at start | `floater` stage 2 from inventory | RAM |
| `FreeLute` | Lute at start | `lute` from inventory | RAM |
| `FreeRod` | Rod at start | `rod` from inventory | RAM |
| `FreeTail` | Tail at start | `tail` from inventory | RAM |
| `IsFloaterRemoved` | Airship placed as an item; no Floater/desert step | `floater` progressive assumes Floater→Airship | probably RAM (airship byte lights stage 2); **verify** |
| `AirBoat` | Ship doubles as airship after Floater | `airBoat` progressive, rules use it | code |
| `GameMode` / `NoOverworld` | Mode 2 = No-Overworld | `isNoOverworld()` from variant UID | variant (warning printed on mismatch) |
| `DesertOfDeath` | Mode 3: desert overworld, damage tiles | none; `flag_mapping` warns on non-standard `GameMode` | unmodellable today |
| `ShardHunt` | Goal is shards, not orbs | variant + `hasEnoughShards()` | variant |
| `OnlyRequireGameIsBeatable` | Placement leniency | — | n/a |
| `LooseExcludePlacedDungeons` | Placement | — | n/a |

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
| `MapAirshipHike` | — | **missing** (also read by `EntrancesFloorsShuffle.cs`) |
| `MapCardiaLandBridge` | — | **missing** |
| `ShipDrydock` | — | **missing**; Tracker.cs reads it, so FFR thinks a tracker needs it |
| `DisableOWMapModifications` | — | n/a (meta: disables all of the above) |

### NPC behaviour (`NPCs.cs`)

| FFR flag | Pack code | Status |
|---|---|---|
| `EarlyKing` | `earlyKing` | code |
| `EarlySarda` | `earlySarda` | code |
| `EarlySage` | `earlySage` | code |
| `NoTail` | `noTail` | code — declared in `IVictoryConditionFlags` but **`FF1Lib/Sanity/` never reads it**; it reaches the checker only as a pool edit (`PlacementContext.cs:99,205`), so it belongs here, not in A |
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

`NoTail` was the seventh and is **done** — see the row in section B. Closing
it turned up something that applies to the rest of this list: **a flag being
declared in `IVictoryConditionFlags` does not mean `SanityCheckerV2` reads it.**
`NoTail` is declared there and appears nowhere in `FF1Lib/Sanity/`. Check the
grep, not the interface, before filing a flag in section A.

Two to verify rather than add: `IsFloaterRemoved`, `ShuffleObjectiveNPCs`.
One that is a mode, not a flag: `DesertOfDeath`.

That is six codes, not twenty-five, and none is a redesign. Each wants: a
`TOGGLES`/`PROGRESSIVES` row in `flag_mapping.lua`, a code in `items/flags.json`,
the affected `access_rules` alternatives, and one oracle seed rolled with the
flag on so `check_logic` grades the branch. Without the oracle seed the code is
another hand-transcribed rule.

**Rolling the seed can also show the branch is ungradeable, and that is a
result.** `NoTail`'s cartridge proved the flag rewrites no rule FFR hands
Archipelago — its export mentions the Tail nowhere and Bahamut is not an AP
location — so `check_logic` grades it 226/226 against rules that had not
changed. The pack still needed the code, because the lying cell is the pack's
own; the gate for it is `tests/test_flags.lua`, not the oracle.

## Keeping this current

The list of flags the logic consults is a grep, so it can be a test. Vendor the
FFR revision the schemas are generated from, run the two greps above in
`tools/tests`, and fail when a flag appears in `OverworldMap.cs`, `NPCs.cs`,
`MetroidVaniaMap.cs`, `TempleOfFiends.cs` or `IVictoryConditionFlags` that is in
neither `flag_mapping.lua` nor an explicit `NOT_MODELLED` list. That turns
"follow updates to the logic engine" from a habit into a failing test on the
day FFR adds a flag.
