-- Validates map markers against the map definitions and the art itself.
--
-- A marker with a typo'd map name, or an x/y off the edge of its image, draws
-- nothing at all and says nothing about it -- the same silent-failure shape the
-- section-path check in test_mapping.lua exists to catch.
local PACK = arg[1]
local json = dofile(PACK .. "/tests/json.lua")

local fail = 0
local function fails(msg)
  print("FAIL " .. msg)
  fail = fail + 1
end

-- PNG keeps width and height big-endian in the IHDR, at bytes 17-24. That is
-- the whole reason this check can live in the Lua suite instead of a tool with
-- an image dependency.
local function imageSize(path)
  local f = io.open(path, "rb")
  if not f then return nil, "missing" end
  local head = f:read(24)
  f:close()
  -- Only PNG is measurable here; the pack has one .jpg, which still has to
  -- exist but cannot be bounds-checked.
  if not head or #head < 24 or head:sub(2, 4) ~= "PNG" then return nil, "unmeasured" end
  return string.unpack(">I4", head, 17), string.unpack(">I4", head, 21)
end

-- every map name the pack defines, and how big its art is
local maps = {}
for _, file in ipairs({ "maps/maps.json", "maps/NOverworldMaps.json" }) do
  for _, m in ipairs(json.load(PACK .. "/" .. file)) do
    local w, h = imageSize(PACK .. "/" .. m.img)
    if not w and h == "missing" then
      fails(string.format("map %q points at %s, which does not exist", m.name, m.img))
    end
    maps[m.name] = { w = w, h = h, img = m.img, size = m.location_size or 0 }
  end
end

-- every marker in every location file
local markers = {}
local function walk(nodes)
  for _, n in ipairs(nodes) do
    for _, ml in ipairs(n.map_locations or {}) do
      markers[#markers + 1] = { name = n.name, map = ml.map, x = ml.x, y = ml.y }
    end
    walk(n.children or {})
  end
end
for _, file in ipairs({ "locations/overworld.json", "locations/incentives.json" }) do
  walk(json.load(PACK .. "/" .. file))
end
print(string.format("ok   %d markers across %d maps", #markers, (function()
  local n = 0; for _ in pairs(maps) do n = n + 1 end; return n
end)()))

-- 1. every marker names a map the pack actually defines
local unknown = 0
for _, m in ipairs(markers) do
  if not maps[m.map] then
    fails(string.format("%s: marker on undefined map %q", m.name, tostring(m.map)))
    unknown = unknown + 1
  end
end
if unknown == 0 then print("ok   every marker names a defined map") end

-- 2. every marker sits inside its image. PopTracker takes x/y as the centre,
--    so a marker within half a box of the edge is clipped rather than drawn.
local outside = 0
for _, m in ipairs(markers) do
  local mp = maps[m.map]
  if mp and mp.w then
    local half = math.floor(mp.size / 2)
    if type(m.x) ~= "number" or type(m.y) ~= "number" then
      fails(string.format("%s: marker on %s has non-numeric x/y", m.name, m.map))
      outside = outside + 1
    elseif m.x - half < 0 or m.y - half < 0 or m.x + half > mp.w or m.y + half > mp.h then
      fails(string.format("%s: marker (%d,%d) falls outside %s (%dx%d, box %d)",
        m.name, m.x, m.y, m.map, mp.w, mp.h, mp.size))
      outside = outside + 1
    end
  end
end
if outside == 0 then print("ok   every marker sits inside its image") end

-- 3. a location with a marker must have sections of its own.
--    PopTracker's CalculateLocationState only walks loc.getSections(); it does
--    not aggregate from children, and a location with nothing visible returns
--    -1, which mapwidget skips as hidden. So a parent that hands all its
--    sections to children keeps its map_locations entry and silently stops
--    drawing. That is exactly what the Ice Cave split did until the parent got
--    ref sections back.
local sectionless = 0
local function checkSections(nodes)
  for _, n in ipairs(nodes) do
    if n.map_locations and #n.map_locations > 0 then
      if not n.sections or #n.sections == 0 then
        fails(string.format("%s has a map marker but no sections, so it will not draw", n.name))
        sectionless = sectionless + 1
      end
    end
    checkSections(n.children or {})
  end
end
for _, file in ipairs({ "locations/overworld.json", "locations/incentives.json" }) do
  checkSections(json.load(PACK .. "/" .. file))
end
if sectionless == 0 then print("ok   every marker's location has sections to show") end

-- 4. every section ref points at a section that exists
local byName = {}
local function indexSections(nodes)
  for _, n in ipairs(nodes) do
    for _, sec in ipairs(n.sections or {}) do
      byName[n.name .. "/" .. sec.name] = true
    end
    indexSections(n.children or {})
  end
end
for _, file in ipairs({ "locations/overworld.json", "locations/incentives.json" }) do
  indexSections(json.load(PACK .. "/" .. file))
end
local badRef = 0
local function checkRefs(nodes)
  for _, n in ipairs(nodes) do
    for _, sec in ipairs(n.sections or {}) do
      if sec.ref and not byName[sec.ref] then
        fails(string.format("%s/%s refs %q, which does not exist", n.name, sec.name, sec.ref))
        badRef = badRef + 1
      end
    end
    checkRefs(n.children or {})
  end
end
for _, file in ipairs({ "locations/overworld.json", "locations/incentives.json" }) do
  checkRefs(json.load(PACK .. "/" .. file))
end
if badRef == 0 then print("ok   every section ref resolves") end

-- 4b. every per-chest marker must equal what tools/marker_positions.json says
--     for that chest. This is what makes the coordinates reproducible without a
--     ROM: regenerate them and the JSON has to still agree.
do
  local mk = json.load(PACK .. "/tools/marker_positions.json")
  dofile(PACK .. "/scripts/autotracking/location_mapping.lua")
  -- location node name -> its single non-overworld marker
  local own = {}
  local function collect(nodes)
    for _, n in ipairs(nodes) do
      local secs = n.sections or {}
      if #secs == 1 and secs[1].item_count == 1 then
        for _, ml in ipairs(n.map_locations or {}) do
          if ml.map ~= "overworld" then own[n.name] = ml end
        end
      end
      collect(n.children or {})
    end
  end
  collect(json.load(PACK .. "/locations/overworld.json"))

  local checked, wrong = 0, 0
  for id, v in pairs(LOCATION_MAPPING) do
    if id < 512 and v[1] then
      local node = v[1]:match("^@(.*)/[^/]+$")
      local ml = node and own[node]
      local want = mk[tostring(id - 256)]
      if ml and want and #want == 1 then
        checked = checked + 1
        local w = want[1]
        if ml.map ~= w.map or ml.x ~= w.x or ml.y ~= w.y then
          fails(string.format("%s is at %s(%d,%d) but chest %d belongs at %s(%d,%d)",
            node, ml.map, ml.x, ml.y, id - 256, w.map, w.x, w.y))
          wrong = wrong + 1
        end
      end
    end
  end
  if wrong == 0 then
    print(string.format("ok   %d per-chest markers match the generated coordinates", checked))
  end
end

-- 5. the Ice Cave pilot: sixteen per-chest markers, on the three ice floors
local ice, iceMaps = 0, {}
for _, m in ipairs(markers) do
  if m.name:match("^Ice Cave ") then
    ice = ice + 1
    iceMaps[m.map] = (iceMaps[m.map] or 0) + 1
  end
end
if ice ~= 16 then
  fails(string.format("Ice Cave has %d per-chest markers, expected 16", ice))
else
  print("ok   Ice Cave has 16 per-chest markers")
end
-- Cardia Forest is per-chest, like Ice Cave: seven nodes, one box each. A node
-- carrying two boxes would mean two chests sharing a marker again.
local cardia, cardiaNodes = 0, 0
local function countCardia(nodes)
  for _, n in ipairs(nodes) do
    if n.name:match("^Cardia Forest ") or n.name == "Cardia Forest Incentive" then
      local own = 0
      for _, ml in ipairs(n.map_locations or {}) do
        if ml.map == "cardia" then own = own + 1 end
      end
      if own > 0 then
        cardiaNodes = cardiaNodes + 1
        cardia = cardia + own
        if own ~= 1 then
          fails(string.format("%s has %d boxes, expected exactly one", n.name, own))
        end
      end
    end
    countCardia(n.children or {})
  end
end
countCardia(json.load(PACK .. "/locations/overworld.json"))
if cardia ~= 7 or cardiaNodes ~= 7 then
  fails(string.format("Cardia Forest has %d boxes across %d nodes, expected 7 and 7", cardia, cardiaNodes))
else
  print("ok   Cardia Forest has 7 per-chest markers")
end

for map, want in pairs({ iceB1 = 5, iceB2 = 3, iceB3 = 8 }) do
  local got = iceMaps[map] or 0
  if got ~= want then
    fails(string.format("%s carries %d Ice Cave markers, expected %d", map, got, want))
  else
    print(string.format("ok   %-6s carries %d Ice Cave markers", map, got))
  end
end
for map in pairs(iceMaps) do
  if map ~= "iceB1" and map ~= "iceB2" and map ~= "iceB3" then
    fails("Ice Cave marker on unexpected map " .. map)
  end
end

print(fail == 0 and "\nALL PASS" or string.format("\n%d FAILURE(S)", fail))
os.exit(fail == 0 and 0 or 1)
