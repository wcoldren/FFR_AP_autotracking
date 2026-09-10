-- The hints Archipelago publishes, and where each one lands on this board.
--
-- The channel is data storage, not the scout handler: "_read_hints_<team>_<slot>"
-- is what the server keeps hints under and what its own client watches. These
-- rows are the parse, the filter and the message; tests/test_highlights.lua owns
-- what the resulting claim does to a pin.
local PACK = arg[1]
local json = dofile(PACK .. "/tests/json.lua")
local ItemModel = dofile(PACK .. "/tests/item_model.lua")

local byCode = ItemModel.loadPack(json, PACK, {
  "items/items.json", "items/hosted_items.json",
  "items/flags.json", "items/shards.json",
})

Tracker = {
  BulkUpdate = false,
  ActiveVariantUID = "5standard",
  FindObjectForCode = function(_, code) return byCode[code] end,
  UiHint = function() end,
}
local frameHandlers = {}
ScriptHost = {
  LoadScript = function(_, path) dofile(PACK .. "/" .. path) end,
  AddVariableWatch = function() end,
  AddOnFrameHandler = function(_, name, fn) frameHandlers[name] = fn end,
  RemoveOnFrameHandler = function(_, name) frameHandlers[name] = nil end,
}

local asked = { get = {}, notify = {} }
Archipelago = {
  AddClearHandler = function() end,     AddItemHandler = function() end,
  AddLocationHandler = function() end,  AddSetReplyHandler = function() end,
  AddRetrievedHandler = function() end,
  PlayerNumber = 3,
  TeamNumber = 0,
  Get = function(_, keys) asked.get[#asked.get + 1] = keys[1] end,
  SetNotify = function(_, keys) asked.notify[#asked.notify + 1] = keys[1] end,
  -- The real host answers for any id, checked or not, which is the whole reason
  -- a hint can be named at all. These are worlds/ff1/data/locations.json's own
  -- names for the two ids below.
  GetLocationName = function(_, id, game)
    if game ~= AP_GAME_NAME then return nil end
    return ({ [275] = "Northwest Castle - Treasury 2",
              [257] = "Coneria Castle - Ground Floor Treasury 1",
              [401] = "DeepDungeon29B_Chest146" })[id]
  end,
}

-- The host's own values (locationsection.h:12-18).
Highlight = { Avoid = -1, None = 0, NoPriority = 1, Unspecified = 2, Priority = 3 }

dofile(PACK .. "/scripts/logic.lua")
-- Before autotracking, which loads hints.lua, which registers its scope as it
-- loads -- the same order init.lua puts them in.
dofile(PACK .. "/scripts/highlights.lua")
dofile(PACK .. "/scripts/autotracking.lua")

local counts = {}
for _, v in pairs(LOCATION_MAPPING) do
  if v[1] then counts[v[1]] = (counts[v[1]] or 0) + 1 end
end
for path, n in pairs(counts) do
  -- Highlight present and None, which is what a real section reads: the registry
  -- treats a nil read as a host that will not accept the write either.
  byCode[path] = { ChestCount = n, AvailableChestCount = n,
                   Highlight = Highlight.None }
end

local fail = 0
local function check(label, got, want)
  local ok = got == want
  if not ok then fail = fail + 1 end
  print(string.format("%s %-56s %s", ok and "ok  " or "FAIL", label, tostring(got)))
  if not ok then print(string.format("     wanted %s", tostring(want))) end
end

local said = {}
local realPrint = print
local function capture(fn)
  said = {}
  print = function(line) said[#said + 1] = tostring(line) end
  local a, b = fn()
  print = realPrint
  return a, b
end
local function saidSomething(needle)
  for _, line in ipairs(said) do
    if line:find(needle, 1, true) then return true end
  end
  return false
end

-- The transposed pair, verified from both sides: worlds/ff1/data/locations.json
-- names 275 "Northwest Castle - Treasury 2" while LOCATION_MAPPING gives it
-- "North West Castle Chests 3".
local TREASURY = 275
local CHEST = 257            -- "@Coneria Castle Chests 1/Chest"
local DEEP_DUNGEON = 401     -- in the AP world, in no mapping here

local function hint(id, opts)
  opts = opts or {}
  return {
    location = id,
    finding_player = opts.finder or Archipelago.PlayerNumber,
    receiving_player = 1,
    item = 1,
    found = opts.found or false,
    status = opts.status or 0,
  }
end

------------------------------------------------------------------
print("-- the key")
------------------------------------------------------------------
check("the key names the team and the slot", hintsKey(), "_read_hints_0_3")
Archipelago.TeamNumber = nil
check("a host that will not say the team assumes 0", hintsKey(), "_read_hints_0_3")
Archipelago.TeamNumber = 0
Archipelago.PlayerNumber = -1
check("and no slot means no key", hintsKey(), nil)
Archipelago.PlayerNumber = 3

------------------------------------------------------------------
print("\n-- subscribing, on connect")
------------------------------------------------------------------
capture(onClear)
check("onClear asks for the hints that already stand", asked.get[1], "_read_hints_0_3")
check("and to be told about the later ones", asked.notify[1], "_read_hints_0_3")
check("  neither more than once", #asked.get + #asked.notify, 2)

------------------------------------------------------------------
print("\n-- the key is the discriminator")
------------------------------------------------------------------
-- Both handlers were registered long before anything was subscribed, and both
-- funnelled everything into activateMapTab. A hints payload arriving there is
-- what the dispatch prevents.
local lit = capture(function() return onNotify("_read_hints_0_3", { hint(TREASURY) }) end)
check("a hints payload is read as hints", lit, 1)
check("another key is not", onNotify("ff1/something", 13), nil)
check("and a table on another key is dropped rather than read as a map",
  onNotify("ff1/something", { 1, 2 }), nil)

------------------------------------------------------------------
print("\n-- what the payload may be")
------------------------------------------------------------------
-- nil gets its own row rather than a place in the table below, because a table
-- constructor with a nil value stores no key: `["nil"] = nil` made a row that
-- read as covered and never ran, and the loop it sat in printed two lines where
-- somebody counting would have read three. It is also the case onHints' own
-- comment singles out -- a Get on a key the room has never written answers null
-- -- so it was the one branch the comment justifies and nothing exercised.
check("  nil is a quiet no-op", capture(function() return onHints(nil) end), 0)
for label, value in pairs({ ["a string"] = "x", ["a number"] = 7 }) do
  local n = capture(function() return onHints(value) end)
  check("  " .. label .. " is a quiet no-op", n, 0)
end
check("an empty list is too", capture(function() return onHints({}) end), 0)
local n = capture(function()
  return onHints({ "not a table", hint(TREASURY), { location = "x" } })
end)
check("a malformed row does not stop the ones beside it", n, 1)
check("a row with no status is still live",
  capture(function() return onHints({ { location = CHEST, finding_player = 3 } }) end), 1)

------------------------------------------------------------------
print("\n-- whose board it is on")
------------------------------------------------------------------
local live, elsewhere = capture(function()
  return onHints({ hint(TREASURY), hint(CHEST, { finder = 9 }) })
end)
check("only the hints this slot has to find count", live, 1)
check("  and the rest are counted as somebody else's", elsewhere, 1)

------------------------------------------------------------------
print("\n-- found is not live")
------------------------------------------------------------------
check("a hint the server marked found is not live",
  capture(function() return onHints({ hint(TREASURY, { status = 40 }) }) end), 0)
check("nor one an older server only flagged as found",
  capture(function() return onHints({ hint(TREASURY, { found = true }) }) end), 0)

------------------------------------------------------------------
print("\n-- the message")
------------------------------------------------------------------
resetHints()
capture(function() return onHints({ hint(TREASURY) }) end)
check("a new hint says Archipelago's name",
  saidSomething("Northwest Castle - Treasury 2"), true)
check("  and this board's", saidSomething("North West Castle Chests 3"), true)
check("  and where to look", saidSomething("Other/Northwest Castle"), true)
check("  not the number that reads alike", saidSomething("Chests 2"), false)

-- The server sends the whole list every time it changes, so without this every
-- rebroadcast would reprint every standing hint.
capture(function() return onHints({ hint(TREASURY) }) end)
check("a rebroadcast of the same hint says nothing again", #said, 0)

capture(function() return onHints({}) end)
capture(function() return onHints({ hint(TREASURY) }) end)
check("but a hint that left and came back is new again",
  saidSomething("North West Castle Chests 3"), true)

------------------------------------------------------------------
print("\n-- a location this board has no pin for")
------------------------------------------------------------------
-- The twelve Deep Dungeon ids the AP world carries and LOCATION_MAPPING does
-- not. Named rather than numbered, because somebody is reading a hint that says
-- the name.
resetHints()
local n2 = capture(function()
  return onHints({ hint(DEEP_DUNGEON), hint(TREASURY) })
end)
check("it is not counted as live", n2, 1)
check("  and it says so", saidSomething("no pin on this board"), true)
capture(function() return onHints({ hint(DEEP_DUNGEON) }) end)
check("  once, not every rebroadcast", saidSomething("no pin on this board"), false)

------------------------------------------------------------------
print("\n-- a different slot")
------------------------------------------------------------------
resetHints()
check("reset forgets the key", hintsKey() ~= nil and isHintsKey("_read_hints_0_3"), true)
capture(function() return onHints({ hint(TREASURY) }) end)
check("and a hint after it is new again",
  saidSomething("North West Castle Chests 3"), true)

------------------------------------------------------------------
print("\n-- a host that cannot name a location")
------------------------------------------------------------------
-- Only GetLocationName can name a location nobody has checked. Without it the
-- line still has to say something, or the hint the player is reading has no
-- answer at all.
resetHints()
local savedGetter = Archipelago.GetLocationName
Archipelago.GetLocationName = nil
capture(function() return onHints({ hint(TREASURY) }) end)
check("the board's name and tab are still said",
  saidSomething("North West Castle Chests 3"), true)
check("  with the id standing in for Archipelago's", saidSomething("location 275"), true)
Archipelago.GetLocationName = savedGetter

------------------------------------------------------------------
print("\n-- the pin, and what colour")
------------------------------------------------------------------
local TREASURY_PATH = LOCATION_MAPPING[TREASURY][1]
local function lit(path) return byCode[path].Highlight end

resetHints()
capture(function() return onHints({ hint(TREASURY) }) end)
check("a hint lights its pin", lit(TREASURY_PATH), Highlight.Unspecified)
check("  and the hint owns it", highlightOwnerOf(TREASURY_PATH), "hint")

-- HintStatus is Highlight, colour for colour, so a hint AP says to avoid must
-- not read as one it says to chase.
for status, want in pairs({ [30] = Highlight.Priority, [20] = Highlight.Avoid,
                            [10] = Highlight.NoPriority,
                            [0] = Highlight.Unspecified }) do
  capture(function() return onHints({ hint(TREASURY, { status = status }) }) end)
  check("  status " .. status .. " paints its own colour", lit(TREASURY_PATH), want)
end

-- The status AP has not added yet. HintStatus has grown once already, and the
-- fallback is reached by every value it grows next -- so what it paints is a
-- decision rather than a detail. Unspecified says "a hint stands here" without
-- claiming to know how loudly; gold would say chase this, about a statement
-- nothing in this pack has read.
capture(function() return onHints({ hint(TREASURY, { status = 25 }) }) end)
check("  a status this pack does not know is not gold",
  lit(TREASURY_PATH), Highlight.Unspecified)

-- The three ways a hint stops standing.
capture(function() return onHints({ hint(TREASURY, { status = 40 }) }) end)
check("a found hint puts its pin out", lit(TREASURY_PATH), Highlight.None)

capture(function() return onHints({ hint(TREASURY) }) end)
capture(function() return onHints({}) end)
check("a hint that left the payload puts its pin out", lit(TREASURY_PATH), Highlight.None)

capture(function() return onHints({ hint(TREASURY) }) end)
check("  and a check puts it out before the server says so",
  hintChecked(TREASURY) and lit(TREASURY_PATH), Highlight.None)

-- Two hints on one pin. No two ids share a section path in the shipped mapping
-- today, but the shape allows it -- reconcile.lua indexes path to a *list* of
-- ids for exactly that reason -- so the pair is synthesised rather than found,
-- which is also what keeps this row from going quiet if the data changes.
resetHints()
local SHARED = LOCATION_MAPPING[CHEST][1]
local TWIN = 9001
LOCATION_MAPPING[TWIN] = { SHARED }

capture(function()
  return onHints({ hint(CHEST), hint(TWIN, { status = 30 }) })
end)
check("two hints on one pin take the stronger colour",
  lit(SHARED), Highlight.Priority)
capture(function() return onHints({ hint(CHEST) }) end)
check("  and the pin stays lit while either stands",
  lit(SHARED), Highlight.Unspecified)
capture(function() return onHints({}) end)
check("  going dark only when both are gone", lit(SHARED), Highlight.None)
LOCATION_MAPPING[TWIN] = nil

-- A reconnect to another slot must not carry the last one's gold over.
capture(function() return onHints({ hint(TREASURY) }) end)
resetHints()
check("reset puts out everything the hints held", lit(TREASURY_PATH), Highlight.None)

print("")
if fail > 0 then
  print(string.format("%d FAILED", fail))
  os.exit(1)
end
print("ALL PASS")
