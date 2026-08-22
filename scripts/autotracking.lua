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
    elseif v[2] == "consumable" then
      obj.AcquiredCount = obj.AcquiredCount + 1
    elseif AUTOTRACKER_ENABLE_DEBUG_LOGGING then
      print(string.format("onItem: unknown item type %s for code %s", v[2], v[1]))
    end
  elseif AUTOTRACKER_ENABLE_DEBUG_LOGGING then
    print(string.format("onItem: could not find object for code %s", v[1]))
  end
end

function onLocation(location_id, location_name)
  if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
    print(string.format("called onLocation: %s, %s", location_id, location_name))
  end
  markAPChecked(location_id)
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
