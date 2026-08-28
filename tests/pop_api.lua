-- PopTracker's pack-facing Lua surface, transcribed from the host it runs on.
--
-- The point of writing it down is that the mocks and the pack can disagree
-- silently. Calling a method on the wrong global returns nil rather than
-- raising, and every call site in this pack is behind a
-- `type(X.Method) ~= "function"` feature check -- so a wrong global reads as
-- "this host is too old", the feature turns itself off, and nothing is logged.
-- That is how Tracker:CreateLuaItem shipped: it is ScriptHost:CreateLuaItem,
-- so the ROM memo and the Resync button were never created on any host, and a
-- mock that repeated the mistake kept the suite green.
--
-- Sources (vendor/PopTracker, 0.35.4):
--   doc/PACKS.md:110-150      the documented globals
--   src/core/tracker.cpp:15-25      Tracker's Lua method table
--   src/core/tracker.cpp:731-773    Tracker's Lua properties
--   src/core/scripthost.cpp:16-32   ScriptHost's Lua method table

local M = {}

M.TRACKER = {
  -- methods, tracker.cpp:15-25
  AddItems = true, AddLocations = true, AddMaps = true, AddLayouts = true,
  AddClasses = true, ProviderCountForCode = true, FindObjectForCode = true,
  UiHint = true, OpenLink = true,
  -- properties, tracker.cpp:731-773
  ActiveVariantUID = true, BulkUpdate = true, AllowDeferredLogicUpdate = true,
}

M.SCRIPTHOST = {
  -- methods, scripthost.cpp:16-32
  LoadScript = true, AddMemoryWatch = true, RemoveMemoryWatch = true,
  AddWatchForCode = true, RemoveWatchForCode = true, CreateLuaItem = true,
  AddVariableWatch = true, RemoveVariableWatch = true,
  AddOnFrameHandler = true, RemoveOnFrameHandler = true,
  AddOnLocationSectionChangedHandler = true,
  RemoveOnLocationSectionChangedHandler = true,
  RemoveOnLocationSectionHandler = true,
  RunScriptAsync = true, RunStringAsync = true, AsyncProgress = true,
}

-- Where a name that is easy to reach for actually lives, so the error says so.
local ELSEWHERE = {
  Tracker = { CreateLuaItem = "ScriptHost", AddVariableWatch = "ScriptHost",
              AddOnFrameHandler = "ScriptHost", AddMemoryWatch = "ScriptHost",
              AddWatchForCode = "ScriptHost", LoadScript = "ScriptHost" },
  ScriptHost = { FindObjectForCode = "Tracker", ProviderCountForCode = "Tracker",
                 UiHint = "Tracker", AddItems = "Tracker", AddLayouts = "Tracker",
                 AddLocations = "Tracker", AddMaps = "Tracker" },
}

-- Make `mock` behave like the real global: a documented name the mock does not
-- stub reads as nil, so the pack's feature checks still work, and anything else
-- raises instead of quietly turning a feature off.
--
-- __index fires on reads only, so a plain field assignment like
-- `Tracker.BulkUpdate = true` is unaffected.
function M.strict(name, mock)
  local allowed = M[name:upper()]
  return setmetatable(mock, {
    __index = function(_, key)
      if allowed[key] then return nil end
      local other = ELSEWHERE[name] and ELSEWHERE[name][key]
      if other then
        error(string.format("%s has no %s -- it is %s:%s", name, key, other, key), 2)
      end
      error(string.format("%s has no %s (not in PopTracker's Lua surface)", name, key), 2)
    end,
  })
end

return M
