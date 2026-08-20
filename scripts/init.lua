--  Load configuration options up front
ScriptHost:LoadScript("scripts/settings.lua")
print("Starting up scipts")

-- Add Items
Tracker:AddItems("items/items.json")
Tracker:AddItems("items/hosted_items.json")
Tracker:AddItems("items/flags.json")
Tracker:AddItems("items/shards.json")

-- NOverworld replaces the overworld art only. It still needs the 53 dungeon
-- maps, or the per-chest markers in locations/overworld.json have nowhere to
-- draw; NOverworldMaps.json is loaded second so its "incentives" entry wins.
if Tracker.ActiveVariantUID == "7NOverworld" or Tracker.ActiveVariantUID == "8shardHuntNOverworld" then
  Tracker:AddMaps("maps/maps.json")
  Tracker:AddMaps("maps/NOverworldMaps.json")
else
  Tracker:AddMaps("maps/maps.json")
end

ScriptHost:LoadScript("scripts/logic.lua")

-- locations/NOverworld/locations.json was loaded here and has never existed --
-- not in the tree and not in any commit -- so both NOverworld variants loaded
-- no dungeon locations at all and nothing could clear. The dungeon tree is the
-- same either way; only the incentive pins differ.
if Tracker.ActiveVariantUID == "7NOverworld" or Tracker.ActiveVariantUID == "8shardHuntNOverworld" then
    Tracker:AddLocations("locations/overworld.json")
    Tracker:AddLocations("locations/NOverworld/incentives.json")
else
    Tracker:AddLocations("locations/overworld.json")
    Tracker:AddLocations("locations/incentives.json")
end

Tracker:AddLayouts("layouts/shared.json")
if Tracker.ActiveVariantUID == "6shardHunt" then
  Tracker:AddLayouts("layouts/shardHunt/tracker.json")
  Tracker:AddLayouts("layouts/shardHunt/broadcast.json")
  local shardsRequired = Tracker:FindObjectForCode("shardsRequired")
  shardsRequired.CurrentStage = 8
elseif Tracker.ActiveVariantUID == "2shardHuntNoMap" then
  Tracker:AddLayouts("layouts/shardHuntNoMap/tracker.json")
  Tracker:AddLayouts("layouts/shardHuntNoMap/broadcastNoMap.json")
  local shardsRequired = Tracker:FindObjectForCode("shardsRequired")
  shardsRequired.CurrentStage = 8
elseif Tracker.ActiveVariantUID == "8shardHuntNOverworld" then
  Tracker:AddLayouts("layouts/NOverworld/shardsTracker.json")
  Tracker:AddLayouts("layouts/NOverworld/broadcastShards.json")
  local shardsRequired = Tracker:FindObjectForCode("shardsRequired")
  shardsRequired.CurrentStage = 8
elseif Tracker.ActiveVariantUID == "4shardHuntNOverworldNoMap" then
  Tracker:AddLayouts("layouts/NOverworld/shardsTrackerNoMap.json")
  Tracker:AddLayouts("layouts/NOverworld/broadcastShardsNoMap.json")
  local shardsRequired = Tracker:FindObjectForCode("shardsRequired")
  shardsRequired.CurrentStage = 8
elseif Tracker.ActiveVariantUID == "7NOverworld" then
  Tracker:AddLayouts("layouts/NOverworld/tracker.json")
  Tracker:AddLayouts("layouts/NOverworld/broadcast.json")
elseif Tracker.ActiveVariantUID == "3NOverworldNoMap" then
  Tracker:AddLayouts("layouts/NOverworld/trackerNoMap.json")
  Tracker:AddLayouts("layouts/NOverworld/broadcastNoMap.json")
elseif Tracker.ActiveVariantUID == "1standardNoMap" then
  Tracker:AddLayouts("layouts/standardNoMap/tracker.json")
  Tracker:AddLayouts("layouts/standardNoMap/broadcastNoMap.json")
else
  Tracker:AddLayouts("layouts/standard/tracker.json")
  Tracker:AddLayouts("layouts/standard/standard_broadcast.json")
end

-- Default Flags
local progressionFlag = Tracker:FindObjectForCode("progressionFlag")
progressionFlag.CurrentStage = 1
local npcsIncentive = Tracker:FindObjectForCode("npcsAreIncentive")
npcsIncentive.Active = true
local fetchQuestsIncentive = Tracker:FindObjectForCode("fetchQuestsAreIncentive")
fetchQuestsIncentive.Active = true
local iceIncentive = Tracker:FindObjectForCode("iceCaveIsIncentive")
iceIncentive.Active = true
local ordealsIncentive = Tracker:FindObjectForCode("ordealsIsIncentive")
ordealsIncentive.Active = true
local marshIncentive = Tracker:FindObjectForCode("marshIsIncentive")
marshIncentive.Active = true
local earthIncentive = Tracker:FindObjectForCode("earthIsIncentive")
earthIncentive.Active = true
local seaIncentive = Tracker:FindObjectForCode("seaIsIncentive")
seaIncentive.Active = true
local skyIncentive = Tracker:FindObjectForCode("skyIsIncentive")
skyIncentive.Active = true
local coneriaLockedIncentive = Tracker:FindObjectForCode("coneriaLockedIsIncentive")
coneriaLockedIncentive.Active = true
local earlyKing = Tracker:FindObjectForCode("earlyKing")
earlyKing.Active = true
local earlySarda = Tracker:FindObjectForCode("earlySarda")
earlySarda.Active = true
local earlySage = Tracker:FindObjectForCode("earlySage")
earlySage.Active = true
local earlyOrdeals = Tracker:FindObjectForCode("earlyOrdeals")
earlyOrdeals.Active = true
-- The map tab follows the player by default; click it off when you would
-- rather stay on the floor you are reading.
local tabSwitch = Tracker:FindObjectForCode("tab_switch")
tabSwitch.Active = true

-- AutoTracking for Poptracker
if PopVersion and PopVersion>="0.18.0" then
  ScriptHost:LoadScript("scripts/autotracking.lua")
  -- Local emulator feed over UAT. AddVariableWatch is always registered, so
  -- this is a version check, not a check for the "uat" manifest flag.
  if ScriptHost.AddVariableWatch then
    ScriptHost:LoadScript("scripts/autotracking/uat.lua")
  end
end
