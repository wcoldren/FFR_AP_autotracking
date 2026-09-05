--  Load configuration options up front
ScriptHost:LoadScript("scripts/settings.lua")
print("Starting up scipts")

-- Add Items
Tracker:AddItems("items/items.json")
Tracker:AddItems("items/hosted_items.json")
Tracker:AddItems("items/flags.json")
Tracker:AddItems("items/shards.json")
-- The two rolls the bridge reads off the cartridge. Not flags: nothing in
-- items/rolls.json is a setting anyone chose, and no layout draws them. They
-- exist because a rule can only be re-evaluated by an item changing.
Tracker:AddItems("items/rolls.json")

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

-- The two map-tab controls, and the pin control, are declared in
-- items/flags.json and are not set here. Nothing below is a default.
--
-- Active is a rendering fix, not a preference. A progressive with
-- allow_disabled false starts at stage1 0 -- FromJSON raises it only for a
-- composite toggle and honours initial_active_state only for the toggle family
-- (PopTracker core/jsonitem.cpp:95-121), and _changeStateImpl moves stage2 and
-- never stage1 for this type (:214-237). Item::setStage indexes
-- _surfs[stage1][stage2], so stage1 0 is the disabled row, and with settings.json
-- filtering that row grayscale and dim the icon is drawn greyed at every stage
-- for ever. Lua_NewIndex forces the value true when allow_disabled is false
-- (:459-460), so this cannot carry an opinion about which stage is showing.
--
-- What used to be here was `tabMode.CurrentStage = 0`, which was a no-op --
-- with allow_disabled false the guard reads `_stage2 ~= 0 or _stage1 ~= _stage1`
-- and never fires -- and which asserted stage 0 into the reset snapshot
-- PopTracker takes one line after this script runs. See docs/ISSUES.md, "A
-- pinned control cannot survive Reset", for what that costs and why the fix is
-- upstream.
local tabMode = Tracker:FindObjectForCode("tab_mode")
tabMode.Active = true
local entrancePins = Tracker:FindObjectForCode("entrance_pins")
entrancePins.Active = true

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
    --
    -- The two rolls come off the same feed and have no defaults to restore --
    -- the board already starts where "nothing has said" is -- so unlike
    -- flag_mapping this is loaded here and nowhere else.
    ScriptHost:LoadScript("scripts/autotracking/rolls_mapping.lua")
    ScriptHost:LoadScript("scripts/autotracking/uat.lua")
  end
end
