-- Configuration --------------------------------------
AUTOTRACKER_ENABLE_DEBUG_LOGGING = false
AUTOTRACKER_ENABLE_ITEM_TRACKING = true
AUTOTRACKER_ENABLE_LOCATION_TRACKING = true and not IS_ITEMS_ONLY
-------------------------------------------------------

print("")
print("Active Auto-Tracker Configuration")
print("---------------------------------------------------------------------")
print("Enable Item Tracking:    ", AUTOTRACKER_ENABLE_ITEM_TRACKING)
print("Enable Location Tracking:  ", AUTOTRACKER_ENABLE_LOCATION_TRACKING)
if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
  print("Enable Debug Logging:    ", "true")
end
print("---------------------------------------------------------------------")
print("")

CUR_INDEX = -1

ScriptHost:LoadScript("scripts/autotracking/item_mapping.lua")
ScriptHost:LoadScript("scripts/autotracking/location_mapping.lua")
ScriptHost:LoadScript("scripts/autotracking/reconcile.lua")
ScriptHost:LoadScript("scripts/autotracking/ram_mapping.lua")
ScriptHost:LoadScript("scripts/autotracking/mapValues.lua")
ScriptHost:LoadScript("scripts/autotracking/maptab.lua")
-- After maptab, because the only thing that reads it turns a map id into a
-- tab through tabPathForMap.
ScriptHost:LoadScript("scripts/location_maps.lua")

-- Re-assert the board a moment after a session connects.
--
-- PopTracker restores its own saved state after the pack's scripts have run
-- and gives a pack no signal that it did. onClear's reset runs on connect, so
-- a restore landing after it wins -- and a slot with nothing checked yet sends
-- no locations, so no feed event ever comes along to put it right. What the
-- player sees is the seed they tracked last, on a seed they have not started.
-- See reassertBoard in scripts/autotracking/reconcile.lua.
--
-- One shot per connect. The handler removes itself once it has fired, so it
-- cannot come back and argue with sections cleared by hand later on.
--
-- os.clock is CPU time, not wall time, so under a GUI that spends most of a
-- second idle this deadline arrives later than the number suggests. That is
-- the harmless direction: firing late still catches the restore, where firing
-- early would re-assert before it and change nothing. The same call is what
-- the crystal pack times its entrance highlight on.
local REASSERT_DELAY = 2.0   -- seconds of CPU time, so a generous wall margin
local REASSERT_HANDLER = "ap board reassert"
local reassertDeadline = nil

local function reassertOnce()
  if reassertDeadline and os.clock() < reassertDeadline then
    return
  end
  ScriptHost:RemoveOnFrameHandler(REASSERT_HANDLER)
  reassertDeadline = nil
  reassertBoard()
end

-- Guarded the way scripts/init.lua guards AddVariableWatch: an older host
-- without the hook keeps the pre-existing behaviour rather than erroring out.
local function armReassert()
  if not ScriptHost.AddOnFrameHandler then
    return
  end
  reassertDeadline = os.clock() + REASSERT_DELAY
  ScriptHost:AddOnFrameHandler(REASSERT_HANDLER, reassertOnce)
end

function onClear()
  if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
    print(string.format("called onClear"))
  end
  CUR_INDEX = -1
  -- onClear only fires when an Archipelago session connects, which makes it the
  -- signal ram_mapping needs: AP grants items through onItem and replays them
  -- only from here, so RAM must not clear anything AP owns while a session is
  -- live. See apOwned in scripts/autotracking/ram_mapping.lua.
  AP_ITEM_FEED_ACTIVE = true
  resetChecked()
  resetMapTab()
  -- The pool is known by now (aptracker.h fills MissingLocations before it
  -- emits onClear) and cannot change while the slot is connected, so this is
  -- the one place worth asking whether the chests are checks this seed.
  refreshOverworldTab()
  -- And the one place worth asking whether the seed has each incentive slot at
  -- all: a flag can speak for a slot the seed does not contain, and only the
  -- pool says so. The rings drawn when this file loaded were on the flags
  -- alone, and nothing else revisits them -- no incentive flag moves on
  -- connect, so no watch fires. See slotInPool in scripts/incentives.lua.
  if type(refreshIncentiveHighlights) == "function" then
    refreshIncentiveHighlights()
  end
  for _, v in pairs(ITEM_MAPPING) do
    if v[1] and v[2] then
      if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
        print(string.format("onClear: clearing item %s of type %s", v[1], v[2]))
      end
      local obj = Tracker:FindObjectForCode(v[1])
      if obj then
        if v[2] == "toggle" then
          obj.Active = false
        elseif v[2] == "progressive" then
          obj.CurrentStage = 0
          obj.Active = false
        elseif v[2] == "count" then
          obj.CurrentStage = 0
        elseif v[2] == "consumable" then
          obj.AcquiredCount = 0
        elseif AUTOTRACKER_ENABLE_DEBUG_LOGGING then
          print(string.format("onClear: unknown item type %s for code %s", v[2], v[1]))
        end
      elseif AUTOTRACKER_ENABLE_DEBUG_LOGGING then
        print(string.format("onClear: could not find object for code %s", v[1]))
      end
    end
  end
  armReassert()
  -- The replay burst starts now and is over by the next frame; the
  -- correspondence lines begin after it. See armAPLocationReplay below.
  armAPLocationReplay()
end

function onItem(index, item_id, item_name)
  if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
    print(string.format("called onItem: %s, %s, %s, %s", index, item_id, item_name, CUR_INDEX))
  end
  if index <= CUR_INDEX then return end
  CUR_INDEX = index;
  local v = ITEM_MAPPING[item_id]
  if not v then
    if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
      print(string.format("onItem: could not find item mapping for id %s", item_id))
    end
    return
  end
  if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
    print(string.format("onItem: code: %s, type %s", v[1], v[2]))
  end
  if not v[1] then
    return
  end
  local obj = Tracker:FindObjectForCode(v[1])
  if obj then
    -- Debug-gated like everything else in this handler. Ungated it printed a
    -- bare table address to the PopTracker log once per item received.
    if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
      print(string.format("onItem: found object for %s", v[1]))
    end
    if v[2] == "toggle" then
      obj.Active = true
    elseif v[2] == "progressive" then
      if obj.Active then
        obj.CurrentStage = obj.CurrentStage + 1
      else
        obj.Active = true
      end
    elseif v[2] == "count" then
      -- A plain tally. "progressive" cannot be used here: on an item that
      -- allows a disabled state, setting Active is itself stage 1, but Shards
      -- has allow_disabled:false and no such state -- so the first shard set
      -- Active, left CurrentStage at 0, and every count after it read one low.
      -- The goal then opened a shard late and the grid drew the wrong gif.
      obj.CurrentStage = (obj.CurrentStage or 0) + 1
    elseif v[2] == "consumable" then
      obj.AcquiredCount = obj.AcquiredCount + 1
    elseif AUTOTRACKER_ENABLE_DEBUG_LOGGING then
      print(string.format("onItem: unknown item type %s for code %s", v[2], v[1]))
    end
  elseif AUTOTRACKER_ENABLE_DEBUG_LOGGING then
    print(string.format("onItem: could not find object for code %s", v[1]))
  end
end

-- Archipelago's name for a location, and this board's, are two different
-- vocabularies, and 254 of the 255 they share disagree. Both are defensible:
-- AP's are the randomizer's own player-facing set and read as route jargon plus
-- a floor label, and this pack's say where the thing is on the drawn floor. On
-- a map board the second is the one that helps, so neither wants renaming.
--
-- What costs a player is that 81 of them end in a number that disagrees, and
-- several are transposed -- AP's "Northwest Castle - Treasury 2" is this board's
-- "North West Castle Chests 3", while AP's "Treasury 3" is this board's
-- "Chests 2". Read a hint, match it by eye, and you land on the wrong chest with
-- nothing to tell you so.
--
-- The name has always arrived here and been thrown away. Keeping it, and saying
-- both halves out loud, is what makes the correspondence visible.
AP_GAME_NAME = "Final Fantasy"   -- manifest.json's game_name
AP_LOCATION_NAMES = {}

-- What Archipelago calls this location id.
--
-- GetLocationName answers for any id, checked or not, which is what a hint
-- needs; the recorded table only knows ids that have come through the feed. So
-- the getter is preferred and the table is the fallback for a host without it.
function apLocationName(id)
  if type(Archipelago.GetLocationName) == "function" then
    local ok, name = pcall(function()
      return Archipelago:GetLocationName(id, AP_GAME_NAME)
    end)
    if ok and type(name) == "string" and name ~= "" then
      return name
    end
  end
  return AP_LOCATION_NAMES[id]
end

-- What this board calls it: the location node out of "@Some Location/Section",
-- which is the Lua counterpart of tools/split_locations.leaf_of.
function packLocationName(path)
  return type(path) == "string" and path:gsub("^@", ""):gsub("/[^/]*$", "") or nil
end

-- "on Caves & Dungeons/Marsh Cave/Marsh Cave B1", or nil where nothing can say.
--
-- LOCATION_MAPS gives the map ids and tabPathForMap turns one into the tab it is
-- drawn on, which is also what applies the override's own tabs. Where no tab
-- claims the map, MAP_NAMES is the fallback -- guarded, because that file only
-- loads on the UAT branch. Where a location is drawn on more than one floor all
-- of them are named, because the cartridge really does lay it on more than one.
function locationWhere(path)
  local maps = LOCATION_MAPS and LOCATION_MAPS[path]
  if not maps then
    return nil
  end
  local seen, names = {}, {}
  for _, mapId in ipairs(maps) do
    local where = (type(tabPathForMap) == "function" and tabPathForMap(mapId))
                  or (MAP_NAMES or {})[mapId]
    if where and not seen[where] then
      seen[where] = true
      names[#names + 1] = where
    end
  end
  if #names == 0 then
    return nil
  end
  return table.concat(names, " or ")
end

-- Both names and the tab, in one line.
function describeLocation(id, path)
  local ap = apLocationName(id)
  local here = packLocationName(path)
  if not ap or not here then
    return nil
  end
  local where = locationWhere(path)
  if where then
    return string.format('Archipelago\'s "%s" is this board\'s "%s", on %s',
                         ap, here, where)
  end
  return string.format('Archipelago\'s "%s" is this board\'s "%s"', ap, here)
end

-- A connect replays every location already checked in one burst, and a line per
-- check across 254 of them is noise rather than an answer. So the lines start
-- after the replay, and the boundary is the first frame following onClear --
-- PopTracker delivers that burst inside one poll cycle, so no clock is needed,
-- and os.clock in particular would be wrong here for the reason armReassert
-- above spells out.
local REPLAY_HANDLER = "ap location replay"
local replaying = false

local function endReplay()
  ScriptHost:RemoveOnFrameHandler(REPLAY_HANDLER)
  replaying = false
end

-- Global because onClear is defined above this and would not see a local
-- declared here; it resolves the name when it runs, not when it was written.
function armAPLocationReplay()
  if not ScriptHost.AddOnFrameHandler then
    replaying = false
    return
  end
  replaying = true
  ScriptHost:AddOnFrameHandler(REPLAY_HANDLER, endReplay)
end

function onLocation(location_id, location_name)
  if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
    print(string.format("called onLocation: %s, %s", location_id, location_name))
  end
  if type(location_name) == "string" and location_name ~= "" then
    AP_LOCATION_NAMES[location_id] = location_name
  end
  markAPChecked(location_id)
  if not replaying then
    local v = LOCATION_MAPPING[location_id]
    local said = v and describeLocation(location_id, v[1])
    if said then
      print("check: " .. said)
    end
  end
end

-- The map tab follows the player; see scripts/autotracking/maptab.lua. The
-- emulator bridge is what actually reports the map, but these two handlers stay
-- wired up: if AP/worlds/ff1 ever does start publishing it, the same path
-- works, and until then they are no longer calling a function that does not
-- exist.

function updateEvents(value)
  activateMapTab(value)
end

function onNotify(key, value, old_value)
	updateEvents(value)
end

function onNotifyLaunch(key, value)
	updateEvents(value)
end

Archipelago:AddClearHandler("clear handler", onClear)
Archipelago:AddItemHandler("item handler", onItem)
Archipelago:AddLocationHandler("location handler", onLocation)
Archipelago:AddSetReplyHandler("notify handler", onNotify)
Archipelago:AddRetrievedHandler("notify launch handler", onNotifyLaunch)
