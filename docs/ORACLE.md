# The oracle cartridges

The pack's logic is checked against FFR's own answer, not against a
transcription. FFR's Archipelago export carries a `rules:` section — the access
rules FFR hands Archipelago — and `tools/check_logic.py` compares that with the
pack's rules as truth tables. This file says which cartridge answers which
question, and how to rebuild any of them from nothing.

Five cartridges, all 4.9.2, all generated locally with `Spoilers` and
`Archipelago` on so the export is attached.

**All 4.9.2 is a limit as well as a fact.** `ShipDrydock`, `MapAirshipHike` and
`MapCardiaLandBridge` do not exist in FFR at the 4.9.2 release commit, so no
cartridge here can be rolled with one of them on and no addition to this corpus
grades them. That is what the second corpus below is for. `docs/FLAG_COVERAGE.md`
has the rest of the split, including the three remaining flags that 4.9.2 *does*
carry and neither corpus can grade, because they are Temple of Fiends flags and
the export drops ToFR.

## Inventory

| Slug | Preset | Seed | Mode | Answers |
|---|---|---|---|---|
| `std` | `oracle_std` | `C189A0F0` | GameMode 0, ToFRMode 0 (Long) | the hand-written rules baseline |
| `nov` | `oracle_nov` | `F2585541` | GameMode 2, ToFRMode 2 (Short) | the derived No-Overworld rules |
| `nov2` | `oracle_nov` | `1D0BE11E` | GameMode 2, ToFRMode 2 (Short) | second seed at identical flags — the ToFR control |
| `shard` | `oracle_shard` | `5A4D0BAF` | GameMode 0, ShardHunt | `isShardHunt()` against a real export |
| `notail` | `oracle_notail` | `45057553` | GameMode 0, ToFRMode 0 (Long), NoTail | that `NoTail` reaches no exported rule — see below |

Modes are quoted as **read back off the cartridge**, never off the filename —
that trap has bitten more than once.

`nov` and `nov2` share a flag string by construction: the flag string encodes
flags, not the seed, which is what makes them a fair control for anything
seed-driven.

    std    omlInPoZ8aeRURUYlp1dof0D5xNDnrlGj9iV9YttYmO7Dv1Rmi6B0yqiIVR2PBvLS3STrugBTQeMv5wm1NR0AXzFFQUFmIyOlaB-i7D9BSRt.Lt4Snttst0yPEgyPIqf9Clw2RV-9AxD-qr33Lqb6rXFmyBvUxrD89pHBz3zAEWHH4FmWj
    nov    omlY4TDJ0WBi73FLBF5hW902l51xl72yHm32Rio0v38eGNM0fKy0TT8KJ-a0NWDQIIcxpvj7MlpYDG7gMaaVe-B1jhZllvTugQ53VEQHzfb-1wdKQG2Fnc64238l9e0jitE9LlbLND7XKw-ezMQ4exPzIyBvUxrD89pHBz3zAEWHH4FmWj
    nov2   (identical to nov)
    shard  omlInPoZ8aeCvsimCReMV9G4KHYm3TUYASJBGOBHlVOiR1kCNT91VO6GOxnA9GbEBb7YM1kQIzMfs8M3W7C8VP-aE5sJ0h2VYqBCNFMidFYuxFDg.QyWC6OgqMHtZPIrzXE9LlbLND7XKw-ezMQ4exPzIyBvUxrD89pHBz3zAEWHH4FmWj
    notail omlInPoZ8aeRURUYe2aUg0I8HZZCUXtPc76esLTcnyl5plsgMDVIQ3lOapR226xybGTTrugBTQeMv5wm1NR0AXzFFQUFmIyOlaB-i7D9BSRt.Lt4Snttst0yPEgyPIqf9Clw2RV-9AxD-qr33Lqb6rXFmyBvUxrD89pHBz3zAEWHH4FmWj

Each cartridge sits in its own directory with its spoiler `.txt`, its
Archipelago `.yaml` and, for the two No-Overworld ones, the derived rules JSON.
One cartridge per directory on purpose: `check_logic` globs `*.yaml` beside the
ROM when `--ap-rules` is not given, and two modes' exports in one directory get
folded together into a plausible-looking pile of divergences that are not real.
Pass `--ap-rules` anyway. The corpus lives in the Archipelago workspace, outside
this repo; `FINDINGS.local.md` has the path.

## Measured

Last run 2026-08-30, on freshly rebuilt cartridges.

| Check | Result |
|---|---|
| `std`, pack rules vs FFR | **225 checked, 225 agree, 0 divergences** |
| `shard`, pack rules vs FFR | **229 checked, 229 agree, 0 divergences** |
| `nov`, pack rules vs FFR | **226 compared, 220 agree, 6 deliberately strict**; of the 226, **215 independently supported** by the sweep, 11 not |
| `nov2`, pack rules vs FFR | **224 compared, 218 agree, 6 deliberately strict** |
| `nov`, derived rules vs FFR | **226 compared, 225 agree, 1 divergent** (Lefein) — **5 granted an off-vocabulary item**, so **221** are genuinely comparable; 255 derived, 0 unreachable |
| `nov2`, derived rules vs FFR | **224 compared, 223 agree, 1 divergent** (Lefein) — **5 granted**, **219** genuinely comparable; 255 derived, 0 unreachable |
| `nov` vs `nov2`, ToFR shuffle | **0 differences** |
| `notail`, pack rules vs FFR | **226 checked, 226 agree, 0 divergences** |

`std`'s 225/225 is the baseline to protect: it validates the harness end to end
against rules that were written by hand, and it must not move. `shard`'s 229/229
is the same kind of measurement for `isShardHunt()`.

**`notail`'s 226/226 measures something different, and reading it as a pass is a
mistake.** It was rolled to grade a `NoTail` branch and instead proved there is
no branch to grade: `NoTail` takes the Tail out of the item pool and rewrites no
access rule FFR hands Archipelago. Its export mentions the Tail nowhere, and
Bahamut is not an Archipelago location on any of the five cartridges. So the
226/226 was already true before the pack gained a `noTail` code and stayed true
after — it is a no-regression measurement, not evidence the code is right.

That makes `NoTail` a flag whose only lying cell is the pack's own, and its gate
is `tests/test_flags.lua`, which fails with the `flag_mapping.lua` row removed.
Two things fell out of rolling it, both worth carrying to the remaining flags:
`FF1Lib/Sanity/` never reads `NoTail` despite `IVictoryConditionFlags` declaring
it, and this repo's main 4-9-7 flag fixture has carried `NoTail` all along
without anyone noticing, because there was no code to notice it with.

**The two No-Overworld rows say much less than they look like they say, and the
difference matters more than the numbers.** Read the next section before quoting
either.

The pack's own No-Overworld rules were transcribed from FFR's export for the
seed, so grading them against that export is substantially self-agreement.
Tagging all 226 comparisons on `nov` by where the pack-side rule came from:

| n | provenance |
|---|---|
| 158 | transcribed from FFR's export |
| 12 | FFR region rule plus a pre-existing section gate |
| 6 | intersection of FFR's two seed exports — Cardia Forest |
| 32 | a pre-existing pack rule, written for standard mode years earlier |
| 18 | no gate at all |
| 0 | derived from the cartridge sweep |

That table is a snapshot of where each pack-side *rule* came from, and it has
not changed — the pack's No-Overworld rules were not touched when the last two
gate rows landed. What changed is the second reading available to check them
against. Until 2026-08-30 the sweep contributed **nothing** to the compared set:
the one rule taken from it, Bahamut's Cave, is not in FFR's pool and is never
compared, so independent support counted only the pre-existing and ungated
groups and came to **63 of 226**.

With SubEngineer and Titan gated and Oxyale and the Ruby swept, the sweep
derives a rule for every one of the 226 and agrees with FFR at 225 of them, 221
of those without an item being granted away. At every location where the pack's
transcribed rule agrees with FFR, the derived rule agrees too — the two never
part company. So **215 of the 226 now rest on two independent readings**, the
transcription and a walk of the cartridge. The eleven that do not are the 6
deliberately strict below, the 4 still granted a trade item (Herb, Adamant,
Bottle, Crystal), and Lefein, where the derivation is permissive and FFR is
right — see `docs/ISSUES.md`.

**The eleven, by name**, so this does not have to be re-derived. The 6 strict
are `Cardia Forest Incentive Room Left`, `Incentive Room Middle`,
`Incentive Room Lower`, `Cardia Forest Incentive`, `Cardia Forest Entrance
Bottom` and `Entrance Middle`. The 4 granted are `Dwarf Cave Smith` (adamant),
`Matoya's Cave Matoya` (crystal), `Elf Castle Elf Prince` (herb) and `Fairy`
(bottle). Lefein is granted the slab and is also the one divergence.

Two of the four granted already agree and only the grant hides it -- the
derivation says `[['adamant']]` for the Smith and `[['crystal']]` for Matoya
against FFR's `(Adamant)` and `(Crystal)`. **The Elf Prince does not**: it
derives `(free)` against FFR's `(Herb)`, and the grant is why that passes
quietly. See `docs/ISSUES.md`. The Fairy's `(Sigil AND Bottle)` is the one whose
item the cartridge's talk table does not carry at all -- `bottle` is not among
`talk_item_requirements`' seven entries, where herb, adamant, crystal and slab
all are.

The **6 deliberately strict** are Cardia Forest, and they are not a defect. FFR
says `chime,floater,oxyale OR canoe` on `nov` and `floater` on `nov2` because
that gateway is rolled per seed; the pack ships one static rule, so it ships the
conjunction and is strict on both. A check shown red that is reachable beats a
check shown green that is not.

`nov2`'s counts are 224 rather than 226 because that seed's export carries 225
locations rather than 227 — which pool a seed draws varies, and the comparable
set follows it.

Two waivers apply to every run against hand-written rules, and are not
divergences: Princess2 (the pack wants Garland beaten, FFR folds that in because
Garland is beatable from the start) and Lefein (the pack wants the Slab
translated, FFR counts holding it).

### What these figures do not cover

**The off-vocabulary grant, which was the big one and is now small.**
`check_logic --derived` hands every item the sweep cannot express to *both*
sides before comparing, so FFR reads as permissively as it can and a surviving
divergence cannot be blamed on the vocabulary gap. That is a fair test, but a
location where FFR's whole rule is granted away is not really compared at all.
Every `--derived` run prints the count and it was recorded nowhere until
2026-08-30: **164 of `nov`'s 222, 156 of `nov2`'s 220**, concentrated in one
item — **oxyale x129 and ruby x32 on `nov`** — so "222 of 222 agree" described
58 locations, not 222.

That was **fixable rather than inherent**, and it is fixed. Oxyale and Ruby were
never "game rules" the walk could not see: `FF1Lib/Sanity/SCMap.cs:167-186`
gates five object ids by tile — RodPlate, LutePlate, BlackOrb, SubEngineer and
Titan — and the pack modelled the first three. The last two landed the same day,
with the vocabulary widening they require: `ITEM_NAMES` is twelve items, the
sweep is 2^12, and the grant is down to **5 of 226 on `nov` and 5 of 224 on
`nov2`** — one each for Herb, Adamant, Bottle, Crystal and Slab, the trades that
genuinely are not graph properties.

The sweep is 2^12 and still runs in under a minute, because the floor walk is
memoized on the map, the arrival tile, and the part of the held set that floor
actually consults. That key is the whole risk of having a memo, so it is guarded
exhaustively over the lattice by `tools/tests/test_memo_walk.py`.

**The Temple of Fiends Revisited.** `Archipelago.cs:93` drops ToFR from the AP
pool unconditionally, so FFR writes no rule for any ToFR location and not one of
them is among the compared set. Quoting the figure as covering the whole derived
set overstates it by exactly those eight maps. It is also where the missing
BlackOrb row shows: the derivation says six ToFR locations are free, and that is
wrong rather than correct — No-Overworld strips the `TP_SPEC_4ORBS` tile special
at `TempleOfFiends (20,17)` and leaves the Black Orb *object* standing on it, and
the walk models only the tile. That gap is why `tools/tofr_diff.py`
exists — it covers ToFR by comparison instead: hold the flags still, change the
seed, and report what the shuffle moved.

`nov` vs `nov2` reports 0 differences, and that is a live zero rather than a
dead reader: the two cartridges differ in 45987 bytes, and Gaia's gateway, both
Waterfall stairs and SkyPalace5F's chest layout all moved between them. Nothing
in ToFR did.

**Open, and deliberately not concluded here:** the recorded four-seed finding
that ToFR floor membership varies seed to seed was taken on *standard* seeds,
which roll Long or Mid ToFR. Both cartridges here are ToFRMode 2 (Short), where
Chaos's room holds the whole chest block. Whether Short is genuinely seed-stable
or these two seeds simply agree needs a second standard pair to say, and has not
been measured.

**The derived-rule files in the corpus were regenerated on 2026-08-30**, when
the SubEngineer and Titan rows widened the sweep to 2^12. They had been behind
the page for a while before that — the committed pair predated the NPC-location
split and gave 254 derived and 222/220 compared where this page recorded 255 and
226/224 — and the rows above are what the regenerated files actually produce.
Regenerating them is the two `noverworld_rules.py` commands below and about two
minutes.

## The second corpus: 4.9.7

At `seeds/ff1/oracle-4.9.7/`, built the same way from the 4.9.7 release commit
`1f31434` -- the SHA `tools/ffr_flags/schemas/4-9-7.json` already records, so the
flag decoder accepts a local build of it unmodified.

| Slug | Preset | Seed | Mode | Answers |
|---|---|---|---|---|
| `std497` | `oracle497_std` | `3B7E1C8A` | GameMode 0, ToFRMode 0 (Long) | that the harness and the standard rules hold at 4.9.7 |
| `drydock497` | `oracle497_drydock` | `3B7E1C8A` | the same, plus `ShipDrydock` | what `ShipDrydock` does to the rules FFR exports |
| `extended497` | `oracle497_extended` | `3B7E1C8A` | the same, plus `MapOpenProgressionExtended` | that the `extendedOpen` code describes the flag |
| `airship497` | `oracle497_airship` | `3B7E1C8A` | the same, plus `MapAirshipHike` | what `MapAirshipHike` does to the rules FFR exports |
| `landbridge497` | `oracle497_landbridge` | `3B7E1C8A` | the same, plus `MapCardiaLandBridge` | what `MapCardiaLandBridge` does to the same |
| `objnpc497` | `oracle497_objnpc` | `3B7E1C8A` | the same, plus `ShuffleObjectiveNPCs` | where the three objective NPCs went, which only the cartridge says |
| `gaia497` | `oracle497_gaia` | `3B7E1C8A` | the same, plus `MapOpenProgressionDocks` and `MapGaiaMountainPass` | whether the northern-docks route to Gaia needs the highway |
| `gaiahwy497` | `oracle497_gaia` + `MapHighwayToOrdeals` | `3B7E1C8A` | the same three | that it does |

**The first six share `std497`'s seed and differ from it in one flag value.**
The Gaia pair is the exception and says so: answering that question needs the
docks and the mountain pass both on, so `gaia497` is two flags from the baseline
and `gaiahwy497` is one flag from `gaia497`. It is the pair that isolates, not
either cartridge against `std497`. So anything that moves between an export and `std497`'s is the flag,
not the roll -- a tighter control than `nov`/`nov2`, which hold the flags still
and vary the seed. `std497` is the baseline all four are read against, which is
why its row is the one to protect.

**The stock preset omits all three of the 4.9.7-only flags, and that is not the
same as the build not having them.** 4.9.7's `default.json` names neither
`ShipDrydock` nor `MapAirshipHike` nor `MapCardiaLandBridge`, even though all
three are ordinary `bool?` properties on `Flags` at that commit
(`Flags.cs:326-327`, and `ShipDrydock` beside them). Newtonsoft binds a key
written in explicitly straight onto `Flags`, so every preset here writes
`ShipDrydock` -- `oracle497_std`, `oracle497_drydock`, `oracle497_extended` and
`oracle497_objnpc` are 544 keys -- and `oracle497_airship` and
`oracle497_landbridge` add their own on top, at 545.
Every value was confirmed by decoding it back off the finished cartridge rather
than trusting the preset. An absent key is not an absent flag; that is the trap
this paragraph exists to stop, and it is the only thing that made the last two
rows look harder than `ShipDrydock` was.

### Measured

Last run 2026-09-01.

| Check | Result |
|---|---|
| `std497`, pack rules vs FFR | **226 checked, 226 agree, 0 divergences** |
| `drydock497`, pack rules vs FFR | **223 checked, 223 agree, 0 divergences** — it was 170 agree, 11 divergences over 53 locations before the `shipDrydock` code |
| `extended497`, pack rules vs FFR | **226 checked, 226 agree, 0 divergences** |
| `airship497`, pack rules vs FFR | **224 checked, 224 agree, 0 divergences** — it was 90 agree, 13 divergences over 134 locations before the `airshipHike` code |
| `landbridge497`, pack rules vs FFR | **223 checked, 223 agree, 0 divergences** — it was 177 agree, 5 divergences over 46 locations before the `cardiaLandBridge` code |
| `std497` vs `drydock497`, exported rules | **207 locations in both exports, 52 rules differ; 51 lose a `Ship` alternative and not one gains anything. The 52nd is `Shop Item` and is not the flag — see below** |
| `std497` vs `airship497`, exported rules | **208 in both, 124 differ; every one of them gains `(Floater AND Ship)` and none loses anything** |
| `std497` vs `landbridge497`, exported rules | **206 in both, 42 differ; every one gains `(Canoe AND Canal AND Ship)`** |
| `objnpc497`, pack rules vs FFR | **224 checked, 224 agree, 0 divergences** — one of them waived rather than agreed, and see below |
| `std497` vs `objnpc497`, exported rules | **204 in both, 1 differs, and it is `Shop Item` — roll noise, not the flag. `Elf Prince` and `Lefein` are byte-identical across the two** |
| `std497` vs `objnpc497`, NPC placement | **Bahamut `map 39 (21,3)` -> `map 3 (26,1)`, Unne the reverse; the Elf Doctor unmoved** (`tools/extract_npcs.py`) |
| `gaia497`, pack rules vs FFR | **224 checked, 224 agree, 0 divergences** — it was 223 agree, 1 divergence over 1 location before the Gaia fix |
| `gaiahwy497`, pack rules vs FFR | **225 checked, 225 agree, 0 divergences**, before the fix as well as after |
| `gaia497` vs `gaiahwy497`, the Fairy | **`(Canoe AND Floater AND Bottle)` -> that plus `(Canal AND Ship AND Bottle)`. Lefein moves the same way** |

**`objnpc497` is the row that does not mean what the others mean.** Every other
line above is the pack agreeing with FFR. This one is the pack agreeing with FFR
on 223 locations and deliberately disagreeing on the Elf Prince, waived with its
reason in `check_logic`'s `WAIVED` table. FFR wrote the seed, so its rule names
the home the roll actually picked; the pack cannot read that roll and asks for
all three homes instead. The two rows under it are why the cartridge was worth
building at all: the export cannot see this flag, and `extract_npcs.py` can.

A `NoFloater` cartridge was attempted alongside it and is not here. Removing the
Floater from the pool leaves item placement unable to meet this preset's
incentive count (`ItemPlacement.cs:173`), with or without `IncentivizeAirship`,
so the seed does not generate. `IsFloaterRemoved` did not need it --
`FLAG_COVERAGE.md` section A settles that flag from the source.

`std497`'s 226/226 is `std`'s 225/225 one version later, and it is the row that
says the corpus itself is sound: the harness works against a 4.9.7 export and the
pack's hand-written standard rules hold there unchanged. Protect it the same way.

**`drydock497` is the opposite of `notail`, and that is the whole point of
building this corpus.** `NoTail` rewrote no rule FFR hands Archipelago, so its
cartridge graded an unchanged rule set against itself. `ShipDrydock` rewrites 51
of the 207 rules the two exports share, and every one of the changes is a route
being taken away. Before the pack had a code for the flag it went on offering the
Ship route: 53 locations showed reachable that FFR says are not, across Elf
Castle, Marsh Cave, Earth Cave, the Castle of Ordeals, Astos, the Canoe Sage and
the Elf Prince. A check shown green that is not reachable is the failure mode the
pack cares most about, so this cartridge is the gate the `shipDrydock` code was
written against rather than a pack test, and the 170-of-223 to 223-of-223 move on
it is what says the guard bites.

**What the flag does**, read off the code rather than inferred from the diff:
`MapExchange/ShipLocations.cs:52-60` moves *every* ship spawn to the Gaia
drydock, and `OverworldMapEdits.cs:535-549` (`GaiaDrydock`, applied at
`OverworldMap.cs:69`) lays the dock tiles there. Wherever the seed puts the Ship,
it launches on the far eastern coast. Nothing gains a Ship alternative because
everything reachable from Gaia already needed the Canoe or the Airship.

**The 52nd differing rule is not the flag, and reading it as one is a mistake
worth not repeating.** `Shop Item` goes from `()` to `(Canoe)` between the two
cartridges, which looks like a land route closing. It is not. The slot is
whichever shop the seed chose to hold a key item, and the seeds chose different
ones -- `PravokaShop1` on `std497`, `ElflandShop4` on `drydock497`. The flag
cannot close a route at all: its map edit changes **11 overworld tiles, five of
which go from unwalkable to walkable and none the other way**, so it only ever
opens land. The mountain tiles in `GaiaDrydock` replace terrain that was already
impassable. Measured on the two cartridges 2026-08-31, tile by tile.

`Shop Item` is also the "1 could not be mapped" that every run on every
cartridge prints, so the pack's rule for it -- which is no rule at all -- has
never been compared against FFR on any seed. That is filed in `docs/ISSUES.md`
and is not a `ShipDrydock` defect.

Both check_logic runs print the "where ship, canal, canoe, floater were placed is
not recorded for this seed" caveat and are marked NOT COUNTED. That is the normal
condition for these cartridges -- the 4.9.2 runs behind the 225/225 and 229/229
figures print it too -- and the export diff above is the independent reading that
the 53 are not an artefact of it.

### Checking the 4.9.7 corpus

    O7=<corpus>/oracle-4.9.7
    for s in std drydock extended airship landbridge objnpc gaia gaiahwy; do
        python3 tools/check_logic.py $O7/${s}497/${s}497.nes \
            --ap-rules $O7/${s}497/${s}497.yaml --ff1-world $W
    done

No `--derived` on any of them: the sweep derives No-Overworld rules and all eight
are standard seeds.

### Rebuilding the 4.9.7 corpus

The recipe below, with three differences:

- base commit `1f31434` on local branch `ffr-497-oracle`, worktree
  `vendor/ff1/FF1Randomizer-497` (pinned in `pins.yaml` as
  `ff1_randomizer_497`); stamp `FFRVersion.Sha = "1f31434"`.
- **4.9.7 targets `net10.0`, not `net6.0`**, so the CLI is at
  `FF1R/bin/Release/net10.0/FF1R.dll` and `DOTNET_ROLL_FORWARD` is not needed.
- the presets are 4.9.7's own `default.json` with the same six flags flipped on,
  plus `ShipDrydock` written explicitly -- `false` in `oracle497_std` and `true`
  in `oracle497_drydock`. The stock preset omits the key entirely; Newtonsoft
  binds it straight onto `Flags`, and the value was confirmed by decoding it back
  off each finished cartridge rather than trusting the preset. The other three
  are `oracle497_std` with exactly one value changed in the same way:
  `MapOpenProgressionExtended`, `MapAirshipHike`, `MapCardiaLandBridge` and
  `ShuffleObjectiveNPCs`. The first three are keys the stock preset omits;
  `ShuffleObjectiveNPCs` is present and `false`, so that one is an edit rather
  than an addition.

Generating one of the newer three, for the record:

    O7=<corpus>/oracle-4.9.7
    dotnet FF1R/bin/Release/net10.0/FF1R.dll generate "<vanilla FF1 ROM>" \
        -j $O7/flags/oracle497_airship.json -s 3B7E1C8A \
        -o $O7/airship497/airship497.nes

## Rebuilding

The build tree is a git worktree of the FFR clone, pinned in `pins.yaml` as
`ff1_randomizer_492`, on local branch **`ffr-492-oracle`** — two commits on top
of the 4.9.2 release commit `01272d4`:

- the FF1R commit that writes the Archipelago export beside the ROM. 4.9.2's CLI
  cannot write one unaided: `--ap-export` is a later addition and only the web UI
  downloaded the export at that release. The spoiler it does write carries no
  `rules:`, so without this there is nothing to compare against.
- the `FFRVersion` stamp. A local build leaves the literal `"SHA"` in the ROM's
  FFRInfo block, and the flag decoder refuses on a mismatch with the SHA recorded
  in `tools/ffr_flags/schemas/4-9-2.json`.

Neither is pushed anywhere; they exist to make a local build usable.

    git -C <ffr-clone> worktree add -b ffr-492-oracle ../FF1Randomizer-492 01272d4
    # cherry-pick the export commit, stamp FFRVersion.Sha = 01272d4
    DOTNET_ROLL_FORWARD=LatestMajor dotnet build FF1R -c Release

`DOTNET_ROLL_FORWARD` is not optional — the projects target `net6.0`, which a
modern SDK will not run without it.

Generating, per cartridge:

    DOTNET_ROLL_FORWARD=LatestMajor dotnet FF1R/bin/Release/net6.0/FF1R.dll generate \
        "<vanilla FF1 ROM>" -j flags/<preset>.json -s <SEED> -o <slug>/<name>.nes

`-j` takes a preset-shaped file; `-p` looks in the user settings directory and
will not accept a path. Each flags preset is a stock 4.9.2 preset from
`FF1Blazorizer/wwwroot/presets/` with exactly six flags flipped on: `Spoilers`,
`Archipelago`, and the four pool flags `ArchipelagoConsumables`,
`ArchipelagoEquipment`, `ArchipelagoGold`, `ArchipelagoShards`. The pool flags
are what take FFR's `rules:` from the key items alone up to 225 locations.
`oracle_std` is `default.json`, `oracle_nov` is `NOverworld.json`, `oracle_shard`
is `Shard_Hunt.json`.

**The rebuild is bit-reproducible.** Regenerating `std` and `nov` from their
flags JSON at their recorded seeds produced ROMs, spoilers and exports
byte-identical to the originals. (Regenerating from a cartridge's own *flag
string* is a weaker operation — it reproduces the logic exactly but loses
`Preferences`, so around 25540 bytes of CHR, credits and dialogue differ. Neither
touches a map bank.)

## Running the checks

    W=<archipelago>/worlds/ff1
    O=<corpus>

    python3 tools/noverworld_rules.py $O/nov/oracle_nov.nes   -o $O/nov/derived_nov.json
    python3 tools/noverworld_rules.py $O/nov2/oracle_nov2.nes -o $O/nov2/derived_nov2.json

    python3 tools/check_logic.py $O/nov/oracle_nov.nes \
        --derived $O/nov/derived_nov.json --ap-rules $O/nov/oracle_nov.yaml --ff1-world $W
    python3 tools/check_logic.py $O/std/oracle_std.nes \
        --ap-rules $O/std/oracle_std.yaml --ff1-world $W
    python3 tools/check_logic.py $O/shard/oracle_shard.nes \
        --ap-rules $O/shard/oracle_shard.yaml --ff1-world $W
    python3 tools/check_logic.py $O/notail/notail.nes \
        --ap-rules $O/notail/notail.yaml --ff1-world $W

    python3 tools/tofr_diff.py $O/nov/oracle_nov.nes $O/nov2/oracle_nov2.nes

`--ff1-world` is load-bearing: without it only about 20 checks map and the run
reports a cheerful zero. `--ap-rules` is load-bearing for the reason above. The
`nov` derivation sweep is about 60 seconds -- 4096 subsets rather than the old
1024, and faster than the old sweep was, because the floor walk is memoized;
everything else is fast.

`tofr_diff.py` has three answers, not two — 0 same, 1 differs, 2 incomparable.
It refuses to compare rather than report a shape difference as a shuffle
difference, and there are three ways it refuses:

- `GameMode` differs. No-Overworld repoints TempleOfFiends straight at Chaos and
  orphans the seven interior floors, so `inbound` differs by construction. This
  is what `std` against `nov` hits first.
- `ToFRMode` differs. The mode decides which floors exist at all.
- `ToFRMode` is 3 (**Random**) on both sides. The cartridge records the setting,
  never the roll — `FF1Lib/TempleOfFiends.cs:52` collapses Random with `rng` and
  writes the result nowhere — so two cartridges from one Random preset can be
  Long and Short while their flags match to the byte. Equal is not comparable.
  A corpus meant for this tool should pin `ToFRMode`, which is what the three
  presets here do.
