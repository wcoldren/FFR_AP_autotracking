# The oracle cartridges

The pack's logic is checked against FFR's own answer, not against a
transcription. FFR's Archipelago export carries a `rules:` section — the access
rules FFR hands Archipelago — and `tools/check_logic.py` compares that with the
pack's rules as truth tables. This file says which cartridge answers which
question, and how to rebuild any of them from nothing.

Six cartridges, all 4.9.2, all generated locally with `Spoilers` and
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
| `novnolefein` | `oracle_novnolefein` | `F2585541` | the same as `nov`, minus `LefeinSuperStore` | what `LefeinSuperStore` does to a No-Overworld seed, which is nothing a router sees |

Modes are quoted as **read back off the cartridge**, never off the filename —
that trap has bitten more than once.

`nov` and `nov2` share a flag string by construction: the flag string encodes
flags, not the seed, which is what makes them a fair control for anything
seed-driven.

**`nov` and `novnolefein` are the other kind of pair**, and share the *seed*
rather than the flags -- the tighter control, and the one the 4.9.7 corpus uses
throughout. Two cartridges here now carry seed `F2585541`, so name the slug in
prose for these as well; the paragraph below about `F258553F` says why.

    std    omlInPoZ8aeRURUYlp1dof0D5xNDnrlGj9iV9YttYmO7Dv1Rmi6B0yqiIVR2PBvLS3STrugBTQeMv5wm1NR0AXzFFQUFmIyOlaB-i7D9BSRt.Lt4Snttst0yPEgyPIqf9Clw2RV-9AxD-qr33Lqb6rXFmyBvUxrD89pHBz3zAEWHH4FmWj
    nov    omlY4TDJ0WBi73FLBF5hW902l51xl72yHm32Rio0v38eGNM0fKy0TT8KJ-a0NWDQIIcxpvj7MlpYDG7gMaaVe-B1jhZllvTugQ53VEQHzfb-1wdKQG2Fnc64238l9e0jitE9LlbLND7XKw-ezMQ4exPzIyBvUxrD89pHBz3zAEWHH4FmWj
    nov2   (identical to nov)
    shard  omlInPoZ8aeCvsimCReMV9G4KHYm3TUYASJBGOBHlVOiR1kCNT91VO6GOxnA9GbEBb7YM1kQIzMfs8M3W7C8VP-aE5sJ0h2VYqBCNFMidFYuxFDg.QyWC6OgqMHtZPIrzXE9LlbLND7XKw-ezMQ4exPzIyBvUxrD89pHBz3zAEWHH4FmWj
    notail omlInPoZ8aeRURUYe2aUg0I8HZZCUXtPc76esLTcnyl5plsgMDVIQ3lOapR226xybGTTrugBTQeMv5wm1NR0AXzFFQUFmIyOlaB-i7D9BSRt.Lt4Snttst0yPEgyPIqf9Clw2RV-9AxD-qr33Lqb6rXFmyBvUxrD89pHBz3zAEWHH4FmWj
    novnol omlY4TDJ0WBi73FLBF5VGzzAxztAsvA1h7hrrqcjdsidtXDK56cD4rAwa.3JnP7xA1eccFbQG-e.47l5WKeeBsCx37sjlvTugQ53VEQHzfb-1wdKQG2Fnc64238l9e0jitE9LlbLND7XKw-ezMQ4exPzIyBvUxrD89pHBz3zAEWHH4FmWj

Each cartridge sits in its own directory with its spoiler `.txt`, its
Archipelago `.yaml` and, for the two No-Overworld ones, the derived rules JSON.
One cartridge per directory on purpose: `check_logic` globs `*.yaml` beside the
ROM when `--ap-rules` is not given, and two modes' exports in one directory get
folded together into a plausible-looking pile of divergences that are not real.
Pass `--ap-rules` anyway. The corpus lives in the Archipelago workspace, outside
this repo; `FINDINGS.local.md` has the path.

## The play cartridges

Not oracles, and not interchangeable with them. These were rolled to be played,
and they are where the pack's *art* comes from and where most in-game
observations were made. They ship no Archipelago export, so nothing can be
graded against them -- a figure taken here is a measurement, never a grade.

| Seed | Directory | FFR | Mode | What it answers |
|---|---|---|---|---|
| `F258553F` | `duck-104` | 4.9.2 | GameMode 2, ToFRMode 2 (Short) | the reference No-Overworld cartridge; the source of the `nov` art and of most No-Overworld measurements in the log |
| `8EF791AA` | `duck-weekly-0831` | 4.9.7 | GameMode 0 | the source of the `std` art, and the seed the Cardia pins were reported wrong on |
| `05436F8E` | `duck-weekly-0831-v2` | 4.9.7 | GameMode 0 | the replay of that flag set, rolled with `Spoilers` on. One setting of 568 differs from `8EF791AA`, and it is `Spoilers` |
| `C189A0EF` | `duck-102` | 4.9.2 | GameMode 0 | the standard seed the sprite and Crown-gate counts were taken on |
| `2CCBA52F` | `duck-103` | 4.9.2 | GameMode 0 | the second standard seed, so a count has two cartridges behind it |
| `72A52C25` | `practice-72A52C25` | 4.9.2 | GameMode 0 | the standard control for the Temple of Fiends floor comparison |
| `F2585540` | not kept | 4.9.8 | GameMode 2, ToFRMode 2 (Short) | rolled once to measure version drift against `F258553F`, then discarded |

`duck-weekly-0831` and `duck-104` are the pair the installed override was
rendered from, standard and No-Overworld. Replacing either means a regen for
that mode, not a file swap.

**`F258553F` and `F2585541` are different cartridges.** Both are FFR 4.9.2,
both GameMode 2, both ToFRMode 2 (Short), and they differ in the last two
characters. One is the play seed above; the other is the `nov` oracle in the
inventory at the top of this page. Nothing distinguishes them at a glance, and
a measurement filed against the wrong one would look right. **Name the slug in
prose** -- `duck-104`, `nov` -- and leave the bare hex to these two tables.

Two more identifiers appear in the docs and are not cartridges anyone can load:
`D0E0CDBF` in `tools/ffr_flags/README.md` and `6BF0DEA9` in `docs/BRIDGE.md`
are sample output, showing the shape of an `FFRInfo` record and of a run-clock
log line.


## Measured

Last run 2026-09-03. The header names the freshest row in the table, which is
`novnolefein`; the rows above it were run 2026-08-30 on freshly rebuilt
cartridges, and the `nov` and `nov2` derived rows were regraded 2026-09-03
against regenerated derivations.

| Check | Result |
|---|---|
| `std`, pack rules vs FFR | **225 checked, 225 agree, 0 divergences** |
| `shard`, pack rules vs FFR | **229 checked, 229 agree, 0 divergences** |
| `nov`, pack rules vs FFR | **226 compared, 220 agree, 6 deliberately strict**; of the 226, **215 independently supported** by the sweep, 11 not |
| `nov2`, pack rules vs FFR | **224 compared, 218 agree, 6 deliberately strict** |
| `nov`, derived rules vs FFR | **226 compared, 225 agree, 1 divergent** (Lefein) — **5 granted an off-vocabulary item**, so **221** are genuinely comparable; 256 derived, 0 unreachable |
| `nov2`, derived rules vs FFR | **224 compared, 223 agree, 1 divergent** (Lefein) — **5 granted**, **219** genuinely comparable; 256 derived, 0 unreachable |
| `nov` vs `nov2`, ToFR shuffle | **0 differences** |
| `notail`, pack rules vs FFR | **226 checked, 226 agree, 0 divergences** |
| `novnolefein`, derived rules vs FFR | **222 compared, 221 agree, 1 divergent** (Lefein, the same strict row `nov` has) — **5 granted an off-vocabulary item**; 256 derived, 0 unreachable |

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
| `dock497` | `oracle497_dock` | `3B7E1C8A` | the same, plus `MapBahamutCardiaDock` | what the Bahamut dock opens, and what it leaves shut |
| `dockbridge497` | `oracle497_dock` + `MapCardiaLandBridge` | `3B7E1C8A` | the same two | what the dock and the land bridge do *together* |
| `hoard497` | `oracle497_hoard` | `3B7E1C8A` | the same, plus `MapDragonsHoard` | that the hoard relocates the Cardia locations, so the export can be asked about Bahamut's Cave at all |
| `hoarddock497` | `oracle497_hoard` + `MapBahamutCardiaDock` | `3B7E1C8A` | the same two | Bahamut's Cave's requirement with the dock |
| `hoardbridge497` | `oracle497_hoard` + `MapCardiaLandBridge` | `3B7E1C8A` | the same two | Bahamut's Cave's requirement with the land bridge |
| `hoarddockbridge497` | `oracle497_hoard` + both | `3B7E1C8A` | the same three | Bahamut's Cave's requirement with both, which is not the union |
| `hoardhike497` | `oracle497_hoard` + `MapAirshipHike` | `3B7E1C8A` | the same two | Bahamut's Cave's requirement with the hike |
| `nonpcitems497` | `oracle497_nonpcitems` | `3B7E1C8A` | `std497` **minus** `NPCItems` | what `NPCItems` governs, which turns out to be the incentive pool and not the rules |
| `nofetchitems497` | `oracle497_nofetchitems` | `3B7E1C8A` | `std497` **minus** `NPCFetchItems` | the same question for the fetch half, which turns out to be the incentive pool and not the rules either -- and which of the pack's eight fetch rows FFR actually incentivizes |
| `hoarddockhike497` | `oracle497_hoard` + `MapBahamutCardiaDock` + `MapAirshipHike` | `3B7E1C8A` | the same three | the three Cardia-relevant flags a played seed rolled, carried on `std497`'s baseline rather than that seed's whole flag set, and the combination the pairs above do not cover |

**Every cartridge here shares `std497`'s seed**, a tighter control than
`nov`/`nov2`, which hold the flags still and vary the seed. `std497` is the
baseline they are all read against, which is why its row is the one to protect.

**A shared seed holds the rules still, not the pool**, and this page said
otherwise until 2026-09-03: "anything that moves between an export and
`std497`'s is the flag, not the roll" is true of the rules, the location ids and
`priority_locations`, and true of which locations are in the export at all only
in the sense that nothing there can be attributed by counting. About twenty
locations change hands either way on every pair. A flag that changes the pool's
*shape* also moves locations in and out for real, and the two look alike. The
figures are below, under "Diffing the corpus, and what one flag apart does not
hold still".

**Most of them are one flag from that baseline; the rest say which pair they
isolate.** `drydock497`, `extended497`, `airship497`, `landbridge497`,
`objnpc497`, `dock497` and `hoard497` each change one value. The others exist
because the question needs two flags at once, and then it is the *pair* that
isolates rather than either cartridge against `std497`: `gaia497` needs the
docks and the mountain pass together, with `gaiahwy497` one flag further on;
`dockbridge497` is `dock497` plus the land bridge; and the four `hoard*`
cartridges are `hoard497` plus the flag whose effect on Bahamut's Cave is being
read.

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

Last run 2026-09-03.

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
| `dock497`, pack rules vs FFR | **225 checked, 225 agree, 0 divergences** |
| `dockbridge497`, pack rules vs FFR | **226 checked, 226 agree, 0 divergences** — it was 215 agree, 3 divergences over 11 locations before the dock-and-land-bridge alternative |
| `hoard497`, pack rules vs FFR | **223 checked, 223 agree, 0 divergences** |
| `hoarddock497`, pack rules vs FFR | **225 checked, 225 agree, 0 divergences** — it was 215 agree, 3 divergences over 10 locations before the `BahamutHoard` alternative |
| `hoardbridge497`, pack rules vs FFR | **225 checked, 225 agree, 0 divergences** |
| `nonpcitems497`, pack rules vs FFR | **224 checked, 224 agree, 0 divergences** |
| `std497` vs `nonpcitems497`, exported rules | **206 in both, 0 differ.** `NPCItems` moves no reachability rule at all |
| `std497` vs `nonpcitems497`, `priority_locations` | **7 gone: King, Princess, Bikke, Sarda, Canoe Sage, CubeBot and Shop Item**, with `IncentivizeFreeNPCs` still on -- the `NPCItems` conjunct of the computed `IncentivizeCaravan`, measured rather than read off `FlagsCompute.cs`. The pack rings all seven; see `docs/ISSUES.md` |
| `nofetchitems497`, pack rules vs FFR | **226 checked, 226 agree, 0 divergences** |
| `std497` vs `nofetchitems497`, exported rules | **206 in both, 0 differ.** `NPCFetchItems` moves no reachability rule at all, the same as its free-half sibling |
| `std497` vs `nofetchitems497`, `priority_locations` | **7 gone: Astos, Elf Prince, Fairy, Lefein, Matoya, Nerrick and Smith**, with `IncentivizeFetchNPCs` still on -- the `NPCFetchItems` conjunct of the seven computed at `FlagsCompute.cs:220-226`. The pack rings all seven; see `docs/ISSUES.md` |
| `std497` vs `nofetchitems497`, whether a slot leaves | **no. All seven stay in `rules` and `locations`** -- 227 to 226, and both the removed and the added names are chests, so the net one is pool churn the tool declines to attribute. Unlike the free half there is no caravan-shaped second repair: the fetch fix is the conjunction on seven rows and nothing else |
| the incentive rings, all 23 exports | **0 wrong**, since 2026-09-03. `tools/tests/test_incentive_conjunction.py` predicts each slot's ring from the export's own flags and compares it to `priority_locations`. Before the conjunctions it was 13 wrong rings and one ghost -- 7 on `nofetchitems497`, 6 plus the caravan slot on `nonpcitems497` -- and before Nerrick's third term, `nov` and `nov2` each rang him. One disagreement is waived by name rather than scoped away: a Sea Shrine chest `notail` does not have. Two others were waived and are not now. `Dr Unne`, who is no seed's location, went when the slot was removed rather than excused; the Cardia ring on the five hoard cartridges went when the progressive was split, and `hoarddockbridge497`'s Cardia ghost went with it -- that row was only reachable through the ring being wrong, so the finding behind it is open and this corpus can no longer show it. Both 2026-09-03 |
| `std497` vs `nofetchitems497`, `Dr Unne` | **not among the seven, and not an AP location at all.** FFR has no `IncentivizeUnne`; `SCLogic.cs:555-557` folds Unne into Lefein's reachability. The pack gave `I: Dr Unne` an incentive section on both sheets, `hosted_item: slabTranslated` gated on `fetchQuestsAreIncentive` -- an eighth slot FFR never fills. Removed 2026-09-03 rather than re-gated, with no line cited here because the close took both sections out; `docs/ISSUES.md` has it |
| `std497` vs `nonpcitems497`, the caravan slot | **`Shop Item` leaves `rules` and `locations` too**, not only the incentive pool: 227 locations to 224, and the six NPCs stay. So six of the seven are un-ringed checks and the seventh is not a check at all -- a different repair, and the one the pool heading hid until 2026-09-03 |
| `hoarddockbridge497`, pack rules vs FFR | **227 checked, 227 agree, 0 divergences** — it was 216 agree, 3 divergences over 11 locations |
| `hoardhike497`, pack rules vs FFR | **226 checked, 226 agree, 0 divergences** |
| `hoarddockhike497`, pack rules vs FFR | **224 checked, 224 agree, 0 divergences** — and 95 agree, 13 distinct divergences over 129 locations against the rules as they stood at `2b0ff32`, which is what this row exists to have caught |
| `std497` vs `dock497`, the Cardia islands | **unmoved at `(Canoe AND Floater)`. The Bahamut dock opens Bahamut's Cave and nothing else** |
| `std497` vs `hoard497`, chest placements | **map 39 (BahamutCaveB2) goes 0 -> 13 and no map loses one** (`tools/extract_chests.py`) |
| Bahamut's Cave's requirement, read through the hoard | **std `(Canoe AND Floater)`; +dock `(Canal AND Ship)` as well; +land bridge `(Canal AND Canoe AND Ship)` as well; +both `(Canal AND Ship)`, not the union; +hike `(Floater AND Ship)` as well** |
| +dock +hike together | **`(Canal AND Ship) OR (Floater AND Ship) OR (Canoe AND Floater)` — this pair *is* the union, unlike dock-and-land-bridge. "Not the union" is a result about that pair, not a rule about pairs** |

### Bahamut's Cave has no location of its own, and the hoard is the way in

**FFR's export never mentions Bahamut's Cave.** Bahamut hands out a class
change, which is not an Archipelago item, and the cave holds no chest on an
ordinary seed -- so on `std497` the whole node is absent from the yaml, absent
from the spoiler's source table, and absent from `check_logic`'s `FFR_SOURCES`.
Nothing in the corpus graded it, which is why the pack's own rule for it could
sit a flag behind its three Cardia siblings without a single figure moving.

**`MapDragonsHoard` is what makes it gradeable.** `SMUpdates.cs:534` writes the
thirteen Cardia chest tiles into `BahamutCaveB2` and then calls
`ItemLocations.CardiaN.ChangeMapLocation(MapLocation.BahamutCave2)`, so the
exported rule for every Cardia location becomes *Bahamut's Cave's* requirement.
Read those rows and you are reading the node the export otherwise hides.

**The relocation was confirmed rather than assumed, because on a plain seed the
two requirements coincide and prove nothing.** `dock497` is the control:
`MapBahamutCardiaDock` on and the hoard off leaves the Cardia islands at
`(Canoe AND Floater)`, because the dock serves Bahamut's Cave alone. Add the
hoard and the same locations gain `(Canal AND Ship)` -- so the rows really did
move, and the dock cartridge is what says so.

**The chests are duplicated, not moved, and that is the pack's side of it.**
`tools/extract_chests.py` across `std497` and `hoard497` puts map 39 at 0 -> 13
placements with no map losing any, matching the comment at `SMUpdates.cs:537`.
So with the hoard on, each of the thirteen is reachable from its island *or*
from Bahamut's Cave, and the pack's Cardia nodes carry a `BahamutHoard`
alternative for the second route. Only the alternative that adds something is
written: the airship, the hike and the land bridge already reach both places, so
the dock is the one route that needed spelling out. **The No-Overworld hoard
case is not measured** -- no such cartridge was built -- so that alternative is
guarded `$standardWorld` and claims nothing there.

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

`Shop Item` used to be the "1 could not be mapped" that every run on every
cartridge printed, because its ref matches both the dungeon tree and the
incentive poster and `find_section` refused rather than choosing. It resolves
the way PopTracker does now, so the line is gone: `std` reads 226 checked with
none unmapped. The pack's rule for it is still no rule at all, deliberately --
`docs/ISSUES.md` says why, and it is not a `ShipDrydock` defect.

Both check_logic runs print the "where ship, canal, canoe, floater were placed is
not recorded for this seed" caveat and are marked NOT COUNTED. That is the normal
condition for these cartridges -- the 4.9.2 runs behind the 225/225 and 229/229
figures print it too -- and the export diff above is the independent reading that
the 53 are not an artefact of it.

### Checking the 4.9.7 corpus

    O7=<corpus>/oracle-4.9.7
    for s in std drydock extended airship landbridge objnpc gaia gaiahwy \
             dock dockbridge hoard hoarddock hoardbridge hoarddockbridge hoardhike \
             hoarddockhike nonpcitems; do
        python3 tools/check_logic.py $O7/${s}497/${s}497.nes \
            --ap-rules $O7/${s}497/${s}497.yaml --ff1-world $W
    done

No `--derived` on any of them: the sweep derives No-Overworld rules and all eight
are standard seeds.

### Diffing the corpus, and what one flag apart does not hold still

`tools/export_diff.py` does by tool what the flag rows above were produced by
hand: roll two cartridges one flag apart, diff the exports, and the rules that
moved are that flag's doing.

    O7=<corpus>/oracle-4.9.7
    python3 tools/export_diff.py $O7/std497 $O7/dock497 --ff1-world $W

Either argument may be the cartridge's directory rather than the export, which
is what the one-cartridge-per-directory layout is for. Three answers like
`tofr_diff.py` -- 0 same, 1 differs, 2 incomparable -- and it refuses rather than
reporting a count when it cannot certify the pair is one seed, or when an export
cannot be read at all.

**The corpus README's "anything that moves between one of those exports and
`std497`'s is the flag and not the roll" is true of the rules and true of the
pool only by count.** FFR exports only the locations holding pool items, and
changing a flag moves the RNG stream, so which chests hold gold moves whether or
not the logic does. Measured against `std497` across the fifteen variants that
predate the tool — seven of them one flag from the baseline, the rest the pairs
and triples named above:

    variant             pool +   pool -   rules moved
    hoard497                17       20             0
    dock497                 21       22             1
    objnpc497               21       23             1
    dockbridge497           19       19            40
    airship497              17       19           124

All fifteen churn 17 to 23 locations in *both* directions, `hoard497` included,
whose rules do not move at all. So the pool difference is printed under its own
heading and is not counted: a differ that counted it would have reported a
finding for every flag in the corpus, including the one that found nothing.

**Not counted is not the same as "it is the roll", and the sixteenth cartridge
is why.** `nonpcitems497` is the only 4.9.7 export of the eighteen with no
`Shop Item` in it at all — `NPCItems` off deletes the caravan slot rather than
reassigning it — and that difference sat on line twenty of an uncounted list of
chests until it was looked for. Nothing distinguishes a removed location from a
reassigned one by counting, so the tool crosses the pool difference with
`priority_locations`, which is stable, and marks a name that left both:

    A only  Shop Item   -- and not in B's pool at all, so not a check on B

A pool-shape flag that moves plain chests — `ChestsKeyItems` is the one to
expect — is still past what two exports can settle, and the heading says so.

What is stable, and is therefore counted: the location ids, which never moved in
fifteen pairs and which `LOCATION_MAPPING` is keyed on, and
`priority_locations` -- the incentive pool -- identical across all fifteen.

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
  off each finished cartridge rather than trusting the preset. The remaining
  presets are `oracle497_std` with one or two values changed in the same way:
  `MapOpenProgressionExtended`, `MapAirshipHike`, `MapCardiaLandBridge`,
  `ShuffleObjectiveNPCs`, `MapBahamutCardiaDock` and `MapDragonsHoard`, plus the
  pairs the table names. `MapOpenProgressionExtended`, `MapAirshipHike` and
  `MapCardiaLandBridge` are keys the stock preset omits; the other three are
  present and `false`, so those are edits rather than additions.

Generating one of the newer three, for the record:

    O7=<corpus>/oracle-4.9.7
    dotnet FF1R/bin/Release/net10.0/FF1R.dll generate "<vanilla FF1 ROM>" \
        -j $O7/flags/oracle497_airship.json -s 3B7E1C8A \
        -o $O7/airship497/airship497.nes

`oracle497_nonpcitems` and `oracle497_nofetchitems` are each `oracle497_std`
with exactly one boolean flipped -- `NPCItems` and `NPCFetchItems` respectively,
both `true` in the stock preset, and `IncentivizeFreeNPCs` / `IncentivizeFetchNPCs`
left on, which is what makes each pair isolate a single conjunct.

## What the corpus holds constant, and why that is not "unmeasured"

Measured 2026-09-03. A flag every preset here sets the same way cannot be
graded by anything in this corpus, however many cartridges it grows. That is a
different state from a flag nobody has got to, and `LefeinSuperStore` is the
case that made the difference visible, because its coverage row asserted the
opposite and a reader following it would have rolled a seed the corpus already
had.

| question | answer |
|---|---|
| `LefeinSuperStore` across the 4.9.2 presets | **`true` in 4 of 4** — `oracle_std`, `oracle_nov`, `oracle_shard`, `oracle_notail` |
| across the 4.9.7 presets | **`true` in 18 of 18** |
| so the No-Overworld rules and the 75-link table were derived | **with the flag on**, which `docs/FLAG_COVERAGE.md` said was off |
| the cartridge's own tiles, `oracle_nov` | **all 10 cells the flag-on branch of `ApplyMapMods` writes hold what it writes; 0 of the 14 that only the flag-off branch touches do** |
| the three writes both branches share | **all 36 cells match, unflipped** — so `ApplyMapMods` ran and the `(x, y)` reading is right, which is what makes the answer above evidence rather than a miss |
| why those numbers are not 5, 4 and 3 | those are **statements**, and a `Map.Put` writes a row of cells rather than one. The flag-on branch is 5 statements over 10 cells, the flag-off branch 4 over 18 of which 14 are its alone, and the shared writes 3 over 36 (`MetroidVaniaMap.cs:235-277`). Counting statements understated the evidence by a factor of two to twelve, and left a row whose job is to make the `(x, y)` reading auditable stating a number a reader cannot re-derive from the map |
| what the flag-off branch would change | **`(x=0,y=2)` and `(x=1,y=2)` become tile `0x0E`, property `0x01`** — a plain wall where the corpus has `0x00` and walkable |
| where those two cells sit | on the left-edge column. **Not its mouth**, which is the correction below |

The coordinate convention is the trap worth writing down. `Map.Put` takes
`(x, y)` and the indexer is `[y, x]` (`FF1Lib/StandardMaps/Map.cs:170` and
`:13`), and `ApplyMapMods` opens by taking `maps.HorizontalFlippedMaps`, so a
flipped map would put every coordinate at `63-x`. Both readings were checked
against the three shared writes before any conclusion was drawn from the
conditional ones; Lefein is not flipped on `oracle_nov`.

The seed owed was **No-Overworld with `LefeinSuperStore` off**. It was rolled
on 2026-09-03 as `novnolefein`, and the next section is what it answered.

## `LefeinSuperStore` off: what it moves, which is not a link

Measured 2026-09-03 on `novnolefein`, rolled for this and nothing else —
`oracle_nov`'s preset at `oracle_nov`'s seed with one boolean flipped. The
cartridge is a clean control: decoding both gives **533 flags each and exactly
one differing**, and it is `LefeinSuperStore`. `GameMode 2` and `ToFRMode 2` are
read back off the cartridge, not off the preset.

| question | answer |
|---|---|
| does any link move | **no.** `entrance_graph.py` gives 32 doors identical, 157 staircases both, 54 of 61 maps reachable with every item both |
| does any derived rule move | **no.** Both cartridges derive **256 locations, 0 unreachable**, and the two sets have the same names |
| the 10 locations whose rule differs | all of them are the **per-seed rolled things `docs/NOVERWORLD.md` already names** — 8 are the Cardia/Bahamut gateway permutation (`Bahamut's Cave Bahamut` trades rules with the seven `Cardia Forest` entries) and 2 are the ToFR bonus chest ids (`ToFR Kary Floor 1` and `ToFR Lute Plate Room 1` trade) |
| does it grade differently against FFR | **no.** `check_logic --derived` gives **222 compared, 221 agree, 1 divergent**, and the divergence is the same deliberately-strict `Lefein` row `nov` has |
| why that is 222 where `nov` is 226 | **not four comparisons lost -- the two exports do not cover the same locations.** FFR exports only the locations holding pool items and this pair re-rolls the placement, so 227 joined rules on `nov` and 223 on `novnolefein` share **204 names**: 23 appear only on `nov`, 19 only on `novnolefein`, and 6 shared names carry different rule text, those 6 being the Cardia Forest gateway rows. The "no" is about the divergence's identity, not about the counts |
| Lefein's own tiles | **72 cells differ, and every one is a cell one of the two code paths writes** — 68 by `EnableLefeinSuperStore` (the 3×24 store blob at `(0x28, 0x01)`, and the tree cleared at `[0x00, 0x34]`), 4 by `ApplyMapMods`' two branches. Nothing else on the map moved. Each path's writes hold on its own cartridge: 36/36 shared and 10/10 flag-on-branch cells plus 70/70 store cells on `nov`, 14/14 off-branch-only cells on `novnolefein`, and **0 of those 14** hold the off value on `nov` |
| three other maps differ too | Gaia 20 cells, Waterfall 4, Castle Ordeals 2F 14 — **roll churn, not the flag**; see below |

**The flag does not seal the left-edge column; it moves the plug down a row.**
The premise this measurement was pointed at said `(0,2)` and `(1,2)` are the
mouth of a walkable column and asked whether sealing them moves a link. Reading
the column on both cartridges says the mouth is already shut on the flag-**on**
side:

    x=0..1   y=0    y=1    y=2    y=3..8   y=9
    nov      walk   WALL   walk   walk     WALL
    off      walk   walk   WALL   walk     WALL

So each cartridge has exactly one two-cell plug in that column, one row apart,
and the row between the two plugs changes which pocket it belongs to. Nothing
opens and nothing closes, which is why no link moves. A reader who took
"sealing" at face value would have gone looking for a lost connection.

**The roll diverges, and attributing the other three maps to the flag would be
the diff-shaped-evidence mistake.** The two spoilers differ by 795 lines: item
placement is re-rolled wholesale, so this pair holds the rules still and not the
pool, exactly as the 4.9.7 one-flag pairs do. None of the three routines that
wrote those cells reads `LefeinSuperStore` — Gaia's 20 are one
`PickRandom(rng)` replacement tile in `MoveGaiaItemShop`
(`StandardMaps/SMUpdates.cs:286`), Waterfall's 4 and Ordeals' 14 are
permutations of their own tiles. There is a path by which the flag reaches the
stream: `ApplyMapMods` runs at `MetroidVaniaMap.cs:58` and
`CreateTeleporters(..., rng)` at `:60`, and that derives its unused-tile pool
from what is on the maps (`:462`, `:22-44`). Which rng draw first differs was
not pinned and is deliberately not claimed here.

**One number in this file was tool drift, not the flag, and the stale file is
gone now.** The committed `nov/derived_nov.json` held 255 rules where a fresh
derivation of the same cartridge holds 256; the extra one is `Titan's Tunnel
Titan`, which the NPC location work added after that file was written.
Re-deriving `nov` before comparing is what kept that from being read as a
location the flag creates -- but leaving the stale file in the corpus left the
trap armed for the next reader, who would run the comparison the way this page
describes it and get a location only `novnolefein` appears to have. **Both
No-Overworld derivations were regenerated on 2026-09-03**, `nov` and `nov2`
alike, each gaining that one rule and changing no other; `nov` regrades
226 compared / 225 agree / 1 divergent and `nov2` 224 / 223 / 1, unmoved. This
also matters to `verify.sh` stage 3, which feeds `derived_nov.json` to
`check_logic` -- it was grading the pack against a derivation the tool no longer
produces.

### What the flag does on a standard cartridge

Measured 2026-09-03, because the entry above answers for No-Overworld and the
flag is not a No-Overworld flag. `EnableLefeinSuperStore` is called from
`Update()`, the general standard-maps pass (`SMUpdates.cs:116` at 4.9.7, `:39`
at 4.9.2), and only its last two `TownTree` writes sit behind `if (nooverworld)`
-- so the store blob and the tree clear land on either mode. That is now read
off cartridges rather than off the call site:

| question | answer |
|---|---|
| is the store on a standard cartridge | **yes, 72 of 72 blob cells on both `std` (4.9.2) and `std497` (4.9.7)**, with `[0x00, 0x34]` cleared to `0x00`, walkable, on both |
| did `ApplyMapMods` run on them | **no** — 3 of its 46 cells match by chance, against 46 of 46 on `nov`. The map edit is `EnableLefeinSuperStore`'s alone there |
| does it change what a party can reach in Lefein | **no pin's worth.** Walking `std`'s Lefein from the overworld arrival `(19, 23)` against the same map with the 73 written cells restored to their flag-off values, **all 14 objects on the map stay reachable at identical distances**, the Lefein man `$0F` at `(24, 21)` among them |
| what does change | the 4 shop doors the store adds (`TP_SPEC_DOOR`), and **one** tile outside the 73: `(52, 63)`, an exit tile the cleared tree reaches across the map's vertical wrap. Lefein carries **no `TP_SPEC_TREASURE` tile at all**, so there is no chest for any of this to gate |

The flag-off standard map is a reconstruction rather than a roll -- no cartridge
in either corpus has the flag off on standard mode -- and it is sound because
the base map is shared: `std` and `novnolefein` agree on Lefein everywhere
except the cells one of these two code paths writes, plus `[0x03, 0x00]` and
`[0x04, 0x00]` (`ApplyMapMods`' unconditional pair) and `(19, 21)`, the
staircase No-Overworld stamps into the town. None of those is in the store's
region, so `novnolefein`'s tiles there are what standard mode would hold with
the flag off.


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
is `Shard_Hunt.json`. `oracle_novnolefein` is `oracle_nov.json` with
`LefeinSuperStore` set `false` and nothing else -- the two files differ on that
line and the `Name`, and on nothing else.

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

`--ff1-world` no longer has to be passed, as of 2026-09-03: the default was
pointing one directory level short of the world and every location came back
unmapped, so a run without the flag mapped about 20 checks and reported a
cheerful zero. It resolves on its own now, and a path given explicitly and not
found refuses rather than reporting that zero. Passing it is still right when
the Archipelago checkout is somewhere else. `--ap-rules` is load-bearing for
the reason above. The
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
