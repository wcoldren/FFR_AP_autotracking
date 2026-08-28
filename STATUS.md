# Where this pack is

Working notes on what is built, what is next, and what is known to be wrong.
`README.md` says how to use the pack; this says what state it is in.

Last updated 2026-08-28.

## Working today

- Two autotracking feeds, reconciled rather than merged: Archipelago over the
  wire, and a Mesen Lua bridge that mirrors `$6000-$62FF` over UAT. Either alone
  or both at once. `scripts/autotracking/reconcile.lua` takes the union and
  preserves hand clears.
- Chests, NPC and event flags, orbs, key items and every turn-in stage, vehicles,
  shard count, seed-swap detection, and a Resync button.
- A run clock drawn on the emulator's screen, counted in frames so it pauses
  when emulation does, kept per cartridge across a power cycle.
- The flags grid configures itself from the FFR flag string stamped in the ROM,
  for the FFR versions there is a schema for.
- Map tabs follow the player. 36 of 53 dungeon maps are calibrated and carry
  per-chest markers.
- Offline tools that read a cartridge directly: the flag decoder, an
  entrance/floor shuffle reader and router, an HTML door map, an overworld
  reachability walk, and a logic checker that diffs the pack's access rules
  against FFR's own spoiler.
- `tests/run.sh` — 12 Lua suites, no emulator or ROM needed.

## Next

1. **The flags grid can assert something false.** On a seed whose FFR version
   has no schema, `decodeFFRFlags` correctly refuses, but the board then keeps
   `scripts/init.lua:73-90`'s hardcoded defaults, which turn nine incentive
   toggles on. Seed `72A52C25` is FFR 4-9-2 and shows Sky as incentivized when it
   is not. Two halves: generate the 4-9-2 schema (the ROM is in hand, which is
   what `gen_schema.py` needs to verify the build SHA), and add a "flags not
   read" indicator so defaults never pass as decoded truth. A schema alone only
   fixes today — the next FFR release brings the bug back.
2. **A boss row.** `chaos` and `vampire` are fully plumbed and render in no
   layout grid at all. A `shared_boss_grid` of `garland, vampire, astos, bikke,
   chaos` — the five fights with a real signal — following the
   `shared_shard_hunt_grid` shape. Three of those already render elsewhere, so
   this means moving cells rather than duplicating them.

## Designed, not started

- **Entrance markers.** The data half is done: `tools/entrance_graph.py` reads
  the whole shuffle off the cartridge. The display half is designed end to end —
  the bridge watches party position (`ow_scroll` `$27/$28`, `sm_scroll`
  `$29/$2A`, the party is always 7 tiles in) and publishes an edge log, so the
  pack learns the permutation by observation and reveal-on-visit cannot spoil.
  Needs `min_poptracker_version` raised to 0.32.0. Staged; the first useful
  increment is the log plus a console print.
- **Door-map click-through.** Give `tools/doormap.py` a focus panel and real
  `#map-<id>` anchors driven by `hashchange`, so the shuffled dungeon can be
  walked by clicking. One file.
- **Trap tiles on the map tabs.** FFR randomizes them and the tracker does not
  show them. Shares its whole tile-to-pixel path with entrance markers, on a
  much smaller blast radius.

## Known wrong

- **Missing `LOCATION_MAPPING` rows.** Garland (514), Dr Unne (523) and Bahamut
  (526) have sections but no mapping, so the Archipelago feed can never clear
  them. They light from RAM only.
- **Titan has no box.** The code `titan` is already taken by `ruby` stage 2, so
  a Locations-grid cell needs a new hosted toggle under a different code.
- **17 maps have no markers.** 16 are uncalibrated; `ConeriaCastle2F` is a
  calibration alias away from working.
- **Non-incentivized checks cannot be hidden.** PopTracker does not support
  rule-hiding an `itemgrid` cell — the widget adds every cell unconditionally.
  The map pins already hide correctly. Doing it for the grid means converting
  the 25 hosted toggles to LuaItems that blank their own icon. Deferred until
  the incentive flags themselves are right, since that is most of the
  complaint.
- **`shopItem`** is the one Locations-grid cell with no incentive toggle behind
  it and no FFR flag mapped to it.
- **`items/flags.json:121` has `"active": true`,** which is not a PopTracker key
  and is silently ignored. The real one is `initial_active_state`.

## Open questions

- `smith $6209` reads `0x05` and `fairy $6213` reads `0x04` on a live seed —
  both have the chest bit set with the event bit clear, while their rules test
  `0x02`/`0x03`. Probably fine, since that is chest `$09`/`$13` rather than the
  NPC. Unproven; one before/after read across a turn-in settles it.
- The four Fiends and the ToFR refights cannot be autotracked at all. They are
  spiked battle tiles that write no flag in vanilla or FFR, and the orb byte —
  set by stepping on the altar, not by the kill — is the only proxy. Any box for
  them would be manual-click forever.
