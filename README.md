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

It also times the run. Nothing else on the machine can: FF1 keeps no play-time
counter in its save, FFR adds no timer flag, and Mesen does not track time per
game. The bridge appends two kinds of line to `ffr_times.log`, in the same
directory as the ROM:

    2026-08-21 17:30:08  start  FFR_6BF0DEA9_XsBTKFAK.nes
    2026-08-21 20:11:02  chaos  FFR_6BF0DEA9_XsBTKFAK.nes  2:40:54 this sitting

`start` is written the first time the bridge trusts a loaded save, once per
sitting; `chaos` is written when the goal flag appears, once per cartridge. A
seed played over several evenings leaves one `start` per evening and a single
`chaos`, so the total is the last stamp minus the first. It only runs while
PopTracker is connected, and it needs the same `Allow access to I/O and OS
functions` restriction the script already requires.

Separately from that log there is a run clock, drawn in the top right of the
emulator's own screen. It starts itself when you start a new game -- a flag page
back at its new-game defaults, with nothing opened and nobody talked to -- and
stops itself on the frame the Chaos flag appears. It counts emulated frames
rather than seconds, which is what makes it pause when the emulation does: tab
away with Mesen's `Preferences -> General -> Pause when in background` ticked and
the clock holds, and it picks up again when you come back. A manual pause, the
menus and a debugger break all do the same. Nothing in Mesen's Lua API reports
focus or pause state, so counting frames is not a shortcut here -- it is the only
way to get that behaviour, and it is exact at the split as a bonus.

The clock does not need PopTracker, for starting it or for keeping it. It keeps
its position in `ffr_timer.<cartridge>.state` beside the ROM and resumes from
it, so a power cycle, a script re-run or picking the seed up tomorrow all
continue the same run rather than starting a new one. There is one such file per
cartridge, not one per directory, which is what lets two seeds sitting in the
same folder each keep a clock -- alternating between them in an evening costs
neither one its time. The line inside names the cartridge too, so a file copied
or renamed by hand is not adopted either.

Starting a new game on a seed whose run already finished starts a new clock for
it. Practice runs, a second attempt on race night and a reset after a bad start
past the goal are all the same thing to the bridge: only a brand new game can
arm the clock, so a finished time is replaced rather than kept forever.

Resets are the case that matters, and the two kinds are not alike. A soft reset
-- the controller combo, or Mesen's Reset, which is the one a run actually
leans on -- leaves the script alive, so frames keep arriving and the clock does
not so much as flinch. A power cycle destroys the script. Mesen starts a fresh
one, and it reads the clock back off disk, but the frames in between are gone:
Mesen tears the Lua state down in a way that fires no `scriptEnded`, so nothing
gets a last write in. Two things keep the damage small. The clock is written
down once a second, so at most a second of it dies with the script; and the
state file carries a timestamp, so the restart itself is measured and added
back. That bridge is capped at fifteen seconds -- a power cycle is back well
inside it, and an emulator closed overnight must not donate the night to the
run. The
final time is appended to `ffr_times.log` as a third kind of line:

    2026-08-21 20:11:02  clock  FFR_6BF0DEA9_XsBTKFAK.nes  2:40:54.38

Two things worth knowing. Mesen has its own `Show game timer` HUD, which times
the session rather than the run; leave it off unless you want both, since they
share a corner. And the community rule is that timing ends when the battle text
on Chaos clears, whereas what the cartridge gives us is the goal flag FFR sets
when the fight is won -- close to that moment but not verified identical, so
check it against a recording before submitting a time.

It also fills in the flags grid. FFR stamps the flag string it rolled with into
the cartridge, so the settings that used to need clicking -- Early King, the
dock and pass flags, Sarda's Forest, open progression, the incentive categories
-- are read off the ROM and applied when you load a seed. A flag you left on
"random" in the generator is the one thing that cannot be read: the flag string
records that it was rolled, not which way it landed, so those stay on whatever
the grid already had and the Script Window names them. Clicking a flag
afterwards sticks; only a new seed or the resync arrow stamps over it. Seeds
from an FFR version the pack has no schema for keep the manual grid, and say so
rather than guessing. `tools/ffr_flags/` has the offline version of the same
decoder, and the details.

The board follows the game rather than accumulating. Loading an older save
un-marks the chests it had not opened and walks items back to what that save
actually holds, and putting a different seed in the emulator drops the previous
one's board wholesale -- the bridge reports which cartridge is loaded, so the
tracker notices the swap without anything being re-run or re-clicked. It will
not fight you over a section you clear yourself: anything you clear by hand
stays cleared.

Starting a new file on the same seed counts too: the moment the feed goes from
having checks to having none, the game has been started over and the board is
wiped to match.

The one exception is an Archipelago session. AP hands you items over the wire
and only replays them when you connect, so while `AP` is online the items it
grants are left alone rather than being second-guessed against cart RAM.

If the board is ever showing something it should not, the circular arrow in the
`Incentives` panel throws it away and rebuilds from the feeds. Nothing is lost
by pressing it while the bridge is connected -- chests, events and items are all
re-derived within about a second -- so it is the thing to reach for after
updating the pack, or if you want your own clicks cleared out. What it does not
bring back is a section you cleared by hand.

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

The access rules get checked against FFR itself rather than trusted.
`tools/check_logic.py` reads the requirement expressions FFR wrote down for a
seed -- in its own spoiler, and in the `rules:` Archipelago is handed -- pins
the flag grid from the cartridge, and compares the two as truth tables over the
items they mention. It reports rules that open a location FFR would not and
rules that hold one closed FFR would open, and it names what it could not map
rather than counting it as agreement. Point it at a seed, or let it find every
ROM under Archipelago's output directory:

    python3 tools/check_logic.py

One rule that reads like a mistake and is not: the `hwyOrdeals,ship,canal,canoe`
alternatives on Gaia, Lefein, Mirage Tower and Sky Palace. Those four sit on a
continent with no dock tile anywhere on it, so a ship cannot land there and
FFR's vanilla table says plainly `{MapLocation.Gaia, MapChange.Airship}`. The
canoe is what makes them reachable: it can be taken from the ship straight into
a river mouth, and there is exactly one river touching that continent, at
overworld (134, 33). Highway to Ordeals and Gaia Mountain Pass then move you
around *inside* it -- neither is what gets you on.

So the reachability question for that continent is "does a river touch both the
ocean and this landmass", not "is there a dock". Walking the map to confirm also
needs the coast tiles (0x06-0x08, 0x16, 0x18, 0x26-0x28) treated as shoreline
the ship enters *and* you can walk; making them purely land cuts the ship off
from the river mouth, and making them purely water severs the path up the pass.
Either way you get a false negative and four correct rules look like false
greens.


Introducing:  Maps!
- This is in it's most basic form. These maps were mostly created and shared with the FFR community by DarkmoonEX.
- Some of the maps are placeholders for the moment.
- Hopefully with the next release maps with chest on them will have red/green tracker boxes on them.
