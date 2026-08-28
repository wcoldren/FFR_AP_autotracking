------------------------------------------------------------------
-- UAT feed: chest/event flags read out of the emulator by the bridge script
-- in bridge/ffr_uat_bridge.lua.
--
-- The bridge is deliberately dumb -- it mirrors the 768 bytes at CPU
-- $6000-$62FF and knows nothing about Final Fantasy. The bit semantics live
-- here, next to LOCATION_MAPPING, and mirror worlds/ff1/Client.py:
--
--   byte i & 0x04  chest opened  -> AP location id 0x100 + i
--   byte i & 0x02  NPC/event     -> AP location id 0x200 + i
--
-- This runs alongside the Archipelago feed rather than instead of it: both
-- backends can be connected at once, and the reconcile core takes the union.
--
-- The two bits are not handled symmetrically, on purpose. Chest flags are
-- dense -- worlds/ff1 defines a location for 253 of the 254 possible chest
-- indices -- so a chest bit on an index the pack has no mapping for is a real
-- gap worth reporting. Event flags are sparse: only 14 indices are tracked
-- locations, and the game sets bit 0x02 on plenty of other bytes for events
-- that were never AP locations at all (byte 0xFE bit 0x02 is the Chaos kill).
-- Those are ignored rather than reported, or every playthrough would warn
-- about ids that are not locations in the first place.
------------------------------------------------------------------

local FLAGS_OFF = 0x200   -- the flag array's offset within ff1/mem
local CHEST_FLAG = 0x04
local EVENT_FLAG = 0x02
local CHEST_BASE = 0x100
local EVENT_BASE = 0x200

local UNMAPPED_CHEST_WARNED = {}

-- Which cartridge this board belongs to, from ff1/rom. Nearly everything the
-- pack derives from RAM used to be raise-only, so swapping seeds left the
-- finished run's orbs, key items and hosted codes on screen with no way for the
-- new game's zeroed RAM to take them back down. This is the signal that says
-- "different game" so reconcile can throw the old board away.
ROM_ID = ROM_ID or nil

-- A manual "start this board over", for the states nothing can detect: a save
-- written before the ROM memo below existed, manual clears you no longer want,
-- or an older save that still has checks in it and so leaves the hosted codes
-- behind the Incentive Locations pins lit. It costs nothing to press --
-- everything the feeds own is re-derived on the next tick, about a second away.
--
-- Created before the memo on purpose; see the note on creation order there.
local function makeResyncButton()
  if type(ScriptHost.CreateLuaItem) ~= "function" then
    print("uat: no ScriptHost:CreateLuaItem -- no Resync button on this host")
    return
  end
  local ok, item = pcall(function() return ScriptHost:CreateLuaItem() end)
  if not ok or not item then
    print("uat: could not create the Resync button")
    return
  end
  item.Name = "Resync tracker"
  item.Icon = "images/flags/resync.png"
  -- How the layouts find it. CanProvideCodeFunc rather than PotentialCodes,
  -- which is the newer of the two ways and would raise the PopTracker version
  -- this pack needs.
  item.CanProvideCodeFunc = function(_, code)
    return code == "resync"
  end
  item.OnLeftClickFunc = function()
    print("uat: resync -- rebuilding the board from the feeds")
    -- Forget which flag string was applied, so the next tick re-reads the
    -- seed's settings too. Resync is the one place that is meant to throw away
    -- hand edits, flag-grid clicks included.
    FFR_FLAGS_SOURCE = nil
    resetForNewGame()
  end
end
makeResyncButton()

-- It has to survive a PopTracker restart, too: a fresh Lua state has nothing to
-- compare against, and PopTracker restores its saved board after the pack's
-- scripts run, so the stale board would win. A LuaItem is the pack-side way to
-- persist a value -- it is saved under lua_items and its LoadFunc runs during
-- loadState (tracker.cpp:1341).
--
-- The restore always beats the first tick, so one comparison is enough: PopTracker
-- runs init.lua, saves the reset snapshot and calls loadState in one synchronous
-- block (poptracker.cpp:1436-1450), while variable watches only fire later from
-- the frame loop. ROM_ID is therefore already restored when checkRom first runs.
--
-- A LuaItem's stable id is "<type>:<name>@<hash of the source *filename*>"
-- (updateLuaStableIDs, tracker.cpp:982-1000) -- no line number in it. So editing
-- this file is free; what drops the memo is renaming the item or moving it to
-- another script. On a host too old for stable ids the fallback is the sequential
-- item id (tracker.cpp:1434-1438), which is creation-order sensitive -- so keep
-- the Resync button created first and this one second.
local function rememberRomAcrossRestarts()
  if type(ScriptHost.CreateLuaItem) ~= "function" then
    print("uat: no ScriptHost:CreateLuaItem -- the ROM memo cannot persist, so a "
      .. "seed swap across a restart will not be noticed; press Resync if the "
      .. "board looks like the last seed")
    return
  end
  local ok, item = pcall(function() return ScriptHost:CreateLuaItem() end)
  if not ok or not item then
    print("uat: could not create the ROM memo")
    return
  end
  item.Name = "FFR ROM id"
  item.SaveFunc = function()
    -- The flag record rides along rather than getting a LuaItem of its own:
    -- both answer "which cartridge is this", and a second item would be a
    -- second id to keep stable.
    return { rom = ROM_ID, flags = FFR_FLAGS_SOURCE }
  end
  item.LoadFunc = function(_, data)
    if type(data) == "table" and type(data.rom) == "string" and data.rom ~= "" then
      ROM_ID = data.rom
    end
    -- Without this a PopTracker restart would re-apply the seed's settings
    -- over a flag the player had corrected by hand -- most likely one FFR
    -- rolled at generation, which is exactly the one the cartridge cannot
    -- answer and the player had to set themselves.
    if type(data) == "table" and type(data.flags) == "string" and data.flags ~= "" then
      FFR_FLAGS_SOURCE = data.flags
    end
    return true
  end
end
rememberRomAcrossRestarts()

-- "" means the emulator would not tell us, which is not the same as a change.
local function checkRom(store)
  local rom = store:ReadVariable("ff1/rom")
  if type(rom) ~= "string" or rom == "" then
    return
  end
  if ROM_ID ~= nil and rom ~= ROM_ID then
    print("uat: different ROM -- dropping the previous game's board")
    -- The flag record goes too. applyFFRFlags short-circuits on an unchanged
    -- string (flag_mapping.lua:201), so two seeds rolled on the same flags would
    -- otherwise carry the previous one's hand-corrected grid into the new game.
    FFR_FLAGS_SOURCE = nil
    resetForNewGame()
  elseif ROM_ID == nil then
    -- No memo to compare against: a first run, or a save written before the memo
    -- existed. The board on screen is whatever PopTracker restored, and nothing
    -- here can tell whether it belongs to this cartridge.
    print("uat: adopting ROM " .. rom .. " with no previous memo -- press Resync "
      .. "if this board is from another seed")
  end
  ROM_ID = rom
end

function onFF1Flags(store)
  -- Ahead of the ready gate on purpose: ff1/rom is published whatever the
  -- save-loaded guard says, and the window right after a ROM swap -- guard
  -- unhappy, no save loaded yet -- is exactly when the swap has to be noticed.
  checkRom(store)

  -- Likewise ahead of it, and after checkRom so a swap has already dropped the
  -- old board: this is what the seed was rolled with, not how far into it you
  -- are, and it is worth having on screen before a save is even loaded.
  -- applyFFRFlags is a no-op unless the string actually changed.
  if applyFFRFlags then
    applyFFRFlags(store:ReadVariable("ff1/flags"))
  end

  -- The bridge only claims ready once a save is actually loaded, which keeps
  -- a reset or the character-creation screen from reading as a wipe.
  if store:ReadVariable("ff1/ready") ~= true then
    if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
      print("uat: bridge not ready, ignoring flags")
    end
    return
  end

  local mem = store:ReadVariable("ff1/mem")
  if type(mem) ~= "table" then
    return
  end

  local checked = {}
  -- ff1/mem is a 0-indexed byte array sent as a JSON array, so Lua sees it
  -- 1-based: element n holds byte n-1. The flag array starts at FLAGS_OFF.
  for n = 1, 256 do
    local byte = mem[FLAGS_OFF + n]
    if type(byte) == "number" then
      local i = n - 1
      if byte & CHEST_FLAG ~= 0 then
        local id = CHEST_BASE + i
        checked[id] = true
        if not LOCATION_MAPPING[id] and not UNMAPPED_CHEST_WARNED[id] then
          UNMAPPED_CHEST_WARNED[id] = true
          print(string.format("uat: chest flag set for unmapped AP location id %d (byte 0x%02X)", id, i))
        end
      end
      -- Only events the pack already knows about; see the note above.
      if byte & EVENT_FLAG ~= 0 then
        local id = EVENT_BASE + i
        if LOCATION_MAPPING[id] then
          checked[id] = true
        end
      end
    end
  end

  setUATChecked(checked)

  -- Bosses, orbs, turn-ins and vehicles are not Archipelago locations at all,
  -- so they come straight off the RAM mirror.
  applyRamRules(function(addr)
    return mem[addr - RAM_MEM_BASE + 1]
  end)

  if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
    local n = 0
    for _ in pairs(checked) do n = n + 1 end
    print(string.format("uat: %d locations checked", n))
  end
end

-- ff1/rom rides on the same watch rather than getting its own. Watch firing
-- order is not defined, and reading both out of one store removes any chance of
-- decoding the new cartridge's flags against the old cartridge's identity.
ScriptHost:AddVariableWatch("ff1mem", {"ff1/mem", "ff1/ready", "ff1/rom", "ff1/flags"}, onFF1Flags)
