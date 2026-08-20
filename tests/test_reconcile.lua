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

-- A section path that is not a "@" location: reconcile drives those as a
-- plain toggle, and the manual-clear handling differs between the two.
local TOGGLE = "toggleSection"
LOCATION_MAPPING[999004] = { TOGGLE }

-- Build stub sections sized to however many ids the mapping points at them,
-- so counts are internally consistent for the test.
local counts, hosted = {}, {}
for id, v in pairs(LOCATION_MAPPING) do
  if v[1] then counts[v[1]] = (counts[v[1]] or 0) + 1 end
  if v[2] then hosted[v[2]] = true end
end
for path, n in pairs(counts) do
  if path:sub(1, 1) == "@" then mkSection(path, n) else mkItem(path) end
end
for code in pairs(hosted) do mkItem(code) end

-- A path naming a section the pack does not have is the failure that looks
-- exactly like "I opened the chest and nothing happened", so it has to be
-- reported without anyone having to turn debug logging on first. Added after
-- the stubs are built, so nothing answers for it.
LOCATION_MAPPING[999998] = { "@Nowhere At All/Chest" }

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

-- The audit runs once, on the first data from either feed, so it has to be
-- checked before anything else touches reconcile.
do
  local said = {}
  local realPrint = print
  print = function(...) said[#said + 1] = table.concat({ ... }, " ") end
  reconcileInit()
  print = realPrint
  local found = false
  for _, line in ipairs(said) do
    if line:find("Nowhere At All", 1, true) then found = true end
  end
  check("unresolved section is reported at startup", found, true)
  LOCATION_MAPPING[999998] = nil
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

-- 10. a clear the player made by hand is not undone by the next feed update.
--     applyAll() runs on every ff1/mem change, which during play is every few
--     seconds, so a recompute that ignored the player would wipe the click
--     almost immediately.
resetChecked()
setUATChecked({})
check("section starts full", sec.AvailableChestCount, full)
sec.AvailableChestCount = full - 1                        -- player clicks one
setUATChecked({})                                         -- next RAM tick, no news
check("manual clear survives an idle tick", sec.AvailableChestCount, full - 1)
setUATChecked({ [multiIds[1]] = true })
check("manual clear survives a feed check", sec.AvailableChestCount, full - 2)
setUATChecked({})                                         -- older save loaded
check("older save un-marks the feed's chest only", sec.AvailableChestCount, full - 1)
sec.AvailableChestCount = full                            -- player un-clicks it
setUATChecked({})
check("un-clicking releases the manual clear", sec.AvailableChestCount, full)

-- 11. and onClear really is a full wipe, manual clears included
sec.AvailableChestCount = full - 1
setUATChecked({})
check("manual clear held before reset", sec.AvailableChestCount, full - 1)
resetChecked()
check("resetChecked drops manual clears too", sec.AvailableChestCount, full)

-- 12. the same, for a section reconcile drives as a toggle
local tog = objects[TOGGLE]
setUATChecked({ [999004] = true })
check("toggle set by the feed", tog.Active, true)
setUATChecked({})
check("toggle released by the feed", tog.Active, false)
tog.Active = true                                         -- player clicks it
setUATChecked({})
check("manual toggle survives a feed tick", tog.Active, true)
tog.Active = false                                        -- player un-clicks it
setUATChecked({})
check("un-clicking releases the manual toggle", tog.Active, false)

-- 13. we are not the only writer. PopTracker restores its own saved state
--     after the pack's scripts have run, and a pack reload does the same
--     mid-session. Read as hand clears those become offsets that outlive
--     every later feed update, which pins the whole board cleared -- the
--     board then cannot be corrected by correct RAM, which is exactly the
--     failure this guards.
resetChecked()
setUATChecked({})
local sections = {}
for path, o in pairs(objects) do
  if o.ChestCount and o.ChestCount > 0 then sections[#sections + 1] = path end
end
check("harness has enough sections to be bulk", #sections > 10, true)

for _, path in ipairs(sections) do objects[path].AvailableChestCount = 0 end
setUATChecked({})                                  -- next RAM tick, no news
local stillCleared = 0
for _, path in ipairs(sections) do
  local o = objects[path]
  if o.AvailableChestCount ~= o.ChestCount then stillCleared = stillCleared + 1 end
end
check("a mass move is not taken as hand clears", stillCleared, 0)

-- and it stays corrected: the offsets were never recorded, so later ticks
-- have nothing to re-apply
setUATChecked({ [multiIds[1]] = true })
check("the feed still owns its own checks", sec.AvailableChestCount, full - 1)
setUATChecked({})
check("and releases them again", sec.AvailableChestCount, full)

-- 14. one hand clear still survives, right after a bulk event -- the guard
--     keys on how many moved at once, not on having seen one.
sec.AvailableChestCount = full - 1
setUATChecked({})
check("a single hand clear still sticks", sec.AvailableChestCount, full - 1)
sec.AvailableChestCount = full
setUATChecked({})
check("and is still released by un-clicking", sec.AvailableChestCount, full)

print(fail == 0 and "\nALL PASS" or string.format("\n%d FAILURE(S)", fail))
os.exit(fail == 0 and 0 or 1)
