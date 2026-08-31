--  Load configuration options up front
ScriptHost:LoadScript("scripts/settings.lua")
print("Starting up scipts")

-- Add Items
Tracker:AddItems("items/items.json")
Tracker:AddItems("items/hosted_items.json")
Tracker:AddItems("items/flags.json")
Tracker:AddItems("items/shards.json")

-- NOverworld needs the 53 dungeon maps too, or its per-chest markers have
-- nowhere to draw; NOverworldMaps.json is loaded second so its entries win.
-- In the shipped pack that is one row, the overworld art. Once regen_maps.py
-- has drawn a No-Overworld cartridge it is every dungeon map as well, which is
-- what keeps that seed's extra staircases off a standard tracker.
if Tracker.ActiveVariantUID == "7NOverworld" or Tracker.ActiveVariantUID == "8shardHuntNOverworld" then
  Tracker:AddMaps("maps/maps.json")
  Tracker:AddMaps("maps/NOverworldMaps.json")
else
  Tracker:AddMaps("maps/maps.json")
end

ScriptHost:LoadScript("scripts/logic.lua")

-- locations/NOverworld/locations.json was loaded here and has never existed --
-- not in the tree and not in any commit -- so both NOverworld variants loaded
-- no dungeon locations at all and nothing could clear. AddLocations on a
-- missing file says nothing, which is how that survived; the slot is filled
-- properly now.
--
-- The two trees hold the same locations and differ only in where the dungeon
-- markers sit. They have to be separate files because the art is: a
-- No-Overworld cartridge and a standard one disagree about 34 to 39 of the 61
-- maps, so tools/regen_maps.py renders and crops a set for each, and a crop
-- box that differs is a pixel coordinate that differs. Without the split the
-- No-Overworld variants would draw standard markers on No-Overworld art.
if Tracker.ActiveVariantUID == "7NOverworld" or Tracker.ActiveVariantUID == "8shardHuntNOverworld" then
    Tracker:AddLocations("locations/NOverworld/overworld.json")
    Tracker:AddLocations("locations/NOverworld/incentives.json")
else
    Tracker:AddLocations("locations/overworld.json")
    Tracker:AddLocations("locations/incentives.json")
end

-- After the locations, because it addresses their sections by path.
ScriptHost:LoadScript("scripts/incentive_slots.lua")
ScriptHost:LoadScript("scripts/incentives.lua")

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

-- Default Flags.
--
-- The values are the `default` fields on the tables in
-- scripts/autotracking/flag_mapping.lua rather than a second copy here,
-- because the same set has to be *restorable*: a cartridge whose settings
-- cannot be read has to put the grid back, or it goes on showing the previous
-- seed's answers. Two lists would drift, and the one that drifted would be the
-- one nobody looks at.
--
-- Loaded here rather than with the autotracking scripts below for that reason
-- -- these defaults are the board's, not the feed's, and a host too old for
-- autotracking still needs them. It defines functions and touches nothing at
-- load time.
ScriptHost:LoadScript("scripts/autotracking/flag_mapping.lua")
resetFlagsToDefaults()

-- The map tab follows the player by default; click it off when you would
-- rather stay on the floor you are reading.
local tabSwitch = Tracker:FindObjectForCode("tab_switch")
tabSwitch.Active = true
-- And which of the two overworld tabs it follows to. Stage 0 is Auto, which
-- reads the seed; click it round to pin the incentive map or the full one.
-- See overworldTab() in scripts/autotracking/maptab.lua.
local tabMode = Tracker:FindObjectForCode("tab_mode")
tabMode.CurrentStage = 0

-- AutoTracking for Poptracker
if PopVersion and PopVersion>="0.18.0" then
  ScriptHost:LoadScript("scripts/autotracking.lua")
  -- Local emulator feed over UAT. AddVariableWatch is always registered, so
  -- this is a version check, not a check for the "uat" manifest flag.
  if ScriptHost.AddVariableWatch then
    -- The seed's own settings, read out of the cartridge by the bridge. Loaded
    -- with the UAT feed because that is the only feed that carries them --
    -- Archipelago sends no slot data for Final Fantasy.
    ScriptHost:LoadScript("scripts/flags/schemas.lua")
    ScriptHost:LoadScript("scripts/autotracking/flags_decode.lua")
    -- flag_mapping.lua is already loaded, above, for the defaults.
    ScriptHost:LoadScript("scripts/autotracking/uat.lua")
  end
end
