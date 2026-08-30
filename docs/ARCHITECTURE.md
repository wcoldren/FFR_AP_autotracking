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
hidden. That was a deliberate change: hiding a slot the seed did not incentivize
took a real check off the board, and on a shard hunt that was nearly every check.

## The Lua

```
scripts/init.lua              entry point; loads everything in order
scripts/logic.lua             rules access_rules cannot express
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
| `sprites.py` / `font.py` | NPC sprite art and the cartridge's menu font |

**`regen_maps.py` writes to PopTracker's `user-override/` tree, never into the
repo.** That keeps ROM-derived art out of git and is also more correct, since
some map details are rolled per seed. `--clean` puts the shipped art back.

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

## Tests

```
tests/run.sh         13 Lua suites. Needs only Lua 5.4+ — no ROM, no emulator,
                     no PopTracker. The APIs are stubbed; the scripts are real.
tools/tests/run.sh   8 Python suites for the cartridge-reading tools. Tests that
                     need a cartridge skip unless FF1_ROM points at one.
```

Both are fast and neither needs a network. Run them before believing anything.

## Where the docs are

```
README.md              using the pack
STATUS.md              the working log — what was built, and why
docs/ARCHITECTURE.md   this file
docs/NOVERWORLD.md     what the No-Overworld mode actually is
docs/ROADMAP.md        what is next, in order
docs/ISSUES.md         known defects and open questions
docs/IDEAS.md          unscoped, with the facts already attached
```
