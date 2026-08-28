local PACK = arg[1]
AUTOTRACKER_ENABLE_DEBUG_LOGGING = false

local PopApi = dofile(PACK .. "/tests/pop_api.lua")

local objects = {}
-- LuaItems, the way PopTracker hands them out: a bare table the pack fills in
-- with Name/Icon/callbacks. Kept so the tests can find them by the code they
-- claim, which is how a layout finds them too (tracker.cpp:663).
local luaItems = {}
-- Both globals are strict: a name PopTracker does not put on this object raises
-- rather than reading as nil. Without that, calling a ScriptHost method on
-- Tracker just looks like an old host to the pack's feature checks and the
-- feature disables itself in silence -- which is the bug this file missed.
Tracker = PopApi.strict("Tracker", {
  BulkUpdate = false,
  FindObjectForCode = function(self, c)
    if objects[c] then return objects[c] end
    for _, it in ipairs(luaItems) do
      if it.CanProvideCodeFunc and it.CanProvideCodeFunc(it, c) then return it end
    end
  end,
})

local captured = nil
ScriptHost = PopApi.strict("ScriptHost", {
  AddVariableWatch = function(self,n,vars,cb) captured = {n=n,vars=vars,cb=cb} end,
  -- scripthost.cpp:22 -- CreateLuaItem is ScriptHost's, not Tracker's.
  CreateLuaItem = function(self)
    local it = {}
    luaItems[#luaItems + 1] = it
    return it
  end,
})

dofile(PACK .. "/scripts/autotracking/location_mapping.lua")
local counts, hosted = {}, {}
for id,v in pairs(LOCATION_MAPPING) do
  if v[1] then counts[v[1]]=(counts[v[1]] or 0)+1 end
  if v[2] then hosted[v[2]]=true end
end
for p,n in pairs(counts) do objects[p]={ChestCount=n,AvailableChestCount=n} end
for c in pairs(hosted) do objects[c]={Active=false} end

dofile(PACK .. "/scripts/autotracking/reconcile.lua")
dofile(PACK .. "/scripts/autotracking/ram_mapping.lua")
dofile(PACK .. "/scripts/autotracking/uat.lua")

local fail=0
local function check(name,got,want)
  if got~=want then print(string.format("FAIL %-48s got=%s want=%s",name,tostring(got),tostring(want))); fail=fail+1
  else print(string.format("ok   %-48s %s",name,tostring(got))) end
end

check("watch registered", captured and captured.n, "ff1mem")
check("watches ff1/mem", captured.vars[1], "ff1/mem")
check("watches ff1/ready", captured.vars[2], "ff1/ready")
check("watches ff1/rom", captured.vars[3], "ff1/rom")

-- build a store stub
local function store(ready, mem)
  return { ReadVariable = function(self,name)
    if name=="ff1/ready" then return ready end
    if name=="ff1/mem" then return mem end
  end }
end
-- 768-byte image; the flag array lives at offset 0x200, so flag byte B is
-- element 0x200 + B + 1. Everything below indexes through this helper so a
-- regression in the offset shows up as a test failure, not a silent miss.
local FLAGS_OFF = 0x200
local function blank() local t={} for i=1,768 do t[i]=0 end return t end
local function setflag(t, byte, val) t[FLAGS_OFF + byte + 1] = val end

-- not ready -> nothing happens
local f = blank()
setflag(f, 0x2B, 0x04)                       -- byte 0x2B chest -> id 0x12B = 299
captured.cb(store(false, f))
local sec299 = LOCATION_MAPPING[299][1]
check("not ready leaves section alone", objects[sec299].AvailableChestCount, objects[sec299].ChestCount)

-- ready -> chest marked. AP id 299 is "Matoya's Cave - Chest 1" per worlds/ff1
captured.cb(store(true, f))
check("chest bit 0x04 on byte 0x2B marks id 299", objects[sec299].AvailableChestCount, objects[sec299].ChestCount-1)

-- Same bit written at the WRONG offset (as if FLAGS_OFF were dropped) must do
-- nothing -- this is the off-by-0x200 guard for the ff1/mem migration.
local fwrong = blank()
fwrong[1 + 0x2B] = 0x04
captured.cb(store(true, fwrong))
check("bit at offset 0 is not a flag", objects[sec299].AvailableChestCount, objects[sec299].ChestCount)
captured.cb(store(true, f))

-- idempotent: same state again
captured.cb(store(true, f))
check("same flags twice is a no-op", objects[sec299].AvailableChestCount, objects[sec299].ChestCount-1)

-- event bit on a mapped NPC byte: 0x04 -> id 0x204 = 516 (Bikke)
local f2 = blank()
setflag(f2, 0x04, 0x02)
captured.cb(store(true, f2))
check("event bit on byte 0x04 sets Bikke hosted item", objects[LOCATION_MAPPING[516][2]].Active, true)
check("chest 299 released when flags cleared", objects[sec299].AvailableChestCount, objects[sec299].ChestCount)

-- goal bit: byte 0xFE bit 0x02 is Chaos, the same flag AP's client calls the
-- goal. It is a mapped event now, so it must check exactly id 766 and nothing
-- else -- the chest bit on the same byte is a different location.
local f3 = blank()
setflag(f3, 0xFE, 0x02)
captured.cb(store(true, f3))
check("goal bit is a mapped location", LOCATION_MAPPING[766] ~= nil, true)
check("goal bit checks id 766", UAT_CHECKED[766], true)
check("goal bit sets the chaos item", objects["chaos"].Active, true)
local n=0 for _ in pairs(UAT_CHECKED) do n=n+1 end
check("goal-only frame checks just the goal", n, 1)

-- chest bit on the same byte 0xFE IS a real location (0x1FE = 510)
local f4 = blank()
setflag(f4, 0xFE, 0x04 | 0x02)
captured.cb(store(true, f4))
check("byte 0xFE chest bit marks id 510", UAT_CHECKED[510], true)
check("byte 0xFE event bit marks id 766", UAT_CHECKED[766], true)

-- sparse event bits on untracked bytes are silently ignored
local f5 = blank()
for _,b in ipairs({0x20,0x30,0x40,0x50}) do f5[1+b]=0x02 end
captured.cb(store(true, f5))
local n2=0 for _ in pairs(UAT_CHECKED) do n2=n2+1 end
check("untracked event bytes ignored", n2, 0)

------------------------------------------------------------------
-- ff1/rom: the signal that says "different cartridge". Without it the pack's
-- raise-only halves carried a finished seed into the next one.
------------------------------------------------------------------
local function romStore(ready, mem, rom)
  return { ReadVariable = function(self,name)
    if name=="ff1/ready" then return ready end
    if name=="ff1/mem" then return mem end
    if name=="ff1/rom" then return rom end
  end }
end

-- Build a board that looks like a run in progress: a chest, a hosted NPC, and
-- a RAM-derived item.
local function playedBoard(rom)
  local m = blank()
  setflag(m, 0x2B, 0x04)                     -- chest -> id 299
  setflag(m, 0x04, 0x02)                     -- Bikke -> hosted item
  m[1 + 0x31] = 1                            -- $6031, earth orb lit
  captured.cb(romStore(true, m, rom))
  return m
end

ROM_ID = nil
local mA = playedBoard("romA")
check("first rom id is adopted, not a reset", ROM_ID, "romA")
check("first frame still tracked the chest", objects[sec299].AvailableChestCount, objects[sec299].ChestCount-1)
check("first frame set the hosted item", objects[LOCATION_MAPPING[516][2]].Active, true)

-- Same cartridge: nothing is thrown away.
captured.cb(romStore(true, mA, "romA"))
check("same rom keeps the chest", objects[sec299].AvailableChestCount, objects[sec299].ChestCount-1)
check("same rom keeps the hosted item", objects[LOCATION_MAPPING[516][2]].Active, true)

-- An id the emulator would not give us is not a change.
captured.cb(romStore(true, mA, ""))
check("empty rom id is not a change", ROM_ID, "romA")
captured.cb(romStore(true, mA, nil))
check("absent rom id is not a change", ROM_ID, "romA")
check("and the board is untouched", objects[sec299].AvailableChestCount, objects[sec299].ChestCount-1)

-- Different cartridge, and the bridge has not seen a loaded save on it yet:
-- ready is false, and the mem it re-sends is still the OLD game's. The board
-- must go anyway -- this is the window the whole mechanism exists for.
captured.cb(romStore(false, mA, "romB"))
check("rom change is adopted", ROM_ID, "romB")
check("rom change released the chest", objects[sec299].AvailableChestCount, objects[sec299].ChestCount)
check("rom change cleared the hosted item", objects[LOCATION_MAPPING[516][2]].Active, false)
check("rom change emptied UAT_CHECKED", next(UAT_CHECKED), nil)

------------------------------------------------------------------
-- Same cartridge, new game file. The flag page comes back at
-- lut_InitGameFlags: no chest bit, no event bit. Sections and RAM items would
-- follow on their own, but the hosted codes behind the Incentive Locations
-- pins are one-way, so this needs the same wipe a ROM swap gets.
------------------------------------------------------------------
ROM_ID = nil
local m2 = blank()
setflag(m2, 0x2B, 0x04)
setflag(m2, 0x04, 0x02)
captured.cb(romStore(true, m2, "romC"))
check("run in progress on romC", objects[LOCATION_MAPPING[516][2]].Active, true)

local fresh = blank()
for b = 0, 248 do fresh[FLAGS_OFF + b + 1] = 0x01 end
captured.cb(romStore(true, fresh, "romC"))
check("same rom, new file: chest released", objects[sec299].AvailableChestCount, objects[sec299].ChestCount)
check("same rom, new file: hosted item cleared", objects[LOCATION_MAPPING[516][2]].Active, false)

-- and it does not keep firing through the opening minutes of the new run
objects[LOCATION_MAPPING[516][2]].Active = true            -- a hand click
captured.cb(romStore(true, fresh, "romC"))
check("no repeat wipe while the board is empty", objects[LOCATION_MAPPING[516][2]].Active, true)

------------------------------------------------------------------
-- The Resync button. A LuaItem the layouts find by the code it claims.
------------------------------------------------------------------
local button = Tracker:FindObjectForCode("resync")
check("resync button exists", button ~= nil, true)
check("resync button has an icon", button and button.Icon, "images/flags/resync.png")
check("resync button does not answer other codes",
  button.CanProvideCodeFunc(button, "shards"), false)

captured.cb(romStore(true, m2, "romC"))
check("board repopulated before the press", objects[LOCATION_MAPPING[516][2]].Active, true)
button.OnLeftClickFunc(button)
check("pressing resync clears the hosted item", objects[LOCATION_MAPPING[516][2]].Active, false)
check("pressing resync empties UAT_CHECKED", next(UAT_CHECKED), nil)

------------------------------------------------------------------
-- The ROM memo round-trips the way PopTracker saves and restores it.
------------------------------------------------------------------
local memo
for _, it in ipairs(luaItems) do if it.SaveFunc then memo = it end end
check("rom memo exists", memo ~= nil, true)
ROM_ID = "romZ"
local saved = memo.SaveFunc(memo)
check("memo saves the current id", saved.rom, "romZ")
ROM_ID = nil                                               -- fresh Lua state
memo.LoadFunc(memo, saved)
check("memo restores it", ROM_ID, "romZ")
memo.LoadFunc(memo, { rom = "" })
check("an empty saved id is ignored", ROM_ID, "romZ")

-- The flag record rides along, so a restart does not stamp the seed's settings
-- back over a flag the player had put right by hand.
FFR_FLAGS_SOURCE = "4-9-7|abc"
saved = memo.SaveFunc(memo)
check("memo saves the flag record", saved.flags, "4-9-7|abc")
FFR_FLAGS_SOURCE = nil
memo.LoadFunc(memo, saved)
check("memo restores it", FFR_FLAGS_SOURCE, "4-9-7|abc")
memo.LoadFunc(memo, { rom = "romZ" })
check("a save from before this existed is fine", FFR_FLAGS_SOURCE, "4-9-7|abc")

------------------------------------------------------------------
-- The reported bug, end to end: track a seed, quit, put a different cartridge
-- in, relaunch, connect.
--
-- PopTracker runs init.lua and then restores the autosave -- the memo's LoadFunc
-- included -- in one synchronous block before the frame loop turns
-- (poptracker.cpp:1436-1450), so ROM_ID is already back when the first tick
-- arrives. That ordering is what makes a single comparison enough.
--
-- This could not be written before: Tracker:CreateLuaItem is really
-- ScriptHost:CreateLuaItem, so no memo was ever created, ROM_ID was nil on every
-- launch, and the swap went unnoticed while the old board stayed on screen.
------------------------------------------------------------------
local restart = nil
for _, it in ipairs(luaItems) do if it.SaveFunc then restart = it end end

FFR_FLAGS_SOURCE = "4-9-7|seedA"
ROM_ID = "romA"
local carried = restart.SaveFunc(restart)          -- PopTracker writes autosave

-- A fresh Lua state, then the restore, then the board the player left behind.
ROM_ID = nil
FFR_FLAGS_SOURCE = nil
restart.LoadFunc(restart, carried)
check("restart restored the memo before the first tick", ROM_ID, "romA")

local stale = playedBoard("romA")
check("the previous seed's board is on screen", objects[LOCATION_MAPPING[516][2]].Active, true)

-- Now the bridge reports the new cartridge.
captured.cb(romStore(true, blank(), "romB"))
check("swap after a restart cleared the hosted item", objects[LOCATION_MAPPING[516][2]].Active, false)
check("swap after a restart released the chest", objects[sec299].AvailableChestCount, objects[sec299].ChestCount)
check("swap after a restart emptied UAT_CHECKED", next(UAT_CHECKED), nil)
check("swap after a restart adopted the new id", ROM_ID, "romB")
-- Two seeds can share a flag string, and applyFFRFlags short-circuits on an
-- unchanged one, so the record has to go with the board.
check("swap after a restart dropped the flag record", FFR_FLAGS_SOURCE, nil)

------------------------------------------------------------------
-- Same cartridge, same file, checks on the board -- and the restore is holding
-- a hosted code the bridge does not report.
--
-- None of the wipes above can reach this. The ROM has not changed, the feed has
-- not gone from checks to none, and with no Archipelago session there is no
-- onClear to run resetChecked. applyHostedItem is one-way, so before the
-- first-snapshot reassert the stale code stood for the rest of the session and
-- greyed its Incentive Locations pin -- which is how the Dwarf Cave Adamant
-- turn-in came up already-collected on 2026-08-28.
------------------------------------------------------------------
local smith, bikke = LOCATION_MAPPING[521][2], LOCATION_MAPPING[516][2]
check("521 is the Smith turn-in", smith, "smith")

UAT_REASSERTED = false                  -- a fresh session
UAT_CHECKED = {}
ROM_ID = "romD"                         -- already tracking this cartridge
objects[smith].Active = true            -- restored from an older board
objects[bikke].Active = false

local live = blank()
setflag(live, 0x04, 0x02)               -- the bridge reports Bikke, and only Bikke
captured.cb(romStore(true, live, "romD"))
check("first snapshot dropped the stale hosted code", objects[smith].Active, false)
check("first snapshot kept the code the feed reports", objects[bikke].Active, true)
check("first snapshot did not reset the feed", UAT_CHECKED[516], true)
check("first snapshot did not touch the rom id", ROM_ID, "romD")

-- After that one pass the monotonic rule is back: a code set by hand mid-session
-- is not argued with a second later.
objects[smith].Active = true
captured.cb(romStore(true, live, "romD"))
check("a hand click after the snapshot survives", objects[smith].Active, true)
check("and the feed's own code is still up", objects[bikke].Active, true)

------------------------------------------------------------------
-- The unread-flags light, and the creation order it depends on
------------------------------------------------------------------
-- Creation order is load-bearing and was only ever a comment: on a host without
-- stable LuaItem ids the fallback is the sequential item id, so an item added
-- in front of these renumbers the Resync button and the ROM memo and the memo
-- comes back attached to the wrong thing. Pin it.
check("three lua items", #luaItems, 3)
check("resync is first", luaItems[1].Name, "Resync tracker")
check("the rom memo is second", luaItems[2].Name, "FFR ROM id")
check("the unread light is third", luaItems[3].Name, "FFR flags unread")

local light = Tracker:FindObjectForCode("flagsUnread")
check("the light is reachable by its code", light == luaItems[3], true)
check("it starts dark", light.Icon, nil)

-- A refused decode has to reach the board, not just the console. The grid goes
-- on showing init.lua's defaults either way; the light is what tells them apart
-- from the seed's own settings.
setFlagsUnread("no schema for FFR 4-9-2")
check("a refused decode lights it", light.Icon, "images/flags/flagsUnread.png")
check("and it remembers why", FLAGS_UNREAD_WHY, "no schema for FFR 4-9-2")

setFlagsUnread(nil)
check("a good decode clears it", light.Icon, nil)
check("and forgets the reason", FLAGS_UNREAD_WHY, nil)

print(fail==0 and "\nALL PASS" or string.format("\n%d FAILURE(S)",fail))
os.exit(fail==0 and 0 or 1)
