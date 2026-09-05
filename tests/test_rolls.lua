-- ff1/rolls, decoded onto the board.
--
-- The record is two fields, either of which may be empty, and the decoder's
-- whole job is to be strict about them: a rule told the wrong permutation
-- opens a check that cannot be reached, where the unknown state only holds a
-- reachable one closed. So most of what is below is refusals -- a landing
-- named twice, a source the pack does not know, a permutation missing a
-- landing a rule asks about -- and each one has to leave the board saying
-- nothing rather than saying half of something.
local PACK = arg[1]
local json = dofile(PACK .. "/tests/json.lua")
local ItemModel = dofile(PACK .. "/tests/item_model.lua")

local byCode = ItemModel.loadPack(json, PACK, {
  "items/items.json", "items/hosted_items.json", "items/flags.json",
  "items/shards.json", "items/rolls.json",
})

Tracker = {
  ActiveVariantUID = "7NOverworld",
  FindObjectForCode = function(_, code) return byCode[code] end,
}

local fail = 0
local function check(label, got, want)
  local ok = got == want
  if not ok then fail = fail + 1 end
  print(string.format("%s %-52s %s", ok and "ok  " or "FAIL", label, tostring(got)))
  if not ok then print(string.format("     wanted %s", tostring(want))) end
end

local function quiet(fn)
  local realPrint = print
  print = function() end
  local ok, err = pcall(fn)
  print = realPrint
  if not ok then error(err, 0) end
end

-- Does the board hand out this code? The whole point of the item model is that
-- this asks PopTracker's question rather than the pack's.
local function provides(code)
  local item = byCode[code]
  if not item then return nil end
  return item:providesCode(code) == 1
end

local function apply(record)
  local changed
  quiet(function() changed = applyFFRRolls(record) end)
  return changed
end

dofile(PACK .. "/scripts/autotracking/rolls_mapping.lua")

local NOV = "gateways=waterfall:cardiaCaravan,icecave:cardiaForest,"
    .. "gaia:bahamutCave|npcs=bahamut:bahamutCaveB2,elfdoc:elflandCastle,"
    .. "unne:melmond"

------------------------------------------------------------------
print("-- where the board starts")
------------------------------------------------------------------

check("the gateway roll is unread", provides("gatewayRoll"), false)
check("no gateway names a source", provides("cardiaForestFromWaterfall"), false)
check("the objective roll is unread", provides("objectiveRoll"), false)
check("no NPC names a home", provides("unneInMelmond"), false)

-- An Archipelago-only session never publishes the variable at all, and that is
-- not a change: it is where the board already is.
check("no variable is not a change", apply(nil), false)
check("and leaves the board unread", provides("gatewayRoll"), false)

------------------------------------------------------------------
print("\n-- a cartridge that answers for both halves")
------------------------------------------------------------------

check("a record applies", apply(NOV), true)
check("the gateway roll is read", provides("gatewayRoll"), true)
check("Cardia Forest is behind the Ice Cave gateway",
      provides("cardiaForestFromIceCave"), true)
check("Bahamut's Cave is behind the Gaia gateway",
      provides("bahamutCaveFromGaia"), true)
check("the objective roll is read", provides("objectiveRoll"), true)
check("Dr Unne is in Melmond", provides("unneInMelmond"), true)
check("the Elf Doctor is in Elfland Castle",
      provides("elfdocInElflandCastle"), true)
check("Bahamut is in his own cave", provides("bahamutInBahamutCave"), true)

-- The reason every stage carries inherit_codes: false. A PopTracker
-- progressive hands out every code up to its current stage by default, so
-- stage 3 would also say the gateway is behind Waterfall and behind the Ice
-- Cave -- three answers to a question with one.
check("a stage does not inherit the stages below it",
      provides("bahamutCaveFromWaterfall"), false)
check("nor the one directly below", provides("bahamutCaveFromIceCave"), false)
check("and the same for a home", provides("bahamutInMelmond"), false)

check("the same record again is not a change", apply(NOV), false)

------------------------------------------------------------------
print("\n-- the other cartridge")
------------------------------------------------------------------

-- novnolefein's permutation. What matters is that the previous cartridge's
-- answer goes: a stale gateway is the failure this whole feature exists to
-- avoid, one seed later.
check("a different roll applies", apply(
  "gateways=waterfall:cardiaForest,icecave:bahamutCave,gaia:cardiaCaravan"
  .. "|npcs=bahamut:melmond,elfdoc:elflandCastle,unne:bahamutCaveB2"), true)
check("Cardia Forest moved to Waterfall",
      provides("cardiaForestFromWaterfall"), true)
check("and no longer claims the Ice Cave",
      provides("cardiaForestFromIceCave"), false)
check("Bahamut's Cave moved to the Ice Cave",
      provides("bahamutCaveFromIceCave"), true)
check("Dr Unne moved to Bahamut's Cave", provides("unneInBahamutCave"), true)
check("and is no longer in Melmond", provides("unneInMelmond"), false)

------------------------------------------------------------------
print("\n-- a standard cartridge has no gateways")
------------------------------------------------------------------

check("a record with an empty gateway field applies",
  apply("gateways=|npcs=bahamut:bahamutCaveB2,elfdoc:elflandCastle,"
        .. "unne:melmond"), true)
check("the gateway roll reads unread", provides("gatewayRoll"), false)
check("and no gateway names a source",
      provides("cardiaForestFromWaterfall"), false)
check("while the NPC half is still read", provides("objectiveRoll"), true)
check("and says where Dr Unne is", provides("unneInMelmond"), true)

------------------------------------------------------------------
print("\n-- what has to be refused")
------------------------------------------------------------------

-- Each of these leaves both halves unread, because each record below is
-- applied to a board that has just been reset by the previous one.
local REFUSE = {
  { "a landing named twice",
    "gateways=waterfall:cardiaForest,icecave:cardiaForest,gaia:bahamutCave" },
  { "a source the pack does not know",
    "gateways=backdoor:cardiaForest,icecave:bahamutCave,gaia:cardiaCaravan" },
  { "a landing the pack does not know",
    "gateways=waterfall:cardiaForest,icecave:bahamutCave,gaia:atlantis" },
  { "a permutation missing a landing a rule asks about",
    "gateways=waterfall:cardiaCaravan,icecave:cardiaForest" },
  { "a field that is not pairs at all", "gateways=waterfall" },
}
for _, case in ipairs(REFUSE) do
  apply(case[2] .. "|npcs=")
  check(case[1] .. " is refused", provides("gatewayRoll"), false)
  check("  ...and sets no stage", provides("cardiaForestFromWaterfall")
        or provides("cardiaForestFromIceCave")
        or provides("cardiaForestFromGaia"), false)
end

-- cardiaCaravan is known and has no code of its own: the pocket it lands in
-- holds the Caravan door and nothing the pack tracks. A roll that sends a
-- source there is ordinary, and the other two still have to be set.
apply("gateways=waterfall:bahamutCave,icecave:cardiaCaravan,gaia:cardiaForest"
      .. "|npcs=")
check("a source landing in the Caravan pocket is not a refusal",
      provides("gatewayRoll"), true)
check("and the other two are set", provides("cardiaForestFromGaia"), true)

-- The NPC half, same rules.
apply("gateways=|npcs=bahamut:melmond,elfdoc:melmond,unne:bahamutCaveB2")
check("two NPCs in one home is refused", provides("objectiveRoll"), false)
apply("gateways=|npcs=bahamut:melmond,elfdoc:elflandCastle")
check("a permutation missing an NPC is refused", provides("objectiveRoll"), false)
apply("gateways=|npcs=bahamut:melmond,elfprince:elflandCastle,"
      .. "unne:bahamutCaveB2")
check("an NPC the pack does not know is refused",
      provides("objectiveRoll"), false)

------------------------------------------------------------------
print("\n-- the cartridge that answers for neither")
------------------------------------------------------------------

apply(NOV)
check("both halves read again", provides("gatewayRoll") and provides("objectiveRoll"),
      true)
check("an empty record is a change", apply(""), true)
check("and clears the gateway half", provides("gatewayRoll"), false)
check("and the NPC half", provides("objectiveRoll"), false)
check("and every stage under them", provides("bahamutInBahamutCave"), false)

-- A record the pack cannot parse at all is the same answer, not a crash.
check("a record with no fields is a change", apply("nonsense"), true)
check("and leaves the board unread", provides("gatewayRoll"), false)

------------------------------------------------------------------
print("\n-- a code the pack does not have")
------------------------------------------------------------------

-- All or nothing is what the rules were written against, and the toggle is the
-- half that says so: with it on and a stage missing, a location loses both its
-- source's alternative and the strict one it would have fallen back to, which
-- leaves it unreachable rather than merely held. So an item this pack cannot
-- find takes the whole half down to unknown, where every strict rule still
-- fires.
local realFind = Tracker.FindObjectForCode
Tracker.FindObjectForCode = function(_, code)
  if code == "cardiaForestGateway" then return nil end
  return byCode[code]
end
apply(NOV)
check("a missing stage code leaves the gateway half unread",
      provides("gatewayRoll"), false)
check("  and sets none of the stages it could have",
      provides("cardiaForestFromWaterfall"), false)
check("  while the other half is unaffected", provides("objectiveRoll"), true)
Tracker.FindObjectForCode = realFind

print(fail == 0 and "\nALL PASS" or string.format("\n%d FAILURE(S)", fail))
os.exit(fail == 0 and 0 or 1)
