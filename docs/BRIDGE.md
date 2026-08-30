# The emulator bridge, in detail

`README.md` covers connecting the bridge and what it tracks. This is the rest:
the run clock, what happens across a reset, how the flags grid gets filled in,
and how the board is kept honest when two feeds disagree.

All of it is `bridge/ffr_uat_bridge.lua`, one script Mesen runs. Nothing here
modifies the emulator.

## The run clock

The bridge times the run, and nothing else on the machine can. FF1 keeps no
play-time counter in its save, FFR adds no timer flag, and Mesen does not track
time per game.

Two kinds of line are appended to `ffr_times.log`, in the same directory as the
ROM:

    2026-08-21 17:30:08  start  FFR_6BF0DEA9_XsBTKFAK.nes
    2026-08-21 20:11:02  chaos  FFR_6BF0DEA9_XsBTKFAK.nes  2:40:54 this sitting

`start` is written the first time the bridge trusts a loaded save, once per
sitting; `chaos` is written when Chaos goes down, once per cartridge. A seed
played over several evenings leaves one `start` per evening and a single
`chaos`, so the total is the last stamp minus the first. It only runs while
PopTracker is connected, and it needs the same `Allow access to I/O and OS
functions` restriction the script already requires.

Separately from that log there is a run clock, drawn in the top right of the
emulator's own screen. It starts itself when you start a new game -- a flag page
back at its new-game defaults, with nothing opened and nobody talked to -- and
stops itself on the frame Chaos dies.

**It counts emulated frames rather than seconds**, which is what makes it pause
when the emulation does: tab away with Mesen's `Preferences -> General -> Pause
when in background` ticked and the clock holds, and it picks up again when you
come back. A manual pause, the menus and a debugger break all do the same.
Nothing in Mesen's Lua API reports focus or pause state, so counting frames is
not a shortcut here -- it is the only way to get that behaviour, and it is exact
at the split as a bonus.

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

### What a reset costs the clock

The two kinds of reset are not alike. A **soft reset** -- the controller combo,
or Mesen's Reset, which is the one a run actually leans on -- leaves the script
alive, so frames keep arriving and the clock does not so much as flinch.

A **power cycle** destroys the script. Mesen starts a fresh one, and it reads the
clock back off disk, but the frames in between are gone: Mesen tears the Lua
state down in a way that fires no `scriptEnded`, so nothing gets a last write in.
Two things keep the damage small. The clock is written down once a second, so at
most a second of it dies with the script; and the state file carries a timestamp,
so the restart itself is measured and added back. That bridge is capped at
fifteen seconds -- a power cycle is back well inside it, and an emulator closed
overnight must not donate the night to the run.

The final time is appended to `ffr_times.log` as a third kind of line:

    2026-08-21 20:11:02  clock  FFR_6BF0DEA9_XsBTKFAK.nes  2:40:54.38

### Two things worth knowing before submitting a time

Mesen has its own `Show game timer` HUD, which times the session rather than the
run; leave it off unless you want both, since they share a corner.

And the community rule is that timing ends when the battle text on Chaos clears,
whereas the split here is the frame the game itself decides the fight is won --
the instruction before it starts the dissolve, and 110 frames before the dissolve
is on screen. Close to the community moment but **not verified identical**, so
check it against a recording before submitting a time.

The kill is read out of the battle engine rather than off a flag, which is what
makes it work on an ordinary seed. FFR only writes a "Chaos defeated" flag on
Archipelago seeds; on every other seed there is nothing in the save that says the
fight happened, so the bridge watches for the frame the game sets Chaos's battle
result instead. Both routes land on the same frame, so an Archipelago seed's time
is unchanged.

## The flags grid fills itself in

FFR stamps the flag string it rolled with into the cartridge, so the settings
that used to need clicking -- Early King, the dock and pass flags, Sarda's
Forest, open progression, the incentive categories -- are read off the ROM and
applied when you load a seed.

A flag you left on "random" in the generator is the one thing that cannot be
read: the flag string records that it was rolled, not which way it landed, so
those stay on whatever the grid already had and the Script Window names them.

Clicking a flag afterwards sticks; only a new seed or the resync arrow stamps
over it. Seeds from an FFR version the pack has no schema for keep the manual
grid, and say so rather than guessing. `tools/ffr_flags/` has the offline version
of the same decoder, and the details.

## The board follows the game rather than accumulating

Loading an older save un-marks the chests it had not opened and walks items back
to what that save actually holds, and putting a different seed in the emulator
drops the previous one's board wholesale -- the bridge reports which cartridge is
loaded, so the tracker notices the swap without anything being re-run or
re-clicked.

It will not fight you over a section you clear yourself: **anything you clear by
hand stays cleared.**

Starting a new file on the same seed counts too: the moment the feed goes from
having checks to having none, the game has been started over and the board is
wiped to match.

The one exception is an Archipelago session. AP hands you items over the wire and
only replays them when you connect, so while `AP` is online the items it grants
are left alone rather than being second-guessed against cart RAM.

If the board is ever showing something it should not, the circular arrow in the
`Incentives` panel throws it away and rebuilds from the feeds. Nothing is lost by
pressing it while the bridge is connected -- chests, events and items are all
re-derived within about a second -- so it is the thing to reach for after updating
the pack, or if you want your own clicks cleared out. What it does not bring back
is a section you cleared by hand.

## Resetting costs the board nothing

Nothing needs re-running and nothing needs re-clicking. A soft reset leaves the
script running: tracking pauses for about half a second and then picks up where
it was. A power cycle does stop the script, but Mesen starts it again by itself
(`Auto-restart script after power cycle`, on by default) and PopTracker
re-connects within about five seconds and asks for the whole board back.

Neither one loses a mark either, though not because the game preserves anything:
every reset re-seeds its flag page to new-game defaults on the way to the title
screen. It also zeroes the byte the bridge uses to tell whether a save is loaded,
so the bridge stops reporting before that wipe can reach the tracker. Loading a
save copies the real flags back and the board fills in again.

## If it will not connect

`AP` and `UAT` are separate labels and you can have both connected at once. If
`UAT` stays grey, check that the script is actually running in Mesen -- the
Script Window log says which port it is listening on.

The two restrictions in `Script -> Settings -> Script Window -> Restrictions`
have to be set in order: `Allow access to I/O and OS functions` first, then
`Allow network access`, which does nothing until the first one is on.
