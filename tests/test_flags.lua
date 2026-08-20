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

print("")
if fail == 0 then
  print("ALL PASS")
else
  print(fail .. " FAILED")
  os.exit(1)
end
