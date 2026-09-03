# Known wrong, and open questions

Defects and unsettled questions, lifted out of `STATUS.md` so they are findable
without reading the whole log. The narrative — how each was found, what was tried
— stays there.

**A closed entry stays here, dated, and is not deleted.** Nothing re-reads a
closed defect, so an entry that goes quiet outlives its own fix and sends the
next reader after work already done — which is exactly how the first entry below
led this list for weeks after it stopped being true. Say a closed entry closed,
in it, on the day it closes. This is the opposite call from `docs/ROADMAP.md`,
and deliberately: that page is a plan and gets shorter as things land, this one
is a register and only earns its keep by holding the whole history of a defect.

Nothing here is urgent unless it says so.

## Known wrong

- **The Cardia islands had one standard-world route where Bahamut's Cave had
  two. Closed 2026-09-01**, by `73337dc`, `52ba9d5` and `15ac915` -- before it
  was diagnosed, which is why it is filed closed rather than fixed. Reported off
  `8EF791AA`: the Cardia chest pins were red while the Hoard was reachable. On
  the build being played, `Cardia Grassy` carried `$standardWorld,airship` and
  nothing else, while `Bahamut's Cave` already carried the Bahamut-dock
  alternative -- so on a seed with the dock and the hoard on, the cave went green
  and the islands beside it stayed red. Both states the report is consistent with
  leave the Cardia pins red: with Canal and Ship the cave is green and the
  islands red, which is the report as written; with Floater and Ship the cave is
  red too, so the Hoard being reachable in that state was seen in the game rather
  than on a pin. On the rules as they stand both states come out green throughout
  -- the islands through `15ac915`'s `BahamutHoard` alternative under Canal and
  Ship and through `73337dc`'s `airshipHike` one under Floater and Ship, the cave
  through `52ba9d5`. `9d55246` landed in the same batch and is easy to miscredit
  here: it wants `MapCardiaLandBridge`, which this seed has off, so it cannot
  fire on these flags at all.

  What makes it stay closed is `hoarddockhike497`, not the fix: the cartridge
  carries the three flags this entry turns on -- `MapDragonsHoard`,
  `MapBahamutCardiaDock` and `MapAirshipHike` -- on `std497`'s baseline rather
  than the played seed's whole flag set, and the rules that were being played
  grade **95 agree, 13 distinct divergences over 129 locations** against it,
  where the current ones grade 224 of 224. The combination was ungraded until
  now because the corpus had `hoarddock497` and `hoardhike497` and not the pair
  together -- and the pair turns out to be the plain union of the two, which
  `hoarddockbridge497` had established is not something a pair can be assumed to
  be. `docs/ORACLE.md` carries both rows.

- **The No-Overworld variants ran standard-overworld logic. Closed 2026-08-30.**
  This entry led "Known wrong" for weeks saying `scripts/logic.lua` "branches on
  shard hunt and nothing else", and it had not been true since the
  `noverworld-logic` merge. `isNoOverworld()` in `scripts/logic.lua` matches
  `Tracker.ActiveVariantUID` with `:find`; `noOverworld()` and `standardWorld()`
  feed the 25 region rules that replaced the overworld geography, so one set of
  rules serves both modes rather than two trees that must agree and never get
  compared. Named rather than numbered: this entry cited three line numbers that
  had all moved by 2026-09-01.

  The entry is kept rather than deleted because of *how* it went stale: nothing
  re-reads a closed defect, so a "largest live defect in the pack" line survives
  its own fix and sends the next reader after work already done. When a Known
  wrong entry closes, say so in it the same day.

  What is genuinely left on this mode is smaller and is filed separately:
  **Lefein**, the one `--derived` divergence, below; the **committed dungeon
  tree** still being a copy of the standard one; the poster's missing
  **`nerrick`** slot; and the **Gaia** rule the two trees disagree about. None
  of them is a mode guard.

- **The walk models all five object gates the cartridge has. Closed
  2026-08-30.** `FF1Lib/Sanity/SCMap.cs:167-186` gates **five** object ids by
  tile, in one switch: RodPlate `0x16`, LutePlate `0x17`, BlackOrb `0xCA` →
  orbs, SubEngineer `0x10` → oxyale and Titan `0x14` → ruby. All five are
  ordinary map objects standing on chokepoint tiles, and the walk now blocks all
  five. `GATED_OBJECTS` holds the two plates; `black_orb_item()` and
  `object_gate_items()` read the other three off the cartridge per seed.

  This entry used to say Oxyale and the Ruby were "game rules" the sweep could
  not see, and that was wrong twice over. They are graph properties, and
  `orbs` — what BlackOrb wants — had been in the swept vocabulary all along, so
  every sweep to that date walked through an orb gate as though it were not
  there. BlackOrb closed first; it was why seven ToFR locations derived as free,
  and they derive `orbs` now. The last two closed the same day, together with
  the vocabulary widening they needed: a `GATED_OBJECTS` row whose item the
  sweep cannot hold blocks that tile in every subset, so the row and the item
  have to land in one commit or everything behind the gate derives as
  unreachable rather than gated. `ITEM_NAMES` is twelve items and the sweep is
  2^12.

  What that bought is on the measurement rather than on the map: the
  off-vocabulary grant `check_logic --derived` hands both sides fell from 164 of
  `nov`'s 222 comparisons to **5 of 226**, because Oxyale and the Ruby were 161
  of those 164. See `docs/ORACLE.md`.

  The genuinely non-graph requirements are the *trades*, and half of those are
  already read: `entrance_graph.talk_item_requirements()` takes them off the
  talk table — Astos's Crown, Nerrick's TNT, the Smith's Adamant, Matoya's
  Crystal, Unne's Slab, the Elf Doctor's Herb, and Titan's Ruby. `Bottle`
  remains, and so does the Lefein man below.

- **The derivation cannot say "reach another location", and Lefein is where
  that shows.** Found 2026-08-30, when dropping the Ruby grant uncovered it:
  FFR's rule for Lefein is `(Tnt OR Ruby OR Canoe) AND Floater AND Slab`, and
  the derivation says `floater` alone. It is the only divergence left in
  `--derived` on either No-Overworld cartridge.

  Both sides are right about the geography. Lefein town is two teleports from
  the party's start — Coneria Castle 1F `(2,8)`, behind the SIGIL barrier, to
  Waterfall `(57,56)`, then Waterfall `(25,28)` to Lefein — and FFR agrees, its
  Waterfall chests wanting `Sigil` and nothing else. The extra `Tnt OR Ruby OR
  Canoe` is the requirement for reaching **Melmond**, because the Lefein man
  wants the Slab *translated*: `Sanity/SCLogic.cs:555-557` resolves an NPC
  gated on the Unne flag to Dr Unne's own reachability ANDed with `Slab`.

  That is a requirement naming another location, and the sweep's vocabulary is
  items. Nothing here is a small fix — it is the general requirements solver in
  `docs/IDEAS.md`, or a second pass that resolves NPC flags to the reachability
  of the NPC that sets them. Filed rather than fixed; the divergence is
  permissive, so the derived rules open Lefein earlier than FFR does.

  One thing this contradicts, and the contradiction is only about
  No-Overworld: `check_logic.WAIVED` used to say the pack is stricter than FFR
  at Lefein "because Unne is reachable whenever Lefein is". That holds on a
  standard overworld and does not hold here, where the Waterfall route reaches
  Lefein without going near Melmond — and the waiver *is* applied here, on the
  `--ap-rules` run for both No-Overworld cartridges, so the reason was being
  stated where it was false. What the waiver concludes survives: FFR's rule
  already requires reaching Unne, because `SCLogic.cs:555-557` resolves an NPC
  gated on the Unne flag to Unne's own reachability, and on No-Overworld that
  resolution is exactly the `Tnt OR Ruby OR Canoe` term above. So the step the
  pack shows and FFR folds in is still always takeable, and only the rationale
  needed correcting — done 2026-08-30. Clearing the waiver instead would report
  Lefein as a divergence on every cartridge, standard included.

  A second, smaller gap sits behind the same NPC. `talk_item_requirements()`
  finds no requirement for the Lefein man `$0F`, though his byte reads `$0B`
  (Slab): his routine consults it as `A4 74` / `JSR $9079` — LDY tmp+4 into a
  subroutine — rather than the `A6 74` / `BD 20 60` pair the reader matches.
  Closing that would AND the Slab into the derived rule; it would not close the
  divergence above, since the Slab is granted to both sides anyway.

  **There is a second instance of this class, and it is silent rather than
  reported: the Elf Prince.** Found 2026-08-30 while listing which of `nov`'s
  226 comparisons the sweep does not independently support. FFR's rule is
  `(Herb)` on both No-Overworld cartridges and `(Herb AND Ship) OR (Canoe AND
  Herb)` on the standard one; the derivation says **`(free)`**. The mechanism is
  the Lefein one exactly -- `SCLogic.cs:559-562` is
  `allNpcs[ElfDoc].Restrict(SCRequirements.Herb)`, structurally identical to
  `:555-557`'s Unne/Slab -- and there is a second, more mundane reason it
  misses. `talk_item_requirements()` puts the herb on object **`$05`, the Elf
  Doc**, while the `Elf Castle Elf Prince` node resolves to object **`$06`**, so
  `noverworld_rules.py:395` finds no trade for that node and ANDs nothing in.
  Smith `$09` -> adamant and Matoya `$0A` -> crystal are hosted by the node
  their requirement sits on and both derive correctly, which is what makes the
  Elf Prince the odd one.

  **The shipped tracker is not affected.** `locations/NOverworld/overworld.json`
  ships `access_rules: ["herb"]` and agrees with FFR; this is the derivation
  alone. What it costs is a claim: the "requirement names another location"
  class was recorded as one location of 226, and it is two. Lefein is at least
  loud -- it shows up as the one `--derived` divergence. The Elf Prince does not
  show up at all, because `herb` is outside `SWEPT_ITEMS` so `check_logic`
  grants it to both sides and the comparison passes as agreeing. A silently
  permissive rule is the worse of the two, and it argues for widening the swept
  vocabulary before trusting the "225 of 226 agree" figure as coverage.

- **`ShuffleObjectiveNPCs` moved two cells and nothing in the pack knew. Closed
  strictly 2026-09-01, the day it was found.** Found and closed 2026-09-01. `NPCs.cs:135` runs the shuffle when `ChestsKeyItems` is also
  on and the mode is not Deep Dungeon, and `NPCs.cs:277` permutes Bahamut, Dr
  Unne and the Elf Doctor across BahamutCave2, Melmond and Elfland Castle.
  Measured on `objnpc497` — `std497` plus this one flag — with
  `tools/extract_npcs.py`: Bahamut moved to Melmond and Unne to BahamutCave2,
  the Elf Doctor stayed.

  The pack hosts `bahamut` under `Cardia Islands/Bahamut's Cave`, gated on the
  airship, and `slabTranslated` under `Melmond Continent/Melmond/Dr Unne`. On
  that cartridge the first is held red while Bahamut is reachable early and the
  second reads reachable while Unne is behind the airship. **The second is the
  over-reporting direction**, which is the one that matters.

  Nothing grades it. Of the 204 rules `std497` and `objnpc497` share, exactly one
  moves, and it is `Shop Item` — roll noise, the same row the `ShipDrydock` diff
  hit for the same reason. `Elf Prince` and `Lefein` are byte-identical across
  the two, so the pack scores 224 of 224 on a seed it is wrong about. This is the
  `NoTail` case: the export cannot see the branch and the lying cell is the
  pack's own.

  **The close is the strict one and not the right one.** With the flag on, both
  cells now ask for all three homes at once, which collapses to Bahamut's Cave
  because it dominates the other two under every one of its alternatives.
  `$noObjectiveShuffle` in `scripts/logic.lua` is the guard, `check_logic`
  answers it the same way, and `tests/test_ram.lua` demonstrates it opening and
  closing.

  What that costs: on a shuffled seed the pack now holds the Elf Prince where
  FFR opens him, because FFR wrote the seed and knows where the Elf Doctor went.
  That is a deliberate disagreement rather than an agreement, so it lives in
  `check_logic`'s `WAIVED` table and stays printed. `bahamut` needed no change —
  it was already gated on the home that dominates.

  The right fix is unbuilt and is shared with the Cardia gateway roll: teach the
  bridge to publish the permutation that `tools/extract_npcs.py` already reads.
  `docs/ROADMAP.md` holds it as one item rather than two.

- **Titan has a box now.** Closed 2026-09-02. The obstacle was a name rather
  than a signal: `titan` was taken by `ruby` stage 2, so a cell could not host
  it — `FindObjectForCode` would have handed back the Ruby, and the box would
  have read as cleared whenever the Ruby was spent. The fix was to free the
  name rather than work around it. No access rule ever asked for that second
  code, so renaming it to `rubyDone` cost nothing and is what lets the section
  host the literal `titan`, which is what `extract_npcs.WANTED` calls object
  `$14` — so the pin, the object-gate id and the `npc` classification all join
  with no alias taught to `regen_maps.py`, `noverworld_rules.py` or
  `pin_visibility.py`. `$6214` is read twice, once as `ruby` stage 1 and once
  as `titan`, the way `sigil` and `mark` already read the Floater and the Canoe.
  Bridge-only: Titan is not an Archipelago location.

- **Five NPCs the cartridge places have no box anywhere.** Fifteen of the twenty
  objects `extract_npcs.WANTED` reads have a pin; Unne and the four fiends host
  no section in the location tree, so there is no location a pin could belong
  to. It was six until Titan got his box above; the fiends write no flag that
  could be autotracked at all; Unne holds no shuffled item, and carries the same
  code clash Titan had (`slab,slabTranslated,unne`), resolvable the same way if
  that decision is ever revisited. Each would be a
  manual-click cell, which is a decision rather than an omission — written down
  so it stops reading as a gap in the NPC pins. Reaffirmed 2026-08-30 when the
  pins moved to the cartridge and the other six gained boxes; nothing measured
  in that pass argues for adding these.

- **14 of the 245 shipped images are referenced by nothing.** Counted
  2026-09-01 by grepping every tracked file for `images/...`. They are
  `flags/airBoatOFF.png`, `flags/noOpenProgression.png`, `items/airorb.png`,
  `items/masmune.png`, `items/ribbon.png`, six under `locations/`
  (`earthRod`, `seaShrineKey`, `skyPalaceChime`, `skyPalaceCube`, `volcano`,
  `volcanoArmory`), `misc/gil_shop_item.png`, `misc/northernDocks-old.png` and
  `misc/unne.png`.

  Recorded rather than deleted, and the distinction is the point. Most are
  inherited from the pack this forked and credited in the README; a few name
  things the pack decided differently about (`items/airorb.png` lost to the
  `orb-air-no`/`orb-air-yes` pair, `flags/airBoatOFF.png` to PopTracker's own
  disabled-image filter). `misc/unne.png` is the odd one out and is worth
  keeping on purpose: it is the art for a box `docs/ROADMAP.md` §2 has not
  decided whether to add.

  They cost nothing but the bytes, nothing loads them, and removing another author's art
  from a fork on a tidying impulse is not a change worth making without a
  reason. If one is ever wanted, it is here.

- **17 maps have no markers on the shipped hand-drawn art.** 16 were never
  calibrated and `ConeriaCastle2F` is a composite the schema cannot address. This
  is a limit of that art only: markers on redrawn art are built from the
  cartridge and every map has them. Solving the 16 offsets by hand would only
  benefit a player who never runs `tools/regen_maps.py`.

- **The incentive defaults are still a guess** on a version with no schema. The
  warning light says so, but the toggles stay on whatever `scripts/init.lua` set.
  They cannot simply be cleared: an Archipelago-only player never receives a flag
  string at all, since only the bridge publishes one, so an empty default board
  would be wrong for every AP session. The guess is more visible than it was — it
  now decides which pins are gold and which are blue, rather than which exist.

- **`hide unreachable locations` still hides a skipped slot that is out of
  logic.** PopTracker drops an unreachable pin before anything gets to say it is
  blue, and red outranks blue by design. Nothing to do in the pack; worth knowing
  if that setting is on.

- **`shopItem`** is the one Locations-grid cell with no incentive toggle behind it
  and no FFR flag mapped to it, so it is never blue and never gold.

- **Our trap letters are not DarkmoonEX's**, by design. His are hand-assigned for
  vanilla and do not describe an FFR seed; ours are read per cartridge. Only
  cross-referencing a letter against his guide is unsafe.

  This used to say ours are "self-consistent per map", which is true and is also
  the whole problem — see the next entry. Once the marks are keyed to the
  formation they become self-consistent per *cartridge*, which is the stronger
  claim and the one worth making.

- **The same enemies could carry two different trap letters. Fixed.**
  `trap_letters()` numbered by `(tileset, tile)` enumeration order rather than by
  the formation the tile spawns, so one formation reached through two tileset
  entries got two labels. Measured 2026-08-30, three formations on each oracle
  cartridge: on the std seed formation `$10` was drawn **G** on `earthB1` and
  **W** on `marshB3`; `$1C` was AA and AG; `$4A` V and X.

  That defeated the thing a trap mark is for. Meet a fixed formation early,
  decide it is worth fighting or worth avoiding, and the label it carried the
  next time you met it might be a different one.

  The same enumeration is why labels ran to two characters. 38 distinct labels
  existed on the std cartridge, so everything past index 25 became AA…AL — seven
  maps carried one, `tofrChaos` read AG AH AI AJ across eight tiles in a row and
  `seaB4` read AB AC AD AE, and at two tiles wide a label no longer says which
  tile it marks.

  Both closed together, by keying the mark to the formation id and handing marks
  out only to the formations that stand on a map. `render_maps.trap_marks()`
  does that; `standing_formations()` is the order. Over five cartridges —
  vanilla, std, nov, nov2, shard — every mark is a single glyph, no formation
  carries two and no mark stands for two. 32 formations stand on a map (31 on
  nov and shard) against 35 single glyphs in `0-9A-Z` once `O` is dropped, since
  `tools/font.py` asserts `0` and `O` are the same glyph in the cartridge's font.
  `seaB4` reads `0 1 Y Z` where it read `AB AC AD AE`.

  **It costs the exact agreement with the shipped art, by one place.** The art
  counted formation `$00` — five fixed tileset entries no map places — so
  DarkmoonEX's `earthB1` `{G,H,I}` is this scheme's `{F,G,H}`. `test_crop.py`
  asserts the shift and names its cause rather than pinning the output.

- **A room bigger than the guard stays shut.** Mirage Tower 1F's interior is 458
  cells and `ROOM_MAX_CELLS` is 256, so it does not open. Raising the cap is not
  the answer — the same test finds Waterfall's 1820-cell floor and Volcano B4's
  2650, which are open floor and must stay closed. The door-flood rule handles
  it (353 cells) and is unioned in; what is still unresolved is that on 49 maps
  the union opens cells the flood does not, and ToFR Air has exactly one door
  tile for 241 such cells. Understand what those are before replacing the rule.

- **Crop boxes are looser than the map on several tabs.** Two causes, not one.
  This entry used to name a single one — "stray detached tiles out near the
  boundary hold the frame open" — and **that is wrong for the five worst maps.**

  **The seam. Fixed.** A standard map wraps at 64 tiles (`AND #$3F`, and
  `entrance_graph.floor_walk` already models it). `content_box` did not: it took
  an axis-aligned bounding box in un-rotated coordinates, so a map whose content
  straddles column 0 or row 0 was framed across the void between its two halves.
  `render_maps.content_crop` slides the grid first — the widest empty run goes
  off the end — and boxes what is left. Measured over all 61 maps of the std and
  nov oracle cartridges, which give **identical answers** — the wrap is a
  property of the map, not of the seed, so there is no separate No-Overworld
  audit here:

  | map | boxed before | after the slide | where the content actually is |
  |---|---|---|---|
  | `con_castle` | 64x35 | 31x35 | cols 62-63 + 0-26; the 35 blank columns are 27-61 |
  | `crescent_lake` | 52x64 | 52x43 | rows 58-63 + 0-34 |
  | `melmond` | 45x64 | 45x44 | rows 51-63 + 0-30 |
  | `elf_castle` | 28x64 | 28x35 | row 63 + 0-31 — wrapped by a single row |
  | `sky4F` | 64x64 | 60x59 | a 4x4 tiling of rooms, straddling both axes |

  `con_castle`'s 35 columns are the number this entry always carried; only the
  cause was wrong.

  **`sky4F` moved here from the residue below, against this entry's own
  prediction.** It was filed as a multi-lobe map that rotating "would put the
  left half on the right and make things worse". Rendered both ways, that is
  backwards: the map is a regular 4x4 tiling of identical rooms, so re-phasing
  it cannot swap anything distinguishable, and the un-slid frame *cuts four of
  the sixteen rooms in half* against the top, left and bottom edges. Every room
  is whole after the slide -- checked as a count rather than by eye: sixteen
  torus-connected regions of 88 cells, all sixteen entirely inside the box. The
  prediction was made from the gap list rather than from the image.

  **The slide was switched off again for a fortnight, by the speck rule, and
  the table above went stale with it.** `components()` flooded without
  wrapping, so a region straddling the join split in two and the smaller half
  was dropped as a speck; dropping it removed index 0 or 63 from `occupied`,
  the join test stopped firing, and `melmond`, `elf_castle` and `sky4F` all
  fell back to shift `(0, 0)`. `sky4F` was then clipping *seven* of sixteen
  rooms -- worse than the four this entry set out to fix. Neither suite
  noticed, because nothing the map points at stands on the shaved strips.
  Fixed by wrapping the flood; the rows above are measured against that.

  **The residue, which is the original diagnosis and still stands.** `onrac`,
  `lefein` and `seaB1` have **no empty column at all** — a sliver of one to three
  cells per column runs the full width and holds the frame open (`lefein` rows
  33-47, `seaB1` cols 32-63). `iceB2` (8-column interior gap) and `iceB3` (18)
  are genuinely multi-lobe: their content does not reach the join at all, so the
  slide correctly leaves them where they are, and boxing them tightly would put
  the left lobe on the right. Still deliberately not fixed by adding another
  per-tile proxy — walkability and size were both tried and rejected. The shape
  of a real answer is the one the room work landed on: ask what a region is
  connected to, not what its tiles look like. Insets would dissolve it, and
  `docs/IDEAS.md` names these maps under that heading.

- **The standard-seed reachability oracle is stated without its precondition.**
  It is recorded in several places as "on a Standard seed, `--have
  key,crown,cube,orbs` reaches all 61 maps". Measured 2026-08-30 on two standard
  seeds: that set reaches 52 of 61, and every item reaches 59, with
  `TempleOfFiendsRevisited2F` and `3F` unreachable.

  **That is correct behaviour, not a gap.** Both seeds roll `ToFRMode = Mid`,
  and `MidToFR` (`FF1Lib/TempleOfFiends.cs:138-153`) repoints 1F's left stairs
  straight at the Earth floor and blocks the passages to Stairs B. 2F and 3F are
  never wired in, so they are not in the dungeon to reach. Only `ToFRMode = Long`
  can reach all 61.

  The oracle needs its precondition attached wherever it is cited: **all 61 maps
  is a Long-ToFR statement**, and the item set has to be every item rather than
  `key,crown,cube,orbs`. Better still, derive the expected count from `ToFRMode`
  rather than hardcoding 61.

- **`ChestsKeyItems` is a seven-chest flag, and the pack describes it as a
  general one.** `scripts/autotracking/maptab.lua:65-66` glosses it as "FFR's
  'key items may be placed in chests' -- with it on, an ordinary chest can hold
  the thing that opens the run", and `cartridgeChestsAreChecks()` uses it to
  decide the full overworld tab is worth landing on. That conclusion is fine;
  the description is looser than the cartridge. `ItemLocations.Lists.cs:178-181`
  names exactly seven locations -- `MarshCaveMajor`, `ConeriaMajor`,
  `EarthCaveMajor`, `IceCaveMajor`, `OrdealsMajor`, `SeaShrineMajor`,
  `SkyPalaceMajor` -- and with the flag off `PlacementContext.cs:260` forces
  those seven to their vanilla contents. So the flag opens seven named chests,
  not every chest.

  Not urgent, and it does not change any pin: the tab decision only asks whether
  chests are worth watching, and seven key-item chests is a yes. What it costs
  is anyone reasoning from the comment. Found 2026-08-30 while settling what
  blue promises; the same reading is what corrected the README.

- **A stale override silently shadows pack edits, and a missing layout key says
  nothing at all.** `regen_maps.py` writes `layouts/shared.json`, the four
  location files and `maps/*.json` into PopTracker's `user-override/` tree, and
  `Pack::ReadFile` consults that tree ahead of the checkout. So editing any of
  those in the repo has no effect at all while an override written before the
  edit is installed -- the tracker goes on serving the older copy, and nothing
  reports the divergence.

  The layout case fails worst, because it fails quietly.
  `Tracker::getLayout` returns `blankLayoutNode` for a key it does not have
  (`tracker.cpp:791-794`) with no warning, so a `{"type": "layout", "key": ...}`
  pointing at a key the override's `shared.json` predates renders an **empty
  group** -- a header with nothing under it and no message anywhere.

  Demonstrated 2026-08-30 rather than reasoned: adding `shared_display_grid` to
  `layouts/shared.json` and referencing it from the four map trackers produced
  an empty "Pins" group on an override written the day before. Re-running the
  regen fixed it, because `build_layouts()` rebuilds the override's copy from
  the checkout's.

  This is **not** the cartridge mismatch `docs/IDEAS.md` describes under "Notice
  when the drawn maps are for a different cartridge". There the ROM differs;
  here the ROM is identical and the *pack* moved on.

  **Detected on demand since 2026-08-30**, by the comparison that was already
  sitting in the cache: `.regen_cache.json` stores `inputs`, a sha256 over
  `INPUT_FILES` (`regen_maps.py:126-151`), which lists `layouts/shared.json` and
  all four location files, so the fingerprint moves on exactly this edit.

  **`inputs` was one fingerprint for both modes until 2026-08-29, and that was a
  hole of its own.** `rom`, `npcs` and `marker` were already per mode; `inputs`
  was kept once for the whole tree, so regenerating either mode stamped the new
  fingerprint over both. The other mode's art stayed on disk exactly as the
  older tools drew it, and its next run compared that shared fingerprint, found
  it current, and did nothing. Every renderer change since the modes split had
  this hole; it only surfaced on one that changes pixels somewhere easy to test
  -- the Map Key band reading as one colour rather than three. `inputs` lives in
  each mode's slot now, for the same reason `rom` does.

  The cache version was deliberately **not** bumped when that moved.
  `load_cache` treats a version change as "clear every file the old cache
  lists", which would delete the other mode's art without redrawing it. A cache
  written before the split simply has no per-mode fingerprint, so that mode
  reads as stale and redraws once -- the right answer, reached by doing nothing.
  `tools/regen_maps.py --verify` reads it -- no cartridge, no rendering, a few
  milliseconds against a regen's six seconds per cartridge -- and exits 1 naming
  the stale modes. It is silent where no override is installed, because that is
  not a stale one.

      tools/regen_maps.py --verify

  Deliberately **not** in `tools/tests/run.sh`. Both suites are documented as
  needing nothing outside the checkout, and this answers a question about the
  machine's PopTracker install rather than about the code: a developer with a
  stale override would get a red suite for something no commit can fix. Run it
  when the tracker looks wrong, and after touching anything in `INPUT_FILES`.

  Still open: nothing checks at *tracker load*, which is the moment it matters,
  and the pack's Lua cannot -- PopTracker exposes no layout query and no file
  read, so the pack cannot see either the override's `shared.json` or the cache.
  Closing it properly is a PopTracker change, a warning from `getLayout` on the
  key it could not find.

  Workaround for the remaining gap: re-run `tools/regen_maps.py` after touching
  any file in `INPUT_FILES`, once per mode, or `--clean` the override.

  **Guarded in `start_session.sh` since 2026-09-02**, which is the other half
  of this and fails in the opposite direction. Guarded there and only there:
  the workaround in the paragraph above runs `tools/regen_maps.py` by hand,
  which records the branch but does not check it. That is the deliberate shape
  -- someone typing the tool's own name has chosen the checkout they are
  standing in -- but it does mean the workaround is the unguarded path, and
  the habit it replaces still applies to it. `--verify` answers "is the installed
  override older than the checkout". It cannot answer "is this checkout the one
  that art should be rebuilt from", and `inputs` cannot either: the fingerprint
  notices that the pack moved and not which way, because a hash is the same
  size in both directions. A regen run from a branch without the toggle work
  once wrote four location trees carrying no pin rules into the override.

  So `regen_maps.py` records which working tree drew each mode's art --
  `branch`, `head` and `dirty`, in that mode's cache slot beside `inputs`
  (`tools/regen_maps.py:207`, `checkout_id`) -- and `start_session.sh` compares
  before it redraws (`start_session.sh:87`, `regen_ok`). On a mismatch it skips
  step 1 and counts a problem rather than aborting, so the emulator and the
  tracker still open on the art already on disk, and `FF1_REGEN_ANYWAY=1` goes
  through. Three answers rather than two, and keeping them apart is most of the
  work: a detached head records a commit and no branch, a checkout with no git
  records neither, and both read as "cannot tell", redraw, and say that is what
  happened. A guard that fired on an absence is one people learn to pass with
  the override. `tools/tests/test_regen_branch.py` holds the three apart and
  demonstrates the skip against the same call on a matching branch.

  `head` and `dirty` are recorded and not compared. They are provenance, the
  role `sha1` and `ffr` already play for the cartridge -- what this art was
  built from, answerable after the fact -- and `dirty` covers `INPUT_FILES`
  only, because an edit anywhere else moves no drawn byte. The branch is the
  only one of the three the guard reads.

  **The `ShipDrydock` work is one of those changes, and it is the worst shape
  of one.** It edits `layouts/shared.json` and all four location files, every
  one of them in `INPUT_FILES`. On an override written before it the tracker
  serves the older copies, so the `shipDrydock` and `noTail` cells are not on
  the board and no alternative carries the guard -- a seed with the flag on
  goes on showing 53 locations green that FFR calls unreachable, which is
  exactly the state the branch exists to end, on a board that otherwise looks
  correct. Re-run the regen once per mode before reading anything off it;
  `tools/regen_maps.py --verify` says whether an installed override is stale.

- **The No-Overworld variants inherit the standard `overworld` row, and their
  29 overworld pins are never restamped for it.** `NOverworldMaps.json`
  overrides only the `incentives` row, so once a standard regen has repointed
  `maps.json`'s `overworld` row at the render -- the 3568x3632 crop, at
  `location_size` 92 -- the No-Overworld variants pick that row up too.
  `locations/NOverworld/overworld.json`'s markers are not restamped to match:
  `ow_maps` is empty in `nov` mode by design, so those pins keep hand-drawn
  pixels reaching (2850, 2700), measured against the 3096x3096 drawing.

  **Invisible today, and waived on that basis 2026-08-31** rather than fixed:
  no No-Overworld layout opens an `overworld` map, so nothing renders the row
  either mode inherits. It becomes 29 wrong pins the moment one does, or if the
  standard crop ever tightens below those coordinates. The fix belongs with the
  amalgamated No-Overworld map in `docs/IDEAS.md` -- that entry owns the
  surface, and restamping 29 markers against a crop this mode never renders is
  work with nothing to check it against until there is one.

- **The `I: Shop Item` pin ignores the flag that governs it. Fixed
  2026-09-03.** Found 2026-09-02. Every other incentive slot carries `^$incentiveSlot|<flag>`, so
  the board can grey a slot the seed did not incentivize. `shopItem` carries
  none, on the belief that FFR has no flag for it. FFR does:
  `FlagsCompute.cs:217` computes
  `IncentivizeCaravan => (NPCItems ?? false) && (IncentivizeFreeNPCs ?? false)`,
  and `PlacementContext.cs:198` adds `ItemLocations.CaravanItemShop1` to the
  incentive location pool on it. `IncentivizeFreeNPCs` is `npcsAreIncentive`
  here (`scripts/autotracking/flag_mapping.lua:53`).

  So on a seed with Main NPCs unincentivized the pin claims a slot that FFR
  never considered, and it claims it in the one direction the board has no other
  way to correct — the slot cannot be graded by `check_logic` against a rule it
  does not have.

  **Why it hid.** The flag is computed rather than declared, so it is absent
  from both flag schemas; a search of the schema for "shop" or "caravan" returns
  nothing and reads like proof. The generalisation is the one that keeps
  recurring here: an absence in a derived index is not an absence in the source.
  `FF1Randomizer-497` is vendored, and the answer was three greps into it.

  **The residue is real and separate.** Even with the flag on, roughly half of
  solo seeds hold a consumable, because `ItemPlacement.SelectVendorItem` falls
  back to the treasure pool when no eligible incentive item is left. The slot's
  incentive status is a flag; its content is the roll. Conflating those is what
  produced the wrong close.

  Fixed by `^$incentiveSlot|npcsAreIncentive` on the `shopItem` section in both
  incentive trees, plus `$showPin|slot|npcsAreIncentive` on the pin —
  `pin_visibility.py` stamps the same rule, so the pin half is the tool's output
  rather than a transcription of it. `scripts/incentive_slots.lua` is generated
  and was re-run rather than edited.

  **It gains one row where every other slot gains two**, and that is this
  entry's own collision showing up somewhere new: a row's path is
  `@<node>/<section>`, and the board's node for this slot is itself named
  `I: Shop Item`, so the sheet path and the board path are the same string and
  the second is deduped away. The surviving row reaches the board's section, by
  the same first-match rule recorded below. What the sheet's section loses is
  only the gold ring; its access rule and its pin rule are evaluated directly
  and are unaffected.

  Six counters moved, each re-derived: sections reporting Inspect 49 → 51,
  generated rows 55 → 56, sheet pins with a rule 17 → 18 and 20 → 21, and pins
  drawn with the flag off 9 → 8 and 8 → 7. The last pair is the demonstration
  that the rule bites — with `npcsAreIncentive` absent the pin was drawn before
  and is not drawn now.

- **The `I: Shop Item` pin clears itself now, and is deliberately still green
  until it does.** The pin is `Onrac Continent/I: Shop Item`, with empty
  `access_rules` at node and section level under an organisational parent, so
  the board shows it unconditionally green. That half is now a decision rather
  than an omission; the other half -- nothing ever cleared it on a solo seed --
  is fixed.

  **How a purchase is seen.** FFR gives the shop slot a synthetic object id of
  `0xFF`, so buying a key item out of a shop sets flag byte `0xFF` bit `0x02` --
  `FF1Lib/asm/0E_9F48_ItemShopCheckForSpace.asm:11-31`, which is Archipelago
  location 767 (`0x2FF`), the same arithmetic `worlds/ff1/Client.py` does on
  every NPC id. But `GlobalImprovements.cs` installs that patch only under
  `if (archipelagoenabled)` on the 4.9.x line: measured across the cartridges in
  `seeds/ff1/`, every Archipelago one carries it and every seed rolled on the
  public site has `0xEA` all through `$0E:$9F48` with the old routine still
  hooked. Buy-10 was on in all of them and does not bring it along.

  So a solo seed is read the other way round. The shop's stock is in PRG ROM,
  and since FFR places each key item exactly once, the item sitting in the shop
  identifies the purchase by its inventory byte. `tools/shop_slot.py` and the
  reader in `bridge/ffr_uat_bridge.lua` are twins of that decode, and
  `tools/tests/test_shop_slot.py` holds them to what FFR wrote down first.

  **Two traps in that decode, both of which fail plausibly rather than loudly.**
  `lut_ShopTypes` is not at the address a disassembly of the original gives:
  FFR expands the ROM to 512K and the vanilla fixed bank `0x0F` lands at `0x1F`.
  The reader probes both and takes the one that reads back as six item shops and
  a caravan. And on an Archipelago cartridge the slot holds the FireOrb
  sentinel, whose inventory byte `$6032` is the one `fireorb` already claims
  (`ram_mapping.lua:58`) -- watching it there would tick the shop check when the
  orb lit and light the orb when the sentinel was bought. The reader probes for
  the patch first and refuses the inventory route entirely on those cartridges.

  **Why no access rule, deliberately.** FFR's exported rule for the slot is
  whichever shop the seed chose -- `PravokaShop1` and `()` on `std497`,
  `ElflandShop4` and `(Canoe)` on `drydock497`. Gating the pin on that would
  publish it: a pin that turns red teaches the player the item is behind the
  canoe, and the shop hunt is most of what the slot is for on a seed that has
  one. So the derivation stays inside the bridge, which sends one boolean and
  never names the shop or the item, and the pin stays green until bought. The
  cost is accepted and recorded here: on a seed that puts the slot behind a
  vehicle, the pin is a green check that is not yet reachable.

  **Roughly half of solo seeds have no key item in a shop at all.** The slot can
  legally hold a plain consumable, and rolling ten seeds on one played
  cartridge's flags gave five with no key item in any shop -- so
  `duck-103` having none is ordinary, not a decode failure. Those seeds keep a
  pin only a click will clear, and that is the right outcome: hiding it would
  tell the player not to bother hunting.

  **The grader can see this pin now.** `check_logic` resolved a location by path
  suffix and `find_section` returned None on more than one hit, and
  `I: Shop Item/I: Shop Item` matches both `Onrac Continent/...` in the dungeon
  tree and `I: Onrac Continent/...` on the incentive poster -- which is what the
  "1 could not be mapped" on every run on every cartridge was. That is not
  ambiguous at runtime: `Tracker::getLocation` takes the first match and
  `scripts/init.lua:41-42` loads `overworld.json` before `incentives.json`, so
  the board tree wins, and `find_section` now resolves it the same way. Two hits
  inside the board tree are still a refusal. `std` went from 225 checked with 1
  unmapped to 226 with 0, divergences unchanged at 0; `nov --derived` kept its
  single divergence and now names the pin under "no derived rule".

  **It was never a `ShipDrydock` effect, and the first reading of it said it
  was.** The two 4.9.7 cartridges differ in this rule, which looks like a 52nd
  thing the flag does. It is not: the flag's map edit changes 11 overworld tiles
  and **five go from unwalkable to walkable while none goes the other way**, so
  it only ever opens land. The Shop Item rule moved because the seed put the
  shop slot in a different shop. Do not re-derive this as the drydock closing a
  route.

- **Nothing tests the multi-tile OR in `derive()`.** Fifteen locations on
  `F258553F` resolve to more than one chest tile, and `derive()` unions the
  per-tile rule sets rather than intersecting them. The union is doing real
  work, not agreeing with itself: ToFR Kary Floor 2 resolves to
  `canoe,floater OR chime,floater | UNREACHABLE | (free)` and ships `(free)`,
  where an AND would demand the Floater. Free is right — opening any one copy
  clears the lot, so the party needs only the easiest. But the rule rests on a
  comment in `derive()` and on that measurement, and no test would notice it
  becoming an AND.

  **A retraction, so it is not cited again.** A first pass printed an "if it
  ANDed instead" column that agreed with the shipped rule everywhere, which
  looked like confirmation. It was computed over the already-filtered live-tile
  list, so it reproduced the OR answer by construction and could not have
  disagreed. It is evidence of nothing.

- **Seven incentive slots ring gold on a seed FFR did not incentivize them on.**
  Found 2026-09-03 by the first use of `tools/export_diff.py`, on the cartridge
  rolled for it. `FlagsCompute.cs:217` makes the incentive status of the six
  free NPCs and the caravan slot the *conjunction*
  `(NPCItems ?? false) && (IncentivizeFreeNPCs ?? false)`. The pack models one
  conjunct: all seven rows in `scripts/incentive_slots.lua` -- King, Sara,
  Bikke, Sarda, Sages, Robot and Shop Item -- carry `npcsAreIncentive`, which is
  `IncentivizeFreeNPCs`, and no `npcItems` code exists anywhere in the pack.

  So on `NPCItems` off with `IncentivizeFreeNPCs` on, FFR drops all seven from
  `priority_locations` and the pack rings all seven gold. Measured on
  `nonpcitems497` against `std497`: seven priority locations gone, and **zero
  access rules moved** -- the seven names FFR drops are exactly the seven the
  pack rings.

  **Six of the seven are a wrong ring. The seventh is a check that does not
  exist.** `Shop Item` leaves `rules` and `locations` as well as
  `priority_locations` -- 227 exported locations to 224 -- while the six NPCs
  stay in both. `PlacementContext.cs:243` forces vanilla placements on the six
  and on the vendor slot alike when `NPCItems` is off, and `SelectVendorItem`
  (`ItemPlacement.cs:227`) hands back a Bottle before it looks at anything, so
  the source alone does not say which of the seven Archipelago still calls a
  location. The export does, and it says the caravan slot is not one. Reading
  that off `PlacementContext.cs` would have got it wrong in both directions.

  So the fix is three, not one -- two on the free half, and the fetch half
  below:

  - **The ring, on six.** An `npcItems` code and the conjunction on the NPC rows
    of `scripts/incentive_slots.lua` -- thirteen `npcsAreIncentive` rows across
    the two incentive trees, seven in the `I:` tree and six in the standard one,
    which has no caravan row -- and on the matching `access_rules` in
    `locations/incentives.json` and `locations/NOverworld/incentives.json`. This
    is the shop-slot build one conjunct along.
  - **The slot, on one.** The caravan slot needs `npcItems` on its *existence*,
    not its colour, in all four location files. Today
    `locations/incentives.json` and its `NOverworld` twin gate the section on
    `^$incentiveSlot|npcsAreIncentive` and the pin on
    `$showPin|slot|npcsAreIncentive`, and `locations/overworld.json` and its
    twin gate neither -- the overworld tree shows a shop-item check
    unconditionally. With `NPCItems` off, all four show a check FFR did not
    create.

  **The fetch half has the same shape and is not fixed by the above.** Read
  from source rather than measured, so the numbers below are the source's and
  not a cartridge's. `FlagsCompute.cs:220-226` computes the fetch NPCs as
  `(NPCFetchItems ?? false) && (IncentivizeFetchNPCs ?? false)`, the same
  conjunction one flag along, and the pack again models one conjunct: the
  sixteen fetch rows of `scripts/incentive_slots.lua` -- eight per tree, Smithy,
  Nerrick, Astos, Matoya, Elf Prince, Dr Unne, Lefein and Fairy -- carry
  `fetchQuestsAreIncentive`, which `flag_mapping.lua:54` binds to
  `IncentivizeFetchNPCs` alone. `NPCFetchItems` is in both shipped schemas and
  in `tools/doormap.py`, and appears nowhere in `scripts/`: no code, no
  `NOT_MODELLED` row, no row in `docs/FLAG_COVERAGE.md`. So a seed with
  `NPCFetchItems` off and `IncentivizeFetchNPCs` on rings those slots gold on a
  seed FFR did not incentivize them on -- the same defect, and the coverage test
  cannot see it either, because `consulted()` greps FFR's *reachability* logic
  and this flag is only read on the incentive path.

  Two things in the fetch half do not match the free half, and both would be
  got wrong by copying the six-NPC fix across:

  - **Nerrick is a three-term conjunction.** `IncentivizeNerrick` is
    `(NPCFetchItems ?? false) && (IncentivizeFetchNPCs ?? false) && !NoOverworld`
    (`FlagsCompute.cs:224`). `IncentivizedLocationCountMin` (`:229`) reads the
    same way -- seven fetch slots, or six under No-Overworld. The `NOverworld`
    incentive tree must drop the Nerrick row rather than gate it.
  - **FFR computes seven fetch slots; the pack carries eight rows per tree.**
    There is no `IncentivizeUnne` anywhere in `FlagsCompute.cs`, and
    `ItemLocations.cs:277-278` makes Unne a *secondary* requirement on Lefein's
    reward rather than a reward slot of its own. Whether the pack's `Dr Unne`
    row answers to any FFR incentive at all is an open question, not a settled
    defect; it wants the same treatment the free half got -- a cartridge with
    `NPCFetchItems` off, diffed against `std497` -- before anything is changed
    on it. The corpus has no such cartridge today.

  This is the same mistake the shop slot's close made and caught late, in the
  opposite direction. That one read a flag's absence from a schema as FFR having
  no such flag; this one modelled a computed flag by whichever conjunct the pack
  already had a name for. A conjunction is not modelled by one of its terms --
  which the review of `flag-coverage` said in almost these words about a
  coverage row, and it was not carried across to a rule.

## Open questions

- **`canon` has a latent false FAIL in `test_maps.lua` check 7.** It treats a
  rule as unconstrained only when *every* alternative empties out, but in
  PopTracker an OR with one unconditional branch is unconditional. No rule
  reaches it today — every `^$incentiveSlot` term sits either alone in its list
  or in all of them — so this is a false FAIL waiting on the next incentive
  rule rather than something being missed now.

- **The toggle icons are sized against a filter a third darker than their
  docstring assumed.** `make_toggle_icons.py` draws only the "on" image and lets
  PopTracker grey the off state; the docstring described the default `grey`
  filter, but `settings.json` sets `disabled_image_filter` to `grayscale, dim`,
  and `dim` is a flat halving (`imagefilter.cpp:78-81`) applied after a greyscale
  taken at full value. Measured through the real filter: GROUND 24/24/28 -> 12,
  GLYPH 188 -> 94, blue -> 61, gold -> 78. The glyph shapes hold at 94 on 12.
  The gold ring at 78 against a 94 glyph has stopped being gold, which makes
  `showIncentiveRings` the one of the four most likely to want a drawn "off"
  image. A look-at-it-on-a-board decision, not a code one.

- **A stop at a chest re-orients for free, and nothing says whether it
  should.** `Floor.lane` chains its legs with `path()`, and `search()` seeds
  `(start, None)`, so the heading a leg arrives on is dropped and the first
  step of the next leg is never charged `TURN`. The DP prices legs the same
  way, since `cost_to()` folds `dist()` across headings, so the tour and the
  walk it reconstructs agree with each other -- but `turns()`, which the CLI
  report prints, counts the junction turns on the finished path, so the two
  numbers describe different walks at up to eighteen nodes on a floor.

  The case for leaving it: the turn term exists because holding a direction
  until the map stops you needs no counting, and opening a chest is already a
  stop, so there is no held direction to lose. The case against: the term is
  meant to be a real cost and this exempts it wherever the errand touches. The
  fix is a heading in the DP state, which is four times the table -- against
  `MAX_ENTRIES`, that is a real ceiling, not a formality -- for a term that is
  last in the lexicographic order. Not worth it while `--lanes` is off by
  default and the tour is headed for replacement by authored waypoints, where
  the visit order is the author's and the free re-orientation is correct.
  Raised by review 2026-08-31.

- **The agreement figures used to grant away most of what they appeared to
  compare. Largely closed 2026-08-30.** `check_logic --derived` hands every
  off-vocabulary item to both sides before comparing (`offvocab_items()`), so a
  location whose FFR rule is entirely granted is counted as agreeing without
  being tested. On the corpus as it stood that was most of them, and the
  concentration was one item — the Oxyale and the Ruby, neither in the swept
  vocabulary, because the SubEngineer and Titan gate rows were missing. The
  counts, before and after those rows landed, are in `docs/ORACLE.md`.

  Both rows landed with the vocabulary that carries them. The grant is now **5
  of `nov`'s 226 and 5 of `nov2`'s 224** — one each for Herb, Adamant, Bottle,
  Crystal and Slab, the trades the walk genuinely cannot express — so 221 and
  219 are really compared, against 58 and 64 before.

  The pack's own No-Overworld rules had the mirror-image problem: transcribed
  from FFR's export for the seed, so grading them against that export was
  largely self-agreement. By provenance, of 226 comparisons: **63 independently
  supported, 163 self-agreeing by construction, 6 deliberately strict** (Cardia
  Forest, whose gateway is rolled per seed), with the sweep contributing nothing
  because the single rule taken from it was not in FFR's pool.

  That is what the two rows changed. The sweep now derives a rule for every
  compared location and agrees with FFR at 225 of 226, and at every location
  where the pack's transcribed rule agrees with FFR the derived rule does too.
  **215 of the 226 now rest on two independent readings** — the transcription
  and a walk of the cartridge — rather than on the transcription alone. The
  eleven that do not: 6 deliberately strict, 4 still granted a trade item, and
  Lefein, where the derivation is genuinely permissive (see above). Quote 215,
  not 220, and not 226.

- **Nothing cross-checks the ToFR rules, so the agreement figure does not cover them.**
  `Archipelago.cs:93` excludes ToFR from the pool unconditionally, so FFR writes
  no rule for any ToFR location and not one of them is among the 226 the
  derivation is measured against. Their derived rules are validated only by
  direct sweeps against the cartridge — which is how the six `(free)` ones were
  settled (`docs/NOVERWORLD.md`, "What the shortcut drops you into"), one
  location at a time and by hand. **That settlement is now believed wrong**: it
  reasoned from where the lute gate stands and never asked what the Black Orb
  object does, and the walk has no row for it. The oracle could not have caught
  it, which is the entry above in miniature. This is a limit on what the agreement figure
  licenses rather than a defect: quoting it as though it covered the whole
  derived set overstates it by exactly the ToFR floors. Anything that changes
  how ToFR is walked needs its own measurement, because the oracle will stay
  silent.

- **`smith $6209` reads `0x05` and `fairy $6213` reads `0x04`** on a live seed —
  both have the chest bit set with the event bit clear, while their rules test
  `0x02`/`0x03`. Probably fine, since that is chest `$09`/`$13` rather than the
  NPC. Unproven; one before-and-after read across a turn-in settles it.

- **The four Fiends and the ToFR refights cannot be autotracked at all.** They are
  spiked battle tiles that write no flag in vanilla or FFR, and the orb byte — set
  by stepping on the altar, not by the kill — is the only proxy. Any box for them
  would be manual-click forever.

- **The committed No-Overworld dungeon tree is a copy of the standard one.**
  `locations/NOverworld/overworld.json` has been byte-identical to
  `locations/overworld.json` since `c0b494b` created it, and that commit is the
  one saying why it should not be: "the crop makes the same tile a different
  pixel in each set, so the dungeon tree splits too". A No-Overworld cartridge
  seals every town wall and stamps 75 new staircases, so 34 to 39 of the 61 maps
  are cropped differently and the same tile lands elsewhere. The committed file
  carries the standard crop's pixels for all of them. It is a fallback, not the
  live path -- `regen_maps.py` writes markers into an override directory and
  never into the tracked pack -- so a No-Overworld player who has rendered art
  sees correct pins and one who has not sees every box off its chest, which is
  the same failure `load_cache`'s stale-override branch exists to prevent. Fixing
  it means committing a rendered No-Overworld tree, which needs a decision about
  whether generated marker coordinates belong in the repo at all.

- **`test_maps.lua` check 6 is comparing a file to itself.** It exists to hold
  the two dungeon trees in step -- same locations, same sections, same access
  rules, map names but not pixels -- and while the two files are identical it
  cannot fail for any reason, including the pixel tolerance it is written around.
  It passed the Ordeals defect for that reason and would have passed it for that
  reason no matter what the check compared. It starts doing real work the moment
  the trees legitimately diverge, which is the entry above; until then its 283
  matching locations are not evidence of anything. Its sibling check 7, which
  compares the incentive tree against the dungeon tree, is unaffected -- those
  two files are genuinely different.

- **The No-Overworld incentive poster is missing one slot, not two.** Diffing
  `hosted_item` across the two posters gives exactly `nerrick` and `airship`,
  and this entry used to call both defects. Only `nerrick` is.

  **`nerrick` belongs there.** It is a real Archipelago location on this mode --
  the export has `ConeriaCastle1 -> DwarfCave -> Nerrick (Tnt)` -- and both
  dungeon trees carry it.

  **`airship`'s absence is correct, and it is not a location at all.** Grep the
  four oracle exports for it and you get nothing, on standard either: the slot
  is `I: Ryukahn Desert / I: Floater Turn In`, and `hosted_item: airship` means
  it *grants the vehicle to the tracker* when checked, not that an item is
  placed there. On No-Overworld there is no desert and no vehicle -- the Floater
  is `NoOW_Floater`, a barrier key for Coneria Castle 1F, Castle Ordeals 1F and
  Ice Cave B1 -- and all 26 of the nov poster's `airship` mentions are already
  behind `$standardWorld`, so they are dead rules. A poster slot for it would be
  a way to hand the tracker a vehicle the seed does not have.

  Do not re-derive this as a missing pair. The pairing was the error.

  `test_maps.lua` check 7 walks the incentive sheet and asks the dungeon tree
  about each slot it finds, so a slot the poster omits is invisible to it -- the
  check is one-way by construction, and making it two-way would fail on the four
  orb-lit slots that are poster-only by design. Where `nerrick` should sit on a
  poster with no overworld is the same question as deriving the rest of the
  pins, so it stays filed with `docs/ROADMAP.md` item 3.

- **The two tabs disagreed about how to reach Gaia. Closed 2026-09-01: the
  poster was right.** The Gaia node's northern-docks route read
  `northernDocks,hwyOrdeals,gaiaMountain,ship,canal` in
  `locations/incentives.json` and dropped `hwyOrdeals` in
  `locations/overworld.json` — identical in upstream's `9ed47a4` and here, so a
  rule written twice and never compared rather than drift.

  It was not answerable from the location files, so it was answered off a
  cartridge. Two seeds one flag apart: `oracle-4.9.7/gaia497` rolls
  `MapOpenProgressionDocks` and `MapGaiaMountainPass` with `MapHighwayToOrdeals`
  **off**, and FFR still gives the Fairy as `(Canoe AND Floater AND Bottle)` —
  no Ship route at all, while 79 other rules do move, so the flags are certainly
  live. `gaiahwy497` turns the highway on and the rule gains `(Canal AND Ship
  AND Bottle)`. Lefein moves with it, which is why its northern-docks route
  always carried `hwyOrdeals` in both trees.

  So the dungeon tree was over-reporting: on a docks-and-pass seed without the
  highway it opened Gaia with the Ship and the Canal and FFR does not. Fixed in
  both `overworld.json` trees, graded 223 of 224 before and 224 of 224 after.

  `tests/test_maps.lua` check 7 waived `fairy` by name and now waives nothing —
  every slot the two trees share has to match.

- **What a diamond means is unsettled.** Square and diamond are the same size,
  centre, colours and click target; the only difference is that a diamond leaves
  the tile's four corners unpainted so a sprite reads behind it. At three pins
  that read as an exception. At fourteen it is every NPC pin there is, on both
  modes, which makes the shape a category whether or not it was meant as one —
  especially once the trapezoid arrives meaning "entrance". Either say out loud
  that diamond means NPC, or move the sprite off-centre within its tile so a
  square pin stops covering it. The first is free and is what the output already
  looks like.

- **Should the variant be auto-selected from `GameMode`? Answered 2026-09-01:
  it cannot be.** The suspicion in this entry was right and is now checked
  rather than suspected. `Tracker.ActiveVariantUID` is read-only from Lua and
  raises `"Tried to write read-only property"` if assigned (PopTracker
  `core/tracker.cpp:747-749`), and `Pack::setVariant` has exactly one caller,
  `poptracker.cpp:1202`, on the load path. No runtime path exists, so this is
  refused rather than parked.

  What the pack does instead is the `modeMismatch` light, which says on the
  board what the console was already saying. Closing this also fixed a warning
  that was wrong: the old `GameMode ~= 0` line fired on every No-Overworld seed
  loaded into the No-Overworld variant it belongs in.

- **Does anyone outside this repo use the pack?** It decides the four `NoMap`
  variants question in `docs/IDEAS.md`, and nothing else can settle it.
