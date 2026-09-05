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

**An AP location id is `512 + ObjectId` (`FF1Lib/Items.cs`), and only fourteen
ids above 510 exist.** `worlds/ff1/data/locations.json` — identical in all three
vendored Archipelago clones — holds 513 King, 516 Bikke, 518 Elf Prince, 519
Astos, 520 Nerrick, 521 Smith, 522 Matoya, 525 Sarda, 527 Lefein, 529 CubeBot,
530 Princess, 531 Fairy, 533 Canoe Sage and 767 Shop Item. The gaps are the
eight NPCs that hold no shuffled item — Garland, Princess1, ElfDoc, Unne,
Vampire, Bahamut, SubEngineer and Titan. Lighting those from RAM only is correct
rather than a missing `LOCATION_MAPPING` row: a row for one of them would map to
an id the server never sends.

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

**A grid's row count and its tiling are separate decisions, and only one of them
is free.** The docked strip takes its height from the tallest grid in it, so the
row count is load-bearing — shortening the item grids is what gives the map tabs
their height. The tiling within those rows is not: each row leads with a group
(orbs, key items, vehicles) and the two warning lights park at the end of row 1,
which is a readability choice and can move. A reflow that changes the row count
to fix how a grid reads is spending the maps' height on it; move the tiling
instead. `shared_item_grid` lost its row meanings to exactly that once and was
re-tiled to get them back at the same 26 cells, width and four rows.

Grid composition is decided off the cell lists rather than a screenshot, so it
wants looking at on a real board before it is trusted.

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
`GameMode` is decoded (`scripts/autotracking/flag_mapping.lua`) and lights the
`modeMismatch` warning when it disagrees with the chosen variant — reporting the
mode and the goal together, since a seed can be wrong on both at once. Selecting
the variant for the player is not expressible: `Tracker.ActiveVariantUID` is
read-only from Lua and `Pack::setVariant` is called once, from the load path.
`docs/BRIDGE.md` has the light; `docs/ISSUES.md` has the refusal.

### The location tree

`locations/overworld.json` is the whole board — 283 locations holding 511
sections between them, and 283 map pins. `locations/incentives.json` is a
smaller sheet of just the slots a key item can be in.

The No-Overworld variants load their own copies from `locations/NOverworld/`.
Those exist because the *art* differs: a No-Overworld cartridge and a standard
one disagree about 34 to 39 of the 61 maps, so a marker's pixel coordinate
differs even when the location is identical. `tests/test_maps.lua` check 6 is
written to hold the two trees in step, but the committed No-Overworld tree is
still byte-identical to the standard one, so today the check cannot fail for any
reason. It starts doing work the moment the trees legitimately diverge. Both the
copy and the check that cannot bite are in `docs/ISSUES.md`.

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
incentive sheets -- 26 gated sections on the standard sheet and 25 on the
No-Overworld one, and **zero** on either dungeon tree -- so an ordinary chest
cannot come out blue. The 26 dungeon-tree rows in that table are there so
`scripts/incentives.lua` can ring them gold, not to demote them.

A section can carry the term twice, because two of FFR's incentive conditions
are conjunctions rather than flags, so counting terms and counting gated
sections are different questions and the second is the one that means anything.
`tests/test_incentives.lua` holds both, and holds every alternative of a section
to naming the same set.

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
`visibility_rules` would take the check off the board, which is what a one-shot
rewrite had to undo once already -- so "an off switch must not hide a check" is
met by which field it is written to, not by care.

The rules are generated by `tools/pin_visibility.py` and never edited by hand.
`tools/regen_maps.py` calls the same `stamp()` on its own output, which is not
an optimization: `place_locations()` rebuilds every marker on a map it redraws
from the tile up, so an override written without it would carry none of these
rules, and the toggles would go quiet on exactly the seeds an override exists
for. Stamping rather than preserving is also what gives the pins a cartridge
newly places their rule on arrival.

`rules_for()` dispatches on the map name, and where it stops is the design:

    a drawn map      the pin's kind -- $showPin|chest or $showPin|npc
    incentives       $showPin|slot|<flag>... , the section's own flags
    overworld        nothing

The overworld is left out because one of its pins stands for a whole town at
once -- its chests, its NPC and its shop -- so no kind describes it, and a
player able to switch it off could empty the tab.

A node whose sections do not *all* carry an incentive flag gets no slot rule,
because the outer rule array is OR'd (`location.cpp:266`): an unflagged section
is visible whatever the flags say, so an entry for it would be always true. That
is what keeps the five orb slots on the sheet.

Within one entry the flags are ANDed, which is what lets a section spell out a
condition FFR computes rather than stores: the caravan's entry names both
`npcItems` and `npcsAreIncentive`, and a fetch NPC's is the same shape. The OR
a pin wants -- one live slot under it is reason enough to draw it -- is the
array's, so a node whose sections answer to different flags gets an entry
apiece. Naming them all in one entry instead asks for every slot at once, and
takes the pin away as soon as any one of them goes dark.

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
                              and has: the flags, and then the AP pool
scripts/incentive_slots.lua   generated table of slot -> flags, and the hosted
                              code that joins a slot to its AP location
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
| `entrance_graph.py` | Reads the entrance/floor shuffle; routes; self-checks; `--rolls` reads the two permutations no flag string carries |
| `noverworld_rules.py` | Derives a No-Overworld seed's access rules from the walk |
| `doormap.py` | A clickable HTML page of the shuffle |
| `lane.py` | Routes one floor: the cost model and the pathing primitive |
| `lane_edit.py` | A loopback page for drawing a floor's route by hand |
| `lane_file.py` | The authored lane's format, digest and refusal |
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

**`tools/lanes/*.json` is the stated exception, and it is one because those
files are an input rather than an output.** Everything else the rule covers is
derived from a cartridge, so throwing it away costs a regen; an authored lane
is a judgement about which chests are worth the detour, and nothing can
re-derive it. What keeps the exception honest is that the file carries a digest
of the floor it was drawn on and refuses to draw on a floor that does not match
-- so a committed lane can be wrong about a seed, but it cannot be quietly
wrong about one.

A layout entry carries one judgement besides the stops: **`retrace`**, whether
that floor's lanes should prefer their own edges and so collapse a loop into
one line. Per layout for the same reason the stops are, and absent by default.
`regen_maps.py --retrace {auto,on,off}` overrides every entry at once rather
than switching the feature; `docs/ISSUES.md`, "Is a loop worth collapsing?",
has why the answer cannot be one setting for the whole set.

It carries one piece of bookkeeping too: **`ported`**, true on an entry
`tools/port_lanes.py` carried from another cartridge and nobody has reviewed
yet. A carried lane is legal and may still be silly, so the distinction is real
work; without a key for it, a floor somebody opened and left alone looks exactly
like one nobody has opened, since a port has already written the cartridge into
`seen`. `lane_edit` clears it on save, so what is left to review is a query
against the files rather than a note in a doc.

Four things to know before trusting any tool that reads maps:

- **Maps live in bank `$14`, not `$04`.** Every FFR seed relocates all 61 standard
  maps and repoints the engine's constants. Banks 4-7 keep untouched vanilla
  copies, so reading there does not fail — it returns a complete, confident,
  wrong answer. The same shape of trap exists for the talk jump table (`$11:8000`
  live, a vanilla copy left at `$0E:90D3`).
- **FFR's own `renderdungeon` is not an oracle.** It reads from the vanilla bank
  too, so it draws vanilla for every seed.
- **A standard map is a torus.** `SMMove_Right` adds one to `sm_scroll_x` and
  masks `AND #$3F` — "and wrap at 64 tiles" (`bank_0F.asm:3070`) — and the other
  three directions do the same on their axis. A walk that stops at 0 and 63 seals
  pockets that the engine does not: SeaShrineB1 went 526 reachable tiles to 611
  when the wrap landed. It hid well, because wrapping adds tiles rather than
  maps, so the all-items oracle below could not see it and neither could any
  tool suite — every number stayed internally consistent. It took someone who
  had walked the room.
- **NPC positions are per seed.** FFR randomizes where an NPC stands, not only
  what it hands over: `titan` moves `(60,8,7)` → `(60,4,8)` and `nerrick`
  `(19,16,45)` → `(19,15,47)`. `npc_positions.json` is the vanilla reference and
  nothing more; a tool that resolves a node against it is deriving rules from
  vanilla tiles. `test_npc_pins.py` asserts the two disagree wherever the
  cartridge moves someone, so the claim cannot quietly come back.

The cheap test that catches most routing mistakes: holding every item, all 61
maps must be reachable from the doors. `entrance_graph.py --self-check`.

**All 61 is a No-Overworld statement, and on a standard seed a Long-ToFR one.**
`MetroidVaniaMap.cs` connects all 61 and drops none, so on No-Overworld a map
the walk cannot find is the tool's own fault -- that is what makes this a
theorem rather than a measurement. On a standard seed the count follows
`ToFRMode`: `MidToFR` never wires the two upper Temple floors in, so they are
not in the dungeon to reach and 61 is unreachable by construction. Quoted
without either precondition, the oracle reads as a failure on seeds that are
behaving. `docs/ISSUES.md` has the measurement and the case for deriving the
expected count from `ToFRMode` rather than hardcoding it.

### The derivations, and what pins each one

Four of these tools read art or geometry the ROM does not label. In each case
the base is derived from engine constants that do not know about each other, and
the agreement is the guard — an eyeballed offset that merely looks right has
none, which is how each of these was wrong once.

- **The sprite sheet origin.** `LoadMapObjCHR` adds the graphic id to the *high*
  byte of a pointer, so it is a page index: art for graphic *g* is the `$100`
  bytes at `lut_MapObjCHR + g * $100`, and `lut_MapObjCHR` is `$A200` in bank
  `$02`. Bank `$02` has no gap for a base to slide into — 12 + 6 pages from
  `$9000` land exactly on `$A200`, and 30 pages from `$A200` land exactly on
  `$C000`, where `render_maps.py` already reads the background tileset. Move it
  a page either way and one of them breaks.
- **The menu font base.** `LoadMenuCHR` points at `$09:8800` and loads 8 rows of
  16 tiles, so the font is the `$800` bytes there. `LoadMenuCHR` writes to PPU
  `$0800`, making its first tile background tile `$80`; FFR's encoding table
  independently says `0` is `$80`, `A` is `$8A`, `a` is `$A4`
  (`FF1Text.cs:174,184,210`). Those are `TEXT_BASE + CHARS.index(ch)` exactly.
  `test_font.py` also requires a base one tile or one row out to be *rejected*.
  `0` and `O` are one glyph — the font's own property, asserted so nobody
  tightens the check into "all 62 distinct".
- **The crop.** A 64x64 render is mostly not map. `content_box()` floods the
  border tile inward and takes the bounding box of what the flood cannot reach,
  padded a tile; mean 48% of the grid survives. Flooding rather than testing
  `tile == filler` is the whole point — Waterfall's `$46` is the open water
  outside the map *and* the room floor inside it, same tile, same property
  bytes, which defeated every per-tile test. A wall stops a flood; it does not
  stop a comparison. The guard is that the box cuts nothing off: every chest
  tile, every NORM/EXIT teleport and every tracked NPC survives it. WARP
  teleports are excluded because they *are* the filler.
- **Unroofing.** Ask the rendered tile whether it is blank, not the palette — a
  palette test finds a room's furniture, not the floor between it. `hidden_cells()`
  runs a palette test and an art test, each size-guarded on its own components,
  then unions them; neither may define a region alone. Both failure modes were
  found by asking *closer to the original maps, or farther?* — the art test alone
  merges separate rooms into one region that then fails the size guard, and
  seeding from the palette and flooding through art-blank cells runs away,
  because a room can touch a wall that is also art-blank.

The hand-drawn art is the acceptance test for the last two, not the input. The
derived crop lands within one tile of the box DarkmoonEX drew on 22 of the 30
calibrated maps with nothing tuned to make it happen, and the union leaves zero
walkable cells drawing flat white — the measurable form of "closer to the
shipped art", since the hand art never draws one.

**`doormap.py` reports a floor's whole staircase list, not the walkable half.**
Three things it got wrong are worth not reintroducing: it counted every entry in
the teleport table as a door rather than asking `starts()`, so it claimed 30
doors on a 9-door cartridge; it hid gated staircases entirely, so every floor
behind the Rod plate looked like a dead end rather than a floor with a locked
half; and `reachable_teleports` drops the tile it starts on, which is correct for
routing and made Coneria Castle 2F's way down report as gated. The page is read
as a local file, so it needs its `<meta charset>` or the arrows mojibake.

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
- **A Final Fantasy cartridge** for the tools that read one. Name it once in
  `verify.local.sh`, the untracked shell fragment beside `verify.sh` that holds
  the paths one machine happens to use:

      FF1_ROM=$HOME/path/to/Final Fantasy (USA).nes

  Then `./verify.sh` runs the full tool suite against it, and
  `./verify.sh --rom <other cartridge>` overrides it for one run. `FF1_ROM` is
  still read from the environment for CI, which has no such file — but do not
  write it as a command prefix. `FF1_ROM=... ./tools/tests/run.sh` is a
  different command from `./tools/tests/run.sh` as far as anything matching on
  the command goes, which is why the path lives in a file instead.

  Tests that need a cartridge **skip** rather than fail without it, so a bare
  `./tools/tests/run.sh` still passes and still checks less than you think. Any
  Final Fantasy image works, since the seed-specific layouts are synthesised —
  but a real FFR seed exercises strictly more.

## Tests

`./verify.sh` is the whole gate in one command: both suites, `check_logic` on a
No-Overworld and a standard cartridge, and whether the installed override still
matches the checkout. A stage that needs something this machine has not got --
a Lua interpreter, the oracle corpus, the cartridges in it, an Archipelago
checkout, an installed override -- reports SKIP rather than failing, and the
summary says a skip is not a pass. An override that is installed and stale is
an answer rather than an absence, and is the one thing outside the checkout
that fails the run. That is the thing to run before
calling anything done; what follows is what it runs.

```
tests/run.sh         14 Lua suites. Needs only Lua 5.4+ — no ROM, no emulator,
                     no PopTracker. The APIs are stubbed; the scripts are real.
tools/tests/run.sh   32 Python suites for the cartridge-reading tools.
                     Eighteen of them skip, wholly or in part, unless FF1_ROM
                     points at a cartridge, and three more unless FF1_SEEDS
                     points at the seed tree — so a bare run passes and checks
                     a good deal less than the count suggests. One slow guard opts in
                     separately with FF1_SLOW=1 and wants a No-Overworld
                     cartridge as well. One asks git rather than a cartridge —
                     the regen branch guard — and skips where there is no git.
```

Both are fast and neither needs a network. Run them before believing anything.

`check_logic` is the third stage because the access rules are one set serving
both game modes since the `noverworld-logic` merge: a change that satisfies the
standard tree can break the No-Overworld one, and only running both says which.
It exits non-zero when it finds a divergence, and `nov` is expected to find one
(`docs/ROADMAP.md`, "Five object gates, twelve items, and one divergence that
had been hiding"), so `verify.sh` compares the count against what the corpus is
known to produce rather than gating on the exit status.

## Where the docs are

[`docs/README.md`](README.md) indexes them and says which page holds what.
`../README.md` is the one for using the pack rather than working on it.
