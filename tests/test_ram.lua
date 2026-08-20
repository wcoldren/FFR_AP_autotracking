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
local function reset()
  MEM = {}
  rebuild()
end

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
MEM[0x6214] = 0x02  -- Titan
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
-- sigil and mark share bytes with floater and canoe in no-overworld mode, so
-- nothing here may write them -- in either direction.
------------------------------------------------------------------
reset()
MEM[0x602B], MEM[0x6012] = 1, 1
applyRamRules(byteAt)
check("sigil untouched by floater's byte", provided("sigil"), false)
check("mark untouched by canoe's byte", provided("mark"), false)
byCode["sigil"].Active = true
byCode["mark"].Active = true
MEM[0x602B], MEM[0x6012] = 0, 0
applyRamRules(byteAt)
check("sigil survives a clearing pass", provided("sigil"), true)
check("mark survives a clearing pass", provided("mark"), true)
clearRamDerivedItems()
check("sigil survives the ROM-change wipe", provided("sigil"), true)
check("mark survives the ROM-change wipe", provided("mark"), true)

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

-- shards has allow_disabled:false, so no offset, and the AP feed leaves
-- CurrentStage at count-1. Match it exactly or the feeds disagree.
reset()
MEM[0x6035] = 12
applyRamRules(byteAt)
check("shards follows the count up", byCode["shards"].CurrentStage, 11)
MEM[0x6035] = 3
applyRamRules(byteAt)
check("shards follows the count down", byCode["shards"].CurrentStage, 2)
MEM[0x6035] = 0
applyRamRules(byteAt)
check("shards clears at zero", byCode["shards"].CurrentStage, 0)

reset()
MEM[0x6035] = 1
applyRamRules(byteAt)
check("1 shard -> stage 0", byCode["shards"].CurrentStage, 0)
MEM[0x6035] = 25
applyRamRules(byteAt)
check("25 shards -> stage 24", byCode["shards"].CurrentStage, 24)
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
