-- RAM-derived codes: the real rules, applied to a synthetic memory image.
local PACK = arg[1]
local json = dofile(PACK .. "/tests/json.lua")

AUTOTRACKER_ENABLE_DEBUG_LOGGING = false

-- Build stub tracker objects from the pack's real item definitions, so stage
-- counts and code names come from the JSON rather than from assumptions.
local objects = {}
local stageCount = {}
for _, file in ipairs({ "items/items.json", "items/hosted_items.json", "items/flags.json", "items/shards.json" }) do
  for _, it in ipairs(json.load(PACK .. "/" .. file)) do
    local codes = {}
    if it.codes then
      for c in tostring(it.codes):gmatch("[^,]+") do codes[#codes + 1] = c:match("^%s*(.-)%s*$") end
    end
    if it.stages and it.stages[1] and it.stages[1].codes then
      for c in tostring(it.stages[1].codes):gmatch("[^,]+") do codes[#codes + 1] = c:match("^%s*(.-)%s*$") end
    end
    for _, c in ipairs(codes) do
      objects[c] = { Active = false, CurrentStage = 0 }
      stageCount[c] = it.stages and #it.stages or 1
    end
  end
end

Tracker = {
  ActiveVariantUID = "5standard",
  FindObjectForCode = function(self, code) return objects[code] end,
}

dofile(PACK .. "/scripts/autotracking/ram_mapping.lua")
dofile(PACK .. "/scripts/logic.lua")

local MEM = {}
local function byteAt(addr) return MEM[addr] or 0 end
local function reset()
  MEM = {}
  for _, o in pairs(objects) do o.Active = false; o.CurrentStage = 0 end
end

local fail = 0
local function check(name, got, want)
  if got ~= want then
    print(string.format("FAIL %-50s got=%s want=%s", name, tostring(got), tostring(want)))
    fail = fail + 1
  else
    print(string.format("ok   %-50s %s", name, tostring(got)))
  end
end

-- 1. Garland, the thing that started this
reset()
check("garland starts inactive", objects.garland.Active, false)
MEM[0x6202] = 0x01                       -- object visible, not yet defeated
applyRamRules(byteAt)
check("garland: visible bit alone does nothing", objects.garland.Active, false)
MEM[0x6202] = 0x02                       -- defeated: visible cleared, event set
applyRamRules(byteAt)
check("garland: event bit sets it", objects.garland.Active, true)

-- 2. Vampire, same routine
reset()
MEM[0x620C] = 0x02
applyRamRules(byteAt)
check("vampire set by event bit", objects.vampire.Active, true)

-- 3. Orbs -> canBreakOrb(), the gate nothing could satisfy before
reset()
check("canBreakOrb false with no orbs", canBreakOrb(), false)
MEM[0x6031], MEM[0x6032], MEM[0x6033] = 1, 1, 1
applyRamRules(byteAt)
check("three orbs is not enough", canBreakOrb(), false)
MEM[0x6034] = 1
applyRamRules(byteAt)
check("earth orb lit -> stage 1", objects.earthorb.CurrentStage, 1)
check("air orb lit -> stage 1", objects.airorb.CurrentStage, 1)
check("canBreakOrb true with all four lit", canBreakOrb(), true)

-- 4. Turn-ins: holding, then handed over (item byte is consumed)
reset()
MEM[0x6022] = 1                          -- holding Crown
applyRamRules(byteAt)
check("crown held -> stage 0 active", objects.crown.Active, true)
check("crown held -> stage 0", objects.crown.CurrentStage, 0)
MEM[0x6022] = 0                          -- traded away
MEM[0x6207] = 0x02                       -- Astos event
applyRamRules(byteAt)
check("crown traded -> stage 1", objects.crown.CurrentStage, 1)

-- 5. Slab's two turn-ins
reset()
MEM[0x6028] = 1
applyRamRules(byteAt)
check("slab held -> stage 0", objects.slab.CurrentStage, 0)
MEM[0x620B] = 0x02                       -- Unne translated
applyRamRules(byteAt)
check("slab translated -> stage 1", objects.slab.CurrentStage, 1)
MEM[0x620F] = 0x02                       -- Lefein
applyRamRules(byteAt)
check("slab turned in -> stage 2", objects.slab.CurrentStage, 2)

-- 6. Raise-only: dropping the RAM bit must not walk anything back
MEM[0x620F], MEM[0x620B], MEM[0x6028] = 0, 0, 0
applyRamRules(byteAt)
check("stage holds when RAM bit clears", objects.slab.CurrentStage, 2)
check("Active holds when RAM bit clears", objects.slab.Active, true)

-- ...and a manually advanced stage is never lowered
reset()
objects.crown.Active, objects.crown.CurrentStage = true, 1
MEM[0x6022] = 1                          -- RAM only proves stage 0
applyRamRules(byteAt)
check("manual stage 1 not lowered to 0", objects.crown.CurrentStage, 1)

-- 7. canal is inverted
reset()
MEM[0x600C] = 1                          -- canal object still there = not dug
applyRamRules(byteAt)
check("canal NOT set while byte nonzero", objects.canal.Active, false)
MEM[0x600C] = 0
applyRamRules(byteAt)
check("canal set when byte reads zero", objects.canal.Active, true)

-- 8. vehicles
reset()
MEM[0x6000], MEM[0x6008], MEM[0x6012] = 1, 1, 1
applyRamRules(byteAt)
check("ship", objects.ship.Active, true)
check("bridge", objects.bridge.Active, true)
check("canoe", objects.canoe.Active, true)

-- 9. floater then airship
reset()
MEM[0x602B] = 1
applyRamRules(byteAt)
check("floater held -> stage 0", objects.floater.CurrentStage, 0)
MEM[0x6004] = 1
applyRamRules(byteAt)
check("airship -> floater stage 1", objects.floater.CurrentStage, 1)

-- 10. shards match the AP feed's convention (N shards -> stage N-1)
reset()
MEM[0x6035] = 1
applyRamRules(byteAt)
check("1 shard -> active, stage 0", objects.shards.CurrentStage, 0)
check("1 shard -> active", objects.shards.Active, true)
MEM[0x6035] = 25
applyRamRules(byteAt)
check("25 shards -> stage 24", objects.shards.CurrentStage, 24)
MEM[0x6035] = 99
applyRamRules(byteAt)
check("99 shards clamps to max stage", objects.shards.CurrentStage, RAM_SHARDS.maxStage)
check("max stage matches shards.json", RAM_SHARDS.maxStage, stageCount["shards"] - 1)

-- 11. every code the rules mention actually exists in the pack
local unknown = {}
for _, rule in ipairs(RAM_RULES) do
  if not objects[rule.code] then unknown[rule.code] = true end
end
if not objects[RAM_SHARDS.code] then unknown[RAM_SHARDS.code] = true end
local list = {}
for c in pairs(unknown) do list[#list + 1] = c end
table.sort(list)
check("all rule codes exist in the pack", #list == 0 and "none" or table.concat(list, ","), "none")

-- 12. chaos stays manual -- see the $62FE collision note in ram_mapping.lua
local mentionsChaos = false
for _, rule in ipairs(RAM_RULES) do
  if rule.code == "chaos" then mentionsChaos = true end
end
check("chaos is not RAM-derived", mentionsChaos, false)

print(fail == 0 and "\nALL PASS" or string.format("\n%d FAILURE(S)", fail))
os.exit(fail == 0 and 0 or 1)
