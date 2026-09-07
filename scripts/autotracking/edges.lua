-- ff1/edges, drawn onto the entrance pins.
--
-- The pins say a door is here. Which door leads where is the shuffled half, and
-- it is deliberately not read off the cartridge: a tracker told the permutation
-- up front spoils an entrance-randomised seed before the first town. So the
-- bridge watches the party walk instead and publishes what it saw --
--
--   <from map>,<from col>,<from row>,<to map>,<to col>,<to row>[;...]
--
-- with -1 for the overworld, the same value ff1/map uses. Each record is one
-- door somebody has actually been through, so acting on it can reveal nothing
-- that has not already been seen from inside the game.
--
-- What this does with them is mark the pin standing on the tile the door was
-- entered from, which is what the open-door icon has meant since it landed --
-- except that until now "I have been in here" was a click.
--
-- Both ends are looked up, and only one of them usually resolves. Entering a
-- town lands the party on a plain tile inside the border, which carries no pin;
-- the way back out departs from a border warp tile, which does. So each
-- direction marks itself from its own departure, and the arrival lookup is the
-- bonus that fires on a dungeon staircase, where both ends really are teleport
-- tiles.
--
-- ENTRANCE_LINKS resolves a tile to a pin and comes from scripts/entrance_links.lua,
-- which a regen writes into the override; the copy the pack ships is empty. It
-- has to exist because a pin does not always sit on the tile that was walked --
-- a doorway is as wide as the art draws it and a town is a blob of tiles, and
-- both collapse to one marker. tools/regen_maps.build_entrance_links has the
-- rest of the reasoning.

-- The cartridge these marks belong to, and the record they were made from. Both
-- nil means nothing has been seen yet, which is where a fresh tracker starts
-- and is not the same as a cartridge that has published an empty log.
EDGES_ROM = nil
EDGES_SOURCE = nil

local MISSING_WARNED = {}
local EMPTY_WARNED = false

-- Every distinct pin ENTRANCE_LINKS knows about. Several tiles share a pin, so
-- this is not the key set.
local function entranceSections()
  local paths = {}
  for _, path in pairs(ENTRANCE_LINKS or {}) do
    paths[path] = true
  end
  return paths
end

local function sectionFor(path)
  local obj = Tracker:FindObjectForCode(path)
  if obj then
    return obj
  end
  -- A table written by a regen against location trees that have since moved.
  -- Warned once each rather than per record: the log republishes in full on
  -- every reconnect, so a per-call print would be a wall of them.
  if not MISSING_WARNED[path] then
    MISSING_WARNED[path] = true
    print("edges: no entrance section at " .. path)
  end
  return nil
end

-- Marks the pin standing on one tile, if a pin stands on it at all. An edge
-- whose departure carries no pin is dropped here and that is the filter: Exit
-- and Warp move the party between maps without a door, and neither of them
-- leaves from a staircase.
local function markTile(map, col, row)
  local path = (ENTRANCE_LINKS or {})[string.format("%d,%d,%d", map, col, row)]
  if not path then
    return false
  end
  local sec = sectionFor(path)
  -- One way only, the rule reconcile.applyHostedItem already states: a player
  -- who cleared a door by hand is not fought, and nothing here un-walks one.
  if not sec or sec.AvailableChestCount == 0 then
    return false
  end
  sec.AvailableChestCount = 0
  return true
end

local function applyRecord(record)
  if type(record) ~= "string" then
    return 0
  end
  -- A pack with no override has an empty table, and that is not an error -- the
  -- entrance pins are not drawn there either. But it is indistinguishable from
  -- a working setup where nothing happens to be marking, because an empty table
  -- has no path to fail to resolve and nothing else says a word. Said once, and
  -- only once the bridge has actually reported a door, so a board that has
  -- simply not walked through one yet stays quiet.
  if record ~= "" and not next(ENTRANCE_LINKS or {}) and not EMPTY_WARNED then
    EMPTY_WARNED = true
    print("edges: the bridge is reporting doors, but no entrance pin knows which "
      .. "tile it stands on -- scripts/entrance_links.lua is empty, which is "
      .. "what a pack with no regenerated override has. Run "
      .. "tools/regen_maps.py on this cartridge to draw the pins and write the "
      .. "table that marks them.")
  end
  local marked, bad = 0, 0
  for rec in record:gmatch("[^;]+") do
    local fm, fc, fr, tm, tc, tr =
        rec:match("^(%-?%d+),(%d+),(%d+),(%-?%d+),(%d+),(%d+)$")
    if not fm then
      bad = bad + 1
    else
      if markTile(tonumber(fm), tonumber(fc), tonumber(fr)) then
        marked = marked + 1
      end
      if markTile(tonumber(tm), tonumber(tc), tonumber(tr)) then
        marked = marked + 1
      end
    end
  end
  if bad > 0 then
    print(string.format("edges: %d record(s) the bridge sent are not edges", bad))
  end
  return marked
end

local function unmarkAll()
  for path in pairs(entranceSections()) do
    local sec = Tracker:FindObjectForCode(path)
    if sec then
      sec.AvailableChestCount = sec.ChestCount
    end
  end
end

-- Called by reconcile.resetForNewGame, and it re-applies rather than only
-- clearing because the two feeds reach a cartridge swap in an order PopTracker
-- does not define. If the edge watch has already seen the new cartridge then
-- EDGES_SOURCE is the new cartridge's record and this puts its doors straight
-- back; if it has not, the record here is the previous cartridge's and the
-- watch corrects it a moment later, because it notices the swap for itself.
--
-- No BulkUpdate: the one caller is already inside one.
function clearEntranceMarks()
  unmarkAll()
  applyRecord(EDGES_SOURCE)
end

-- Returns whether anything on the board moved.
function applyFFREdges(record, rom)
  -- A different cartridge is a different permutation, so its doors start shut.
  -- EDGES_ROM nil is a first sighting rather than a change -- the board on
  -- screen is whatever PopTracker restored, and checkRom is what decides
  -- whether that belongs to this cartridge.
  if type(rom) == "string" and rom ~= "" then
    if EDGES_ROM ~= nil and rom ~= EDGES_ROM then
      Tracker.BulkUpdate = true
      unmarkAll()
      Tracker.BulkUpdate = false
      EDGES_SOURCE = nil
    end
    EDGES_ROM = rom
  end
  if record == EDGES_SOURCE then
    return false
  end
  EDGES_SOURCE = record
  Tracker.BulkUpdate = true
  local marked = applyRecord(record)
  Tracker.BulkUpdate = false
  if marked > 0 and AUTOTRACKER_ENABLE_DEBUG_LOGGING then
    print(string.format("edges: %d entrance pin(s) marked from the walk", marked))
  end
  return marked > 0
end

function onFF1Edges(store)
  applyFFREdges(store:ReadVariable("ff1/edges"), store:ReadVariable("ff1/rom"))
end

-- Its own watch rather than joining ff1mem's, the way ff1/map has its own and
-- for the same reason maptab.lua gives: this moves every time the party steps
-- through a door, and sharing that callback would run the 256-byte flag decode
-- on every doorway.
if ScriptHost.AddVariableWatch then
  ScriptHost:AddVariableWatch("ff1edges", { "ff1/edges", "ff1/rom" }, onFF1Edges)
end
