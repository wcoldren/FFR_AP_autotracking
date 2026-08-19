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
local KNOWN_OVER = {
  -- Pre-existing, predates the autotracking work, left alone deliberately:
  ["@Earth Cave/2 Right"] = true,
}
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
for path, want in pairs({
  ["@ToFR/Vanilla Masa"] = 1,
  ["@ToFR/Kary Floor"] = 4,
  ["@ToFR/Lute Plate Room"] = 2,
  ["@Dwarf Cave/Nerrick (Vanilla Canal)"] = 1,
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

print(fail == 0 and "\nALL PASS" or string.format("\n%d FAILURE(S)", fail))
os.exit(fail == 0 and 0 or 1)
