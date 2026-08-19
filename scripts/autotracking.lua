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
--ScriptHost:LoadScript("scripts/mapValues.lua")		//  for possible future auto-swappable map tabbing

function onClear()
  if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
    print(string.format("called onClear"))
  end
  CUR_INDEX = -1
  resetChecked()
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
    print(string.format("onItem: Found object %s", obj))
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

--this is stuff to update the tabs using the AT, but will need to wait til AP/worlds/ff1 has some updates

function onNotify(key, value, old_value)
	updateEvents(value)
end

function onNotifyLaunch(key, value)
	updateEvents(value)
end

--[[  for possible future auto-swappable map tabbing

function updateEvents(value)
    if value ~= nil then
	    print(string.format("updateEvents %x",value))
		--local tabswitch = Tracker:FindObjectForCode("tab_switch")
        --Tracker:FindObjectForCode("cur_level_id").CurrentStage = value
		if tabswitch.Active then
			local mapValue = MAP_VALUE and MAP_VALUE[value]
            if mapValue then
                -- Split by '/' and process each map name/tab
                for str in string.gmatch(mapValue, "([^/]+)") do
                    if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
                        print(string.format("Updating ID %x to Tab %s", value, str))
                        Tracker:UiHint("ActivateTab", str)
                    end
                end
                if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
                    print(string.format("Value: %x --- Map: %s", value, mapValue))
                end
            else
                if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
                    print("Overworld or unknown map value: ", value)
                end
            end
		end
	end
end

]]--

Archipelago:AddClearHandler("clear handler", onClear)
Archipelago:AddItemHandler("item handler", onItem)
Archipelago:AddLocationHandler("location handler", onLocation)
Archipelago:AddSetReplyHandler("notify handler", onNotify)
Archipelago:AddRetrievedHandler("notify launch handler", onNotifyLaunch)
