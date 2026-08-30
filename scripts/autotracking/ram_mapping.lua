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
  -- event flag, which is what survives after the item is consumed. The talk
  -- that takes the item is the same talk that sets the flag, so there is no
  -- window where neither stage holds. The Bottle below does not work this way.
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
  -- Titan is the one turn-in with no event bit to read. Talk_Titan takes the
  -- Ruby and calls HideMapObject and nothing else -- in vanilla
  -- (bank_0E.asm:1437) and in FFR alike (11_8200_TalkRoutines.asm:415) -- so
  -- SetGameEventFlag is never reached for OBJID_TITAN ($14). FFR's own in-game
  -- item tracker says so where it lists what it can follow: "Not ruby --
  -- Titan's event flag is not updated in talk routines"
  -- (1B_A100_ItemMenuTracker.asm:693). Every other turn-in here reads a bit
  -- that something actually sets; mask 0x02 on this one could never match, so
  -- the spent Ruby fell to stage 0, stopped providing `ruby`, and took Titan's
  -- Trove and Sarda red on the seed where they had just opened.
  --
  -- What Talk_Titan does leave is the visibility bit going out.
  -- lut_InitGameFlags starts $14 at 0x01 (GMFLG_OBJVISIBLE) and HideMapObject
  -- ANDs it off, so *that bit* is the turn-in.
  --
  -- Read the bit, not the byte. An earlier version of this rule tested
  -- `zero = true` on the theory that nothing else ever writes to $6214, and
  -- that is wrong: the flag array is indexed by a *shared* id space, where
  -- byte i carries both chest i's opened bit (0x04) and event i's bit (0x02)
  -- -- see the header of uat.lua, which mirrors worlds/ff1/Client.py. Index
  -- $14 is OBJID_TITAN and chest $14 at the same time, so opening that chest
  -- parks 0x04 in this byte for the rest of the run.
  --
  -- Measured across five real saves: $6214 is 0x01 with Titan still standing,
  -- and 0x04 once he is fed and that chest is open. `zero` therefore never
  -- matched, the spent Ruby fell through to no rule at all, and applyCode()
  -- blanked the item -- which also un-did every manual click on the next scan.
  -- Masking 0x04 or 0x06 would be the same bug wearing a hat: it would call
  -- the Titan fed the moment chest $14 was opened.
  --
  -- A bit-clear test does read an all-zero flag page as "fed". That is safe
  -- only because applyRamRules runs behind ff1/ready, which the bridge holds
  -- low until a save is actually loaded. Fed-with-the-chest-shut is a real
  -- 0x00, so this cannot be tightened by demanding a nonzero byte.
  { code = "ruby",    stage = 1, addr = 0x6214, clear = 0x01 },  -- Titan fed
  { code = "tail",    stage = 0, addr = 0x602D },
  { code = "tail",    stage = 1, addr = 0x620E, mask = 0x02 },  -- Bahamut
  -- The Bottle is spent by USING it, not by handing it over, so its two events
  -- are an unbounded stretch of play apart. UseItem_Bottle zeroes $602F and
  -- calls ShowMapObject(OBJID_FAIRY) in the same breath (bank_0E.asm:6925),
  -- and ShowMapObject sets the object-visible bit, 0x01. The Fairy's event bit
  -- 0x02 only arrives later, when she is actually talked to. Matching 0x02
  -- alone left nothing providing `bottle` for exactly the stretch where the
  -- Fairy check is open, which is what @Gaia/Fairy's access rule reads -- so
  -- the marker went red on the seed where it had just gone live. 0x03 rather
  -- than 0x01 so the stage holds either way, in case FFR hides the object on
  -- the turn-in the way Talk_Titan does.
  { code = "bottle",  stage = 0, addr = 0x602F },
  { code = "bottle",  stage = 1, addr = 0x6213, mask = 0x03 },  -- Fairy popped

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

-- Shard count is a number, not a flag, so it gets its own rule. The stage is
-- the count itself: Shards is allow_disabled:false, so RAM_NO_STAGE_OFFSET
-- holds and CurrentStage is the stages[] index directly.
--
-- This used to publish count-1, to agree with an AP feed that granted the
-- first shard as Active and left the stage at zero. Both ends were one low --
-- one shard drew shard-00.gif, and hasEnoughShards wanted 29 for a 28-shard
-- goal. The AP side counts properly now (ITEM_MAPPING type "count"), so this
-- one no longer has to be bent to match it.
RAM_SHARDS = { code = "shards", addr = 0x6035, maxStage = 36 }

-- Chaos is not here either, but it is tracked: it is an ordinary event flag
-- ($62FE bit 0x02) and lives in LOCATION_MAPPING with the other events. See the
-- note there about the airship, which is why it took so long to trust.
--
-- Nothing to derive from RAM:
--
--   sigil and mark -- No-Overworld renames exactly two items and only on the
--   item screen: MetroidVaniaMap.cs:843-844 sets ItemsText[Floater] = "SIGIL"
--   and ItemsText[EarthOrb] = "MARK". So SIGIL is the Floater at $602B and
--   MARK is the Earth Orb at $6031, both already read above, and neither is a
--   byte of its own. This used to say MARK was the Canoe at $6012, which is
--   the dialogue talking: the Canoe gate NPCs say "Lukahn's mark" and their
--   talk routine checks the Canoe. docs/NOVERWORLD.md states it plainly for
--   the same reason -- it was recorded backwards for a while.

local UNKNOWN_CODE_WARNED = {}

-- Last stage each code was derived at, and which codes have already reported
-- losing it. Both feed the present -> absent warning at the end of
-- applyRamRules; neither changes what the board shows.
LAST_RAM_STAGE = LAST_RAM_STAGE or {}
VANISH_WARNED = VANISH_WARNED or {}

-- Every code this file owns, and which of them have stages worth walking.
-- Built once from the tables above so adding a rule needs no second edit.
-- Codes carrying more than one stage in RAM_RULES: an inventory sighting and at
-- least one "it was handed over" rule. Those are the only ones for which "no
-- rule matched" is ambiguous rather than simply absent, and so the only ones
-- worth reporting when they go out. Derived rather than listed so a turn-in
-- added later is covered without anyone remembering to come back here.
local RAM_TURN_IN = {}

local RAM_CODES, RAM_HAS_STAGES = {}, {}
local seenStage = {}
for _, rule in ipairs(RAM_RULES) do
  RAM_CODES[rule.code] = true
  if rule.stage > 0 then
    RAM_HAS_STAGES[rule.code] = true
  end
  seenStage[rule.code] = seenStage[rule.code] or {}
  if not seenStage[rule.code][rule.stage] then
    seenStage[rule.code][rule.stage] = true
    seenStage[rule.code].n = (seenStage[rule.code].n or 0) + 1
    if seenStage[rule.code].n > 1 then
      RAM_TURN_IN[rule.code] = true
    end
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
  -- The previous cartridge's stages are not evidence about this one, so drop
  -- them here rather than letting the first snapshot of a new seed report every
  -- item the old one had finished.
  LAST_RAM_STAGE, VANISH_WARNED = {}, {}
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
      elseif rule.clear then
        -- Bits that mean something by going *out*. Distinct from `zero`: the
        -- flag-array bytes are shared between a chest bit and an event bit, so
        -- "this object's visibility went away" is a single bit going low in a
        -- byte whose other bits are still moving under it. See the Titan rule.
        hit = (byte & rule.clear) == 0
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
    best[RAM_SHARDS.code] = math.min(shards, RAM_SHARDS.maxStage)
  end

  -- A byteAt that answered nothing at all is a malformed feed, not a game with
  -- no items. Lowering on it would blank the board.
  if not seen and shards == nil then
    return
  end

  -- Say so when an item the cartridge was showing stops being shown at all.
  --
  -- For a turn-in item "no rule matched" is ambiguous: it means either "never
  -- picked it up" or "spent it, and the rule that was supposed to notice is
  -- wrong". Those look identical in a single snapshot, and the second one has
  -- now shipped three times -- Titan's Trove and Sarda going red (f09e25b), the
  -- Fairy going red (the Bottle note above), and the Ruby vanishing on a looted
  -- chest $14. Each time the item silently blanked and then fought the player's
  -- clicks, because applyRamRules re-runs every scan.
  --
  -- The board still walks back: RAM stays authoritative, which is what makes
  -- loading an older save drop what that save had not collected. Only the
  -- present -> absent transition is reported, and only once per code, so a new
  -- game does not narrate every item nobody has yet.
  --
  -- And a snapshot cannot tell the two apart. Loading a save from before the
  -- Ruby was picked up is the same transition as a turn-in rule reading the
  -- wrong bit, so the line names both rather than accusing the rule -- a
  -- diagnostic that cries wrong-bit at an ordinary save load is one nobody will
  -- believe the third time.
  for code in pairs(RAM_CODES) do
    if RAM_TURN_IN[code] and best[code] == nil and LAST_RAM_STAGE[code] ~= nil
       and not VANISH_WARNED[code] then
      VANISH_WARNED[code] = true
      print(string.format(
        "ram: %s was at stage %d and now matches no rule -- expected if you "
        .. "just loaded an older save; if the cartridge still has it, a turn-in "
        .. "rule is reading the wrong bit",
        code, LAST_RAM_STAGE[code]))
    end
    LAST_RAM_STAGE[code] = best[code]
    applyCode(code, best[code], not apOwned(code))
  end
end
