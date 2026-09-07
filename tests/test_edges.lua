-- ff1/edges, drawn onto the entrance pins.
--
-- The board is where this has to be checked rather than the parser, because
-- the interesting cases are all about which pin a raw tile belongs to. A pin
-- is named for the middle of its cluster and a party walks onto whichever tile
-- of a five-tile doorway it reached, so the tile observed and the tile named
-- disagree most of the time; ENTRANCE_LINKS is what puts them back together and
-- these rows are what say it is being consulted.
local PACK = arg[1]
local popapi = dofile(PACK .. "/tests/pop_api.lua")

-- Four pins. The Coneria door is a three-tile blob on the overworld, the way
-- out of the map below it is a two-tile doorway, and the two staircases are
-- single tiles -- which is the whole spread the real table carries.
local DOOR = "@Entrances/Entrance: Coneria/Coneria"
local WAY_OUT = "@Entrances/Entrance: ConeriaTown S Downstairs/ConeriaTown S Downstairs"
local STAIR_UP = "@Entrances/Entrance: MarshCaveB1 NW Downstairs/MarshCaveB1 NW Downstairs"
local STAIR_DOWN = "@Entrances/Entrance: MarshCaveB2 SE Downstairs/MarshCaveB2 SE Downstairs"

ENTRANCE_LINKS = {
  ["-1,152,161"] = DOOR, ["-1,153,161"] = DOOR, ["-1,152,162"] = DOOR,
  ["1,7,15"] = WAY_OUT, ["1,8,15"] = WAY_OUT,
  ["5,11,3"] = STAIR_UP,
  ["6,5,29"] = STAIR_DOWN,
}

-- A section is its two counts and nothing else: AvailableChestCount is what
-- PopTracker lets a script write (locationsection.cpp:262-294) and ChestCount
-- is what it reads back, so a mark is one and un-marking is the other.
local SECTIONS = {}
local function section(path)
  if not SECTIONS[path] then
    SECTIONS[path] = { ChestCount = 1, AvailableChestCount = 1 }
  end
  return SECTIONS[path]
end
for _, path in pairs(ENTRANCE_LINKS) do section(path) end

-- Nesting BulkUpdate wrongly is the hazard here: clearEntranceMarks runs
-- inside reconcile's own batch, so an inner `= false` would end the outer one.
-- Counting it means nothing may be rawset onto the mock -- a plain assignment
-- would leave the key present and __newindex would stop firing after the first.
local bulk = 0
Tracker = popapi.strict("Tracker", {
  FindObjectForCode = function(_, code) return SECTIONS[code] end,
})
local strictIndex = getmetatable(Tracker).__index
setmetatable(Tracker, {
  __index = strictIndex,
  __newindex = function(_, k, v)
    if k == "BulkUpdate" then bulk = bulk + (v and 1 or -1) end
  end,
})
ScriptHost = popapi.strict("ScriptHost", {
  AddVariableWatch = function(_, name, vars) WATCH = { name = name, vars = vars } end,
})

local fail = 0
local function check(label, got, want)
  local ok = got == want
  if not ok then fail = fail + 1 end
  print(string.format("%s %-52s %s", ok and "ok  " or "FAIL", label, tostring(got)))
  if not ok then print(string.format("     wanted %s", tostring(want))) end
end

-- Returns what the call returned, with its warning kept off the transcript --
-- the warning is the point of the row below, not noise to be read here.
local function quiet(fn, ...)
  local realPrint = print
  print = function() end
  local ok, res = pcall(fn, ...)
  print = realPrint
  if not ok then error(res, 0) end
  return res
end

local function walked(path)
  return SECTIONS[path].AvailableChestCount == 0
end

local function reset()
  for _, sec in pairs(SECTIONS) do sec.AvailableChestCount = 1 end
  EDGES_ROM, EDGES_SOURCE = nil, nil
end

-- The naming half, stubbed. What edges.lua owes it is the two ends of the
-- record it just marked from -- tests/test_entrance_items.lua owns what the
-- badge then says, and a stub here keeps the two files from asserting the same
-- thing twice.
local named = {}
function setEntranceForward(path, mapId, destPath)
  named[#named + 1] = { "fwd", path, mapId, destPath }
  return true
end
function setEntranceReverse(path, mapId, srcPath)
  named[#named + 1] = { "rev", path, mapId, srcPath }
  return true
end
local function namings()
  local out = {}
  for _, n in ipairs(named) do
    out[#out + 1] = table.concat({ n[1], n[2], tostring(n[3]),
                                   tostring(n[4]) }, " ")
  end
  return table.concat(out, "; ")
end

dofile(PACK .. "/scripts/autotracking/edges.lua")

local OW_TO_TOWN = "-1,153,161,1,7,16"
local TOWN_TO_OW = "1,8,15,-1,152,162"
local STAIRS = "5,11,3,6,5,29"

------------------------------------------------------------------
print("-- the watch it registers")
------------------------------------------------------------------

check("it takes its own watch", WATCH and WATCH.name, "ff1edges")
check("and asks for the log", WATCH.vars[1], "ff1/edges")
-- The cartridge rides along because the marks belong to one permutation, and
-- an edge log has no other way to notice a swap.
check("and for the cartridge", WATCH.vars[2], "ff1/rom")

------------------------------------------------------------------
print("\n-- where the board starts")
------------------------------------------------------------------

check("every door starts shut", walked(DOOR), false)
check("no variable is not a change", applyFFREdges(nil, nil), false)
check("and leaves the doors shut", walked(DOOR), false)
check("an empty log is not a change either", applyFFREdges("", "romA"), false)

------------------------------------------------------------------
print("\n-- a door that was walked through")
------------------------------------------------------------------

reset()
check("one record moves the board", applyFFREdges(OW_TO_TOWN, "romA"), true)
-- 153,161 is not the tile the pin is named after -- 152,161 is -- so this row
-- fails the moment the cluster table stops being consulted.
check("the door is marked from a tile it does not name", walked(DOOR), true)
-- The town's arrival tile carries no pin, which is the ordinary case: a party
-- entering a town lands inside the border, not on it.
check("an arrival with no pin marks nothing", walked(WAY_OUT), false)
check("re-sending the same record is not a change",
  applyFFREdges(OW_TO_TOWN, "romA"), false)

-- And the badge is told the same walk. Only the departure end is named here,
-- because only it has a pin -- the arrival's map id still travels, which is
-- what the badge actually prints.
reset()
named = {}
applyFFREdges(OW_TO_TOWN, "romA")
check("the walk names the door it left from", namings(),
  "fwd " .. DOOR .. " 1 nil")

-- A staircase is the case where both ends carry a pin, so both get named and
-- in opposite directions: the one you left says where it led, the one you
-- arrived on says what led there.
reset()
named = {}
applyFFREdges(STAIRS, "romA")
check("a staircase names both of its ends", namings(),
  "fwd " .. STAIR_UP .. " 6 " .. STAIR_DOWN
  .. "; rev " .. STAIR_DOWN .. " 5 " .. STAIR_UP)

------------------------------------------------------------------
print("\n-- the way back out is its own door")
------------------------------------------------------------------

check("the reverse marks the border tile",
  applyFFREdges(OW_TO_TOWN .. ";" .. TOWN_TO_OW, "romA"), true)
check("the way out is walked", walked(WAY_OUT), true)
check("and the door it leads to stays walked", walked(DOOR), true)

------------------------------------------------------------------
print("\n-- a staircase, where both ends carry a pin")
------------------------------------------------------------------

reset()
check("both ends of a staircase mark", applyFFREdges(STAIRS, "romA"), true)
check("the stair walked down", walked(STAIR_UP), true)
check("and the one walked up to", walked(STAIR_DOWN), true)

------------------------------------------------------------------
print("\n-- what it refuses")
------------------------------------------------------------------

reset()
-- Exit and Warp move the party between maps without a door. Neither departs
-- from a staircase, so the tile carries no pin and the record is dropped here.
check("an edge from no pin at all marks nothing",
  applyFFREdges("5,40,40,6,41,41", "romA"), false)
check("and nothing else moved", walked(STAIR_UP), false)

check("a malformed record is not a change",
  quiet(applyFFREdges, "5,11,3,6;nonsense", "romA"), false)
check("and leaves the board alone", walked(STAIR_UP), false)

-- A good record beside a bad one is still applied: the log is one string and
-- refusing all of it over one line would lose doors that were really walked.
check("a good record beside a bad one still marks",
  quiet(applyFFREdges, "nonsense;" .. STAIRS, "romA"), true)
check("the good half took", walked(STAIR_UP), true)

------------------------------------------------------------------
print("\n-- the pack with no override, which is what shipped inert")
------------------------------------------------------------------

-- The table is empty in the committed pack and written by a regen, so a
-- tracker with no override marks nothing. That is correct -- it has no
-- entrance pins either -- but it looked exactly like a wired-up board that
-- happened not to be marking, because an empty table has no path that can fail
-- to resolve and nothing else said a word. It says one now, once.
reset()
local saved = ENTRANCE_LINKS
ENTRANCE_LINKS = {}
local said = {}
local realPrint = print
print = function(msg) said[#said + 1] = msg end
applyFFREdges(STAIRS, "romA")
applyFFREdges(STAIRS .. ";" .. OW_TO_TOWN, "romA")
print = realPrint
ENTRANCE_LINKS = saved

check("an empty table says so when a door is reported", #said, 1)
check("  and names the file to regenerate",
  said[1] and said[1]:find("entrance_links.lua", 1, true) ~= nil, true)

-- Not on a board that has simply not walked anywhere yet: an empty log through
-- an empty table is two kinds of nothing, and warning there would fire on every
-- Archipelago-only session.
ENTRANCE_LINKS = {}
said = {}
print = function(msg) said[#said + 1] = msg end
applyFFREdges("", "romB")
print = realPrint
ENTRANCE_LINKS = saved
check("but stays quiet when no door has been walked", #said, 0)

------------------------------------------------------------------
print("\n-- a cartridge swap")
------------------------------------------------------------------

reset()
applyFFREdges(STAIRS, "romA")
check("the first cartridge's doors are open", walked(STAIR_UP), true)
check("the second cartridge's log applies",
  applyFFREdges(OW_TO_TOWN, "romB"), true)
-- A different cartridge is a different permutation, and a stair left open from
-- the previous seed would be an answer nobody has earned on this one.
check("and the first cartridge's doors are shut again", walked(STAIR_UP), false)
check("while the new one's is open", walked(DOOR), true)

-- Coming to a board with no memo is not a swap. PopTracker has just restored
-- whatever was saved, and checkRom is what decides whether it belongs here.
reset()
SECTIONS[STAIR_UP].AvailableChestCount = 0
applyFFREdges(OW_TO_TOWN, "romA")
check("a first sighting does not clear the restored board",
  walked(STAIR_UP), true)

------------------------------------------------------------------
print("\n-- resetForNewGame's hook")
------------------------------------------------------------------

-- reconcile calls this, and the two feeds reach a cartridge swap in an order
-- PopTracker does not define. So it re-applies rather than only clearing: the
-- record it holds is whichever cartridge the edge watch has already seen.
reset()
applyFFREdges(STAIRS, "romA")
SECTIONS[DOOR].AvailableChestCount = 0
clearEntranceMarks()
check("the hook keeps what the log says", walked(STAIR_UP), true)
check("and drops what it does not", walked(DOOR), false)

check("bulk updates are balanced", bulk, 0)

print(fail == 0 and "\nALL PASS" or string.format("\n%d FAILURE(S)", fail))
os.exit(fail == 0 and 0 or 1)
