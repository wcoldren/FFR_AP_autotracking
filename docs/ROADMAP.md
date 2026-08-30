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
because the six now resolve. (That run's output was never committed; the corpus
files as they stand give 254 derived and 222 compared. And most of the agreeing
222 are granted away rather than compared — see `docs/ORACLE.md`.)

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

The No-Overworld numbers do not. Read `docs/ORACLE.md`, "What these figures do
not cover", before quoting them. The derived rules report 222 of 222 agreeing,
but **164 of those 222 had an off-vocabulary item granted free**, so 58 are
actually compared. The pack's own rules report 220 of 226, but they were
transcribed from the export they are graded against: **63 independently
supported, 163 self-agreeing by construction, 6 deliberately strict**. The
honest figure for this item is 63, and the way to move it is the three missing
`GATED_OBJECTS` rows, not more seeds.

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

One thing not to break: a slot the seed did not incentivize is drawn blue rather
than hidden, deliberately, because it is still a check. These toggles are a
different question and must not quietly re-introduce hiding.

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
part that goes stale fastest; check `git log trunk..` before trusting it.

**`noverworld-logic` -- fourteen commits, merged to `trunk`.** `trunk` is
sixteen commits ahead of `origin/trunk` and clean, as of 2026-08-30. The
wiring (feed split, mode guards, 25 region rules, checker), the record
correction, the Black Orb gate, the idea below, and five commits answering the
review. All suites green; std 225/225 and shard 229/229 unmoved throughout.

**The review gate is closed.** `/code-review` ran in a fresh-context session on
`trunk...noverworld-logic` at high effort and returned seven findings, all of
which held up against the files. All seven were fixed rather than waived; each
has its own commit message. Two were more than tidying:

- The mode guards had landed on `locations/incentives.json` alone, which the two
  NoMap variants load, while the two *map* variants load
  `locations/NOverworld/incentives.json` and kept the poster's old geography.
  Twenty-two slots disagreed between the two sheets. `test_maps.lua` check 7
  compares them and had been exempted for exactly that pair.
- `check_logic --derived` graded standard and shard cartridges against rules
  keyed to the No-Overworld tree, producing 279 divergences that described
  nothing. Those cartridges are skipped now.

Nothing pushed without explicit go-ahead.

**Next branch: the remaining two object gates, and the sweep that can hold
them.** One commit, because the parts cannot land separately -- a
`GATED_OBJECTS` row whose item the sweep cannot hold blocks that tile in every
subset, and everything behind it derives as unreachable rather than gated. It
carries:

- SubEngineer `0x10` -> oxyale and Titan `0x14` -> ruby, the last two rows of
  `Sanity/SCMap.cs:167-186`. **Read off the cartridge, not tabulated**, the way
  `black_orb_item()` and `noverworld_gate_items()` are. The two differ in what
  is legible: Titan's requirement byte is set (`Item.Ruby = 9`) and
  `talk_item_requirements()` already finds it; SubEngineer's byte is `0x00`
  (`NPCs.cs` never assigns it), so the only signal is `AD 30 60` in the routine
  body -- the same body scan the `direct` case already uses.
- `entrance_graph.ITEM_NAMES` gains both, taking the sweep to 2^12.
- `check_logic.SWEPT_ITEMS` gains both, or `offvocab_items()` goes on granting
  them free and the new rules read as strict rather than as agreement.
- The memoization at "Memoize the floor walk" in `docs/IDEAS.md`, with its
  **all-subsets equivalence guard** -- memoized and unmemoized must produce
  identical rules over the whole lattice. Note the filed design counts only
  `floor_walk`; `reachable_tiles` also calls `reachable_teleports`, and both
  need the same key or the memo is half applied.
- A failure demonstration per row, per the working rule below. Expected payoff:
  independent support on `nov` rising from 63 toward ~190, since oxyale alone
  blocks 129 of the 226 comparisons.

**Branch after that: make the rendered maps legible.** Three changes that share
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
  than the raw grid and cannot referee the rotation. Look at it before applying
  the change there. `crescent_lake` and `melmond` have no calibration entry, so
  there is nothing to check them against.
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

## Working rules

- One topic branch per item, off `trunk`, named for the theme.
- `/code-review` in a fresh-context session before any merge into `trunk`.
  Findings addressed, or waived in the commit message saying which and why.
- Nothing is done on a successful edit alone. `tests/run.sh` and
  `tools/tests/run.sh` green, and for item 1, `check_logic.py` clean on both a
  No-Overworld and a standard cartridge.
- **A new gate row does not count until it demonstrates a failure.** Adding a
  row to `GATED_OBJECTS` -- or any other rule that is supposed to close
  something -- means showing a location that was reachable without the item
  before the row and gated after it, and saying so in the commit that adds it.
  A row that changes nothing anywhere is either dead code or evidence the
  enforcement is not wired, and both are worth catching at commit time rather
  than on the next person to trust the output. Where the demonstration cannot
  be run yet -- a gate whose item the sweep cannot hold until the vocabulary
  widens -- say that in the commit rather than skipping it silently.
  This is `test_maps.lua` check 6's lesson generalised: a check that cannot
  fail is worthless, and so is a rule that cannot bite.
