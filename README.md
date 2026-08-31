# FFR_AP_autotracking

An autotracker pack for Final Fantasy Randomizer, for black-sliver's
[PopTracker](https://github.com/black-sliver/PopTracker/). It tracks over
[Archipelago](https://github.com/ArchipelagoMW/Archipelago) and over a Mesen Lua
bridge, so it works on a plain FFR async too.

This is a fork of SunflashRune/FFR_AP_autotracking, and a personal project. I
picked it up to learn the randomizer from the inside -- how a seed lays out its
checks, how you read one out of the cartridge while the game is running, how the
entrance shuffle is stored -- and to see how far PopTracker's own features go. A
set of offline tools grew out of that and lives in `tools/`: a flag decoder, an
entrance router, a clickable door map, an overworld reachability walk, and a
renderer that draws the game's maps out of your own ROM.

The pack, the maps and most of the groundwork are other people's work. See
[Credits](#credits).

**It needs PopTracker 0.35.1 or newer.** Older versions refuse to load the pack
outright rather than loading it with less in it, so if it will not open, that is
the first thing to check.

## Setup

To use the pack, all you need is PopTracker. Put this directory in PopTracker's
`packs/` folder and pick one of the eight variants -- standard or shard hunt,
No-Overworld or not, with or without map tabs.

For the emulator feed, see [Autotracking from the emulator](#autotracking-from-the-emulator-mesen).

Working on it rather than using it needs a little more -- Lua, Python and
optionally a cartridge. See
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#what-you-need-to-work-on-it).

The map tabs work out of the box: the maps that ship with the pack are
hand-drawn, and need no cartridge and no emulator. Drawing them from your own
ROM instead is an optional upgrade -- see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

No ROM is included or downloaded, and none ever will be. Neither is any art
derived from one: `tools/regen_maps.py` writes into PopTracker's user-override
directory, never into this repo. The hand-drawn maps are not that -- they came
with the pack this forked, and their authors are in [Credits](#credits).

## What each feed can see

The **Archipelago feed** only knows about locations that are in the multiworld's
pool, because all it does is talk to the AP server. On its own it cannot see
chests outside the pool, orbs lit, items turned in, or shards from lighting orbs.

The **emulator feed** covers all of those, including the Sigil and Mark boxes on
the No-Overworld item grid. Those are renamed items rather than new ones, so they
are read from the bytes their originals already use and light on their own.
Nothing needs a manual click on the emulator feed today.

They run side by side. If a chest is in the AP pool both feeds report it and the
tracker counts it once.

## Autotracking from the emulator (Mesen)

FFR randomizes every chest, but Archipelago only ever sees the ones you put in
the pool -- and a plain FFR async has no AP server at all. `bridge/` holds a Lua
script that reads the game's own progress out of the emulator and feeds it to
PopTracker over UAT, which covers both cases.

This does not modify the emulator. It is one Lua script that Mesen runs.

1. In Mesen, open `Script -> Settings -> Script Window -> Restrictions`. Tick
   `Allow access to I/O and OS functions`, then `Allow network access`. Order
   matters -- the network checkbox does nothing until the first one is on. Both
   are off by default and only need setting once.
2. Load your ROM, then open `bridge/ffr_uat_bridge.lua` in the Script Window and
   run it. On macOS `bridge/launch_mesen_ffr.sh /path/to/seed.nes` does both in
   one go.
3. Load this pack in PopTracker and click the `UAT` label in the top bar. It
   turns green and reads `Online` once the bridge is connected, which can take up
   to five seconds.
4. Load your save. The bridge waits for a save to actually be loaded before it
   reports anything, so nothing is marked while you sit on the title screen.
5. Open a chest. It should clear in the tracker within a second.

Once connected it tracks chests and NPCs, Chaos, Garland and the Vampire, the
four orbs being lit, key items and every turn-in stage (Crown to Astos, Slab to
Unne and then Lefein, Ruby to the Titan, and so on), Bridge/Ship/Canal/Canoe/
Airship, and the shard count. It also times the run, fills in the flags grid from
the flag string FFR stamped into the cartridge, and follows you between floors.

**[`docs/BRIDGE.md`](docs/BRIDGE.md) has the rest** -- the run clock and what a
reset costs it, how the flags grid is filled in and what it cannot read, how the
board is kept honest across save loads and seed swaps, and what to check if `UAT`
stays grey.

## The map tabs

The bridge reports which map you are standing on, so the map tab follows you into
whichever floor you just walked into. `Auto-Tab` in the flags grid turns that off
if you would rather stay on the floor you are reading; it is on by default. This
needs the emulator bridge -- Archipelago on its own does not report your position
-- and only the two map variants have dungeon tabs to switch between.

Towns and the overworld land on one of the two overworld tabs, which are the same
art carrying different markers: `Incentive Locations` has the slots a key item
can be in, `Overworld` has every chest in the game as well. `Overworld Tab` in
the flags grid decides which. On `Auto`, the default, an Archipelago session is
asked what is in its pool, and a bridge-only one is asked what the cartridge
rolled -- a shard hunt, or key items allowed in chests, and it lands on the full
map, because on those seeds the chests are the run. Click it round to pin either
tab if you would rather decide yourself.

## What the pin colours mean

    gold ring    an incentive location this seed reserved -- an incentivized
                 item is here
    green        reachable
    blue         an incentive location this seed did not reserve
    red          not reachable yet
    dark grey    done

Gold and blue belong to incentive locations and to nothing else. FFR keeps a
fixed set of places it is allowed to guarantee something good in; each seed
reserves some of them and passes over the rest. An ordinary chest is never blue.
It is green, red or done, like any other check.

**Blue does not mean "nothing good here."** It means this seed did not promise
anything. A key item FFR did not pick as an incentive goes into the pool of
locations it did not reserve, and the blue ones are in that pool -- as is any
incentivized item left over when a seed rolls more of them than it has places to
put them. So a blue pin is a check like any other, with no promise attached
either way. The incentive map used to hide those pins outright, which on a shard
hunt took nearly every check off the board.

Red beats blue: a slot that is unreserved and out of logic reads as unreachable,
like any other check you cannot get to yet. Worth knowing if you run PopTracker
with `hide unreachable locations` on, since that will still hide it.

The colours themselves are PopTracker's rather than the pack's -- packs choose
which state a pin reports, not what colour the tracker paints it. If you want
different ones, they come from `colors.json` in your PopTracker config directory.

## Turning pins off

The **Pins** group in the left dock, under Incentives, has four switches. All
four start on, so a board you never touch is the board described above.

    Chest Pins               the 251 chest markers on the dungeon and town maps
    NPC Pins                 the NPC markers on those same maps
    Skipped Incentive Pins   the blue slots on the Incentive Locations tab
    Incentive Rings          the gold ring, without hiding anything

These hide *markers*, not checks. A hidden pin's location stays in the tree, in
the counts, and clearable from the location list -- switching Chest Pins off is
a way to read a crowded map, not a way to shorten the run.

Three things are deliberately not switchable. The overworld pins stay, because
one of them stands for a whole town -- its chests, its NPC and its shop at once
-- so no switch describes it and turning them off would empty the tab. The five
orb slots on the incentive sheet stay, for the same reason: each holds sections
the flags do not speak for. And Skipped Incentive Pins does nothing at all on a
shard hunt, or on a seed that allows key items in chests, because on those every
chest is a check and none of those slots is really being skipped.

## Maps

The dungeon maps are DarkmoonEX's, drawn and shared with the FFR community. The
same set is published in the wiki's chest-location appendix, which is the thing
to have open while you play:

<https://wiki.finalfantasyrandomizer.com/FFRGuide/Appendix_D/ChestLocations>

They carry a lot more than walls -- chests numbered per room, trap tiles keyed by
letter, optimal and loot routes, a legend on each one -- and the appendix has more
than one map for the floors a flag can reshuffle. Reading them as a specification
rather than as pictures is where most of the map work here came from.

Drawn for a vanilla layout, though. A seed that moves things is showing you the
right rooms and the wrong exits, and No-Overworld moves a great deal: it seals
every town's outer wall and stamps 75 new staircases across 34 maps.

So `tools/regen_maps.py` will redraw them from your own cartridge if you want
that -- your seed's maps, cropped to the part of each floor that is actually map,
with every chest where the ROM puts it, and rooms drawn open so you can see what
is in them. It reads the cartridge's game mode and keeps a standard set and a
No-Overworld set side by side, so each tracker variant shows its own. Nothing is
written into the pack: it all goes to PopTracker's user-override directory, and
`--clean` puts DarkmoonEX's art back.

    tools/regen_maps.py ~/Downloads/FFR_yourseed.nes

## Under the hood

Everything above is what the pack does. How it is built, what it models, how its
access rules are checked against FFR's own, what is measured and what is still
broken all live in **[`docs/`](docs/)** -- start with
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Credits

jat2980, DarkmoonEX, HaateXIII, SunflashRune and meklin89 built this pack and its
maps; black-sliver builds PopTracker. FFR itself is at
<https://finalfantasyrandomizer.com/>.
