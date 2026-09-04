# Ideas, not yet scoped

Things worth doing that nobody has designed yet, each recorded with whatever is
already known about it so scoping does not start from scratch. Nothing here is a
commitment and the order means nothing — `docs/ROADMAP.md` is what is actually
next.

## On the maps

**Show the towns when you walk into one. Built 2026-08-31** -- the answer was
the third of the three this paragraph offered, an override shipping its own
`mapValues.lua`, and it cost about forty lines. `STATUS.md`, "The towns got tabs
the party can walk into", has what it turned on. Kept below as written, because
the reasoning about why the base pack cannot name those tabs is still the reason
the file is generated rather than edited.

**Show the towns when you walk into one.** No-Overworld gives every town
staircases, so a town is a room you route through — but `MAP_VALUE` still calls
maps 0-7 "Overworld" and `maptab.lua` sends you to the overworld tab. The town
tabs exist, but only in `regen_maps.py`'s override, because the pack has no town
art to ship. So `MAP_VALUE` cannot simply name them: the base pack would point at
tabs it does not have and `test_maptab.lua` would fail for the right reason.
Whatever the answer is — mode-aware `MAP_VALUE`, an override shipping its own
`mapValues.lua`, town art committed after all — it has to keep the standard
variants pointing at the overworld.

**Follow the party into the room.** The tab shows a whole map at one zoom and
never moves. PopTracker takes `Tracker:UiHint("Zoom <map>", "2.5")` and
`UiHint("Pan <map>", "x,y")` per map, since 0.34.0 — which is part of why the
manifest floor is 0.35.1. The pack already drives `UiHint("ActivateTab", ...)`
from `maptab.lua`, and the bridge would be reading party position anyway for
entrance markers (`sm_scroll` `$29/$2A`, party always 7 tiles in). So this needs
no new art and no new data — it is the same hint channel that already switches
the tab.

**Insets, the way the hand art does them.** Three shipped maps are composites of
disjoint pieces at unrelated offsets: `cardia` in 3 regions, `marshB2` and
`seaB3` in 2. The calibration format already carries that and `region_for`
already reads it, so a renderer that split a map into connected components and
laid them out would reproduce the effect — and would also dissolve the loose crop
boxes in `docs/ISSUES.md`, by laying disjoint components out separately instead
of framing their union.

**Which maps that is, now measured.** The seam-wrap half of the loose-crop entry
has its own fix on the roadmap; what is left for this idea is six maps, in two
shapes. `onrac`, `lefein` and `seaB1` have **no empty column anywhere** — a one-
to three-cell sliver spans the full width, so no bounding box can help and the
question is which components are worth framing at all. `iceB2` (8-column interior
gap), `iceB3` (18) and `sky4F` (six scattered gaps) are multi-lobe maps where a
rotation would actively make things worse by putting the left half on the right.
Add the three composites above and this idea covers nine maps.

The guard is already written: `render_maps.crop_violations` refuses a box that
cuts off a chest, a staircase or an exit, so "drop a component" has a test that
says when it went too far. What it cannot answer is the judgement — Onrac's river
is real map content and still not worth framing — so a size threshold here is a
decision to be defended, not tuned.

**The two lanes are named wrong, and one of them is the wrong lane. Raised
2026-08-31, from play judgement, after the first build; fixed 2026-09-03.**
The analysis below is what the fix implements, so it is kept as written. What
the build added to it: both lanes now hold `graph.floor_items(map_id)` and the
keyless `Floor` is gone entirely -- it existed only to derive the second lane
by difference. Holding an item only widens the walkable set, so a traversal
route holding the floor's key is never longer or less safe than one without.
The `prefer=` direction is unchanged and reads better for it: the loot lane
prefers the route lane's edges, so cyan is the walk you would make anyway and
purple is what the loot costs you on top.

Two measured consequences. A loot lane now appears wherever there is loot
rather than only on a gated floor, so 29 of the 39 lanes on the duck cartridge
are a pair where most were a single line, and 28 maps grow a legend row. And
"Optimal Route for Loot" is 22 characters, which needs 384px at scale 2, so the
Map Key halves its letters on three maps per cartridge; `ISSUES.md` has that
one, and shortening the name to protect a font size would be the trap this page
already names for the trap letters. What shipped is two
*loot* lanes that differ by whether you hold the floor's key: cyan "Optimal
Route" collects what it can keyless, purple "Optimal w Key" collects the rest.
That is not what the pair means. The reference's two flavours are:

- **Optimal Route** -- **no loot at all**. Arrival to exit, the safest walk
  through the floor for someone who is passing through and not opening
  anything. Nothing in the tracker draws this today.
- **Optimal Route for Loot** -- everything, and **"for loot" already implies the
  key**: a loot route that stopped at the locked door would not be the loot
  route. So the key is a property of the loot lane, not a second lane beside it.

So the built pair is really one lane drawn in two halves, and the genuinely
missing one is the traversal lane. The fix is not a rename: it is to route
`arrival -> nearest exit` with an empty errand for the first lane, and to let
the second hold the floor's items from the start rather than deriving a keyless
variant to diff against. The two-colour drawing mechanism survives intact --
what changes is what each colour is routed for.

**And a loot lane should not collect a check it would already have.** A linked
chest index sits on up to three tiles across the run, and the errand treats each
floor in isolation, so a floor whose only remaining claim on an index is its
second tile still walks to it -- `MarshCaveB2`'s bottom half is 179 steps for
two checks its top half already cleared. Deciding this needs an order the router
does not have: which floor you reach first, which is a run-wide question and not
a per-map one. Filed rather than guessed at.

**Routes drawn on the map. Built 2026-08-31** -- the with-loot flavour, baked
into the regenerated art by `tools/lane.py` and `render_maps.draw_lanes`, keyed
in the Map Key band, drawn on request with `--lanes loot`. `STATUS.md`,
"The route to walk is drawn on the map", has what the port found wrong with the
prototype and what the three open questions were settled by. The shortest-to-
the-exit flavour is still unbuilt; everything below is kept as written, because
the reasoning is what the built thing was built from. **Two figures in it are
wrong and are corrected where they appear.**

**Routes drawn on the map.** Wanted in two flavours — shortest to the exit, and
one that collects the loot on the way — and eventually per-map custom routes for
towns, where the useful stops are shops and NPCs rather than chests.
`entrance_graph.py` has the graph *between* maps; a route *within* a map is a
different problem and wants walkability per tile, which `lut_OWTileset` gives for
the overworld and the tileset property tables give for standard maps. Settle
first whether the drawing surface is the PopTracker tab (a static image, so the
route has to be baked in at render time) or `tools/doormap.py` (free to draw
anything, but not in front of you while you play).

The reference art both online and in the older guides already draws these lanes,
and is the thing to improve on rather than copy: **it is not consistent about
colour**, swapping cyan and purple between the optimised route and the with-loot
one from map to map. Ours should fix one colour per lane across all 61 and draw a
key on the map saying which is which — the Map Key band `render_maps` already
reserves is where that goes.

**"Optimal" needs an objective function, and the reference publishes his.**
Read off the head of the Appendix D page 2026-08-31, in his own words:

> routing floors is based on how many unsafe tiles a player has to cross to get
> to their goal (treasure rooms, the stairs to the next floor, and/or the boss of
> that dungeon). Unsafe tiles are tiles that can cause an encounter... Safe tiles
> are tiles that do not cause an encounter, such as lava tiles, door tiles, and
> tiles along the bottom of any room with a door. Maximizing the number of safe
> tiles you take, along with minimizing unsafe tiles, will result in the best,
> fastest route through a floor.

and separately, that trap tiles do not raise the encounter counter but should
still be minimised. So the objective is **lexicographic and step count comes
last**: fewest fixed-formation traps, then fewest encounter tiles, then fewest
steps, then fewest counted turns.

This page argued for step count first with a turn tie-break until that was
read -- the same ordering upside down, and the reason a derived lane could look
reasonable and still not be his. The turn preference below survives as the last
term, and the reasoning for it is unchanged.

**The turn tie-break, kept as the last term.** Running into a wall is easier to
execute than turning in an open four-way: holding a direction until the map
stops you needs no counting. A route that is two steps shorter and needs three
counted turns is the worse route. Where turning at a non-dead-end is genuinely
necessary the route should still take it -- a preference, not a constraint.

**How much of his work has lanes: 58 drawn images, in 15 groups.** Counted from
the page contents 2026-08-31 -- 1 Elfland magic route, 7 vampire-blighted towns,
6 Circle Sea locations, 3 Marsh, 4 Earth, 1 Titan, 6 Volcano, 4 Ice, 2 Ordeals,
3 Cardia, 5 Sea Shrine, 1 Waterfall, 7 Mirage/Sky, 3 overworld routes, 5 ToFR.
Note what that is not: 58 is not 58 of our 61 maps. His unit is a region, so
several of his images are one map of ours (Marsh is 3 images over 2 maps that
carry chests), and several of his subjects -- the town routes, the overworld
routes -- are not dungeon map tabs at all.

Deriving is not the whole job either. A by-eye pass per map, flagging where a
better route exists than the reference draws, is expected to stay in the loop.

**Scoped 2026-08-31, from a prototype rather than by reasoning.** The with-loot
lane is the flavour to build first, because it is the one with no spoiler
question attached: the chests it strings together are already drawn on the art.
Three things the prototype settled:

- **A chest tile is not walkable**, so a lane routed *to* a chest routes to
  nowhere and every chest reads as unreachable. That is the engine's own rule --
  `walkable()` refuses `TP_SPEC_TREASURE` -- and the fix is that the target is
  the walkable neighbour you stand on to open it. `render_maps` had hit the same
  rule from the other side, drawing chest tiles as roof.
- **The arrival comes off the teleport tables, not off `Graph.route()`.** route()
  walks in from an overworld door, so it answers "can I get here holding
  nothing", which a drawing does not ask -- deep floors reported as having no
  route at all. Scanning `norm_map` and `entr_map` for the target gives every
  tile the game can put you down on. Likewise the walk uses `floor_items(map)`
  as its inventory: a lane is a drawing of the map, and routing with an empty
  one stops at the first gated tile and draws a floor half its real size.
- **One lane per map is nearly always enough, and the exceptions are
  structural.** Swept both duck cartridges: of the 38 maps carrying chests on
  the standard one (37 on the No-Overworld one), **36 have every check reachable
  from a single arrival**. The two that do not are `Cardia` (7 of 13 checks from
  the best of 8 ways in) and `SeaShrineB3` (2 of 4, of 3). Both are map geometry
  rather than the shuffle: Cardia is eight islands sharing one map.

  **This said 35 and named a third map until the linked chests were understood.**
  Counting chest *tiles*, `MarshCaveB2` looks split -- 4 of 7 from the best
  arrival. Counting *checks* it is not split at all: indices `25` and `26` each
  have a tile in both halves, so the reachable half already clears them, and one
  lane collects all four checks in 97 steps. The old figure was not a
  miscount, it was the wrong unit. Which means the two maps above are the real
  exceptions and DarkmoonEX's Top/Middle split of that floor is about drawing
  legibility, not about reachability.

**And that is what the reference does too, which settles the drawing unit.**
Read off DarkmoonEX's own Marsh Cave pages 2026-08-31: he draws one image per
**connected region**, not per map -- "Marsh Top" and "Marsh Middle" are the two
halves of the single map `MarshCaveB2`, separately titled, separately routed,
each with its own entrance. The three maps the sweep found are exactly the ones
he splits. His floor labels are one behind FFR's map names; `FINDINGS.local.md`
has the correspondence and how it was settled.

**His Map Key asks for four things the plan did not have.** Worth reading before
scoping the drawing, because two of them are nearly free and two are not:

- **Two lanes, not one: "Optimal Route" and "Optimal w/Key".** A second lane for
  the same region, walked holding the key. Nearly free -- the walk is already
  parameterised on `have`, so it is the same search run twice.
- **Linked chests as a line**, with the key naming the region the twin is on.
  Already measured; the data is in `extract_chests`.
- **"Better Trap Chest", marked with an asterisk.** Which of the trap-guarded
  chests is the one worth eating the fight for. That is a judgement about
  contents, not geometry, and on a randomised cartridge the contents are not
  what his art assumed.
- **Room names -- "Corner", "Single", "Duo", "Distant", "Tetris-Z First".**
  Hand-authored, not derivable from anything on the cartridge. Either
  transcribed with credit or left off; inventing a parallel set would be the
  trap-tile letters again.

**The visit order is solved exactly, not greedily.** Nearest-neighbour left
visible wandering in the middle of `MarshCaveB3` -- it commits to the nearest
chest and pays for it later -- and so did rebuilding a path by walking the cost
field down, which needs a tolerance for the turn charge and spends it on
detours. Real predecessors out of the search, plus Held-Karp over the chests,
took that floor's with-key lane from **419 steps to 336**.

**The largest chest count is 18, not the 13 this said.** Swept over both duck
cartridges 2026-08-31: `GurguVolcanoB2` carries 18 checks, `SkyPalace3F` and
`GurguVolcanoB4` 14 apiece, and `Cardia` 15 on the No-Overworld one. The old
figure was chest *tiles* on the maps that had been looked at rather than checks
over all of them -- the same unit error that made `MarshCaveB2` look split. An
exact tour is still affordable: 2**18 is twelve seconds, and about a third of a
whole cartridge's 35.

**Two lanes, where the floor says there should be.** `Graph.floor_items()`
returns `['key']` for `MarshCaveB3` and nothing at all for the other two Marsh
floors -- which is exactly where DarkmoonEX drew a second "Optimal w/Key" line
and where he did not. So the two-lane treatment does not need a rule about which
maps get it: the cartridge already says. On that floor the plain lane reaches
8 of 11 chests in 204 steps crossing one trap; the with-key lane reaches all 11
in 336 crossing three.

**A linked chest is one check, and the lane visits it once.** An index can sit
on up to three tiles and opening any one clears the lot, so an errand built on
tiles walks detours for nothing: `MarshCaveB2` is 7 tiles and 4 checks,
`MarshCaveB3` is 11 and 9. Visiting checks took B3's with-key lane from 336
steps to **304** and B2's from 99 to **97 while going from 4 of 7 to 4 of 4**.

Which tile of a linked set to use is part of the problem rather than something
to settle up front -- the one nearest the door is not always the one the rest of
the round wants -- so a node in the tour carries every tile you could stand on
to open any of its tiles, and the state is (visited, node, which tile).

**And the ones it skips get a silver connector**, the way the reference does:
straight, orthogonal, drawn under the lanes and through walls where the twins
are in different rooms. Through walls is the point -- the claim is "these two
are one check", not "you can walk between them" -- and a lane crossing over the
top of one is what keeps a connector from reading as a route. On `MarshCaveB2`
that single drawing element is what explains why the lane never goes near the
bottom-right half of the map.

**A second lane has to be told to coincide with the first.** Left alone it
re-routes: with nine checks instead of six the cheapest order changes, so the
with-key lane approached shared rooms down *parallel* corridors and the drawing
grew divergences that meant nothing. Measured before fixing, on `MarshCaveB3`:
of 119 segments drawn in the second colour, **none** retraced the first lane and
all 119 reached tiles it never touched -- so this was not overlap being drawn
twice, it was two equally cheap routes through the same region.

The fix is a tie-break that cannot outrank anything real: every cost is
multiplied by 1000 and a step the first lane does not draw costs 1 more.
**Over tiles, as this first said, is not enough** -- two tiles the first lane
reaches by separate routes are both preferred, so a step straight between them
is free and the second lane draws a purple stub across ground that is already
cyan. Over *edges* it is right, and the difference is 121 purple segments to
101 on `MarshCaveB3` and 122 to 105 on `TempleOfFiendsRevisitedFire`. The two lanes then run together wherever that is free and part only where
the map makes them, which took the second colour from 1710 to 1589 pixels and
removed both of the divergences that were visible on the right of that floor.

**Each region gets its own lane, from its own door.** `MarshCaveB2` is two
halves that do not connect, and drawing one lane left the other half a map with
no route on it. Two things had to be true for the second lane to appear at all,
and both were wrong first:

- **Regions are read holding what the floor gates on.** A locked door is not a
  region boundary, it is the reason for the second lane; reading regions keyless
  files the gated checks as "not on this floor" and `MarshCaveB3` lost its
  with-key lane entirely.
- **A region's lane must start at that region's own door.** A linked chest with
  a tile in each half belongs to both, so an unconstrained "best arrival" served
  the smaller half from the larger half's door -- drawing a second lane on top
  of the first and leaving the other half bare, which looks exactly like the bug
  it is meant to fix.

**The second lane is drawn as an extension, not as a second line.** Where both
lanes use the same corridor there is one line, in the colour of the walk you can
always do; the key colour appears only on the steps the key actually buys.
Drawing both in full -- even offset by a pixel -- puts two parallel lines down a
shared corridor, which reads as "there are two ways through here", and that is
not what is true. On `MarshCaveB3` it is the difference between 4032 and 1710
pixels of the second colour, all of it now saying something.

**The cost model, measured on `MarshCaveB3` (his "Bottom"), 11 chests:**

| costs | steps | encounter tiles | traps crossed | turns |
|---|---|---|---|---|
| step count only | 380 | 311 | 5 | 65 |
| + turn preference | 380 | 318 | 4 | 58 |
| + encounter floor | 380 | 306 | 5 | 67 |
| + fixed traps | 419 | 347 | **3** | 66 |

The turn preference is free -- same step count, seven fewer counted turns. The
trap term costs 39 steps to avoid two fights, which is worth it. **Three
crossings is the floor, not a failure:** flooding the map with trap tiles made
impassable reaches 8 of the 11 chests, and chests `28`, `31` and `32` are
reachable no other way -- trap `(23,40)` is the only way to 28, `(26,53)` or
`(27,54)` to 31, `(52,54)` to 32. So a lane should draw a forced crossing
differently rather than pretend it avoided it.

**Linked chests belong on the same drawing pass.** A chest index can sit on more
than one tile, so opening any one clears the lot, and nothing on the map says so
today. Measured 2026-08-30 on the oracle corpus — and the count is
**seed-dependent**, so it derives per cartridge rather than from a table:

- **6 multi-tile indices on std, 14 on nov.** The difference is Short ToFR, which
  duplicates indices onto `tofrChaos`.
- **Same-map groups, wanting a grey connecting line:** four, identical on both —
  `25` and `26` on `marshB2`, `29` on `marshB3`, `101` on `volcB4`.
- **Cross-map groups, wanting a badge or a circle rather than a line, because
  there is no line to draw:** two on std (`92` across volcB4+volcB5, `123` across
  ordeals2F+3F), ten on nov, including `254` across `cardia`, `tofr3F` and
  `tofrChaos`.

`extract_chests.extract()` already returns a *list* of placements per index for
exactly this reason, so the data needs no new ROM reading. Note the pin side has
bitten before: keying pins by map name collapses three `marshB3` pins into one,
so compare as multisets.

**Mark the hint givers.** Wanted as an annotation beside the sprite rather than a
PopTracker marker — a reminder of which NPC in a town has something to say, and
whether you have been to them. There is no flag for "talked to", so a pin would
be manual-click forever; drawing it into the art at render time sidesteps that
entirely, and it is the same mechanism the trap marks already use
(`font.draw_text` over the rendered tile). No location node, no autotracking
question.

What is already known, off FFR's own source rather than guessed:

- **The hint givers are a fixed set of eight**, one per town, written as a
  literal in `FF1Lib/NpcHints.cs:452` — ConeriaOldMan `52`, PravokaOldMan `64`,
  ElflandScholar1 `83`, MelmondOldMan2 `110`, CrescentSage11 `130`,
  OnracOldMan2 `154`, GaiaWitch `185`, LefeinMan12 `200`. They are not shuffled
  into the role. None is in `extract_npcs.WANTED` today, and adding them there is
  how their tiles get read.
- **Positions still have to come off the cartridge.** Turning hints on *moves*
  the Lefein one (`maps[MapIndex.Lefein].MapObjects.MoveNpc(0x0C, 0x0E, 0x15…)`),
  which is the same reason the NPC pins stopped reading `npc_positions.json`.
- **Whether the seed has hints at all is knowable.** `flags.HintsVillage` is in
  the decoded schema (`tools/ffr_flags/schemas/4-9-2.json:2255`) and already
  reaches the pack over the bridge.
- **The catch that decides the scope: there are no village hints on an
  Archipelago seed.** `NPCHints()` returns immediately when `flags.Archipelago`
  is set (`NpcHints.cs:427`), alongside DeepDungeon. So this annotation is a
  bridge/UAT-only feature by construction, and drawing it on an AP seed would be
  pointing at an NPC with nothing to say.

Unsettled: whether "have I visited this one" can be shown at all without a flag,
or whether the annotation is purely static and the visited-ness stays in the
player's head. The observation channel the entrance markers are designed around —
the bridge watching party position — is the only thing that could answer it, and
standing next to an NPC is not the same as having talked to them.

**The No-Overworld tab wants an amalgamated map, not a picture of the stub.**
Raised 2026-08-31, deciding what a rendered overworld should do for those
variants. The obvious move is the one that was tried and backed out: draw the
cartridge's own overworld and put it on a tab. It renders correctly -- the
renderer needs no changes and the pins resolve to 27 of 29 -- and it is still
the wrong thing, because a No-Overworld map is an ocean stub carrying nine
one-tile town pads within fourteen tiles of each other, and every continent it
still draws has had its towns, castles and caves erased off it. Cropped to the
pins it is legible and says almost nothing; uncropped it is a picture of
somewhere the seed never goes, which is the reasoning
`scripts/autotracking/maptab.lua` has carried all along.

What those variants want is a map that does not exist in the cartridge at all:
the areas arranged so the *connections* are the subject, in the spirit of the
`nooverworldmap.jpg` sheet they already carry but built from the seed rather
than drawn once. That is the same want as the connection diagram under "The
shape of the fix" in `STATUS.md`, and it is where marking the shuffled
entrances belongs -- on a No-Overworld cartridge the geography carries nearly
no information and the links carry all of it, so drawing the map and drawing
the connections on it are one piece of work rather than two. `entrance_graph`
already emits every door and floor link with tile coordinates, so what is
missing is the surface, not the data. Nothing is blocked on it: the standard
tab is done and the No-Overworld variants are exactly as they were.

**Notice when the drawn maps are for a different cartridge.** Raised while
regenerating after a rules change: the override shadows the checkout, so a stale
override serves stale art *and* stale access rules, and nothing says so. The ask
was to trigger a regen from Lua on connect when the ROM differs from last time,
and keep the images otherwise.

**The caching half already exists.** `.regen_cache.json` records each mode's ROM
sha, the input fingerprint, `--npcs` and the marker geometry, and a second run on
the same cartridge prints `up to date: 129 files ... nothing to do`. So "keep the
images otherwise" is not work; only the trigger is.

**There are two mismatches to detect, not one.** The cartridge can change, which
is what this entry was raised about; the *pack* can also change under a fixed
cartridge, and that is the case that has actually bitten. `INPUT_FILES`
(`regen_maps.py:126-151`) lists `layouts/shared.json` and the four location files,
so the `inputs` fingerprint already moves the moment one is edited. That half is
done: `regen_maps.py --verify` compares it, reads no cartridge and exits 1
naming the stale modes. What it cannot do is fire at the moment it matters,
which is tracker load -- see below, and `docs/ISSUES.md`, "A stale override
silently shadows pack edits".

**The pack cannot be the trigger.** PopTracker's Lua exposes `Tracker` (items,
locations, maps, layouts, `ProviderCountForCode`, `FindObjectForCode`, `UiHint`,
`OpenLink`, `ActiveVariantUID`) and `ScriptHost` (the watches, `CreateLuaItem`,
frame handlers, `RunScriptAsync`/`RunStringAsync`) and nothing else --
`tests/pop_api.lua` is the transcribed surface. No `io`, no `os`. `RunScriptAsync`
runs *Lua*, not a shell command.

**The bridge could be**, mechanically: `ffr_uat_bridge.lua` already reads and
writes files (`EMU.readFile` / `writeFile` / `appendFile`) and already requires
Mesen's "Allow access to I/O and OS functions" for its sockets, so `os.execute`
is plausibly in reach. Two constraints on any version that actually runs one:

- **It has to be eager and detached.** Eager because the useful moment is the
  one where the cartridge is first seen -- on connect, or on the seed swap the
  bridge already detects -- not when someone notices the pins are wrong.
  Detached because a regen renders 61 maps; run inline on the emulator's script
  thread it stalls emulation for the duration.
- **The restart is irreducible.** PopTracker loads pack images at load time,
  which is why `regen_maps.py` signs off with "Restart PopTracker to pick it
  up". No amount of triggering removes that step, so an automatic regen buys
  the render, never the reload -- and a regen the player does not know happened,
  followed by a tracker still showing the old art, is worse than no regen.

**So the first version to build is detection.** The bridge reads
`.regen_cache.json`, compares it against the cartridge in the emulator, and
publishes a variable; the pack lights a warning cell the way `flagsUnread`
already does (`uat.lua:159-203` -- a LuaItem whose Icon appears only when there
is a reason). That fits inside both sandboxes, needs no new permission, and turns
a silent wrong-pins failure into a visible one.

**And then execution, which this page used to argue against.** The old conclusion
was "detection, not execution", on the grounds that a regen the player did not
know happened, followed by a tracker still showing the old art, is worse than no
regen at all. **That objection is answered by the warning cell itself**: once the
mismatch is on screen, the player knows both that the art is stale and that
something was done about it, and the detached regen means the new art is already
waiting by the time PopTracker is restarted. Superseded 2026-08-30 rather than
dropped, because the reasoning is still the reason the warning comes first.

What has *not* changed is the restart. PopTracker loads pack images at load time,
so an automatic regen buys the render and never the reload.

**That precondition is now measured, and it holds.** `os.execute` was called
"plausibly in reach" above on the strength of the file and socket functions the
bridge already uses, which was an inference rather than a test. Run in Mesen's
script window on 2026-08-31, with the "Allow access to I/O and OS functions"
restriction the bridge already requires:

- `os` is a table, and `execute`, `time`, `getenv`, `remove` and `tmpname` are
  all functions on it.
- `os.execute` runs. Checked by side effect -- a file written and read back --
  rather than by return value, because Lua 5.1 and 5.4 disagree about what it
  returns and a stubbed one can look like a success.
- **It detaches.** A backgrounded three-second sleep returned in under a second,
  so the detached half of the constraint above is satisfied by the shell rather
  than needing anything cleverer.

So the execution half is buildable and no longer gates on a measurement. The
order does not change: detection still ships first, for the reason the
superseded paragraph gives -- the warning cell is what makes an automatic regen
legible to the player, and the restart it cannot remove is still there.

One thing it needs first: the bridge has no sha256, so the cache has to record
something cheap to compare. The FFR seed string and flag string are already read
on both sides, so writing those into `.regen_cache.json` alongside the sha is the
enabling change.

**Built 2026-08-31, and that last paragraph was half right.** The comparator is
the seed and flag string, as proposed -- but not written into
`.regen_cache.json`, because the reader has no JSON parser either. It goes in
`.regen_stamp`, one line per mode. And "the bridge has no sha256" skipped a
step: the bridge has a *sha1*, `emu.getRomInfo().fileSha1Hash`, which it already
spends as the cartridge id. What that hash covers is not written down anywhere
here, so the stamp records the file's sha1 and the bridge lets it agree but
never disagree; `bridge/probe_rom_id.lua` is the measurement that would settle
it. Detail in `STATUS.md`, "The art on disk now says what it was drawn for".

**Incentive and gate markers want their own shape, and the shape is already
taken.** Proposed 2026-09-02: incentive slots and gating events draw as diamonds
on the map tabs while plain chests stay squares, so a glance separates "a key
item was placed here" from "this is a chest". Feeding Titan is a gating event;
the Floater turn-in is probably another; the full list is not drawn up.

**Scope it against the base randomizer first; Archipelago is the later case.**
That is not only a priority call, it is where the idea is native: an incentive
slot is an FFR concept, defined by the `Incentivize*` flags in FFR's own schema,
so a solo cartridge is what the shape is describing. An AP seed draws its pool
from Archipelago instead, and what a diamond should mean there is a separate
question that does not have to be answered to build this.

The obstacle is that `diamond` already means something, and for a *rendering*
reason rather than a semantic one. PopTracker's rect pin is opaque -- `drawRect`
fills its interior with a solid state colour and `StateColors` carry no alpha --
so a square pin on a tile with an NPC sprite drawn under it hides the sprite
completely. `place_locations` emits a diamond exactly there, leaving the tile's
four corners unpainted so the sprite reads through (`tools/regen_maps.py:928`).
Titan's new pin came out a diamond for that reason and not because he is a gate.
So this cannot simply adopt the shape: it has to say what a pin does when it is
both an incentive and standing on a sprite. That is the question `ROADMAP.md`
section 3 already holds as "What a diamond means", and this is a candidate
answer to it rather than a separate item.

Three shapes exist, not four: rect, diamond and trapezoid, with no circle, and
state colours are not pack-selectable. Trapezoid is the one nothing uses yet,
which makes it the obvious third channel if diamond stays booked for sprite
collision.

**A union is the cheapest way out, and it is coherent.** Let a diamond mean
"a sprite check or an incentive slot" -- every notable sprite and event flag is
a diamond, and not every diamond is one, because incentive chests are diamonds
too. Nothing breaks: the rendering constraint is one-directional, a pin *on* a
sprite must be a diamond or it hides it, and adding more diamonds never violates
that. What is given up is reading the shape backwards; a diamond stops meaning
"there is a sprite here" and starts meaning "something here is worth a look",
which may be the more useful sentence on a board anyway.

**Settled 2026-09-04, as the naming half only.** The union is now what a diamond
means: `docs/ISSUES.md`, "What a diamond means", records it and `README.md`,
"What the pin shapes mean", tells a player. It was settled because the trapezoid
was about to arrive meaning "entrance", and three shapes on a board people read
is the wrong moment to discover the second one means two things. Nothing changed
in what gets drawn -- the decision licenses incentive-slot diamonds, it does not
emit them. What is still unscoped is below: emitting them at all, the shop leak
that comes with it, and whether shape is even the right channel.

Two consequences to settle before drawing. **The sprite half is decided by a
render flag, not by the seed**: `sprite_cells` is empty under `--npcs none`, so
with sprites off every diamond is an incentive and with them on it is the union.
A legend that says what a diamond means therefore has to be written from how the
art was drawn, which is the kind of conditional that goes stale. And **shape is
not the only free channel** -- `size` and `border_thickness` are already
per-marker (the regen writes `size: 16, border_thickness: 2`), so a thicker or
larger pin could carry "incentive" and leave the diamond to mean sprite alone.
Worth trying against the union rather than assuming shape is the axis.

**The shop pin is the one place this leaks, and the leak is new.** The bridge
already knows whether the seed put a key item in any shop -- `readShopSlot`
returns `item = nil` when none did, and the comment beside it says that is an
ordinary outcome on roughly half of solo seeds. It publishes neither the shop
nor the item on purpose, because naming either hands over the hunt, and
`ff1/shopitem` carries only whether the thing has been bought. A diamond on that
pin would say "there is one somewhere, go look" without naming which shop --
weaker than what the pack currently refuses, but not nothing. So this idea owes
a decision the pack has so far been able to avoid: does the board admit that a
key item is in a shop at all? Answer it before drawing the shop pin, not after.

Where to try it: the incentive sheet first, because it is one hand-drawn image
whose pins are all slots, so nothing there competes for the shape. The overworld
is the crowded one and the place the idea might not survive. Inside a dungeon
tab, where a floor holds a handful of pins, the distinction should read easily.
None of that is knowable without drawing it.

**The icon half is a separate change, to the Locations grid rather than the
maps, and it is a redraw of cells that already exist rather than a new
encoding.** The rule: an incentive slot that is a *chest* draws as a chest
carrying the area's glyph, and a key as well where the slot is behind a locked
door. An incentive slot that is a *person* keeps the person. What the icon is
for is telling the player what they are hunting, and today it does the opposite
on most of the board.

**The grid already makes the split; the icons are the only thing out of step.**
Rows 1 and 2 of `shared_locations_grid` are the NPC slots and rows 3 and 4 are
the chest slots -- but nine of the eleven chest cells are drawn as a monster or
a person. `seaShrine.png` is a mermaid, `earth.png`, `redD.png`, `ordeals.png`,
`iceCave.png`, `skyPalace.png` and `marsh.png` are the creature you meet near
the chest, and `titansTrove` is the Titan himself. A player reading row 3 is
told to look for people.

The eleven, with what each would carry:

| cell | drawn as |
|---|---|
| `marsh` | a chest with the Marsh Cave glyph |
| `marshLocked` | the same, and a key |
| `coneriaLocked` | a chest with the King of Coneria, and a key |
| `iceCave` | a chest with the Ice Cave glyph |
| `ordeals` | a chest with the Castle of Ordeals glyph |
| `titansTrove` | a chest with a Titan on it |
| `cardiaIncentive` | a chest with Bahamut on it |
| `earth` | a chest with the Earth Cave glyph |
| `volcano` | a chest with the Gurgu Volcano glyph |
| `sea` | a chest with the Sea Shrine glyph |
| `sky` | a chest with the Sky Palace glyph |

`shopItem` sits in row 4 and is deliberately not in the table: it is a shop
rather than a chest, and it is the one slot with no `^$incentiveSlot` flag at
all, so whatever it draws as should say "shop" and not "chest".

The key on the two locked rows is not a second encoding of the locked state --
those cells already *are* the locked halves, `coneriaLocked` and `marshLocked`
-- it is the icon finally saying what the cell has always meant.
`cardiaIncentive` is safe to draw as Bahamut specifically: that section is named
"Cardia Incentive - Hoard" and carries `visibility_rules: ["BahamutHoard"]`, so
it is on the board only when the Hoard flag is on.

This also settles a gap recorded 2026-09-02. `images/locations/titan.png` is the
Titan sprite and currently serves both `titansTrove` and the Titan NPC cell,
which now sit in adjacent rows wearing the same picture. Under this scheme the
NPC keeps the bare sprite and the Trove gets the chest with a Titan on it, which
is the distinction those two cells needed anyway.


## Bosses and trap tiles

The four fiends and the ToFR refights have no pins. Two separate problems wearing
one label, and neither needs new ROM reading:

- **The four fiends are map objects.** `extract_npcs.WANTED` already reads their
  tiles off the seed — lich on map 32, marilith 36, kraken 42, tiamat 51, and
  the same four in `tools/npc_positions.json`, which is the vanilla snapshot
  those numbers came from — and `tools/tests/test_npc_pins.py` lists them as
  deliberately unpinned. What is missing is a location node for a pin to belong
  to.
- **The refights and traps are `TP_SPEC_BATTLE` tiles.**
  `render_maps.fixed_formations()` already reads byte 1 of each — the formation
  id, which is *which boss spawns* — and `trap_marks()` then spends it on a
  mark rather than a name. Naming the boss is reading a field the code already
  has in hand, and since the marks became formation-keyed the mapping from mark
  to fight is one-to-one, so a Map Key row could carry the name directly.

Placement would reuse `regen_maps.place_locations()`, which builds a pin from a
tile: hand it more tiles and it emits more pins. A boss tile is not walkable, so
a pin on it wants offsetting by a tile — that is `± tile_px` in the same
transform, and there is precedent for the problem in the other direction (the
shipped art draws Astos one tile above the cell the cartridge places him on).

**ToFR is not one layout, and the bosses move with it.** `ToFRMode` is
`Long / Mid / Short / Random` (`FF1Lib/TempleOfFiends.cs:6-16`) and it changes
which floors exist and where the fiends stand:

- **Long** wires the whole gauntlet, 1F through 3F and the four elemental
  floors.
- **Mid** (`:138-153`) repoints 1F's left stairs straight at the Earth floor and
  blocks the passages to Stairs B, so **2F and 3F are not in the dungeon at
  all**. Both standard seeds here are Mid.
- **Short** collapses it further, and the fiends end up on the Chaos map.
  Measured on `F258553F`: `tofrChaos` carries **8 fixed-formation trap tiles in
  a row at y=9**, where both Mid seeds have none on that map.

`FiendsRefights` moves them again -- `None` writes `0x5C` over the four refight
tiles outright (`TempleOfFiends.cs:92-97`), and `TwoPaths` shuffles which floor
each staircase leads to.

So any boss annotation has to read the cartridge, never a vanilla table. The
good news is that the existing mechanism already does: `fixed_formations()`
enumerates fixed-formation tiles off the tileset property tables and
`map_trap_marks()` asks one map which of them it places, so both are
mode-correct by construction. The thing to avoid is hardcoding a floor list or a
tile position from vanilla.

Note the keying changed under this idea and in its favour. These used to be
`trap_letters()` / `map_trap_letters()`, keyed `(tileset, tile)`, which drew the
same fight as two different letters on two maps — useless for naming a boss.
They are keyed to the formation now, so a mark identifies a fight rather than a
position.

The blocker is unchanged and is in `docs/ISSUES.md`: none of them writes a flag,
so every such box is manual-click forever. Worth deciding whether that is
acceptable before drawing anything.

## On the derivation

**Memoize the floor walk. Built 2026-08-30.** Instrumenting a full 1024-subset
sweep on a No-Overworld cartridge said 99.8% of it was repeated work:

    floor_walk calls over the full sweep : 86464
    distinct (map, arrival) pairs        :   129
    distinct results across all of them  :   188

92 of the 129 pairs produced the same walk no matter what was held, and none
produced more than four distinct results, so 86464 calls were doing 188 walks'
worth of work.

The key could not be `have` wholesale — that is one distinct set per subset and
gives no reuse at all. It is `(map, arrival, stop_on_teleport, have & the items
this floor consults)`, with the floor's items found by scanning its tile
properties and objects for what `walkable()` and `gated_objects` actually
consult. On the vanilla cartridge 42 of the 61 floors consult nothing and are
walked once for the whole sweep; on the No-Overworld oracle it is 38. Both
`floor_walk` and `reachable_teleports` are memoized -- the filed design counted
only the first, and `reachable_tiles` calls both, so a memo on one is half a
memo.

The key was the entire risk: one that omits an item the walk consults returns
stale reachability silently, which is the failure class this tree has hit four
times. `tools/tests/test_memo_walk.py` guards it two ways. The cheap one is
exhaustive and runs every time: a walk reads `have` in exactly two places, so if
neither `walkable()` on any of a map's property bytes nor `blocking_objects()`
on its objects can tell `have` from the trimmed key, over every map and all 4096
subsets, then no walk can. The expensive one is the equivalence the entry
demanded -- every subset, memoized against unmemoized, tile for tile -- and runs
on `FF1_SLOW=1`; it passed on the `nov` cartridge over all 4096 subsets on
2026-08-30.

It does not move the exponent, and did not have to. The outer loop is still 2^n,
but the sweep went from 1024 subsets in about 85 seconds to 4096 in about 57 --
which is what made the SubEngineer and Titan rows affordable in the same commit.

That comparison is across two runs and folds the memo together with the
vocabulary widening, so this entry's own "no speedup is quoted here" is answered
properly by an A/B on one build instead. Measured on `nov` 2026-08-30, same
gates and same twelve items either way, the memo switched off by the `NoMemo`
subclass `tools/tests/test_memo_walk.py` already carries:

    memoized     14.0 ms/subset      57.2s for 4096   (the real sweep, timed)
    unmemoized   77.5 ms/subset     ~318s for 4096   (projected from 120)

**About 5.5x.** Projecting the unmemoized side is fair because it has no
cross-subset reuse by construction, and the rate holds across sample sizes --
79.1 ms at 40 subsets, 77.5 at 120. It also brackets the old pre-memo run from
the other side: 85 seconds for 1024 is 83 ms/subset, so the walk was costing
what it costs unmemoized now and the memo is doing essentially all of the
difference.

Within a single subset the memo is only about 4x -- 18.8 ms against 79.1 on a
40-subset sample, which is the reuse inside one `reachable_tiles` fixed point.
The rest comes from the cache saturating across the sweep: 38 of `nov`'s 61
floors consult no item at all, so they are walked once for all 4096 subsets
rather than 4096 times, and the whole lattice only ever produces about 188
distinct walks.

The five further items -- the Slab, the Herb, the Adamant, the Bottle and the
Crystal -- are trades rather than tiles, so they want the solver below rather
than more headroom. It was seven before this commit; Oxyale and the Ruby were
the two that turned out to be tiles after all.

**Solve the requirements instead of sampling them.** The sweep asks the walker
2^n times. FFR does not: `Sanity/SCLogic.cs` propagates `SCRequirements` bitflags
over the map it built, which is a fixpoint over the graph rather than a sweep
over the item lattice. Reachability here is monotone — holding more never closes
a route — so the same shape works: each tile carries an or-of-ands requirement,
minimised as it propagates, and the output is the expression directly rather than
a set of samples to minimise afterwards.

That is the only approach that survives the items the derivation currently cannot
express, and it emits the same shape `check_logic` already compares against. Two
things to hold on to when it is done: the sweep's agreement with FFR is
much weaker than it was once recorded as. Most comparisons used to grant the
disputed item to both sides -- 58 of 222 were really compared -- and closing the
SubEngineer and Titan gates took that to 221 of 226, so the sweep is now a real
check on the twelve-item vocabulary rather than the oracle it was called here.
What is left outside it is not a graph property at all: the trades, and the
requirements that name another *location* rather than an item -- Lefein wants
the Slab translated, which is Dr Unne's own reachability. That last shape is the
one the sampling approach cannot express at any vocabulary size, and it is the
strongest argument for the solver.

**FFR already runs that solver, and the oracle is its output -- which changes
what is worth building.** `SanityCheckerV2` builds the map, `SCLogic` propagates
`SCRequirements` over it, and `FF1Lib/archipelago/Archipelago.cs:205` serialises
the result as the export's `rules:` section: one entry per Archipelago location,
`List<List<string>>`, an or-of-ands of item names. That is the file
`tools/check_logic.py` already grades against. So the interesting option is not
writing a propagation pass. It is **compiling the pack's Lua rules from that
export** instead of hand-writing them or sampling them.

That dissolves the Lefein class outright rather than working around it.
`SCLogic.cs:555-557` resolves the translated Slab to `allNpcs[Unne]` restricted
by the Slab -- a requirement naming another location -- and by the time it
reaches the export it has been flattened to items, `(Tnt OR Ruby OR Canoe) AND
Floater AND Slab`. Nothing downstream has to express "reach another location",
because the solver already did.

**The class has two members, not one, and the second is the stronger
argument.** `SCLogic.cs:559-562` is `allNpcs[ElfDoc].Restrict(Herb)`, the same
shape, and the derivation gets the Elf Prince `(free)` where FFR says `(Herb)`.
Lefein at least reports itself as the one `--derived` divergence; the Elf Prince
passes as agreeing, because `herb` is off-vocabulary and `check_logic` grants it
to both sides. So the sampling approach is not merely unable to express this
shape -- it cannot currently see how often it is hitting it. Full write-up in
`docs/ISSUES.md`. The vocabulary is wider too: `nov`'s rules
mention fifteen distinct items, including `Mark` and `Sigil` (the renamed Canoe
and Floater), against the twelve `entrance_graph.ITEM_NAMES` sweeps, and all
five trades the sweep cannot hold -- Slab, Herb, Adamant, Bottle, Crystal -- are
in there.

Three things to settle before this is a plan rather than an idea.

- **The export is per-seed and the pack ships one rule set.** Not a new problem:
  158 of `nov`'s 226 pack-side rules were already transcribed from one seed's
  export, per the provenance table in `docs/ORACLE.md`. Compiling makes that
  dependence visible rather than introducing it, and gives it a test -- compile
  from two seeds at identical flags and diff. On No-Overworld the difference is
  likely small, since three seeds carry 157 links each and differ only in the
  Gaia gateway and the two Waterfall stairs. Under entrance rando it would not
  be.
- **`Orbs` is the one requirement flag the export drops.** `SCRequirements` has
  twenty flags; both `GetRule` overloads emit nineteen and neither emits `Orbs`
  (`0x0100`), so a location requiring it exports with an empty -- that is,
  free -- clause. It does not bite today, because the orb-gated floors are the
  Temple of Fiends Revisited and those are excluded from the Archipelago pool
  unconditionally. A compiler would inherit the hole in silence, so it needs a
  guard that refuses an empty clause it cannot account for.
- **`ExtSpoiler.cs` is the wrong source.** Its `WriteItemPlacementSpoiler` uses
  the same `GetRule` shape, but filters `logic.RewardSources` to incentive
  items, quest items and orbs, so the `.txt` carries requirements for a handful
  of slots rather than all of them. The yaml's `rules:` is over every reward
  source: 227 locations on `nov`, 226 on `std`, 230 on `shard`.

**And the argument against, which is the one to answer first.** The current
setup's whole value is that the two sides are independent -- rules written one
way, graded against an answer produced another way. Compiling makes the oracle
and the rules the same object, so they agree by construction and
`check_logic.py` stops being a check at all. What would replace it is the
cartridge sweep, which is the genuinely independent third reading and today
supports 215 of `nov`'s 226. Whether that is enough cover is the decision, and
it is a decision about provenance rather than an optimisation. It wants its own
session; `docs/ROADMAP.md` says so at the bottom rather than queueing it.

## Notes and hints

Wanted: somewhere to write down a hint — which orbs a seed requires, what an NPC
said — ideally auto-populated as checks resolve.

**PopTracker has no notes feature.** Layouts have a static `"text"` widget and
items can carry short overlay badges; there is no free-text input anywhere. So a
manual notes surface is not a pack-side thing to build.

What does exist is `Archipelago:LocationScouts(locations, sendAsHint)`, since
0.26.2, gated on an `aphintgame` flag in `manifest.json` that this pack does not
currently set. That is the real hint path, it needs no ROM tooling, and it is
Archipelago-only — which on this pack means it would cover the thinner of the two
feeds.

Tied to this: **which orbs a seed requires is deliberately not derived.**
`scripts/logic.lua` returns 4 whenever `OrbsRequiredMode` is non-zero, because
which orbs is rolled into the seed rather than the flag string. Reveal-on-
observation — the pack learning by watching the player, the way the entrance
markers are designed to — is the shape that would not spoil. Parked here until
there is a surface to show it on.

## Options UI, pass 2

`layouts/settings_popup.json` is a named layout PopTracker recognises: define it
and a gear button appears in the toolbar opening a pack-specific settings window.
The Crystal pack uses it for ~60 seed settings across two tabs. Worth doing once
there are enough visibility toggles to justify a panel; until then they fit in
the existing flags grid.

## Names that have drifted

None urgent, none decided. Grouped because they are the same kind of question — a
label chosen for what this was, still attached to what it has become.

**`package_version` was `1.1b`, which was upstream's, on a tree sharing little
with the pack that carried it. Changed to `0.1.0` on 2026-09-01**, a fresh line
starting at the fork rather than a claim on a lineage that had stopped being
true. `0.x` says the honest thing about how much of `ROADMAP.md` is still open,
so it needs no second marker on top of it.

**One thing in that reasoning was wrong and is worth keeping written down.** It
said PopTracker "uses it for nothing else — no update check, no compatibility
gate — so any value is safe". The first half holds; the conclusion does not.
Saved state is filed at `<statedir>/<uid>/<version>/<variant>/<name>.json`
(`core/statemanager.cpp:54-66`), so the version string is part of the path a
board is saved under and **changing it orphans saved boards** exactly the way
changing the uid does. Nothing is lost or corrupted — the old directory stays
where it is — but a board does not come back. That is a cost worth paying once
and not worth paying twice, which is the argument for moving the uid in the same
release rather than later.

`game_variant` went with it, from `Entroper (V4.8.6)` to the versions the pack
actually models. Nothing in the pack reads that field; it was simply three minor
versions stale.

The `author` line is deliberately unchanged: it credits the five people whose
pack this started from, and that is what it is for.

**The repo is called `FFR_AP_autotracking`, and most of it is not AP.** The
Archipelago feed carries checked locations and items received and nothing else;
everything else comes off the cartridge over UAT. So the name points at the
thinner feed. Bringing AP to parity is not pack work at all — it means changing
`worlds/ff1` in Archipelago to publish slot data, a different repository and a
different review path. Worth being explicit about that split before any renaming,
because the name is the only place it currently reads as though this repo could
close the gap on its own.

**The four `NoMap` variants.** PopTracker's chooser lists eight entries, four of
them map-less. They are not the broadcast windows — every variant already loads a
broadcast layout of its own — they are full trackers whose main window has no map
tabs. So the chooser offers a one-in-eight chance of landing in a variant with no
maps, on a pack whose recent work is almost entirely maps. Against dropping them:
they are cheap, and they are what someone with a small screen or a second monitor
would pick. For dropping them: every layout and location change has to be sound
in both trees, and nobody here runs them. Deciding needs the one thing nobody
knows — whether anyone outside this repo uses the pack.

**What a new user gets without the emulator bridge, and what the pack claims
about its assets.** Raised 2026-08-30 while looking at the regenerated maps. The
facts, gathered rather than assumed, because most of the answer turns out to be
"this already works" and the rest is one thing the README does not say.

- **Mesen is the emulator feed, and only the emulator feed.** `bridge/` is one
  Lua script Mesen runs. Nothing else in the pack needs it.
- **Without it, the Archipelago feed still autotracks.** What it cannot see is
  already written down under "What each feed can see": chests outside the
  multiworld's pool, orbs lit, items turned in, and shards from lighting orbs.
  A plain FFR async has no AP server either, and that is the case the bridge
  exists for.
- **Manual tracking is what the four `NoMap` variants are**, and the four map
  variants work with no ROM and no emulator at all — they load the 53
  hand-drawn PNGs in `images/maps/`, which ship with the pack.
- **Those PNGs are the pack's only substantial shipped assets**, 12 MB of them,
  inherited from the pack this forked and credited in the README. The README's
  claim is that no ROM is included and that no art *derived from one* is either,
  and both hold: `regen_maps.py` writes only into PopTracker's user-override
  directory. The hand-drawn maps are a different thing and are not covered by
  that sentence, which is easy to misread as "no assets ship at all".
- **The Pins toggles are map-only, and that is correct rather than a gap.**
  Measured: the `Pins` group appears in `standard/tracker.json`,
  `shardHunt/tracker.json`, `NOverworld/tracker.json` and
  `NOverworld/shardsTracker.json` — the four map variants. A variant with no map
  tabs has no pins to switch off, so parity here would mean adding a control that
  does nothing.

  **The Flags group was not map-only and had no such reason. Fixed 2026-09-01.**
  It was in the standard and shard-hunt layouts and nowhere else, so six of the
  eight variants showed no seed settings at all while `scripts/init.lua` went on
  setting `tab_switch` and `tab_mode` for them — the behaviour on, the controls
  invisible, and the README describing both as though they were there. The two
  No-Overworld map variants have it now, on `NOverworld_flags_grid`: the same
  grid minus `tab_mode`, which is the one cell that genuinely does nothing there
  because `maptab.lua`'s `overworldTab()` returns the incentive poster before it
  ever asks. `tests/test_mapping.lua` holds the two grids together so the fork
  cannot drift. The four `NoMap` variants stay thin, for the reason above.

So the bridge-less experience is fine and mostly documented. What was missing was
one sentence saying it: that the map tabs work out of the box on hand-drawn art,
that rendering them from your own cartridge is an optional upgrade, and that the
emulator feed is what the extra boxes need. That paragraph is in the README now,
along with a "Which variant shows what" section, since the honest answer to that
turned out to be shorter than the investigation.

The open question underneath is the one the `NoMap` entry above already names —
nobody knows whether anyone outside this repo runs the pack — and it is worth
answering before spending on either.

## Tell "unmeasured" apart from "unmeasurable from this corpus"

Raised 2026-09-03, by `LefeinSuperStore`. Its coverage row said the No-Overworld
75-link table had been derived with the flag off; every preset in both corpora
sets it on, so the table was derived with it on and no cartridge here has ever
varied it. Both statuses print as `unjudged` and both reasons read as "nobody
got to it", but one is answered by rolling a seed and the other says the seed
does not exist yet. A reader acting on the wrong one re-measures the corpus.

The check is mechanical and wants no prose matching. `tools/tests/test_flag_coverage.py`
already parses the rows and their statuses; the presets are JSON on disk beside
the cartridges. For every flag a row leaves unsettled, read its value across
every preset and report which of the two states it is in. Then the assertions:

- a row whose flag is **unanimous across the corpus** may not claim a cartridge
  measured it, and may not name a value the corpus contradicts;
- a row that says a derivation was made "with the flag off" or "on" is holdable
  against the presets directly, since that is a claim about a file on disk.

The second is the one that would have fired here, and it is the cheaper half:
it needs no judgement about what a row *should* say, only that what it says
about a preset matches the preset.

Two things make this more than bookkeeping. It is a check on the *reasons*, and
this pack's coverage table has now been wrong in a reason twice while every
status was right — the `flag-coverage` review found the first, a row naming a
conjunction only one term of which ever fired. And it fails closed on a machine
with no corpus: no presets, no claim to check, skip.

Cost is a corpus read and a value comparison per unsettled row, so it belongs
in the gated half of the suite that already skips without `FF1_CORPUS`.

**Still wanted after the flag that raised it was settled.** `LefeinSuperStore`
was measured on 2026-09-03 by rolling `novnolefein`, so it is no longer
unanimous and no longer unsettled -- but the three rows still filed `unjudged`
make the same kind of claim with the same nothing holding them to it, and the
answer here was that rolling the cartridge cost less than the two wrong reasons
that preceded it. The check's real value is that it names which of the two
states a row is in *before* someone spends a day arguing from a call site.
