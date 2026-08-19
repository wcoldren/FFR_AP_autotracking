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
check("canBreakOrb false with no orbs", canBreakOrb(), false)
MEM[0x6031], MEM[0x6032], MEM[0x6033] = 1, 1, 1
applyRamRules(byteAt)
check("three orbs is not enough", canBreakOrb(), false)
MEM[0x6034] = 1
applyRamRules(byteAt)
check("earth orb lit provides 'earthorblit'", provided("earthorblit"), true)
check("air orb lit provides 'airorblit'", provided("airorblit"), true)
check("lit orb still provides base 'earthorb'", provided("earthorb"), true)
check("canBreakOrb true with all four lit", canBreakOrb(), true)
check("I: Earth Orb incentive marker clears", markerCleared("earthorblit"), true)

------------------------------------------------------------------
-- Raise-only
------------------------------------------------------------------
reset()
MEM[0x6028] = 1
MEM[0x620B] = 0x02
MEM[0x620F] = 0x02
applyRamRules(byteAt)
MEM[0x6028], MEM[0x620B], MEM[0x620F] = 0, 0, 0
applyRamRules(byteAt)
check("stage holds when RAM bits clear", provided("slabDone"), true)

reset()
byCode["crown"].Active = true
byCode["crown"].CurrentStage = 2                 -- manually advanced to crownDone
MEM[0x6022] = 1                                  -- RAM only proves "holding"
applyRamRules(byteAt)
check("manual crownDone not walked back", provided("crownDone"), true)

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
