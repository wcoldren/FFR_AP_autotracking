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

function onFF1Flags(store)
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

  if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
    local n = 0
    for _ in pairs(checked) do n = n + 1 end
    print(string.format("uat: %d locations checked", n))
  end
end

ScriptHost:AddVariableWatch("ff1mem", {"ff1/mem", "ff1/ready"}, onFF1Flags)
