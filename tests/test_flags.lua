-- The seed's flag string, decoded and applied.
--
-- The fixture is a real one: the flag record out of
-- FFR_D0E0CDBF_TFXhhTGS.nes, a 4.9.7 seed with Sarda's Forest on, extended open
-- progression, the Cardia dock, and all four early NPCs. Its expected values
-- were cross-checked against tools/ffr_flags/decode.py, which is a separate
-- implementation of the same encoding, and against FFR's own spoiler for the
-- seed.
local PACK = arg[1]
local json = dofile(PACK .. "/tests/json.lua")
local ItemModel = dofile(PACK .. "/tests/item_model.lua")

local ITEM_FILES = {
  "items/items.json", "items/hosted_items.json",
  "items/flags.json", "items/shards.json",
}
local byCode = ItemModel.loadPack(json, PACK, ITEM_FILES)

Tracker = {
  ActiveVariantUID = "5standard",
  FindObjectForCode = function(_, code) return byCode[code] end,
}

dofile(PACK .. "/scripts/flags/schema_4-9-7.lua")
dofile(PACK .. "/scripts/autotracking/flags_decode.lua")
dofile(PACK .. "/scripts/autotracking/flag_mapping.lua")

local FLAGS = "g5jrLtdMmcv8HX6LJ6nJPKcN-pOcGr.UqftO9ERRZxcJAm2FedFY9IbNbcwcfP42E3ox1CUTLP3B"
    .. "ckfY4bbk1QLYOSKSncQLMf736lC0yuYUnP8O0Aja65mD2xLk.Uh2.zp0863A0c4qaK.L5-2-qjgYWZ"
    .. "Lm0AspmNOb6gNh9Y8ESTrxmXfI2oZHl9iIdXYCxVNLqv"
local RECORD = "4-9-7|" .. FLAGS

local fail = 0
local function check(label, got, want)
  local ok = got == want
  if not ok then fail = fail + 1 end
  print(string.format("%s %-46s %s", ok and "ok  " or "FAIL", label, tostring(got)))
  if not ok then print(string.format("     wanted %s", tostring(want))) end
end

------------------------------------------------------------------
print("-- decode")
------------------------------------------------------------------

local flags, err = decodeFFRFlags("4-9-7", FLAGS)
check("decoded", flags ~= nil, true)
if not flags then
  print("     " .. tostring(err))
  os.exit(1)
end

check("Sarda's Forest is on", flags.MapSardasForest, true)
check("open progression", flags.MapOpenProgression, true)
check("extended open progression", flags.MapOpenProgressionExtended, true)
check("northern docks off", flags.MapOpenProgressionDocks, false)
check("cardia dock on", flags.MapBahamutCardiaDock, true)
check("airboat off", flags.AirBoat, false)
check("early sarda", flags.EarlySarda, true)
check("orbs required", flags.OrbsRequiredCount, 3)
check("standard game mode", flags.GameMode, 0)
check("vanilla overworld", flags.OwMapExchange, 0)
check("not a shard hunt", flags.ShardHunt, false)

local n = 0
for _ in pairs(flags) do n = n + 1 end
check("every setting decoded", n, 568)

------------------------------------------------------------------
print("\n-- a decode that must not be trusted")
--
-- The build SHA rides on the end of the same number, so a string from another
-- FFR build, a typo, or a schema that is one property out all land here. The
-- point is that they are refused rather than producing settings that are
-- quietly shifted -- a board that looks configured and is wrong is worse than
-- one that was never touched.
------------------------------------------------------------------

local bumped = FLAGS:sub(1, #FLAGS - 1) .. (FLAGS:sub(-1) == "A" and "B" or "A")
local got, why = decodeFFRFlags("4-9-7", bumped)
check("a changed digit is refused", got, nil)
check("and says why", why ~= nil and why:find("build sha") ~= nil, true)

got, why = decodeFFRFlags("9-9-9", FLAGS)
check("an unknown FFR version is refused", got, nil)
check("and says which", why, "no schema for FFR 9-9-9")

check("a character outside the alphabet is refused",
      decodeFFRFlags("4-9-7", FLAGS:sub(1, 10) .. "!"), nil)
check("an empty string is refused", decodeFFRFlags("4-9-7", ""), nil)

------------------------------------------------------------------
print("-- a second schema, from a real 4-9-2 cartridge")
------------------------------------------------------------------
-- Two schemas have to coexist, because a seed names its own version and the
-- pack sees whatever the player rolled. This is the case that shipped wrong:
-- FFR_72A52C25 is 4-9-2, the pack only had 4-9-7, the decode was refused, and
-- the board fell back to init.lua's defaults -- which assert Sky, Sea and Earth
-- are incentivized when this seed says none of them are, and deny Titan's Trove
-- when it says otherwise. Refusing was right; the silent fallback was not.
dofile(PACK .. "/scripts/flags/schema_4-9-2.lua")

local FLAGS_492 = "MoELv7QsOnnoCGNext9M-X.DLA8uPmRIhOYKgmMLa.c3zogofl1b4Dr-P5C7xjCHCNENxi2q-J6nmd"
    .. "1hZjc3CDN7rgnWiMm-DE1gqFjpvDgolgrnkD64HomL8SJIFEME.i85x4NtiKjbt8oENXFzsTqIRuWd"
    .. "0W7wyKO7JQyzAEWHH4FmWj"

local f492, err492 = decodeFFRFlags("4-9-2", FLAGS_492)
check("4-9-2 decodes", f492 ~= nil, true)
if not f492 then
  print("     " .. tostring(err492))
  os.exit(1)
end
check("4-9-2 did not clobber 4-9-7", decodeFFRFlags("4-9-7", FLAGS) ~= nil, true)
check("sky is not incentivized", f492.IncentivizeSkyPalace, false)
check("sea is not incentivized", f492.IncentivizeSeaShrine, false)
check("earth is not incentivized", f492.IncentivizeEarth, false)
check("titan's trove is", f492.IncentivizeTitansTrove, true)
-- The wrong schema on the right string has to be caught by the build sha
-- rather than quietly producing shifted flags.
check("4-9-7's schema refuses a 4-9-2 string",
      decodeFFRFlags("4-9-7", FLAGS_492), nil)

------------------------------------------------------------------
print("\n-- applied to the board")
------------------------------------------------------------------

check("applied", applyFFRFlags(RECORD), true)

check("sardasForest set", byCode["sardasForest"].Active, true)
check("cardiaDock set", byCode["cardiaDock"].Active, true)
check("northernDocks cleared", byCode["northernDocks"].Active, false)
check("luffyDock cleared", byCode["luffyDock"].Active, false)
check("melmondRiver cleared", byCode["melmondRiver"].Active, false)
check("earlyOrdeals set", byCode["earlyOrdeals"].Active, true)
check("titansTrove incentive cleared", byCode["titansTroveIsIncentive"].Active, false)
check("ice cave incentive set", byCode["iceCaveIsIncentive"].Active, true)

-- Stage 2 of Open Progression is Extended, and stage 2 inherits stage 1's
-- codes, so a rule asking for either is satisfied.
check("open progression at extended", byCode["progressionFlag"].CurrentStage, 2)
check("still provides openProgression",
      byCode["progressionFlag"]:providesCode("openProgression"), 1)
check("and extendedOpen", byCode["progressionFlag"]:providesCode("extendedOpen"), 1)
check("airBoat off", byCode["airBoat"].CurrentStage, 0)
check("airBoat provides nothing", byCode["airBoat"]:providesCode("airBoat"), 0)

check("ffrFlag reads the set", ffrFlag("OrbsRequiredCount", 4), 3)
check("ffrFlag falls back", ffrFlag("NoSuchFlag", "fallback"), "fallback")

------------------------------------------------------------------
print("\n-- the same seed again is a no-op")
--
-- Otherwise every scan would stamp the grid back over a deliberate override,
-- ten times a second.
------------------------------------------------------------------

byCode["cardiaDock"].Active = false
check("re-applying the same record does nothing", applyFFRFlags(RECORD), false)
check("the override survived", byCode["cardiaDock"].Active, false)

check("an empty record does nothing", applyFFRFlags(""), false)
check("a malformed record does nothing", applyFFRFlags("nonsense"), false)

------------------------------------------------------------------
print("\n-- a flag left random is not a flag turned off")
--
-- FFR's tri-states can be left for the generator to roll, and the flag string
-- records that it was rolled without recording which way. Treating that as off
-- would silently narrow the logic.
------------------------------------------------------------------

byCode["gaiaMountain"].Active = true
byCode["lefeinBridge"].Active = false
local partial = {}
for k, v in pairs(flags) do partial[k] = v end
partial.MapGaiaMountainPass = nil
partial.MapBridgeLefein = nil
applyFFRFlagsToBoard(partial)
check("a random flag that was on stays on", byCode["gaiaMountain"].Active, true)
check("a random flag that was off stays off", byCode["lefeinBridge"].Active, false)
check("a known flag next to it still applies", byCode["hwyOrdeals"].Active, false)

------------------------------------------------------------------
print("\n-- the goal, once the seed has been read")
--
-- canBreakOrb used to compare ActiveVariantUID against "shardHunt", which is
-- not one of the four UIDs manifest.json declares, so every shard-hunt seed
-- was gated on four lit orbs and hasEnoughShards never ran.
------------------------------------------------------------------

dofile(PACK .. "/scripts/logic.lua")

local function lightOrbs(n)
  local orbs = { "earthorb", "fireorb", "waterorb", "airorb" }
  for i, code in ipairs(orbs) do
    byCode[code].Active = i <= n
    byCode[code].CurrentStage = i <= n and 1 or 0
  end
end

local function orbGate(n)
  lightOrbs(n)
  return canBreakOrb()
end

-- The seed applied above wants three orbs and picks which three (mode 1), and
-- the flag string does not say which, so the rule holds out for all four.
check("three of four is not enough when the seed names them", orbGate(3), 0)
check("all four always is", orbGate(4), 1)

-- Any three would do if the seed had not named them.
FFR_FLAGS.OrbsRequiredMode = 0
check("three is enough when any three will do", orbGate(3), 1)
check("two is not", orbGate(2), 0)

-- With no seed read at all, the rule is what it always was.
FFR_FLAGS = nil
check("four orbs without a seed", orbGate(4), 1)
check("three orbs without a seed", orbGate(3), 0)

Tracker.ActiveVariantUID = "6shardHunt"
byCode["shardsRequired"].Active = true
byCode["shardsRequired"].CurrentStage = 8   -- what init.lua sets: 24 shards
byCode["shards"].Active = true
-- The stage is the shard count itself, so the goal opens on the 24th shard
-- and not the 25th. Both feeds published count-1 before, which cost a shard.
byCode["shards"].CurrentStage = 23
check("a shard hunt is not gated on orbs", canBreakOrb(), 0)
check("23 of 24 shards is not enough", canBreakOrb(), 0)
byCode["shards"].CurrentStage = 24
check("and opens on the 24th shard", canBreakOrb(), 1)
Tracker.ActiveVariantUID = "5standard"

------------------------------------------------------------------
print("\n-- Sarda's Forest")
--
-- The flag decides whether the airship can put down outside the cave, and
-- access_rules cannot ask "not this flag".
------------------------------------------------------------------

byCode["sardasForest"].Active = true
check("forested: the airship is not enough", noSardasForest(), 0)
byCode["sardasForest"].Active = false
check("clear: the airship lands", noSardasForest(), 1)

------------------------------------------------------------------
print("\n-- shard hunt")
--
-- A second real fixture: FFR_CB6414F9_NXBGBhKK.nes, the 4.9.7 shard-hunt seed
-- from an Archipelago multiworld. It wants 28 shards, which FFR encodes as
-- ShardCount 3 -- and nothing carried that onto the board before, so every
-- shard-hunt seed sat on init.lua's default of 24.
------------------------------------------------------------------

local SHARD_FLAGS = "omlY4N4.V52WES0FKfb3ZxqHNRewObPWrp0keW4wjHQk75ON22XOGtSwrxhJa3i8yc4fU1Jdd9sE"
    .. "UrFQ96DyNrA5wAexni92MMVEJCkftnhxAq2PHaL4g0pZGJFcgOAwicDmBndclzeEIMGfegxxO2Sd8l"
    .. "Q8SvZID-d.IPXduLuhTy62ki-t2H6ylljIdXYCxVNLqv"

local shardFlags = decodeFFRFlags("4-9-7", SHARD_FLAGS)
check("shard-hunt seed decodes", shardFlags ~= nil, true)
check("it is a shard hunt", shardFlags.ShardHunt, true)
check("ShardCount is Count28", shardFlags.ShardCount, 3)

local required = byCode["shardsRequired"]
local INIT_DEFAULT = 8    -- what scripts/init.lua starts every shard variant on

Tracker.ActiveVariantUID = "6shardHunt"
required.CurrentStage = INIT_DEFAULT
applyFFRFlagsToBoard(shardFlags)
check("28 shards lands on stage 12", required.CurrentStage, 12)
-- The stage is the number hasEnoughShards adds sixteen back to.
check("which reads back as 28", required.CurrentStage + 16, 28)

-- A range is rolled at generation: the string says it was rolled, not where it
-- landed, so it has to be left alone the way a random tri-state is.
local ranged = {}
for k, v in pairs(shardFlags) do ranged[k] = v end
ranged.ShardCount = 7                       -- Range24_32
required.CurrentStage = INIT_DEFAULT
applyFFRFlagsToBoard(ranged)
check("a rolled range is left alone", required.CurrentStage, INIT_DEFAULT)

-- Every seed carries a ShardCount, orb goals included. The orb fixture at the
-- top of this file must not have its count stamped over.
required.CurrentStage = INIT_DEFAULT
applyFFRFlagsToBoard(flags)
check("an orb seed leaves the count alone", required.CurrentStage, INIT_DEFAULT)

-- Every fixed count maps to its own stage, and the two ends are the bounds of
-- the Shards Required item.
Tracker.ActiveVariantUID = "6shardHunt"
for value, count in pairs({ [0] = 16, [1] = 20, [2] = 24, [3] = 28, [4] = 32, [5] = 36 }) do
  local one = {}
  for k, v in pairs(shardFlags) do one[k] = v end
  one.ShardCount = value
  required.CurrentStage = INIT_DEFAULT
  applyFFRFlagsToBoard(one)
  check("ShardCount " .. value .. " -> " .. count .. " shards", required.CurrentStage + 16, count)
end

-- The goal rule is picked by variant, not by flag, so a shard-hunt seed on a
-- standard variant is silently gated on orbs. applyFFRFlags is the only place
-- that can notice, so it has to say so.
local SHARD_RECORD = "4-9-7|" .. SHARD_FLAGS
local function applyCapturing(record)
  local said, realPrint = {}, print
  print = function(...)
    local parts = {}
    for i = 1, select("#", ...) do parts[#parts + 1] = tostring((select(i, ...))) end
    said[#said + 1] = table.concat(parts, " ")
  end
  FFR_FLAGS_SOURCE = nil            -- applyFFRFlags skips a record it just read
  applyFFRFlags(record)
  print = realPrint
  return table.concat(said, "\n")
end

Tracker.ActiveVariantUID = "5standard"
local said = applyCapturing(SHARD_RECORD)
check("shard seed on a standard variant is called out",
      said:find("this seed is a shard hunt", 1, true) ~= nil, true)

Tracker.ActiveVariantUID = "6shardHunt"
said = applyCapturing(SHARD_RECORD)
check("and says nothing once the variant matches",
      said:find("shard hunt --", 1, true) ~= nil, false)

said = applyCapturing(RECORD)
check("orb seed on a shard variant is called out",
      said:find("this seed is not a shard hunt", 1, true) ~= nil, true)

Tracker.ActiveVariantUID = "5standard"

print("")
if fail == 0 then
  print("ALL PASS")
else
  print(fail .. " FAILED")
  os.exit(1)
end
