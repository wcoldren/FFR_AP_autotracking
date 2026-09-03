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
-- BahamutHoard stands for MapDragonsHoard -- a map edit. With it off those
-- chests are not in the cartridge, so a blue "there is a check here" pin would
-- be a lie rather than a demotion, and that section keeps its visibility rule.
------------------------------------------------------------------
local hidden = {}
for _, file in ipairs(INCENTIVE_FILES) do
  eachSection(json.load(PACK .. "/" .. file), function(node, section)
    if section.visibility_rules then
      hidden[#hidden + 1] = {
        rule = section.visibility_rules[1],
        text = string.format("%s: %s/%s on %s", file, node.name, section.name,
          section.visibility_rules[1]),
      }
    end
  end)
end
-- Two per incentive sheet, and they mean opposite things -- which is why each
-- flag is tallied and not only the total. A count alone passes on a sheet that
-- lost the hoard's rule and grew a second npcItems one somewhere else, which is
-- the shape a careless edit takes.
--
-- Both are the same kind, and BahamutHoard was read as the other kind until
-- 2026-09-03. FFR's NPCItems off does not un-incentivize the caravan slot, it
-- deletes it: Shop Item leaves `rules` and `locations` as well as
-- priority_locations, 227 to 224 on nonpcitems497. A slot FFR did not create is
-- not a check, so it is hidden rather than drawn blue -- the one place in this
-- pack where hiding a pin is right rather than the bug it usually is.
-- MapDragonsHoard off is the same statement about the hoard's chests. What it
-- is not is a statement about whether they are incentivized, which is what the
-- pack read it as while one progressive carried both facts; the section now
-- carries a ring rule for that, and this rule only for existence.
--
-- Both sheets host both. The NOverworld sheet was missing the hoard hosting
-- entirely until the rules were brought into line with the standard sheet's.
local HIDDEN_BY = { "BahamutHoard", "npcItems" }
check("only existence flags still hide a pin", #hidden, 2 * #INCENTIVE_FILES)
local tally = {}
for _, flag in ipairs(HIDDEN_BY) do tally[flag] = 0 end
for _, one in ipairs(hidden) do
  local named = false
  for _, flag in ipairs(HIDDEN_BY) do
    if one.rule:find(flag, 1, true) then
      tally[flag] = tally[flag] + 1
      named = true
    end
  end
  if not named then
    fails("a surviving visibility rule is " .. one.text
      .. ", which is neither BahamutHoard nor an existence flag")
  end
end
-- One of each per sheet, which is the half the total cannot say.
for _, flag in ipairs(HIDDEN_BY) do
  check("sections hidden by " .. flag, tally[flag], #INCENTIVE_FILES)
end

------------------------------------------------------------------
-- 2. Every alternative carries the term, and they all name the same flag.
------------------------------------------------------------------
-- Every term in the alternative, not the first. A section can name two -- FFR
-- computes IncentivizeCaravan and each fetch incentive as conjunctions rather
-- than storing them -- and matching once per alternative read a conjunction as
-- whichever conjunct came first in the string. That is the defect this branch
-- fixed, and the check that was meant to catch a section naming two flags could
-- not see one: it compared first-matches, which agree by construction.
local function slotFlags(alt)
  local found = {}
  for term in alt:gmatch("[^,]+") do
    local flag = term:match("^%^%$incentiveSlot|([%w_]+)$")
    if flag then found[#found + 1] = flag end
  end
  table.sort(found)
  return found
end

local gated, flagsUsed = 0, {}
for _, file in ipairs(INCENTIVE_FILES) do
  eachSection(json.load(PACK .. "/" .. file), function(node, section)
    local rules = section.access_rules or {}
    local seen = nil
    local without = 0
    for _, alt in ipairs(rules) do
      local flags = slotFlags(alt)
      if #flags > 0 then
        local key = table.concat(flags, "+")
        if seen and seen ~= key then
          fails(string.format("%s/%s names two flag sets: %s and %s",
            node.name, section.name, seen, key))
        end
        seen = key
        for _, flag in ipairs(flags) do flagsUsed[flag] = true end
      else
        without = without + 1
      end
    end
    if seen then
      gated = gated + 1
      if without > 0 then
        fails(string.format("%s: %s/%s has %d alternative(s) with no %s term "
          .. "-- the slot is ungated through them", file, node.name,
          section.name, without, "^$incentiveSlot"))
      end
    end
  end)
end
-- 26 gated sections in locations/incentives.json, plus 25 in the NOverworld
-- tree, which has no Nerrick.
--
-- One more on each sheet than before the shop slot took its flag: FFR computes
-- the shop-slot incentive rather than declaring it, so the slot is spoken for
-- by npcsAreIncentive like the six free NPCs and reports Inspect on a seed
-- that left Main NPCs unincentivized.
--
-- And one more again on each since the cardia split. The Bahamut hoard used to
-- be counted on neither sheet: it carried a visibility rule and an empty
-- access_rules, so it was hidden rather than demoted, on the reading that
-- MapDragonsHoard was its incentive condition. It is not -- that flag says the
-- Cardia chests are duplicated into the cave, not that they are incentivized --
-- so the section now carries both, and the two are about different things. A
-- seed with the hoard and no Cardia incentive draws the pin and demotes it,
-- which is the case the pack could not state at all before.
check("sections reporting Inspect when not incentivized", gated, 51)

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
check("distinct incentive flags, all defined", nflags, 15)

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

-- The Cardia incentive and Bahamut's Hoard are two items, and the whole point
-- of the split is that all four combinations can be said. They were one
-- progressive until 2026-09-03, stage 2 being the hoard, and a progressive
-- provides every code up to its stage -- so the fourth row below was not merely
-- untested, it was unsayable, and the pack rang Cardia Forest gold on five
-- cartridges FFR incentivized nothing on. docs/ISSUES.md.
--
-- Walked through providesCode rather than by setting `provided` directly, so
-- this still answers to what the item definitions actually hand out: making
-- them one item again reddens the fourth row here.
local cardia, hoard = byCode["cardiaIsIncentive"], byCode["BahamutHoard"]
local function setFlags(cardiaOn, hoardOn)
  provided = {}
  cardia.Active, hoard.Active = cardiaOn, hoardOn
  -- providesCode answers a count, and 0 is truthy in Lua -- the same trap
  -- scripts/logic.lua opens by warning about.
  if cardia:providesCode("cardiaIsIncentive") > 0 then provided.cardiaIsIncentive = 1 end
  if hoard:providesCode("BahamutHoard") > 0 then provided.BahamutHoard = 1 end
end

setFlags(false, false)
check("neither: cardia is not incentivized", incentiveSlot("cardiaIsIncentive"), 3)
check("neither: there is no hoard", incentiveSlot("BahamutHoard"), 3)

setFlags(true, false)
check("cardia alone incentivizes cardia", incentiveSlot("cardiaIsIncentive"), 6)
check("  and is still not a hoard", incentiveSlot("BahamutHoard"), 3)

setFlags(true, true)
check("both: the hoard exists", incentiveSlot("BahamutHoard"), 6)
check("  and cardia is incentivized", incentiveSlot("cardiaIsIncentive"), 6)

-- The row the old shape could not reach. Every hoard*497 cartridge is this
-- combination, and the pack ringed all of them.
setFlags(false, true)
check("a hoard does not incentivize cardia", incentiveSlot("cardiaIsIncentive"), 3)
check("  though the hoard itself exists", incentiveSlot("BahamutHoard"), 6)

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

-- `flags` is a list and an AND: two of FFR's incentive conditions are computed
-- conjunctions rather than stored flags, so a slot can answer to more than one.
local unresolved, flagsInTable = {}, {}
for _, slot in ipairs(INCENTIVE_SLOTS) do
  if #slot.flags == 0 then
    fails("no flag on the slot table row for " .. slot.path)
  end
  for _, flag in ipairs(slot.flags) do flagsInTable[flag] = true end
  if not byPath[slot.path] then
    unresolved[#unresolved + 1] = slot.path
  end
end
check("every slot path names a real section", #unresolved, 0)
for _, path in ipairs(unresolved) do
  fails("no section at " .. path)
end

-- No row rings on an existence flag, and this row is here because reverting the
-- change that made that true reddened nothing.
--
-- BahamutHoard says the Cardia chests are duplicated into Bahamut's Cave; it is
-- not an incentive category, and a row naming it rings the slot gold on every
-- hoard seed whatever IncentivizeCardia says. Three rows did until 2026-09-03.
-- Two of them are graded against FFR -- they are Archipelago locations, and
-- tools/tests/test_incentive_conjunction.py caught them on five cartridges.
-- The third, @Bahamut's Cave/Cardia Incentive - Hoard, is graded by nothing:
-- Bahamut's Cave is not an Archipelago location, so it sits in that suite's
-- NOT_AP_LOCATIONS and its ring is invisible to the corpus. Taking BahamutHoard
-- back out of incentive_slots.EXISTENCE_FLAGS flips that one row back and every
-- suite stays green, which is the failure shape this pack refuses everywhere
-- else. So the invariant is stated here rather than left to the corpus.
--
-- npcItems is the other existence flag and is deliberately not listed: it is
-- half of FFR's computed IncentivizeCaravan (FlagsCompute.cs:217) and its rows
-- name it as a conjunct for that reason, alongside npcsAreIncentive.
for _, slot in ipairs(INCENTIVE_SLOTS) do
  for _, flag in ipairs(slot.flags) do
    if flag == "BahamutHoard" then
      fails("BahamutHoard is an existence flag, not a ring flag, and "
        .. slot.path .. " rings on it")
    end
  end
end
check("no slot rings on BahamutHoard", flagsInTable.BahamutHoard, nil)

-- 26 on the incentive tab (the 25 demoted plus the hoard, which still hides),
-- 3 more the NOverworld tree renames or hosts under a different node, and 25 on
-- the real board.
--
-- The shop slot adds one row where every other slot adds two, and that is not
-- an omission. A row's path is `@<node>/<section>`, and the board's node for
-- this slot is itself named `I: Shop Item` -- the only board node carrying the
-- sheet prefix -- so the sheet path and the board path are the same string and
-- the second is deduped away. Which section that one row reaches is settled
-- and not ambiguous: PopTracker splits the ref at its last slash and looks up
-- the node *named* `I: Shop Item`, taking the first one loaded, and
-- scripts/init.lua loads overworld.json first, so it is the board's.
-- docs/ISSUES.md, "The `I: Shop Item` pin ignores the flag that governs it".
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
-- 6. The one deduped row reaches the board's section, and keeps doing so.
--
-- `@I: Shop Item/I: Shop Item` is the sheet path and the board path at once,
-- so which of the two sections gets the ring is settled by PopTracker, not by
-- anything visible in the row. getLocationAndSection splits the ref at its
-- LAST slash and looks up the bare node name; getLocation then tries an exact
-- id match across every loaded tree BEFORE it compares names, and only after
-- both does load order decide. A node's id is its full path, so a top-level
-- node's id is its bare name -- and a sheet node moved to the top level would
-- win the exact-id pass outright, ahead of the board and ahead of load order,
-- moving the ring to the sheet with no counter changing and no test noticing.
-- That is the invariant this section holds, because the row cannot state it.
------------------------------------------------------------------
local function shopItemNodes(file)
  local out = {}
  local function walk(nodes, prefix)
    for _, node in ipairs(nodes) do
      local id = prefix == "" and node.name or (prefix .. "/" .. node.name)
      if node.name == "I: Shop Item" then
        local hasSection = false
        for _, section in ipairs(node.sections or {}) do
          if section.name == "I: Shop Item" then hasSection = true end
        end
        out[#out + 1] = { id = id, top = not id:find("/"), hasSection = hasSection }
      end
      walk(node.children or {}, id)
    end
  end
  walk(json.load(PACK .. "/" .. file), "")
  return out
end

for _, variant in ipairs({ { "locations/overworld.json", "locations/incentives.json" },
                           { "locations/NOverworld/overworld.json",
                             "locations/NOverworld/incentives.json" } }) do
  local board, sheet = shopItemNodes(variant[1]), shopItemNodes(variant[2])
  check("one board node named I: Shop Item in " .. variant[1], #board, 1)
  check("one sheet node named I: Shop Item in " .. variant[2], #sheet, 1)
  local boardTop = #board == 1 and board[1].top
  if #board == 1 and not board[1].hasSection then
    fails("the board node has no section named I: Shop Item, so the row rings "
      .. "nothing: " .. variant[1])
  end
  for _, node in ipairs(sheet) do
    if node.top and not boardTop then
      fails("the sheet node sits at the top level, so its id is the bare name "
        .. "`I: Shop Item` and wins getLocation's exact-id pass before load "
        .. "order is consulted -- the ring moves off the board: " .. variant[2])
    end
  end
end

------------------------------------------------------------------
-- 7. refreshIncentiveHighlights.
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

-- show_gold_rings is on here because the item ships initial_active_state true,
-- and the stub answers ProviderCountForCode out of this table rather than out
-- of the item model. Every ring below is conditional on it.
provided = { show_gold_rings = 1 }
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

provided = { show_gold_rings = 1, npcsAreIncentive = 1, npcItems = 1 }
local ringed = refreshIncentiveHighlights()
check("the NPC slots ring together", ringed > 0, true)
check("the incentive tab's King is ringed",
  sectionsByPath["@I: Coneria Castle/I: King"].Highlight, Highlight.Priority)
check("and so is the one on the real board",
  sectionsByPath["@Coneria Castle King/King"].Highlight, Highlight.Priority)
check("a slot on another flag is left alone",
  sectionsByPath["@I: Sea Shrine/I: Sea Incentive"].Highlight, Highlight.None)

-- One conjunct alone rings nothing, which is the whole of this repair.
--
-- FFR computes IncentivizeCaravan as (NPCItems && IncentivizeFreeNPCs)
-- (FlagsCompute.cs:217), and the pack modelled IncentivizeFreeNPCs alone. On
-- nonpcitems497 -- std497 with NPCItems off and IncentivizeFreeNPCs left on --
-- FFR drops all seven free slots from priority_locations and the pack ringed
-- all seven. Either conjunct on its own has to ring nothing, and it has to be
-- both directions: a check that only tried the flag the pack already had would
-- have passed before this branch.
provided = { show_gold_rings = 1, npcsAreIncentive = 1 }
check("the incentive flag without NPCItems rings nothing",
  refreshIncentiveHighlights(), 0)
check("...including King", 
  sectionsByPath["@I: Coneria Castle/I: King"].Highlight, Highlight.None)
provided = { show_gold_rings = 1, npcItems = 1 }
check("and NPCItems without the incentive flag rings nothing",
  refreshIncentiveHighlights(), 0)

-- Nerrick's third term, which the other six fetch slots do not have.
--
-- FFR computes IncentivizeNerrick as (NPCFetchItems && IncentivizeFetchNPCs &&
-- !NoOverworld) -- FlagsCompute.cs:224 -- and IncentivizedLocationCountMin at
-- :229 reads the same way: seven fetch slots, or six under No-Overworld.
-- Measured on the nov cartridge, whose four relevant flags are all on: Nerrick
-- is a location and is in `rules`, and is the one fetch NPC missing from
-- priority_locations while Smith, Astos, Matoya, Elf Prince, Lefein and Fairy
-- are all in it.
--
-- The board tree is one file loaded by both variants, so the row carries the
-- term rather than the file. Smith is the control: same sheet, same two flags,
-- no third term, and he must keep his ring on both modes -- without him this
-- would also pass if the variant check put every fetch ring out.
provided = { show_gold_rings = 1, fetchQuestsAreIncentive = 1, npcFetchItems = 1 }
refreshIncentiveHighlights()
check("Nerrick rings on a standard seed",
  sectionsByPath["@Dwarf Cave Nerrick/Nerrick (Vanilla Canal)"].Highlight,
  Highlight.Priority)
check("and so does Smith",
  sectionsByPath["@Dwarf Cave Smith/Smithy McBeardSmith"].Highlight,
  Highlight.Priority)

Tracker.ActiveVariantUID = "7NOverworld"
refreshIncentiveHighlights()
check("Nerrick does not ring on a No-Overworld seed",
  sectionsByPath["@Dwarf Cave Nerrick/Nerrick (Vanilla Canal)"].Highlight,
  Highlight.None)
check("and Smith still does",
  sectionsByPath["@Dwarf Cave Smith/Smithy McBeardSmith"].Highlight,
  Highlight.Priority)
Tracker.ActiveVariantUID = "5standard"

-- The rings toggle. A Highlight is not a pin state -- PopTracker draws it as a
-- glow around a marker it is already drawing -- so this one is a guard inside
-- the refresh rather than a rule on the pin. What that has to buy is not just
-- "stop drawing new rings" but "put out the ones already there", since nothing
-- else ever revisits a section's Highlight.
provided = { npcsAreIncentive = 1, npcItems = 1 }
check("the toggle off rings nothing", refreshIncentiveHighlights(), 0)
check("and puts out a ring that was already drawn",
  sectionsByPath["@I: Coneria Castle/I: King"].Highlight, Highlight.None)
check("on the real board too",
  sectionsByPath["@Coneria Castle King/King"].Highlight, Highlight.None)

provided = { show_gold_rings = 1, npcsAreIncentive = 1, npcItems = 1 }
check("the toggle back on rings the same slots again",
  refreshIncentiveHighlights(), ringed)

-- A code nothing defines counts zero exactly like a toggle switched off, so a
-- typo in the item or the rule would blank every ring for good. wantRings()
-- separates the two cases and keeps ringing.
local savedRingItem = byCode["show_gold_rings"]
byCode["show_gold_rings"] = nil
provided = { npcsAreIncentive = 1, npcItems = 1 }
check("an undefined toggle rings anyway rather than blanking the board",
  refreshIncentiveHighlights(), ringed)
byCode["show_gold_rings"] = savedRingItem

-- The one that matters. A refresh that opened a bulk update would flush it on
-- the way out, the flush would run these watches, and the watches would refresh
-- again -- for ever. PopTracker died on the stack overflow rather than saying
-- anything.
maxDepth = 0
provided = { show_gold_rings = 1, npcsAreIncentive = 1, npcItems = 1, seaIsIncentive = 1 }
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

-- A row in the pre-conjunction `flag =` shape, which is what a stale or
-- hand-edited scripts/incentive_slots.lua would leave behind. The script reads
-- the table at load time and outside any pcall, so an `ipairs(nil)` there does
-- not cost one ring -- it aborts the file, and with it every watch and the
-- first refresh. Loading has to survive it; what the ringless row does after
-- that is not the point.
local savedSlots = INCENTIVE_SLOTS
INCENTIVE_SLOTS = { { path = "@Coneria/King", flag = "npcItems" } }
local loaded = pcall(dofile, PACK .. "/scripts/incentives.lua")
INCENTIVE_SLOTS = savedSlots
check("a row in the old shape does not abort the script", loaded, true)

print()
if fail == 0 then
  print("ALL PASS")
else
  print(fail .. " FAILED")
  os.exit(1)
end
