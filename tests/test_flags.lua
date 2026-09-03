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

-- What the pack printed while `fn` ran. Half of what this file is checking is
-- a line the player is meant to read -- a flag the cartridge could not answer
-- for is only "left as it was" if the log says which one.
local function capture(fn)
  local said, realPrint = {}, print
  print = function(...)
    local parts = {}
    for i = 1, select("#", ...) do parts[#parts + 1] = tostring((select(i, ...))) end
    said[#said + 1] = table.concat(parts, " ")
  end
  local ok, err = pcall(fn)
  print = realPrint
  if not ok then error(err, 0) end
  return table.concat(said, "\n")
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

-- The coverage tables have to describe flags that exist, and each flag has to
-- be claimed once. A name that drifts -- FFR renames one, or a code lands in
-- two tables -- is invisible at runtime: the toggle silently never applies, or
-- a flag is both modelled and declared unmodelled and the docs pick one.
do
  local cov = FFR_FLAG_COVERAGE
  check("the coverage tables are exported", cov ~= nil, true)
  local function names(version)
    local out = {}
    for _, e in ipairs((FFR_FLAG_SCHEMAS[version] or {}).properties or {}) do
      out[e.name] = true
    end
    return out
  end
  local n492, n497 = names("4-9-2"), names("4-9-7")
  -- A flag FF1Lib computes rather than stores has no field in either schema --
  -- FlagsCompute.cs derives IsShipFree, NoOverworld and six more from the
  -- flags that are stored. So `computed` exempts an entry from the check
  -- below, and the exemption is itself checked: a computed flag that turns up
  -- in a schema is either a typo or FFR having started to store it, and both
  -- want looking at.
  local KNOWN_STATUS = {
    ram = true, variant = true, noise = true,
    unmodellable = true, decided = true, unjudged = true,
  }
  local seen, dupes, unknown, wrongly = {}, {}, {}, {}
  local badStatus, shortWhy, noMeasure = {}, {}, {}
  for _, which in ipairs({"toggles", "progressives", "notModelled"}) do
    for _, entry in ipairs(cov[which] or {}) do
      -- A progressive names its sources inside its stage function rather than
      -- on the entry, so only the tables carrying an `ffr` are checked here.
      local name = entry.ffr
      if name then
        if seen[name] then dupes[#dupes + 1] = name end
        seen[name] = which
        local inSchema = n492[name] or n497[name]
        if entry.computed then
          if inSchema then wrongly[#wrongly + 1] = name end
        elseif not inSchema then
          unknown[#unknown + 1] = name
        end
      end
    end
  end
  check("no flag is claimed by two coverage tables", #dupes, 0)
  check("every named flag exists in a shipped schema", #unknown, 0)
  check("and no computed flag claims to", #wrongly, 0)
  for _, n in ipairs(dupes) do print("     claimed twice: " .. n) end
  for _, n in ipairs(unknown) do print("     in no schema: " .. n) end
  for _, n in ipairs(wrongly) do print("     computed, yet in a schema: " .. n) end

  -- Every entry carries its reason, not just the one this list started with.
  -- The reason is the whole value of the table: tools/tests/test_flag_coverage.py
  -- makes the list complete, and only this makes it honest. An `unjudged` entry
  -- additionally has to name the measurement that would settle it, so a flag
  -- nobody has looked at cannot sit here borrowing a neighbour's argument.
  for _, e in ipairs(cov.notModelled or {}) do
    local label = tostring(e.ffr)
    if not KNOWN_STATUS[e.status] then badStatus[#badStatus + 1] = label end
    if type(e.why) ~= "string" or #e.why < 40 then shortWhy[#shortWhy + 1] = label end
    if e.status == "unjudged" and (type(e.measure) ~= "string" or #e.measure < 10) then
      noMeasure[#noMeasure + 1] = label
    end
  end
  check("every not-modelled flag has a known status", #badStatus, 0)
  check("every not-modelled flag has a reason", #shortWhy, 0)
  check("every unjudged flag names its measurement", #noMeasure, 0)

  -- And the measurement having *run* is a field, not a turn of phrase. The
  -- NPCItems row was measured on 2026-09-03 and its `measure` rewritten from a
  -- request into a result; the check above went on passing either way, because
  -- a result is also a string longer than ten characters. So an `unjudged` flag
  -- nobody has looked at and one waiting only on a build became
  -- indistinguishable, and if the build never lands nothing here notices.
  -- `measured` separates them, `owed` names the code that retires the entry,
  -- and the third row is the one with teeth: once that code exists in the
  -- mapping the flag is modelled, and an entry still sitting here is stale.
  -- Both halves of the mapping, because an owed code can land in either. The
  -- toggles-only reading missed exactly the case this row exists for:
  -- `cardiaIsIncentive` is an incentive code of the kind these entries owe and
  -- it lives in PROGRESSIVES, so a code retiring into that half would have left
  -- the stale entry sitting here with the suite green.
  local codes = {}
  for _, list in ipairs({ cov.toggles or {}, cov.progressives or {} }) do
    for _, e in ipairs(list) do
      if e.code then codes[e.code] = true end
    end
  end
  local sayNothing, undated, noOwed, landed = {}, {}, {}, {}
  for _, e in ipairs(cov.notModelled or {}) do
    local label = tostring(e.ffr)
    if e.status == "unjudged" then
      local measure = type(e.measure) == "string" and e.measure or ""
      local says = measure:sub(1, 5) == "done:"
      if says ~= (e.measured == true) then sayNothing[#sayNothing + 1] = label end
      -- The row above catches the loud direction -- prose rewritten to a
      -- result, field left false. It cannot catch the quiet one: drop the
      -- `done:` convention while rewriting and both sides read false, the row
      -- goes green, and a flag that was measured reads as never looked at,
      -- which is the confusion these fields were added to remove. A date is
      -- what a measurement that has run leaves in the prose, so prose carrying
      -- one has to be spelled the way the field is read from.
      if measure:match("%d%d%d%d%-%d%d%-%d%d") and not says then
        undated[#undated + 1] = label
      end
      -- Only once measured. A flag nobody has looked at cannot yet know
      -- whether it wants a code at all, let alone which -- demanding one
      -- there would be the invented reason the `why` rule already forbids.
      --
      -- Shape as well as length, since by definition the name does not exist
      -- yet and there is nothing to match it against: pack codes are
      -- lowerCamelCase identifiers, and an `owed` that is not one can never
      -- fire the row below. A well-formed typo still passes -- that gap closes
      -- only when the code lands -- but "TBD", a sentence, or a name written
      -- with a space no longer does.
      if e.measured and (type(e.owed) ~= "string" or #e.owed < 3
          or not e.owed:match("^%l[%a%d]*$")) then
        noOwed[#noOwed + 1] = label
      end
      if type(e.owed) == "string" and codes[e.owed] then
        landed[#landed + 1] = label .. " (" .. e.owed .. ")"
      end
    end
  end
  check("a measured flag says so in a field, not only in its prose",
        #sayNothing, 0)
  check("and a measurement that has run is spelled `done:`", #undated, 0)
  check("every measured flag names the code that would retire it", #noOwed, 0)
  check("and no flag sits unjudged once that code exists", #landed, 0)
  for _, n in ipairs(sayNothing) do print("     measured/prose disagree: " .. n) end
  for _, n in ipairs(noOwed) do print("     names no owed code: " .. n) end
  for _, n in ipairs(landed) do print("     code landed, entry stale: " .. n) end
  for _, n in ipairs(badStatus) do print("     bad status: " .. n) end
  for _, n in ipairs(shortWhy) do print("     no reason: " .. n) end
  for _, n in ipairs(noMeasure) do print("     no measurement: " .. n) end

  -- ExitToFR is the one this list was added for: it is read, and deliberately
  -- carries no code. If a code ever appears for it, this says so.
  local exitToFR
  for _, e in ipairs(cov.notModelled or {}) do
    if e.ffr == "ExitToFR" then exitToFR = e end
  end
  check("ExitToFR is declared not modelled, with a reason",
        exitToFR ~= nil and #exitToFR.why > 40, true)
  check("and it is not also a toggle", seen["ExitToFR"], "notModelled")
end

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

-- Neither is applied. What they do to the grid instead is two blocks down.
check("an empty record applies nothing", applyFFRFlags(""), false)
check("a malformed record applies nothing", applyFFRFlags("nonsense"), false)

------------------------------------------------------------------
print("\n-- a cartridge with no flag record still says so")
--
-- The bridge publishes "" for a cartridge it could not get a record out of --
-- not an FFR ROM, a PRG it could not read, a build with no FFRInfo. The grid
-- goes back to the defaults there (the block after next), and the defaults are
-- a guess: nothing on the board distinguishes a setting read off the cartridge
-- from one nobody has answered for, which is what the light is for.
-- Nothing publishing the variable at all is a different thing: an Archipelago
-- session, where the defaults are what the player is meant to start from.
------------------------------------------------------------------

local litWith, lit = nil, 0
function setFlagsUnread(why) litWith, lit = why, lit + 1 end

FFR_FLAGS_SOURCE = nil
check("an empty record is still not applied", applyFFRFlags(""), false)
check("but it lights the unread light", type(litWith), "string")
check("once", lit, 1)
check("and it does not light again on the next scan", applyFFRFlags(""), false)
check("really once", lit, 1)

litWith, lit = nil, 0
FFR_FLAGS_SOURCE = nil
check("no variable at all does nothing", applyFFRFlags(nil), false)
check("and lights nothing", lit, 0)

litWith, lit = nil, 0
FFR_FLAGS_SOURCE = nil
check("a malformed record is not applied", applyFFRFlags("nonsense"), false)
check("and it lights the light too", type(litWith), "string")

litWith, lit = nil, 0
FFR_FLAGS_SOURCE = nil
check("a good record applies", applyFFRFlags(RECORD), true)
check("and clears the light", litWith, nil)
check("having said so", lit, 1)
setFlagsUnread = nil

------------------------------------------------------------------
print("\n-- the defaults, which are now written down once")
--
-- scripts/init.lua used to hold its own copy of these and set them by hand.
-- They live on the TOGGLES and PROGRESSIVES tables now, because the same set
-- has to be put *back* when a cartridge cannot be read, and two copies would
-- drift. This is the check that the surviving copy still says what the board
-- has started every session on since the pack shipped.
------------------------------------------------------------------

local DEFAULTS = {
  northernDocks = false, luffyDock = false, cardiaDock = false,
  lefeinRiver = false, lefeinBridge = false, gaiaMountain = false,
  hwyOrdeals = false, melmondRiver = false, sardasForest = false,
  shipDrydock = false, noTail = false,
  earlyKing = true, earlySarda = true, earlySage = true, earlyOrdeals = true,
  npcsAreIncentive = true, fetchQuestsAreIncentive = true,
  iceCaveIsIncentive = true, ordealsIsIncentive = true, marshIsIncentive = true,
  marshLockedIsIncentive = false, titansTroveIsIncentive = false,
  earthIsIncentive = true, volcanoIsIncentive = false, skyIsIncentive = true,
  seaIsIncentive = true, coneriaLockedIsIncentive = true,
}
local STAGE_DEFAULTS = { progressionFlag = 1, airBoat = 0, cardiaIsIncentive = 0 }

-- Every cell moved off its default first, so a reset that does nothing fails.
for code, want in pairs(DEFAULTS) do byCode[code].Active = not want end
for code, want in pairs(STAGE_DEFAULTS) do
  byCode[code].Active = true
  byCode[code].CurrentStage = want == 1 and 2 or 1
end
resetFlagsToDefaults()

local wrong = {}
for code, want in pairs(DEFAULTS) do
  if byCode[code].Active ~= want then wrong[#wrong + 1] = code end
end
for code, want in pairs(STAGE_DEFAULTS) do
  if byCode[code].CurrentStage ~= want then wrong[#wrong + 1] = code end
end
table.sort(wrong)
check("every flag cell is back on its default", table.concat(wrong, ", "), "")

-- The shard count is the one default that is not the board's everywhere: only
-- the shard-hunt variants show it, and only there does the goal read it.
Tracker.ActiveVariantUID = "6shardHunt"
byCode["shardsRequired"].CurrentStage = 3
resetFlagsToDefaults()
check("a shard variant is back on 24 shards",
      byCode["shardsRequired"].CurrentStage + 16, 24)
Tracker.ActiveVariantUID = "5standard"
byCode["shardsRequired"].CurrentStage = 3
resetFlagsToDefaults()
check("and a standard one is left alone", byCode["shardsRequired"].CurrentStage, 3)

------------------------------------------------------------------
print("\n-- a cartridge that cannot be read puts the grid back")
--
-- The flag grid outlives a cartridge swap: resetForNewGame clears what the RAM
-- feed owns and deliberately not this. So a cartridge whose settings cannot be
-- read has to put the defaults back itself, or the previous seed's answers go
-- on being asserted about a seed that never had them, with only the unread
-- light to say otherwise. That is the hole the absent-flag branch closes for a
-- version swap, in the case where there is nothing to decode at all.
--
-- All three ways of failing to read one are the same hole: no record, a record
-- that is not "<version>|<flags>", and one that is but will not decode.
------------------------------------------------------------------

for _, unreadable in ipairs({ "", "junk", "4-9-7|not-a-real-flagstring" }) do
  FFR_FLAGS_SOURCE = nil
  capture(function() applyFFRFlags(RECORD) end)
  check("a cartridge that reads, first", byCode["sardasForest"].Active, true)
  byCode["volcanoIsIncentive"].Active = true    -- and a click of the player's own

  FFR_FLAGS_SOURCE = nil
  local applied
  local said = capture(function() applied = applyFFRFlags(unreadable) end)
  check(string.format("then %q is not applied", unreadable), applied, false)
  check("  the seed's settings are gone", byCode["sardasForest"].Active, false)
  check("  the defaults are back", byCode["skyIsIncentive"].Active, true)
  check("  including the progressive", byCode["progressionFlag"].CurrentStage, 1)
  check("  and the click on top of them", byCode["volcanoIsIncentive"].Active, false)
  check("  nothing claims to know the settings", FFR_FLAGS, nil)
  check("  and the log says so", said:find("back to defaults", 1, true) ~= nil, true)

  -- Once, not on every scan: the same unreadable record has to be a no-op the
  -- second time, or the reset would sit on top of the grid the player is now
  -- setting by hand.
  byCode["sardasForest"].Active = true
  said = capture(function() applyFFRFlags(unreadable) end)
  check("  the same record again does nothing", byCode["sardasForest"].Active, true)
  check("  and says nothing", said, "")
end

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

-- The progressives are the half of this that was missed. Every source flag
-- behind them is a tri-state too -- MapOpenProgression, its Extended, AirBoat,
-- MapDragonsHoard, IncentivizeCardia -- and each stage function tested `== true`
-- and read a rolled flag as off. So a seed with AirBoat left on random cleared
-- the cell the player had set by hand, and the "left as they were" line, which
-- is the only place the pack admits it does not know, never mentioned it.
byCode["airBoat"].Active = true
byCode["airBoat"].CurrentStage = 1
partial.AirBoat = nil
local rolled = capture(function() applyFFRFlagsToBoard(partial, "4-9-7") end)
check("a rolled AirBoat leaves the cell alone", byCode["airBoat"].CurrentStage, 1)
check("  and is named in the log", rolled:find("AirBoat", 1, true) ~= nil, true)

-- Rolled means unknown, not unanswerable: a source flag the stage does not
-- depend on is not an unknown. Extended is only offered when Open Progression
-- is on, so a rolled Extended on a seed that says Open is off settles at 0.
local closedOpen = {}
for k, v in pairs(flags) do closedOpen[k] = v end
closedOpen.MapOpenProgression = false
closedOpen.MapOpenProgressionExtended = nil
byCode["progressionFlag"].Active = true
byCode["progressionFlag"].CurrentStage = 2
rolled = capture(function() applyFFRFlagsToBoard(closedOpen, "4-9-7") end)
check("a rolled Extended under a closed Open is off",
      byCode["progressionFlag"].CurrentStage, 0)
check("  so it is not reported as rolled",
      rolled:find("MapOpenProgressionExtended", 1, true), nil)

-- And with Open itself rolled there is no stage to be had: 0, 1 and 2 are all
-- still open, so the cell keeps what it had.
closedOpen.MapOpenProgression = nil
byCode["progressionFlag"].Active = true
byCode["progressionFlag"].CurrentStage = 2
rolled = capture(function() applyFFRFlagsToBoard(closedOpen, "4-9-7") end)
check("a rolled Open leaves the cell alone", byCode["progressionFlag"].CurrentStage, 2)
-- The frontier stops this matching MapOpenProgressionExtended, which is a
-- different flag and is not the one being reported here.
check("  and is named in the log",
      rolled:find("MapOpenProgression%f[%A]") ~= nil, true)

-- The Hoard is asked before IncentivizeCardia and wins outright when it is on,
-- so a rolled Hoard is unknown whichever way the incentive went.
local hoard = {}
for k, v in pairs(flags) do hoard[k] = v end
hoard.MapDragonsHoard = nil
hoard.IncentivizeCardia = false
byCode["cardiaIsIncentive"].Active = true
byCode["cardiaIsIncentive"].CurrentStage = 2
rolled = capture(function() applyFFRFlagsToBoard(hoard, "4-9-7") end)
check("a rolled Hoard leaves the cell alone", byCode["cardiaIsIncentive"].CurrentStage, 2)
check("  and is named in the log", rolled:find("MapDragonsHoard", 1, true) ~= nil, true)

------------------------------------------------------------------
print("\n-- the goal, once the seed has been read")
--
-- canBreakOrb used to compare ActiveVariantUID against "shardHunt", which is
-- not one of the four UIDs manifest.json declares, so every shard-hunt seed
-- was gated on four lit orbs and hasEnoughShards never ran.
------------------------------------------------------------------

dofile(PACK .. "/scripts/logic.lua")

-- Said here rather than inherited from whichever record was applied last: the
-- blocks above deliberately end with a cartridge that could not be read, which
-- leaves FFR_FLAGS nil. A copy, because this block moves OrbsRequiredMode and
-- the fixture is read again below.
FFR_FLAGS = {}
for k, v in pairs(flags) do FFR_FLAGS[k] = v end

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
print("\n-- Ship Drydock")
--
-- The flag moves every ship spawn to the Gaia drydock, which sits behind the
-- Canoe already, so the Ship stops opening anything. Same shape of question as
-- Sarda's Forest and the same reason it cannot live in access_rules.
------------------------------------------------------------------

byCode["shipDrydock"].Active = true
check("drydocked: the Ship opens nothing", noShipDrydock(), 0)
byCode["shipDrydock"].Active = false
check("ordinary: the Ship sails", noShipDrydock(), 1)

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
  return capture(function()
    FFR_FLAGS_SOURCE = nil          -- applyFFRFlags skips a record it just read
    applyFFRFlags(record)
  end)
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
      said:find("this variant is a shard hunt", 1, true) ~= nil, true)

-- Both halves at once. A seed can be wrong about the mode and the goal
-- together, and a chain of elseifs would report the first and hide the second.
Tracker.ActiveVariantUID = "7NOverworld"
said = applyCapturing(SHARD_RECORD)
check("a No-Overworld variant on a standard shard seed says both",
      said:find("this variant is No-Overworld", 1, true) ~= nil
      and said:find("this seed is a shard hunt", 1, true) ~= nil, true)

Tracker.ActiveVariantUID = "5standard"

-- Every path that resets the grid also has to blow the mode light out.
--
-- The light is decided from a decoded flag string, so a record that is absent,
-- malformed or undecodable says nothing about the mode -- and one left burning
-- describes the cartridge that just came out. uat.lua's swap cleanup does not
-- cover this: checkRom returns early when the emulator reports no rom at all,
-- which is exactly when the empty record arrives.
local mismatchCalls = {}
setModeMismatch = function(why) mismatchCalls[#mismatchCalls + 1] = { why = why } end

for _, case in ipairs({
      { "an absent record",    "" },
      { "a malformed record",  "no pipe in this one" },
      { "an undecodable one",  "4-9-7|!!!!!!!!" },
    }) do
  mismatchCalls = {}
  FFR_FLAGS_SOURCE = nil
  capture(function() applyFFRFlags(SHARD_RECORD) end)
  local lit = mismatchCalls[#mismatchCalls]
  check(case[1] .. ": the light is on to start", lit ~= nil and lit.why ~= nil, true)

  mismatchCalls = {}
  FFR_FLAGS_SOURCE = nil
  capture(function() applyFFRFlags(case[2]) end)
  local after = mismatchCalls[#mismatchCalls]
  check("  and " .. case[1] .. " puts it out", after ~= nil and after.why == nil, true)
end
setModeMismatch = nil

------------------------------------------------------------------
-- The two flags the overworld tab falls back on.
--
-- scripts/autotracking/maptab.lua asks the cartridge which overworld map to
-- land on when Archipelago never stated a pool. It asks by name, so a schema
-- that stopped carrying either name would break that quietly -- the fallback
-- would just always answer "ordinary seed".
------------------------------------------------------------------
dofile(PACK .. "/scripts/flags/schema_4-9-2.lua")
for _, version in ipairs({ "4-9-7", "4-9-2" }) do
  local schema = FFR_FLAG_SCHEMAS and FFR_FLAG_SCHEMAS[version]
  check(version .. " has a schema", schema ~= nil, true)
  local names = {}
  for _, entry in ipairs(schema and schema.properties or {}) do
    names[entry.name] = true
  end
  check("  it carries ShardHunt", names.ShardHunt == true, true)
  check("  it carries ChestsKeyItems", names.ChestsKeyItems == true, true)
end


------------------------------------------------------------------
print("\n-- NoTail, off the oracle cartridge that carries it")
------------------------------------------------------------------
-- NoTail takes the Tail out of the item pool and rewrites no access rule FFR
-- hands Archipelago, so no export grades it -- notail.yaml's rules mention the
-- Tail nowhere, and Bahamut is not an Archipelago location at all. The Bahamut
-- cell is the pack's own, and on a NoTail seed its `tail` can never light:
-- stage 0 reads $602D, and the seed has no Tail to put there. Without the
-- noTail alternative the cell reads unreachable right up until the class
-- change lights stage 1 from $620E and makes the question moot.
--
-- The before/after anchor is deliberately not this file's main 4-9-7 fixture,
-- which turns out to carry NoTail itself -- unnoticed for as long as there was
-- no noTail code to notice it with. SHARD_RECORD is the NoTail-off record here.
--
-- Flag string is read off seeds/ff1/oracle-4.9.2/notail at seed 45057553,
-- which is oracle_std with exactly one flag flipped.
local NOTAIL_FLAGS = "omlInPoZ8aeRURUYe2aUg0I8HZZCUXtPc76esLTcnyl5plsgMDVIQ3lOapR226xybGTTrugBTQeMv5"
    .. "wm1NR0AXzFFQUFmIyOlaB-i7D9BSRt.Lt4Snttst0yPEgyPIqf9Clw2RV-9AxD-qr33Lqb6rXFmyBv"
    .. "UxrD89pHBz3zAEWHH4FmWj"
local NOTAIL_RECORD = "4-9-2|" .. NOTAIL_FLAGS

check("ordinary 4-9-2 cartridge decodes NoTail off", f492.NoTail, false)
local fNoTail = decodeFFRFlags("4-9-2", NOTAIL_FLAGS)
check("the NoTail cartridge decodes", fNoTail ~= nil, true)
check("  and it says NoTail", fNoTail and fNoTail.NoTail, true)

-- On, then off again: the toggle has to track the flag in both directions, or
-- a NoTail seed followed by an ordinary one leaves Bahamut permanently open.
check("applied the NoTail cartridge", applyFFRFlags(NOTAIL_RECORD), true)
check("  noTail is set", byCode["noTail"].Active, true)
check("applied a NoTail-off cartridge", applyFFRFlags(SHARD_RECORD), true)
check("  noTail is cleared again", byCode["noTail"].Active, false)


------------------------------------------------------------------
print("\n-- ShipDrydock, off the pair of oracle cartridges that isolate it")
------------------------------------------------------------------
-- Unlike NoTail, this flag really does rewrite the rules FFR exports: 51 of
-- them lose their Ship alternative between these two cartridges and not one
-- gains anything, so check_logic on seeds/ff1/oracle-4.9.7/drydock497 is the
-- gate that matters -- 170 of 223 agreeing before the guard went in, 223 of 223
-- after. What is checked here is the wiring underneath it: that the flag
-- decodes, that the toggle tracks it in both directions, and that no
-- alternative names the Ship without asking.
--
-- The two flag strings are the 4.9.7 pair at seed 3B7E1C8A. They are the same
-- preset with one value flipped, so they differ only where ShipDrydock is.
local DRYDOCK_FLAGS = "omlInJg6XzA6ypn7hzElNF7feiRqCHN1fiyoFizlFcDuXxehujG-vKfclxv-8HQG57wxyvAys-E7mP"
    .. "MchXTUEJF9lu3nwFr7KOXbK9XmXUsGsOzVZziqYGv7eLzCNOX0A0qCgFrFWP5VVE7WVoV-omff9Q8H"
    .. "yBpYrWYp7tB-1lm86rN9GZM2xdjsmljIdXYCxVNLqv"
local PLAIN497_FLAGS = "omlInJg6XzAlwLPjeZz.e4gJprxdS0bG639WW9s6EcDuXxehujG-vKfclxv-8HQG57wxyvAys-E7mP"
    .. "MchXTUEJF9lu3nwFr7KOXbK9XmXUsGsOzVZziqYGv7eLzCNOX0A0qCgFrFWP5VVE7WVoV-omff9Q8H"
    .. "yBpYrWYp7tB-1lm86rN9GZM2xdjsmljIdXYCxVNLqv"

local fPlain497 = decodeFFRFlags("4-9-7", PLAIN497_FLAGS)
local fDrydock = decodeFFRFlags("4-9-7", DRYDOCK_FLAGS)
check("the 4.9.7 baseline cartridge decodes", fPlain497 ~= nil, true)
check("  and it says ShipDrydock off", fPlain497 and fPlain497.ShipDrydock, false)
check("the drydock cartridge decodes", fDrydock ~= nil, true)
check("  and it says ShipDrydock on", fDrydock and fDrydock.ShipDrydock, true)

-- On, then off again: a drydock seed followed by an ordinary one has to give
-- the Ship back, or every ship route stays shut for the rest of the session.
check("applied the drydock cartridge", applyFFRFlags("4-9-7|" .. DRYDOCK_FLAGS), true)
check("  shipDrydock is set", byCode["shipDrydock"].Active, true)
check("  and the Ship opens nothing", noShipDrydock(), 0)
check("applied the baseline cartridge", applyFFRFlags("4-9-7|" .. PLAIN497_FLAGS), true)
check("  shipDrydock is cleared again", byCode["shipDrydock"].Active, false)
check("  and the Ship sails again", noShipDrydock(), 1)

-- A flag the build has never heard of is not a flag the generator rolled.
-- schema_4-9-2 carries neither ShipDrydock nor MapSardasForest, so decoding a
-- 4.9.2 cartridge leaves both nil -- and nil used to mean "left as they were".
-- The toggles survive a cartridge swap, so a 4.9.7 drydock seed followed by a
-- 4.9.2 one kept shipDrydock set and every Ship alternative dead for the rest
-- of the session. NOTAIL_RECORD is a 4.9.2 cartridge, so it is the swap.
check("applied the drydock cartridge again", applyFFRFlags("4-9-7|" .. DRYDOCK_FLAGS), true)
check("  shipDrydock is set", byCode["shipDrydock"].Active, true)
byCode["sardasForest"].Active = true
-- The two overworld-shape flags added for 4.9.7 are new members of the same
-- class: schema_4-9-2 has no field for either, so both have to clear on the
-- swap rather than survive it and hold a route open on a cartridge that never
-- rolled them.
byCode["airshipHike"].Active = true
byCode["cardiaLandBridge"].Active = true
check("then swapped to a 4.9.2 cartridge", applyFFRFlags(NOTAIL_RECORD), true)
check("  shipDrydock is off, not left as it was", byCode["shipDrydock"].Active, false)
check("  and so is sardasForest, same cause", byCode["sardasForest"].Active, false)
check("  airshipHike too, which 4.9.2 has no field for", byCode["airshipHike"].Active, false)
check("  and cardiaLandBridge", byCode["cardiaLandBridge"].Active, false)

-- The other kind of nil still has to be left alone, or a tri-state rolled at
-- generation would be forced off instead of kept. A hand-built table has no
-- version behind it and is the case that must not change.
byCode["earlyKing"].Active = true
applyFFRFlagsToBoard({ EarlyKing = nil })
check("a nil with no schema to ask is left alone", byCode["earlyKing"].Active, true)
applyFFRFlagsToBoard({ EarlyKing = nil }, "4-9-7")
check("  and a tri-state the schema does carry, too", byCode["earlyKing"].Active, true)

-- The guard is only worth anything if every alternative carries it. One added
-- later without it would put back a route FFR has taken away, and nothing else
-- in either suite would notice.
local TREES = {
  "locations/overworld.json", "locations/incentives.json",
  "locations/NOverworld/overworld.json", "locations/NOverworld/incentives.json",
}

-- `sections` is the one that has to be spelled out. A location's rules can sit
-- on the node or on a section under it -- 296 lists at node level and 110 at
-- section level across the four trees -- and a walk that follows only
-- `children` reaches none of the second kind. It counted 121 and passed either
-- way, which is exactly the shape of canary this file is meant not to be.
--
-- `visibility_rules` is deliberately not walked: it decides whether a pin is
-- drawn, not whether it can be reached, and no alternative in it names the
-- Ship.
local function eachRule(node, fn)
  if type(node) ~= "table" then return end
  for _, alt in ipairs(node.access_rules or {}) do fn(alt) end
  for _, section in ipairs(node.sections or {}) do eachRule(section, fn) end
  for _, child in ipairs(node.children or {}) do eachRule(child, fn) end
  if node[1] ~= nil then
    for _, child in ipairs(node) do eachRule(child, fn) end
  end
end

local guarded, bare = 0, {}
for _, file in ipairs(TREES) do
  local fh = io.open(PACK .. "/" .. file)
  local tree = json.decode(fh:read("*a"))
  fh:close()
  eachRule(tree, function(alt)
    local namesShip, guardedHere = false, false
    for raw in tostring(alt):gmatch("[^,]+") do
      local term = raw:match("^%s*(.-)%s*$")
      if term == "ship" then namesShip = true end
      if term == "$noShipDrydock" then guardedHere = true end
    end
    if namesShip then
      if guardedHere then guarded = guarded + 1 else bare[#bare + 1] = alt end
    end
  end)
end

-- A floor rather than the count. `#bare == 0` is the invariant; 121 is only
-- evidence that the walk still reaches the alternatives it is meant to check,
-- and an exact match would fail on a legitimate new one that carries the guard
-- -- which is the canary this file's own comment warns against planting.
check("the walk still reaches the Ship alternatives", guarded >= 121, true)
check("  none of them unguarded", #bare, 0)
print(string.format("     %d alternatives name the Ship, all guarded", guarded))
for _, alt in ipairs(bare) do print("     unguarded: " .. alt) end


print("")
if fail == 0 then
  print("ALL PASS")
else
  print(fail .. " FAILED")
  os.exit(1)
end
