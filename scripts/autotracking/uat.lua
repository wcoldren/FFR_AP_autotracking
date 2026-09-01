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
-- @ToFR/Chaos, the same id LOCATION_MAPPING[766] carries. Named because it is
-- the one event that does not always arrive in the flag page; see the ff1/goal
-- read in onFF1Flags.
local GOAL_LOCATION_ID = EVENT_BASE + 0xFE

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
    -- second id to keep stable. So does why the record could not be read: it is
    -- the same fact seen from the other side, and it has to survive whatever
    -- FFR_FLAGS_SOURCE survives or the two come back disagreeing.
    return { rom = ROM_ID, flags = FFR_FLAGS_SOURCE, unread = FLAGS_UNREAD_WHY }
  end
  item.LoadFunc = function(_, data)
    if type(data) == "table" and type(data.rom) == "string" and data.rom ~= "" then
      ROM_ID = data.rom
    end
    -- Without this a PopTracker restart would re-apply the seed's settings
    -- over a flag the player had corrected by hand -- most likely one FFR
    -- rolled at generation, which is exactly the one the cartridge cannot
    -- answer and the player had to set themselves.
    --
    -- "" is restored with the rest, and has to be. It is a real record -- the
    -- bridge attached and got nothing off the cartridge -- and applyFFRFlags
    -- resets the grid to defaults every time it meets a record it has not
    -- already put in FFR_FLAGS_SOURCE. Dropping "" here left that variable nil
    -- on every restart, so the reset fired again each time and a grid set by
    -- hand on a non-FFR cartridge was wiped on reopening. A source that was
    -- never read at all is nil, not "", and still fails the type check.
    if type(data) == "table" and type(data.flags) == "string" then
      FFR_FLAGS_SOURCE = data.flags
      -- And with it the verdict on that record. Restoring the source without
      -- the verdict is the bad case: applyFFRFlags short-circuits on the
      -- unchanged string and never gets as far as lighting the light again, so
      -- a refused decode would come back looking like a read one.
      if type(data.unread) == "string" and data.unread ~= "" then
        setFlagsUnread(data.unread)
      end
    end
    return true
  end
end
rememberRomAcrossRestarts()

-- Lit when there is a cartridge in the slot whose settings we could not read.
--
-- Refusing to decode is right -- the wrong property list does not fail, it
-- returns flags shifted by one setting -- but refusing is silent, and what the
-- player is left looking at is init.lua's defaults. Those are a guess, and on
-- FFR_72A52C25 (a 4-9-2 seed, before that schema existed) the guess claimed Sky,
-- Sea and Earth were incentivized when the seed said none of them were. A
-- console line is not enough for something the board is actively asserting.
--
-- Deliberately not a fix for the defaults themselves. They are what an
-- Archipelago-only player starts from -- AP never sends a flag string, only the
-- bridge does -- so clearing them would trade a wrong board on one seed for an
-- empty board on every AP session. The honest move is to say the grid is
-- unread, not to pretend it is empty.
--
-- Third of the three LuaItems in this file. Append, never insert: on a host
-- without stable ids the fallback is the sequential item id, so a new item in
-- front of these would renumber the Resync button and the ROM memo.
local flagsUnreadItem = nil
FLAGS_UNREAD_WHY = FLAGS_UNREAD_WHY or nil

local function makeFlagsUnreadLight()
  if type(ScriptHost.CreateLuaItem) ~= "function" then
    return
  end
  local ok, item = pcall(function() return ScriptHost:CreateLuaItem() end)
  if not ok or not item then
    print("uat: could not create the unread-flags light")
    return
  end
  item.Name = "FFR flags unread"
  item.Icon = nil
  item.CanProvideCodeFunc = function(_, code)
    return code == "flagsUnread"
  end
  item.OnLeftClickFunc = function()
    if FLAGS_UNREAD_WHY then
      print("flags: " .. FLAGS_UNREAD_WHY .. " -- the grid is showing defaults "
        .. "and your own clicks, not this seed's settings")
    else
      print("flags: this seed's settings were read from the cartridge")
    end
  end
  flagsUnreadItem = item
end
makeFlagsUnreadLight()

-- why = nil clears the light. Called from applyFFRFlags on both paths, and on a
-- cartridge swap, so the light always describes the cartridge in the slot.
function setFlagsUnread(why)
  FLAGS_UNREAD_WHY = why
  if not flagsUnreadItem then
    return
  end
  -- A LuaItem's icon override is not reset by state changes the way a
  -- JsonItem's is, so nil genuinely blanks the cell and stays blank.
  --
  -- pcall'd like every other host call here. This one runs inside a variable
  -- watch, so a host that refuses the write -- a nil Icon on an older 0.23.x,
  -- say -- would otherwise take the whole autotracking update down with it, and
  -- lose the board to a warning light.
  local ok, err = pcall(function()
    flagsUnreadItem.Icon = why and "images/flags/flagsUnread.png" or nil
  end)
  if not ok then
    print("uat: cannot set the unread-flags light -- " .. tostring(err))
  end
end

-- The other warning light: the map tabs are showing art drawn off a different
-- cartridge. tools/regen_maps.py renders 61 maps into PopTracker's
-- user-override tree and PopTracker serves that ahead of the pack's own art, so
-- art from the last seed under this seed's pins looks entirely normal and is
-- wrong about every staircase.
--
-- Nothing here can work that out. This Lua has no io and no os, so the pack
-- cannot read the override it is being served from; the bridge does the
-- comparison and sends the verdict as ff1/art. Which means this light is
-- bridge-only by construction -- an Archipelago-only session never learns
-- anything about the art on disk, the same way it never learns the flag string.
--
-- Fourth of the five LuaItems in this file. Append, never insert, for the
-- reason the third one gives.
local artStaleItem = nil
ART_STALE_WHY = ART_STALE_WHY or nil

local function makeArtStaleLight()
  if type(ScriptHost.CreateLuaItem) ~= "function" then
    return
  end
  local ok, item = pcall(function() return ScriptHost:CreateLuaItem() end)
  if not ok or not item then
    print("uat: could not create the stale-art light")
    return
  end
  item.Name = "Drawn maps are another cartridge's"
  item.Icon = nil
  item.CanProvideCodeFunc = function(_, code)
    return code == "artStale"
  end
  item.OnLeftClickFunc = function()
    if ART_STALE_WHY then
      print("maps: " .. ART_STALE_WHY .. " -- re-run tools/regen_maps.py on "
        .. "this cartridge and restart PopTracker, or --clean it to go back to "
        .. "the pack's hand-drawn art")
    else
      print("maps: nothing says the drawn maps are another cartridge's")
    end
  end
  artStaleItem = item
end
makeArtStaleLight()

-- why = nil clears the light, exactly as setFlagsUnread does. Driven straight
-- off the variable every update rather than latched: the bridge computes it per
-- cartridge and republishes on a swap, so the store always holds the verdict
-- for the cartridge in the slot and there is no separate state to keep in step.
function setArtStale(why)
  if why == "" then
    why = nil
  end
  ART_STALE_WHY = why
  if not artStaleItem then
    return
  end
  local ok, err = pcall(function()
    artStaleItem.Icon = why and "images/flags/artStale.png" or nil
  end)
  if not ok then
    print("uat: cannot set the stale-art light -- " .. tostring(err))
  end
end

-- The third warning light: this seed is not the game the loaded variant tracks.
-- A No-Overworld seed on a standard variant colours every pin with the wrong
-- geography, and a shard-hunt seed on a standard variant is gated on four lit
-- orbs instead of the shard count -- both quietly, because nothing downstream
-- can correct either.
--
-- The pack cannot fix this by switching variants, and that is settled rather
-- than assumed: PopTracker's Tracker.ActiveVariantUID is read-only from Lua and
-- says so out loud (core/tracker.cpp:747-749, "Tried to write read-only
-- property"), and Pack::setVariant is called once, from poptracker.cpp:1202,
-- while the pack is being loaded. There is no runtime path to it at all. So the
-- honest move is the one flagsUnread makes: say it on the board, where a player
-- who missed the console line will see it.
--
-- Fifth of the five LuaItems in this file, and last, for the same reason.
local modeMismatchItem = nil
MODE_MISMATCH_WHY = MODE_MISMATCH_WHY or nil

local function makeModeMismatchLight()
  if type(ScriptHost.CreateLuaItem) ~= "function" then
    return
  end
  local ok, item = pcall(function() return ScriptHost:CreateLuaItem() end)
  if not ok or not item then
    print("uat: could not create the mode-mismatch light")
    return
  end
  item.Name = "Seed and variant disagree"
  item.Icon = nil
  item.CanProvideCodeFunc = function(_, code)
    return code == "modeMismatch"
  end
  item.OnLeftClickFunc = function()
    if MODE_MISMATCH_WHY then
      print("flags: " .. MODE_MISMATCH_WHY .. " -- close the pack and reopen it "
        .. "on the matching variant; PopTracker cannot switch one at runtime")
    else
      print("flags: this seed matches the variant you have loaded")
    end
  end
  modeMismatchItem = item
end
makeModeMismatchLight()

-- why = nil clears it, exactly as the two above. Set from applyFFRFlags on
-- every decode, so it always describes the cartridge in the slot.
function setModeMismatch(why)
  if why == "" then
    why = nil
  end
  MODE_MISMATCH_WHY = why
  if not modeMismatchItem then
    return
  end
  local ok, err = pcall(function()
    modeMismatchItem.Icon = why and "images/flags/modeMismatch.png" or nil
  end)
  if not ok then
    print("uat: cannot set the mode-mismatch light -- " .. tostring(err))
  end
end

-- "" means the emulator would not tell us, which is not the same as a change.
local function checkRom(store)
  local rom = store:ReadVariable("ff1/rom")
  if type(rom) ~= "string" or rom == "" then
    return
  end
  if ROM_ID ~= nil and rom ~= ROM_ID then
    print("uat: different ROM -- dropping the previous game's board")
    -- The flag record goes too. applyFFRFlags short-circuits on an unchanged
    -- string (flag_mapping.lua:347), so two seeds rolled on the same flags would
    -- otherwise carry the previous one's hand-corrected grid into the new game.
    FFR_FLAGS_SOURCE = nil
    -- With it the verdict on that record. ff1/rom and ff1/flags normally arrive
    -- in the same message, so applyFFRFlags is about to re-decide this a few
    -- lines below -- but "normally" is not "always", and the light left over
    -- from the last cartridge describes a cartridge that is no longer in the
    -- slot.
    setFlagsUnread(nil)
    -- And the mode verdict, which described the cartridge that just left.
    setModeMismatch(nil)
    -- And the stale-art verdict, for the same reason. ff1/art is computed per
    -- cartridge and republished on a swap, so the frame below normally carries
    -- the new one -- but a frame that carries ff1/rom and not ff1/art would
    -- leave the triangle lit against a cartridge the verdict was never
    -- computed for, and the light is meant to be read the moment a seed is
    -- loaded.
    setArtStale(nil)
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

  -- Ahead of the ready gate for the third time, and for the same reason: which
  -- cartridge the art on disk was drawn for is a fact about the installation,
  -- not about how far into the seed you are. It is also the moment it is worth
  -- knowing -- before you have read anything off a map.
  local art = store:ReadVariable("ff1/art")
  setArtStale(type(art) == "string" and art or nil)

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

  -- The Chaos kill is the one check that is not always in the flag page. FFR
  -- only patches the goal bit into byte 0xFE on an Archipelago seed
  -- (FF1Lib/archipelago/Archipelago.cs:225-226); a solo seed leaves that byte
  -- alone forever, so the bridge reads the kill off the battle engine instead
  -- and reports it here. On an Archipelago seed both routes agree and this is
  -- the redundant one.
  if store:ReadVariable("ff1/goal") == true then
    checked[GOAL_LOCATION_ID] = true
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
ScriptHost:AddVariableWatch("ff1mem",
  {"ff1/mem", "ff1/ready", "ff1/rom", "ff1/flags", "ff1/goal", "ff1/art"},
  onFF1Flags)
