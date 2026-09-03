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
been fixed by the time it was looked at -- `73337dc` landed at 09:42 on 09-01 and
`15ac915` at 12:04, and the session that saw it was running `2b0ff32` from 20:17
the night before. `docs/ISSUES.md` carries the close, and which commit closes
which half of it.

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
well short of the current ones (`docs/ORACLE.md`) -- a gate that demonstrates the
failure it was added for, rather than one added after the fact that can only
report a pass.

The pair also turns out to be the plain union of the two flags,
`(Canal AND Ship) OR (Floater AND Ship) OR (Canoe AND Floater)`. That is worth
saying only because `hoarddockbridge497` established that a pair *can* fail to be
the union, and one counter-example is enough to make "not the union" a result
about that pair rather than a rule about pairs.


## A regen bakes in the branch you are standing on

Landed 2026-09-02. `start_session.sh` redraws the map art when the art on disk
was drawn from another cartridge, and a redraw is not only art: `regen_maps.py`
rebuilds the four location trees and `layouts/shared.json` from the working tree
and writes them into the override, which PopTracker serves ahead of the pack. So
the branch checked out at regen time decides what the session then plays on, and
nothing about the art on disk records which branch that was.

The rule already existed as a habit -- check the branch before any regen that
will be played on -- earned when a regen from a branch without the toggle work
wrote four location trees with zero pin rules into the override and would have
dropped the Pins group at the next restart. A habit is the thing this pack keeps
catching itself failing at, so it is code now.

**The fingerprint that looks like it already covers this does not.** The cache
carries `inputs`, a sha256 over `INPUT_FILES`, which lists all four location
trees and `layouts/shared.json`, so it moves on exactly this edit. But it moves
the same distance in both directions. `inputs` differing is what makes the regen
*happen*; it has no opinion about whether the change was the work landing or the
work missing, and on the run that caused this it said "the pack or these tools
changed" and redrew.

So the branch is recorded rather than derived. `checkout_id()` writes `branch`,
`head` and `dirty` into a mode's cache slot at the moment that mode's art is
written, and `regen_ok` compares before the next redraw. Recorded only where art
is actually written: the "up to date, fill in the missing identity" path
backfills `sha1` and `ffr` because `rom` proves the cartridge in hand is the one
the art came from, and nothing on that path proves a branch.

**Three answers, and the two that are not a mismatch were most of the work.** A
detached head has a commit and no branch; a checkout with no git has neither;
art drawn before this landed has no branch recorded at all. All three read as
"cannot tell", redraw, and say that is what happened. The alternative -- fire on
the absence -- makes the guard's first week a wall of false alarms on every
override already installed, and what people learn in that week is
`FF1_REGEN_ANYWAY=1`.

`head` and `dirty` are recorded and not compared, which is worth saying out loud
because this pack treats a field nothing reads as dead code. They are
provenance, the role `sha1` and `ffr` already play for the cartridge: what this
art was built from, answerable after the fact. `dirty` covers `INPUT_FILES`
rather than the whole tree, because an edit to a note or a doc moves no drawn
byte, and a guard that mentions one teaches its reader to skim.

The demonstration is the same call twice, in `tools/tests/test_regen_branch.py`:
on the matching branch it redraws and counts nothing, on a mismatch it skips step
1 and counts a problem. It skips rather than aborting, so the emulator and the
tracker still open on the art already on disk -- no other failure in that script
aborts either. The guard is sliced out of `start_session.sh` rather than restated
in the test, so rewording the message is free and changing the predicate is not.

Still true and not addressed here: nothing tracked in the repo describes
`start_session.sh` at all. It arrived undocumented outside its own header
comment, and `docs/README.md`'s ownership map has no row that would hold it.

## Titan gets a cell, by freeing the name rather than working around it

Landed 2026-09-02. He was the last of the six unpinned NPCs with a real signal:
`$6214` says he has been fed, and the pack was already reading that byte as
`ruby` stage 1. What stood in the way was a name. `titan` was the second code on
that stage, so a Locations section could not host it -- `FindObjectForCode`
would have handed back the Ruby, the box would have read as cleared whenever the
Ruby was spent, and it could never have been clicked on its own.

**The roadmap asked for a fresh hosted code, and that was the wrong shape.** A
new name like `titanFed` looks free and is not: the NPC-pin join is keyed on the
hosted code *being* what `extract_npcs.WANTED` calls object `$14`, and three
tools do that join independently -- `regen_maps.py`, `noverworld_rules.py`,
`pin_visibility.py`. A section hosting anything else gets no pin, no object-gate
id and no `npc` classification, and gets them silently, which is the failure
`STATUS.md` already records under renaming a `hosted_item`: the report went from
29 slots to 28 and passed. Freeing the name costs one rename and teaches nothing
to anybody. No access rule ever asked for that second code -- they all ask for
`ruby`, which both stages provide -- so `Ruby` stage 2 carries `rubyDone` now,
on the pattern the Slab already set with `slabDone`.

`$6214` is then read twice, once as `ruby` stage 1 and once as `titan`, which is
exactly what `sigil` and `mark` do to the Floater and the Canoe and for the same
reason: the code with the rule is not the code with the box.

**The scoping question was answered by the wrong measurement first.** Asked
where the Titan gate actually bites, the quick answer was a link-level diff --
hold every item, withhold the Ruby, count the map links lost. That says two
links on a No-Overworld cartridge and zero on a standard one, three nov and two
std cartridges agreeing, and it reads as "this only matters in No-Overworld". It
is the wrong test: a chest *inside* Titan's Tunnel is not a map link and cannot
show up in that diff at all. Every access rule on Titan's Trove -- both trees,
all five alternatives, standard included -- already requires `ruby`, and
`tests/test_ram.lua` had written down years-equivalent of the same fact in a
comment: "Both Titan's Trove and Sarda's Cave gate on the bare `ruby` code." So
on a seed that incentivized the Trove, the slot behind him is a key item on
either mode, and the cell belongs in both trees.

The generalisation is the one this pack keeps relearning in new clothes: a diff
answers the question its own units can express. Links were the unit, so links
were the answer, and the thing actually asked about was checks.

**The pin is not hand-authored, and an early draft of it was wrong twice over.**
`place_locations` builds a dungeon marker for any node that resolves to a tile,
so the `titans` pin comes off the cartridge like every other NPC pin -- that is
the whole payoff of hosting the literal `titan`. The draft also carried an
overworld marker copied from Titan's Trove, which would have put a second pin on
exactly `(400, 1950)`, on top of the Trove's own. Dropping it left
`test_pins.lua`'s four drawn-pin counters untouched, which is the right outcome:
this node gains no hand-drawn marker.

Counters that did move, both of them re-derived rather than adjusted until
green: the NPC nodes that join go 14 to 15 on an FFR cartridge and 13 to 14 on a
vanilla one, and the unpinned list goes from six to five.

## The shop slot takes the flag FFR computes for it

Landed 2026-09-03. Every incentive slot but this one carried
`^$incentiveSlot|<flag>`, so the board could grey a slot the seed never
incentivized. `shopItem` carried nothing, and the reason it carried nothing was
a search that came back empty: there is no `IncentivizeShopItem` in either flag
schema, and that absence was reported as FFR's answer.

FFR computes it instead. `FlagsCompute.cs:217` gives `IncentivizeCaravan` as
`(NPCItems ?? false) && (IncentivizeFreeNPCs ?? false)`, and
`PlacementContext.cs:198` puts `ItemLocations.CaravanItemShop1` into the
incentive pool on it. `IncentivizeFreeNPCs` is what this pack has always called
`npcsAreIncentive`, and FFR's own label for it -- "Main NPCs" -- was sitting in
`flag_mapping.lua`'s header comment the whole time. **An absence in a derived
index is not an absence in the source**, and the source was three greps into a
clone that is already vendored here.

**The build turned up something the finding had not.** Every other slot
contributes two rows to the generated table, a sheet path and a board path.
This one contributes a single row, because the board's node for the slot is
itself named `I: Shop Item` -- the only board node wearing the sheet's prefix --
so `@I: Shop Item/I: Shop Item` is both paths at once and the second is deduped
away. That is not a new ambiguity: it is the collision `check_logic.find_section`
already resolves board-first. The rule that settles it is not the one first
written down here: `Tracker::getLocationAndSection` splits a ref at its *last*
slash, so what PopTracker looks up is the bare node name `I: Shop Item`, and
with no slash left in it `Tracker::getLocation` compares names and never reaches
the id-suffix branch. Load order does the rest, `init.lua` taking
`overworld.json` first. Suffix and name-equality agree on this pin, which is why
the wrong justification read as verified; they part company as soon as a board
node's id ends with a name it is not itself named for. So the
row reaches the board's section. What the sheet's section loses is the gold ring
and nothing else -- its access rule and its pin rule are evaluated directly by
PopTracker and never go through `FindObjectForCode`.

**Six counters moved and the guess about them was wrong in both directions.**
The prediction named four and expected the NPC classifications to move; what
actually moved was six, and `npcs` was not among them. Sections reporting
Inspect went 49 to 51, generated rows 55 to 56, sheet pins with a rule 17 to 18
and 20 to 21, and pins drawn with the flag off 9 to 8 and 8 to 7. That last pair
is the demonstration the gate asks for rather than a number that merely moved:
with `npcsAreIncentive` absent the pin was drawn before and is not drawn now,
and the diff reaches only the two `shopItem` blocks, so it is that pin.

`pin_visibility.py` stamps the same pin rule that was added by hand, and "the
stamped copy equals the committed tree" still passes -- so the rule is the
tool's own output rather than a transcription anybody has to trust.

The residue stays separate and is worth restating because conflating the two is
what let this close wrongly the first time. The slot's **incentive status** is a
flag. The slot's **content** is the roll: `ItemPlacement.SelectVendorItem` falls
back to a consumable when no eligible incentive item is left, which is why
roughly half of solo seeds hold nothing worth hunting there even with the flag
on. And the pin still clears itself, off PRG ROM on a solo seed and off flag
byte `0xFF` on an Archipelago one.

## check_logic was pointing one directory short of the world

Landed 2026-09-03, on the same branch because it is what would have graded the
change above. `ap_location_paths` defaulted to `<pack>/../Archipelago/worlds/ff1`.
The pack sits at `vendor/ff1/<pack>`, so `..` is `vendor/ff1` and that path has
never existed; the world is one level further up. The miss hit `return {}`,
every location reported unmapped, and the run finished with a zero.

A zero is the worst possible way for this tool to fail, because a zero here
reads as agreement rather than as an unanswered question. `docs/ORACLE.md` had
been carrying the symptom as a workaround -- "`--ff1-world` is load-bearing:
without it only about 20 checks map and the run reports a cheerful zero" --
which is a sentence that names the failure precisely and was quoted for long
enough to become procedure. The cause was four lines from the words describing
it.

The default resolves 255 locations now. A `--ff1-world` given explicitly and not
found refuses; the default being absent is still a skip, deliberately, because a
machine with no Archipelago checkout is an ordinary condition and a flag that
names nothing is a typo. `verify.sh` passes `--world` explicitly, which is why
the gate never saw any of this -- it was ad-hoc runs that were lying.
