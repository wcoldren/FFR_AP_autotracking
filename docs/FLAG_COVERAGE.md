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
| `IsFloaterRemoved` | Read once, at `SanityCheckerV2.cs:178`, and only to clear `MapChange.Airship` out of `requiredMapChanges` — which feeds the `complete` boolean and no per-location rule | `floater` progressive assumes Floater->Airship | n/a for colours — verified 2026-09-01, see below |
| `AirBoat` | Ship doubles as airship after Floater | `airBoat` progressive, rules use it | code |
| `GameMode` | Compared against `DeepDungeon` and nothing else (`SanityCheckerV2.cs:183,779`) | `isNoOverworld()` from variant UID | variant (warning printed on mismatch) |

**`IsFloaterRemoved` was on the verify list and is now answered: it moves no
pin.** Two facts settle it and both are in the source. It is *computed*, not
stored -- `FlagsCompute.cs:85` gives it as `((NoFloater|IsAirshipFree) &
!NoOverworld) | DesertOfDeath` -- so it has no field in either shipped schema
and a pack code could not read it directly anyway; `NoFloater` is the field that
exists. And its single read inside `FF1Lib/Sanity/` relaxes the *completion*
requirement rather than any location's rule, so no exported rule can move with
it. A cartridge would say the same thing, and one was attempted: a `NoFloater`
seed will not roll against this corpus's preset at all, because removing the
Floater from the pool leaves item placement unable to meet the incentive count
(`ItemPlacement.cs:173`), with or without `IncentivizeAirship`. The by-
construction argument is what stands, and it is the stronger of the two.

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
Desert`. A Desert seed is warned about, but by `flag_mapping.lua:410`
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
| `MapAirshipHike` | `airshipHike` | code — 4.9.7+ only. `OverworldMap.cs:62` adds the `AirshipHike` map edit; every rule it rewrites gains a `(Floater AND Ship)` alternative, which is the Floater standing in for having raised the airship where it stands. 124 of the 208 rules `std497` and `airship497` share move (`docs/ORACLE.md`) |
| `MapCardiaLandBridge` | `cardiaLandBridge` | code — 4.9.7+ only. `OverworldMap.cs:64` adds the land bridge, `:392` moves the Cardia and Bahamut overworld teleport coordinates with it, and `:55` suppresses `BahamutCardiaDock`; the rewritten rules gain `(Canoe AND Canal AND Ship)`. 42 of 206 shared rules move. Also the one of the two read outside `OverworldMap.cs`, at `EntrancesFloorsShuffle.cs:71` |
| `ShipDrydock` | `shipDrydock`, through `$noShipDrydock` | code — 4.9.7+ only. Every alternative naming `ship` carries the guard, because a drydocked Ship opens nothing (`docs/ORACLE.md`) |
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
| `ShuffleObjectiveNPCs` | — | **missing**, and confirmed to move pins on 2026-09-01. `NPCs.cs:135` runs it when `ChestsKeyItems` is also on and the mode is not Deep Dungeon; `NPCs.cs:277` permutes Bahamut, Dr Unne and the Elf Doctor across BahamutCave2, Melmond and Elfland Castle. Measured on `objnpc497`: Bahamut and Unne swapped outright. It rewrites **no** exported rule, so `check_logic` cannot see it — see "The permutation is the problem" below |
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
| `ToFRMode` | `shortToFR` progressive; `shortToFR,$canBreakOrb` on the ToFR node | code — only Short moves a rule |
| `ChaosRush` | `chaosRush` toggle; `chaosRush,$canBreakOrb,lute` on the ToFR node | code |
| `ExitToFR` | `NOT_MODELLED` in `flag_mapping.lua` | **decided against** — it opens nothing; see below |

## D. Placement-only (large group, all n/a for colours)

`Incentivize*` (~50 properties), `*IncentivePlacementType`, `Treasures`, `Shops`,
`RandomizeTreasure`, `WorldWealth`, `Guaranteed*`, `NoMasamune`, `NoXcalber`,
`SendMasamuneHome`, `ItemMagicMode`, `Etherizer`, `MermaidPrison`, `TitansTrove`.
These decide *what is where*, which the tracker must not know. The `Incentivize*`
and `TitansTrove` codes the pack does carry drive pin colour (blue/gold) and
whether Titan's Trove exists as a check — presentation, not reachability.

## Missing rows, in one place

Reachability flags with no pack code today:

1. `ShuffleObjectiveNPCs`

**Every flag that was on this list by name is done.** `MapAirshipHike` and
`MapCardiaLandBridge` were the last two and landed 2026-09-01, graded on a
cartridge each — see their rows in section B and `docs/ORACLE.md`. What replaced
them is the one entry above, which was on the *verify* list rather than this one
and turned out to belong here.

`IsFloaterRemoved` was the other name on the verify list and is answered in
section A: it moves no pin.

### The permutation is the problem, not the flag

`ShuffleObjectiveNPCs` is in both shipped schemas, so the pack can see that it
is on. That is not enough to colour anything, because **where the three NPCs
went is rolled at generation and reaches neither the flag string nor the
spoiler** — the same shape as the Cardia gateway roll, and the reason both sit
here rather than being a morning's work.

Measured rather than argued. `objnpc497` is `std497` plus this one flag, and
`tools/extract_npcs.py` reads both cartridges:

    bahamut   map 39 (21,3)  ->  map 3  (26,1)     BahamutCave2 -> Melmond
    unne      map 3  (26,1)  ->  map 39 (21,3)     Melmond -> BahamutCave2
    elfprince unchanged

FFR's export does not notice. Of the 204 rules the two exports share exactly one
moves, and it is `Shop Item`, which tracks where the shop landed and is roll
noise rather than the flag (the `ShipDrydock` diff hit the same row for the same
reason). `Elf Prince` and `Lefein` are byte-identical across the two. So the
pack grades **224 of 224** on `objnpc497` while being wrong, which makes this
the `NoTail` case: the export cannot grade the branch, and the lying cell is the
pack's own.

**Two cells lie on that cartridge, in opposite directions.** The pack hosts
`bahamut` under `Cardia Islands/Bahamut's Cave`, gated on the airship, and
`slabTranslated` under `Melmond Continent/Melmond/Dr Unne`. With the two swapped,
`bahamut` is held red while Bahamut stands in Melmond and is reachable early,
and `slabTranslated` reads reachable while Unne sits behind the airship. The
second is the over-reporting direction and is the one that matters.

Two ways to close it, and they are not equivalent:

- **Strict.** With the flag on, gate all three objective NPCs on reaching all
  three of their possible homes. Honest, cheap, and dominated by Bahamut's Cave,
  so in practice it means "needs the airship". This is what the Cardia roll got.
- **Read it off the cartridge.** `tools/extract_npcs.py` already finds the
  answer, and `regen_maps.py` already reads the cartridge per seed; the live
  bridge does not publish NPC positions today. This is the same feature as
  publishing `ff1/gateways` for the Cardia roll and should be built once, for
  both.

**`ToFRMode` and `ChaosRush` landed 2026-08-31.** Neither can be graded by
`check_logic` — `Archipelago.cs:93` drops every ToFR location from the pool, so
rolling a cartridge for either reproduces the `NoTail` outcome by construction,
an unchanged rule set graded against itself. Their evidence is the derived walk
instead: `oracle-4.9.2/nov` rolls `ToFRMode 2` and derives all seven ToFR chests
as `[["orbs"]]`, which the pack contradicted until now.

**`ExitToFR` was the fifth, and is now decided rather than pending.** It writes
an exit portal and nothing else: `0x40`, `TP_TELE_WARP`, and `reachable_maps`
only follows `TP_TELE_NORM`, so it creates no way in — `NOVERWORLD.md`, "the
exit portal is an exit and nothing more". This pack does not model points of no
return, so there is nothing for it to gate. A code for it would be a cell on
the board that changes no colour, which is worth less than nothing.

It is named in `NOT_MODELLED` in `flag_mapping.lua` rather than left off the
list, because a flag with no code cannot otherwise be told from one nobody has
got to yet. `tests/test_flags.lua` holds that table against both shipped
schemas: every name in it has to be a real flag, and no flag may be claimed by
two of the three coverage tables.

`NoTail` and `ShipDrydock` were on this list and are **done** — see their rows
in section B. `NoTail` turned up the rule this page now applies throughout: **a
flag being declared in `IVictoryConditionFlags` does not mean `SanityCheckerV2`
reads it.** Section A' is what running that grep over the rest produced, and it
moved seven rows out of section A.

Each row here cost the same four things: a `TOGGLES`/`PROGRESSIVES` row in
`flag_mapping.lua`, a code in `items/flags.json`, the affected `access_rules`
alternatives, and one oracle seed rolled with the flag on so `check_logic`
grades the branch. The last two were `MapAirshipHike` and `MapCardiaLandBridge`,
and the only thing that made them look harder than they were is that the stock
4.9.7 preset omits both keys — the same omission `ShipDrydock` had, and
Newtonsoft binds a key written in explicitly straight onto `Flags`.

**A loosening flag needs the same guard a tightening one does.** Both of these
add a route rather than take one away, so the failure they cause is a pin held
red rather than a pin shown green — less dangerous to a player, and just as
wrong. Their new alternatives carry `$noShipDrydock` like every other one that
names the Ship, because a drydocked Ship opens nothing and neither flag changes
that; `tests/test_ram.lua` demonstrates that half too.

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
amount of rolling against the present corpus reaches them. **All three are done
now**, each on its own 4.9.7 cartridge.

**Three are Temple of Fiends flags, and the export never covers ToFR.**
`ToFRMode`, `ChaosRush` and `ExitToFR` are all present at 4.9.2, so a cartridge
*can* be rolled — but `archipelago/Archipelago.cs:93` drops every ToFR location
from the pool unconditionally, and ToFR appears zero times in all five existing
exports. Rolling one of these produces the `NoTail` outcome by construction
rather than by accident: an unchanged rule set graded against itself.

So the oracle-seed-per-branch step was never one more 4.9.2 cartridge for any of
the six.

**The 4.9.7 corpus closed the first half.** `std497` and `drydock497`, one seed
apart by a single flag value, at `seeds/ff1/oracle-4.9.7/`. `ShipDrydock` turned
out to have the export footprint `NoTail` did not — it rewrites 51 of the 207
rules the two exports share, every one of them by taking the `Ship` alternative
away, and
the pack was over-reporting 53 locations as reachable on such a seed. It has a
code now, graded on that cartridge: 170 of 223 agreeing before, 223 of 223
after. `MapAirshipHike` and `MapCardiaLandBridge` were rollable there
too, and are measured now. `MapAirshipHike` and `MapCardiaLandBridge` were rolled the
same way on 2026-09-01 and behaved like `ShipDrydock` rather than `NoTail`,
except that both **loosen**: the pack was over-strict, holding 134 and 46
locations red that FFR calls reachable, and grades 224 of 224 and 223 of 223
after. Figures, mechanism and the build deltas are in `docs/ORACLE.md`, "The
second corpus: 4.9.7".

The three ToFR flags still want something other than the export;
`tools/tofr_diff.py` is the tool that covers ToFR by comparison instead.

Both names that were on the verify list are answered: `IsFloaterRemoved` moves
no pin (section A), and `ShuffleObjectiveNPCs` moves two (above).

## Keeping this current

The list of flags the logic consults is a grep, so it can be a test. Vendor the
FFR revision the schemas are generated from, run the two greps above in
`tools/tests`, and fail when a flag appears in `OverworldMap.cs`, `NPCs.cs`,
`MetroidVaniaMap.cs`, `TempleOfFiends.cs` or `IVictoryConditionFlags` that is in
neither `flag_mapping.lua` nor an explicit `NOT_MODELLED` list. That turns
"follow updates to the logic engine" from a habit into a failing test on the
day FFR adds a flag.
