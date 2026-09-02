# Where this pack is

The working log. What was built, why, and what each decision cost, kept as a
narrative so a thread can be picked up cold -- the reasoning that was tried and
rejected is here, which is the half no settled page has room for.

Opened 2026-09-01. The first build-out, 2026-08-18 to 2026-09-01, is in
[`STATUS.md`](STATUS.md), which is closed.

If you are looking for something specific it is probably not in here. This is
the log; the settled half lives in `docs/`, and `docs/README.md` says which page
owns what. To use the tracker rather than read about it, the root `README.md` is
the whole story.

## How this file works

- **New entries go at the end**, dated, with a heading that says what changed
  rather than what area it touched.
- **When an entry's conclusion settles, lift it into the page that owns it** and
  leave a pointer plus the part that only ever lives in a log: why it was
  written down, what it cost, and what it got wrong first. `docs/README.md` has
  the ownership map.
- **Say a thing changed on the day it changes.** Every stale claim this project
  has had to chase came from a line nothing re-read after it was written.
- **Quote a figure where it is the subject of the sentence, and point
  otherwise.** `docs/ORACLE.md` owns the cartridges and the grading figures.
- `tools/tests/test_docs.py` holds this file to its citations along with the
  rest of the prose, so a `path:line` that stops resolving fails a test rather
  than waiting to mislead someone.
- **Close this file and open the next when it stops being readable.** That is
  why `STATUS.md` ends where it does.

## Working today

- Two autotracking feeds, reconciled rather than merged: Archipelago over the
  wire, and a Mesen Lua bridge that mirrors `$6000-$62FF` over UAT. Either alone
  or both at once. `scripts/autotracking/reconcile.lua` takes the union and
  preserves hand clears.
- Chests, NPC and event flags, orbs, key items and every turn-in stage, vehicles,
  shard count, seed-swap detection, and a Resync button.
- A run clock drawn on the emulator's screen, counted in frames so it pauses
  when emulation does, kept per cartridge across a power cycle.
- The flags grid configures itself from the FFR flag string stamped in the ROM.
  Schemas ship for FFR 4-9-7 and 4-9-2; a seed on any other version lights the
  unread-flags warning in the grid rather than letting the defaults pass as the
  seed's own settings.
- A Bosses row for the five fights that have a real signal: Garland, the
  Vampire, Astos, Bikke and Chaos.
- Both overworld tabs show every slot there is. A slot the seed did not
  incentivize reports `AccessibilityLevel.Inspect` and draws blue instead of
  having its pin dropped, and a slot the seed did incentivize gets a gold
  `Highlight.Priority` ring on both tabs. Green still means reachable and red
  still means not: Inspect only sets `inspectOnly`, so a slot that is both
  skipped and out of logic comes out red.
- An `Overworld Tab` item that cycles Auto / Incentive / Full. Auto reads the
  Archipelago pool where there is one and the cartridge otherwise — `ShardHunt`
  or `ChestsKeyItems` and it lands on the full map. A bridge-only shard hunt
  used to land on the incentive map, which hid nearly every check it had.
- The Chaos kill read out of the battle engine — a battle running (`$60FC`),
  Chaos's formation in `btlformation` (`$6A`), `btl_result` (`$6B86`) set to
  `$FF` — rather than off `$62FE` bit 0x02, which FFR only writes on an
  Archipelago seed. It is the same instant the Archipelago patch sets its bit,
  so no seed's split moved. Feeds the run clock, the `chaos`/`clock` lines in
  `ffr_times.log`, and `ff1/goal`, which the pack now reads for
  `LOCATION_MAPPING[766]`.
- Map tabs follow the player. On the shipped hand-drawn art, 36 of 53 dungeon
  maps are calibrated and carry per-chest markers; on art redrawn from a
  cartridge, all 61 do, because those markers are built from the ROM's own
  chest tiles rather than moved from a hand-solved pixel.
- Redrawn maps are cropped to the part of each floor that is actually map and
  filed by the cartridge's game mode, so a standard tracker and a No-Overworld
  one each show their own set. `tools/regen_maps.py` keeps both in one override
  tree.
- Offline tools that read a cartridge directly: the flag decoder, an
  entrance/floor shuffle reader and router, an HTML door map, an overworld
  reachability walk, a map renderer that can draw the NPCs standing on a map,
  and a logic checker that diffs the pack's access rules against FFR's own
  spoiler. The map-reading half of that was wrong until
  2026-08-29 — see `STATUS.md`,
  "Read the maps from the bank FFR actually puts them in".
- The door map is walkable by clicking. Every floor name on the page is a
  `#map-<id>` link, and a focus panel driven by `hashchange` lists that floor's
  ways in and staircases on, so you follow the shuffle a room at a time instead
  of scrolling two tables; Back retraces. Works the same on a No-Overworld
  cartridge, which is the point — the mode shuffles through the same teleport
  tables the page already reads.
- An all-items reachability oracle in `entrance_graph.py --self-check`: holding
  every item, all 61 maps must be reachable from the doors. A theorem on
  No-Overworld and only there, since `MetroidVaniaMap.cs` connects all 61 and
  drops none, so a map the walk cannot find is the tool's own fault. It is the
  cheapest test of the whole routing stack -- map decompression, tile
  properties, both teleport tables, the doors and the gates all have to be right
  at once. Written down after the bank bug and never run until now -- and it
  earned itself immediately, by failing on its own stated invariant. See
  `STATUS.md`, "The gauntlet the mode skips".
- `tests/run.sh` — 14 Lua suites, no emulator or ROM needed. `tools/tests/run.sh`
  — the cartridge-reading tools' own tests, Python and nothing else; the ones
  that need a cartridge skip unless `FF1_ROM` points at one.
- `tools/regen_maps.py --verify` — not part of either suite, because it asks
  about this machine's PopTracker install rather than about the code. Run it
  when the tracker looks wrong: it says whether the installed override predates
  the checkout, which is a failure with no visible symptom. `docs/ISSUES.md`.

## The Cardia pins, and a combination the corpus did not have

Closed 2026-09-01. Reported off `8EF791AA` played bridge-only: the Cardia chest
pins were red while the Hoard was reachable. The defect was real and had already
been fixed fourteen hours before it was looked at -- `52ba9d5`, `9d55246` and
`15ac915` landed at 12:03 on 09-01, and the session that saw it was running
`2b0ff32` from 20:17 the night before. `docs/ISSUES.md` carries the close.

What is worth keeping is not the fix.

**The first three things checked were all the wrong thing, and each was cheap.**
The decoder returned a real table, `MapDragonsHoard` came back on,
`cardiaIsIncentive` reached stage 2, and `ProviderCountForCode("BahamutHoard")`
was 1 -- the board had always had the code. Five of the six terms of the
alternative were satisfied and `canal` was the only one that was not, which read
like an answer and was not one: the rule that wanted `canal` was on a node whose
siblings had three other routes, and it was the *absence* of those on the Cardia
side that made the colour. Evaluating one alternative term by term says which
term failed; it cannot say which alternative should have been there instead.

**The state at the time was not recorded and did not need to be.** No save, and
`ffr_times.log` carries only `start`, `clock` and `chaos` lines, so what was held
is gone. Both states the report is consistent with -- Canal and Ship, or Floater
and Ship -- were replayed against the rules as played and as they stand, and both
reproduce the report on the old rules and come out green on the new. Two
candidate states beat one recovered state, because the answer holds for either.

**The corpus had each flag and not the combination.** `hoarddock497` and
`hoardhike497` had a cartridge each; `MapDragonsHoard`, `MapBahamutCardiaDock`
and `MapAirshipHike` together had none, and that is what a real seed rolled.
`hoarddockhike497` is now the row, and it grades the rules that were being played
at 95 of 224 -- a gate that demonstrates the failure it was added for, rather than
one added after the fact that can only report a pass.

The pair also turns out to be the plain union of the two flags,
`(Canal AND Ship) OR (Floater AND Ship) OR (Canoe AND Floater)`. That is worth
saying only because `hoarddockbridge497` established that a pair *can* fail to be
the union, and one counter-example is enough to make "not the union" a result
about that pair rather than a rule about pairs.
