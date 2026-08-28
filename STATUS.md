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
- The flags grid configures itself from the FFR flag string stamped in the ROM.
  Schemas ship for FFR 4-9-7 and 4-9-2; a seed on any other version lights the
  unread-flags warning in the grid rather than letting the defaults pass as the
  seed's own settings.
- A Bosses row for the five fights that have a real signal: Garland, the
  Vampire, Astos, Bikke and Chaos.
- Map tabs follow the player. 36 of 53 dungeon maps are calibrated and carry
  per-chest markers.
- Offline tools that read a cartridge directly: the flag decoder, an
  entrance/floor shuffle reader and router, an HTML door map, an overworld
  reachability walk, and a logic checker that diffs the pack's access rules
  against FFR's own spoiler.
- `tests/run.sh` — 12 Lua suites, no emulator or ROM needed.

## Next

1. **Door-map click-through.** `tools/doormap.py` gets a focus panel and real
   `#map-<id>` anchors driven by `hashchange`, so the shuffled dungeon can be
   walked by clicking instead of scrolled. One file, no pack risk.
2. **The missing `LOCATION_MAPPING` rows** below, which are a quiet correctness
   hole rather than a feature.

## Designed, not started

- **Entrance markers.** The data half is done: `tools/entrance_graph.py` reads
  the whole shuffle off the cartridge. The display half is designed end to end —
  the bridge watches party position (`ow_scroll` `$27/$28`, `sm_scroll`
  `$29/$2A`, the party is always 7 tiles in) and publishes an edge log, so the
  pack learns the permutation by observation and reveal-on-visit cannot spoil.
  Needs `min_poptracker_version` raised to 0.32.0. Staged; the first useful
  increment is the log plus a console print.
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
- **The incentive defaults are still a guess** on a version with no schema.
  The warning light says so, but the toggles themselves stay on whatever
  `scripts/init.lua:73-90` set. They cannot simply be cleared: an
  Archipelago-only player never receives a flag string at all, since only the
  bridge publishes one, so an empty default board would be wrong for every AP
  session.
- **Non-incentivized checks cannot be hidden.** PopTracker does not support
  rule-hiding an `itemgrid` cell — the widget adds every cell unconditionally.
  The map pins already hide correctly. Doing it for the grid means converting
  the 25 hosted toggles to LuaItems that blank their own icon. Deferred until
  the incentive flags themselves are right, since that is most of the
  complaint.
- **`shopItem`** is the one Locations-grid cell with no incentive toggle behind
  it and no FFR flag mapped to it.
- **The Chaos goal flag only exists on Archipelago seeds, and three things
  depend on it.** `$62FE` bit 0x02 is written by a patch FFR applies only in
  `FF1Lib/archipelago/Archipelago.cs:225-226`, which rewrites bank `0x0B`
  `$9ADF` to `20 40 9B`. Every solo seed has the vanilla `20 52 A0` there, so
  the bit is never set, and: the run clock never stops, no `chaos` or `clock`
  line is ever appended to `ffr_times.log`, and the tracker's Chaos check
  (`LOCATION_MAPPING[766]`) never clears from the bridge. Confirmed against
  three cartridges and two logs holding 27 `start` lines and nothing else.
  The clock is the visible symptom; the un-clearing Chaos check is the bigger
  one. A fix has to stop reading that flag — hooking execution of `ChaosDeath`
  (bank `0x0B` `$A052`) is exact and available, since Mesen can break on an
  address. Note the routine waits **110 frames** for the victory fanfare before
  the dissolve begins, so the entry point and the kill screen are 1.8s apart and
  which one the community times to needs settling before it is wired up.

## What Archipelago can and cannot tell the tracker

Worth writing down, because "bring AP to parity with the bridge" sounds like
pack work and is not. The AP feed carries checked locations in the multiworld
pool and items received, and nothing else: `worlds/ff1/__init__.py:123`'s
`fill_slot_data` returns an empty dict. So chests outside the pool, orbs lit,
turn-in stages, the current map, the seed's flags, the cartridge's identity and
the run clock are all unavailable over AP by construction, not by omission here.
Closing that gap means changing the Archipelago world, not this pack. The
reconcile core already does the right thing with what exists — takes the union
of both feeds and lets either run alone.

The traffic is not one-way, though: the Chaos goal flag above is the one thing
an AP seed has that a solo seed does not.

## Open questions

- `smith $6209` reads `0x05` and `fairy $6213` reads `0x04` on a live seed —
  both have the chest bit set with the event bit clear, while their rules test
  `0x02`/`0x03`. Probably fine, since that is chest `$09`/`$13` rather than the
  NPC. Unproven; one before/after read across a turn-in settles it.
- The four Fiends and the ToFR refights cannot be autotracked at all. They are
  spiked battle tiles that write no flag in vanilla or FFR, and the orb byte —
  set by stepping on the altar, not by the kill — is the only proxy. Any box for
  them would be manual-click forever.
