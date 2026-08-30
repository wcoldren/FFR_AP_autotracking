# The oracle cartridges

The pack's logic is checked against FFR's own answer, not against a
transcription. FFR's Archipelago export carries a `rules:` section — the access
rules FFR hands Archipelago — and `tools/check_logic.py` compares that with the
pack's rules as truth tables. This file says which cartridge answers which
question, and how to rebuild any of them from nothing.

Four cartridges, all 4.9.2, all generated locally with `Spoilers` and
`Archipelago` on so the export is attached.

## Inventory

| Slug | Preset | Seed | Mode | Answers |
|---|---|---|---|---|
| `std` | `oracle_std` | `C189A0F0` | GameMode 0, ToFRMode 0 (Long) | the hand-written rules baseline |
| `nov` | `oracle_nov` | `F2585541` | GameMode 2, ToFRMode 2 (Short) | the derived No-Overworld rules |
| `nov2` | `oracle_nov` | `1D0BE11E` | GameMode 2, ToFRMode 2 (Short) | second seed at identical flags — the ToFR control |
| `shard` | `oracle_shard` | `5A4D0BAF` | GameMode 0, ShardHunt | `isShardHunt()` against a real export |

Modes are quoted as **read back off the cartridge**, never off the filename —
that trap has bitten more than once.

`nov` and `nov2` share a flag string by construction: the flag string encodes
flags, not the seed, which is what makes them a fair control for anything
seed-driven.

    std    omlInPoZ8aeRURUYlp1dof0D5xNDnrlGj9iV9YttYmO7Dv1Rmi6B0yqiIVR2PBvLS3STrugBTQeMv5wm1NR0AXzFFQUFmIyOlaB-i7D9BSRt.Lt4Snttst0yPEgyPIqf9Clw2RV-9AxD-qr33Lqb6rXFmyBvUxrD89pHBz3zAEWHH4FmWj
    nov    omlY4TDJ0WBi73FLBF5hW902l51xl72yHm32Rio0v38eGNM0fKy0TT8KJ-a0NWDQIIcxpvj7MlpYDG7gMaaVe-B1jhZllvTugQ53VEQHzfb-1wdKQG2Fnc64238l9e0jitE9LlbLND7XKw-ezMQ4exPzIyBvUxrD89pHBz3zAEWHH4FmWj
    nov2   (identical to nov)
    shard  omlInPoZ8aeCvsimCReMV9G4KHYm3TUYASJBGOBHlVOiR1kCNT91VO6GOxnA9GbEBb7YM1kQIzMfs8M3W7C8VP-aE5sJ0h2VYqBCNFMidFYuxFDg.QyWC6OgqMHtZPIrzXE9LlbLND7XKw-ezMQ4exPzIyBvUxrD89pHBz3zAEWHH4FmWj

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
| `nov`, pack rules vs FFR | **226 compared, 220 agree, 6 deliberately strict**; of the 226, **63 independently supported, 163 self-agreeing by construction** |
| `nov2`, pack rules vs FFR | **224 compared, 218 agree, 6 deliberately strict**; **69 independently supported, 155 self-agreeing** |
| `nov`, derived rules vs FFR | **222 compared, 222 agree, 0 divergent** — but **164 of the 222 had an off-vocabulary item granted free**, so **58** are genuinely comparable; 254 derived, 0 unreachable |
| `nov2`, derived rules vs FFR | **220 compared, 220 agree, 0 divergent** — **156 granted**, **64** genuinely comparable; 254 derived |
| `nov` vs `nov2`, ToFR shuffle | **0 differences** |

`std`'s 225/225 is the baseline to protect: it validates the harness end to end
against rules that were written by hand, and it must not move. `shard`'s 229/229
is the same kind of measurement for `isShardHunt()`.

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

Only the last three groups are independent of the transcription, and the sweep
contributes **nothing** to the compared set: the one rule taken from it,
Bahamut's Cave, is not in FFR's pool and is never compared. Counting a location
as independently supported when its gate is pre-existing, ungated, or
corroborated by the sweep gives **63 of 226**; the other 163 rest on the
transcription alone.

The **6 deliberately strict** are Cardia Forest, and they are not a defect. FFR
says `chime,floater,oxyale OR canoe` on `nov` and `floater` on `nov2` because
that gateway is rolled per seed; the pack ships one static rule, so it ships the
conjunction and is strict on both. A check shown red that is reachable beats a
check shown green that is not.

`nov2`'s counts are 224 and 220 rather than 226 and 222 because that seed's
export carries 225 locations rather than 227 — which pool a seed draws varies,
and the comparable set follows it.

Two waivers apply to every run against hand-written rules, and are not
divergences: Princess2 (the pack wants Garland beaten, FFR folds that in because
Garland is beatable from the start) and Lefein (the pack wants the Slab
translated, FFR counts holding it).

### What these figures do not cover

**The off-vocabulary grant, which is the big one.** `check_logic --derived`
hands every item the sweep cannot express — Oxyale, the Ruby, the Slab, the
Bottle — to *both* sides before comparing, so FFR reads as permissively as it
can and a surviving divergence cannot be blamed on the vocabulary gap. That is a
fair test, but a location where FFR's whole rule is granted away is not really
compared at all. Every `--derived` run prints the count and it was recorded
nowhere until now: **164 of `nov`'s 222, 156 of `nov2`'s 220.** The
concentration is one item — **oxyale x129 and ruby x32 on `nov`** — so quoting
"222 of 222 agree" describes 58 locations, not 222.

This is now known to be **fixable rather than inherent**, and that is a change
from how it has been filed. Oxyale and Ruby are not "game rules" the walk cannot
see: `FF1Lib/Sanity/SCMap.cs:167-186` gates five object ids by tile — RodPlate,
LutePlate, BlackOrb, SubEngineer and Titan — and the pack modelled two of the
five. BlackOrb was closed on 2026-08-30 (read per cartridge by
`entrance_graph.black_orb_item()`); SubEngineer and Titan remain, and they are
what the oxyale and ruby grants above are waiting on. They are ordinary blocking objects on
chokepoint tiles, no different in kind from the two plates already handled. The
genuinely non-graph requirements are the trades: Slab, Herb, Adamant, Bottle,
Crystal.

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

**The committed corpus artefacts are behind the numbers above.**
`derived_nov.json` and `derived_nov2.json` predate the NPC-location split, so
re-running `--derived` against them gives 254 derived and 222/220 compared where
this page once recorded 255 and 226/224. The larger figures came from a
regenerated set that was never committed, so they cannot be reproduced from the
corpus as it stands. The derived-rule rows above quote what the committed files
actually produce.

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

    python3 tools/tofr_diff.py $O/nov/oracle_nov.nes $O/nov2/oracle_nov2.nes

`--ff1-world` is load-bearing: without it only about 20 checks map and the run
reports a cheerful zero. `--ap-rules` is load-bearing for the reason above. The
`nov` derivation sweep is about 85 seconds; everything else is fast.

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
