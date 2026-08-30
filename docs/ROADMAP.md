# What is next, in order

The No-Overworld map work is the focus. This is what should happen around it, and
why in this order. `docs/IDEAS.md` holds everything not on this list.

The ordering principle: **correctness before art, and infrastructure before the
features that need it.** A pin in the wrong place is a cosmetic problem; a pin
coloured green when the check is unreachable is a lie the player acts on.

## 1. The No-Overworld logic branch

The largest live defect in the pack, and the largest player-facing win available.

`scripts/logic.lua` branches on shard hunt and nothing else, so roughly thirty
overworld-geography rules still gate No-Overworld seeds — a mode where ship and
bridge are free and the canoe is not a vehicle at all. Every pin on those two
variants is coloured by rules that do not describe the seed.

The research half is already done. The gates are readable off the cartridge, the
router stops at them, and `entrance_graph.noverworld_gate_items()` derives which
routine wants which item from the cartridge's own talk table rather than from
transcription. What is missing is the pack acting on any of it.

Shape of the work:

- Add `isNoOverworld()` to `scripts/logic.lua`, matching `Tracker.ActiveVariantUID`
  the way `isShardHunt()` does — with `:find`, not `==`.
- **Put the mode difference in Lua, not in a second JSON tree.** Rewrite the
  geography rules as `$`-prefixed calls, the way `^$incentiveSlot|<flag>` already
  works, so one set of rules serves both modes. Two trees that must agree and are
  never compared is exactly how a missing location file survived for weeks.
- `regen_maps.place_locations()` only rewrites `map_locations` and passes
  `access_rules` through untouched, so this survives a regen.
- Extend `tests/test_maps.lua` check 6, which already compares the two trees
  location by location, to compare access rules too.

**The oracle has been run, and the derivation has been fixed against it.**
`tools/check_logic.py --derived` compares the derived rules with FFR's own
Archipelago export as truth tables. First run: 218 comparable locations, 52
agree, **166 divergent and every one permissive** — the derivation opening what
FFR holds closed.

The cause was one line. `noverworld_rules.reachable_tiles` seeded its walk from
everything `Graph.starts()` returns, which is a fact about the *table* — the
entrances that have a tile — not about the player. On this mode that is nine
separate one-tile islands on the ocean stub. The party starts on exactly one of
them, and cannot leave it: every pad carries tile property `0x0E`, walkable on
foot and refused to the canoe, the ship and the airship alike. There is no
sailing or flying between pads; all travel is the teleporter table, and the
items that open it are the four gate NPCs standing in corridors.

`start_doors()` now reads the party's start off the cartridge (bank `$00:$B010`,
plus FFR's `+7` scroll offset) and takes the doors on its own landmass, walking
the overworld with `overworld_reach` rather than assuming. On the reference
flagset that is the eight-tile Coneria Castle platform, holding one door.
Empty-handed reach drops from 45 maps to 22; with every item it stays 54 of 61,
which is the invariant `docs/NOVERWORLD.md` says gates must not move.

After the fix: **216 of 218 agree, 2 divergent.** The two were Nerrick and Astos,
who want the TNT and the Crown handed over before they give anything — a trade,
not a tile.

**Both are closed, and the six unplaced NPCs with them.** The trade is data on
the cartridge: FFR's talk records carry a requirement byte, and
`entrance_graph.talk_item_requirements()` reads it for the objects whose script
is shown to consult it. The six were never placed because `extract_npcs.WANTED`
had not been asked for their object ids; while fixing that, positions moved to
being read off the seed rather than out of the vanilla snapshot, which FFR moves.

Re-run on a freshly built 4.9.2 oracle cartridge: **226 comparable, 226 agree, 0
divergent**, no location left without a derived rule. The count rises from 218
because the six now resolve. (The corpus's derived files were behind that for a
while, giving 254 derived and 222 compared; they were regenerated on 2026-08-30
with the widened sweep and now give 255 and 226.)

The **pins** read the cartridge too, since 2026-08-30. `marker_tiles` and the
two crop guards took NPC tiles out of `tools/npc_positions.json`, the vanilla
snapshot, which drew Nerrick's pin two rows off his sprite on a No-Overworld
regen. Fourteen NPCs have a pin now rather than eight; the King, Sara, the Elf
Prince and the Robot each got a location of their own first, because a marker's
state is ORed over its node's sections and their pins would otherwise have
reported a dungeon's chests. `npc_positions.json` stays as the vanilla anchor
`tests/test_maps.lua` reads, having no cartridge of its own.

The same run on a standard cartridge, against the pack's existing hand-written
rules, is the baseline to protect: **225 checked, 225 agree, 0 divergences**, and
unpruned — `reqs` was empty, so no achievability pruning hid anything. That is
also what validates the harness end to end. This must not move.

Both cartridges are generated locally, with their own ground truth attached.
**The recipe, the inventory and the recorded numbers now live in
`docs/ORACLE.md`** rather than here, alongside the corpus they describe: four
cartridges (standard, No-Overworld, a second No-Overworld seed, shard hunt),
their flag strings, the `ffr-492-oracle` build tree, and the exact commands.
Rebuilding is bit-reproducible — regenerating either cartridge from its flags
preset at its recorded seed gives byte-identical output.

Three results from that page belong here, because they are what this item rests
on. The standard baseline is **225 checked, 225 agree**, and it must not move;
shard hunt has a first measurement too, **229 of 229**. Both are hand-written
rules graded against an independent export, so both mean what they say.

The No-Overworld numbers said much less until 2026-08-30, and the reason is
worth keeping. The derived rules reported 222 of 222 agreeing, but **164 of
those 222 had an off-vocabulary item granted free**, so 58 were actually
compared; the pack's own rules reported 220 of 226 while having been transcribed
from the export they were graded against — **63 independently supported, 163
self-agreeing by construction, 6 deliberately strict**. The honest figure was
63, and the way to move it was the missing `GATED_OBJECTS` rows rather than more
seeds.

That is what the SubEngineer and Titan rows did. The grant is down to **5 of
226**, the derived rules are **226 compared, 225 agree, 1 divergent**, and **215
of the 226 now rest on two independent readings** — the transcription and a walk
of the cartridge — against 63 before. Read `docs/ORACLE.md`, "What these figures
do not cover", before quoting any of it; the one divergence is Lefein, filed in
`docs/ISSUES.md`.

What the oracle does not cover is ToFR — `Archipelago.cs:93` drops it from the
AP pool unconditionally. `tools/tofr_diff.py` covers that gap by comparison
instead: same flags, different seed, report what the shuffle moved.

## 2. Visibility toggles

Infrastructure, and the reason it comes before the remaining map work: the
features after this each add a large set of pins, and pins with no off switch are
worse than no pins.

Everything needed is available at the current `min_poptracker_version` of 0.35.1.
`visibility_rules` has existed since 0.17.0 and per-pin
`restrict_visibility_rules` / `force_invisibility_rules` since 0.25.4. This pack
uses `visibility_rules` exactly once per tree.

The pattern to copy is two-stage progressive items whose "on" stage grants a
`show_*` code and whose "off" stage grants nothing, with `inherit_codes: false`
on both — that is what makes a `visibility_rules` entry flip.

Start with the categories that have pins today, chests and NPCs, and add a
category alongside each later feature rather than declaring empty ones now.

One thing not to break: an incentive slot the seed did not reserve is drawn blue
rather than hidden, deliberately, because it is still a check -- and can still
hold a key item, since FFR places the ones it did not incentivize into exactly
that pool. These toggles are a different question and must not quietly
re-introduce hiding.

`layouts/settings_popup.json` — the gear-button panel — is a later pass, once
there are enough toggles to justify it.

## 3. The No-Overworld map surface

The current focus, resumed once the above are in.

- **The connection diagram.** A hand-drawn pseudo-overworld arranging the areas
  geographically with the fixed links as roads, in the pack's own style. A static
  map is the right shape because the topology is fixed, and that is measured
  rather than assumed: three seeds carry 157 links each and differ only in the
  Gaia gateway and the two Waterfall stairs. Those three gateways want a `?`.
  Deriving the pin coordinates from the same layout that renders the art is the
  thing worth insisting on — hand-placed pins are what let the poster's markers
  drift off its art in the first place.
- **The 28 incentive pins.** `locations/NOverworld/incentives.json` is still
  hand-authored against upstream's poster. Derive them from the cartridge.
- **Entrance markers.** The data half is done — `entrance_graph.py` reads the whole
  shuffle. The display half is designed end to end: the bridge watches party
  position and publishes an edge log, so the pack learns the permutation by
  observation and reveal-on-visit cannot spoil. The trapezoid shape is reserved
  for these and does not clash with the diamond. First useful increment is the
  log plus a console print.
- **Boss pins**, if the manual-click cost is judged acceptable — see
  `docs/IDEAS.md` and the open question in `docs/ISSUES.md`.

Entrance markers ship **off** by default and are worth turning on in No-Overworld
and entrance rando. That is a setting, not a branch, which is why item 2 comes
first.

## Branch queue

Where item 1 actually stands, 2026-08-30, and what comes off it. This is the
part that goes stale fastest, and `git log trunk..` is what actually says
where a branch stands.

**`noverworld-logic` -- fourteen commits, merged to `trunk`, pushed.** `trunk`
is level with `origin/trunk` and clean, as of 2026-08-30. The wiring (feed
split, mode guards, 25 region rules, checker), the record correction, the Black
Orb gate, the idea below, and five commits answering the review. All suites
green; std 225/225 and shard 229/229 unmoved throughout, including across the
gate branch below.

**The review gate is closed.** A full review of `trunk...noverworld-logic`
returned seven findings, all of which held up against the files. All seven were fixed rather than waived; each
has its own commit message. Two were more than tidying:

- The mode guards had landed on `locations/incentives.json` alone, which the two
  NoMap variants load, while the two *map* variants load
  `locations/NOverworld/incentives.json` and kept the poster's old geography.
  Twenty-two slots disagreed between the two sheets. `test_maps.lua` check 7
  compares them and had been exempted for exactly that pair.
- `check_logic --derived` graded standard and shard cartridges against rules
  keyed to the No-Overworld tree, producing 279 divergences that described
  nothing. Those cartridges are skipped now.

**Landed: the remaining two object gates, and the sweep that can hold them.**
One commit, because the parts could not land separately -- a `GATED_OBJECTS` row
whose item the sweep cannot hold blocks that tile in every subset, and everything
behind it derives as unreachable rather than gated. What went in:

- SubEngineer `0x10` -> oxyale and Titan `0x14` -> ruby, the last two rows of
  `Sanity/SCMap.cs:167-186`, read off the cartridge by
  `entrance_graph.object_gate_items()`. The two differ in what is legible, and
  the reader follows the cartridge rather than flattening them: Titan's
  requirement byte is set (`Item.Ruby = 9`) and `talk_item_requirements()`
  already found it, while SubEngineer's is `0x00`, so his item comes from the
  routine body -- `AD 30 60`, LDA item_oxyale -- and only when the body names
  exactly one item address.
- `entrance_graph.ITEM_NAMES` gained both, taking the sweep to 2^12, and
  `check_logic.SWEPT_ITEMS` with it, so the two stop being granted free.
- The memoized floor walk, with the all-subsets equivalence guard, in
  `tools/tests/test_memo_walk.py`. `reachable_teleports` is memoized alongside
  `floor_walk`, which the filed design had missed. The sweep went from 1024
  subsets in ~85s to 4096 in ~57s.

The demonstrations, per the working rule below. On `std`, holding every item but
the one: SubEngineer closes 32 locations across the five Sea Shrine floors,
Titan closes the 4 in his tunnel. On `nov` Titan closes the same 4; SubEngineer
closes nothing at that level, because with everything else in hand the Sea Shrine
has another way in -- so the demonstration for it is one subset down, holding
`chime,floater`, where it closes 59 locations across Crescent Lake, the Ice Cave
and all five Volcano floors. That is FFR's own `(Chime AND Oxyale AND Sigil) OR
(Mark)` shape, derived rather than transcribed.

The payoff was larger than the estimate. Independent support on `nov` went from
63 of 226 to **215**, not the ~190 guessed here: the off-vocabulary grant fell
from 164 to 5, and at every location where the pack's transcribed rule agrees
with FFR the derived rule now agrees too.

One thing it uncovered rather than caused: **Lefein**, the only `--derived`
divergence left on either No-Overworld cartridge. The Ruby grant had been hiding
it. FFR wants `(Tnt OR Ruby OR Canoe) AND Floater AND Slab` and the derivation
says `floater`, because the Lefein man wants the Slab *translated* and
`SCLogic.cs:555-557` resolves that to Dr Unne's own reachability -- a requirement
naming another location, which the item sweep cannot express at any vocabulary
size. Filed in `docs/ISSUES.md`, and it is an argument for the solver in
`docs/IDEAS.md` rather than for a patch.

**The review gate is closed on this branch too.** A full review of
`trunk..object-gates` returned four findings, all of which held up. All four are fixed rather than waived, in one
commit. Two were more than tidying:

- `object_gate_items()` could name any of `ITEM_RAM`'s seventeen items while the
  sweep varies twelve, so a reassigned routine would have blocked its chokepoint
  in every subset -- the exact invariant this branch states on three pages and
  enforced nowhere. It refuses an off-vocabulary row now, as `black_orb_item()`
  already refused a shard count.
- `check_logic.WAIVED`'s Lefein reason was being stated on the two No-Overworld
  `--ap-rules` runs, where it is false. The waiver's conclusion holds on both
  worlds and the rationale is rewritten to one that does; clearing the waiver
  would have reported Lefein as a divergence on every cartridge.

The two smaller ones: the walk memo was invalidated by `gated_objects` but not by
`grids`, though `floor_items()` reads both, and `docs/IDEAS.md` said "seven
further items" over a list of five. All figures unmoved -- `nov --derived`
226/225/1 with 5 granted, `nov` 226/220, std 225/225, shard 229/229 -- and the
`FF1_SLOW` full-lattice guard re-passed on `nov`, 4096 of 4096.

**Next branch: make the rendered maps legible.** Three changes that share
one regen, because each moves the `inputs` or `marker` fingerprint in
`.regen_cache.json` and a single run picks up all of them. All measured
2026-08-30 on the std and nov oracle cartridges, which agree, so there is no
separate No-Overworld pass here.

- **Rotate before boxing, and treat it as a contract change.** A standard map
  wraps at 64 tiles and `render_maps.content_box` does not, so four maps are
  framed across the void between their two halves: `con_castle` 64x35 -> 31x35,
  `crescent_lake` 52x64 -> 53x43, `melmond` 45x64 -> 45x46, `elf_castle` 28x64 ->
  29x35. The box is not a render detail -- it is computed once
  (`regen_maps.py:177`), handed both to the render (`:262`) and to marker
  placement, and asserted from the other side by `tools/tests/test_crop.py`. So
  pick the representation up front rather than discovering it: **rotate the grid
  first and keep the box axis-aligned in rotated coordinates**, a `(shift_x,
  shift_y)` pair alongside an ordinary `(c0, c1, r0, r1)`. Every consumer goes on
  receiving a plain box; only the tile-to-pixel mapping gains the modular shift.

  **The hand art confirms this for `elf_castle` and does not settle
  `con_castle`.** Checked 2026-08-30 against the shipped images: DarkmoonEX's
  Elf Castle is 34.2 x 34.2 tiles with **no flat row band anywhere**, against the
  tool's current 28x64 and the rotated 29x35 -- he drew the wrapped row at the
  top and cropped to the same height the rotation derives. Coneria Castle is a
  different story: 67.1 x 37.8 tiles, wider than the 64-tile grid, with a single
  4.6-tile flat band and no 35-column void, so that image is a composition rather
  than the raw grid and cannot referee the rotation. `crescent_lake` and
  `melmond` have no calibration entry, so there is nothing to check them
  against.
- **Trap marks keyed to the formation id**, closing the defect in
  `docs/ISSUES.md` where the same enemies carry two different letters, and
  killing every two-character label with it. 32 formations stand on a map (31 on
  nov) against 35 single glyphs in `0-9A-Z` minus `O` -- `O` because
  `tools/font.py` asserts it and `0` are the same glyph in the cartridge's font.
  Assert the ceiling: a cartridge past 35 falls back to two characters rather
  than silently reusing a mark.
- **The marker default, 16px -> 14px, conditionally.** `MARKER_SIZE = TILE_PX`
  carries a written rationale (`regen_maps.py:265-273`) -- the box outlines the
  tile the chest stands on and nothing more -- so the number does not move on its
  own. It moves with a rewritten rationale in the same commit, or it does not
  move. The argument to test: once a trap mark is one glyph and therefore exactly
  one tile, a marker box *inside* a tile is what separates outline from glyph.
  Render one map both ways and look. A recorded decline is a valid outcome.

Two claims this branch invalidates, and must update rather than leave standing:
`test_crop.py:179` and `:195` assert `volcB4`'s letters are `{M,N}` and land on
named tiles (updated to the new scheme, not waived -- the per-tile half exists
because a sorted-set comparison hides a mis-assignment), and `STATUS.md:1213`
records that the enumeration "reproduces the shipped art exactly", which becomes
historical with a line saying what replaced it.

Acceptance beyond the suites: `test_crop.py` gains an explicit wrapped case, it
has none today; and the four seam maps pass `crop_violations` with their markers
landing on their chests.

**Branch after that: the stale-override warning**, per "Notice when the drawn
maps are for a different cartridge" in `docs/IDEAS.md`. Separate because it
touches the bridge and the pack rather than the tools, and is worth nothing
until someone is playing on rendered art.

It builds **detection and execution both**, which is a change from what that page
used to conclude -- see the entry, which says why the old "detection, not
execution" no longer holds rather than dropping it. In order: record the FFR seed
and flag strings into `.regen_cache.json` beside the sha, since the bridge has no
sha256 and both sides already read both; compare on connect and publish a
variable; light a warning cell on mismatch per the `flagsUnread` pattern
(`uat.lua:159-203`); and on mismatch also start the regen **detached**, because
rendering 61 maps inline on the emulator's script thread stalls emulation.

**It has a second mismatch to cover, and that one is not hypothetical.** The
override shadows pack edits as well as cartridge changes: `layouts/shared.json`
and the four location files are in `INPUT_FILES`, so editing one in the repo
does nothing at all while an older override is installed, and a layout key the
override predates renders an **empty group** with no warning anywhere
(`tracker.cpp:791-794`). That happened on 2026-08-30 and is filed in
`docs/ISSUES.md`. The `inputs` fingerprint already moves on such an edit, so
covering it is one more comparison beside the ROM one -- and it is the cheaper
half, because it needs no seed or flag string and no regen to fix a false alarm.
Whichever warning cell this branch lights should say **which** of the two
mismatched, since the fixes differ.

**Step 0 is a measurement, not code:** `os.execute` inside Mesen's Lua is filed
as "plausibly in reach", which is an inference from the file and socket functions
the bridge already uses. If it is not reachable, the first three steps ship and
the fourth does not. The restart is irreducible either way.

Acceptance is a demonstrated failure, per the working rule below: connect with a
mismatched cartridge and show the cell lights, connect with the matching one and
show it does not.

**On the order of those two.** The legibility branch sits first so the regen the
warning triggers produces the better art. That holds **only while it stays one
branch of the size above** -- the torus leg is a contract change and is the leg
that might grow. If it does, the warning branch goes first and a regen is re-run
once the art lands. That costs one extra regen, which is cheaper than delaying a
correctness guard behind an art change.

Not queued, and deliberately: a general requirements solver, and more oracle
seeds. The provenance table says where the risk is; spend there.

The solver has one more argument for it than it did, and it is still not enough
to queue it: Lefein above is a requirement that names another *location* rather
than an item, so no widening of the sweep reaches it. It is one location of 226,
and it is permissive rather than silent, so it stays filed.
