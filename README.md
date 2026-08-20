# FFR_AP_autotracking

Setting up a recieved item autotracker for FFR on Archipelago (https://github.com/ArchipelagoMW/Archipelago).

This is a pack for black-silver's Poptracker (https://github.com/black-sliver/PopTracker/). 

Pretty simple to use, not 100% as fully functional as the EmoTracker pack, but works for Archipelago.

Known Issues:
  - <del> Map Logic is borked still. </del>
  - <del> Specifically, the northern continents show as available, even when they're not. </del>
  - *Fixed

Known Limitations:
The Archipelago feed only knows about locations that are in the multiworld's
pool, because all it does is talk to the AP server. On its own it cannot see
chests outside the pool, orbs lit, items turned in, or shards from lighting
orbs.

The emulator feed described below covers all of those. What still needs a manual click:
- Sigil and Mark, in no-overworld seeds. They share their memory with Floater
  and Canoe, and nothing in RAM tells them apart.
- The settings flags (Early King, the dock and pass flags, the incentive
  flags). Those describe the seed, not your progress.


Autotracking from the emulator (Mesen)

FFR randomizes every chest, but Archipelago only ever sees the ones you put in
the pool -- and a plain FFR async has no AP server at all. `bridge/` holds a
Lua script that reads the game's own progress out of the emulator and feeds it
to PopTracker over UAT, which covers both cases. It runs alongside an AP
connection rather than replacing it; if a chest is in the AP pool, both feeds
report it and the tracker counts it once.

This does not modify the emulator. It is one Lua script that Mesen runs.

1. In Mesen, open `Script -> Settings -> Script Window -> Restrictions`. Tick
   `Allow access to I/O and OS functions`, then `Allow network access`. Order
   matters -- the network checkbox does nothing until the first one is on.
   Both are off by default and only need setting once.
2. Load your ROM, then open `bridge/ffr_uat_bridge.lua` in the Script Window
   and run it. On macOS `bridge/launch_mesen_ffr.sh /path/to/seed.nes` does
   both in one go.
3. Load this pack in PopTracker and click the `UAT` label in the top bar. It
   turns green and reads `Online` once the bridge is connected, which can take
   up to five seconds.
4. Load your save. The bridge waits for a save to actually be loaded before it
   reports anything, so nothing is marked while you sit on the title screen.
5. Open a chest. It should clear in the tracker within a second.

Once connected it tracks chests and NPCs, Chaos, Garland and the Vampire, the
four orbs being lit, key items and every turn-in stage (Crown to Astos, Slab to
Unne and then Lefein, Ruby to the Titan, and so on), Bridge/Ship/Canal/Canoe/
Airship, and the shard count.

The emulator feed only ever sets things, never un-sets them -- every one of
these events is one-way in the game -- so it will not fight you if you click
something yourself.

It also reports which map you are standing on, so the map tab follows you into
whichever floor you just walked into. `Auto-Tab` in the flags grid turns that
off if you would rather stay on the floor you are reading; it is on by default.
Towns and the overworld both land on the Incentive Locations tab, which is the
same overworld art carrying the markers worth watching during a run. This needs the emulator
bridge -- Archipelago on its own does not report your position -- and only the
two map variants have dungeon tabs to switch between.

Resetting needs nothing re-run and nothing re-clicked. A soft reset -- the
controller combo, or Mesen's Reset -- leaves the script running: tracking pauses
for about half a second and then picks up where it was. A power cycle does stop
the script, but Mesen starts it again by itself (`Auto-restart script after
power cycle`, on by default) and PopTracker re-connects within about five
seconds and asks for the whole board back. Neither one loses a mark either,
though not because the game preserves anything: every reset re-seeds its flag
page to new-game defaults on the way to the title screen. It also zeroes the
byte the bridge uses to tell whether a save is loaded, so the bridge stops
reporting before that wipe can reach the tracker. Loading a save copies the real
flags back and the board fills in again.

`AP` and `UAT` are separate labels and you can have both connected at once.
If `UAT` stays grey, check that the script is actually running in Mesen -- the
Script Window log says which port it is listening on.

To check the scripts without an emulator or a ROM, run `tests/run.sh`; it
needs only a Lua 5.4+ interpreter.


Introducing:  Maps!
- This is in it's most basic form. These maps were mostly created and shared with the FFR community by DarkmoonEX.
- Some of the maps are placeholders for the moment.
- Hopefully with the next release maps with chest on them will have red/green tracker boxes on them.
