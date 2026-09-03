------------------------------------------------------------------
-- The seed's settings, applied to the board.
--
-- scripts/autotracking/flags_decode.lua turns the cartridge's flag string into
-- FFR's own setting names; this maps those onto the pack's flag items and
-- keeps the whole decoded set around for logic that has no item to hang off.
--
-- Names were read off FFR's own Overworld and Incentives tabs
-- (FF1Blazorizer/Tabs/*.razor), not guessed from the pack's labels -- several
-- pairs read alike and mean different things. "Main NPCs" is
-- IncentivizeFreeNPCs while "Fetch Quest NPCs" is IncentivizeFetchNPCs, and
-- the pack's Northern Docks is MapOpenProgressionDocks rather than any of the
-- three flags with Dock in the name.
--
-- A tri-state left on "random" decodes to nil. That is not the same as off --
-- it means the generator rolled it and the string does not say which way -- so
-- those are left on whatever the flag grid already had, and named in the log.
------------------------------------------------------------------

-- Every setting for the cartridge in the slot, or nil when nothing has been
-- decoded. Logic helpers read this through ffrFlag(); see scripts/logic.lua.
FFR_FLAGS = FFR_FLAGS or nil

-- The flag string this was decoded from, so a re-send of the same seed is not
-- mistaken for a new one and does not stamp over a deliberate override.
FFR_FLAGS_SOURCE = FFR_FLAGS_SOURCE or nil

-- `default` is the cell the board starts on, and the one resetFlagsToDefaults
-- puts it back to; absent means off. scripts/init.lua applies these rather than
-- writing its own copy, because the same set has to be restorable when a
-- cartridge turns up whose settings cannot be read -- two lists would drift,
-- and the one that drifted would be the one nobody looks at.
local TOGGLES = {
  { ffr = "MapOpenProgressionDocks", code = "northernDocks" },
  { ffr = "MapAirshipDock",          code = "luffyDock" },
  { ffr = "MapBahamutCardiaDock",    code = "cardiaDock" },
  { ffr = "MapLefeinRiver",          code = "lefeinRiver" },
  { ffr = "MapBridgeLefein",         code = "lefeinBridge" },
  { ffr = "MapGaiaMountainPass",     code = "gaiaMountain" },
  { ffr = "MapHighwayToOrdeals",     code = "hwyOrdeals" },
  { ffr = "MapRiverToMelmond",       code = "melmondRiver" },
  { ffr = "MapSardasForest",         code = "sardasForest" },
  { ffr = "ShipDrydock",             code = "shipDrydock" },
  { ffr = "MapAirshipHike",          code = "airshipHike" },
  { ffr = "MapCardiaLandBridge",     code = "cardiaLandBridge" },
  { ffr = "EarlyKing",               code = "earlyKing", default = true },
  { ffr = "EarlySarda",              code = "earlySarda", default = true },
  { ffr = "EarlySage",               code = "earlySage", default = true },
  { ffr = "EarlyOrdeals",            code = "earlyOrdeals", default = true },
  { ffr = "NoTail",                  code = "noTail" },
  { ffr = "ChaosRush",               code = "chaosRush" },
  { ffr = "ShuffleObjectiveNPCs",    code = "objectiveNPCs" },
  { ffr = "IncentivizeFreeNPCs",     code = "npcsAreIncentive", default = true },
  { ffr = "IncentivizeFetchNPCs",    code = "fetchQuestsAreIncentive", default = true },
  { ffr = "IncentivizeIceCave",      code = "iceCaveIsIncentive", default = true },
  { ffr = "IncentivizeOrdeals",      code = "ordealsIsIncentive", default = true },
  { ffr = "IncentivizeMarsh",        code = "marshIsIncentive", default = true },
  { ffr = "IncentivizeMarshKeyLocked", code = "marshLockedIsIncentive" },
  { ffr = "IncentivizeTitansTrove",  code = "titansTroveIsIncentive" },
  { ffr = "IncentivizeEarth",        code = "earthIsIncentive", default = true },
  { ffr = "IncentivizeVolcano",      code = "volcanoIsIncentive" },
  { ffr = "IncentivizeSkyPalace",    code = "skyIsIncentive", default = true },
  { ffr = "IncentivizeSeaShrine",    code = "seaIsIncentive", default = true },
  { ffr = "IncentivizeConeria",      code = "coneriaLockedIsIncentive", default = true },
}

-- Flags FFR's logic consults that carry no code here, each with the reason.
--
-- A flag with no code is ambiguous on its own: nobody can tell "decided
-- against" from "not got to yet", and FLAG_COVERAGE.md kept having to say
-- which. Naming them here settles it in the same file the codes live in, and
-- gives the tests something to hold the list against --
-- tools/tests/test_flag_coverage.py greps FFR's own source and fails when a
-- flag it consults is in neither this table nor the ones above it.
--
-- `status` says which kind of "no code" it is, using the key
-- docs/FLAG_COVERAGE.md already publishes, so an entry and its row on that page
-- can be checked against each other instead of drifting apart:
--
--   ram           the effect lands in $6000-$62FF and the pack reads it there
--   variant       answered by which tracker variant is loaded
--   noise         sits in a grepped file without reaching reachability at all
--   unmodellable  a permutation chosen at generation that no toggle can state
--   decided       read, understood, and deliberately given no code
--   unjudged      consulted, and not settled yet -- carries `measure`
--
-- `computed = true` marks a flag FF1Lib derives rather than stores
-- (FlagsCompute.cs). Those have no field in either shipped schema, so a code
-- could not read one even if it wanted to, and tests/test_flags.lua exempts
-- them from its "every named flag is a real flag" check on that basis.
--
-- `unjudged` is the entry that keeps this list honest. A list padded to make
-- the test pass is the test not existing, so a flag nobody has measured says
-- so and names the measurement rather than borrowing a neighbour's reason.
local NOT_MODELLED = {
  {
    ffr = "ExitToFR",
    status = "decided",
    why = "writes an exit portal and nothing else. It reads 0x40, "
       .. "TP_TELE_WARP, and reachable_maps only follows TP_TELE_NORM, so it "
       .. "creates no way in -- and this pack does not model points of no "
       .. "return, so there is nothing for it to gate. See NOVERWORLD.md, "
       .. "\"the exit portal is an exit and nothing more\".",
  },
  {
    ffr = "IsShipFree",
    status = "ram",
    computed = true,
    why = "computed as FreeShip | NoOverworld (FlagsCompute.cs:80), so it has "
      .. "no field in either shipped schema and no code could read it. A "
      .. "free Ship is in the starting inventory, so it shows up in $6000 "
      .. "like a Ship the party sailed to; the pack reads the RAM and never "
      .. "the flag.",
  },
  {
    ffr = "IsBridgeFree",
    status = "ram",
    computed = true,
    why = "computed as FreeBridge | NoOverworld | DesertOfDeath "
      .. "(FlagsCompute.cs:83). The bridge reads out of $6008 whether the "
      .. "seed gave it away or the party built it.",
  },
  {
    ffr = "IsCanalFree",
    status = "ram",
    computed = true,
    why = "computed as (FreeCanal & !NoOverworld) | DesertOfDeath "
      .. "(FlagsCompute.cs:84). The canal reads out of $600C either way.",
  },
  {
    ffr = "IsCanoeFree",
    status = "ram",
    computed = true,
    why = "computed as FreeCanoe | DesertOfDeath (FlagsCompute.cs:81). A free "
      .. "Canoe is an inventory item like any other Canoe.",
  },
  {
    ffr = "IsAirshipFree",
    status = "ram",
    computed = true,
    why = "computed as FreeAirship & !NoOverworld & !DesertOfDeath "
      .. "(FlagsCompute.cs:82). It arrives as the Floater's second "
      .. "progressive stage, which the pack reads from inventory.",
  },
  {
    ffr = "FreeLute",
    status = "ram",
    why = "starting inventory (FF1Lib/StartingItems/StartingItems.cs:59 -- "
      .. "the path matters, there is a second StartingItems.cs under "
      .. "FF1Lib/Data/). The Lute is an inventory item and reads the same "
      .. "whether the seed handed it over or the party found it.",
  },
  {
    ffr = "FreeRod",
    status = "ram",
    why = "starting inventory, the Lute's case exactly. Nothing about a rule "
      .. "changes -- only how early the item shows up in RAM.",
  },
  {
    ffr = "NoOverworld",
    status = "variant",
    computed = true,
    why = "computed as GameMode == GameModes.NoOverworld "
      .. "(FlagsCompute.cs:77), so it is not a schema field. The pack "
      .. "answers it with isNoOverworld() off the variant UID, because the "
      .. "mode needs a different location tree rather than a toggle, and the "
      .. "modeMismatch light says so when the cartridge and the chosen "
      .. "variant disagree.",
  },
  {
    ffr = "IsFloaterRemoved",
    status = "decided",
    computed = true,
    why = "computed as ((NoFloater|IsAirshipFree) & !NoOverworld) | "
      .. "DesertOfDeath (FlagsCompute.cs:85). Its one read inside "
      .. "FF1Lib/Sanity/ clears MapChange.Airship out of requiredMapChanges "
      .. "(SanityCheckerV2.cs:178), which feeds the completion test and no "
      .. "per-location rule -- so no exported rule can move with it and no "
      .. "pin can change colour. Verified 2026-09-01; docs/FLAG_COVERAGE.md "
      .. "section A carries the working.",
  },
  {
    ffr = "DisableOWMapModifications",
    status = "decided",
    computed = true,
    why = "computed as GameMode == Standard && OwMapExchange != None "
      .. "(FlagsCompute.cs:50), so it is not an independent toggle: it is "
      .. "true exactly when an exchanged overworld is in play, and it then "
      .. "suppresses every map-open flag at OverworldMap.cs:37. An exchanged "
      .. "overworld is unmodellable rather than uncoded, and the warning "
      .. "that covers it already exists -- the OwMapExchange line in this "
      .. "file.",
  },
  {
    ffr = "ChestsKeyItems",
    status = "decided",
    why = "already read, just not through a flag item: "
      .. "cartridgeChestsAreChecks() in scripts/autotracking/maptab.lua:87 "
      .. "asks ffrFlag for it directly, and that answer reaches "
      .. "chestsAreChecks() and logic.lua's showPin(). What it carries no "
      .. "code for is its second role, the conjunct FFR ANDs onto "
      .. "ShuffleObjectiveNPCs (NPCs.cs:135): with it off the shuffle does "
      .. "not run and the $noObjectiveShuffle guard is needlessly strict, "
      .. "which is the side to be wrong on -- strict holds a pin red where "
      .. "FFR opens it, and the pack already prints that divergence rather "
      .. "than hiding it. A code would only relax it.",
  },
  {
    ffr = "BossScaleHpHigh",
    status = "noise",
    why = "an enemy HP scaling bound, passed to ScaleSingleEnemyStats at "
      .. "TempleOfFiends.cs:252. It is caught by the grep because the fiends "
      .. "are rescaled in a file the map flags also live in; it changes how "
      .. "hard a fight is and never whether a tile can be reached.",
  },
  {
    ffr = "BossScaleHpLow",
    status = "noise",
    why = "an enemy HP scaling bound, passed to ScaleSingleEnemyStats at "
      .. "TempleOfFiends.cs:252. It is caught by the grep because the fiends "
      .. "are rescaled in a file the map flags also live in; it changes how "
      .. "hard a fight is and never whether a tile can be reached.",
  },
  {
    ffr = "BossScaleStatsHigh",
    status = "noise",
    why = "an enemy stat scaling bound, passed to ScaleSingleEnemyStats at "
      .. "TempleOfFiends.cs:251. Difficulty, not reachability.",
  },
  {
    ffr = "BossScaleStatsLow",
    status = "noise",
    why = "an enemy stat scaling bound, passed to ScaleSingleEnemyStats at "
      .. "TempleOfFiends.cs:251. Difficulty, not reachability.",
  },
  {
    ffr = "SeparateBossHPScaling",
    status = "noise",
    why = "selects whether boss HP scales on its own curve "
      .. "(TempleOfFiends.cs:252). Difficulty, not reachability.",
  },
  {
    ffr = "EvadeCap",
    status = "noise",
    why = "an evade ceiling handed to ScaleSingleEnemyStats via "
      .. "GetEvadeIntFromFlag (TempleOfFiends.cs:252). Difficulty, not "
      .. "reachability.",
  },
  {
    ffr = "IncludeMorale",
    status = "noise",
    why = "whether morale is scaled along with the other stats "
      .. "(TempleOfFiends.cs:251). Difficulty, not reachability.",
  },
  {
    ffr = "ChaosFloorEncounters",
    status = "noise",
    why = "puts random encounters on the Chaos floor (TempleOfFiends.cs:60, "
      .. ":65, :112). It adds fights to a floor the party is already "
      .. "standing on and moves no teleport, chest or gate.",
  },
  {
    ffr = "Entrances",
    status = "unmodellable",
    why = "the entrance shuffle. It rewrites which overworld door reaches "
      .. "which dungeon (MetroidVaniaMap.cs:63, :1134), so the answer is a "
      .. "permutation chosen at generation rather than a rule. No toggle can "
      .. "say it, and a toggle that tried would have to be wrong on every "
      .. "seed. The pack's answer is the entrance markers -- learned by "
      .. "observation, so reveal-on-visit cannot spoil -- which is "
      .. "docs/ROADMAP.md section 4.",
  },
  {
    ffr = "Towns",
    status = "unmodellable",
    why = "the town shuffle, the same permutation one layer in "
      .. "(MetroidVaniaMap.cs:63, :1124, :1156). Entrances' case exactly.",
  },
  {
    ffr = "Floors",
    status = "unmodellable",
    why = "the floor shuffle, which permutes staircases rather than doors "
      .. "(MetroidVaniaMap.cs:1134, :1144, :1215). Entrances' case, per "
      .. "floor. tools/entrance_graph.py already reads the whole permutation "
      .. "off a cartridge; what is missing is a way for the board to show "
      .. "it.",
  },
  {
    ffr = "EntrancesMixedWithTowns",
    status = "unmodellable",
    why = "mixes the two pools into one (MetroidVaniaMap.cs:1294). It widens "
      .. "a permutation the pack cannot express at all, so it cannot make it "
      .. "worse.",
  },
  {
    ffr = "AllowDeepCastles",
    status = "unmodellable",
    why = "lets the shuffle put Coneria Castle and the Temple of Fiends "
      .. "behind each other (MetroidVaniaMap.cs:1138, :1146). A constraint "
      .. "on a permutation the pack does not model; it only matters once "
      .. "Entrances or Floors is on.",
  },
  {
    ffr = "IncludeConeria",
    status = "unmodellable",
    why = "adds Coneria to the town pool (MetroidVaniaMap.cs:1128, :1151). "
      .. "Same shape: it widens a permutation rather than gating anything.",
  },
  {
    ffr = "NPCItems",
    status = "unjudged",
    -- The measurement ran on 2026-09-03 -- nonpcitems497 against std497 --
    -- and it moved zero access rules and seven priority locations. So what is
    -- unsettled is no longer the measurement but the build: this flag is the
    -- other conjunct of the computed IncentivizeCaravan, and the seven slots
    -- that answer to it carry only npcsAreIncentive today. It stays here rather
    -- than becoming noise or decided, because neither is true of a flag that
    -- demonstrably moves a ring; it leaves when the code lands.
    --
    -- Six of the seven want the conjunction. The seventh, the caravan slot,
    -- wants more than that: it leaves the export entirely with this flag off,
    -- so its existence answers to npcItems and not only its colour.
    measure = "done: nonpcitems497 vs std497, docs/ISSUES.md, \"Seven "
      .. "incentive slots ring gold on a seed FFR did not incentivize them "
      .. "on\". What remains is a code, not a measurement.",
    why = "decides whether the NPCs hand out shuffled items. It is read in "
      .. "two places that do different things -- NPCs.cs:236 gives Nerrick "
      .. "the Canal or a Cabin, MetroidVaniaMap.cs:871 swaps a line of "
      .. "dialogue -- and FlagsCompute.cs:64, :69 folds it into RequiredRuby "
      .. "and RequiredTnt. Whether any of that moves a pin on an Archipelago "
      .. "seed has not been measured, and inventing a reason here would be "
      .. "the padding this list exists to prevent.",
  },
  {
    ffr = "NPCSwatter",
    status = "unjudged",
    measure = "roll a 4.9.7 pair one flag apart and diff the exports",
    why = "rewrites every Talk_norm NPC to Talk_kill (NPCs.cs:134, :259-275), "
      .. "protecting only the Lute and Rod plates. That plainly changes what "
      .. "an NPC does; whether it changes what the party can end up holding, "
      .. "and so whether an NPC cell should colour differently, has not been "
      .. "measured.",
  },
  {
    ffr = "FiendsRefights",
    status = "unjudged",
    measure = "tools/tofr_diff.py on a pair, since the AP export never covers "
      .. "ToFR",
    why = "decides whether the four fiends stand in the Temple of Fiends "
      .. "Revisited and on which paths (TempleOfFiends.cs:53, :93, :100). "
      .. "This flag and its sibling are the two docs/FLAG_COVERAGE.md never "
      .. "listed at all, which is the miss this test was built for -- so "
      .. "filing them as settled on the day they were found would be the "
      .. "wrong lesson.",
  },
  {
    ffr = "ShortToFRFiendsRefights",
    status = "unjudged",
    measure = "tools/tofr_diff.py on a pair, since the AP export never covers "
      .. "ToFR",
    why = "the same decision for a shortened ToFR, with seven arrangements "
      .. "rather than three (TempleOfFiends.cs:54, :207-332). The export "
      .. "cannot grade either one: archipelago/Archipelago.cs:93 drops every "
      .. "ToFR location from the pool, so this wants the derived walk or "
      .. "tofr_diff.py, not a graded cartridge.",
  },
  {
    ffr = "LefeinSuperStore",
    status = "unjudged",
    measure = "walk Lefein on a No-Overworld pair one flag apart -- the town "
      .. "layout is in the decompressed map, so this is a diff of two "
      .. "cartridges rather than a graded export",
    why = "not only a shop. Its one use is ApplyMapMods "
      .. "(MetroidVaniaMap.cs:58), which is called only from NoOverworld() "
      .. "(:47-58), and at :260 it chooses between two different sets of "
      .. "tile writes to MapIndex.Lefein -- on, lefeinNorthedge2 at "
      .. "(0x24,0x02), lefeinSouthedge2 at (0x00,0x01), a blob named "
      .. "lefeinNonteleport at (0x00,0x02) and 0x0E at [0x01,0x33] and "
      .. "[0x01,0x3F]; off, lefeinNorthedge at (0x26,0x02), lefeinNorthedge2 "
      .. "at (0x3C,0x02), lefeinSouthedge2 at (0x00,0x02) and 0x0E at "
      .. "[0x01,0x39]. Walls and a teleport tile, in a town the "
      .. "hand-authored 75-link No-Overworld topology was derived from with "
      .. "the flag off. Held as noise until 2026-09-01 on the strength of "
      .. "the word 'store' in the name, which is the reading the call site "
      .. "does not support. Whether the walk still holds with it on is the "
      .. "open question; the 4.9.2-to-4.9.8 diff moving the whole "
      .. "No-Overworld surface by exactly this line is a reason to measure "
      .. "it rather than a reason to pass over it.",
  },
}

-- Progressive items, where the stage is a count of settings rather than one
-- boolean. Stage 0 is off; PopTracker's Lua-visible CurrentStage sits one above
-- the stages[] index whenever allow_disabled holds, which it does here.
--
-- Every source flag here is a tri-state, so each can come back "the generator
-- rolled it" the way a toggle can, and each has to be left alone rather than
-- read as off when it does. `stage` takes a reader rather than the flag table
-- for that: `get(name)` gives the value, or nil for one that was rolled, and a
-- nil that decides the stage is returned as `nil, "<the flag to report>"`. A
-- rolled flag the stage does not depend on is not an unknown -- Extended is
-- only asked once Open Progression says yes -- so the questions are asked in
-- order rather than all at once.
--
-- Reading a rolled flag as off is what this file did until 2026-08-31, which
-- meant a seed with AirBoat left on random silently cleared a cell the player
-- had set by hand, and said nothing in the "left as they were" line.
local PROGRESSIVES = {
  {
    code = "progressionFlag",
    default = 1,
    -- Extended Open Progression is only offered when Open Progression is on,
    -- and stage 2 inherits stage 1's codes, so extendedOpen implies
    -- openProgression the way the rules already assume.
    stage = function(get)
      local open = get("MapOpenProgression")
      if open == nil then return nil, "MapOpenProgression" end
      if open ~= true then return 0 end
      local extended = get("MapOpenProgressionExtended")
      if extended == nil then return nil, "MapOpenProgressionExtended" end
      return extended == true and 2 or 1
    end,
  },
  {
    code = "shortToFR",
    -- ToFRMode is Long/Mid/Short/Random = 0..3, an enum rather than a
    -- tri-state, so it decodes to a number and cannot go through TOGGLES:
    -- setToggle would write 2 into Active, and check_logic's flag_codes tests
    -- `is True`, which an integer fails.
    --
    -- Only Short moves a rule. MidToFR rewrites the lock door at [0x16,0x14]
    -- and still calls AddLutePlateToFloor1F, so Mid asks for exactly what Long
    -- asks for and reads as 0 here. Short is the one that repoints the Black
    -- Orb warp at Chaos and lays the seven chests in front of the landing tile,
    -- with the lute gate two tiles past it.
    --
    -- Random is rolled at generation -- FF1Lib picks the mode with rng and the
    -- flag string still records "Random" -- so the cartridge cannot say where
    -- it landed, and strict is the only honest answer. An absent flag reads
    -- false from get(), which is not 2, so that lands strict too.
    stage = function(get)
      local mode = get("ToFRMode")
      if mode == nil then return nil, "ToFRMode" end
      return mode == 2 and 1 or 0
    end,
  },
  {
    code = "airBoat",
    stage = function(get)
      local airBoat = get("AirBoat")
      if airBoat == nil then return nil, "AirBoat" end
      return airBoat == true and 1 or 0
    end,
  },
  {
    code = "cardiaIsIncentive",
    -- Stage 2 is Bahamut's Hoard, which is a map edit rather than an incentive
    -- category, so it comes from a different flag than stage 1. Stage 2
    -- inherits stage 1's code, so a hoard seed also reads as Cardia-incentive;
    -- that only affects which pins are drawn, never what is reachable.
    --
    -- The Hoard is asked first and a rolled one is unknown either way: it wins
    -- outright when it is on, so no value of IncentivizeCardia settles the
    -- stage without it.
    stage = function(get)
      local hoard = get("MapDragonsHoard")
      if hoard == nil then return nil, "MapDragonsHoard" end
      if hoard == true then return 2 end
      local cardia = get("IncentivizeCardia")
      if cardia == nil then return nil, "IncentivizeCardia" end
      return cardia == true and 1 or 0
    end,
  },
}

-- Shard hunt: how many shards the black orb wants.
--
-- Six fixed counts and three ranges. A range is rolled at generation the way a
-- tri-state is -- the string records that it was rolled, not where it landed --
-- so those join the same "left as they were" list the toggles use.
--
-- Shards Required counts from sixteen, one stage per shard, and is not an
-- allow_disabled progressive, so its stage is the stages[] index rather than
-- one above it: stage 8 is the 24 the board starts every shard-hunt variant on.
-- That sixteen is the same one hasEnoughShards adds back in scripts/logic.lua.
local SHARD_COUNTS = { [0] = 16, [1] = 20, [2] = 24, [3] = 28, [4] = 32, [5] = 36 }
local SHARD_DEFAULT = 24

-- A setting by FFR's name, falling back to `default` when no seed has been read
-- or the flag was rolled at generation. Logic that depends on a setting with no
-- item on the board goes through here.
function ffrFlag(name, default)
  if not FFR_FLAGS then return default end
  local value = FFR_FLAGS[name]
  if value == nil then return default end
  return value
end

local function setToggle(code, value)
  local item = Tracker:FindObjectForCode(code)
  if not item then
    print("flags: no item for " .. code)
    return false
  end
  item.Active = value
  return true
end

local function setStage(code, stage)
  local item = Tracker:FindObjectForCode(code)
  if not item then
    print("flags: no item for " .. code)
    return false
  end
  -- Order matters: a progressive that is Active = false resets to stage 0, so
  -- clearing first and then setting the stage would land on the wrong one.
  if stage == 0 then
    item.Active = false
  else
    item.Active = true
    item.CurrentStage = stage
  end
  return true
end

-- Written straight rather than through setStage: Shards Required has no
-- disabled state, so the Active dance that setStage does for stage 0 would
-- land count sixteen on the wrong stage.
local function setShardsRequired(count)
  local item = Tracker:FindObjectForCode("shardsRequired")
  if not item then
    print("flags: no item for shardsRequired")
    return false
  end
  item.CurrentStage = count - 16
  return true
end

-- Put the flag grid back where the board starts.
--
-- scripts/init.lua calls this to set the defaults in the first place, so this
-- file is the only place they are written down.
--
-- The other caller is applyFFRFlags, on a cartridge whose settings could not be
-- read at all. The grid outlives a cartridge swap -- resetForNewGame clears
-- what the RAM feed owns and deliberately not this -- so without a reset the
-- previous seed's answers go on being asserted about a seed that never had
-- them, with only the unread light to say otherwise. That is the same hole the
-- absent-flag branch below closes for a version swap, in the case where there
-- is nothing to decode at all.
--
-- It costs the player's own clicks, which is the right trade only because it
-- happens once per record rather than once per scan: every caller records
-- FFR_FLAGS_SOURCE, so the next scan of the same unreadable cartridge changes
-- nothing and a grid set by hand afterwards stands.
function resetFlagsToDefaults()
  for _, entry in ipairs(TOGGLES) do
    setToggle(entry.code, entry.default == true)
  end
  for _, entry in ipairs(PROGRESSIVES) do
    setStage(entry.code, entry.default or 0)
  end
  -- Only the shard-hunt variants have a count to start: on the others the goal
  -- never reads it and the board does not show it.
  if Tracker.ActiveVariantUID:find("shardHunt") then
    setShardsRequired(SHARD_DEFAULT)
  end
  -- And the decoded set with them, or logic reading a setting with no cell on
  -- the board would still be answering out of the last cartridge.
  FFR_FLAGS = nil
end

-- Only on a shard hunt. Every seed carries a ShardCount, orb goals included,
-- so applying it unconditionally would move a number the player can see for a
-- goal that never reads it.
local function applyShardCount(flags, random)
  if flags.ShardHunt ~= true then
    return 0
  end
  local count = SHARD_COUNTS[flags.ShardCount]
  if not count then
    random[#random + 1] = "ShardCount"
    return 0
  end
  return setShardsRequired(count) and 1 or 0
end

-- The flag names one FFR build actually has, cached per version.
--
-- A decoded table says nil for two different things and they want opposite
-- treatment. A tristate the generator rolled is genuinely unknown, so the board
-- keeps whatever it had. A flag the build has never heard of is a definite off:
-- `schema_4-9-2.lua` carries neither `ShipDrydock` nor `MapSardasForest`,
-- because 4.9.2 has neither flag, and a build with no drydock cannot have
-- drydocked the ship.
--
-- Both loops make the distinction, toggles and progressives alike. The
-- progressives are the half that was missed: their five source flags are all
-- tristates too, and reading a rolled one as off cleared a cell the player had
-- set by hand.
--
-- Telling them apart matters because the toggles survive a cartridge swap --
-- `resetForNewGame` clears what the RAM feed owns, not the flag grid. Treating
-- both as "rolled" left a 4.9.7 drydock seed's `shipDrydock` set when the next
-- cartridge was a 4.9.2 one, and with it every alternative in the trees that
-- names the Ship, for the rest of the session.
local SCHEMA_NAMES = {}
local function schemaNames(version)
  if version == nil or FFR_FLAG_SCHEMAS == nil then return nil end
  local cached = SCHEMA_NAMES[version]
  if cached then return cached end
  local schema = FFR_FLAG_SCHEMAS[version]
  if not schema then return nil end
  local names = {}
  for _, entry in ipairs(schema.properties or {}) do names[entry.name] = true end
  SCHEMA_NAMES[version] = names
  return names
end

-- Push a decoded set onto the flag grid. Returns how many settings were applied.
--
-- `version` is the FFR release the string was decoded against. Omitting it is
-- for a hand-built table with no schema behind it, and costs the absent-flag
-- distinction above -- every nil then reads as rolled.
function applyFFRFlagsToBoard(flags, version)
  local applied, random, absent = 0, {}, {}
  local names = schemaNames(version)

  -- One flag, with the two kinds of nil told apart:
  --   value, nil       the string says so
  --   false, "absent"  this build has no such flag, so it cannot be on
  --   nil,   "rolled"  the generator rolled it and the string does not say
  local function readFlag(name)
    local value = flags[name]
    if value ~= nil then return value end
    if names ~= nil and not names[name] then return false, "absent" end
    return nil, "rolled"
  end

  for _, entry in ipairs(TOGGLES) do
    local value, why = readFlag(entry.ffr)
    if why == "rolled" then
      random[#random + 1] = entry.ffr
    else
      if why == "absent" then absent[#absent + 1] = entry.ffr end
      -- An absent flag is switched off, but it is not a setting this build has,
      -- so it is not counted as one applied -- the `absent` line below is what
      -- reports it, and counting it there as well made the two disagree.
      if setToggle(entry.code, value) and why == nil then applied = applied + 1 end
    end
  end

  -- The reader the stage functions take. Same three-way answer, minus the
  -- toggles' bookkeeping: an absent source flag reads as off, and is reported
  -- on the same line the toggles use. No shipped schema is missing one of these
  -- five -- 4.9.2 and 4.9.7 both carry all of them -- so that branch is here to
  -- keep a future schema from reopening what the absent-flag branch just shut,
  -- not because it fires today.
  local function get(name)
    local value, why = readFlag(name)
    if why == "absent" then absent[#absent + 1] = name end
    return value
  end
  for _, entry in ipairs(PROGRESSIVES) do
    local stage, rolled = entry.stage(get)
    if stage == nil then
      random[#random + 1] = rolled
    elseif setStage(entry.code, stage) then
      applied = applied + 1
    end
  end

  applied = applied + applyShardCount(flags, random)

  if #random > 0 then
    table.sort(random)
    print("flags: rolled at generation, left as they were -- " .. table.concat(random, ", "))
  end
  if #absent > 0 then
    table.sort(absent)
    print("flags: not settings in FFR " .. tostring(version) .. ", so switched off -- "
          .. table.concat(absent, ", "))
  end
  return applied
end

-- The whole job: "<version>|<flagstring>" in, configured board out.
--
-- Re-applied only when the string changes, so a deliberate click is not undone
-- ten times a second. A new cartridge changes it; a reset does not.
function applyFFRFlags(record)
  -- No such variable at all: an Archipelago-only session, where nothing is
  -- publishing ff1/flags and there is no cartridge to have failed to read. The
  -- grid is showing init.lua's defaults, which is what an AP player is meant to
  -- start from, so the light stays off.
  if type(record) ~= "string" then
    return false
  end
  if record == FFR_FLAGS_SOURCE then
    return false
  end
  -- "" is different: the bridge is attached and told us it got nothing out of
  -- the cartridge -- not an FFR ROM, a PRG it could not read, or a build with no
  -- FFRInfo record (readFlags in bridge/ffr_uat_bridge.lua). That is the
  -- commonest way the grid ends up asserting settings this seed never had, so
  -- it is what both the light and the reset are for: the previous cartridge's
  -- answers go, and what is left is a board that says it does not know.
  -- Recorded as the source so that is done once, not on every scan.
  if record == "" then
    FFR_FLAGS_SOURCE = record
    print("flags: this cartridge carries no flag record -- the flag grid is "
          .. "back to defaults, set it by hand")
    resetFlagsToDefaults()
    if setFlagsUnread then
      setFlagsUnread("this cartridge carries no flag record")
    end
    -- No flag record says nothing about the mode either, so the light from the
    -- last cartridge has to go out rather than stand. checkRom returns early
    -- when the emulator reports no rom at all, so the swap cleanup there cannot
    -- be relied on to have cleared it.
    if setModeMismatch then setModeMismatch(nil) end
    return false
  end

  local version, flagstring = record:match("^([^|]+)|(.+)$")
  if not version then
    print("flags: cannot read " .. string.format("%q", record)
          .. " -- the flag grid is back to defaults")
    resetFlagsToDefaults()
    if setFlagsUnread then setFlagsUnread("the cartridge's flag record is malformed") end
    -- Same as above: a record we cannot split names no mode.
    if setModeMismatch then setModeMismatch(nil) end
    FFR_FLAGS_SOURCE = record   -- said once, and reset once, not every scan
    return false
  end

  local flags, err = decodeFFRFlags(version, flagstring)
  if not flags then
    print("flags: " .. err .. " -- the flag grid is back to defaults")
    resetFlagsToDefaults()
    -- Say it on the board too. Defaults are a guess, and a player who missed
    -- this line has no way to tell them from the seed's own settings.
    if setFlagsUnread then setFlagsUnread(err) end
    -- An unread flag string says nothing about the mode either, so the light
    -- from the last cartridge has to go out rather than stand.
    if setModeMismatch then setModeMismatch(nil) end
    FFR_FLAGS_SOURCE = record   -- do not retry the same bad string every scan
    return false
  end

  FFR_FLAGS = flags
  FFR_FLAGS_SOURCE = record
  if setFlagsUnread then setFlagsUnread(nil) end

  -- Which game this seed is, against which game the loaded variant tracks.
  --
  -- Both halves are chosen by variant and neither can be corrected downstream:
  -- scripts/logic.lua reads Tracker.ActiveVariantUID for the overworld shape
  -- and again for the goal, so a No-Overworld seed on a standard variant
  -- colours every pin with the wrong geography, and a shard-hunt seed on a
  -- standard variant is gated on four lit orbs instead of the shard count.
  --
  -- Nor can the pack switch variants for the player. That is settled rather
  -- than assumed: Tracker.ActiveVariantUID is read-only from Lua and says so
  -- (PopTracker core/tracker.cpp:747-749), and Pack::setVariant is called once
  -- while the pack loads (poptracker.cpp:1202). There is no runtime path.
  --
  -- So both go to the board as well as to the console. Collected rather than
  -- chained, because a seed can be wrong on both counts at once and reporting
  -- only the first hides the second.
  local uid = Tracker.ActiveVariantUID
  local variantIsNoOverworld = uid:find("NOverworld") ~= nil
  local variantIsShardHunt = uid:find("shardHunt") ~= nil
  local wrong = {}

  -- GameMode 2 is No-Overworld and 1 is Deep Dungeon (Enums.cs:396-404). The
  -- line this replaced warned on any non-zero mode, which fired on every
  -- No-Overworld seed loaded into the No-Overworld variant it belongs in.
  if flags.GameMode == 1 then
    wrong[#wrong + 1] = "this seed is Deep Dungeon, which this pack does not track"
  elseif flags.GameMode ~= 0 and flags.GameMode ~= 2 then
    wrong[#wrong + 1] = "this seed is GameMode " .. tostring(flags.GameMode)
                        .. ", which this pack does not track"
  elseif (flags.GameMode == 2) ~= variantIsNoOverworld then
    wrong[#wrong + 1] = flags.GameMode == 2
      and "this seed is No-Overworld and this variant is not, so the overworld "
          .. "rules do not describe it"
      or "this variant is No-Overworld and this seed is not, so its rules do "
         .. "not describe the seed"
  end

  if (flags.ShardHunt == true) ~= variantIsShardHunt then
    wrong[#wrong + 1] = flags.ShardHunt == true
      and "this seed is a shard hunt and the goal on this variant is gated on "
          .. "the four orbs"
      or "this variant is a shard hunt, so its goal is gated on the shard "
         .. "count, which an orb seed never fills"
  end

  local mismatch = #wrong > 0 and table.concat(wrong, "; ") or nil
  if mismatch then
    print("flags: " .. mismatch .. " -- load the matching pack variant")
  end
  if setModeMismatch then setModeMismatch(mismatch) end
  if flags.OwMapExchange ~= 0 then
    print("flags: this seed has a non-vanilla overworld (OwMapExchange "
          .. tostring(flags.OwMapExchange) .. ") -- map logic does not model it")
  end

  local applied = applyFFRFlagsToBoard(flags, version)
  print(string.format("flags: FFR %s seed, %d settings applied from the cartridge",
                      version, applied))
  return true
end


-- What this file claims about FFR's flags, for the tests and for check_logic.
-- Exported rather than kept local because a coverage list that cannot be read
-- back is a list that drifts.
FFR_FLAG_COVERAGE = {
  toggles = TOGGLES,
  progressives = PROGRESSIVES,
  notModelled = NOT_MODELLED,
}
