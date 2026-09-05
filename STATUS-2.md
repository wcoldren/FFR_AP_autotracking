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

## One flag apart does not hold the pool still

Landed 2026-09-03. `tools/export_diff.py` is the tool the fifteen 4.9.7 flag
rows were produced without: roll two cartridges one flag apart, diff the
exports, and what moved is the flag's doing. `docs/ORACLE.md` has the invocation
and the figures; `docs/ROADMAP.md` section 5 has the close.

**The scope was one assumption short, and it was the corpus's own sentence.**
The 4.9.7 README says "anything that moves between one of those exports and
`std497`'s is the flag and not the roll", and that reads like a licence to diff
everything in the file and call all of it the flag. It is true of the rules and
true of the pool only by count -- which is not the same as "the pool is the
roll", and the section below is where that difference got paid for. FFR exports only the locations holding pool items, and a flag
change moves the RNG stream, so which chests hold gold moves whether or not the
logic did. All fifteen variants churn 17 to 23 locations in *both* directions
against the baseline.

The measurement that settles it is `hoard497`: 17 locations gained, 20 lost,
**zero rules moved**. A differ that counted pool membership would have reported
a finding for every flag in the corpus, including the one flag whose export says
plainly that it changed nothing. That is the failure worth naming, because it is
not a wrong number — it is fifteen confident answers, one per flag, all of them
the roll. The tool prints the pool difference under its own heading, says what
it is, and does not count it.

**What is counted was checked for the same fault rather than assumed safe.**
Location ids never moved across the fifteen, and `LOCATION_MAPPING` is keyed on
them, so a name that keeps its place and changes its id would be read as a
different location by everything downstream — a row of its own even though
nothing has tripped it. `priority_locations` was identical across all fifteen,
so the incentive pool is signal and not roll, which is what makes it the place a
computed flag like `IncentivizeCaravan` shows up.

**Absence and emptiness are kept apart in three places**, all the same failure
in different clothes. An export that cannot be read exits 2 rather than
inheriting `parse_ap_rules`'s empty dict and reporting "no changes" for a file
it never opened — the `ap_location_paths` cheerful zero, one function along, and
it was written down in the roadmap before it could be built wrong. A pair whose
seeds cannot both be named is incomparable rather than agreement, because
attribution is only sound at one seed. And a section the other export shape does
not carry is reported as not compared rather than as everything removed: an
Archipelago spoiler has rules and no `priority_locations`, and "21 incentive
locations removed" would be a finding invented out of a file format.

**The test earns its rows by being broken on purpose.** Three mutations, each
turning exactly the intended rows red: compare nothing and the rule rows fail;
make the comparison order-sensitive and the reordered-rule row fails; count the
pool churn and the row that says churn alone is zero fails. Sixteen green rows
prove nothing on their own, which this pack has already recorded about
`test_maps.lua` check 6 — a check that compares a file to itself cannot fail for
any reason.

Still true and not addressed here: the corpus README's sentence is unqualified
where it sits, in `seeds/ff1/oracle-4.9.7/README.md`, which is in the workspace
repo rather than this one.

## The first use of the diff found a defect, one conjunct along

Landed 2026-09-03, the same day as the tool. `NPCItems` was the measurement
`docs/FLAG_COVERAGE.md` had been asking for by name, and it needed one cartridge
rather than the two the roadmap said: `std497` already carries the flag on, so it
is the control and only `nonpcitems497` had to be rolled.

**The answer is clean and it is not the one the row expected.** Zero exported
rules move -- `NPCItems` touches no reachability at all, which the row had
guessed at with "n/a for reachability" and now has measured. Seven
`priority_locations` go: King, Princess, Bikke, Sarda, Canoe Sage, CubeBot and
Shop Item, with `IncentivizeFreeNPCs` still on. That is `IncentivizeCaravan`
losing its other conjunct, demonstrated on a cartridge rather than read off
`FlagsCompute.cs:217`.

**And those seven are exactly the seven the pack rings.** All seven rows in
`scripts/incentive_slots.lua` carry `npcsAreIncentive`, which is
`IncentivizeFreeNPCs` alone; no `npcItems` code exists anywhere in the pack. So
on that seed FFR incentivizes none of the seven and the board rings all seven
gold. `docs/ISSUES.md` has the entry and `docs/ROADMAP.md` section 1 has the
build.

**It is the shop-slot mistake in the other direction, and that is the part worth
keeping.** That one read a flag's absence from a schema as FFR having no such
flag. This one modelled a computed flag by whichever conjunct the pack already
had a name for -- `npcsAreIncentive` was there, `npcItems` was not, and the
conjunction quietly became the term that had a code. The `flag-coverage` review
had already written the general form of this down about a coverage row: a
conjunction that comes out false demonstrates neither conjunct. It was recorded
as a lesson about a test row and not carried across to a rule.

The cartridge exists before the fix does, which is the order section 1 asks for:
the gate row can show the ring the flag was wrong about rather than report a
pass after the fact.


## The pool heading was hiding a flag, which is what a review is for

Landed 2026-09-03, same day, off `/code-review` on the branch. The tool was
right not to count the pool difference and wrong about why, and the sentence it
was wrong in is one it had just corrected somebody else's version of.

**The evidence supported a noise floor and the claim made was a verdict.**
Fifteen variants churn 17 to 23 locations either way, so a *count* of pool
differences attributes nothing -- that much is measured. "The pool is the roll"
is a different sentence, and nothing in the corpus supported it, because until
`nonpcitems497` the corpus held no flag whose effect is the pool's shape. The
sixteenth cartridge held one. `NPCItems` off deletes the caravan slot: of the
seventeen 4.9.7 exports, `nonpcitems497` is the only one with no `Shop Item` in
it at all. That difference was printed on line twenty of an uncounted list under
a heading that said it was gold moving between chests.

**The fix is a cross-check, not a count.** Nothing separates a removed location
from a reassigned one by counting, so the tool does not try. It crosses the pool
difference with `priority_locations` -- the one set measured stable across the
fifteen -- and marks a name that left both:

    A only  Shop Item   -- and not in B's pool at all, so not a check on B

A pool-shape flag that moves plain chests is still past what two exports settle;
`ChestsKeyItems` is the one to expect, and the heading now says so rather than
implying the opposite.

**And the `NPCItems` finding was one repair short.** Six of the seven slots are
a wrong ring -- the NPCs stay checks and lose their gold. The seventh is not a
check at all on that seed, and all four location files show it anyway: the two
`incentives.json` gate it on `npcsAreIncentive`, the two `overworld.json` gate
it on nothing. Reading `PlacementContext.cs:243` would have got this wrong in
both directions -- it forces vanilla placements on the six NPCs and the vendor
slot alike, and the export keeps the six and drops the vendor. Which of the
seven Archipelago still calls a location is a thing only the export says.

**Four smaller ones from the same review, all now closed.** Schema-only flags
were computed and then dropped whenever the shared flags all matched, which is
the cross-version case the version note exists for. `read()` took the first
scope with a `rules` key while `parse_ap_rules` requires a non-empty one, so a
blob with two game scopes would have compared one game's locations against
another's logic. The docstring claimed Archipelago yamls and spoilers were
readable when the seed gate refuses every one of them, and now says FFR's export
and why. And "all fifteen one-flag variants" was seven one-flag variants and
eight pairs and triples, contradicting the same page two paragraphs up.

**The tests grew the rows that would have caught them, and the seeded ones the
file had none of.** Every row above was hand-built, so nothing exercised the
reading -- not the permalink, not the nested scope, not the flag decode. Five
rows now run against the corpus and skip without it, on `test_shop_slot.py`'s
`FF1_SEEDS` pattern. Three mutations, each turning exactly its own rows red:
drop the caravan cross-check and the row that names it fails; restore the
schema-only suppression and two fail; weaken the scope test and the two-scope
row fails.


## The route lanes are named for what they are, and a person draws them now

Landed 2026-09-03. `--lanes` was off by default and `ROADMAP.md` said why: a
solver cannot know which chests are worth the detour on a given seed. What
shipped was also named wrong, which mattered more than it sounds, because an
editor authoring into the wrong vocabulary would have had to be re-authored.
Both went in together.

**The naming was one loot round drawn in two halves.** Cyan was the keyless
walk, purple what the key bought. The reference's pair is a traversal route and
a loot route, and "for loot" already implies the key -- so the genuinely useful
lane, the walk through a floor opening nothing, did not exist anywhere. The fix
was not a rename: `plan()` now builds one `Floor` holding the floor's items and
routes the first lane arrival-to-nearest-exit with no errand at all, one
`path()` call rather than a tour. The keyless `Floor` is gone; it only ever
existed to derive the second lane by difference.

The one-inventory consequence is worth stating because it looks like a lost
check. The route lane may now walk through a door the floor's own key opens.
That is deliberate: holding an item only widens the walkable set, so the
traversal is never longer or less safe for it, and `arrivals()` already filtered
on the full inventory -- which is why the old code needed a keyless-walkability
guard on the start tile that has now simply gone away, along with the
No-Overworld ConeriaCastle1F `(2, 8)` case it was written for.

**What it cost, measured rather than expected.** A loot lane appears wherever
there is loot rather than only on a gated floor, so 29 of the 39 lanes on the
duck cartridge became a pair and 28 maps grew a legend row -- the first regen
after this redraws every image, which is the change working and not a bug. And
`ISSUES.md` gained a font-scale entry: three maps per cartridge now draw their
Map Key at half size because the longest row is 22 characters.

**The editor is a layered shortest path, not a tour, and that is the whole
reason it is cheap.** The author supplies the order, so `lane.walk` runs one
layer per stop over the candidate tiles each stop could be satisfied at --
one Dijkstra per distinct candidate where `Floor.lane` costs `2**n`. It is
still exact: taking the nearest candidate at each step commits to a standing
tile the next leg pays for, which is the defect nearest-neighbour had in the
tour, one dimension down.

**A stop says what it is, not where it is**, so an authored lane can outlive
the cartridge it was drawn on. The hint the editor recorded is used where it
still holds -- so redrawing on the seed it was drawn for gives back exactly the
lane that was drawn -- and falls back to the stop's meaning where it does not.
Arrivals need that most: the tiles the game can put you down on are the
destinations of whatever teleports point at the floor, and a shuffle repoints
them even when the floor is untouched. Exits are teleport tiles of the map
itself, so they are as stable as the digest.

**Three outcomes, not two, and that is the thing this got right by writing it
down first.** No lane file is ordinary. A file whose layout this cartridge does
not have is also ordinary -- it is a seed having re-laid a floor. Only a layout
that does match, whose stops will not resolve, is a defect, and that one stops
the run and writes nothing. Collapsing the first two into "failed" would have
made a No-Overworld regen a wall of red; collapsing the last into "skipped"
would have drawn a lane through rock.

**Two things were got wrong first.** The refusal was handed to `report()`,
which formats a marker as "name on map at x,y" and raised `ValueError` on a
`(map, why)` pair -- a crash that exits 1 and prints a traceback, which from
the outside is indistinguishable from the refusal working. And the lane files
needed a cache key of their own: `inputs_fingerprint` hashes `INPUT_FILES`, so
without one, editing a lane and re-running printed "nothing to do" over art
drawn from the old stops. Globbing them into `INPUT_FILES` would have been
worse -- it moves the fingerprint for every cartridge including `--lanes none`
runs, which these files have no bearing on.

**A latent drawing bug came out with it.** `draw_lanes` subtracts a region's
route lane from its loot lane so a shared corridor draws one line, and it found
the pair by position. Position cannot tell `[routeA, lootB]` from
`[routeA, lootA]`, and the first became reachable here, because a region whose
only way out is the way it came in gets no route run at all. On that shape the
second region's whole lane is erased. Not on either duck cartridge today, but
both halves of the shape are, so `Run` gained a region index.

**No lane has been authored yet.** The tool is the deliverable; which chests are
worth the detour is a judgement pass that wants a person and a seed in front of
them, and `tools/lanes/` is empty on purpose rather than seeded with the
solver's answer wearing an author's hat.


## Whether a floor should retrace is 24 questions, and the numbers hid three

`--retrace` landed as one switch over 57 files, off, with the reason recorded
as a judgement rather than a defect: on a floor that genuinely loops, one line
with arrows both ways reads as "walk this twice" when what is true is "there is
a way round". A switch cannot hold that answer, because the answer is different
per floor. So it moved onto the layout entry -- `retrace` beside `digest` and
`lanes` in `tools/lanes/<map>.json` -- and the flag became the override:
`--retrace {auto,on,off}`, `auto` by default, a bare `--retrace` still meaning
`on` so that every figure ever measured against it still means what it said.

**Written only when true.** `false` on every entry would be 57 lines of no
information, and worse, it would make a floor nobody has looked at
indistinguishable from one that was looked at and left alone -- which is
exactly the distinction the pass ahead produces.

**The triage measurement is what changed the design, and it did it twice.** The
first pass counted loops: 72 over the whole set, 23 retraced, on 21 maps. The
note being worked from said 24. Both are right. ConeriaTown, MarshCaveB3 and
SeaShrineB1 are *redrawn* without their loop count moving, and a map rail built
on the counts would have marked those three as untouched and sent the pass
straight past them. So the rail asks whether the drawn *edges* differ and shows
the count only as a label. A full regen either way confirms it: exactly 24 of
the 61 images change, and `--retrace auto` with nothing marked is byte-identical
to `--retrace off`.

**A checkbox that re-bakes is the wrong instrument for this.** The difference on
most of the 24 is one corridor, and a bake takes about a second -- long enough
to lose what you were comparing against. `Preview A/B` fetches both renders,
holds them as object URLs, and swaps `img.src` between two images the browser
has already decoded, so the change happens in front of you. A is always retrace
off and B always on, fixed and independent of the checkbox, because a caption
that could not name what was on screen would be worse than no caption.

**And the flip must not be a keypress alone, which is how it was built first.**
Space was the only way to swap, and space is the one key that cannot work when
it is wanted: clicking `retrace this floor` leaves focus in the checkbox, where
space is the browser's own toggle. So the first thing a person does on a floor
disarmed the flip *and* silently unticked the box they had just ticked -- which
presents as "I click the box and A/B and see no difference", with nothing on
the page suggesting otherwise. There are now three ways in and none of them is
required to be the keyboard: an A|B control in the caption, a click anywhere on
the map, and the key. The checkbox hands focus back on change so the key keeps
working. Each path has its own test row, named rather than counted -- the first
version of that test counted flip call sites and stayed green when the
map-click path was deleted.

**`loops()` folds the components term away, which is an argument and not an
identity.** The circuit rank is `|E| - |V| + |components|`, and a walk is
consecutive, so its line is one piece and that term is always 1. A repeated
tile drops an edge without breaking the chain. `test_lane.py` runs the
long-hand version -- components actually walked -- over every drawn lane on the
corpus against the folded one, so the argument is checked rather than trusted.

**The live canvas deliberately does not retrace.** `/path` runs per drag and a
growing prefer set invalidates `Floor.search`'s memo, which is one Dijkstra per
leg instead of per lane. The judgement is about the baked art and the baked
preview is where it gets made.

**Nothing has been judged yet** at the commit that carries the mechanism. The
pass is 24 floors and a person, and it wants its own commit -- the 57 authored
files are the irreplaceable part of this branch and a mechanism commit should
not be carrying data edits.


## Seventeen of the twenty-four collapse, and the towns are the seven that do not

The judgement pass, made floor by floor on the A/B flip. 17 of the 24 redrawn
floors carry `retrace: true`; the loop count across the set as it now bakes is
30, against 72 unretraced and the 23 it would be with every floor forced on.

The seven left alone are not a gap, and five of them are one answer: `elfland`,
`elf_castle`, `melmond`, `onrac` and `pravoka` are towns, and a town is where
"there is a way round" is the true thing to draw. Collapsing those would have
the map say walk this twice about the one kind of floor a player circles
freely. That is the case docs/ISSUES.md described in the abstract, met in the
particular.

The other two are `marshB3` and `seaB1`, of the three floors whose drawing
changes without the loop count moving. `coneria_town` is the third and it *was*
marked -- so the class got looked at rather than read past, which is the whole
reason the rail marks a floor by its edges and not by its numbers. Had it shown
counts, all three would have read as unaffected and none of these three
decisions would have been made at all.



## The digest was refusing floors over enemies it had no business reading

The lane files were keyed by a digest over the map's tiles, its tileset id and
that tileset's whole 256-byte property block. The block is two bytes per tile,
and the second one is a fixed trap tile's formation id -- which FFR rolls per
seed. So the key churned on every reroll while nothing the router reads had
moved, and the format's stated purpose, outliving the seed it was drawn on, was
delivered by the typed stops and then taken away by the digest.

**The narrowing is not "drop byte 1".** That byte decides one thing the walk
cares about: `render_maps.fixed_formations` reads it through
`battle_byte_inverted` to sort fixed traps from random encounters, and the sort
prices `Floor.enter`, so it can move a drawn lane. The digest now hashes the
grid and then, per tile id the map actually lays, that id, its byte 0 and the
derived fixed/random bit. Restricting to laid ids is the other half: a tileset
entry no cell places cannot decide whether a lane drawn on that map still holds.

**The tileset id came out with it.** It was in the digest as a stand-in for the
properties -- two identical grids under different tilesets walk differently --
and the narrow digest hashes those properties directly, for every tile the map
lays. An id is the weaker claim of the two, and keeping it would refuse a
cartridge that renumbered a tileset without changing what any laid tile does.

**What it bought, on the files as committed.** All 57 still resolve on
`duck-weekly-0831-v2`, the cartridge they were drawn on. 15 now resolve on
`duck-104` with nothing authored for it -- the floors laid tile-for-tile as
their standard twins, where the ported lane draws the same path anyway. And a
standard reroll keeps 51 of 57 where it kept 10: `duck-102`, `duck-103` and
`duck-weekly-0831` all land on 51, `practice-72A52C25` on 49, and each of those
is that cartridge's tile-grid ceiling exactly. The six floors `duck-weekly-0831`
misses are `gaia` and the five ToFR floors, which it genuinely lays differently.

**`VERSION` went to 2 and all 57 files were re-keyed in one pass**, refusing any
file whose stored digest was not the old digest of that cartridge. The bump is
what makes a stale file say so: without it, a file written under the old key
reads back as "no layout for this cartridge", which is the ordinary outcome on a
reroll rather than the defect it would be.

**Four rows in `test_lane_file.py` hold the shape**, on a patched copy of the
cartridge rather than a fixture: a trap tile's formation id must not move the
digest, the fixed/random sort must, a laid tile's byte 0 must, and a tile id the
map never lays must not. A digest that noticed everything passed three of those,
which is why the first row exists at all.

**The re-key found a green check over stale art.** With all 57 files rewritten
and the standard art necessarily redrawn, `verify.sh` stage 4 said the override
was current. `verify()` compared the INPUT_FILES fingerprint and the written
files and nothing else -- and `tools/lane_file.py`, which decides which layout a
digest resolves to, was not in INPUT_FILES. The `lane_files` sha it wanted was
already in the cache and already read by `flag_change`. One key, two readers,
one of them not reading it. Both holes are closed, and `docs/ISSUES.md` carries
the entry because the shape outlives these two lines.

**The standard art is byte-identical across the change**, which is the check
worth keeping: a private render of `duck-weekly-0831-v2` into a scratch
directory matches the installed override's 68 files exactly. The narrowing
accepts strictly more cartridges and draws the same lane on the ones it already
accepted, so the only visible movement is the 15 floors the No-Overworld half
gains.


## Carrying 32 lanes to the other cartridge, and what would have eaten them

The narrowing handed No-Overworld 15 floors and left 42. Those 42 were never an
authoring problem: the standard route already walks on 32 of them, and what was
missing was the key, not the judgement. `tools/port_lanes.py` mints it — for
each floor it takes the entry matching the cartridge the lane was drawn on,
re-keys a copy to the target's digest, and accepts it only if `lane.authored`
walks it.

**The acceptance test is the drawing code, deliberately.** The one failure worth
designing against is a port the tool accepts and `regen_maps` then refuses, so
the check is the same call the art makes rather than a second opinion about what
a walkable lane is.

**The verbatim rule is the whole tool.** Every stop keeps its `kind`, its `at`
hint and its `region`; the entry keeps its `retrace`. It is tempting to drop the
hints and let `lane.anchors` re-resolve each stop from what it means — the typed
kinds exist precisely so a stop can survive a cartridge that moved it. That is
wrong here and measurably so: with both ends free to move, a route lane
collapses to the cheapest arrival/exit pair the floor offers, on 23 of the 42,
sometimes to a single step. The typed kind is the fallback for a hint that no
longer holds, not an improvement on one that does.

**The tally reproduced a measurement taken before the tool existed**, which is
the reason to trust it: 15 already drawn, 32 carried, 10 refused, and the ten
are the ones `docs/ROADMAP.md` had already named — six towns plus `tofr1F`
losing the arrival outright, `elf_castle` and `nw_castle` keeping one they
cannot walk from, `bahamutB2` on a chest index. The nov oracle refuses the same
ten, which is what the test walks, so the refusal is a property of No-Overworld
sealing rather than of one seed.

**A port that walks is a draft.** It is the drawn route replayed on a floor
whose walls have moved: legal, and possibly silly, because a corridor that was
the short way round on one cartridge can be the long way on another. The 32 want
an eye in `tools/lane_edit.py` before they are believed. The exception is the 15
that share a layout outright, where the path is byte-identical and there is
nothing to look at.

**The art moved this time.** `regen_maps.py` on `duck-104` drew 47 and wrote 32
of 67 files — exactly the ported floors, which is the tally agreeing with itself
from the other end.
## The doors are on the map

2026-09-04. Thirty trapezoids on the standard overworld, one per door, plus the
three-stage control that switches them and a decision about diamonds that had to
be taken first.

**The union, before a third shape existed.** A diamond meant two things already
-- a pin standing on a sprite, because a rect is opaque and would hide it, and
an incentive slot -- and the trapezoid arriving meaning "entrance" is what made
that worth closing rather than tolerating. Settled as a union: a diamond means
"a sprite check or an incentive slot", and the shape no longer reads backwards.
Nothing that gets drawn changed. It went in `README.md` and not the Map Key
`docs/ROADMAP.md` had asked for, because the Map Key is rendered art whose band
is reserved only where there is something to say -- shape rows would reserve one
on all 61 maps, change every crop height, and move every marker coordinate.

**The pins cannot live in the committed trees, and finding that out settled most
of the design.** `overworld_pins.restamp` drops any marker on an overworld map
whose node the resolver did not place, and `place_locations` treats an
unplaceable node on a redrawn map as fatal. A committed node set is one fixed
count and the cartridge's is not -- 30 doors and 99 floor links on the standard
oracle against 165 links on the No-Overworld one -- so a node absent from a seed
would hard-fail the regen. Everything is injected by `regen_maps` into its own
output instead. The consequence is worth banking: the four committed trees never
change, so `check_logic`, `test_maps.lua`, `test_pins.lua`'s counts and
`pin_visibility --check` all stay green by construction, and the invariants
`test_maps.lua` owns had to be restated in a suite that can still see them.

**The doors keep their tiles.** Twenty-seven of the thirty already carried a
place pin, and a trapezoid is the same size box as a rect, so coincident means
one of them invisible and which one depends on tree order. `spread()` already
stacked pins that shared a door; it now takes the door tiles as occupied before
it starts. Every standard overworld place pin therefore moved up by one marker
height -- the most visible change here, and the one that makes a town read as a
door with its contents on top. The doors are anchors for the crop too, because
five of them carry no place pin and two of those sit well away from the nearest;
that cost six rows and no width, and the eight-pass fixed point settled.

**And the collision had to become a box, not a tile.** `spread()` took its step
from the marker and then asked whether two pins sat on the same *cell*, which is
two different measurements: Cardia Swampy stood three tiles off Bahamut's door,
cleared the tile test, and drew half on top of the trapezoid. Two boxes clash
when they are within a step on both axes. That takes the standard overworld from
six overlapping pairs to three, and the incentive sheet to none. The three left
are doors sixteen to eighty pixels apart -- Elfland and its castle, Coneria and
its castle, Bahamut's cave and Cardia -- where no marker size separates them and
stacking one would put a trapezoid on a tile that is not its door, which is the
one thing these pins exist to say.

**Two of those three were still one shape, and half a marker fixed it.** A full
step is what puts a pin off its door; half is not, because the box reaches half
a marker either side of centre, so a town nudged by half still covers the tile
it names -- off centre, not off its door. Coneria and its castle go from sixteen
pixels apart to sixty-six, Elfland's pair from sixteen to fifty-one. They still
overlap, since the boxes are ninety-two and the doors are one tile apart, but
they read as two shapes, which is what the board needed.

Which of a pair moves is read off the names rather than listed: a town's name is
a prefix of its castle's, so the shorter is the town. South, because the place
pins stack north and nudging up would walk a door into the pins that just moved
out of its way. Bahamut's Cave and Cardia are not a pair and stay put at eighty
pixels -- a rule firing wherever boxes touch would move pins nobody was
struggling to tell apart. It runs inside the crop's fixed point and off the
unnudged doors every pass, because the nudge is measured in markers and the
marker is what that loop is settling.

**The tooltip icon is the one place a pin can carry a picture.** The marker is
a shape and a state colour and nothing else -- `mapwidget.cpp:352` paints a
diamond, a trapezoid or a rect and has no path to an image -- so the door a
player hovers is `chest_unopened_img` / `chest_opened_img` on the group, which
every section under it inherits (`location.cpp:175`). The pack set neither
anywhere, so an entrance was showing PopTracker's built-in chest.

The tile is found by its own property: the first tile any drawn map calls
`TP_SPEC_LOCKED`, the door the Mystic Key opens. $3B in every tileset that has
one on all four measured cartridges, and Coneria Castle is always the first map
with one -- but reading the property is what makes that a measurement.

**They are committed, and `Pack::hasFile` is the reason.** The first cut had a
regen write them into the override beside the art, which is where cartridge art
belongs here and which does not work: `Pack::ReadFile` consults the override but
`MakeLocationIcon` asks `hasFile` first (`maptooltip.cpp:214`), and
`Pack::hasFile` (`pack.cpp:200`) looks only in the zip or the pack directory. A
section image that lives only in the override fails that test and falls back to
the chest -- silently, with every other overridden file being served. So it went
in the pack, which `README.md` allows: whole maps stay out, "single sprites are
a deliberate exception ... icons made that way may ship here". These are the
first two. The door is not rolled per seed -- byte-identical off all four
cartridges -- so a reader gets a door without owning a ROM.

**A locked door and an unlocked one are the same tile**, which is the
cartridge's answer and not a shortcut, so the state is carried by a transform rather
than by a second piece of art. The transform is the pack's own -- `settings.json`
sets `disabled_image_filter` to `grayscale, dim`, an average greyscale at half
brightness (`imagefilter.cpp:66-81`) -- but which side it goes on came out
backwards first time, from reading that filter as the answer. It is not: it is
about items, where the axis is have and have-not. A location's axis is done and
not-done, and PopTracker ships that answer in its own pair -- `assets/closed.png`
averages 63.7 over its opaque pixels against `open.png`'s 53.1. So the shut door
is full colour and the one you have walked through fades, and the suite asserts
the direction rather than only the difference. PopTracker cannot do that
dimming for us: a section image is a raw path and `img_mods` are not applied to
one (`maptooltip.cpp:228`, "TODO: +img_mods"). A path that resolves to nothing
falls back to the chest without a word, so both sides name one pair of
constants rather than two strings that could drift apart.

**Where the injection goes is load-bearing in both directions.** After
`restamp`, which would otherwise take all thirty straight back out. Before
`pin_visibility.stamp`, so the rule is the stamper's to write -- it learned an
`entrance` kind keyed on the injected group's *name*, not on the marker's shape,
because keying on the shape would make the shape the source of truth for what a
pin means, which is the reading the diamond entry had just closed.

**The Auto stage needed an item, not a flag read.** `Tracker::isVisible` resolves
a marker's visibility rule with no cache, but the view only asks on
`onStateChanged` -- an item changing. The incentive `$showPin|slot` rules refresh
because their flags are items; a rule reading `FFR_FLAGS` alone would have
nothing to fire it and would draw the previous cartridge's answer. So
`flag_mapping` ORs `Entrances`, `Towns` and `Floors` into an ungridded
`entranceShuffle` toggle. `test_mapping.lua`'s "every flag reaches a grid" check
caught it the moment it was added, which is what `OFF_BOARD` is for.

**And a greyed icon nobody had named.** Chasing why a pinned `Overworld Tab`
does not survive Reset turned up that `init.lua`'s `tabMode.CurrentStage = 0` had
always been a no-op -- with `allow_disabled` false, `Lua_NewIndex` compares
`_stage1` against itself -- and that the item has been drawing its *disabled* row
at every stage since it landed, because `FromJSON` raises `stage1` only for a
composite toggle and `_changeStateImpl` never moves it for a plain progressive.
`Active = true` is the fix and cannot carry an opinion about the stage.

Reset itself is upstream's. The snapshot is taken one line after `init.lua` and
one line before the autosave restore, `saveState` ignores the ScriptHost so Lua
state is neither saved nor restored, and the sandbox opens no `io`. What was in
reach was making that snapshot hold what `items/flags.json` declares rather than
what a script wrote over it, and `docs/ISSUES.md` carries the rest with the
citations.

## And the staircases with them

2026-09-04, the same day. 148 floor links on the standard oracle and 190 on the
No-Overworld one, in the same group and under the same switch as the doors. The
count moves with the layout now that a floor's own door is one of them -- the
duck weekly cartridge comes out at 147 -- so a figure here names its cartridge.
A door and a staircase are the same thing to a player and to the toggle; that
they come from three different tables is the tool's problem.

**The warp filter is the whole feature, and taking the kind wholesale was too
much of it.** `Graph.teleports` returns warp tiles as well as links, and a
town's entire outer border is warp-to-overworld: 33,282 of them on the standard
oracle against 99 `norm`-and-`exit` links, and 32,200 against 165 on the
No-Overworld one. Dropping the kind outright is what made the board readable --
and it also dropped every dungeon floor's way out, because leaving a floor for
the overworld is a warp too.

**Mirage Tower 1F is the case that showed it.** Two teleport tiles: `(14,31)`
norm up to 2F, drawn, and `(17,31)` warp out to the overworld, not. The lane's
own `arrival` stop is `(17,31)`, so the art painted its start box on the tile
and the pins left it bare -- the map disagreeing with itself in the one place a
player looks to find the exit. The standard and No-Overworld boards disagreed
too, because on a No-Overworld cartridge that same tile is a `norm`.

**The two shapes are nowhere near each other, which is what makes the rule
safe.** Warp clusters on the standard oracle run 1, 1, ... 2, 3, then 5, 6, 7,
11, 18, 39, then 1074 and up to 3510. A cluster of four or fewer is a door;
above that is a border. Size alone was not enough: everything from 5 up is a
straight run along a map edge, and those runs leave stragglers no flood joins --
three tiles at x=0 in Lefein, three at y=0 in Northwest Castle, eleven in all.
So a door has to be inside the map's content as well, measured with the same
edge flood the crop uses.

**And inside the content the crop keeps, which is not the same set.** Sky Palace
4F has a warp tile at (3,3) that is its own one-cell region, walled off from all
sixteen rooms -- a tile nobody can reach, and one `content_crop` drops as a
speck. The flood's answer put a pin on art that is not drawn and the regen
stopped on it, which is the guard doing its job on a rule that was wrong: a door
nobody can walk to is not a door. Dropping specks the same way costs two tiles
on the standard oracle and one on the No-Overworld, and Sea Shrine B3's
thirteen-cell pocket is the other one.

That leaves 61 tiles on the standard oracle across 47 maps and 36 on the
No-Overworld one across 28: one per floor, except Cardia's five mouths and ten
floors with two.

**One pin per link, not per tile.** A doorway is as wide as the art draws it and
the teleport table repeats itself across every tile of it, so Coneria Castle
drew eight trapezoids in two rows along its rim -- three tiles and five -- for
what a player walks through twice. Ice Cave B2's wide pit is the same thing a
floor down. Adjacent tiles are one pin when they are the same link, same kind
and same teleport id, which is what makes the merge lossless: measured on four
cartridges every run of adjacent link tiles is uniform in both. 160 tiles come
out as 148 pins on the standard oracle and 201 as 190 on the No-Overworld one.

Two pits that share a destination but not a wall stay two pins, because that is
what the floor has -- fifteen of Ice Cave B2's nineteen holes go to one tile of
B3 and are scattered across the floor. Merging on the destination would also be
the one merge that spoils: it is the shuffled half.

The suite asserts both sides. The border half stays five figures, which is the
only form that holds whichever cartridge it is handed. The door half is checked
on a grid built in the test -- a lone warp inside the content, one out in the
filler, and a 3x3 flood inside it -- because a cartridge can only ever show the
rule agreeing with itself, and each condition has to be seen rejecting a tile
the other would let through.

**Same-floor links were nearly filtered out, and the measurement said not to.**
The case for dropping them was that a warp pad is not a hole. The case against
was worth having the numbers for: every same-floor link in the game is on
Castle of Ordeals 2F, 15 of them on both cartridge kinds, so the filter is not a
general rule at all -- it is a decision about one room. Ordeals 2F is the
teleport maze, the pins land on its pads, and that is the floor where they say
most. Left in.

**Ice Cave B2 is the other end of the same argument and also stayed.** Fifteen
of its nineteen holes land on one tile of iceB3. On a No-Overworld cartridge the
other four do not: one goes back up to B1 and one drops into Gurgu Volcano B2.
Nothing on the floor tells them apart, which is the argument for drawing all
nineteen rather than the four that are interesting.

**A trapezoid beats a diamond.** Three tiles on the standard oracle and seven on
the No-Overworld one are both a floor link and a drawn sprite. `marker_pixel`
takes an explicit shape for exactly this: the diamond rule is a rendering
answer, and letting it win would have a door start meaning "something here is
worth a look" instead. The sprite is covered on those ten tiles and the count is
printed, so a number that grows is news.

**A claim that did not survive being checked.** The first look at Ice Cave B2
said the pins sat over the trap-tile letters. They do not -- zero overlaps
across all 61 maps, because a trap tile is standing ground and a link tile is a
hole. The pins in that preview had been drawn at 24px when the map's markers are
14px, which is also what made the floor look like a blob.
