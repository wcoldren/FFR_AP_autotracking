-- Rules that access_rules cannot say on their own.
--
-- PopTracker's access_rules are a list of alternatives, each a set of codes
-- that all have to be present. There is no way to write "and not this flag",
-- and no way to count. Both come up, so they live here and are called from a
-- rule as $name.
--
-- These return 0 or 1 rather than false or true: that is what PopTracker reads
-- as an accessibility level, and 0 is truthy in Lua, so a function that fell
-- back to returning a boolean would be read as accessible either way.

-- Whether Sarda's Cave sits in the open or in trees.
--
-- FFR's "Sarda's Forest" (MapSardasForest) replaces the clearing outside the
-- cave with forest, and the airship cannot land on forest. With it off the
-- airship reaches Sarda by itself; with it on the only ways in are through the
-- Titan's tunnel, which is what the Ruby buys. FFR's own logic for a
-- forested seed says so: Sarda needs (Ruby AND Canal AND Ship) OR (Ruby AND
-- Canoe AND Floater), where an unforested one drops the Ruby from the second.
--
-- The flag is read off the cartridge when the emulator bridge is connected and
-- is a click in the flags grid otherwise; either way it is the item that is
-- asked, so both paths behave the same.
function noSardasForest()
  local flag = Tracker:FindObjectForCode("sardasForest")
  if flag and flag.Active then
    return 0
  end
  return 1
end

-- Shard hunt: the goal is a count of shards rather than four lit orbs.
--
-- The variants are named in manifest.json, and the UID carries a leading digit
-- that fixes the order they appear in PopTracker's variant list. Matching the
-- bare string "shardHunt" matched none of them, so every shard-hunt seed was
-- quietly gated on orbs instead and hasEnoughShards never ran.
local function isShardHunt()
  return Tracker.ActiveVariantUID:find("shardHunt") ~= nil
end

function hasEnoughShards()
  local shards = Tracker:FindObjectForCode("shards")
  local required = Tracker:FindObjectForCode("shardsRequired")
  -- The Shards Required item starts counting at sixteen; its stage is the
  -- number above that.
  if shards.CurrentStage >= required.CurrentStage + 16 then
    return 1
  end
  return 0
end

local ORBS = { "earthorb", "fireorb", "waterorb", "airorb" }

local function orbsLit()
  local n = 0
  for _, code in ipairs(ORBS) do
    local orb = Tracker:FindObjectForCode(code)
    if orb and orb.CurrentStage > 0 then
      n = n + 1
    end
  end
  return n
end

-- How many orbs the black orb wants. FFR can ask for fewer than four, either
-- "any N of them" or N particular ones.
--
-- Only the count is in the flag string. Which orbs, in the specific mode, is
-- rolled from the seed and written into the game rather than into the flags,
-- so there is nothing here to read -- and "any three" would then be a rule
-- that turns the goal green while the wrong three are lit. All four is the
-- answer that is always sufficient, so that is what the specific mode gets;
-- the game tells you which three it wants when you get there.
local function orbsRequired()
  local count = ffrFlag and ffrFlag("OrbsRequiredCount", 4) or 4
  local mode = ffrFlag and ffrFlag("OrbsRequiredMode", 0) or 0
  if type(count) ~= "number" or count < 1 or count > 4 then
    return 4
  end
  if mode ~= 0 then
    return 4
  end
  return count
end

function canBreakOrb()
  if isShardHunt() then
    return hasEnoughShards()
  end
  if orbsLit() >= orbsRequired() then
    return 1
  end
  return 0
end
