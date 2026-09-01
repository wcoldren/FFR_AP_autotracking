# What No-Overworld actually is

Settled reference for FFR's No-Overworld mode (`GameMode 2`), derived from a live
cartridge and checked against FFR's own source. This is the stable half of what
was triaged in `STATUS.md`; the log there keeps the story of how it was found.

Everything below was verified on seed `F258553F` (FFR 4-9-2) and re-checked on a
4.9.8 seed. Where a number is quoted, it was measured rather than reasoned.

All of the mode is `FF1Lib/MetroidVaniaMap.cs`, entry `FF1Rom.NoOverworld()` at
line 47.

**This is not a description of the setting.** For what No-Overworld does to a
run as a player, read the FFR wiki or the preset itself. What is here is the
half a tracker has to model and cannot look up: the teleporter table, which
entrance rows have a tile, and what each gate NPC actually wants. Most of it
reaches no spoiler log, so the cartridge is the only source.

## The overworld is not removed

It is swapped for `nooverworld.ffm`, an ocean stub with nine one-tile pads around
`x 96-110, y 154-162` — the eight towns plus Coneria Castle. Confirmed off the
cartridge: of 32 entrance rows, only those nine have a tile on the map. The other
23 keep an ordinary map byte and no tile anywhere, which is why anything counting
"doors" has to ask `Graph.starts()` rather than filtering on FFR's spare pair.

## Everything else is a fixed table

A hand-authored table of **75 teleporters**, ids `0x41-0x8B`, at
`MetroidVaniaMap.cs:458-776`. 54 of the 61 maps are wired into it.

The mode is deterministic apart from three things:

- the three Cardia/Bahamut one-way gateways are permuted across Waterfall,
  Ice Cave B1 and Gaia (`:726`);
- the two Waterfall stair positions;
- which ToFR chest ids the two bonus chests reuse.

None of that reaches the spoiler log, so the cartridge is the only source. On the
reference seed, Bahamut is behind Gaia.

Measured across three seeds: **157 links each**, and the only differences are
those two rolled things. The other ~154 links are identical on every seed, which
is what makes a static connection diagram the right shape — the three gateways
want a `?` rather than a destination.

## The gates are NPCs standing in corridors

FFR's own logic model says which item each wants — `Sanity/SCMap.cs:218-226`,
which is the authority worth using over the dialogue, because the dialogue is
deliberately misleading.

| Routine | Wants | Stands on |
|---|---|---|
| `NoOW_Floater` | Floater | Coneria Castle 1F, Castle Ordeals 1F, Ice Cave B1 |
| `NoOW_Canoe` | Canoe | Crescent Lake, Elfland Castle, Castle Ordeals 1F |
| `NoOW_Chime` | Chime | Gaia (the robot, Gaia to Mirage) |
| `Talk_Nerrick` | TNT | Dwarf Cave |

CROWN and KEY gate tiles as usual. Ship and bridge are free.

**Two items are renamed, and only two** (`:844`): `ItemsText[Floater] = "SIGIL"`
and `ItemsText[EarthOrb] = "MARK"`.

There are two different things called MARK here and they are not the same item.
Say which namespace before answering, or the answer flips:

| | SIGIL | MARK |
|---|---|---|
| **the game's item screen** (`ItemsText`, `:844`) | Floater | **Earth Orb** |
| **the AP exporter's item name**, which is where the pack's `sigil` / `mark` codes come from | Floater | **Canoe** (`$6012`) |

So on the screen the player is reading, MARK is the Earth Orb. In the tracker's
codes — `scripts/autotracking/item_mapping.lua` and the `mark` RAM rule in
`ram_mapping.lua` — `mark` is the Canoe, because the pack follows the exporter's
names and the Earth Orb keeps its own `earthorb` code and its own box. The
Canoe NPCs' dialogue talks about "Lukahn's mark", which is flavour on both
readings; the item their routine checks is the Canoe.

This has been recorded backwards twice, in both directions, which is why it is
a table rather than a sentence.

None of this is a new tracker code. The pack already tracks every one of these
items — the mode needs new topology, not new codes.

The object-to-item map is **read, not transcribed**:
`entrance_graph.noverworld_gate_items()` reads the talk routine each object runs
and refuses to answer unless the eight objects sort into four routines wanting
four items, so a standard cartridge says "no gate layout" rather than inventing
one.

One thing deliberately left alone: `Talk_Nerrick` is the *vanilla* routine
(`MetroidVaniaMap.cs:833-834` leaves the `NoOW_Nerrick` assignment commented out)
and `SCMap.cs:214` gates it on TNT for every mode. So a standard cartridge's
router walks through Nerrick too. Changing that moves standard-mode answers.

## The Temple of Fiends Revisited is orphaned

Seven maps cannot be reached from the doors while holding every item: ToFR 1F,
2F, 3F, Earth, Fire, Water and Air. This is the cartridge, not a bug in the walk.

- On a **vanilla** cartridge `TempleOfFiends (20,17)` carries both a
  `TP_SPEC_4ORBS` special and a normal teleport. That pair is the time warp: the
  special gates on the four Orbs, the teleport moves you.
- On a **No-Overworld** seed the special is **stripped** and the teleport points
  straight at `TempleOfFiendsRevisitedChaos`. The mode skips the gauntlet and
  drops you at the Chaos fight.

Nothing else on the cartridge teleports into those seven, of any teleport kind.
`MetroidVaniaMap.cs` gives them a backdrop (`:942-948`) and a tileset
(`:1108-1114`) but no entry in its teleporter table. The chain runs
1F → Earth → Fire → Water → Air → Chaos and 1F → 2F → 3F, all of it flowing
toward Chaos, with no way in.

The reachability oracle excepts those seven by name and checks the reason instead
of waving it through: Chaos's own room still has to be reachable, since the
shortcut is what makes the seven unreachable. A seed that wires the gauntlet up
passes too.

### What the shortcut drops you into

Measured 2026-08-30. The warp lands at `tofrChaos (15,3)`, and on a
`ToFRMode = Short` seed there are seven chests in front of you: ToFR chest
indices 248-254, in a fixed block at cols 12-18, rows 1-2.

    vanilla                      0 chests on tofrChaos
    6BF0DEA9  ToFRMode 0 (Long)  0
    C189A0EF  ToFRMode 1 (Mid)   0
    72A52C25  ToFRMode 2 (Short) 7   cols 12-18, rows 1-2
    F258553F  ToFRMode 2 (Short) 7   the same positions, byte for byte

The enum is `Long / Mid / Short / Random` = 0-3, from the `ToFRMode` declaration
at the top of `FF1Lib/TempleOfFiends.cs` and the same mapping in
`tools/ffr_flags/schemas/4-9-2.json`.

So this follows `ToFRMode` and not `GameMode`: a *standard* Short seed has the
same seven. See `docs/IDEAS.md` for the Long/Mid/Short taxonomy and what else
Short moves onto this map.

**The lute gate is behind the chests, not in front of them.** Object 23 is
lute-gated and stands at `(15,5)`, two tiles past the landing spot, while the
chests sit at rows 1-2 on the near side. Nothing on `TempleOfFiends` gates the
warp -- `blocking_objects` there is empty with or without the Lute, because
object 23 is not on that map at all. The party warps in, takes seven chests, and
the gate stops them going deeper.

That is why seven ToFR locations derived as `(free)` — and that reading was
wrong. It asks where the lute gate stands and never asks what the Black Orb
does. `Sanity/SCMap.cs:167-186` gates the BlackOrb object's tile on the four
Orbs; the object stands at `TempleOfFiends (20,17)`; and FFR strips the
`TP_SPEC_4ORBS` *tile* special there while leaving the object
(`BlackOrb.cs:286`). **Not a No-Overworld edit** — every cartridge in the corpus
reads `0x80` at that tile, standard and No-Overworld alike, where vanilla reads
`0x92`. The walk modelled the tile and not the object, so it stepped through an
orb gate on every FFR seed. Fixed by `entrance_graph.black_orb_item()`, which
reads the requirement off the NPC's routine rather than assuming it: the stock
routine ANDs the four orb bytes, a shard-hunt seed compares a count instead, and
the reader refuses the latter rather than gating on orbs the seed never wants.
All seven now derive `orbs`.

**Chaos is behind both gates, and the key one is the second.** Walked
2026-09-01 from the same landing at `(15,3)`, on three Short cartridges —
`duck-104` and `practice-72A52C25` standard, `oracle-4.9.2/nov` No-Overworld —
all reading identically:

    holding      reaches   column 15 stops at
    nothing      31        row 4    the lute plate, object 0x17 at (15,5)
    key          31        row 4    the same; the Key alone buys nothing
    lute         33        row 6    the `0x3B` door at (15,7)
    lute + key   425       row 31   Chaos, objects 0x18-0x1a at (15,17-19)

`ShortenToFR` lays that door itself: `Put((0x0A, 0x00), landingArea)` with row
eight `31313030303B3030303131`, which puts `0x3B` at `(15,7)`, two rows past
the lute plate. So the shipped `lute,key` on the `Chaos` node is measured and
not conservative, and `EnableChaosRush` — whose whole body rewrites tile `0x3B`
in the ToFR tileset — is what lifts the Key half of it.

**The exit portal is an exit and nothing more.** `ExitToFR` is on in every
oracle cartridge, and on Short ToFR it writes a `PortalWarp` at
`tofrChaos (15,3)` (`TempleOfFiends.cs:398-409`) — which is exactly where the
time warp lands you. It reads `0x40`, `TP_TELE_WARP`, and is the only teleport
on that map, so it takes you out and creates no way in; `reachable_maps` only
follows `TP_TELE_NORM`. On a standard seed the warp lands on
`TempleOfFiendsRevisited1F (20,17)` instead and the portal goes there. It was worth checking precisely
because a final-floor chest reading as free from the start is the shape of a
walk stepping somewhere it should not -- here the geometry says otherwise.

## The full shuffle is off by default

It runs only with `Entrances` or `Towns` set. The stock preset ships both off, so
a default No-Overworld seed uses the fixed table above.

## Version drift is not the thing to worry about

Measured rather than assumed. Diffing FFR from the commit that first stamped
4.9.2 (Nov 2025) to 4.9.8 (May 2026) — six releases — the whole No-Overworld
surface moved by **one line**, and that line is a shop flag:

    FF1Lib/MetroidVaniaMap.cs | 3 ++-
    FF1Lib/Sanity/SCMap.cs        unchanged
    FF1Lib/Teleporters.cs         unchanged
    FF1Lib/StandardMaps.cs        unchanged
    FF1Lib/Enums.cs               unchanged

Generating a 4.9.8 seed and reading it with the same tools gives identical
numbers across six releases *and* a different seed:

    4.9.2  F258553F   stairs=157 gates=8 empty-handed=45/61 links=124 walkable=117 all-items=54/61
    4.9.8  F2585540   stairs=157 gates=8 empty-handed=45/61 links=124 walkable=117 all-items=54/61

The volatile surface is the **flag string**, not the topology — 4.9.8 adds five
properties and drops two, so a 4.9.8 seed genuinely cannot be read with the 4-9-7
schema. That has its own mechanism (`tools/ffr_flags/gen_schema.py`) and
regenerating is one command.

**No 4-9-8 schema is committed, deliberately.** A schema records the build SHA it
was proved against and the decoder refuses on mismatch, so one keyed to a local
fork build would never match a real 4.9.8 seed — dead weight that reads as
support. Regenerate from the release checkout when 4.9.8 ships.

The conclusion worth keeping: **derive from the cartridge, transcribe nothing from
C#.** A derived rule set re-derives on a new version, and that is worth more than
tracking upstream.

## Where the pack stands against this

- Map art can be drawn per seed and is filed by game mode, so a standard tracker
  and a No-Overworld one each show their own set.
- The gates are readable off the cartridge and the router stops at them. On the
  reference seed that moved maps-open-empty-handed from 47 to 45 and walkable
  floor links from 135 to 117 — eighteen staircases that a SIGIL, Canoe or Chime
  barrier actually blocks. The all-items count is 54 before and after, which is
  the check worth keeping: gates must not move that answer. Still 54 after the
  SubEngineer and Titan rows landed on 2026-08-30, and `test_gate_objects.py`
  asserts it rather than leaving it to a rerun.
- **The logic is still the standard-overworld logic.** `scripts/logic.lua`
  branches on shard hunt and nothing else, so a No-Overworld seed is gated on
  vanilla ship/canoe/canal/floater reachability — for a mode with no overworld,
  whose canoe and floater are not vehicles. This is the open defect; see
  `docs/ROADMAP.md`.
- Mode detection works and drives nothing but a warning.
