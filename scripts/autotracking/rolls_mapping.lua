-- ff1/rolls, decoded onto the board.
--
-- Two permutations FFR picks at generation and records nowhere a flag string
-- or a spoiler can carry them, so the bridge reads them off the cartridge and
-- publishes one key with two fields:
--
--   gateways=waterfall:cardiaForest,icecave:cardiaCaravan,gaia:bahamutCave
--   npcs=bahamut:melmond,elfdoc:elflandCastle,unne:bahamutCaveB2
--
-- joined by "|". Either field may be empty, and an empty field is an answer:
-- every standard cartridge has no gateways, and a read that did not recognise
-- what it found publishes nothing rather than a guess.
--
-- Why this sets item codes rather than leaving a Lua global for the rules to
-- read: PopTracker only re-evaluates a rule when an item changes. A rule that
-- called a function reading a variable would be evaluated once, against
-- whatever the variable held then, and never again when the bridge answered.
-- That is the same reason isNoOverworld() reads the variant rather than
-- ffrFlag("GameMode") -- see the comment in scripts/logic.lua.
--
-- The codes are two progressives per subject-with-a-rule plus a toggle per
-- half. Stage 0 on a progressive is PopTracker's disabled row and provides no
-- code at all, so "nothing has said" is a state the rules can be written
-- against rather than a value they have to test for -- and it is where the
-- board starts, which is what an Archipelago-only session, a UAT-less session
-- and every pre-connect board get.

-- Which landing each gateway code names, and which home each NPC code names.
-- The stage numbers are 1-based over the stages[] array in items/rolls.json,
-- with 0 left for the disabled row.
--
-- The codes below are the *handle* each of those progressives carries on every
-- one of its stages, the way items/flags.json gives every Open Progression
-- stage `progressionFlag`: a progressive has no top-level code, so a stage code
-- is the only thing Tracker:FindObjectForCode can resolve, and one that is only
-- on stage 1 would stop resolving the moment the item left stage 1.
local GATEWAY_SOURCE_STAGE = { waterfall = 1, icecave = 2, gaia = 3 }
local OBJECTIVE_HOME_STAGE = { melmond = 1, elflandCastle = 2, bahamutCaveB2 = 3 }

-- landing -> the progressive that says which source leads there. cardiaCaravan
-- is deliberately absent: the pocket it lands in holds the Caravan door and
-- nothing the pack tracks, so no rule can ask about it. It is still read, on
-- the bridge side, because a permutation that does not account for all three
-- is not one this pack will believe.
local GATEWAY_CODE = {
  cardiaForest = "cardiaForestGateway",
  bahamutCave = "bahamutCaveGateway",
}

local OBJECTIVE_CODE = {
  bahamut = "bahamutHome",
  elfdoc = "elfdocHome",
  unne = "unneHome",
}

-- The record last applied, so a scan that repeats it costs nothing. Global for
-- the same reason FFR_FLAGS_SOURCE is: uat.lua clears it on a cartridge swap,
-- and a swap to a seed rolled the same way must still re-apply rather than
-- being mistaken for no change.
FFR_ROLLS_SOURCE = FFR_ROLLS_SOURCE or nil

local function setStage(code, stage)
  local item = Tracker:FindObjectForCode(code)
  if not item then
    print("rolls: no item for " .. code)
    return false
  end
  -- Same order as flag_mapping.setStage, and for the same reason: a
  -- progressive set Active = false falls back to stage 0, so clearing after
  -- setting the stage would land on the wrong one.
  if stage == 0 then
    item.Active = false
  else
    item.Active = true
    item.CurrentStage = stage
  end
  return true
end

local function setToggle(code, value)
  local item = Tracker:FindObjectForCode(code)
  if not item then
    print("rolls: no item for " .. code)
    return false
  end
  item.Active = value
  return true
end

-- "a:b,c:d" -> { a = "b", c = "d" }, or nil if any pair is malformed.
local function pairsOf(field)
  if field == nil or field == "" then
    return nil
  end
  local out, n = {}, 0
  for part in field:gmatch("[^,]+") do
    local key, value = part:match("^(%w+):(%w+)$")
    if key == nil or out[key] ~= nil then
      return nil
    end
    out[key], n = value, n + 1
  end
  if n == 0 then
    return nil
  end
  return out
end

-- Put both halves back where the board starts: nothing has been said.
function resetRollsToDefaults()
  setToggle("gatewayRoll", false)
  for _, code in pairs(GATEWAY_CODE) do
    setStage(code, 0)
  end
  setToggle("objectiveRoll", false)
  for _, code in pairs(OBJECTIVE_CODE) do
    setStage(code, 0)
  end
end

-- The gateway field. -> how many stages were set, or nil if the field says
-- nothing usable, in which case nothing is set at all.
--
-- All or nothing on purpose. Half a permutation is worse than none: a rule
-- told the wrong source opens a check that cannot be reached, where the
-- unknown state only holds a reachable one closed.
local function applyGateways(field)
  local roll = pairsOf(field)
  if roll == nil then
    return nil
  end
  local stage = {}
  for source, landing in pairs(roll) do
    if GATEWAY_SOURCE_STAGE[source] == nil then
      return nil
    end
    local code = GATEWAY_CODE[landing]
    -- An unknown landing name is a bridge this pack does not understand.
    -- cardiaCaravan is known and has no code, which is not the same thing.
    if code == nil and landing ~= "cardiaCaravan" then
      return nil
    end
    if code ~= nil then
      if stage[code] ~= nil then
        return nil
      end
      stage[code] = GATEWAY_SOURCE_STAGE[source]
    end
  end
  -- Every landing with a code has to have been named, or a rule would be left
  -- reading the previous cartridge's answer for the one that was not.
  for _, code in pairs(GATEWAY_CODE) do
    if stage[code] == nil then
      return nil
    end
  end
  local applied = 0
  for code, value in pairs(stage) do
    if setStage(code, value) then
      applied = applied + 1
    end
  end
  setToggle("gatewayRoll", true)
  return applied
end

local function applyObjectiveNpcs(field)
  local roll = pairsOf(field)
  if roll == nil then
    return nil
  end
  local stage, seen = {}, {}
  for npc, home in pairs(roll) do
    local code = OBJECTIVE_CODE[npc]
    local where = OBJECTIVE_HOME_STAGE[home]
    if code == nil or where == nil or seen[home] then
      return nil
    end
    seen[home] = true
    stage[code] = where
  end
  for _, code in pairs(OBJECTIVE_CODE) do
    if stage[code] == nil then
      return nil
    end
  end
  local applied = 0
  for code, value in pairs(stage) do
    if setStage(code, value) then
      applied = applied + 1
    end
  end
  setToggle("objectiveRoll", true)
  return applied
end

-- The whole record. -> true when something changed on the board.
--
-- Every path resets first, so a cartridge that answers for one half and not
-- the other leaves the other half unknown rather than carrying the previous
-- cartridge's answer -- the failure the flag grid's unread light exists for,
-- one feed along.
function applyFFRRolls(record)
  -- No such variable: an Archipelago-only session, or a bridge too old to
  -- publish it. Both are "nothing has said", which is where the board already
  -- is, and neither is a change.
  if type(record) ~= "string" then
    return false
  end
  if record == FFR_ROLLS_SOURCE then
    return false
  end
  FFR_ROLLS_SOURCE = record
  resetRollsToDefaults()

  -- "" is the bridge saying it read the cartridge and recognised neither half:
  -- not an FFR image, a PRG it could not read, or a build whose tables have
  -- moved. Distinct from the variable being absent only in the log.
  if record == "" then
    print("rolls: the cartridge answered for neither permutation -- the "
      .. "gateway and objective-NPC rules stay strict")
    return true
  end

  local gateways = record:match("gateways=([^|]*)")
  local npcs = record:match("npcs=(.*)$")
  if gateways == nil or npcs == nil then
    print("rolls: ff1/rolls did not have the two fields -- ignoring it")
    return true
  end

  local said = {}
  if applyGateways(gateways) == nil then
    said[#said + 1] = "no gateway roll"
  else
    said[#said + 1] = "gateways " .. gateways
  end
  if applyObjectiveNpcs(npcs) == nil then
    said[#said + 1] = "no objective-NPC roll"
  else
    said[#said + 1] = "npcs " .. npcs
  end
  print("rolls: " .. table.concat(said, ", "))
  return true
end
