# Known wrong, and open questions

Defects and unsettled questions, lifted out of `STATUS.md` so they are findable
without reading the whole log. The narrative — how each was found, what was tried
— stays there.

Nothing here is urgent unless it says so.

## Known wrong

- **The No-Overworld variants run standard-overworld logic.** `scripts/logic.lua`
  branches on shard hunt and nothing else, so roughly thirty overworld-geography
  rules (`ship`, `canoe`, `canal`, `bridge`, `northernDocks`, `lefeinBridge`,
  `hwyOrdeals`, `gaiaMountain`, `melmondRiver`, `luffyDock`, `cardiaDock`) gate a
  mode where ship and bridge are free and the canoe is not a vehicle. Every pin
  on a No-Overworld tracker is coloured by rules that do not describe the seed.
  This is the largest live defect in the pack. See `docs/NOVERWORLD.md` and
  `docs/ROADMAP.md`.

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

- **Titan has no box.** The code `titan` is already taken by `ruby` stage 2, so a
  Locations-grid cell needs a new hosted toggle under a different code. It would
  be a bridge-only cell — Titan is not an Archipelago location either.

- **Six NPCs the cartridge places have no box anywhere.** Fourteen of the twenty
  objects `extract_npcs.WANTED` reads have a pin; Unne, Titan and the four
  fiends host no section in the location tree, so there is no location a pin
  could belong to. Titan's is the code clash above; the fiends write no flag that
  could be autotracked at all; Unne holds no shuffled item. Each would be a
  manual-click cell, which is a decision rather than an omission — written down
  so it stops reading as a gap in the NPC pins. Reaffirmed 2026-08-30 when the
  pins moved to the cartridge and the other six gained boxes; nothing measured
  in that pass argues for adding these.

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

- **The same enemies can carry two different trap letters.** `trap_letters()`
  numbers by `(tileset, tile)` enumeration order rather than by the formation the
  tile spawns, so one formation reached through two tileset entries gets two
  labels. Measured 2026-08-30, three formations on each oracle cartridge: on the
  std seed formation `$10` is drawn **G** on `earthB1` and **W** on `marshB3`;
  `$1C` is AA and AG; `$4A` is V and X.

  That defeats the thing a trap letter is for. Meet a fixed formation early,
  decide it is worth fighting or worth avoiding, and the label it carries the
  next time you meet it may be a different one.

  The same enumeration is why labels run to two characters. 38 distinct labels
  exist on the std cartridge, so everything past index 25 becomes AA…AL — seven
  maps carry one, `tofrChaos` reads AG AH AI AJ across eight tiles in a row and
  `seaB4` reads AB AC AD AE, and at two tiles wide a label no longer says which
  tile it marks.

  Both close together by keying the mark to the formation id. Only **32
  formations actually stand on a map** (31 on nov), and the cartridge's own font
  carries `0-9A-Z` — 35 single glyphs once `O` is dropped, since `tools/font.py`
  asserts `0` and `O` are the same glyph in it. On `docs/ROADMAP.md`.

- **A room bigger than the guard stays shut.** Mirage Tower 1F's interior is 458
  cells and `ROOM_MAX_CELLS` is 256, so it does not open. Raising the cap is not
  the answer — the same test finds Waterfall's 1820-cell floor and Volcano B4's
  2650, which are open floor and must stay closed. The door-flood rule handles
  it (353 cells) and is unioned in; what is still unresolved is that on 49 maps
  the union opens cells the flood does not, and ToFR Air has exactly one door
  tile for 241 such cells. Understand what those are before replacing the rule.

- **Crop boxes are looser than the map on several tabs.** Two causes, not one.
  This entry used to name a single one — "stray detached tiles out near the
  boundary hold the frame open" — and **that is wrong for the four worst maps.**

  **The seam.** A standard map wraps at 64 tiles (`AND #$3F`, and
  `entrance_graph.floor_walk` already models it). `render_maps.content_box` does
  not: it takes an axis-aligned bounding box in un-rotated coordinates, so a map
  whose content straddles column 0 or row 0 is framed across the void between
  its two halves. Measured 2026-08-30 over all 61 maps of the std and nov oracle
  cartridges, which give **identical answers** — the wrap is a property of the
  map, not of the seed, so there is no separate No-Overworld audit here:

  | map | boxed now | on the torus | where the content actually is |
  |---|---|---|---|
  | `con_castle` | 64x35 | 31x35 | cols 62-63 + 0-26; the 35 blank columns are 27-61 |
  | `crescent_lake` | 52x64 | 53x43 | rows 58-63 + 0-34 |
  | `melmond` | 45x64 | 45x46 | rows 51-63 + 0-30 |
  | `elf_castle` | 28x64 | 29x35 | row 63 + 0-31 — wrapped by a single row |

  `con_castle`'s 35 columns are the number this entry always carried; only the
  cause was wrong. Fixing it is a rotation before boxing, and it is on
  `docs/ROADMAP.md`.

  **The residue, which is the original diagnosis and still stands.** `onrac`,
  `lefein` and `seaB1` have **no empty column at all** — a sliver of one to three
  cells per column runs the full width and holds the frame open (`lefein` rows
  33-47, `seaB1` cols 32-63). `iceB2` (8-column interior gap), `iceB3` (18) and
  `sky4F` (six scattered gaps) are genuinely multi-lobe maps, where rotating
  would put the left half on the right and make things worse. Still deliberately
  not fixed by adding another per-tile proxy — walkability and size were both
  tried and rejected. The shape of a real answer is the one the room work landed
  on: ask what a region is connected to, not what its tiles look like. Insets
  would dissolve it, and `docs/IDEAS.md` names these maps under that heading.

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

## Open questions

- **The agreement figures used to grant away most of what they appeared to
  compare. Largely closed 2026-08-30.** `check_logic --derived` hands every
  off-vocabulary item to both sides before comparing (`offvocab_items()`), so a
  location whose FFR rule is entirely granted is counted as agreeing without
  being tested. On the corpus as it stood that was **164 of `nov`'s 222
  comparisons and 156 of `nov2`'s 220**, so "222 of 222 agree" described **58**
  locations. The concentration was one item — **oxyale x129, ruby x32** on
  `nov` — and neither was in the swept vocabulary because the SubEngineer and
  Titan gate rows were missing.

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

- **The No-Overworld incentive poster is missing two slots.** It hosts no
  `nerrick` and no `airship` (the Floater turn-in in Ryukahn Desert), both of
  which `locations/incentives.json` and both dungeon trees carry. `test_maps.lua`
  check 7 walks the incentive sheet and asks the dungeon tree about each slot it
  finds, so a slot the poster omits is invisible to it -- the check is one-way
  by construction, and making it two-way would fail on the four orb-lit slots
  that are poster-only by design. Deciding what these two should look like on a
  poster with no overworld is the same question as deriving the rest of the
  pins, so it is filed with `docs/ROADMAP.md` item 3 rather than patched here.

- **The two tabs disagree about how to reach Gaia.** The Gaia node's
  northern-docks route reads `northernDocks,hwyOrdeals,gaiaMountain,ship,canal`
  in `locations/incentives.json` and drops `hwyOrdeals` in
  `locations/overworld.json`. Identical in upstream's `9ed47a4` and here, so it
  is not drift — it is a rule that was written twice and never compared. It is
  the one slot `tests/test_maps.lua` check 7 waives by name; every other slot the
  two trees share now has to match. Which of the two is right is not answerable
  from the location files, and the neighbouring rules do not settle it either:
  Lefein's northern-docks route carries `hwyOrdeals` in both trees and Sky
  Palace's carries it in neither. Deciding it wants FFR's own logic for the
  Fairy on a seed where the two differ.

- **What a diamond means is unsettled.** Square and diamond are the same size,
  centre, colours and click target; the only difference is that a diamond leaves
  the tile's four corners unpainted so a sprite reads behind it. At three pins
  that read as an exception. At fourteen it is every NPC pin there is, on both
  modes, which makes the shape a category whether or not it was meant as one —
  especially once the trapezoid arrives meaning "entrance". Either say out loud
  that diamond means NPC, or move the sprite off-centre within its tile so a
  square pin stops covering it. The first is free and is what the output already
  looks like.

- **Should the variant be auto-selected from `GameMode`?** Mode detection already
  works and drives nothing but a warning. PopTracker picks a variant once, at
  load, so this may not be expressible — worth checking before assuming it is a
  gap.

- **Does anyone outside this repo use the pack?** It decides the four `NoMap`
  variants question in `docs/IDEAS.md`, and nothing else can settle it.
