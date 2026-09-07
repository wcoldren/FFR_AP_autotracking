-- The badge on an entrance pin: where the door came out.
--
-- The pins say a door is here and, since the edge log landed, that somebody has
-- walked through it. What they cannot say is where it led, and a marker's name
-- is fixed at load -- AvailableChestCount and Highlight are the only things a
-- script may write to a section (locationsection.cpp:262-294). So the text
-- rides on an item the section hosts, one item per pin, and this is where they
-- are made.
--
-- Nothing here reads a teleport table. A badge is filled in from ff1/edges,
-- which is the party's own walk, so the board learns the permutation exactly as
-- the player does and reveal-on-visit still cannot spoil a seed. That is why
-- "walked through" and "destination known" are the same fact here.
--
-- ENTRANCE_PINS comes from scripts/entrance_links.lua, which a regen writes
-- into the override beside the art. The pack's copy is empty, so a tracker with
-- no override makes no items -- which is right, since it has no pins to hang
-- them on either.
--
-- The item always provides its code, and that is deliberate rather than
-- incidental: locationsection.cpp:236-249 clears a section only when its items
-- are cleared *and* every hosted code has a provider, so an item that withheld
-- its code would hold the pin open and take the hand-click clear away with it.
-- The badge is text; the state stays edges.lua's.

-- path -> { item, code, map, name, fwdMap, fwdPath, revMap, revPath }
ENTRANCE_ITEMS = {}

-- Byte escapes rather than literals so the file's encoding cannot decide what
-- a player sees: -> <- <->
local ARROW_FWD = "\226\134\146"
local ARROW_REV = "\226\134\144"
local ARROW_BOTH = "\226\134\148"

-- The pins' own icons, and committed rather than written by a regen --
-- Pack::hasFile does not consult the override even though Pack::ReadFile does,
-- which is why they are in the pack at all. An item with no icon draws
-- PopTracker's fallback, and these are the two pictures the board already uses
-- for the same two states.
-- The badge item's picture, and it is transparent on purpose.
--
-- A tooltip draws the location's own icon *and* every hosted item
-- (maptooltip.cpp:143-158), so an entrance section has always been two cells:
-- the door's state, which edges.lua opens when the party walks through, and
-- this one, which carries where it went. Both used to wear the same door and
-- read as one thing printed twice.
--
-- It cannot simply have no icon. makeItem skips an item whose image is empty,
-- and Item::render returns at :262 before it reaches the overlay -- so a badge
-- with no picture draws no text either. The cell has to hold something and the
-- something has to be invisible.
--
-- The open/shut pair went with the door: this cell no longer has a state to
-- report, because the cell beside it already reports it.
local DOOR_BADGE_ICON = "images/icons/door_badge.png"

-- How long the far pin stays lit after a click that tabbed to it, in seconds
-- of wall time -- see removeEntranceHighlight for where the seconds come from.
local HIGHLIGHT_SECONDS = 5
local HIGHLIGHT_SECTION = nil
local HIGHLIGHT_ELAPSED = 0

-- Names the badge draws shorter than the tab does.
--
-- The badge is an item overlay, and PopTracker neither measures an overlay into
-- the tooltip's width nor clips it when it draws it (item.cpp:336-368), so the
-- text used to render straight out through the popup's background. The fix is
-- two halves and this is the cheaper one: the slot is widened to
-- overworld_pins.ENTRANCE_ITEM_WIDTH, and the names below are trimmed so the
-- slot does not have to be half as wide again.
--
-- Fourteen because fourteen is all there is. Measured through
-- DejaVuSans-Bold.ttf -- the face the overlay is actually drawn in -- at the
-- 10px SetOverlayFontSize below, everything else is already under the five
-- Gurgu Volcano floors at 109.2px, so trimming any of them would buy nothing.
-- Left alone the widest line is "TempleOfFiendsRevisitedWater" at 186.7px;
-- trimmed, the widest is "Ice Cave Incentive" at 111.3px.
--
-- Keyed on the name rather than the map id because that is what mapName has in
-- hand at the point it answers, and because a tab renamed in mapValues.lua
-- should stop matching rather than quietly abbreviate to the old name.
-- tools/tests/test_badge_width.py measures every name the pack can show against
-- the slot, so a new long one fails a suite instead of overflowing a popup
-- nobody is looking at.
local BADGE_SHORT = {
  ["Ice Cave - Incentive Room"] = "Ice Cave Incentive",
  ["Ice Cave - Bottom Floor"] = "Ice Cave Bottom",
  ["Ice Cave - Exit Floor"] = "Ice Cave Exit",
  ["Castle of Ordeals 1F"] = "Ordeals 1F",
  ["Castle of Ordeals 2F"] = "Ordeals 2F",
  ["Castle of Ordeals 3F"] = "Ordeals 3F",
  -- MAP_NAMES rather than tab leaves. Every map on the board is claimed by a
  -- tab today, so these only answer where tabPathForMap does not -- which is
  -- the case the fallback exists for, and a badge should not overflow there
  -- either. The Revisited floors are the whole of that list: nothing else in
  -- map_names.lua is over budget.
  ["TempleOfFiendsRevisited1F"] = "ToFR 1F",
  ["TempleOfFiendsRevisited2F"] = "ToFR 2F",
  ["TempleOfFiendsRevisited3F"] = "ToFR 3F",
  ["TempleOfFiendsRevisitedEarth"] = "ToFR Earth",
  ["TempleOfFiendsRevisitedFire"] = "ToFR Fire",
  ["TempleOfFiendsRevisitedWater"] = "ToFR Water",
  ["TempleOfFiendsRevisitedAir"] = "ToFR Air",
  ["TempleOfFiendsRevisitedChaos"] = "ToFR Chaos",
}

-- What to call the map a door came out on.
--
-- The tab's own leaf first, because that is the label the player is about to be
-- looking at -- "Earth Cave B1" rather than "EarthCaveB1" -- and MAP_NAMES
-- underneath for a map no tab claims. A badge with no name in it is the thing
-- this file exists to remove, so it is answered twice rather than once.
--
-- The overworld is the exception and has to be, because there the tab is not a
-- name for the map. tabPathForMap(-1) answers overworldTab(), which picks
-- between two posters of the same ground by what the seed put in the pool, and
-- on the ordinary incentive-only seed -- and on both NOverworld variants,
-- whatever the pool says -- that leaf is "Incentive Locations". Every door back
-- out to the overworld would have read "-> Incentive Locations", which is the
-- right answer to "which tab does clicking this open" and the wrong one to
-- "where did this door come out". Which is also why navigate() below still
-- asks tabPathForMap: the click wants the tab, the badge wants the map.
--
-- The towns reach overworldTab() by the same route in the pack's own MAP_VALUE,
-- but not here: the pins come from an override, and an override's table names
-- each town's tab outright.
local function mapName(mapId)
  if mapId == nil then
    return nil
  end
  local name = nil
  if mapId ~= -1 then
    local path = tabPathForMap and tabPathForMap(mapId)
    if path then
      for part in string.gmatch(path, "([^/]+)") do
        name = part
      end
    end
  end
  name = name or (MAP_NAMES or {})[mapId]
  if name == nil then
    return nil
  end
  -- One abbreviation step for both sources rather than one per branch. The
  -- fallback used to skip it, which put the widest name the pack can draw --
  -- "TempleOfFiendsRevisitedChaos", 166.6px against a 102px slot -- on the one
  -- path nothing was checking.
  return BADGE_SHORT[name] or name
end

local function badgeText(row)
  local fwd = mapName(row.fwdMap)
  local rev = mapName(row.revMap)
  if fwd and rev then
    -- One line where both ends are the same map, which is what a two-way door
    -- looks like from here, and two where they are not -- a seed with the
    -- directions decoupled, and a staircase whose halves land on different
    -- floors.
    if row.fwdMap == row.revMap then
      return ARROW_BOTH .. fwd
    end
    return ARROW_FWD .. fwd .. "\n" .. ARROW_REV .. rev
  elseif fwd then
    return ARROW_FWD .. fwd
  elseif rev then
    return ARROW_REV .. rev
  end
  return ""
end

local function redraw(row)
  local item = row.item
  local text = badgeText(row)
  item.BadgeText = text
  if text ~= "" then
    item.BadgeTextColor = "#ffd700"
  end
  if type(item.SetOverlayBackground) == "function" then
    item:SetOverlayBackground("#c0000000")
    item:SetOverlayFontSize(10)
    item:SetOverlayAlign("left")
  end
end

-- The frame handler's own argument is where the seconds come from, and it has
-- to be: os.clock() is process CPU time, and PopTracker spends most of an idle
-- second in the compositor rather than in Lua, so a five-CPU-second deadline
-- arrives tens of wall seconds after the click. That is harmless where
-- autotracking.lua times its board reassert -- firing late still catches the
-- restore -- and it is the visible symptom here, since the thing being timed is
-- a gold pin somebody is looking at. PopTracker passes wall seconds since this
-- handler last ran (scripthost.cpp:516-522), documented since 0.25.9 and so
-- well under the pack's floor, and accumulating them is exact.
function removeEntranceHighlight(elapsed)
  HIGHLIGHT_ELAPSED = HIGHLIGHT_ELAPSED + (type(elapsed) == "number" and elapsed or 0)
  if HIGHLIGHT_ELAPSED < HIGHLIGHT_SECONDS then
    return
  end
  ScriptHost:RemoveOnFrameHandler("entrance highlight")
  if HIGHLIGHT_SECTION then
    HIGHLIGHT_SECTION.Highlight = Highlight.None
  end
  HIGHLIGHT_SECTION = nil
  HIGHLIGHT_ELAPSED = 0
end

-- Tab to where a door goes and light the pin at the far end for a moment.
--
-- Priority rather than Avoid, which is what the pack this idea came from used:
-- the two are a colour each and PopTracker's defaults make Avoid red and
-- Priority gold (mapwidget.cpp:54-60). Red on the pin you were just sent to
-- reads as a warning about it.
--
-- The far end is often not a pin at all: entering a town lands the party on a
-- plain tile inside its border, and only the way back out departs from one. So
-- the tab is the answer that always works and the highlight is the bonus, which
-- is the same split edges.lua makes when it marks.
local function navigate(mapId, path)
  if mapId == nil then
    return false
  end
  local tab = tabPathForMap and tabPathForMap(mapId)
  if tab then
    activateTabPath(tab)
  end
  if path and Highlight then
    local sec = Tracker:FindObjectForCode(path)
    if sec then
      if HIGHLIGHT_SECTION then
        HIGHLIGHT_SECTION.Highlight = Highlight.None
      end
      sec.Highlight = Highlight.Priority
      HIGHLIGHT_SECTION = sec
      HIGHLIGHT_ELAPSED = 0
      if type(ScriptHost.AddOnFrameHandler) == "function" then
        ScriptHost:AddOnFrameHandler("entrance highlight", removeEntranceHighlight)
      end
    end
  end
  return tab ~= nil
end

-- One item per pin, in a fixed order.
--
-- Sorted rather than left to pairs() because a LuaItem's id falls back to its
-- creation order on a host too old for stable ids (tracker.cpp:1434-1438), and
-- a set of items whose order moved between two runs of the same cartridge would
-- restore onto each other. On a current host the id is
-- "<type>:<name>@<hash of the source filename>", so the names being unique per
-- pin is what makes them stable, and this file being its own is what keeps
-- uat.lua's five untouched.
function buildEntranceItems()
  ENTRANCE_ITEMS = {}
  local paths = {}
  for path in pairs(ENTRANCE_PINS or {}) do
    paths[#paths + 1] = path
  end
  if #paths == 0 then
    return 0
  end
  if type(ScriptHost.CreateLuaItem) ~= "function" then
    print("entrances: no ScriptHost:CreateLuaItem -- the door pins cannot say "
      .. "where they lead on this host")
    return 0
  end
  table.sort(paths)
  local made = 0
  for _, path in ipairs(paths) do
    local pin = ENTRANCE_PINS[path]
    local ok, item = pcall(function() return ScriptHost:CreateLuaItem() end)
    if not ok or not item then
      print("entrances: could not create the badge for " .. path)
    else
      local row = { item = item, code = pin.code, map = pin.map,
                    name = pin.name, path = path }
      item.Name = pin.name
      -- Set once and never again: the cell is a text field and its picture is
      -- the transparent plate that lets the text draw at all.
      item.Icon = DOOR_BADGE_ICON
      -- Both ways of saying the same thing, because there are 178 of these.
      --
      -- Tracker::ProviderCountForCode pcalls every LuaItem's
      -- CanProvideCodeFunc unless PotentialCodes is set, and clears its cache
      -- on every item change (tracker.cpp:605-612, luaitem.cpp:208-209). The
      -- pack had four such items before this file; with a closure each, these
      -- pins would put 178 pcalls behind every code re-resolved on every tick
      -- that flips an item. PotentialCodes answers the same question from a
      -- list in C++ and never enters Lua at all.
      --
      -- It needs 0.35.4 and the pack's floor is 0.35.1 (manifest.json), so the
      -- closure stays as the fallback rather than raising that floor over a
      -- performance fix. Set under pcall rather than gated on a version string:
      -- an older host is one that refuses the assignment, which is exactly what
      -- pcall is for, and a host that accepts it stops calling the closure.
      pcall(function() item.PotentialCodes = { row.code } end)
      item.CanProvideCodeFunc = function(_, code)
        return code == row.code
      end
      item.ProvidesCodeFunc = function(_, code)
        return code == row.code and 1 or 0
      end
      item.OnLeftClickFunc = function()
        navigate(row.fwdMap, row.fwdPath)
      end
      item.OnRightClickFunc = function()
        navigate(row.revMap, row.revPath)
      end
      redraw(row)
      ENTRANCE_ITEMS[path] = row
      made = made + 1
    end
  end
  return made
end

-- Where this door led. `path` is the pin walked out of, `mapId` the map it came
-- out on, and `destPath` the pin at the far end where there is one.
function setEntranceForward(path, mapId, destPath)
  local row = ENTRANCE_ITEMS[path]
  if not row or (row.fwdMap == mapId and row.fwdPath == destPath) then
    return false
  end
  row.fwdMap, row.fwdPath = mapId, destPath
  redraw(row)
  return true
end

-- And what led here, which is the same edge read from the other end.
function setEntranceReverse(path, mapId, srcPath)
  local row = ENTRANCE_ITEMS[path]
  if not row or (row.revMap == mapId and row.revPath == srcPath) then
    return false
  end
  row.revMap, row.revPath = mapId, srcPath
  redraw(row)
  return true
end

-- Every badge back to blank. The caller is the cartridge swap and the reset in
-- edges.lua: a different seed is a different permutation, and a badge left over
-- from the last one is worse than no badge at all.
function clearEntranceNames()
  local cleared = 0
  for _, row in pairs(ENTRANCE_ITEMS) do
    if row.fwdMap ~= nil or row.revMap ~= nil then
      row.fwdMap, row.fwdPath, row.revMap, row.revPath = nil, nil, nil, nil
      redraw(row)
      cleared = cleared + 1
    end
  end
  return cleared
end

buildEntranceItems()
