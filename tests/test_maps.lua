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

-- JPEG keeps its dimensions in a frame header that sits an arbitrary distance
-- in, behind however many other segments the encoder wrote, so unlike PNG there
-- is no fixed offset to read. Walking the segment chain is still only a few
-- lines, and it is what lets nooverworldmap.jpg be bounds-checked like anything
-- else -- see the note on the two map tables below for why that mattered.
local function jpegSize(data)
  if data:sub(1, 2) ~= "\255\216" then return nil end
  local i = 3
  while i + 3 <= #data do
    if data:byte(i) ~= 0xFF then return nil end
    local marker = data:byte(i + 1)
    if marker >= 0xD0 and marker <= 0xD9 then
      i = i + 2                                   -- standalone, no length
    else
      -- SOF0..SOF15 carry the size; 0xC4, 0xC8 and 0xCC are not frame headers.
      if marker >= 0xC0 and marker <= 0xCF
         and marker ~= 0xC4 and marker ~= 0xC8 and marker ~= 0xCC then
        return string.unpack(">I2", data, i + 7), string.unpack(">I2", data, i + 5)
      end
      i = i + 2 + string.unpack(">I2", data, i + 2)
    end
  end
  return nil
end

-- PNG keeps width and height big-endian in the IHDR, at bytes 17-24. That is
-- the whole reason this check can live in the Lua suite instead of a tool with
-- an image dependency.
local function imageSize(path)
  local f = io.open(path, "rb")
  if not f then return nil, "missing" end
  local head = f:read(24)
  if head and #head >= 24 and head:sub(2, 4) == "PNG" then
    f:close()
    return string.unpack(">I4", head, 17), string.unpack(">I4", head, 21)
  end
  f:seek("set", 0)
  local data = f:read("a")
  f:close()
  local w, h = jpegSize(data or "")
  if w then return w, h end
  return nil, "unmeasured"
end

-- Every map name the pack defines, and how big its art is -- in two tables,
-- because the pack loads two. scripts/init.lua reads maps.json and then, on the
-- NOverworld variants only, NOverworldMaps.json over the top, later entries
-- winning. So "incentives" means overworld.png on a standard tracker and
-- nooverworldmap.jpg on a No-Overworld one.
--
-- This used to be one merged table, which is worse than it sounds: the jpg row
-- overwrote the png one, and a jpg was unmeasurable, so check 2's `if mp.w`
-- guard silently skipped every incentive marker in BOTH trees -- 54 pins that
-- looked checked and were not. Measuring the jpg fixes the guard; keeping the
-- tables apart is what makes each tree checked against the art its own variant
-- actually opens.
local function loadMaps(file, into)
  local out = into or {}
  for _, m in ipairs(json.load(PACK .. "/" .. file)) do
    local w, h = imageSize(PACK .. "/" .. m.img)
    if not w and h == "missing" then
      fails(string.format("map %q points at %s, which does not exist", m.name, m.img))
    end
    out[m.name] = { w = w, h = h, img = m.img, size = m.location_size or 0 }
  end
  return out
end
local maps = loadMaps("maps/maps.json")
local novMaps = loadMaps("maps/NOverworldMaps.json", (function()
  local copy = {}
  for k, v in pairs(maps) do copy[k] = v end
  return copy
end)())

-- Which table a marker is judged against: the tree it came from decides.
local function mapsFor(m) return m.nov and novMaps or maps end

-- Every location file the pack loads. The two NOverworld trees were outside
-- this test until now, which mattered once the No-Overworld variants stopped
-- sharing the standard tree: their dungeon markers sit on their own art, at
-- their own crop, so nothing else would notice one drifting off the edge.
local LOCATION_FILES = {
  "locations/overworld.json",
  "locations/incentives.json",
  "locations/NOverworld/overworld.json",
  "locations/NOverworld/incentives.json",
}

-- every marker in every location file
local markers = {}
local into = markers
local inNOverworld = false
local function walk(nodes)
  for _, n in ipairs(nodes) do
    for _, ml in ipairs(n.map_locations or {}) do
      into[#into + 1] = { name = n.name, map = ml.map, x = ml.x, y = ml.y,
                          nov = inNOverworld }
    end
    walk(n.children or {})
  end
end
for _, file in ipairs(LOCATION_FILES) do
  inNOverworld = file:find("^locations/NOverworld/") ~= nil
  walk(json.load(PACK .. "/" .. file))
end
inNOverworld = false

-- The counting checks below -- sixteen Ice Cave chests, seven in Cardia Forest
-- -- are about what the tree contains, not about how many copies of it the
-- pack loads. They run on the standard tree alone; check 6 is what says the
-- No-Overworld tree holds the same locations, so checking one is enough.
local stdMarkers = {}
into = stdMarkers
for _, file in ipairs({ "locations/overworld.json", "locations/incentives.json" }) do
  walk(json.load(PACK .. "/" .. file))
end
into = markers
print(string.format("ok   %d markers across %d maps", #markers, (function()
  local n = 0; for _ in pairs(novMaps) do n = n + 1 end; return n
end)()))

-- 1. every marker names a map the pack actually defines
local unknown = 0
for _, m in ipairs(markers) do
  if not mapsFor(m)[m.map] then
    fails(string.format("%s: marker on undefined map %q", m.name, tostring(m.map)))
    unknown = unknown + 1
  end
end
if unknown == 0 then print("ok   every marker names a defined map") end

-- 2. every marker sits inside its image. PopTracker takes x/y as the centre,
--    so a marker within half a box of the edge is clipped rather than drawn.
local outside = 0
for _, m in ipairs(markers) do
  local mp = mapsFor(m)[m.map]
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
local unmeasured = 0
for _, m in ipairs(markers) do
  local mp = mapsFor(m)[m.map]
  if mp and not mp.w then unmeasured = unmeasured + 1 end
end
if unmeasured > 0 then
  -- The whole point of the rewrite above: a marker that cannot be measured is
  -- a marker that is not checked, and that has to be said out loud rather than
  -- passing as a clean run.
  fails(string.format("%d markers sit on art this test cannot measure",
    unmeasured))
end
if outside == 0 and unmeasured == 0 then
  print("ok   every marker sits inside its image")
end

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
for _, file in ipairs(LOCATION_FILES) do
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
for _, file in ipairs(LOCATION_FILES) do
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
for _, file in ipairs(LOCATION_FILES) do
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


-- 4c. the same reproducibility guarantee for the NPC turn-ins that carry a
--     dungeon marker. Chests come out of the map tile data; NPCs come out of
--     lut_MapObjects, so they get their own extractor and their own file, but
--     the pixel maths is the one in tools/make_markers.py and the answer has to
--     agree with what is in the location JSON.
do
  local npcs = json.load(PACK .. "/tools/npc_positions.json")
  local cal = json.load(PACK .. "/tools/map_calibration.json")

  -- Which node carries which NPC's marker, and which calibrated map it is on.
  local PLACED = {
    ["Dwarf Cave Smith"]   = { npc = "smith",   map = "dwarves" },
    ["Dwarf Cave Nerrick"] = { npc = "nerrick", map = "dwarves" },
    ["Sarda's Cave"]       = { npc = "sarda",   map = "sarda" },
  }

  local nodes = {}
  local function collect(list)
    for _, n in ipairs(list) do
      nodes[n.name] = n
      collect(n.children or {})
    end
  end
  collect(json.load(PACK .. "/locations/overworld.json"))

  for name, want in pairs(PLACED) do
    local node = nodes[name]
    local entry = cal[want.map]
    local places = npcs[want.npc]
    if not node then
      fails(string.format("no location node named %q for the %s marker", name, want.npc))
    elseif not entry then
      fails(string.format("%s has no calibration entry", want.map))
    elseif not places or #places ~= 1 then
      fails(string.format("npc_positions.json does not place %s exactly once", want.npc))
    else
      local pos = places[1]
      if pos.map_id ~= entry.rom_map_id then
        fails(string.format("%s is on ROM map %d but %s is calibrated for %d",
          want.npc, pos.map_id, want.map, entry.rom_map_id))
      else
        -- make_markers.py: offset + tile * tile_px + half
        local r = entry.regions[1]
        local half = entry.tile_px // 2
        local x = r.offset_x + pos.tile_col * entry.tile_px + half
        local y = r.offset_y + pos.tile_row * entry.tile_px + half
        -- A node can carry more than one pin -- Sarda's Cave has its overworld
        -- pin first and its dungeon pin second -- so this picks the one on the
        -- map being checked rather than whichever was written first.
        local ml
        for _, cand in ipairs(node.map_locations or {}) do
          if cand.map == want.map then ml = cand end
        end
        if not ml then
          fails(string.format("%s has no map_location on %s", name, want.map))
        elseif ml.x ~= x or ml.y ~= y then
          fails(string.format("%s is at %s(%d,%d) but %s belongs at %s(%d,%d)",
            name, ml.map, ml.x or -1, ml.y or -1, want.npc, want.map, x, y))
        else
          print(string.format("ok   %-22s marker matches %s at %s(%d,%d)",
            name, want.npc, want.map, x, y))
        end
      end
    end
  end
end

-- 4d. the calibration entries derived from an upstream pixel instead of solved
--     from chest sprites. Their maps hold no chest, so 4b can never reach them
--     and solve_calibration.py reports "ok 0/0" for each. What is still
--     checkable is the correspondence they were built on: the NPC's tile comes
--     off the cartridge (npc_positions.json) and the pixel comes from
--     upstream's art, and the offset is the only thing that joins the two. If
--     either end is edited, the offset stops being the answer and this says so.
do
  local npcs = json.load(PACK .. "/tools/npc_positions.json")
  local cal = json.load(PACK .. "/tools/map_calibration.json")

  local checked = 0
  for map, entry in pairs(cal) do
    local d = type(entry) == "table" and type(entry._derived_from) == "table"
      and entry._derived_from or nil
    if d then
      local pos
      for _, p in ipairs(npcs[d.npc] or {}) do
        if p.map_id == entry.rom_map_id then pos = p end
      end
      if not pos then
        fails(string.format("%s is derived from %s, which npc_positions.json "
          .. "does not place on ROM map %d", map, tostring(d.npc), entry.rom_map_id))
      elseif #entry.regions ~= 1 then
        fails(string.format("%s has %d regions; a derived entry describes one",
          map, #entry.regions))
      else
        -- make_markers.py: offset + tile * tile_px + half
        local r = entry.regions[1]
        local half = entry.tile_px // 2
        local x = r.offset_x + pos.tile_col * entry.tile_px + half
        local y = r.offset_y + pos.tile_row * entry.tile_px + half
        if x ~= d.pixel[1] or y ~= d.pixel[2] then
          fails(string.format("%s puts %s at (%d,%d); it was derived from (%d,%d)",
            map, d.npc, x, y, d.pixel[1], d.pixel[2]))
        else
          checked = checked + 1
          print(string.format("ok   %-8s reproduces %s at (%d,%d)", map, d.npc, x, y))
        end
      end
    end
  end
  if checked == 0 then
    fails("no calibration entry carries a machine-readable _derived_from")
  end
end

-- 5. the Ice Cave pilot: sixteen per-chest markers, on the three ice floors
local ice, iceMaps = 0, {}
for _, m in ipairs(stdMarkers) do
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

-- 6. the two dungeon trees hold the same locations.
--
-- locations/NOverworld/overworld.json exists because the art does: a
-- No-Overworld cartridge and a standard one disagree about 34 to 39 of the 61
-- maps, so regen_maps.py crops a set for each and the same tile lands on a
-- different pixel in each. Everything except those pixels has to stay in step
-- -- the same locations, the same sections, the same access rules -- or a
-- No-Overworld player is tracking a different game. Two files that are meant
-- to agree and are never compared is how the pack ended up loading a dungeon
-- tree that did not exist at all.
do
  local function shape(nodes, path, out)
    for _, n in ipairs(nodes) do
      local here = path .. "/" .. (n.name or "?")
      local secs = {}
      for _, sec in ipairs(n.sections or {}) do
        -- " OR " between alternatives, because "," already separates the
        -- ANDed codes inside one: joined with a comma, ["a,b"] (a AND b) and
        -- ["a","b"] (a OR b) are the same string, and that is exactly the
        -- drift this field exists to show.
        secs[#secs + 1] = (sec.name or "") .. "|" .. (sec.ref or "") .. "|" ..
          tostring(sec.item_count) .. "|" .. (sec.hosted_item or "") .. "|" ..
          table.concat(sec.access_rules or {}, " OR ") .. "|" ..
          table.concat(sec.visibility_rules or {}, " OR ")
      end
      -- map names, not pixels: which map a marker is on must match, where on
      -- it must not, because that is the whole difference between the two.
      --
      -- The marker's restrict_visibility_rules travels with the map name, and
      -- the section's visibility_rules with the section above: both are
      -- generated -- pin_visibility.py stamps one, incentives the other -- and
      -- neither was compared, so a rule landing on one tree and not the other
      -- passed here in silence. Which is the exact drift this check exists for.
      local onmaps = {}
      for _, ml in ipairs(n.map_locations or {}) do
        onmaps[#onmaps + 1] = ml.map .. "[" ..
          table.concat(ml.restrict_visibility_rules or {}, " OR ") .. "]"
      end
      -- the node's own rules as well as its sections'. A split child carries its
      -- requirement on the node -- "Coneria Castle Chests 1" is access_rules
      -- ["key"] with a bare section under it -- so a shape built from sections
      -- alone would let one tree gain or lose a rule without a word.
      out[here] = table.concat(n.access_rules or {}, " OR ") .. " :: " ..
        table.concat(secs, ";") .. " @ " .. table.concat(onmaps, ",")
      shape(n.children or {}, here, out)
    end
    return out
  end
  local a = shape(json.load(PACK .. "/locations/overworld.json"), "", {})
  local b = shape(json.load(PACK .. "/locations/NOverworld/overworld.json"), "", {})
  local drift, n = 0, 0
  for k, v in pairs(a) do
    n = n + 1
    if b[k] == nil then
      fails("NOverworld tree is missing " .. k)
      drift = drift + 1
    elseif b[k] ~= v then
      fails(string.format("%s differs between the trees:\n       std %s\n       nov %s",
                          k, v, b[k]))
      drift = drift + 1
    end
  end
  for k in pairs(b) do
    if a[k] == nil then
      fails("NOverworld tree has an extra " .. k)
      drift = drift + 1
    end
  end
  if drift == 0 then
    print(string.format("ok   both dungeon trees hold the same %d locations", n))
  end
end

-- 7. the incentive map and the dungeon map must agree about a slot's rule.
--
-- Every incentive slot is in both trees: locations/incentives.json draws it on
-- the incentive poster and locations/overworld.json draws it where the check
-- actually is. Same check, same requirement -- so a player who opens the other
-- tab must not be told something different.
--
-- They drifted. The per-chest marker split moved Ordeals' incentive into a
-- child location and left its ["earlyOrdeals", "crown"] behind, so the slot was
-- gated on one tab and free on the other for as long as nothing compared them.
-- That is check 6's lesson in a second place: two files meant to agree and
-- never compared.
--
-- A rule here is a set of alternatives and each alternative a set of codes, so
-- everything is sorted and de-duplicated before comparing: order never meant
-- anything (three slots write the same codes in a different order and always
-- did) and "key AND key", which is what a child under a keyed parent produces,
-- is just "key".
--
-- Not compared: the ^$incentiveSlot|<flag> term, which only the incentive tree
-- carries and which decides a colour rather than access.
--
-- Both pairs are compared, the standard one and the No-Overworld one. The
-- No-Overworld pair used to be exempt, on the grounds that its incentive sheet
-- was hand-authored against upstream's poster and disagreed about twenty slots
-- anyway. That exemption is what let the mode guards land on one of the two
-- sheets and not the other: the guarded rules went into
-- locations/incentives.json, which the two NoMap variants load, while the two
-- map variants load locations/NOverworld/incentives.json and kept the old
-- geography. Nothing said so, because the only check that would have was off
-- for exactly that pair.
--
-- What stays hand-authored is where the pins sit, which is docs/ROADMAP.md item
-- 3 and is not what this check reads. The rules are the standard sheet's now.
do
  local function copy(t)
    local out = {}
    for i, v in ipairs(t) do out[i] = v end
    return out
  end

  -- one access_rules list -> a canonical string, or nil if it constrains nothing
  local function canon(rules)
    local alts = {}
    for _, alt in ipairs(rules) do
      local terms = {}
      for term in string.gmatch(alt, "[^,]+") do
        if not string.match(term, "^%^%$incentiveSlot") then
          terms[#terms + 1] = term
        end
      end
      table.sort(terms)
      -- one alternative that constrains nothing satisfies the whole OR, so the
      -- rule as a whole constrains nothing. Not reachable on today's data --
      -- every ^$incentiveSlot term sits either alone or in every alternative --
      -- but the next incentive rule written the other way would otherwise be
      -- reported as drift against a tree that correctly has no rule at all.
      if #terms == 0 then return nil end
      alts[#alts + 1] = table.concat(terms, ",")
    end
    if #alts == 0 then return nil end
    table.sort(alts)
    return table.concat(alts, "|")
  end

  -- the chain of rules a section inherits, as a sorted set: AND commutes and
  -- repeats itself for nothing.
  local function express(chain)
    local seen, out = {}, {}
    for _, c in ipairs(chain) do
      if not seen[c] then
        seen[c] = true
        out[#out + 1] = c
      end
    end
    table.sort(out)
    return #out == 0 and "(free)" or table.concat(out, " AND ")
  end

  local function slots(file)
    local out = {}
    local function walk(nodes, chain)
      for _, n in ipairs(nodes) do
        local here = chain
        local c = canon(n.access_rules or {})
        if c then here = copy(chain); here[#here + 1] = c end
        for _, sec in ipairs(n.sections or {}) do
          if sec.hosted_item and not sec.ref then
            local full = here
            local sc = canon(sec.access_rules or {})
            if sc then full = copy(here); full[#full + 1] = sc end
            -- every hosting, not the last one seen: cardiaIncentive is hosted
            -- twice in each tree -- Bahamut's Cave behind the ship route and
            -- Cardia Forest behind the airship alone -- so a single slot is
            -- a set of rules, and keying by name alone compared one and
            -- silently dropped the other.
            local at = out[sec.hosted_item]
            if not at then at = {}; out[sec.hosted_item] = at end
            at[#at + 1] = express(full)
          end
        end
        walk(n.children or {}, here)
      end
    end
    walk(json.load(PACK .. "/" .. file), {})
    -- sorted so the two trees can be compared as multisets: which node hosts
    -- which copy is a fact about the art, the rules it carries are not.
    for _, rules in pairs(out) do table.sort(rules) end
    return out
  end

  -- Known, and older than this check. The Gaia node's northern-docks route
  -- reads "northernDocks,hwyOrdeals,gaiaMountain,ship,canal" on the incentive
  -- poster and drops hwyOrdeals in the dungeon tree, identically in upstream's
  -- 9ed47a4 and here, so it is neither drift nor anything this pack did.
  -- Which of the two is right is not answerable from the location files, and
  -- guessing would be a standard-mode rule change with nothing behind it.
  -- Filed in docs/ISSUES.md; named here so the rest of the check can be strict.
  local KNOWN = { fairy = true }

  -- The four orb-lit slots are the incentive poster's own: they light the orb
  -- panel from a flag and there is no dungeon location behind them, so they
  -- are absent from the dungeon tree by design. Named, because "absent" is
  -- otherwise indistinguishable from a hosted_item that has been renamed or
  -- typo'd -- which is precisely what unlinks an incentive marker -- and
  -- skipping every unmatched slot let that through with the count one lower.
  local POSTER_ONLY = {
    airorblit = true, earthorblit = true, fireorblit = true, waterorblit = true,
  }

  local function same(a, b)
    if #a ~= #b then return false end
    for i = 1, #a do if a[i] ~= b[i] then return false end end
    return true
  end

  local PAIRS = {
    { "standard", "locations/incentives.json", "locations/overworld.json" },
    { "No-Overworld", "locations/NOverworld/incentives.json",
      "locations/NOverworld/overworld.json" },
  }

  for _, pair in ipairs(PAIRS) do
    local label, incFile, owFile = pair[1], pair[2], pair[3]
    local inc, ow = slots(incFile), slots(owFile)
    local drift, shared, waived, only = 0, 0, 0, 0
    for slot, rules in pairs(inc) do
      if POSTER_ONLY[slot] then
        only = only + 1
      elseif not ow[slot] then
        fails(string.format("%s: the dungeon tree hosts no %q, which the incentive tree does",
          label, slot))
        drift = drift + 1
      elseif KNOWN[slot] then
        waived = waived + 1
      else
        shared = shared + 1
        if not same(rules, ow[slot]) then
          fails(string.format("%s: the two tabs disagree about %q:\n       incentives %s\n       overworld  %s",
            label, slot, table.concat(rules, " / "), table.concat(ow[slot], " / ")))
          drift = drift + 1
        end
      end
    end
    if drift == 0 then
      print(string.format("ok   %s: %d incentive slots carry the same rule on both tabs (%d waived, %d poster-only)",
                          label, shared, waived, only))
    end
  end
end

print(fail == 0 and "\nALL PASS" or string.format("\n%d FAILURE(S)", fail))
os.exit(fail == 0 and 0 or 1)
