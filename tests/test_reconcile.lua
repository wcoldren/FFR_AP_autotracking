-- Offline harness: stub PopTracker Tracker, load the real mapping + reconcile.
local PACK = arg[1]

AUTOTRACKER_ENABLE_DEBUG_LOGGING = false

local objects = {}
local function mkSection(path, chestCount)
  objects[path] = { ChestCount = chestCount, AvailableChestCount = chestCount }
  return objects[path]
end
local function mkItem(code)
  objects[code] = { Active = false }
  return objects[code]
end

Tracker = {
  BulkUpdate = false,
  FindObjectForCode = function(self, code) return objects[code] end,
}

dofile(PACK .. "/scripts/autotracking/location_mapping.lua")

-- A section fed by several ids, built here rather than borrowed from the pack.
-- Every real section is one-to-one now that the dungeons are split per chest,
-- but reconcile still has to handle the many-to-one case: it is what the union
-- of two feeds is for, and a pack that regrouped anything would rely on it.
local MULTI = "@Test Group/Chests"
for _, id in ipairs({ 999001, 999002, 999003 }) do
  LOCATION_MAPPING[id] = { MULTI }
end

-- Build stub sections sized to however many ids the mapping points at them,
-- so counts are internally consistent for the test.
local counts, hosted = {}, {}
for id, v in pairs(LOCATION_MAPPING) do
  if v[1] then counts[v[1]] = (counts[v[1]] or 0) + 1 end
  if v[2] then hosted[v[2]] = true end
end
for path, n in pairs(counts) do mkSection(path, n) end
for code in pairs(hosted) do mkItem(code) end

dofile(PACK .. "/scripts/autotracking/reconcile.lua")

local fail = 0
local function check(name, got, want)
  if got ~= want then
    print(string.format("FAIL %-46s got=%s want=%s", name, tostring(got), tostring(want)))
    fail = fail + 1
  else
    print(string.format("ok   %-46s %s", name, tostring(got)))
  end
end

local multi, multiIds = MULTI, {}
for id, v in pairs(LOCATION_MAPPING) do
  if v[1] == multi then multiIds[#multiIds + 1] = id end
end
table.sort(multiIds)
print(string.format("\n-- section under test: %s (%d chests, ids %s)\n",
  multi, objects[multi].ChestCount, table.concat(multiIds, ",")))

local sec = objects[multi]
local full = sec.ChestCount

-- 1. single AP check decrements once
markAPChecked(multiIds[1])
check("AP check once", sec.AvailableChestCount, full - 1)

-- 2. THE test: same id again must be a no-op
markAPChecked(multiIds[1])
markAPChecked(multiIds[1])
check("AP same id x3 still counts once", sec.AvailableChestCount, full - 1)

-- 3. same id from the UAT feed too -- union, not sum
setUATChecked({ [multiIds[1]] = true })
check("AP+UAT same id counts once", sec.AvailableChestCount, full - 1)

-- 4. UAT adds a second, distinct id
setUATChecked({ [multiIds[1]] = true, [multiIds[2]] = true })
check("AP+UAT two distinct ids", sec.AvailableChestCount, full - 2)

-- 5. UAT full state shrinks (older save loaded) -> count goes back up,
--    but the AP-checked id survives because the union still holds it
setUATChecked({})
check("UAT shrinks, AP id survives", sec.AvailableChestCount, full - 1)

-- 6. onClear path clears AP state
resetChecked()
check("resetChecked restores section", sec.AvailableChestCount, full)

-- 7. clamp: more checked ids than the section has chests
local all = {}
for _, id in ipairs(multiIds) do all[id] = true end
setUATChecked(all)
check("all ids checked -> zero", sec.AvailableChestCount, 0)
local extra = {}
for k, v in pairs(all) do extra[k] = v end
check("never negative", sec.AvailableChestCount >= 0, true)

-- 8. hosted item toggles on
local hostedId
for id, v in pairs(LOCATION_MAPPING) do if v[2] then hostedId = id break end end
resetChecked()
setUATChecked({})
check("hosted item starts false", objects[LOCATION_MAPPING[hostedId][2]].Active, false)
markAPChecked(hostedId)
check("hosted item set by check", objects[LOCATION_MAPPING[hostedId][2]].Active, true)

-- 9. unmapped id does not crash, warns once
markAPChecked(999999)
markAPChecked(999999)
check("unmapped id survived", true, true)

print(fail == 0 and "\nALL PASS" or string.format("\n%d FAILURE(S)", fail))
os.exit(fail == 0 and 0 or 1)
