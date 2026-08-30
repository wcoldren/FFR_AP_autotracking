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

**There is a real oracle for this.** `tools/check_logic.py` diffs the pack's
access rules against FFR's own spoiler as truth tables, and names what it could
not map rather than counting it as agreement. Run it on a No-Overworld cartridge
before and after: rules that open a location FFR would not, and rules that hold
one closed FFR would open, both have to reach zero. Run it on a standard seed
too — this must not move a single standard-mode answer.

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
