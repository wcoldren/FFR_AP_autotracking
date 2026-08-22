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
  { ffr = "EarlyKing",               code = "earlyKing" },
  { ffr = "EarlySarda",              code = "earlySarda" },
  { ffr = "EarlySage",               code = "earlySage" },
  { ffr = "EarlyOrdeals",            code = "earlyOrdeals" },
  { ffr = "IncentivizeFreeNPCs",     code = "npcsAreIncentive" },
  { ffr = "IncentivizeFetchNPCs",    code = "fetchQuestsAreIncentive" },
  { ffr = "IncentivizeIceCave",      code = "iceCaveIsIncentive" },
  { ffr = "IncentivizeOrdeals",      code = "ordealsIsIncentive" },
  { ffr = "IncentivizeMarsh",        code = "marshIsIncentive" },
  { ffr = "IncentivizeMarshKeyLocked", code = "marshLockedIsIncentive" },
  { ffr = "IncentivizeTitansTrove",  code = "titansTroveIsIncentive" },
  { ffr = "IncentivizeEarth",        code = "earthIsIncentive" },
  { ffr = "IncentivizeVolcano",      code = "volcanoIsIncentive" },
  { ffr = "IncentivizeSkyPalace",    code = "skyIsIncentive" },
  { ffr = "IncentivizeSeaShrine",    code = "seaIsIncentive" },
  { ffr = "IncentivizeConeria",      code = "coneriaLockedIsIncentive" },
}

-- Progressive items, where the stage is a count of settings rather than one
-- boolean. Stage 0 is off; PopTracker's Lua-visible CurrentStage sits one above
-- the stages[] index whenever allow_disabled holds, which it does here.
local PROGRESSIVES = {
  {
    code = "progressionFlag",
    -- Extended Open Progression is only offered when Open Progression is on,
    -- and stage 2 inherits stage 1's codes, so extendedOpen implies
    -- openProgression the way the rules already assume.
    stage = function(flags)
      if flags.MapOpenProgression ~= true then return 0 end
      return flags.MapOpenProgressionExtended == true and 2 or 1
    end,
  },
  {
    code = "airBoat",
    stage = function(flags) return flags.AirBoat == true and 1 or 0 end,
  },
  {
    code = "cardiaIsIncentive",
    -- Stage 2 is Bahamut's Hoard, which is a map edit rather than an incentive
    -- category, so it comes from a different flag than stage 1. Stage 2
    -- inherits stage 1's code, so a hoard seed also reads as Cardia-incentive;
    -- that only affects which pins are drawn, never what is reachable.
    stage = function(flags)
      if flags.MapDragonsHoard == true then return 2 end
      return flags.IncentivizeCardia == true and 1 or 0
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
-- one above it: stage 8 is the 24 that init.lua starts every shard-hunt
-- variant on. That sixteen is the same one hasEnoughShards adds back in
-- scripts/logic.lua.
local SHARD_COUNTS = { [0] = 16, [1] = 20, [2] = 24, [3] = 28, [4] = 32, [5] = 36 }

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

-- Push a decoded set onto the flag grid. Returns how many settings were applied.
function applyFFRFlagsToBoard(flags)
  local applied, random = 0, {}

  for _, entry in ipairs(TOGGLES) do
    local value = flags[entry.ffr]
    if value == nil then
      random[#random + 1] = entry.ffr
    elseif setToggle(entry.code, value) then
      applied = applied + 1
    end
  end

  for _, entry in ipairs(PROGRESSIVES) do
    if setStage(entry.code, entry.stage(flags)) then
      applied = applied + 1
    end
  end

  applied = applied + applyShardCount(flags, random)

  if #random > 0 then
    table.sort(random)
    print("flags: rolled at generation, left as they were -- " .. table.concat(random, ", "))
  end
  return applied
end

-- The whole job: "<version>|<flagstring>" in, configured board out.
--
-- Re-applied only when the string changes, so a deliberate click is not undone
-- ten times a second. A new cartridge changes it; a reset does not.
function applyFFRFlags(record)
  if type(record) ~= "string" or record == "" then
    return false
  end
  if record == FFR_FLAGS_SOURCE then
    return false
  end

  local version, flagstring = record:match("^([^|]+)|(.+)$")
  if not version then
    print("flags: cannot read " .. string.format("%q", record))
    return false
  end

  local flags, err = decodeFFRFlags(version, flagstring)
  if not flags then
    print("flags: " .. err .. " -- leaving the flag grid alone")
    FFR_FLAGS_SOURCE = record   -- do not retry the same bad string every scan
    return false
  end

  FFR_FLAGS = flags
  FFR_FLAGS_SOURCE = record

  if flags.GameMode ~= 0 then
    print("flags: this seed is not a standard game (GameMode " .. tostring(flags.GameMode)
          .. ") -- load the matching pack variant")
  end
  -- The goal rule is chosen by variant, not by flag: scripts/logic.lua reads
  -- Tracker.ActiveVariantUID, so a shard-hunt seed tracked on a standard
  -- variant is gated on four lit orbs and never on the shard count. Nothing
  -- downstream can correct that, so say so where the rest of the flag report
  -- goes.
  local variantIsShardHunt = Tracker.ActiveVariantUID:find("shardHunt") ~= nil
  if flags.ShardHunt == true and not variantIsShardHunt then
    print("flags: this seed is a shard hunt -- load a Shard Hunt pack variant, "
          .. "the goal on this one is gated on the four orbs")
  elseif flags.ShardHunt ~= true and variantIsShardHunt then
    print("flags: this seed is not a shard hunt -- load a non-Shard-Hunt pack "
          .. "variant, the goal on this one is gated on the shard count")
  end
  if flags.OwMapExchange ~= 0 then
    print("flags: this seed has a non-vanilla overworld (OwMapExchange "
          .. tostring(flags.OwMapExchange) .. ") -- map logic does not model it")
  end

  local applied = applyFFRFlagsToBoard(flags)
  print(string.format("flags: FFR %s seed, %d settings applied from the cartridge",
                      version, applied))
  return true
end
