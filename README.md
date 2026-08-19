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
pool, because all it does is talk to the AP server. It cannot see:
- Orbs lit
- Items turned in (i.e. you won't get the checkmark on the item when you've turned it in)
- When the slab is translated vs when it's picked up. You'll have to manually click the slab to indicate you translated it.
- Shards obtained by lighting orbs rather than through AP.

Chests are no longer on that list. See "Chest tracking without Archipelago" below.


Chest tracking without Archipelago (Mesen)

FFR randomizes every chest, but Archipelago only ever sees the ones you put in
the pool -- and a plain FFR async has no AP server at all. `bridge/` holds a
Lua script that reads the game's chest and event flags straight out of the
emulator and feeds them to PopTracker over UAT, which covers both cases. It
runs alongside an AP connection rather than replacing it; if a chest is in the
AP pool, both feeds report it and the tracker counts it once.

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

`AP` and `UAT` are separate labels and you can have both connected at once.
If `UAT` stays grey, check that the script is actually running in Mesen -- the
Script Window log says which port it is listening on.

To check the scripts without an emulator or a ROM, run `tests/run.sh`; it
needs only a Lua 5.4+ interpreter.


Introducing:  Maps!
- This is in it's most basic form. These maps were mostly created and shared with the FFR community by DarkmoonEX.
- Some of the maps are placeholders for the moment.
- Hopefully with the next release maps with chest on them will have red/green tracker boxes on them.
