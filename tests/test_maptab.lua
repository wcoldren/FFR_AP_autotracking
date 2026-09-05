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

-- 0. every layout the pack registers has to be a JSON *object*.
--
--    Tracker::AddLayouts (tracker.cpp:505-515) skips any top-level value that
--    is not an object -- it prints "Bad layout" to stderr and carries on -- so
--    a layout wrapped in an array is never registered, and every
--    {"type": "layout"} reference to it expands to nothing. The tab that holds
--    it still draws, empty. That is how all three dungeon trees came to be
--    array-wrapped and every map tab in every map variant came up blank while
--    this suite stayed green: the walker below follows a reference into a Lua
--    table without caring whether it decoded from [ ] or { }, and PopTracker
--    cares very much.
local LAYOUT_FILES = {
  "layouts/shared.json",
  "layouts/standard/tracker.json",
  "layouts/standard/standard_broadcast.json",
  "layouts/standardNoMap/tracker.json",
  "layouts/standardNoMap/broadcastNoMap.json",
  "layouts/shardHunt/tracker.json",
  "layouts/shardHunt/broadcast.json",
  "layouts/shardHuntNoMap/tracker.json",
  "layouts/shardHuntNoMap/broadcastNoMap.json",
  "layouts/NOverworld/tracker.json",
  "layouts/NOverworld/broadcast.json",
  "layouts/NOverworld/trackerNoMap.json",
  "layouts/NOverworld/broadcastNoMap.json",
  "layouts/NOverworld/shardsTracker.json",
  "layouts/NOverworld/broadcastShards.json",
  "layouts/NOverworld/shardsTrackerNoMap.json",
  "layouts/NOverworld/broadcastShardsNoMap.json",
}

local registered = {}
local badLayouts = 0
for _, file in ipairs(LAYOUT_FILES) do
  local doc = json.load(PACK .. "/" .. file)
  if type(doc) ~= "table" then
    fails(file .. ": not a JSON object")
    badLayouts = badLayouts + 1
  else
    for key, value in pairs(doc) do
      -- json.lua decodes both [ ] and { } to a table, so an array is one with
      -- a [1]. Every layout here has named keys and no positional ones.
      if type(value) ~= "table" or value[1] ~= nil then
        fails(string.format("%s: layout %q is not an object, so PopTracker "
          .. "drops it and anything referencing it draws blank", file, key))
        badLayouts = badLayouts + 1
      else
        registered[key] = true
      end
    end
  end
end
if badLayouts == 0 then
  print(string.format("ok   all %d layout files register objects, not arrays",
    #LAYOUT_FILES))
end

-- 0b. and every reference names one of them.
local unresolved = {}
local function walkRefs(node)
  if type(node) ~= "table" then return end
  if node.type == "layout" and node.key and not registered[node.key] then
    unresolved[node.key] = true
  end
  for _, v in pairs(node) do walkRefs(v) end
end
for _, file in ipairs(LAYOUT_FILES) do walkRefs(json.load(PACK .. "/" .. file)) end
local missingRefs = {}
for key in pairs(unresolved) do missingRefs[#missingRefs + 1] = key end
table.sort(missingRefs)
if #missingRefs > 0 then
  for _, key in ipairs(missingRefs) do
    fails(string.format("layout %q is referenced but never registered", key))
  end
else
  print("ok   every layout reference resolves to a registered layout")
end

-- Every tab title the layout defines, at any nesting depth.
--
-- {"type": "layout", "key": k} has to be followed into layouts/shared.json,
-- because PopTracker expands it before any of this is on screen. The dungeon
-- tree lives there once and is referenced from all four map layouts, so a
-- walker that stopped at the reference would report that the standard layout
-- has no dungeon tabs at all.
local function tabTitles(file)
  local shared = json.load(PACK .. "/layouts/shared.json")
  local titles = {}
  local seen = {}
  local function walk(node)
    if type(node) ~= "table" then return end
    if node.type == "layout" and node.key then
      if not seen[node.key] then
        seen[node.key] = true
        walk(shared[node.key])
      end
      return
    end
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

-- The four layouts that lay out dungeon map tabs. The NOverworld pair joined
-- them when the dungeon tree moved into layouts/shared.json: they reference the
-- same three keys, so a tab renamed there has to stay in step with MAP_VALUE
-- for all four at once.
local MAP_LAYOUTS = {
  "layouts/standard/tracker.json",
  "layouts/shardHunt/tracker.json",
  "layouts/NOverworld/tracker.json",
  "layouts/NOverworld/shardsTracker.json",
}

-- Two of the four live in the same directory, so the directory alone names them
-- both: an "ok" line and a missing one would look identical at a glance.
local function layoutLabel(file)
  return (file:gsub("^layouts/", ""):gsub("%.json$", ""))
end

-- maptab.lua's own MAP_VALUE_OVERWORLD is a local, so this is a second copy on
-- purpose. It is one string and the check below is the thing that would notice
-- it drifting: change it there and every town starts failing here.
local MAP_VALUE_OVERWORLD = "Overworld"

dofile(PACK .. "/scripts/autotracking/mapValues.lua")

-- 1. every path segment in MAP_VALUE names a real tab, in both layouts that
--    have them
for _, file in ipairs(MAP_LAYOUTS) do
  local titles = tabTitles(file)
  local bad = {}
  for id, path in pairs(MAP_VALUE) do
    -- The eight towns come through the table as the bare string "Overworld",
    -- which activateMapTab never looks up: it redirects them through
    -- overworldTab() exactly like map id -1. Checking it as a literal title
    -- would demand an "Overworld" tab from the NOverworld layouts, which have
    -- no overworld to draw. The tabs it can redirect *to* are 1b's job.
    if path ~= MAP_VALUE_OVERWORLD then
      for name in string.gmatch(path, "([^/]+)") do
        if not titles[name] then
          bad[#bad + 1] = string.format("map %d wants tab %q", id, name)
        end
      end
    end
  end
  table.sort(bad)
  if #bad > 0 then
    for _, b in ipairs(bad) do fails(file .. ": " .. b) end
  else
    print(string.format("ok   every MAP_VALUE tab exists in %s", layoutLabel(file)))
  end
end

-- 1b. the tabs used for anywhere without one of its own are not in MAP_VALUE,
--     so they need the same existence check or they fail the same silent way.
--     Both are live now: which one the overworld lands on depends on whether
--     the seed put the chests in the pool.
--     The NOverworld layouts are the exception and deliberately so: they have
--     no "Overworld" tab because the mode has no overworld to draw, and
--     overworldTab() collapses to the incentive tab there rather than asking
--     for one that is not laid out.
local FALLBACKS = { "Incentive Locations", "Overworld" }
for _, file in ipairs(MAP_LAYOUTS) do
  local titles = tabTitles(file)
  local noverworld = file:find("NOverworld") ~= nil
  for _, fallback in ipairs(FALLBACKS) do
    local want = not (noverworld and fallback == "Overworld")
    if titles[fallback] == nil and want then
      fails(string.format("%s has no %q tab for the overworld fallback", file, fallback))
    elseif titles[fallback] and not want then
      fails(string.format("%s has an %q tab, but the mode has no overworld", file, fallback))
    else
      print(string.format("ok   %q %s in %s", fallback,
        want and "exists" or "is absent as intended", layoutLabel(file)))
    end
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

dofile(PACK .. "/scripts/autotracking/location_mapping.lua")
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

-- 5. the four NoMap variants have no tabbed widget at all, so they never touch
--    the UI. The NOverworld pair used to be in this list and no longer is:
--    they carry the shared dungeon tree now.
resetMapTab()
for _, v in ipairs({ "1standardNoMap", "2shardHuntNoMap", "3NOverworldNoMap",
                     "4shardHuntNOverworldNoMap" }) do
  Tracker.ActiveVariantUID = v
  local moved = activateMapTab(13)
  if moved or take() ~= "" then
    fails(string.format("variant %s activated a tab it does not have", v))
  end
end
print("ok   variants without dungeon tabs are left alone")

-- 5b. ...and the NOverworld map variants do follow the player into a dungeon,
--     down the same three-deep nest as the standard layout.
for _, v in ipairs({ "7NOverworld", "8shardHuntNOverworld" }) do
  Tracker.ActiveVariantUID = v
  resetMapTab()
  check(v .. " follows into Earth Cave B1", activateMapTab(13), true)
  check("  activates the whole nest", take(),
    "ActivateTab:Fiend Dungeons,ActivateTab:Earth Cave,ActivateTab:Earth Cave B1")
  -- and the overworld it has no tab for collapses to the incentive map
  check("  overworld goes to the incentive tab", overworldTab(), "Incentive Locations")
end

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


-- 7. which overworld tab the fallback lands on follows the Archipelago pool.
--
-- The two pools below are real. The incentive-only one is the location list
-- off an ordinary generation (spoiler "locations:" line, 19 ids); the chest
-- pool is every id the pack maps, which is what a shard hunt or a chest
-- shuffle produces. The gap between them is the whole detection: 0 chests
-- against 230, with nothing observed in between.
local INCENTIVE_ONLY_POOL = {
  259, 370, 387, 284, 317, 489, 436, 767,      -- incentive slots + shop
  513, 530, 519, 516, 522, 533, 518, 520, 525, 531, 529,  -- NPCs
}
local function poolOf(ids, checkedCount)
  local missing, checked = {}, {}
  for i, id in ipairs(ids) do
    if i <= (checkedCount or 0) then checked[#checked + 1] = id
    else missing[#missing + 1] = id end
  end
  return { MissingLocations = missing, CheckedLocations = checked }
end

Tracker.ActiveVariantUID = "5standard"

-- No host support at all: the pack keeps the behaviour it has always had.
Archipelago = nil
resetMapTab()
refreshOverworldTab()
check("no AP host -> incentive map", overworldTab(), "Incentive Locations")
check("  and the overworld goes there", activateMapTab(-1), true)
check("  hint", take(), "ActivateTab:Incentive Locations")

-- An ordinary seed. Every id in the pool is an incentive slot or an NPC.
Archipelago = poolOf(INCENTIVE_ONLY_POOL, 4)
resetMapTab()
refreshOverworldTab()
check("incentive-only pool has no chests", apPoolChestCount(), 0)
check("incentive-only pool -> incentive map", overworldTab(), "Incentive Locations")
check("  overworld lands on it", activateMapTab(-1), true)
check("  hint", take(), "ActivateTab:Incentive Locations")
check("  a town lands on it too", activateMapTab(3), true)
check("  hint", take(), "ActivateTab:Incentive Locations")

-- Shard hunt / chests shuffled in: the incentive map would hide almost every
-- check the player has, so the fallback moves to the full Overworld.
local everything = {}
for id in pairs(LOCATION_MAPPING) do everything[#everything + 1] = id end
table.sort(everything)
Archipelago = poolOf(everything, 10)
resetMapTab()
refreshOverworldTab()
check("chest pool is counted", apPoolChestCount(), 230)
check("chest pool -> full overworld", overworldTab(), "Overworld")
check("  overworld lands on it", activateMapTab(-1), true)
check("  hint", take(), "ActivateTab:Overworld")
check("  a town lands on it too", activateMapTab(3), true)
check("  hint", take(), "ActivateTab:Overworld")

-- A host too old to report the pool must not walk back what an earlier
-- connect proved: a reconnect through such a host keeps the full overworld.
Archipelago = { MissingLocations = nil, CheckedLocations = nil }
refreshOverworldTab()
check("unreportable pool leaves the answer alone", overworldTab(), "Overworld")

-- And a genuinely incentive-only reconnect does move it back.
Archipelago = poolOf(INCENTIVE_ONLY_POOL, 0)
refreshOverworldTab()
check("a new incentive-only seed moves it back", overworldTab(), "Incentive Locations")
Archipelago = nil

------------------------------------------------------------------
-- 8. the player's own say, and the cartridge as a second opinion.
--
-- The bridge-only case is the one that started this: no Archipelago at all,
-- so no pool was ever stated, and the pack used to fall through to the
-- incentive map -- which on a shard hunt hides nearly every check there is.
------------------------------------------------------------------
Archipelago = nil
objects.tab_mode = { CurrentStage = 0 }

-- Auto with a pool still follows the pool, both ways.
Archipelago = poolOf(everything, 0)
refreshOverworldTab()
check("auto still follows a chest pool", overworldTab(), "Overworld")
Archipelago = poolOf(INCENTIVE_ONLY_POOL, 0)
refreshOverworldTab()
check("auto still follows an incentive pool", overworldTab(), "Incentive Locations")

-- Pinned, the pool does not get a vote.
objects.tab_mode.CurrentStage = 2
check("Full wins over an incentive-only pool", overworldTab(), "Overworld")
check("  and the overworld goes there", activateMapTab(-1), true)
check("  hint", take(), "ActivateTab:Overworld")
Archipelago = poolOf(everything, 0)
refreshOverworldTab()
objects.tab_mode.CurrentStage = 1
check("Incentive wins over a chest pool", overworldTab(), "Incentive Locations")
check("  and a town goes there", activateMapTab(3), true)
check("  hint", take(), "ActivateTab:Incentive Locations")

-- Now the bridge-only case. No Archipelago at all, so nothing ever set
-- chestsInPool -- which has to stay distinguishable from "the pool had no
-- chests", or the cartridge would never be asked.
-- Reloaded rather than reset: chestsInPool is a file-local, and a fresh load
-- is the only way back to "no pool has ever been stated".
Archipelago = nil
dofile(PACK .. "/scripts/autotracking/maptab.lua")
objects.tab_mode = { CurrentStage = 0 }

ffrFlag = nil
check("no pool and no cartridge -> incentive map", overworldTab(), "Incentive Locations")

local FLAGS = {}
function ffrFlag(name, default)
  local v = FLAGS[name]
  if v == nil then return default end
  return v
end

FLAGS = {}
check("an ordinary cartridge -> incentive map", overworldTab(), "Incentive Locations")

FLAGS = { ShardHunt = true }
check("a shard hunt -> full overworld", overworldTab(), "Overworld")
check("  and the overworld goes there", activateMapTab(-1), true)
check("  hint", take(), "ActivateTab:Overworld")

FLAGS = { ChestsKeyItems = true }
check("key items in chests -> full overworld", overworldTab(), "Overworld")

-- Rolled at generation: the flag string records that it was rolled, not where
-- it landed, so it decodes to nil and must not move the tab.
FLAGS = { ShardHunt = nil, ChestsKeyItems = nil }
check("a rolled tri-state leaves it alone", overworldTab(), "Incentive Locations")

-- Flags that look relevant and are not: neither makes a chest hold anything it
-- would not otherwise have held.
FLAGS = { RelocateChests = true, TCChestCount = 40 }
check("relocated and trapped chests do not count", overworldTab(), "Incentive Locations")

-- And a pool, once one is stated, outranks the cartridge.
FLAGS = { ShardHunt = true }
Archipelago = poolOf(INCENTIVE_ONLY_POOL, 0)
refreshOverworldTab()
check("a stated pool outranks the cartridge", overworldTab(), "Incentive Locations")
Archipelago = nil
ffrFlag = nil

------------------------------------------------------------------
-- 9. the fresh board's defaults are declared, not written.
--
-- scripts/init.lua used to set both of these at load. The tab_mode write was a
-- no-op -- with allow_disabled false the guard in Lua_NewIndex compares a value
-- with itself (PopTracker core/jsonitem.cpp:473-500) -- and both of them landed
-- in the reset snapshot PopTracker takes one line after init.lua runs, so Reset
-- walked a pinned choice back to what the script had asserted rather than to
-- what the pack declares.
--
-- Declaring them is what makes the snapshot the pack's own answer. This is the
-- check that fails if someone puts the writes back: an item whose default lives
-- in a script has no default here at all.
------------------------------------------------------------------
local defs = {}
for _, def in ipairs(json.load(PACK .. "/items/flags.json")) do
  if def.name then defs[def.name] = def end
end
check("Auto-Tab declares that it starts on",
      defs["Auto-Tab"] and defs["Auto-Tab"].initial_active_state, true)
-- Nothing declares a starting stage, so stage 0 is Auto by position. Saying so
-- here is what stops the stages being reordered under overworldTab()'s
-- comparisons without anything noticing.
check("Overworld Tab starts on Auto by position",
      defs["Overworld Tab"] and defs["Overworld Tab"].initial_stage_idx, nil)
check("  and its first stage is the Auto one",
      defs["Overworld Tab"].stages[1].name,
      "Overworld Tab: Auto (the seed decides)")

local init = io.open(PACK .. "/scripts/init.lua"):read("a")
-- Line by line with the comments dropped, rather than a two-line window over
-- the whole file. The assignment does not have to sit directly under the
-- lookup to be back -- `tabMode.Active = true` occupies the line it used to be
-- on, so the natural place to re-add it is one lower, which the window missed.
-- Comments are dropped because init.lua's own note says the words
-- `tabMode.CurrentStage = 0` to explain why they are gone, and `shardsRequired`
-- sets CurrentStage for real, so neither the bare name nor the bare field is
-- something to search the file for.
local function sets(text, pattern)
  for line in text:gmatch("[^\n]+") do
    if not line:match("^%s*%-%-") and line:match(pattern) then
      return true
    end
  end
  return false
end
check("init.lua asserts no tab stage",
      sets(init, "tabMode%.CurrentStage")
      or sets(init, "tab_mode.*CurrentStage"), false)
check("  and no Auto-Tab default", sets(init, "tabSwitch%.Active"), false)

print(fail == 0 and "\nALL PASS" or string.format("\n%d FAILURE(S)", fail))
os.exit(fail == 0 and 0 or 1)
