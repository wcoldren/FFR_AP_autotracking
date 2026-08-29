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

-- Where to go when the player is somewhere with no dungeon tab of its own:
-- the overworld itself, or one of the eight towns (MAP_VALUE sends those to
-- "Overworld" because they have no tab either).
--
-- Both candidates are the same overworld art; they differ in which markers
-- they carry. On an ordinary seed the incentive map carries the whole board --
-- AP puts only the incentive slots and the NPCs in the pool -- so it is much
-- the better of the two to land on. On a shard hunt, or any seed with the
-- chests shuffled in, the pool also holds all 230 chests and the incentive map
-- hides nearly everything the player is tracking; there the full Overworld is
-- the one to land on.
--
-- Which it is comes from the pool where there is one: AP states the location
-- list outright at connect, and apPoolChestCount() reads it. See the note there
-- for why presence, not a threshold, is the test.
--
-- A bridge-only session has no pool to read, and used to fall all the way
-- through to the incentive map -- which is exactly backwards on the seed most
-- likely to be played that way. The cartridge can answer the same question, so
-- it is asked second. The player can also just say; see tabMode() below.
local OVERWORLD_INCENTIVE = "Incentive Locations"
local OVERWORLD_FULL = "Overworld"
local MAP_VALUE_OVERWORLD = "Overworld"   -- what the data table calls it

-- nil until a session has been seen, and it has to stay distinguishable from
-- false: "no pool was ever stated" is what hands the question to the cartridge,
-- while "the pool holds no chests" is an answer in itself.
local chestsInPool = nil

local TAB_AUTO, TAB_INCENTIVE, TAB_FULL = 0, 1, 2

-- The player's own say, from the Overworld Tab item in the flags grid. It is a
-- progressive with allow_disabled false, so its stage is the stages[] index
-- rather than one above it, and there is no dead "off" click in the cycle.
local function tabMode()
  local obj = Tracker:FindObjectForCode("tab_mode")
  if not obj then
    return TAB_AUTO
  end
  return obj.CurrentStage or TAB_AUTO
end

-- Does the cartridge itself say the chests are worth watching?
--
-- Only asked when Archipelago never stated a pool. Two flags decide it:
--
--   ShardHunt       the shards are in the chests and collecting them is the
--                   goal, so every chest is a check by definition
--   ChestsKeyItems  FFR's "key items may be placed in chests" -- with it on,
--                   an ordinary chest can hold the thing that opens the run
--
-- Deliberately narrow. RelocateChests only moves chests about and TCChestCount
-- only counts the trapped ones; neither makes a chest hold something it would
-- not otherwise have held.
--
-- ffrFlag lives in flag_mapping.lua, which init.lua only loads for the UAT
-- feed, so this has to cope with it not existing at all. A tri-state rolled at
-- generation decodes to nil and takes the default, which is the ordinary seed.
local function cartridgeChestsAreChecks()
  if type(ffrFlag) ~= "function" then
    return false
  end
  return ffrFlag("ShardHunt", false) == true
      or ffrFlag("ChestsKeyItems", false) == true
end

-- Whether this variant lays out the full overworld map at all.
--
-- The NOverworld layouts do not, and cannot usefully: the mode replaces the
-- overworld with an ocean stub carrying nine one-tile town pads, so vanilla
-- overworld art would be a picture of somewhere the seed never goes. Every
-- answer below therefore has to collapse to the incentive tab there, whatever
-- the pool says -- asking for a tab the layout has not got activates nothing,
-- silently, which is the same failure the tab titles are checked for.
local function hasFullOverworldTab()
  return Tracker.ActiveVariantUID:find("NOverworld") == nil
end

-- Exposed for the tests and for anyone reading a log.
function overworldTab()
  if not hasFullOverworldTab() then return OVERWORLD_INCENTIVE end
  local mode = tabMode()
  if mode == TAB_INCENTIVE then return OVERWORLD_INCENTIVE end
  if mode == TAB_FULL then return OVERWORLD_FULL end
  if chestsInPool ~= nil then
    return chestsInPool and OVERWORLD_FULL or OVERWORLD_INCENTIVE
  end
  if cartridgeChestsAreChecks() then return OVERWORLD_FULL end
  return OVERWORLD_INCENTIVE
end

-- Called from onClear, once per connect. A host too old to report the pool
-- leaves the previous answer alone rather than resetting it to the default:
-- a mid-session reconnect should not walk back what an earlier connect proved.
function refreshOverworldTab()
  local chests = apPoolChestCount()
  if chests == nil then
    return
  end
  chestsInPool = chests > 0
  if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
    print(string.format("maptab: %d chests in the pool -> overworld tab is %q",
      chests, overworldTab()))
  end
end

-- Which variants lay out dungeon map tabs. The four NoMap variants have no
-- tabbed widget at all, so there is nothing to activate and no reason to look.
--
-- The NOverworld pair used to be excluded for the same reason -- they had a
-- single tab, the incentive poster. They now carry the same dungeon tree as
-- the standard layouts, from the same three shared_*_tabs keys, so the player
-- is followed into a dungeon there too. They still have no full overworld tab,
-- which hasFullOverworldTab above is what handles.
local TABBED_VARIANTS = {
  ["5standard"] = true,
  ["6shardHunt"] = true,
  ["7NOverworld"] = true,
  ["8shardHuntNOverworld"] = true,
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
    -- lastMapId has already moved, deliberately: turning the toggle back on
    -- should resume following from wherever the player is, not replay the
    -- floor they were on when they turned it off.
    return false
  end

  local path = (mapId == -1) and overworldTab() or (MAP_VALUE and MAP_VALUE[mapId])
  -- Towns come through the table as "Overworld"; send them the same way.
  if path == MAP_VALUE_OVERWORLD then
    path = overworldTab()
  end
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
  -- The bridge publishes a map with its opening full-state burst, before the
  -- save guard has settled, and holds the last one across a reset. Acting on
  -- that would throw whoever just connected mid-dungeon out to the Overworld
  -- tab for half a second.
  if store:ReadVariable("ff1/ready") ~= true then
    return
  end
  activateMapTab(store:ReadVariable("ff1/map"))
end

if ScriptHost.AddVariableWatch then
  ScriptHost:AddVariableWatch("ff1map", { "ff1/map", "ff1/ready" }, onFF1Map)
end
