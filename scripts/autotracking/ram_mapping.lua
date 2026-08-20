------------------------------------------------------------------
-- Tracker codes derived directly from cart RAM, via the ff1/mem mirror the
-- bridge ships. This covers the things Archipelago cannot tell us about:
-- bosses, orbs being lit, and key items being handed in.
--
-- ADDRESSES ARE FFR-SPECIFIC. Sources, all cross-checked against each other:
--   * BenWenger/FinalFantasyDisassembly -- Constants.inc, variables.inc,
--     bank_0E.asm (Disch's commented disassembly of the US ROM)
--   * FiendsOfTheElements/FF1Randomizer -- Items.cs, GlobalHacks.cs,
--     NpcScripts.List.cs, asm/11_8200_TalkRoutines.asm
--   * the EmoTracker FFR pack (jtoyoda/jtoyoda.github.io), which this pack
--     descends from and which reads the same window
--
-- Two places where FFR differs from vanilla FF1, both load-bearing:
--
--   Garland. Vanilla's Talk_Garland only hides the object and never sets an
--   event bit. FFR remaps it to Talk_fight, which sets the flag AFTER the
--   battle -- so $6202 & 0x02 is a real "defeated", not "talked to". On a
--   vanilla ROM this would never fire.
--
--   Orbs. ShiftEarthOrbDown() runs unconditionally so the Shard counter can
--   sit contiguously after the orbs, moving Earth Orb from $6035 to $6031.
--   The orb byte IS the lit flag; there is no separate one.
--
-- Flag bits, from Constants.inc:123-128 -- $6200+id is indexed by BOTH map
-- object id and treasure chest id, which is why the masks matter:
--   0x01 object visible   0x02 event happened   0x04 chest opened
------------------------------------------------------------------

RAM_MEM_BASE = 0x6000

-- Codes whose items set allow_disabled:false. Everything else defaults to
-- allow_disabled:true, which gives the item a synthetic "not acquired" stage
-- and pushes its Lua-visible CurrentStage one above the stages[] index
-- (jsonitem.cpp:381 and :473). Getting this wrong is silent: the item lands on
-- stages[0] and looks acquired while never providing the turn-in code.
RAM_NO_STAGE_OFFSET = {
  earthorb = true, fireorb = true, waterorb = true, airorb = true,
  shards = true,
}

-- Each rule: the code, the stage it proves, and the test.
--   mask set  -> (byte & mask) ~= 0
--   zero set  -> byte == 0
--   neither   -> byte ~= 0
-- `stage` is the index into that item's stages[] array in items/*.json, so
-- these numbers can be read straight against the JSON; the conversion to
-- PopTracker's Lua numbering happens in raiseTo.
-- Highest satisfied stage per code wins. Nothing here is ever lowered.
RAM_RULES = {
  -- Bosses. Both go through FFR's Talk_fight, flag set after the win.
  { code = "garland", stage = 0, addr = 0x6202, mask = 0x02 },
  { code = "vampire", stage = 0, addr = 0x620C, mask = 0x02 },

  -- Orbs: nonzero means lit, which is stage 1 (the *orblit codes).
  -- canBreakOrb() in logic.lua needs all four at this stage.
  { code = "earthorb", stage = 1, addr = 0x6031 },
  { code = "fireorb",  stage = 1, addr = 0x6032 },
  { code = "waterorb", stage = 1, addr = 0x6033 },
  { code = "airorb",   stage = 1, addr = 0x6034 },

  -- Plain key items: held or not.
  { code = "lute",   stage = 0, addr = 0x6021 },
  { code = "key",    stage = 0, addr = 0x6025 },
  { code = "rod",    stage = 0, addr = 0x602A },
  { code = "chime",  stage = 0, addr = 0x602C },
  { code = "cube",   stage = 0, addr = 0x602E },
  { code = "oxyale", stage = 0, addr = 0x6030 },

  -- Key items with a turn-in. Stage 0 is holding it; stage 1 is the NPC's
  -- event flag, which is what survives after the item is consumed.
  { code = "crown",   stage = 0, addr = 0x6022 },
  { code = "crown",   stage = 1, addr = 0x6207, mask = 0x02 },  -- Astos
  { code = "crystal", stage = 0, addr = 0x6023 },
  { code = "crystal", stage = 1, addr = 0x620A, mask = 0x02 },  -- Matoya
  { code = "herb",    stage = 0, addr = 0x6024 },
  { code = "herb",    stage = 1, addr = 0x6205, mask = 0x02 },  -- Elf Doctor
  { code = "tnt",     stage = 0, addr = 0x6026 },
  { code = "tnt",     stage = 1, addr = 0x6208, mask = 0x02 },  -- Nerrick
  { code = "adamant", stage = 0, addr = 0x6027 },
  { code = "adamant", stage = 1, addr = 0x6209, mask = 0x02 },  -- Smith
  { code = "ruby",    stage = 0, addr = 0x6029 },
  { code = "ruby",    stage = 1, addr = 0x6214, mask = 0x02 },  -- Titan
  { code = "tail",    stage = 0, addr = 0x602D },
  { code = "tail",    stage = 1, addr = 0x620E, mask = 0x02 },  -- Bahamut
  { code = "bottle",  stage = 0, addr = 0x602F },
  { code = "bottle",  stage = 1, addr = 0x6213, mask = 0x02 },  -- Fairy

  -- Slab has two turn-ins: Unne translates it, Lefein takes it.
  { code = "slab", stage = 0, addr = 0x6028 },
  { code = "slab", stage = 1, addr = 0x620B, mask = 0x02 },     -- Unne
  { code = "slab", stage = 2, addr = 0x620F, mask = 0x02 },     -- Lefein

  -- Floater, then the airship it produces.
  { code = "floater", stage = 0, addr = 0x602B },
  { code = "floater", stage = 1, addr = 0x6004 },               -- airship_vis

  -- Vehicles and world state.
  { code = "ship",   stage = 0, addr = 0x6000 },
  { code = "bridge", stage = 0, addr = 0x6008 },
  { code = "canoe",  stage = 0, addr = 0x6012 },
  -- canal_vis is the *undug canal object*, so it reads INVERTED: the byte
  -- goes to zero once the canal is open.
  { code = "canal",  stage = 0, addr = 0x600C, zero = true },
}

-- Shard count is a number, not a flag, so it gets its own rule.
-- The AP feed advances this item once per shard received, leaving
-- CurrentStage at count-1 (the first shard only sets Active). Match that
-- exactly, or the two feeds would disagree by one.
RAM_SHARDS = { code = "shards", addr = 0x6035, maxStage = 36 }

-- Chaos is not here either, but it is tracked: it is an ordinary event flag
-- ($62FE bit 0x02) and lives in LOCATION_MAPPING with the other events. See the
-- note there about the airship, which is why it took so long to trust.
--
-- Deliberately NOT derived from RAM:
--
--   sigil and mark -- FFR's no-overworld mode reuses the floater byte
--   ($602B) for Sigil and the canoe byte ($6012) for Mark. Nothing in RAM
--   distinguishes them from the items they share a byte with; it depends on
--   the seed's flags, which we do not read.

local UNKNOWN_CODE_WARNED = {}

-- Every code this file owns, and which of them have stages worth walking.
-- Built once from the tables above so adding a rule needs no second edit.
local RAM_CODES, RAM_HAS_STAGES = {}, {}
for _, rule in ipairs(RAM_RULES) do
  RAM_CODES[rule.code] = true
  if rule.stage > 0 then
    RAM_HAS_STAGES[rule.code] = true
  end
end
RAM_CODES[RAM_SHARDS.code] = true
RAM_HAS_STAGES[RAM_SHARDS.code] = true

-- Set by onClear, which fires when an Archipelago session connects. See
-- apOwned below for why it matters.
AP_ITEM_FEED_ACTIVE = AP_ITEM_FEED_ACTIVE or false

-- Codes Archipelago also grants through onItem. RAM is authoritative for the
-- game's own state, but AP's item feed replays only on onClear, so anything we
-- clear here that AP granted is gone until the player reconnects. While an AP
-- session is live those codes stay raise-only; the rest -- bosses, orbs, every
-- turn-in stage -- follow RAM in both directions regardless.
local function apOwned(code)
  if not AP_ITEM_FEED_ACTIVE then
    return false
  end
  if type(ITEM_MAPPING) ~= "table" then
    return false
  end
  for _, v in pairs(ITEM_MAPPING) do
    if v[1] == code then
      return true
    end
  end
  return false
end

local function objectFor(code)
  local obj = Tracker:FindObjectForCode(code)
  if not obj and not UNKNOWN_CODE_WARNED[code] then
    UNKNOWN_CODE_WARNED[code] = true
    print(string.format("ram: no tracker object for code %s", code))
  end
  return obj
end

-- The CurrentStage that represents stages[stage] for this code. Items with
-- allow_disabled:true carry a synthetic "not acquired" stage at 0, so their
-- Lua-visible stage sits one above the stages[] index (jsonitem.cpp:381, :473).
local function stageValue(code, stage)
  return RAM_NO_STAGE_OFFSET[code] and stage or (stage + 1)
end

-- RAM is authoritative, the same way it already is for chests and NPC events:
-- what the cart says now is what the tracker shows, so loading an older save or
-- starting a different seed walks items back instead of stranding the previous
-- run's board on screen. This replaced a raise-only rule that was defensive
-- about unverified addresses; the completed-seed sync on 2026-08-19 exercised
-- every one of them against a running game.
--
-- `stage` is nil for "RAM does not have this at all". allowLower is false for
-- the AP-shared codes described above.
local function applyCode(code, stage, allowLower)
  local obj = objectFor(code)
  if not obj then
    return
  end
  if stage == nil then
    if not allowLower then
      return
    end
    if obj.Active then
      obj.Active = false
    end
    if RAM_HAS_STAGES[code] and (obj.CurrentStage or 0) ~= 0 then
      obj.CurrentStage = 0
    end
    return
  end
  if not obj.Active then
    obj.Active = true
  end
  if not RAM_HAS_STAGES[code] then
    -- A toggle has no stages to move.
    return
  end
  local target = stageValue(code, stage)
  local current = obj.CurrentStage or 0
  if current < target or (allowLower and current > target) then
    obj.CurrentStage = target
  end
end

-- Wipe everything this file owns. Called when the bridge reports a different
-- cartridge (see reconcile.resetForNewGame): the previous game's items are not
-- merely stale, they are about to be replaced wholesale by the new one's RAM.
-- The AP carve-out still applies -- a code AP granted would not come back.
function clearRamDerivedItems()
  for code in pairs(RAM_CODES) do
    applyCode(code, nil, not apOwned(code))
  end
end

-- byteAt(addr) returns the byte at a CPU address, or nil if out of range.
function applyRamRules(byteAt)
  local best = {}
  local seen = false
  for _, rule in ipairs(RAM_RULES) do
    local byte = byteAt(rule.addr)
    if byte then
      seen = true
      local hit
      if rule.mask then
        hit = (byte & rule.mask) ~= 0
      elseif rule.zero then
        hit = byte == 0
      else
        hit = byte ~= 0
      end
      if hit and (best[rule.code] == nil or rule.stage > best[rule.code]) then
        best[rule.code] = rule.stage
      end
    end
  end

  local shards = byteAt(RAM_SHARDS.addr)
  if shards and shards > 0 then
    best[RAM_SHARDS.code] = math.min(shards - 1, RAM_SHARDS.maxStage)
  end

  -- A byteAt that answered nothing at all is a malformed feed, not a game with
  -- no items. Lowering on it would blank the board.
  if not seen and shards == nil then
    return
  end

  for code in pairs(RAM_CODES) do
    applyCode(code, best[code], not apOwned(code))
  end
end
