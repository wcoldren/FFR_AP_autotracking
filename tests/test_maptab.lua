-- Map-tab switching: the paths, and the switching logic itself.
--
-- MAP_VALUE names tabs by title, as free text. A renamed or typo'd tab title
-- fails by activating nothing at all, silently, exactly like the section paths
-- in test_mapping.lua -- so it gets the same treatment.
local PACK = arg[1]
local json = dofile(PACK .. "/tests/json.lua")

AUTOTRACKER_ENABLE_DEBUG_LOGGING = false

local fail = 0
local function fails(msg)
  print("FAIL " .. msg)
  fail = fail + 1
end
local function check(name, got, want)
  if got ~= want then
    print(string.format("FAIL %-46s got=%s want=%s", name, tostring(got), tostring(want)))
    fail = fail + 1
  else
    print(string.format("ok   %-46s %s", name, tostring(got)))
  end
end

-- Every tab title the layout defines, at any nesting depth.
local function tabTitles(file)
  local titles = {}
  local function walk(node)
    if type(node) ~= "table" then return end
    if node.type == "tabbed" then
      for _, t in ipairs(node.tabs or {}) do
        if t.title then titles[t.title] = true end
        walk(t.content)
      end
    end
    for _, v in pairs(node) do
      if type(v) == "table" then walk(v) end
    end
  end
  walk(json.load(PACK .. "/" .. file))
  return titles
end

dofile(PACK .. "/scripts/autotracking/mapValues.lua")

-- 1. every path segment in MAP_VALUE names a real tab, in both layouts that
--    have them
for _, file in ipairs({ "layouts/standard/tracker.json", "layouts/shardHunt/tracker.json" }) do
  local titles = tabTitles(file)
  local bad = {}
  for id, path in pairs(MAP_VALUE) do
    for name in string.gmatch(path, "([^/]+)") do
      if not titles[name] then
        bad[#bad + 1] = string.format("map %d wants tab %q", id, name)
      end
    end
  end
  table.sort(bad)
  if #bad > 0 then
    for _, b in ipairs(bad) do fails(file .. ": " .. b) end
  else
    print(string.format("ok   every MAP_VALUE tab exists in %s", file:match("layouts/([^/]+)")))
  end
end

-- 1b. the tab used for anywhere without one of its own is not in MAP_VALUE, so
--     it needs the same existence check or it fails the same silent way.
local FALLBACK = "Incentive Locations"
for _, file in ipairs({ "layouts/standard/tracker.json", "layouts/shardHunt/tracker.json" }) do
  if not tabTitles(file)[FALLBACK] then
    fails(string.format("%s has no %q tab for the overworld fallback", file, FALLBACK))
  else
    print(string.format("ok   %q exists in %s", FALLBACK, file:match("layouts/([^/]+)")))
  end
end

-- 2. the switching logic
local hints = {}
local objects = { tab_switch = { Active = true } }
Tracker = {
  ActiveVariantUID = "5standard",
  FindObjectForCode = function(self, c) return objects[c] end,
  UiHint = function(self, kind, value) hints[#hints + 1] = kind .. ":" .. value end,
}
ScriptHost = { AddVariableWatch = function() end }

dofile(PACK .. "/scripts/autotracking/maptab.lua")

local function take()
  local h = table.concat(hints, ",")
  hints = {}
  return h
end

check("entering Earth Cave B1 moves the tab", activateMapTab(13), true)
check("  activates the whole nest", take(),
  "ActivateTab:Fiend Dungeons,ActivateTab:Earth Cave,ActivateTab:Earth Cave B1")

check("standing still does nothing", activateMapTab(13), false)
check("  and hints nothing", take(), "")

check("walking to B2 moves again", activateMapTab(29), true)
check("  to the right tab", take(),
  "ActivateTab:Fiend Dungeons,ActivateTab:Earth Cave,ActivateTab:Earth Cave B2")

check("a single-level tab works", activateMapTab(60), true)
check("  Titan's Tunnel", take(), "ActivateTab:Other,ActivateTab:Titan's Tunnel")

-- Anywhere without a tab of its own lands on the incentive map, which is the
-- same overworld art carrying the markers worth looking at during a run.
check("leaving for the overworld", activateMapTab(-1), true)
check("  activates Incentive Locations", take(), "ActivateTab:Incentive Locations")

-- towns are standard maps with no tab of their own either
check("a town goes the same way", activateMapTab(3), true)
check("  Incentive Locations again", take(), "ActivateTab:Incentive Locations")

-- 3. the toggle gates it, but the map is still tracked, so switching back on
--    does not replay a stale floor
objects.tab_switch.Active = false
check("toggle off suppresses the hint", activateMapTab(13), false)
check("  nothing activated", take(), "")
objects.tab_switch.Active = true
check("re-entering the same map stays quiet", activateMapTab(13), false)
check("  still nothing", take(), "")

-- 4. an unknown id is ignored rather than guessed at
resetMapTab()
check("unknown map id does nothing", activateMapTab(200), false)
check("  no hint", take(), "")
check("nil is ignored", activateMapTab(nil), false)

-- 5. variants without dungeon tabs never touch the UI
resetMapTab()
for _, v in ipairs({ "1standardNoMap", "3NOverworldNoMap", "7NOverworld", "8shardHuntNOverworld" }) do
  Tracker.ActiveVariantUID = v
  local moved = activateMapTab(13)
  if moved or take() ~= "" then
    fails(string.format("variant %s activated a tab it does not have", v))
  end
end
print("ok   variants without dungeon tabs are left alone")

Tracker.ActiveVariantUID = "6shardHunt"
resetMapTab()
check("shard hunt still switches", activateMapTab(13), true)
take()

-- 6. the watch itself gates on the bridge being ready. The bridge publishes a
--    map in its opening full-state burst and holds the last one across a reset,
--    so acting while not ready throws whoever just connected mid-dungeon out to
--    the Overworld tab.
Tracker.ActiveVariantUID = "5standard"
resetMapTab()
local function store(ready, map)
  return { ReadVariable = function(self, k)
    if k == "ff1/ready" then return ready end
    if k == "ff1/map" then return map end
  end }
end
onFF1Map(store(false, -1))
check("not ready is ignored", take(), "")
onFF1Map(store(true, 13))
check("ready acts", take(),
  "ActivateTab:Fiend Dungeons,ActivateTab:Earth Cave,ActivateTab:Earth Cave B1")
onFF1Map(store(false, -1))
check("a reset does not drag the tab away", take(), "")

print(fail == 0 and "\nALL PASS" or string.format("\n%d FAILURE(S)", fail))
os.exit(fail == 0 and 0 or 1)
