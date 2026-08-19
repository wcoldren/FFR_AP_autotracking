------------------------------------------------------------------
-- Follow the player between floors: when the game says they walked into a
-- different map, bring that map's tab to the front.
--
-- The pieces for this were written long before the bridge was -- MAP_VALUE
-- has named every tab since the maps feature landed, and the switching code
-- sat commented out in autotracking.lua with a note that it was waiting on
-- AP/worlds/ff1 to report the current map. It never did. The emulator bridge
-- reports it directly instead, as ff1/map.
--
-- This watches ff1/map on its own rather than joining the ff1/mem watch. The
-- two change on completely different cadences -- a map id moves every time you
-- step through a door, the flag array only when something is collected -- and
-- sharing a callback would run the 256-byte flag decode on every doorway.
------------------------------------------------------------------

local OVERWORLD = "Overworld"

-- Only two variants lay out dungeon map tabs. The four NoMap variants have no
-- tabbed widget at all and both NOverworld ones have a single tab, so there is
-- nothing to activate and no reason to look.
local TABBED_VARIANTS = {
  ["5standard"] = true,
  ["6shardHunt"] = true,
}

local lastMapId = nil

function mapTabHasTabs()
  return TABBED_VARIANTS[Tracker.ActiveVariantUID] == true
end

-- The toggle is a convenience, so a missing one means on rather than off --
-- better to follow the player than to silently do nothing.
local function switchingEnabled()
  local obj = Tracker:FindObjectForCode("tab_switch")
  if not obj then
    return true
  end
  return obj.Active == true
end

-- mapId is a standard-map id 0..60, or -1 for the overworld. Returns true when
-- it actually moved a tab, which is what the tests assert on.
function activateMapTab(mapId)
  if mapId == nil or not mapTabHasTabs() then
    return false
  end
  -- Change detection. The bridge already only sends this on a change, but the
  -- AP path has no such guarantee and a Sync re-sends everything, so a repeat
  -- must not yank the tab out from under someone reading another floor.
  if mapId == lastMapId then
    return false
  end
  lastMapId = mapId

  if not switchingEnabled() then
    return false
  end

  local path = (mapId == -1) and OVERWORLD or (MAP_VALUE and MAP_VALUE[mapId])
  if not path then
    if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
      print(string.format("maptab: no tab for map id %s", tostring(mapId)))
    end
    return false
  end

  -- Nested tabs: "Fiend Dungeons/Earth Cave/Earth Cave B1" needs each level
  -- brought forward, outermost first.
  for name in string.gmatch(path, "([^/]+)") do
    Tracker:UiHint("ActivateTab", name)
  end
  if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
    print(string.format("maptab: map %d -> %s", mapId, path))
  end
  return true
end

-- Lets onClear and the tests put it back to a known state.
function resetMapTab()
  lastMapId = nil
end

function onFF1Map(store)
  activateMapTab(store:ReadVariable("ff1/map"))
end

if ScriptHost.AddVariableWatch then
  ScriptHost:AddVariableWatch("ff1map", { "ff1/map" }, onFF1Map)
end
