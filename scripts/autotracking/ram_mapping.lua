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

-- Each rule: the code, the stage it proves, and the test.
--   mask set  -> (byte & mask) ~= 0
--   zero set  -> byte == 0
--   neither   -> byte ~= 0
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

-- Deliberately NOT derived from RAM:
--
--   chaos -- $62FE bit 0x02 is Archipelago's goal flag, but FFR also uses it
--   as OBJID_REVEALAIRSHIP and sets it whenever the airship is on screen
--   (asm/1B_A100_ItemMenuTracker.asm). Whether both patches can land in one
--   ROM is unresolved, so auto-checking the goal risks marking the run
--   complete the first time you see the airship. Left as a manual click.
--
--   sigil and mark -- FFR's no-overworld mode reuses the floater byte
--   ($602B) for Sigil and the canoe byte ($6012) for Mark. Nothing in RAM
--   distinguishes them from the items they share a byte with; it depends on
--   the seed's flags, which we do not read.

local UNKNOWN_CODE_WARNED = {}

-- Raise-only. RAM can set a code or push it further along, never clear it or
-- walk it back. Every event here is one-way in the game, so the only thing
-- this gives up is un-marking after loading an older save -- and in exchange,
-- a wrong address degrades to "never lights" instead of "cannot be corrected
-- by hand", which matters while these addresses are unverified in play.
local function raiseTo(code, stage)
  local obj = Tracker:FindObjectForCode(code)
  if not obj then
    if not UNKNOWN_CODE_WARNED[code] then
      UNKNOWN_CODE_WARNED[code] = true
      print(string.format("ram: no tracker object for code %s", code))
    end
    return
  end
  if not obj.Active then
    obj.Active = true
  end
  -- Only touch CurrentStage for real progressives; a toggle has no stages.
  if stage > 0 and (obj.CurrentStage or 0) < stage then
    obj.CurrentStage = stage
  end
end

-- byteAt(addr) returns the byte at a CPU address, or nil if out of range.
function applyRamRules(byteAt)
  local best = {}
  for _, rule in ipairs(RAM_RULES) do
    local byte = byteAt(rule.addr)
    if byte then
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
  for code, stage in pairs(best) do
    raiseTo(code, stage)
  end

  local shards = byteAt(RAM_SHARDS.addr)
  if shards and shards > 0 then
    local stage = math.min(shards - 1, RAM_SHARDS.maxStage)
    raiseTo(RAM_SHARDS.code, stage)
  end
end
