-- The Archipelago item feed: scripts/autotracking.lua's onItem and onClear,
-- against the real ITEM_MAPPING and the real item definitions.
--
-- Nothing loaded this file before, which is how the shard count sat one low in
-- every shard-hunt seed the pack ever tracked: "progressive" grants the first
-- copy by setting Active, and Shards is the one item with no disabled state
-- for that to mean anything.
local PACK = arg[1]
local json = dofile(PACK .. "/tests/json.lua")
local ItemModel = dofile(PACK .. "/tests/item_model.lua")

local byCode = ItemModel.loadPack(json, PACK, {
  "items/items.json", "items/hosted_items.json",
  "items/flags.json", "items/shards.json",
})

Tracker = {
  BulkUpdate = false,
  ActiveVariantUID = "6shardHunt",
  FindObjectForCode = function(_, code) return byCode[code] end,
}
ScriptHost = {
  LoadScript = function(_, path) dofile(PACK .. "/" .. path) end,
  AddVariableWatch = function() end,
  AddOnFrameHandler = function() end,
  RemoveOnFrameHandler = function() end,
}
Archipelago = {
  AddClearHandler = function() end,     AddItemHandler = function() end,
  AddLocationHandler = function() end,  AddSetReplyHandler = function() end,
  AddRetrievedHandler = function() end,
}

-- logic.lua is loaded by init.lua in the app, not by autotracking.lua; the
-- goal rule lives there and is the thing the shard count feeds.
dofile(PACK .. "/scripts/logic.lua")
dofile(PACK .. "/scripts/autotracking.lua")

-- Sections, so onClear's reconcile pass has a board to write to rather than
-- 250 lines of "no location section named ...".
local counts = {}
for _, v in pairs(LOCATION_MAPPING) do
  if v[1] then counts[v[1]] = (counts[v[1]] or 0) + 1 end
end
for path, n in pairs(counts) do
  byCode[path] = { ChestCount = n, AvailableChestCount = n }
end

local fail = 0
local function check(label, got, want)
  local ok = got == want
  if not ok then fail = fail + 1 end
  print(string.format("%s %-46s %s", ok and "ok  " or "FAIL", label, tostring(got)))
  if not ok then print(string.format("     wanted %s", tostring(want))) end
end

local idx = 0
local function grant(id)
  idx = idx + 1
  onItem(idx, id, "item " .. id)
end

------------------------------------------------------------------
print("-- shards are a tally, not a progressive")
------------------------------------------------------------------
-- AP id 277. One grant per shard received, and the count has to be the count:
-- scripts/logic.lua compares it straight against Shards Required + 16.
local shards = byCode["shards"]
check("no shards to start", shards.CurrentStage, 0)
grant(277)
check("the first shard counts", shards.CurrentStage, 1)
for _ = 2, 24 do grant(277) end
check("twenty-four shards read as 24", shards.CurrentStage, 24)

-- The goal must open on the 24th, not the 25th.
byCode["shardsRequired"].CurrentStage = 8      -- init.lua's default: 24
check("the goal opens on the count", canBreakOrb(), 1)
shards.CurrentStage = 23
check("and not one shard early", canBreakOrb(), 0)

------------------------------------------------------------------
print("\n-- the ordinary types still behave")
------------------------------------------------------------------
-- Every other progressive allows a disabled state, so there Active IS stage 1
-- and the existing handling is right. Crown is one of them.
grant(258)
check("the first crown is stage 1", byCode["crown"].CurrentStage, 1)
grant(258)
check("the turn-in is stage 2", byCode["crown"].CurrentStage, 2)

grant(257)
check("a toggle just goes on", byCode["lute"].Active, true)

-- A replayed index is ignored, whatever it carries.
onItem(1, 277, "Shard")
check("an old index is dropped", byCode["shards"].CurrentStage, 23)

------------------------------------------------------------------
print("\n-- onClear puts every type back")
------------------------------------------------------------------
onClear()
check("shards zeroed", byCode["shards"].CurrentStage, 0)
check("crown zeroed", byCode["crown"].CurrentStage, 0)
check("lute cleared", byCode["lute"].Active, false)

print("")
if fail == 0 then
  print("ALL PASS")
else
  print(fail .. " FAILED")
  os.exit(1)
end
