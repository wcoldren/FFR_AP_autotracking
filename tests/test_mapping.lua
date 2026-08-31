-- Validates LOCATION_MAPPING against the actual location JSON.
--
-- This is the guard the pack was missing: "@Dwarf Cave/Nerrick" pointed at a
-- section that does not exist, so its map marker never cleared, and nothing
-- said a word because the only complaint was behind a debug flag.
local PACK = arg[1]
local json = dofile(PACK .. "/tests/json.lua")

dofile(PACK .. "/scripts/autotracking/location_mapping.lua")

-- Collect every "@Location/Section" a pack file defines. PopTracker resolves
-- these by suffix, so the key is the immediate parent location plus section.
local sections = {}
local function walk(nodes, parent)
  for _, n in ipairs(nodes) do
    local name = n.name
    for _, sec in ipairs(n.sections or {}) do
      sections["@" .. name .. "/" .. sec.name] = sec.item_count or 0
    end
    walk(n.children or {}, name)
  end
end
for _, file in ipairs({ "locations/overworld.json", "locations/incentives.json" }) do
  walk(json.load(PACK .. "/" .. file), nil)
end

local fail = 0
local function fails(msg)
  print("FAIL " .. msg)
  fail = fail + 1
end

-- 1. every mapped path resolves
local unresolved, idsFor = {}, {}
for id, v in pairs(LOCATION_MAPPING) do
  local path = v[1]
  if path then
    idsFor[path] = (idsFor[path] or 0) + 1
    if sections[path] == nil then
      unresolved[path] = true
    end
  end
end
local bad = {}
for path in pairs(unresolved) do bad[#bad + 1] = path end
table.sort(bad)
if #bad > 0 then
  for _, path in ipairs(bad) do fails("unresolved section path: " .. path) end
else
  print("ok   all mapped paths resolve to a real section")
end

-- 2. no section is mapped by more ids than it has chests. Over-mapping is not
--    fatal any more (reconcile clamps at zero) but it silently misplaces a
--    location, so it should be visible.
-- Nothing is over-mapped any more. "@Earth Cave/2 Right" used to be: five ids
-- against an item_count of 3, because two chests on B1 had been filed under a
-- floor-2 section. Splitting Earth Cave per chest gave each of the five its own
-- section, which dissolved the mismatch rather than papering over it.
local KNOWN_OVER = {}
local over = {}
for path, n in pairs(idsFor) do
  local count = sections[path]
  if count and count > 0 and n > count and not KNOWN_OVER[path] then
    over[#over + 1] = string.format("%s: %d ids vs item_count %d", path, n, count)
  end
end
table.sort(over)
if #over > 0 then
  for _, msg in ipairs(over) do fails("over-mapped " .. msg) end
else
  print("ok   no section mapped by more ids than item_count (known exceptions aside)")
end

-- 3. the sections this change added line up exactly
--    The Ice Cave entries are the per-chest split: sixteen chests that used to
--    share six grouped sections now get one section each, so every one of them
--    must be mapped by exactly one id. A stray duplicate here would put two
--    chests behind one marker again without failing anything else.
for path, want in pairs({
  ["@Ice Cave Greed Chest Upper/Chest"] = 1,
  ["@Ice Cave Greed Chest Lower/Chest"] = 1,
  ["@Ice Cave Drop Room Left/Chest"] = 1,
  ["@Ice Cave Drop Room Middle/Chest"] = 1,
  ["@Ice Cave Drop Room Right/Chest"] = 1,
  ["@Ice Cave Incentive Room Left/Chest"] = 1,
  ["@Ice Cave Incentive Room Right/Chest"] = 1,
  ["@Ice Cave Incentive/Incentive"] = 1,
  ["@Ice Cave Six-Pack Top Left/Chest"] = 1,
  ["@Ice Cave Six-Pack Top Middle/Chest"] = 1,
  ["@Ice Cave Six-Pack Top Right/Chest"] = 1,
  ["@Ice Cave Six-Pack Bottom Left/Chest"] = 1,
  ["@Ice Cave Six-Pack Bottom Middle/Chest"] = 1,
  ["@Ice Cave Six-Pack Bottom Right/Chest"] = 1,
  ["@Ice Cave IceD Room Left/Chest"] = 1,
  ["@Ice Cave IceD Room Right/Chest"] = 1,
  ["@Cardia Forest Entrance Top/Chest"] = 1,
  ["@Cardia Forest Entrance Middle/Chest"] = 1,
  ["@Cardia Forest Entrance Bottom/Chest"] = 1,
  ["@Cardia Forest Incentive Room Left/Chest"] = 1,
  ["@Cardia Forest Incentive Room Middle/Chest"] = 1,
  ["@Cardia Forest Incentive/Incentive"] = 1,
  ["@Cardia Forest Incentive Room Lower/Chest"] = 1,
  ["@ToFR Vanilla Masa/Chest"] = 1,
  ["@ToFR Kary Floor 1/Chest"] = 1,
  ["@ToFR Kary Floor 2/Chest"] = 1,
  ["@ToFR Kary Floor 3/Chest"] = 1,
  ["@ToFR Kary Floor 4/Chest"] = 1,
  ["@ToFR Lute Plate Room 1/Chest"] = 1,
  ["@ToFR Lute Plate Room 2/Chest"] = 1,
  -- The two Dwarf Cave turn-ins. They moved out of the parent node and into
  -- one child apiece so each could carry its own square on the dwarves map;
  -- the paths below are what that move made of them.
  ["@Dwarf Cave Nerrick/Nerrick (Vanilla Canal)"] = 1,
  ["@Dwarf Cave Smith/Smithy McBeardSmith"] = 1,
}) do
  local got = idsFor[path] or 0
  local count = sections[path]
  if got ~= want then
    fails(string.format("%s mapped by %d ids, expected %d", path, got, want))
  elseif count ~= want then
    fails(string.format("%s item_count is %s, expected %d", path, tostring(count), want))
  else
    print(string.format("ok   %-38s %d ids == item_count", path, got))
  end
end

-- 4. hosted item codes all exist
local items = {}
for _, file in ipairs({ "items/items.json", "items/hosted_items.json", "items/flags.json", "items/shards.json" }) do
  for _, it in ipairs(json.load(PACK .. "/" .. file)) do
    for code in tostring(it.codes or ""):gmatch("[^,]+") do
      items[code:match("^%s*(.-)%s*$")] = true
    end
    for _, stage in ipairs(it.stages or {}) do
      for code in tostring(stage.codes or ""):gmatch("[^,]+") do
        items[code:match("^%s*(.-)%s*$")] = true
      end
    end
  end
end
local missing = {}
for _, v in pairs(LOCATION_MAPPING) do
  if v[2] and not items[v[2]] then missing[v[2]] = true end
end
local miss = {}
for code in pairs(missing) do miss[#miss + 1] = code end
table.sort(miss)
if #miss > 0 then
  for _, code in ipairs(miss) do fails("hosted item code not defined anywhere: " .. code) end
else
  print("ok   every hosted item code in the mapping is defined")
end

-- 4b. the layouts, read as a whole.
--
--     Three failures, none of which shows up as an error at runtime. A grid
--     cell whose code matches no item draws an empty square and says nothing,
--     because PopTracker adds the widget either way. A "layout" reference to a
--     key nobody defines draws nothing at all. And a grid that no layout
--     references is simply invisible -- which is how the boss row shipped
--     missing from all seven broadcast views: garland was moved out of the item
--     grids into a boss grid the trackers referenced and the broadcasts did not.
--
--     The file list comes from scripts/init.lua rather than being repeated
--     here, so it is the set the pack actually loads and a new layout is
--     covered without a second edit. LuaItems are listed by hand because they
--     are created in Lua at load and cannot be read out of items/*.json.
local LUA_ITEM_CODES = { resync = true, flagsUnread = true, artStale = true }
local layoutFiles, layoutSeen = {}, {}
do
  local f = assert(io.open(PACK .. "/scripts/init.lua"))
  local src = f:read("a")
  f:close()
  for file in src:gmatch('AddLayouts%("([^"]+)"%)') do
    if not layoutSeen[file] then
      layoutSeen[file] = true
      layoutFiles[#layoutFiles + 1] = file
    end
  end
end
if #layoutFiles < 2 then
  fails("found " .. #layoutFiles .. " AddLayouts calls in scripts/init.lua")
end

local docs, definedIn, referenced = {}, {}, {}
local gridMissing, gridSeen, gridCodes = {}, 0, {}
local function walkGrids(node, file)
  if type(node) ~= "table" then return end
  if node.type == "itemgrid" then
    for _, row in ipairs(node.rows or {}) do
      for _, code in ipairs(row) do
        gridSeen = gridSeen + 1
        gridCodes[code] = true
        if not items[code] and not LUA_ITEM_CODES[code] then
          gridMissing[code .. "  (" .. file .. ")"] = true
        end
      end
    end
  end
  if node.type == "layout" and type(node.key) == "string" then
    referenced[node.key] = true
  end
  for _, v in pairs(node) do walkGrids(v, file) end
end
for _, file in ipairs(layoutFiles) do
  local doc = json.load(PACK .. "/" .. file)
  for key, node in pairs(doc) do
    docs[key] = node
    definedIn[key] = file
  end
  walkGrids(doc, file)
end

local gm = {}
for code in pairs(gridMissing) do gm[#gm + 1] = code end
table.sort(gm)
if #gm > 0 then
  for _, code in ipairs(gm) do fails("itemgrid names an undefined code: " .. code) end
else
  print(string.format("ok   all %d itemgrid cells across %d layout files name a real item",
                      gridSeen, #layoutFiles))
end

-- 4c. and the same check the other way round: every flag reaches a grid.
--
--     4b catches a cell naming nothing. It cannot catch the reverse, and the
--     reverse is the one that has happened: `noTail` was added to
--     items/flags.json with a flag_mapping row and no cell anywhere, so a
--     NoTail seed set the item and the board showed nothing at all. Autotracking
--     still worked, which is exactly why nobody saw it -- the gap only bites a
--     player reading the board, or one setting flags by hand with no bridge.
--
--     Progressives count too, and by every code they offer rather than by one:
--     the Open Progression cell is named `extendedOpen`, which is a stage-2
--     code, so asking only about a first stage would report it missing. Leaving
--     them out would have exempted the six progressive flags from the very
--     check the noTail bug motivated.
--
--     Anything deliberately kept off the board goes on OFF_BOARD with its
--     reason, so this fails both ways: adding a hidden flag fails, and giving a
--     listed one a cell without taking it off the list fails too.
local OFF_BOARD = {}
local flagItems = {}
for _, item in ipairs(json.load(PACK .. "/items/flags.json")) do
  local codes = {}
  for _, field in ipairs({ item.codes }) do
    for code in tostring(field or ""):gmatch("[^,]+") do codes[#codes + 1] = code end
  end
  for _, stage in ipairs(item.stages or {}) do
    for code in tostring(stage.codes or ""):gmatch("[^,]+") do codes[#codes + 1] = code end
  end
  if #codes > 0 then
    flagItems[#flagItems + 1] = { name = item.name or codes[1], codes = codes }
  end
end
table.sort(flagItems, function(a, b) return a.name < b.name end)
if #flagItems < 30 then
  fails("read only " .. #flagItems .. " flags out of items/flags.json")
end
local hidden, staleOff = {}, {}
for _, item in ipairs(flagItems) do
  local seen = false
  for _, code in ipairs(item.codes) do
    if gridCodes[code] then seen = true end
  end
  if seen then
    if OFF_BOARD[item.name] then staleOff[#staleOff + 1] = item.name end
  elseif not OFF_BOARD[item.name] then
    hidden[#hidden + 1] = item.name
  end
end
for _, name in ipairs(hidden) do
  fails("flag with no grid cell, so the board can never show it: " .. name)
end
for _, name in ipairs(staleOff) do
  fails("flag listed as off-board but it has a grid cell: " .. name)
end
if #hidden == 0 and #staleOff == 0 then
  print(string.format("ok   all %d flags in items/flags.json have a cell on the board",
                      #flagItems))
end

-- 4d. a flag cell that can show more than one picture has to say which.
--
--     PopTracker's tooltip is getCurrentName(): a stage's own `name` if it has
--     one, the item's otherwise (jsonitem.h:133-140, surfaced at
--     defaulttrackerwindow.cpp:196). Without per-stage names the Overworld Tab
--     cell hovered as "Overworld Tab" on all three of its icons, and Open
--     Progression said the same thing whether it was on stage 1 or Extended --
--     so the one place a player can learn what a cell is currently set to said
--     nothing about the setting.
--
--     COUNTERS are the exception and are listed by name: their stages are a
--     quantity, the picture is the number, and a label per stage would repeat
--     it eight times.
local COUNTERS = { ["Loose Items"] = true, ["dud Items"] = true }
local unnamed = {}
for _, item in ipairs(json.load(PACK .. "/items/flags.json")) do
  local stages = item.stages or {}
  if #stages > 1 and not COUNTERS[item.name] then
    for i, stage in ipairs(stages) do
      if not stage.name or stage.name == "" then
        unnamed[#unnamed + 1] = (item.name or "?") .. " stage " .. i
      end
    end
  end
end
table.sort(unnamed)
for _, where in ipairs(unnamed) do
  fails("a flag stage with no name, so the tooltip cannot say which it is: " .. where)
end
if #unnamed == 0 then
  print("ok   every multi-stage flag names each of its stages")
end

local dangling, orphan = {}, {}
for key in pairs(referenced) do
  if not definedIn[key] then dangling[#dangling + 1] = key end
end
-- tracker_default and tracker_broadcast are PopTracker's own entry points, so
-- nothing in the pack references them.
for key, file in pairs(definedIn) do
  if not referenced[key] and not key:match("^tracker_") then
    orphan[#orphan + 1] = key .. "  (" .. file .. ")"
  end
end
table.sort(dangling)
table.sort(orphan)
for _, key in ipairs(dangling) do fails("layout reference to an undefined key: " .. key) end
for _, key in ipairs(orphan) do fails("layout is defined but nothing references it: " .. key) end
if #dangling == 0 and #orphan == 0 then
  print("ok   every layout reference resolves, and every layout is referenced")
end

-- 4c. the broadcast view has to carry the same board as the tracker view.
--
--     Flags and Incentives are deliberately dropped from some of these -- there
--     is no room on a stream overlay -- but an item or a location the tracker
--     shows and the broadcast does not is a hole, not a decision. That is the
--     shape of the garland regression, and only a per-variant comparison sees
--     it: both grids involved were referenced by *something*.
local boardCodes = {}
for _, file in ipairs({ "items/items.json", "items/hosted_items.json" }) do
  for _, it in ipairs(json.load(PACK .. "/" .. file)) do
    for code in tostring(it.codes or ""):gmatch("[^,]+") do
      boardCodes[code:match("^%s*(.-)%s*$")] = true
    end
  end
end

local function codesUnder(node, out, seenKeys)
  if type(node) ~= "table" then return end
  if node.type == "itemgrid" then
    for _, row in ipairs(node.rows or {}) do
      for _, code in ipairs(row) do out[code] = true end
    end
  end
  if node.type == "layout" and type(node.key) == "string" and not seenKeys[node.key] then
    seenKeys[node.key] = true
    codesUnder(docs[node.key], out, seenKeys)
  end
  for _, v in pairs(node) do codesUnder(v, out, seenKeys) end
end

-- Mirrors the variant dispatch in scripts/init.lua. Checked against it below,
-- so the two cannot drift apart quietly.
local VARIANTS = {
  { "1standardNoMap", "layouts/standardNoMap/tracker.json", "layouts/standardNoMap/broadcastNoMap.json" },
  { "2shardHuntNoMap", "layouts/shardHuntNoMap/tracker.json", "layouts/shardHuntNoMap/broadcastNoMap.json" },
  { "3NOverworldNoMap", "layouts/NOverworld/trackerNoMap.json", "layouts/NOverworld/broadcastNoMap.json" },
  { "4shardHuntNOverworldNoMap", "layouts/NOverworld/shardsTrackerNoMap.json", "layouts/NOverworld/broadcastShardsNoMap.json" },
  { "5standard", "layouts/standard/tracker.json", "layouts/standard/standard_broadcast.json" },
  { "6shardHunt", "layouts/shardHunt/tracker.json", "layouts/shardHunt/broadcast.json" },
  { "7NOverworld", "layouts/NOverworld/tracker.json", "layouts/NOverworld/broadcast.json" },
  { "8shardHuntNOverworld", "layouts/NOverworld/shardsTracker.json", "layouts/NOverworld/broadcastShards.json" },
}
local named = {}
for _, v in ipairs(VARIANTS) do named[v[2]], named[v[3]] = true, true end
for _, file in ipairs(layoutFiles) do
  if file ~= "layouts/shared.json" and not named[file] then
    fails("scripts/init.lua loads " .. file .. ", which no variant here names")
  end
end
for uid in pairs(json.load(PACK .. "/manifest.json").variants) do
  local known = false
  for _, v in ipairs(VARIANTS) do known = known or v[1] == uid end
  if not known then fails("manifest variant with no layout pair here: " .. uid) end
end

local holes = 0
for _, v in ipairs(VARIANTS) do
  local uid, trackerFile, castFile = v[1], v[2], v[3]
  local onTracker, onCast = {}, {}
  codesUnder(json.load(PACK .. "/" .. trackerFile).tracker_default, onTracker, {})
  codesUnder(json.load(PACK .. "/" .. castFile).tracker_broadcast, onCast, {})
  local gone = {}
  for code in pairs(onTracker) do
    if boardCodes[code] and not onCast[code] then gone[#gone + 1] = code end
  end
  table.sort(gone)
  if #gone > 0 then
    holes = holes + 1
    fails(uid .. ": the broadcast view is missing " .. table.concat(gone, ", "))
  end
end
if holes == 0 then
  print(string.format("ok   all %d broadcast views carry every item the tracker view does",
                      #VARIANTS))
end

-- 5. every RAM rule's stage must be a real index into that item's stages[].
--    PopTracker clamps an out-of-range stage silently, so a typo here would
--    just land on the last stage and look plausible.
local stagesFor, allowDisabledFor = {}, {}
for _, file in ipairs({ "items/items.json", "items/hosted_items.json", "items/flags.json", "items/shards.json" }) do
  for _, it in ipairs(json.load(PACK .. "/" .. file)) do
    local n = it.stages and #it.stages or 0
    local ad = it.allow_disabled ~= false
    for raw in tostring(it.codes or ""):gmatch("[^,]+") do
      local code = raw:match("^%s*(.-)%s*$")
      stagesFor[code], allowDisabledFor[code] = n, ad
    end
    for _, stage in ipairs(it.stages or {}) do
      for raw in tostring(stage.codes or ""):gmatch("[^,]+") do
        local code = raw:match("^%s*(.-)%s*$")
        if stagesFor[code] == nil then stagesFor[code], allowDisabledFor[code] = n, ad end
      end
    end
  end
end

Tracker = Tracker or {}
dofile(PACK .. "/scripts/autotracking/ram_mapping.lua")

local badStage = 0
for _, rule in ipairs(RAM_RULES) do
  local n = stagesFor[rule.code]
  if n == nil then
    fails("RAM rule for unknown code: " .. rule.code)
    badStage = badStage + 1
  elseif rule.stage > 0 and rule.stage >= math.max(n, 1) then
    fails(string.format("RAM rule %s stage %d is out of range (item has %d stages)",
      rule.code, rule.stage, n))
    badStage = badStage + 1
  end
end
if badStage == 0 then
  print("ok   every RAM rule stage is a valid stages[] index")
end

-- and the offset table must match the JSON rather than drift from it
local offsetWrong = 0
for code, ad in pairs(allowDisabledFor) do
  local listed = RAM_NO_STAGE_OFFSET[code] and true or false
  if not ad and stagesFor[code] > 0 then
    -- allow_disabled:false items may legitimately be absent if no rule uses
    -- them; only flag ones the rules actually touch.
    local used = (RAM_SHARDS.code == code)
    for _, rule in ipairs(RAM_RULES) do if rule.code == code then used = true end end
    if used and not listed then
      fails(string.format("%s has allow_disabled:false but is missing from RAM_NO_STAGE_OFFSET", code))
      offsetWrong = offsetWrong + 1
    end
  elseif ad and listed then
    fails(string.format("%s is in RAM_NO_STAGE_OFFSET but its item allows disabling", code))
    offsetWrong = offsetWrong + 1
  end
end
if offsetWrong == 0 then
  print("ok   RAM_NO_STAGE_OFFSET matches allow_disabled in the item JSON")
end

print(fail == 0 and "\nALL PASS" or string.format("\n%d FAILURE(S)", fail))
os.exit(fail == 0 and 0 or 1)
