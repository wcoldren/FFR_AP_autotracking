-- The badge on an entrance pin: what it says, and where a click sends you.
--
-- The items are the only way a pin can carry text, so what is checked here is
-- text and navigation rather than state -- the mark stays edges.lua's and
-- tests/test_edges.lua owns it. The two files share a fixture on purpose: the
-- same four pins, so a row here about the town case can be read beside the row
-- there about the same walk.
local PACK = arg[1]
local popapi = dofile(PACK .. "/tests/pop_api.lua")

-- Four pins, as in test_edges.lua: an overworld door, the way out of the town
-- below it, and the two ends of one staircase.
local DOOR = "@Entrances/Entrance: Coneria/Coneria"
local WAY_OUT = "@Entrances/Entrance: ConeriaTown S Downstairs/ConeriaTown S Downstairs"
local STAIR_UP = "@Entrances/Entrance: MarshCaveB1 NW Downstairs/MarshCaveB1 NW Downstairs"
local STAIR_DOWN = "@Entrances/Entrance: MarshCaveB2 SE Downstairs/MarshCaveB2 SE Downstairs"

ENTRANCE_LINKS = {
  ["-1,152,161"] = DOOR, ["-1,153,161"] = DOOR,
  ["1,7,15"] = WAY_OUT, ["1,8,15"] = WAY_OUT,
  ["5,11,3"] = STAIR_UP,
  ["6,5,29"] = STAIR_DOWN,
}

ENTRANCE_PINS = {
  [DOOR] = { code = "entr_coneria", map = -1, name = "Entrance: Coneria" },
  [WAY_OUT] = { code = "entr_coneriatown_s_downstairs", map = 1,
                name = "Entrance: ConeriaTown S Downstairs" },
  [STAIR_UP] = { code = "entr_marshcaveb1_nw_downstairs", map = 5,
                 name = "Entrance: MarshCaveB1 NW Downstairs" },
  [STAIR_DOWN] = { code = "entr_marshcaveb2_se_downstairs", map = 6,
                   name = "Entrance: MarshCaveB2 SE Downstairs" },
}

-- Two maps have a tab and two do not, which is the split the badge has to
-- survive: the leaf of a tab path is the friendly name, and MAP_NAMES is what
-- answers for a map no tab claims.
MAP_NAMES = {
  [-1] = "Overworld", [1] = "ConeriaTown", [5] = "MarshCaveB1",
  [6] = "MarshCaveB2",
}

-- The overworld's tab is "Incentive Locations" here rather than "Overworld",
-- and that is the real one rather than an awkward fixture: maptab's
-- tabPathForMap(-1) answers overworldTab(), which is the incentive poster on
-- an ordinary seed and on both NOverworld variants. A tab path is not a map
-- name there, so the badge has to take the overworld from MAP_NAMES -- while a
-- click on the same pin still has to open the tab. Both are checked below.
local TAB_PATHS = {
  [-1] = "Incentive Locations",
  [5] = "Caves & Dungeons/Marsh Cave/Marsh Cave B1",
}

function tabPathForMap(mapId)
  return TAB_PATHS[mapId]
end

local hints = {}
function activateTabPath(path)
  for name in string.gmatch(path, "([^/]+)") do
    hints[#hints + 1] = name
  end
end

-- maptab.lua's, counted rather than stubbed away: a click moves the tab behind
-- activateMapTab's back, and forgetting the last map is how the board is told
-- the tab no longer shows where the party is standing.
local forgotten = 0
function resetMapTab()
  forgotten = forgotten + 1
end

Highlight = { None = 0, Priority = 4 }

local SECTIONS = {}
for _, path in pairs(ENTRANCE_LINKS) do
  SECTIONS[path] = SECTIONS[path] or { ChestCount = 1, AvailableChestCount = 1,
                                       Highlight = Highlight.None }
end

local luaItems = {}
Tracker = popapi.strict("Tracker", {
  FindObjectForCode = function(_, code) return SECTIONS[code] end,
})
local frameHandlers = {}
ScriptHost = popapi.strict("ScriptHost", {
  CreateLuaItem = function()
    local it = {}
    luaItems[#luaItems + 1] = it
    return it
  end,
  AddOnFrameHandler = function(_, name, fn) frameHandlers[name] = fn end,
  RemoveOnFrameHandler = function(_, name) frameHandlers[name] = nil end,
})

local fail = 0
local function check(label, got, want)
  local ok = got == want
  if not ok then fail = fail + 1 end
  print(string.format("%s %-54s %s", ok and "ok  " or "FAIL", label, tostring(got)))
  if not ok then print(string.format("     wanted %s", tostring(want))) end
end

dofile(PACK .. "/scripts/entrance_items.lua")

local FWD = "\226\134\146"
local REV = "\226\134\144"
local BOTH = "\226\134\148"

local function badge(path)
  return ENTRANCE_ITEMS[path].item.BadgeText
end

------------------------------------------------------------------
print("-- one item per pin")
------------------------------------------------------------------

check("an item was made for every pin", #luaItems, 4)
check("and each is reachable by its path",
  ENTRANCE_ITEMS[DOOR] ~= nil and ENTRANCE_ITEMS[STAIR_DOWN] ~= nil, true)
check("the item is named for the pin", ENTRANCE_ITEMS[DOOR].item.Name,
  "Entrance: Coneria")
check("and answers to the code the section hosts",
  ENTRANCE_ITEMS[DOOR].item.CanProvideCodeFunc(nil, "entr_coneria"), true)
check("and to nothing else",
  ENTRANCE_ITEMS[DOOR].item.CanProvideCodeFunc(nil, "entr_cardia1"), false)
-- The same answer a host new enough for it reads without entering Lua. There
-- are 178 of these items on a real board and the closure above is pcalled for
-- every one of them on every code a provider scan resolves, so the list is
-- what a current PopTracker uses and the closure is what an older one falls
-- back to. Both are set; only one of them is ever asked.
check("and says so as a list too, for a host that can read one",
  (ENTRANCE_ITEMS[DOOR].item.PotentialCodes or {})[1], "entr_coneria")

-- The provide is unconditional, and that is load-bearing rather than lazy: a
-- section is CLEARED only when its items are cleared and every hosted code has
-- a provider (locationsection.cpp:236-249), so an item that answered 0 until
-- the destination were known would hold the pin open -- and would take the
-- hand-click clear away with it, on a board where clicking a door has always
-- worked.
check("it provides its code before anything is known",
  ENTRANCE_ITEMS[DOOR].item.ProvidesCodeFunc(nil, "entr_coneria"), 1)
check("the badge starts empty", badge(DOOR), "")

------------------------------------------------------------------
print("\n-- what a walk writes on it")
------------------------------------------------------------------

check("a destination with a tab is named by its leaf",
  setEntranceForward(DOOR, 5, STAIR_UP) and badge(DOOR), FWD .. "Marsh Cave B1")
-- The other half of the same rule: nothing claims map 6, so the badge falls
-- back to the committed name rather than saying nothing at all.
check("and one without a tab by MAP_NAMES",
  setEntranceForward(STAIR_UP, 6, STAIR_DOWN) and badge(STAIR_UP),
  FWD .. "MarshCaveB2")
check("re-setting the same destination is not a change",
  setEntranceForward(DOOR, 5, STAIR_UP), false)
check("the far pin reads the same edge backwards",
  setEntranceReverse(STAIR_DOWN, 5, STAIR_UP) and badge(STAIR_DOWN),
  REV .. "Marsh Cave B1")

-- A door whose two directions agree is one line, which is what a two-way link
-- looks like from the pin standing on it.
setEntranceReverse(STAIR_UP, 6, STAIR_DOWN)
check("both directions on one map collapse to one line", badge(STAIR_UP),
  BOTH .. "MarshCaveB2")
setEntranceReverse(STAIR_UP, -1, DOOR)
check("and two maps are two lines", badge(STAIR_UP),
  FWD .. "MarshCaveB2" .. "\n" .. REV .. "Overworld")

-- The overworld is named from MAP_NAMES and not from its tab. Its tab is
-- whichever of the two posters the seed wants, so taking the leaf there would
-- badge the way out of every town "Incentive Locations" -- the wrong answer to
-- the question the badge asks, on roughly the thirty most-walked pins there
-- are. The two really do disagree in this fixture, which is what makes the row
-- above worth reading.
check("the overworld is not named after whichever poster is up",
  ENTRANCE_ITEMS[STAIR_UP].item.BadgeText:find("Incentive") == nil, true)

check("a pin nothing has said anything about stays blank", badge(WAY_OUT), "")

-- The badge is an item *overlay*, and PopTracker neither measures an overlay
-- into the hover tooltip's width nor clips it when it draws it
-- (item.cpp:336-368, maptooltip.cpp:202-205), so a name wider than the slot
-- renders out through the popup's background with nothing complaining.
-- entrance_items.lua trims the handful of names that would; the slot itself is
-- overworld_pins.ENTRANCE_ITEM_WIDTH, and tools/tests/test_badge_width.py is
-- what measures the two against each other.
--
-- Both sources, because the fallback is where this went wrong: abbreviation
-- used to be applied on the tab-leaf branch only, which left the widest string
-- the pack can draw on the one path nothing checked.
TAB_PATHS[7] = "Caves & Dungeons/Castle of Ordeals/Castle of Ordeals 2F"
MAP_NAMES[8] = "TempleOfFiendsRevisitedChaos"
check("a long tab leaf is abbreviated on the badge",
  setEntranceForward(WAY_OUT, 7, nil) and badge(WAY_OUT), FWD .. "Ordeals 2F")
check("and so is a long MAP_NAMES fallback",
  setEntranceForward(WAY_OUT, 8, nil) and badge(WAY_OUT), FWD .. "ToFR Chaos")
check("a name inside the slot is left alone",
  setEntranceForward(WAY_OUT, 5, nil) and badge(WAY_OUT),
  FWD .. "Marsh Cave B1")
setEntranceForward(WAY_OUT, nil, nil)
check("a path no pin owns is not an item",
  setEntranceForward("@Entrances/Entrance: Nowhere/Nowhere", 1, nil), false)

------------------------------------------------------------------
print("\n-- the clicks")
------------------------------------------------------------------

hints = {}
forgotten = 0
ENTRANCE_ITEMS[WAY_OUT].item.OnLeftClickFunc()
check("a click before the walk goes nowhere", #hints, 0)
-- And leaves the follow alone. Nothing moved, so there is nothing to forget --
-- resetting here would make the next report re-tab for no reason.
check("and leaves the party's tab alone", forgotten, 0)

hints = {}
forgotten = 0
ENTRANCE_ITEMS[DOOR].item.OnLeftClickFunc()
check("left-click tabs to where the door led", table.concat(hints, "/"),
  "Caves & Dungeons/Marsh Cave/Marsh Cave B1")
-- The tab now shows a floor the party is not on, and activateMapTab would go on
-- believing otherwise: its guard drops a report for the map it thinks is
-- showing, which after a click is the one report that would put the board back.
check("and stops claiming the tab follows the party", forgotten, 1)
check("and lights the pin at the far end",
  SECTIONS[STAIR_UP].Highlight, Highlight.Priority)
check("with a frame handler to put it out",
  frameHandlers["entrance highlight"] ~= nil, true)

hints = {}
ENTRANCE_ITEMS[STAIR_DOWN].item.OnRightClickFunc()
check("right-click tabs to what leads here", table.concat(hints, "/"),
  "Caves & Dungeons/Marsh Cave/Marsh Cave B1")

-- The handler is a no-op until the time is up, then it clears the pin and
-- takes itself off. Both halves, because a highlight that never came off would
-- leave the board gold everywhere a door was clicked.
--
-- The seconds are the ones PopTracker hands the handler, and they are wall
-- seconds since it last ran. Fed in a frame at a time here for the same reason
-- the real thing accumulates them: os.clock, which this used to time, is CPU
-- time, and five of those on an idle tracker are tens of seconds of somebody
-- watching a gold pin.
frameHandlers["entrance highlight"](1.0)
frameHandlers["entrance highlight"](1.0)
check("the highlight holds while the clock is running",
  SECTIONS[STAIR_UP].Highlight, Highlight.Priority)
frameHandlers["entrance highlight"](3.0)
check("and comes off when it is up", SECTIONS[STAIR_UP].Highlight,
  Highlight.None)
check("and the handler removes itself",
  frameHandlers["entrance highlight"], nil)

-- The other half of the overworld rule: the badge does not take its name from
-- the tab, and the click still goes to the tab. STAIR_UP's reverse is the
-- overworld door, so this opens whichever poster overworldTab() picked --
-- "Incentive Locations" in this fixture, which is the leaf the badge above
-- refused to use as a name.
hints = {}
ENTRANCE_ITEMS[STAIR_UP].item.OnRightClickFunc()
check("a click bound for the overworld opens the tab that is up",
  table.concat(hints, "/"), "Incentive Locations")

------------------------------------------------------------------
print("\n-- a different cartridge")
------------------------------------------------------------------

check("clearing says how many badges it blanked", clearEntranceNames(), 3)
check("and the door says nothing again", badge(DOOR), "")
check("clearing twice is not a change", clearEntranceNames(), 0)

print("")
if fail > 0 then
  print(string.format("%d FAILED", fail))
  os.exit(1)
end
print("ALL PASS")
