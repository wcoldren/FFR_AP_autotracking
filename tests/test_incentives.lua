-- The incentive map's slots: shown and coloured, rather than hidden.
--
-- A slot the seed did not incentivize used to have its pin dropped by a
-- visibility_rules. It now reports Inspect instead, via `^$incentiveSlot|<flag>`
-- ANDed onto its access rules. Two things about that fail silently and so are
-- checked here rather than trusted:
--
--   * access_rules is an OR of alternatives, so the term has to be on EVERY
--     one of them. A section with the term on the first alternative only is
--     ungated through the second, and the diff looks right.
--   * a flag code that does not name a real item reads as "not incentivized"
--     forever, painting the slot blue on every seed.
local PACK = arg[1]
local json = dofile(PACK .. "/tests/json.lua")
local ItemModel = dofile(PACK .. "/tests/item_model.lua")

local INCENTIVE_FILES = {
  "locations/incentives.json",
  "locations/NOverworld/incentives.json",
}

local fail = 0
local function fails(msg)
  print("FAIL " .. msg)
  fail = fail + 1
end
local function check(name, got, want)
  if got ~= want then
    print(string.format("FAIL %-52s got=%s want=%s", name, tostring(got), tostring(want)))
    fail = fail + 1
  else
    print(string.format("ok   %-52s %s", name, tostring(got)))
  end
end

-- Walk a location file, yielding every section with its node name.
local function eachSection(tree, fn)
  local function walk(nodes)
    for _, node in ipairs(nodes) do
      for _, section in ipairs(node.sections or {}) do
        fn(node, section)
      end
      walk(node.children or {})
    end
  end
  walk(tree)
end

-- A literal "^$" -- both are magic in a Lua pattern, and the term sits at the
-- END of an alternative ("key,^$incentiveSlot|..."), so anchoring would miss it.
local TERM = "%^%$incentiveSlot|"

------------------------------------------------------------------
-- 1. Nothing hides any more, bar the one that must.
--
-- BahamutHoard is stage 2 of the cardia progressive and stands for
-- MapDragonsHoard -- a map edit. With it off those chests are not in the
-- cartridge, so a blue "there is a check here" pin would be a lie rather than
-- a demotion, and that section keeps its visibility rule.
------------------------------------------------------------------
local hidden = {}
for _, file in ipairs(INCENTIVE_FILES) do
  eachSection(json.load(PACK .. "/" .. file), function(node, section)
    if section.visibility_rules then
      hidden[#hidden + 1] = string.format("%s: %s/%s on %s", file, node.name,
        section.name, section.visibility_rules[1])
    end
  end)
end
check("only BahamutHoard still hides a pin", #hidden, 1)
if #hidden == 1 and not hidden[1]:find("BahamutHoard", 1, true) then
  fails("the surviving visibility rule is " .. hidden[1] .. ", not BahamutHoard")
end

------------------------------------------------------------------
-- 2. Every alternative carries the term, and they all name the same flag.
------------------------------------------------------------------
local gated, flagsUsed = 0, {}
for _, file in ipairs(INCENTIVE_FILES) do
  eachSection(json.load(PACK .. "/" .. file), function(node, section)
    local rules = section.access_rules or {}
    local seen = nil
    local without = 0
    for _, alt in ipairs(rules) do
      local flag = alt:match(TERM .. "([%w_]+)")
      if flag then
        if seen and seen ~= flag then
          fails(string.format("%s/%s names two flags: %s and %s",
            node.name, section.name, seen, flag))
        end
        seen = flag
      else
        without = without + 1
      end
    end
    if seen then
      gated = gated + 1
      flagsUsed[seen] = true
      if without > 0 then
        fails(string.format("%s: %s/%s has %d alternative(s) with no %s term "
          .. "-- the slot is ungated through them", file, node.name,
          section.name, without, "^$incentiveSlot"))
      end
    end
  end)
end
-- 26 gated sections in locations/incentives.json less the Bahamut hoard, plus
-- 24 in the NOverworld tree, which has neither Nerrick nor the hoard.
check("sections reporting Inspect when not incentivized", gated, 49)

------------------------------------------------------------------
-- 3. Every flag named is a real item code.
--
-- ProviderCountForCode answers 0 for a code nothing defines, exactly as it does
-- for a flag that is switched off, so a typo here would be invisible on the
-- board and permanent.
------------------------------------------------------------------
local byCode = ItemModel.loadPack(json, PACK, {
  "items/items.json", "items/hosted_items.json",
  "items/flags.json", "items/shards.json",
})
for flag in pairs(flagsUsed) do
  if not byCode[flag] then
    fails("no item defines the flag code " .. flag)
  end
end
local nflags = 0
for _ in pairs(flagsUsed) do nflags = nflags + 1 end
check("distinct incentive flags, all defined", nflags, 13)

------------------------------------------------------------------
-- 4. incentiveSlot itself.
--
-- The AccessibilityLevel numbers are PopTracker's, from
-- api/lua/definition/poptracker.lua: Inspect 3, Normal 6.
------------------------------------------------------------------
AccessibilityLevel = { None = 0, Partial = 1, Inspect = 3,
                       SequenceBreak = 5, Normal = 6, Cleared = 7 }

local provided = {}
Tracker = {
  ActiveVariantUID = "5standard",
  ProviderCountForCode = function(_, code) return provided[code] or 0 end,
  FindObjectForCode = function(_, code) return byCode[code] end,
}
dofile(PACK .. "/scripts/logic.lua")

provided = { npcsAreIncentive = 1 }
check("an incentivized slot is Normal", incentiveSlot("npcsAreIncentive"), 6)
provided = {}
check("a skipped slot is Inspect", incentiveSlot("npcsAreIncentive"), 3)

-- The cardia progressive hands out BahamutHoard only at stage 2, and stage 2
-- inherits stage 1's code -- so a hoard seed reads as both.
local cardia = byCode["cardiaIsIncentive"]
provided = {}
cardia.CurrentStage = 1
-- providesCode answers a count, and 0 is truthy in Lua -- the same trap
-- scripts/logic.lua opens by warning about.
if cardia:providesCode("cardiaIsIncentive") > 0 then provided.cardiaIsIncentive = 1 end
if cardia:providesCode("BahamutHoard") > 0 then provided.BahamutHoard = 1 end
check("cardia stage 1 incentivizes cardia", incentiveSlot("cardiaIsIncentive"), 6)
check("cardia stage 1 is not a hoard", incentiveSlot("BahamutHoard"), 3)

provided = {}
cardia.CurrentStage = 2
-- providesCode answers a count, and 0 is truthy in Lua -- the same trap
-- scripts/logic.lua opens by warning about.
if cardia:providesCode("cardiaIsIncentive") > 0 then provided.cardiaIsIncentive = 1 end
if cardia:providesCode("BahamutHoard") > 0 then provided.BahamutHoard = 1 end
check("cardia stage 2 is a hoard", incentiveSlot("BahamutHoard"), 6)
check("cardia stage 2 still incentivizes cardia", incentiveSlot("cardiaIsIncentive"), 6)

-- A code nothing defines counts zero just like a flag that is off, so without
-- the guard a typo would paint the slot blue on every seed for ever.
provided = {}
check("an unknown flag is treated as incentivized", incentiveSlot("noSuchFlag"), 6)

------------------------------------------------------------------
-- 5. The generated slot table, and the ring it drives.
--
-- The table is written by tools/incentive_slots.py out of the location files.
-- A path that resolves in neither tree is the failure that matters: the pass
-- skips a nil section by design, so a renamed node would silently stop being
-- ringed and nothing would say so.
------------------------------------------------------------------
dofile(PACK .. "/scripts/incentive_slots.lua")

-- Resolve a path the way PopTracker does: "@node/section" matches any location
-- whose full path ends in that node (tracker.cpp:849-871).
local byPath = {}
for _, file in ipairs({ "locations/overworld.json", "locations/incentives.json",
                        "locations/NOverworld/incentives.json" }) do
  eachSection(json.load(PACK .. "/" .. file), function(node, section)
    byPath["@" .. node.name .. "/" .. section.name] = section
  end)
end

local unresolved, flagsInTable = {}, {}
for _, slot in ipairs(INCENTIVE_SLOTS) do
  flagsInTable[slot.flag] = true
  if not byPath[slot.path] then
    unresolved[#unresolved + 1] = slot.path
  end
end
check("every slot path names a real section", #unresolved, 0)
for _, path in ipairs(unresolved) do
  fails("no section at " .. path)
end

-- 26 on the incentive tab (the 25 demoted plus the hoard, which still hides),
-- 2 more the NOverworld tree renames, and 26 on the real board.
check("slots in the generated table", #INCENTIVE_SLOTS, 54)

for flag in pairs(flagsInTable) do
  if not byCode[flag] then
    fails("the slot table names an undefined flag: " .. flag)
  end
end

-- Every gated section on the incentive tab is in the table. This is the one
-- that catches a slot quietly losing its ring.
for _, file in ipairs(INCENTIVE_FILES) do
  eachSection(json.load(PACK .. "/" .. file), function(node, section)
    local wanted = section.access_rules
        and table.concat(section.access_rules, ","):find(TERM)
    if wanted or section.visibility_rules then
      local path = "@" .. node.name .. "/" .. section.name
      local found = false
      for _, slot in ipairs(INCENTIVE_SLOTS) do
        if slot.path == path then found = true end
      end
      if not found then
        fails("gated but not in the slot table: " .. path)
      end
    end
  end)
end

------------------------------------------------------------------
-- 6. refreshIncentiveHighlights.
------------------------------------------------------------------
Highlight = { Avoid = -1, None = 0, NoPriority = 1, Unspecified = 2, Priority = 3 }

local sectionsByPath = {}
for path in pairs(byPath) do
  sectionsByPath[path] = { Highlight = Highlight.Unspecified }
end

-- The stub dispatches watches the way PopTracker does, because that is the
-- whole bug this section exists for: writing Tracker.BulkUpdate = false flushes
-- the queued changes and emits them (tracker.cpp:750-765), which runs the very
-- watches the refresh registers. A stub that only stored the field would have
-- passed while the real thing segfaulted on open, which is exactly what
-- happened.
local watches = {}
local dispatching = false
local depth, maxDepth = 0, 0
local function dispatch()
  if dispatching then
    -- PopTracker does not re-enter its own flush; the recursion it does allow
    -- is the pack calling back into the write that triggered it.
    return
  end
  dispatching = true
  for _, cb in ipairs(watches) do cb() end
  dispatching = false
end

Tracker = setmetatable({
  ActiveVariantUID = "5standard",
  ProviderCountForCode = function(_, code) return provided[code] or 0 end,
  FindObjectForCode = function(_, code)
    if code:sub(1, 1) == "@" then return sectionsByPath[code] end
    return byCode[code]
  end,
}, {
  __index = function(_, k)
    if k == "BulkUpdate" then return false end
    return nil
  end,
  __newindex = function(_, k, v)
    if k == "BulkUpdate" and v == false then
      -- The flush. This is the line that used to recurse.
      dispatch()
    end
  end,
})
ScriptHost = { AddWatchForCode = function(_, _, _, cb)
  watches[#watches + 1] = cb
end }
AUTOTRACKER_ENABLE_DEBUG_LOGGING = false

provided = {}
dofile(PACK .. "/scripts/incentives.lua")

-- Wrap it so the depth is visible, then let a watch fire while it runs.
local realRefresh = refreshIncentiveHighlights
function refreshIncentiveHighlights()
  depth = depth + 1
  if depth > maxDepth then maxDepth = depth end
  local n = realRefresh()
  depth = depth - 1
  return n
end
for i, cb in ipairs(watches) do
  if cb == realRefresh then watches[i] = refreshIncentiveHighlights end
end

check("nothing ringed when no flag is set", refreshIncentiveHighlights(), 0)
check("a skipped slot has no ring",
  sectionsByPath["@I: Coneria Castle/I: King"].Highlight, Highlight.None)

provided = { npcsAreIncentive = 1 }
local ringed = refreshIncentiveHighlights()
check("the NPC slots ring together", ringed > 0, true)
check("the incentive tab's King is ringed",
  sectionsByPath["@I: Coneria Castle/I: King"].Highlight, Highlight.Priority)
check("and so is the one on the real board",
  sectionsByPath["@Coneria Castle King/King"].Highlight, Highlight.Priority)
check("a slot on another flag is left alone",
  sectionsByPath["@I: Sea Shrine/I: Sea Incentive"].Highlight, Highlight.None)

-- The one that matters. A refresh that opened a bulk update would flush it on
-- the way out, the flush would run these watches, and the watches would refresh
-- again -- for ever. PopTracker died on the stack overflow rather than saying
-- anything.
maxDepth = 0
provided = { npcsAreIncentive = 1, seaIsIncentive = 1 }
refreshIncentiveHighlights()
check("a refresh never runs inside itself", maxDepth, 1)

-- And a watch firing mid-refresh is absorbed rather than recursing.
maxDepth = 0
dispatch()
check("a watch during a refresh does not recurse", maxDepth <= 1, true)

-- A host with no Highlight at all must not take the board down with it.
Highlight = nil
check("no Highlight support means no rings, not an error",
  refreshIncentiveHighlights(), 0)
check("and it still does not recurse", maxDepth <= 1, true)


print()
if fail == 0 then
  print("ALL PASS")
else
  print(fail .. " FAILED")
  os.exit(1)
end
