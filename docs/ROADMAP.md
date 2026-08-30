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
