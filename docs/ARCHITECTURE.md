# How this pack fits together

Start here if you have not worked on this repo before. `README.md` says how to
use the pack as a player; this says how it is built and where to look for what.

## What it is

A PopTracker pack for Final Fantasy Randomizer, plus a set of offline tools that
read an FFR cartridge directly. Two separate things live in one repo because the
tools exist to feed the pack: they derive the maps, the marker positions and the
flag schemas that the pack ships.

It is a fork of SunflashRune/FFR_AP_autotracking. `main` is an untouched mirror of
that; everything here is on `trunk`.

## The two feeds, and why there are two

The pack tracks from two sources at once, and either one can run alone.

**Archipelago** connects to the multiworld server. It reports checked locations
and items received — and nothing else. `worlds/ff1/__init__.py`'s
`fill_slot_data` returns an empty dict, so there is no slot data at all. Chests
outside the multiworld pool, orbs lit, turn-in stages, the current map, the
seed's flags, the cartridge's identity and the run clock are all unavailable over
Archipelago by construction. Closing that gap means changing the Archipelago
world, which is a different repository.

**The Mesen Lua bridge** (`bridge/ffr_uat_bridge.lua`) reads the game's own
memory out of the emulator and publishes it over UAT. It covers everything
Archipelago cannot, which is most of what the pack knows. It also works on a
plain FFR async with no server anywhere.

`scripts/autotracking/reconcile.lua` takes the **union** of the two and preserves
anything cleared by hand. Neither feed is authoritative; a check reported by both
is counted once.

The practical consequence, and the thing most likely to mislead: **the repo is
named for the thinner feed.** If you are wondering why some setting is not
tracked over Archipelago, the answer is almost always that Archipelago does not
send it.

## The pack

PopTracker packs are four JSON trees plus Lua. `scripts/init.lua` is the entry
point and does the wiring in a fixed order — items, maps, logic, locations,
incentives, layouts, then defaults.

| Tree | Holds |
|---|---|
| `items/` | Everything with a state: key items, flags, shards, hosted toggles |
| `locations/` | The check tree — regions, locations, sections, access rules, map pins |
| `layouts/` | Window arrangement: item grids, map tabs, broadcast views |
| `maps/` | Map tab definitions — a name, an image, and default pin sizing |

### Variants

`manifest.json` declares **eight** variants, and `scripts/init.lua` picks which
files to load by matching `Tracker.ActiveVariantUID`. Two axes multiplied three
ways: standard vs shard hunt, standard vs No-Overworld, and with or without map
tabs.

The leading digit on each UID fixes its position in PopTracker's variant list. It
is also a trap: matching the bare string `shardHunt` with `==` matches none of
them, which once left every shard-hunt seed quietly gated on orbs. Use `:find`.

**Selection happens once, at load.** Nothing re-selects a variant at runtime, so
the player picks the right one from the pack chooser. The cartridge's own
`GameMode` is decoded (`scripts/autotracking/flag_mapping.lua`) but currently
only prints a warning when it disagrees with the chosen variant.

### The location tree

`locations/overworld.json` is the whole board — 283 locations holding 511
sections between them, and 283 map pins. `locations/incentives.json` is a
smaller sheet of just the slots a key item can be in.

The No-Overworld variants load their own copies from `locations/NOverworld/`.
Those exist because the *art* differs: a No-Overworld cartridge and a standard
one disagree about 34 to 39 of the 61 maps, so a marker's pixel coordinate
differs even when the location is identical. `tests/test_maps.lua` check 6
compares the two trees location by location so they cannot drift apart.

A section can carry `access_rules` (is it reachable), `visibility_rules` (does it
appear at all), `hosted_item` (a toggle it owns), `ref` (a cross-link to another
section) and `map_locations` (where its pin is drawn).

### Rules

Access rules are lists of alternatives, each a set of codes that must all be
present. There is no "and not", and no counting — so anything needing either
lives in `scripts/logic.lua` and is called from a rule as `$name`. Those
functions return `0` or `1` rather than booleans, because PopTracker reads the
return as an accessibility level and `0` is truthy in Lua.

A skipped slot is drawn **blue** (`AccessibilityLevel.Inspect`) rather than
hidden. That was a deliberate change: hiding a slot the seed did not reserve
took a real check off the board, and on a shard hunt that was nearly every check.

"Slot" means one of the sections `scripts/incentive_slots.lua` names and nothing
else. `^$incentiveSlot|<flag>` is ANDed only onto those, and only on the two
incentive sheets -- `grep -c incentiveSlot locations/*.json` gives 25 and 29 on
the sheets and **zero** on either dungeon tree -- so an ordinary chest cannot
come out blue. The 26 dungeon-tree rows in that table are there so
`scripts/incentives.lua` can ring them gold, not to demote them.

Blue is a statement about what the seed promised, not about what is in the slot.
FFR places a key item it did not pick as an incentive into the pool of locations
it did not reserve (`PredictivePlacement.cs:139-143,167,204`), and pushes
overflow incentive items into the same list when a seed rolls more of them than
it has incentive locations (`:178-181`). So a blue slot can hold a key item.

### Which pins can be switched off

The Pins group holds four toggles, all defaulting on. Three of them work through
a `restrict_visibility_rules` on a pin's `map_locations` entry, reading
`$showPin|<kind>` in `scripts/logic.lua`; the fourth, Incentive Rings, is Lua
only and hides nothing.

`restrict_visibility_rules` is the mechanism and not an implementation detail.
It hides one marker (`location.cpp:265-279`) and leaves the section in the tree,
in the counts, and clearable from the location list. Section-level
`visibility_rules` would take the check off the board, which is the thing
`tools/incentives_to_inspect.py` was written to undo -- so "an off switch must
not hide a check" is met by which field it is written to, not by care.

The rules are generated by `tools/pin_visibility.py` and never edited by hand.
`tools/regen_maps.py` calls the same `stamp()` on its own output, which is not
an optimization: `place_locations()` rebuilds every marker on a map it redraws
from the tile up, so an override written without it would carry none of these
rules, and the toggles would go quiet on exactly the seeds an override exists
for. Stamping rather than preserving is also what gives the pins a cartridge
newly places their rule on arrival.

`rule_for()` dispatches on the map name, and where it stops is the design:

    a drawn map      the pin's kind -- $showPin|chest or $showPin|npc
    incentives       $showPin|slot|<flag>... , the section's own flags
    overworld        nothing

The overworld is left out because one of its pins stands for a whole town at
once -- its chests, its NPC and its shop -- so no kind describes it, and a
player able to switch it off could empty the tab.

A node whose sections do not *all* carry an incentive flag gets no slot rule,
because the outer rule array is OR'd (`location.cpp:266`): an unflagged section
is visible whatever the flags say, so an entry for it would be always true. That
is what keeps the five orb slots on the sheet. For the same reason a rule ORs
the flags it names -- one live slot under a pin is reason enough to draw it.

`showPin` fails open. An undefined code counts zero exactly as a switched-off
toggle does, so a typo would empty a tab in silence; an unknown kind or an
unknown toggle draws the pin and prints once. The counts asserted in
`tests/test_pins.lua` are what say the failing-open path is not the one being
taken.

## The Lua

```
scripts/init.lua              entry point; loads everything in order
scripts/logic.lua             rules access_rules cannot express, and showPin
scripts/incentives.lua        gold rings on slots this seed incentivized
scripts/incentive_slots.lua   generated table of slot -> flag
scripts/settings.lua          three globals, no UI

scripts/autotracking.lua      the Archipelago feed
scripts/autotracking/
  uat.lua                     the bridge feed, and the pack's LuaItems
  reconcile.lua               the union of both feeds
  ram_mapping.lua             cart RAM -> codes (orbs, bosses, turn-ins)
  item_mapping.lua            AP item id -> code
  location_mapping.lua        AP location id -> section path
  flags_decode.lua            the FFR flag string -> settings
  flag_mapping.lua            settings -> board items
  maptab.lua                  follow the player between floors
  mapValues.lua               map id -> tab name

scripts/flags/                generated per-version flag schemas
```

### How the flag string is read

FFR stamps the flags it rolled with into the cartridge. The bridge publishes that
string; `flags_decode.lua` decodes it against a version schema.

The encoding is one large integer in FFR's own base-64 alphabet. Lua has no
bigints, so the value is carried as an array of digits and each setting is one
long division by that property's radix. The build SHA falls out last and is
checked against the schema's. **A mismatch refuses the whole decode** rather than
reporting settings shifted by one property — a wrong-but-plausible board is worse
than an honest blank one, and the flags-unread warning light says which happened.

Schemas ship for FFR 4-9-2 and 4-9-7, generated by `tools/ffr_flags/gen_schema.py`
from an FF1Lib checkout plus a real ROM. A new version is one command.

## The tools

`tools/` is offline Python that reads a cartridge. It is not part of the pack and
PopTracker never runs it. Nothing here has a dependency beyond the standard
library — no Pillow, no .NET.

| Tool | Does |
|---|---|
| `render_maps.py` | Draws all 61 maps out of a ROM using the game's own tile art |
| `regen_maps.py` | Renders, places every marker, and installs the result |
| `entrance_graph.py` | Reads the entrance/floor shuffle; routes; self-checks |
| `noverworld_rules.py` | Derives a No-Overworld seed's access rules from the walk |
| `doormap.py` | A clickable HTML page of the shuffle |
| `overworld_reach.py` | Walks the overworld for reachability |
| `check_logic.py` | Diffs the pack's access rules against FFR's own spoiler |
| `ffr_flags/` | The offline flag decoder and schema generator |
| `extract_chests.py` / `extract_npcs.py` | Chest and NPC tile positions |
| `pin_visibility.py` | Stamps the pin toggles' rules onto the location trees |
| `incentive_slots.py` | Writes `scripts/incentive_slots.lua`, the table the rings read |
| `sprites.py` / `font.py` | NPC sprite art and the cartridge's menu font |

**`regen_maps.py` writes to PopTracker's `user-override/` tree, never into the
repo.** That keeps rendered maps out of git and is also more correct, since
some map details are rolled per seed. The rule is about whole maps, not about
everything a cartridge can yield -- single sprites pulled by `sprites.py` or
`font.py` may ship as tracker icons; see the README. `--clean` puts the shipped
art back.

Two things to know before trusting any tool that reads maps:

- **Maps live in bank `$14`, not `$04`.** Every FFR seed relocates all 61 standard
  maps and repoints the engine's constants. Banks 4-7 keep untouched vanilla
  copies, so reading there does not fail — it returns a complete, confident,
  wrong answer. The same shape of trap exists for the talk jump table (`$11:8000`
  live, a vanilla copy left at `$0E:90D3`).
- **FFR's own `renderdungeon` is not an oracle.** It reads from the vanilla bank
  too, so it draws vanilla for every seed.

The cheap test that catches most routing mistakes: holding every item, all 61
maps must be reachable from the doors. `entrance_graph.py --self-check`.

**`check_logic.py` reads FFR rather than trusting the pack.** It takes the
requirement expressions FFR wrote down for a seed -- in its own spoiler, and in
the `rules:` Archipelago is handed -- pins the flag grid from the cartridge, and
compares the two as truth tables over the items they mention. It reports rules
that open a location FFR would not and rules that hold one closed FFR would open,
and it names what it could not map rather than counting it as agreement. Point it
at a seed, or let it find every ROM under Archipelago's output directory:

```
python3 tools/check_logic.py
```

One rule that reads like a mistake and is not: the `hwyOrdeals,ship,canal,canoe`
alternatives on Gaia, Lefein, Mirage Tower and Sky Palace. Those four sit on a
continent with no dock tile anywhere on it, so a ship cannot land there and FFR's
vanilla table says plainly `{MapLocation.Gaia, MapChange.Airship}`. The canoe is
what makes them reachable: it can be taken from the ship straight into a river
mouth, and there is exactly one river touching that continent, at overworld
`(134, 33)`. Highway to Ordeals and Gaia Mountain Pass then move you around
*inside* it -- neither is what gets you on.

So the reachability question for that continent is "does a river touch both the
ocean and this landmass", not "is there a dock". Walking the map to confirm also
needs the coast tiles (`0x06-0x08`, `0x16`, `0x18`, `0x26-0x28`) treated as
shoreline the ship enters *and* you can walk; making them purely land cuts the
ship off from the river mouth, and making them purely water severs the path up
the pass. Either way you get a false negative and four correct rules look like
false greens.

## What you need to work on it

- **Lua 5.4+** for the script tests. `tests/run.sh` needs nothing else — no ROM,
  no emulator, no PopTracker.
- **Python 3** for everything in `tools/`. No third-party packages: the map
  renderer, the font reader and the flag decoder are all standard library.
- **A Final Fantasy cartridge** for the tools that read one. Point `FF1_ROM` at
  it to run the full tool test suite:

      FF1_ROM="/path/to/Final Fantasy (USA).nes" ./tools/tests/run.sh

  Tests that need a cartridge **skip** rather than fail without it, so a bare
  `./tools/tests/run.sh` still passes and still checks less than you think. Any
  Final Fantasy image works, since the seed-specific layouts are synthesised —
  but a real FFR seed exercises strictly more.

## Tests

```
tests/run.sh         13 Lua suites. Needs only Lua 5.4+ — no ROM, no emulator,
                     no PopTracker. The APIs are stubbed; the scripts are real.
tools/tests/run.sh   12 Python suites for the cartridge-reading tools. Tests
                     that need a cartridge skip unless FF1_ROM points at one.
                     One slow guard opts in separately with FF1_SLOW=1.
```

Both are fast and neither needs a network. Run them before believing anything.

## Where the docs are

[`docs/README.md`](README.md) indexes them and says which page holds what.
`../README.md` is the one for using the pack rather than working on it.
