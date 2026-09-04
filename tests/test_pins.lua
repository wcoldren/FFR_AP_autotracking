-- The pin toggles: which pins carry an off switch, and what it does.
--
-- The rules under test are generated -- tools/pin_visibility.py stamps them and
-- tools/regen_maps.py stamps its own output through the same function -- so
-- this is not checking that someone typed 254 rules correctly. It is checking
-- the three things that fail silently:
--
--   * a rule naming a kind, a flag or a toggle nothing defines. PopTracker
--     answers 0 for an undefined code exactly as it does for a switched-off
--     one, so the pin would be gone and stay gone with nothing said. showPin
--     fails open on a code it cannot find, and the counts below are what say
--     the failing-open path is not the one being taken.
--   * a rule on an overworld pin. Those are aggregates -- a town pin stands for
--     its chests, its NPC and its shop at once -- so a kind rule on one would
--     let a player empty the overworld tab.
--   * a rule that changes nothing. Each toggle's before and after count is
--     asserted here, against the real showPin, so "this switch works" is a
--     number rather than a claim.
local PACK = arg[1]
local json = dofile(PACK .. "/tests/json.lua")
local ItemModel = dofile(PACK .. "/tests/item_model.lua")

local DUNGEON_TREES = {
  "locations/overworld.json",
  "locations/NOverworld/overworld.json",
}
local INCENTIVE_TREES = {
  "locations/incentives.json",
  "locations/NOverworld/incentives.json",
}

-- Kinds showPin answers for, and the toggle each reads. Held here rather than
-- imported, because logic.lua's copy is a local: a rename on one side without
-- the other is a thing this should notice.
local KIND_TOGGLE = {
  chest = "show_chests",
  npc   = "show_npcs",
  slot  = "show_skipped",
}

-- Kinds showPin answers for that nothing stamps yet. Empty, now that all three
-- are wired; kept because it is the thing that fails in both directions when a
-- fourth is drawn ahead of its toggle -- a stamped rule with no item, and an
-- item nobody took off this list.
local PENDING_TOGGLE = {}

local fail = 0
local function fails(msg)
  print("FAIL " .. msg)
  fail = fail + 1
end
local function check(name, got, want)
  if got ~= want then
    print(string.format("FAIL %-54s got=%s want=%s", name, tostring(got), tostring(want)))
    fail = fail + 1
  else
    print(string.format("ok   %-54s %s", name, tostring(got)))
  end
end

-- Every marker in a tree, with the node that carries it.
local function eachPin(tree, fn)
  local function walk(nodes)
    for _, node in ipairs(nodes) do
      for _, marker in ipairs(node.map_locations or {}) do
        fn(node, marker)
      end
      walk(node.children or {})
    end
  end
  walk(tree)
end

local trees = {}
for _, rel in ipairs(DUNGEON_TREES) do trees[rel] = json.load(PACK .. "/" .. rel) end
for _, rel in ipairs(INCENTIVE_TREES) do trees[rel] = json.load(PACK .. "/" .. rel) end

------------------------------------------------------------------
-- 1. The shape of every stamped rule.
------------------------------------------------------------------
local kindsUsed, flagsUsed = {}, {}
for rel, tree in pairs(trees) do
  eachPin(tree, function(node, marker)
    local rules = marker.restrict_visibility_rules
    if not rules then return end
    -- One entry per section rather than one per pin, because the two carry
    -- different operators: the flags inside an entry are ANDed by showPin, and
    -- the entries are ORed by the array (location.cpp:266). A node holding two
    -- sections on different flags therefore has two entries, which is the same
    -- OR its one joined entry used to spell -- and a section whose flags are a
    -- conjunction can now say so, which a joined entry could not.
    if #rules < 1 then
      fails(string.format("%s: %s has an empty visibility rule list",
                          rel, node.name or "?"))
      return
    end
    for _, rule in ipairs(rules) do
      local kind, rest = rule:match("^%$showPin|([a-z]+)(.*)$")
      if not kind then
        fails(string.format("%s: %s carries a rule that is not a $showPin term: %s",
                            rel, node.name or "?", rule))
      else
        kindsUsed[kind] = (kindsUsed[kind] or 0) + 1
        for flag in rest:gmatch("|([^|,]+)") do flagsUsed[flag] = true end
      end
    end
    if marker.map == "overworld" then
      fails(string.format("%s: overworld pin %s carries %s -- the overworld "
                          .. "aggregates and must not be switchable off",
                          rel, node.name or "?", rules[1]))
    end
  end)
end

for kind in pairs(kindsUsed) do
  if PENDING_TOGGLE[kind] then
    fails(string.format("%d pins carry a $showPin|%s rule, but %s is not an item "
                        .. "yet -- take it off PENDING_TOGGLE or off the tree",
                        kindsUsed[kind], kind, PENDING_TOGGLE[kind]))
  elseif not KIND_TOGGLE[kind] then
    fails("no toggle is named for the pin kind " .. kind)
  end
end

------------------------------------------------------------------
-- 2. The counts, per tree.
--
-- 251 chest pins rather than 241 because ten chest ids carry two pins -- the
-- Ordeals 2F chest and friends, where one chest is reachable from two floors.
-- The 3 NPC pins are Nerrick, the Smith and Sarda: the only three the shipped
-- tree places on a dungeon map rather than on the overworld. The 29 unruled are
-- the overworld pins.
------------------------------------------------------------------
for _, rel in ipairs(DUNGEON_TREES) do
  local n = { chest = 0, npc = 0, none = 0 }
  eachPin(trees[rel], function(_, marker)
    local rules = marker.restrict_visibility_rules
    local kind = rules and rules[1]:match("^%$showPin|([a-z]+)")
    n[kind or "none"] = (n[kind or "none"] or 0) + 1
  end)
  check(rel .. ": chest pins", n.chest, 251)
  check(rel .. ": npc pins", n.npc, 3)
  check(rel .. ": pins with no rule", n.none, 29)
end

-- The sheets. 17 of 25 std slots and 20 of 27 nov ones can be spoken for by an
-- incentive flag; the rest hold a section no flag covers, so no rule may claim
-- to hide them. Eight and seven: the three with no slot at all -- Temple of
-- Fiends, ToFR, and Ryukahn Desert on the standard sheet -- and the five orb
-- slots. Shop Item used to be a fourth; it has a flag now, because FFR
-- computes the slot's incentive status out of NPCItems and IncentivizeFreeNPCs
-- rather than declaring a flag of its own.
local SHEET_RULED = { ["locations/incentives.json"] = 17,
                      ["locations/NOverworld/incentives.json"] = 20 }
for _, rel in ipairs(INCENTIVE_TREES) do
  local ruled = 0
  eachPin(trees[rel], function(_, marker)
    if marker.restrict_visibility_rules then ruled = ruled + 1 end
  end)
  check(rel .. ": pins with a rule", ruled, SHEET_RULED[rel])
end

------------------------------------------------------------------
-- 3. Every code a rule or a toggle names is a real item.
--
-- ProviderCountForCode answers 0 for a code nothing defines, so a typo here is
-- invisible on the board. showPin fails open rather than hiding, which keeps it
-- from being destructive -- and would also keep it from ever being noticed.
------------------------------------------------------------------
local byCode = ItemModel.loadPack(json, PACK, {
  "items/items.json", "items/hosted_items.json",
  "items/flags.json", "items/shards.json",
})
for flag in pairs(flagsUsed) do
  if not byCode[flag] then
    fails("no item defines the incentive flag " .. flag .. " named by a pin rule")
  end
end

local defs = json.load(PACK .. "/items/flags.json")
local defOf = {}
for _, def in ipairs(defs) do
  if def.codes then defOf[def.codes] = def end
end

local wired = 0
for kind, code in pairs(KIND_TOGGLE) do
  local def = defOf[code]
  if not def then
    fails(string.format("no item in items/flags.json has the code %s, which "
                        .. "showPin reads for the %s kind", code, kind))
  else
    wired = wired + 1
    if def.type ~= "toggle" then
      fails(code .. " is a " .. tostring(def.type) .. ", not a toggle")
    end
    -- Without this the pack ships with every chest pin hidden on first launch.
    if def.initial_active_state ~= true then
      fails(code .. " does not start switched on -- initial_active_state is "
            .. tostring(def.initial_active_state))
    end
  end
end
check("pin toggles defined and starting on", wired, 3)

for kind, code in pairs(PENDING_TOGGLE) do
  if defOf[code] then
    fails(string.format("%s is an item now -- take the %s kind out of "
                        .. "PENDING_TOGGLE and give it its counts", code, kind))
  end
end

-- The fourth switch in the Pins group. It hides no pin at all, so it has no
-- rules to count; it is here because "all of them start on" is the claim.
if not defOf.show_gold_rings or defOf.show_gold_rings.initial_active_state ~= true then
  fails("show_gold_rings is missing or does not start switched on")
end

-- Everything in the group is reachable from the dock, or it may as well not
-- exist. The Pins grid is the one place these are clickable.
local grid = json.load(PACK .. "/layouts/shared.json").shared_display_grid
local inGrid = {}
for _, row in ipairs(grid.content.rows) do
  for _, code in ipairs(row) do inGrid[code] = true end
end
for _, code in pairs(KIND_TOGGLE) do
  if not inGrid[code] then
    fails(code .. " is an item but is not in the Pins grid, so nothing can click it")
  end
end

------------------------------------------------------------------
-- 4. showPin itself.
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

provided = { show_chests = 1, show_npcs = 1 }
check("chest pins draw with the toggle on", showPin("chest"), 1)
check("npc pins draw with the toggle on", showPin("npc"), 1)
provided = { show_npcs = 1 }
check("chest pins go with the toggle off", showPin("chest"), 0)
check("npc pins are unaffected by the chest toggle", showPin("npc"), 1)
provided = {}
check("npc pins go with the toggle off", showPin("npc"), 0)

-- A kind nobody defined, and a toggle nobody defined. Both fail open: the pin
-- draws. The alternative -- a whole tab silently emptied by a typo -- is worse
-- than a pin that will not switch off.
check("an unknown kind draws", showPin("nosuchkind"), 1)
local realSkipped = byCode.show_skipped
byCode.show_skipped = nil
check("an undefined toggle draws", showPin("slot", "npcsAreIncentive"), 1)
byCode.show_skipped = realSkipped

-- The slot kind. An incentivized slot is not a skipped one, so the toggle has
-- no say over it; a slot the seed passed over is, and goes.
provided = { fetchQuestsAreIncentive = 1 }
check("an incentivized slot draws with skipped off",
      showPin("slot", "fetchQuestsAreIncentive"), 1)
check("a skipped slot goes with skipped off",
      showPin("slot", "npcsAreIncentive"), 0)
provided = { show_skipped = 1 }
check("a skipped slot draws with skipped on",
      showPin("slot", "npcsAreIncentive"), 1)

-- Nor is any slot a skipped one where the chests are the run. Both routes to
-- that, because they answer from different places and either may be the only
-- one available: the variant, which is set before the first rule runs, and
-- maptab.lua's chestsAreChecks(), which needs autotracking to have loaded.
provided = {}
Tracker.ActiveVariantUID = "6shardHunt"
check("a shard hunt keeps its skipped slots", showPin("slot", "npcsAreIncentive"), 1)
Tracker.ActiveVariantUID = "5standard"
check("and gives them up again off a shard hunt",
      showPin("slot", "npcsAreIncentive"), 0)

-- logic.lua loads before autotracking and autotracking may never load, so the
-- absent case is the normal one and has to be the quiet one.
check("no chestsAreChecks at all is not an error",
      showPin("slot", "npcsAreIncentive"), 0)
chestsAreChecks = function() return true end
check("a chests-are-checks seed keeps its skipped slots",
      showPin("slot", "npcsAreIncentive"), 1)
chestsAreChecks = function() return false end
check("an ordinary seed does not", showPin("slot", "npcsAreIncentive"), 0)
chestsAreChecks = nil

------------------------------------------------------------------
-- 5. What each toggle is worth, counted through the real showPin.
--
-- PopTracker reports no drawn-pin count, so without this every number in a
-- commit message is a hand count. This walks the shipped trees and evaluates
-- each pin's rules the way tracker.cpp does -- the outer array OR'd
-- (location.cpp:266), commas inside one entry ANDed, a `$fn` term read as a
-- count where anything above zero is true.
------------------------------------------------------------------
local function pinDraws(marker)
  local rules = marker.restrict_visibility_rules
  if not rules or #rules == 0 then return true end
  for _, alt in ipairs(rules) do
    local ok = true
    for term in alt:gmatch("[^,]+") do
      local call = term:match("^%$(.+)$")
      if call then
        local parts = {}
        for part in call:gmatch("[^|]+") do parts[#parts + 1] = part end
        local fn = _G[table.remove(parts, 1)]
        if not fn or fn(table.unpack(parts)) <= 0 then ok = false break end
      elseif (provided[term] or 0) <= 0 then
        ok = false
        break
      end
    end
    if ok then return true end
  end
  return false
end

local function drawn(rel)
  local n = 0
  eachPin(trees[rel], function(_, marker)
    if pinDraws(marker) then n = n + 1 end
  end)
  return n
end

for _, rel in ipairs(DUNGEON_TREES) do
  provided = { show_chests = 1, show_npcs = 1 }
  check(rel .. ": drawn, both toggles on", drawn(rel), 283)
  provided = { show_npcs = 1 }
  check(rel .. ": drawn, chests off", drawn(rel), 32)
  provided = { show_chests = 1 }
  check(rel .. ": drawn, npcs off", drawn(rel), 280)
  provided = {}
  check(rel .. ": drawn, both off", drawn(rel), 29)
end

-- The sheets, on a seed that incentivized nothing -- the worst case, and the
-- one where the toggle is worth most. Then with the NPC flag set, where the
-- slots it speaks for stop being skipped ones and come back on their own.
--
-- Six come back on each sheet, and they are the same six nodes: Coneria
-- Castle, Pravoka, Sarda's Cave, Crescent Lake, the Waterfall and the Shop
-- Item. The two sheets disagree about how Coneria Castle is drawn -- the
-- standard one puts the locked chest in with the King and Sara, so the node
-- carries a rule for the chest and a second one for the NPCs, while the
-- No-Overworld sheet gives the chest a node of its own -- and the counts differ
-- by that one pin rather than by which NPCs are on them. showPin ANDs the flags
-- within one rule and the rule array ORs, so a node whose sections answer to
-- different flags gets an entry apiece rather than one entry naming them all.
--
-- `npcs` and `npcsBoth` are the demonstration that the conjunction bites, and
-- they are stated as two rows because one of them would pass either way.
-- FFR computes IncentivizeCaravan as (NPCItems && IncentivizeFreeNPCs)
-- (FlagsCompute.cs:217), so the incentive flag on its own speaks for nothing:
-- `npcs` equals `off` exactly, no NPC pin comes back, and that equality is the
-- fix. With both conjuncts set, `npcsBoth` reproduces what `npcs` used to be --
-- so the repair took the wrong seeds away without costing the right ones.
local SHEET_DRAWN = {
  ["locations/incentives.json"] = { on = 25, off = 8, npcs = 8, npcsBoth = 14 },
  ["locations/NOverworld/incentives.json"] = { on = 27, off = 7, npcs = 7, npcsBoth = 13 },
}
for _, rel in ipairs(INCENTIVE_TREES) do
  local want = SHEET_DRAWN[rel]
  provided = { show_skipped = 1 }
  check(rel .. ": drawn, skipped on", drawn(rel), want.on)
  provided = {}
  check(rel .. ": drawn, skipped off", drawn(rel), want.off)
  provided = { npcsAreIncentive = 1 }
  check(rel .. ": drawn, one conjunct only", drawn(rel), want.npcs)
  check(rel .. ": ...which is the same as no flag at all", want.npcs, want.off)
  provided = { npcsAreIncentive = 1, npcItems = 1 }
  check(rel .. ": drawn, skipped off, NPCs incentivized", drawn(rel),
        want.npcsBoth)
end

if fail > 0 then
  print(string.format("\n%d FAILURES", fail))
  os.exit(1)
end
print("\nALL PASS")
