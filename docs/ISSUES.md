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

- **The sweep still cannot express the items that are game rules.** It varies
  `entrance_graph.ITEM_NAMES`, the ten items that gate a *tile*. FFR's model also
  carries `Oxyale`, `Ruby`, `Slab`, `Herb`, `Adamant`, `Bottle` and `Crystal`.
  Half of that gap is closed: where one of them is a *trade*,
  `entrance_graph.talk_item_requirements()` reads it off the talk table and the
  rule states it — Astos's Crown, Nerrick's TNT, the Smith's Adamant, Matoya's
  Crystal. What stays out of reach is those items used as access rules
  elsewhere: Oxyale is "you can breathe underwater", and the oracle cartridge
  carries 129 uses of it and 32 of the Ruby. `check_logic --derived` grants them
  to both sides rather than skipping the location, so FFR reads as permissively
  as it can and a surviving divergence cannot be blamed on the gap. That is a
  fair test, not a fix.

- **Map markers still come from the vanilla NPC table.**
  `regen_maps.place_locations()` reads `tools/npc_positions.json`, which is the
  vanilla table; the derivation stopped doing that and reads the cartridge.
  Measured, FFR moves people: Titan by (60,8,7) → (60,4,8) on an ordinary seed,
  Nerrick by (19,16,45) → (19,15,47) on a No-Overworld one. So a No-Overworld
  regen draws Nerrick's pin one column and two rows off the sprite it is meant
  to sit on. Titan has no pin, so he costs nothing today. Switching the pins to
  the cartridge would also hand pins to the six NPCs that just gained locations,
  which is a decision about the location tree rather than a bug fix, so the two
  want doing together.

- **Titan has no box.** The code `titan` is already taken by `ruby` stage 2, so a
  Locations-grid cell needs a new hosted toggle under a different code. It would
  be a bridge-only cell — Titan is not an Archipelago location either.

- **Six NPCs the cartridge places have no box anywhere.** Unne, Titan and the four
  fiends host no section in the location tree, so there is no location a pin
  could belong to. Titan's is the code clash above; the fiends write no flag that
  could be autotracked at all; Unne holds no shuffled item. Each would be a
  manual-click cell, which is a decision rather than an omission — written down
  so it stops reading as a gap in the NPC pins.

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
  vanilla and do not describe an FFR seed; ours are read per cartridge and are
  self-consistent per map. Only cross-referencing a letter against his guide is
  unsafe.

- **A room bigger than the guard stays shut.** Mirage Tower 1F's interior is 458
  cells and `ROOM_MAX_CELLS` is 256, so it does not open. Raising the cap is not
  the answer — the same test finds Waterfall's 1820-cell floor and Volcano B4's
  2650, which are open floor and must stay closed. The door-flood rule handles
  it (353 cells) and is unioned in; what is still unresolved is that on 49 maps
  the union opens cells the flood does not, and ToFR Air has exactly one door
  tile for 241 such cells. Understand what those are before replacing the rule.

- **Crop boxes are looser than the map on several tabs.** Stray detached tiles out
  near the boundary hold the frame open: `con_castle` 35 blank columns, `sky4F`
  22 columns and 26 rows, `elf_castle` 31 rows, and three towns over 16 rows
  each. Deliberately not fixed by adding another per-tile proxy — walkability and
  size were both tried and rejected. The shape of a real answer is probably the
  one the room work landed on: ask what a region is connected to, not what its
  tiles look like. Insets would also dissolve it.

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

## Open questions

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
  that read as an exception. At eight it is every NPC pin there is, which makes
  the shape a category whether or not it was meant as one — especially once the
  trapezoid arrives meaning "entrance". Either say out loud that diamond means
  NPC, or move the sprite off-centre within its tile so a square pin stops
  covering it. The first is free and is what the output already looks like.

- **Should the variant be auto-selected from `GameMode`?** Mode detection already
  works and drives nothing but a warning. PopTracker picks a variant once, at
  load, so this may not be expressible — worth checking before assuming it is a
  gap.

- **Does anyone outside this repo use the pack?** It decides the four `NoMap`
  variants question in `docs/IDEAS.md`, and nothing else can settle it.
