-- RAM-derived codes, checked against a PopTracker-faithful item model.
--
-- Assertions are on the CODES an item ends up providing, not on stage numbers.
-- Codes are what actually drive the UI: an item icon shows its stage's art,
-- and a hosted-item section clears when every code it hosts has a provider
-- (locationsection.cpp:236-247). Testing stage numbers instead is what let the
-- turn-in off-by-one ship.
local PACK = arg[1]
local json = dofile(PACK .. "/tests/json.lua")
local ItemModel = dofile(PACK .. "/tests/item_model.lua")

AUTOTRACKER_ENABLE_DEBUG_LOGGING = false

local ITEM_FILES = {
  "items/items.json", "items/hosted_items.json",
  "items/flags.json", "items/shards.json",
}
local byCode, allItems

local function rebuild()
  byCode, allItems = ItemModel.loadPack(json, PACK, ITEM_FILES)
end
rebuild()

Tracker = {
  ActiveVariantUID = "5standard",
  FindObjectForCode = function(self, code) return byCode[code] end,
  ProviderCountForCode = function(self, code)
    local n = 0
    for _, item in ipairs(allItems) do n = n + item:providesCode(code) end
    return n
  end,
}

dofile(PACK .. "/scripts/autotracking/ram_mapping.lua")
dofile(PACK .. "/scripts/logic.lua")

local MEM = {}
local function byteAt(addr) return MEM[addr] or 0 end

-- Game flags that a freshly initialised save does NOT start at zero, so a test
-- that says nothing about them describes a real new game rather than an
-- impossible one. Read out of lut_InitGameFlags ($AF00, BANK_STARTUPINFO, bank
-- 0 -> file offset 0x2F10): object $14 starts at 0x01, GMFLG_OBJVISIBLE.
--
-- It matters because Titan is read as "the object is gone" rather than as an
-- event bit -- see the ruby rules in ram_mapping.lua. Defaulting him to 0 would
-- have every case here open with the Ruby already eaten.
local INIT_FLAGS = { [0x6214] = 0x01 }   -- Titan, visible

local function reset()
  MEM = {}
  for addr, v in pairs(INIT_FLAGS) do MEM[addr] = v end
  rebuild()
  -- Each case is a different cartridge, not the next scan of the last one, so
  -- drop the derived-stage history too. clearRamDerivedItems() does this in
  -- production; doing it by hand here keeps the item model rebuild above as the
  -- only thing reset() owns.
  LAST_RAM_STAGE, VANISH_WARNED = {}, {}
end
reset()

local fail = 0
local function check(name, got, want)
  if got ~= want then
    print(string.format("FAIL %-52s got=%s want=%s", name, tostring(got), tostring(want)))
    fail = fail + 1
  else
    print(string.format("ok   %-52s %s", name, tostring(got)))
  end
end
local function provided(code) return Tracker:ProviderCountForCode(code) >= 1 end

-- Mirrors locationsection.cpp:236-247 for a section with no item_count:
-- CLEARED once every hosted code has a provider.
local function markerCleared(...)
  for _, code in ipairs({ ... }) do
    if not provided(code) then return false end
  end
  return true
end

------------------------------------------------------------------
-- The turn-ins that prompted this
------------------------------------------------------------------

-- Bahamut's Tail
reset()
MEM[0x602D] = 1                                  -- holding the Tail
applyRamRules(byteAt)
check("tail held provides 'tail'", provided("tail"), true)
check("tail held does NOT provide 'bahamut'", provided("bahamut"), false)
MEM[0x602D] = 0                                  -- consumed by the class change
MEM[0x620E] = 0x02                               -- Bahamut event flag
applyRamRules(byteAt)
check("Bahamut done provides 'bahamut'", provided("bahamut"), true)
check("Bahamut's Cave marker clears", markerCleared("bahamut"), true)

-- The airship
reset()
MEM[0x602B] = 1                                  -- holding the Floater
applyRamRules(byteAt)
check("floater held provides 'inactiveFloater'", provided("inactiveFloater"), true)
check("floater held does NOT provide 'airship'", provided("airship"), false)
MEM[0x6004] = 1                                  -- airship_vis
applyRamRules(byteAt)
check("airship provides 'airship'", provided("airship"), true)
check("Floater Turn In marker clears", markerCleared("airship"), true)

-- The rest of the turn-in family
reset()
MEM[0x6207] = 0x02  -- Astos
MEM[0x620A] = 0x02  -- Matoya
MEM[0x6205] = 0x02  -- Elf Doctor
MEM[0x6208] = 0x02  -- Nerrick
MEM[0x6209] = 0x02  -- Smith
MEM[0x6214] = 0x00  -- Titan fed: the object goes away, no event bit is set
MEM[0x6213] = 0x02  -- Fairy
applyRamRules(byteAt)
check("Astos  -> crownDone",    provided("crownDone"), true)
check("Matoya -> crystalDone",  provided("crystalDone"), true)
check("ElfDoc -> herbDone",     provided("herbDone"), true)
check("Nerrick-> tntDone",      provided("tntDone"), true)
check("Smith  -> adamantDone",  provided("adamantDone"), true)
check("Titan  -> titan",        provided("titan"), true)
check("Fairy  -> bottlepopped", provided("bottlepopped"), true)

-- Slab: two turn-ins, and the earlier code must survive the later one
reset()
MEM[0x6028] = 1
applyRamRules(byteAt)
check("slab held provides 'slab'", provided("slab"), true)
check("slab held does NOT provide 'slabTranslated'", provided("slabTranslated"), false)
MEM[0x620B] = 0x02                               -- Unne translates it
applyRamRules(byteAt)
check("Unne -> slabTranslated", provided("slabTranslated"), true)
check("Dr Unne marker clears", markerCleared("slabTranslated"), true)
MEM[0x620F] = 0x02                               -- Lefein takes it
applyRamRules(byteAt)
check("Lefein -> slabDone", provided("slabDone"), true)
check("Lefein -> slabTurnIn", provided("slabTurnIn"), true)
-- inherit_codes defaults true, so stage 2 still provides stage 1's codes and
-- the Dr Unne marker does not revert to green
check("slabTranslated survives stage 2", provided("slabTranslated"), true)
check("Dr Unne marker stays cleared", markerCleared("slabTranslated"), true)

-- The Bottle is the one item spent by using it rather than by a turn-in: the
-- inventory byte clears the moment it is popped, while the Fairy's event bit
-- does not arrive until she is talked to, potentially hours later. @Gaia/Fairy
-- is gated on the bare `bottle` code, so the popped state has to hold that
-- code across the whole gap or the check falls out of logic while it is open.
reset()
MEM[0x602F] = 1
applyRamRules(byteAt)
check("bottle held provides 'bottle'", provided("bottle"), true)
check("bottle held is not popped yet", provided("bottlepopped"), false)
MEM[0x602F] = 0                                  -- UseItem_Bottle empties it
MEM[0x6213] = 0x01                               -- ShowMapObject(OBJID_FAIRY)
applyRamRules(byteAt)
check("popped bottle keeps 'bottle'", provided("bottle"), true)
check("popped bottle provides 'bottlepopped'", provided("bottlepopped"), true)
MEM[0x6213] = 0x03                               -- then the Fairy hands over
applyRamRules(byteAt)
check("fairy turn-in keeps 'bottle'", provided("bottle"), true)
check("fairy turn-in keeps 'bottlepopped'", provided("bottlepopped"), true)

-- The Ruby's consequence outlives the item by the widest margin of any turn-in:
-- Talk_Titan takes it, and from that moment Titan's Tunnel is simply open for
-- the rest of the seed. Both Titan's Trove and Sarda's Cave gate on the bare
-- `ruby` code, so if the spent Ruby stopped providing it, the chests behind
-- Titan would go red on the seed where they had just opened -- the same shape
-- of bug as the Bottle above, but on four chests and Sarda rather than one NPC.
--
-- Stage 1 carries "ruby,titan" for exactly this reason. These cases pin the
-- real access_rules out of locations/overworld.json to it rather than asserting
-- on the code alone, so a later edit that swaps `ruby` for a code the consumed
-- state does not provide fails here instead of in someone's run.
local OVERWORLD = json.load(PACK .. "/locations/overworld.json")

-- First node with this name, depth first. Names are unique in the tree.
local function findLocation(nodes, name)
  for _, node in ipairs(nodes or {}) do
    if node.name == name then return node end
    local hit = findLocation(node.children, name)
    if hit then return hit end
  end
end

-- One access_rules entry: comma-separated terms, all of which must hold.
-- Only the two forms these locations use are understood; anything else is a
-- hard error rather than a quiet pass, so the day a rule grows a `@section`
-- or a `count:` term this stops claiming to have checked it.
local function ruleHolds(rule)
  for raw in string.gmatch(rule, "[^,]+") do
    local term = raw:match("^%s*(.-)%s*$")
    local held
    if term:sub(1, 1) == "$" then
      local fn = _G[term:sub(2)]
      if not fn then error("access rule calls unknown logic function " .. term) end
      held = (fn() or 0) > 0
    elseif term:match("^[%w_]+$") then
      held = provided(term)
    else
      error("test cannot evaluate access rule term: " .. term)
    end
    if not held then return false end
  end
  return true
end

-- PopTracker takes a location as reachable if ANY of its access_rules holds.
local function inLogic(name)
  local node = findLocation(OVERWORLD, name)
  if not node then error("no location named " .. name .. " in overworld.json") end
  if not node.access_rules or #node.access_rules == 0 then return true end
  for _, rule in ipairs(node.access_rules) do
    if ruleHolds(rule) then return true end
  end
  return false
end

reset()
-- A forested seed, so the one Sarda route that does not need the Ruby
-- ($noSardasForest,airship) is closed and both locations really do hang on it.
byCode["sardasForest"].Active = true
MEM[0x602B] = 1                                  -- Floater
MEM[0x6004] = 1                                  -- airship flying
MEM[0x6029] = 1                                  -- Ruby in the bag
applyRamRules(byteAt)
check("ruby held provides 'ruby'", provided("ruby"), true)
check("ruby held does NOT provide 'titan'", provided("titan"), false)
check("ruby held: Titan's Trove in logic", inLogic("Titan's Trove"), true)
check("ruby held: Sarda's Cave in logic", inLogic("Sarda's Cave"), true)

MEM[0x6029] = 0                                  -- Talk_Titan eats the Ruby
MEM[0x6214] = 0x00                               -- and hides him; no flag is set
applyRamRules(byteAt)
check("spent ruby keeps 'ruby'", provided("ruby"), true)
check("Titan done provides 'titan'", provided("titan"), true)
check("spent ruby: Titan's Trove stays in logic", inLogic("Titan's Trove"), true)
check("spent ruby: Sarda's Cave stays in logic", inLogic("Sarda's Cave"), true)

-- Attaching the tracker to a save that is already past Titan never sees the
-- stage-0 sighting at all, so stage 1 has to stand on the event flag alone.
reset()
byCode["sardasForest"].Active = true
MEM[0x602B] = 1
MEM[0x6004] = 1
MEM[0x6214] = 0x00                               -- only his absence survives
applyRamRules(byteAt)
check("cold start past Titan provides 'ruby'", provided("ruby"), true)
check("cold start past Titan: Titan's Trove in logic", inLogic("Titan's Trove"), true)
check("cold start past Titan: Sarda's Cave in logic", inLogic("Sarda's Cave"), true)

-- The negative: without the Ruby a forested Sarda and the Trove are both shut,
-- so the cases above are not passing on some unrelated always-true route.
reset()
byCode["sardasForest"].Active = true
MEM[0x602B] = 1
MEM[0x6004] = 1
applyRamRules(byteAt)
check("no ruby: Titan's Trove out of logic", inLogic("Titan's Trove"), false)
check("no ruby: Sarda's Cave out of logic", inLogic("Sarda's Cave"), false)

-- $6214 is not Titan's byte alone. The flag array is a shared id space: byte i
-- carries chest i's opened bit (0x04) as well as event i's (0x02), and index
-- $14 is both OBJID_TITAN and chest $14. Every case above leaves that chest
-- shut, which is why a rule reading the whole byte passed here for months and
-- still blanked the Ruby on a real save the moment the chest was looted.
--
-- The two states below are transcribed from saves: 0x04 is fed-with-the-chest-
-- open, 0x05 is still-standing-with-the-chest-open.
reset()
byCode["sardasForest"].Active = true
MEM[0x602B] = 1
MEM[0x6004] = 1
MEM[0x6029] = 0                                  -- Ruby eaten
MEM[0x6214] = 0x04                               -- Titan gone, chest $14 looted
applyRamRules(byteAt)
check("fed Titan with chest $14 open keeps 'ruby'", provided("ruby"), true)
check("fed Titan with chest $14 open provides 'titan'", provided("titan"), true)
check("fed + chest open: Titan's Trove in logic", inLogic("Titan's Trove"), true)
check("fed + chest open: Sarda's Cave in logic", inLogic("Sarda's Cave"), true)

-- The other half of the same trap. Reading 0x04 as the turn-in -- by masking
-- 0x04, or 0x06 -- would call Titan fed here, while he is still standing and
-- the Ruby is still in the bag.
reset()
byCode["sardasForest"].Active = true
MEM[0x602B] = 1
MEM[0x6004] = 1
MEM[0x6029] = 1                                  -- Ruby still held
MEM[0x6214] = 0x05                               -- Titan visible, chest $14 looted
applyRamRules(byteAt)
check("chest $14 alone does NOT feed Titan", provided("titan"), false)
check("chest $14 alone leaves 'ruby' held", provided("ruby"), true)

------------------------------------------------------------------
-- Bosses
------------------------------------------------------------------
reset()
MEM[0x6202] = 0x01                               -- visible, not yet fought
applyRamRules(byteAt)
check("garland: visible bit alone does nothing", provided("garland"), false)
MEM[0x6202] = 0x02                               -- defeated
applyRamRules(byteAt)
check("garland: event bit sets it", provided("garland"), true)
check("Temple of Fiends Garland marker clears", markerCleared("garland"), true)

reset()
MEM[0x620C] = 0x02
applyRamRules(byteAt)
check("vampire set by event bit", provided("vampire"), true)

------------------------------------------------------------------
-- Orbs. These take the other path -- allow_disabled is false, so no offset --
-- which is why they worked while every turn-in did not.
------------------------------------------------------------------
reset()
check("canBreakOrb 0 with no orbs", canBreakOrb(), 0)
MEM[0x6031], MEM[0x6032], MEM[0x6033] = 1, 1, 1
applyRamRules(byteAt)
check("three orbs is not enough", canBreakOrb(), 0)
MEM[0x6034] = 1
applyRamRules(byteAt)
check("earth orb lit provides 'earthorblit'", provided("earthorblit"), true)
check("air orb lit provides 'airorblit'", provided("airorblit"), true)
check("lit orb still provides base 'earthorb'", provided("earthorb"), true)
check("canBreakOrb 1 with all four lit", canBreakOrb(), 1)
check("I: Earth Orb incentive marker clears", markerCleared("earthorblit"), true)

------------------------------------------------------------------
-- ChaosRush. ToFR's chests and the Chaos fight sit behind the lute plate and
-- a key-locked door; EnableChaosRush rewrites that door's tile properties as
-- an ordinary door (FF1Lib/TempleOfFiends.cs:496-500, tileset ToFR only), so
-- the Key stops being the thing that opens the floor. The Lute is not touched
-- -- the plate is an object gate, not this tile.
------------------------------------------------------------------
reset()
MEM[0x6031], MEM[0x6032], MEM[0x6033], MEM[0x6034] = 1, 1, 1, 1   -- four orbs lit
MEM[0x6021] = 1                                  -- Lute
applyRamRules(byteAt)
check("orbs and lute, no key: ToFR out of logic", inLogic("ToFR"), false)
byCode["chaosRush"].Active = true
check("chaosRush opens ToFR without the key", inLogic("ToFR"), true)

-- And the ordinary route is untouched: the Key still opens it on a seed that
-- did not roll the flag.
byCode["chaosRush"].Active = false
MEM[0x6025] = 1                                  -- Key
applyRamRules(byteAt)
check("the key still opens ToFR without chaosRush", inLogic("ToFR"), true)

-- The Lute is not what ChaosRush buys, so it is still required either way.
reset()
MEM[0x6031], MEM[0x6032], MEM[0x6033], MEM[0x6034] = 1, 1, 1, 1
MEM[0x6025] = 1                                  -- Key but no Lute
applyRamRules(byteAt)
byCode["chaosRush"].Active = true
check("chaosRush does not replace the lute", inLogic("ToFR"), false)
byCode["chaosRush"].Active = false

------------------------------------------------------------------
-- RAM is authoritative, in both directions. This used to be raise-only, which
-- is how a finished seed's orbs, key items and turn-ins survived into the next
-- one: the new game's zeroed bytes had no way to take them back down.
------------------------------------------------------------------
reset()
MEM[0x6028] = 1
MEM[0x620B] = 0x02
MEM[0x620F] = 0x02
applyRamRules(byteAt)
check("slab reaches Lefein's stage", provided("slabDone"), true)
MEM[0x6028], MEM[0x620B], MEM[0x620F] = 0, 0, 0
applyRamRules(byteAt)
check("stage clears when RAM bits clear", provided("slabDone"), false)
check("and the base code goes with it", provided("slab"), false)

-- Partway back, not all the way: still translated, no longer handed in.
reset()
MEM[0x6028], MEM[0x620B], MEM[0x620F] = 1, 0x02, 0x02
applyRamRules(byteAt)
MEM[0x620F] = 0
applyRamRules(byteAt)
check("slab walks back one stage", provided("slabDone"), false)
check("slab keeps the stage RAM still proves", provided("slabTranslated"), true)

reset()
byCode["crown"].Active = true
byCode["crown"].CurrentStage = 2                 -- advanced to crownDone
MEM[0x6022] = 1                                  -- RAM only proves "holding"
applyRamRules(byteAt)
check("crownDone walked back to what RAM says", provided("crownDone"), false)
check("crown still held", provided("crown"), true)

-- The whole-board wipe reconcile uses on a ROM change.
reset()
MEM[0x6031], MEM[0x6032], MEM[0x6033], MEM[0x6034] = 1, 1, 1, 1
MEM[0x6021], MEM[0x6035] = 1, 12
applyRamRules(byteAt)
check("board lit before the wipe", provided("earthorblit"), true)
clearRamDerivedItems()
check("orbs wiped", provided("earthorblit"), false)
check("key items wiped", provided("lute"), false)
-- Every shard stage provides the same "shards" code -- logic.lua reads the
-- count off CurrentStage -- so this one is asserted on the number.
check("shards wiped", byCode["shards"].CurrentStage, 0)

------------------------------------------------------------------
-- Archipelago carve-out. AP grants items through onItem and replays them only
-- on onClear, so while a session is live RAM must not clear anything AP owns.
-- Codes RAM alone owns keep following it down.
------------------------------------------------------------------
dofile(PACK .. "/scripts/autotracking/item_mapping.lua")
reset()
MEM[0x6021] = 1                                  -- lute, also an AP item
MEM[0x6202] = 0x02                               -- garland, RAM-only
MEM[0x6031] = 1                                  -- earth orb, RAM-only
applyRamRules(byteAt)
check("lute lit", provided("lute"), true)
check("garland lit", provided("garland"), true)
AP_ITEM_FEED_ACTIVE = true
MEM[0x6021], MEM[0x6202], MEM[0x6031] = 0, 0, 0
applyRamRules(byteAt)
check("AP-owned code is not cleared by RAM", provided("lute"), true)
check("RAM-only boss still clears", provided("garland"), false)
check("RAM-only orb still clears", provided("earthorblit"), false)
AP_ITEM_FEED_ACTIVE = false
applyRamRules(byteAt)
check("and clears once the AP feed is gone", provided("lute"), false)

------------------------------------------------------------------
-- sigil and mark are the floater and the canoe under Archipelago's names for
-- them on a No-Overworld seed, so the bridge sets them off the same two bytes.
--
-- This block used to assert the opposite -- that nothing here writes them --
-- on the reading that they were the item screen's renames and so had no byte
-- of their own. That is half right. The item screen renames Floater to SIGIL
-- and the *Earth Orb* to MARK, but the pack's two codes are fed by AP item ids
-- 499 and 500, and the exporter renames Floater to Sigil and the *Canoe* to
-- Mark (Archipelago.cs:287-289,339-340). Following the exporter is what makes
-- the NOverworld grid's only two gate boxes light for a bridge-fed player.
------------------------------------------------------------------
reset()
MEM[0x602B], MEM[0x6012] = 1, 1
applyRamRules(byteAt)
check("sigil follows floater's byte", provided("sigil"), true)
check("mark follows canoe's byte", provided("mark"), true)
check("floater still set alongside sigil", provided("floater"), true)
check("canoe still set alongside mark", provided("canoe"), true)
MEM[0x602B], MEM[0x6012] = 0, 0
applyRamRules(byteAt)
check("sigil clears with its byte", provided("sigil"), false)
check("mark clears with its byte", provided("mark"), false)
reset()
MEM[0x602B], MEM[0x6012] = 1, 1
applyRamRules(byteAt)
clearRamDerivedItems()
check("sigil is wiped on a ROM change", provided("sigil"), false)
check("mark is wiped on a ROM change", provided("mark"), false)

------------------------------------------------------------------
-- Vehicles, canal inversion, shards
------------------------------------------------------------------
reset()
MEM[0x600C] = 1
applyRamRules(byteAt)
check("canal NOT set while byte nonzero", provided("canal"), false)
MEM[0x600C] = 0
MEM[0x6000], MEM[0x6008], MEM[0x6012] = 1, 1, 1
applyRamRules(byteAt)
check("canal set when byte reads zero", provided("canal"), true)
check("ship", provided("ship"), true)
check("bridge", provided("bridge"), true)
check("canoe", provided("canoe"), true)

-- shards has allow_disabled:false, so RAM_NO_STAGE_OFFSET holds and the stage
-- is the count itself. Both feeds used to sit one low; see ITEM_MAPPING type
-- "count".
reset()
MEM[0x6035] = 12
applyRamRules(byteAt)
check("shards follows the count up", byCode["shards"].CurrentStage, 12)
MEM[0x6035] = 3
applyRamRules(byteAt)
check("shards follows the count down", byCode["shards"].CurrentStage, 3)
MEM[0x6035] = 0
applyRamRules(byteAt)
check("shards clears at zero", byCode["shards"].CurrentStage, 0)

reset()
MEM[0x6035] = 1
applyRamRules(byteAt)
check("1 shard -> stage 1", byCode["shards"].CurrentStage, 1)
MEM[0x6035] = 25
applyRamRules(byteAt)
check("25 shards -> stage 25", byCode["shards"].CurrentStage, 25)
MEM[0x6035] = 99
applyRamRules(byteAt)
check("99 shards clamps to max stage", byCode["shards"].CurrentStage, RAM_SHARDS.maxStage)

------------------------------------------------------------------
-- Sanity on the rule table itself
------------------------------------------------------------------
local unknown = {}
for _, rule in ipairs(RAM_RULES) do
  if not byCode[rule.code] then unknown[rule.code] = true end
end
if not byCode[RAM_SHARDS.code] then unknown[RAM_SHARDS.code] = true end
local list = {}
for c in pairs(unknown) do list[#list + 1] = c end
table.sort(list)
check("all rule codes exist in the pack", #list == 0 and "none" or table.concat(list, ","), "none")

local mentionsChaos = false
for _, rule in ipairs(RAM_RULES) do
  if rule.code == "chaos" then mentionsChaos = true end
end
check("chaos is not RAM-derived", mentionsChaos, false)

print(fail == 0 and "\nALL PASS" or string.format("\n%d FAILURE(S)", fail))
os.exit(fail == 0 and 0 or 1)
