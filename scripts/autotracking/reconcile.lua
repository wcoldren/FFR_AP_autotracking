------------------------------------------------------------------
-- Shared location reconcile core.
--
-- Both autotracking feeds (Archipelago and UAT) end up clearing the same
-- PopTracker sections, so neither one may simply decrement a counter -- two
-- feeds reporting the same location would clear it twice. Instead each feed
-- keeps a set of checked AP location ids, and section counts are recomputed
-- from the union of those sets. Reporting the same id twice is then a no-op,
-- whichever feed it came from.
--
--   AP_CHECKED   grows as the server reports checks, cleared by onClear
--   UAT_CHECKED  replaced wholesale on every full-state message from the
--                emulator bridge, so loading an older save un-marks chests
------------------------------------------------------------------

AP_CHECKED = {}
UAT_CHECKED = {}

local SECTION_IDS = nil
local UNMAPPED_WARNED = {}

-- path -> list of every AP location id that maps to it
local function buildSectionIndex()
  SECTION_IDS = {}
  for id, v in pairs(LOCATION_MAPPING) do
    local path = v[1]
    if path then
      local ids = SECTION_IDS[path]
      if not ids then
        ids = {}
        SECTION_IDS[path] = ids
      end
      ids[#ids + 1] = id
    end
  end
end

local function isChecked(id)
  return AP_CHECKED[id] or UAT_CHECKED[id]
end

-- Recompute one section from the union. Clamped at zero so a mapping row with
-- more ids than the section has chests misplaces exactly one location instead
-- of driving the count negative.
local function recomputeSection(path)
  local ids = SECTION_IDS[path]
  if not ids then
    return
  end
  local obj = Tracker:FindObjectForCode(path)
  if not obj then
    if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
      print(string.format("reconcile: could not find object for code %s", path))
    end
    return
  end
  local n = 0
  for _, id in ipairs(ids) do
    if isChecked(id) then
      n = n + 1
    end
  end
  if path:sub(1, 1) == "@" then
    obj.AvailableChestCount = math.max(0, obj.ChestCount - n)
  else
    obj.Active = n > 0
  end
end

-- Hosted items stay monotonic: set on check, never cleared. That matches how
-- the pack has always behaved (onClear's hosted-item reset is commented out)
-- and avoids fighting a player who toggled one by hand.
local function applyHostedItem(id)
  local v = LOCATION_MAPPING[id]
  if not (v and v[2]) then
    return
  end
  local obj = Tracker:FindObjectForCode(v[2])
  if obj then
    obj.Active = true
  elseif AUTOTRACKER_ENABLE_DEBUG_LOGGING then
    print(string.format("reconcile: could not find object for code %s", v[2]))
  end
end

-- Unmapped ids are the tripwire for gaps in LOCATION_MAPPING. Warn once each
-- rather than failing silently.
local function warnUnmapped(id)
  if UNMAPPED_WARNED[id] then
    return
  end
  UNMAPPED_WARNED[id] = true
  print(string.format("reconcile: no LOCATION_MAPPING entry for AP location id %s", tostring(id)))
end

local function applyAll()
  Tracker.BulkUpdate = true
  for path, _ in pairs(SECTION_IDS) do
    recomputeSection(path)
  end
  for id, _ in pairs(AP_CHECKED) do
    applyHostedItem(id)
  end
  for id, _ in pairs(UAT_CHECKED) do
    applyHostedItem(id)
  end
  Tracker.BulkUpdate = false
end

function reconcileInit()
  if not SECTION_IDS then
    buildSectionIndex()
  end
end

-- Archipelago feed: one id at a time, monotonic.
function markAPChecked(id)
  reconcileInit()
  if AP_CHECKED[id] then
    return
  end
  AP_CHECKED[id] = true
  local v = LOCATION_MAPPING[id]
  if not v then
    warnUnmapped(id)
    return
  end
  if v[1] then
    recomputeSection(v[1])
  end
  applyHostedItem(id)
end

-- UAT feed: full state, replaces whatever the bridge reported last time.
function setUATChecked(checked)
  reconcileInit()
  -- No unmapped warning here: the UAT feed screens its own ids and reports
  -- them with the byte index attached, which is more useful than an id alone.
  UAT_CHECKED = checked or {}
  applyAll()
end

-- Called from onClear: a new AP session replays its checks from scratch.
-- UAT state is independent of the AP server and is deliberately left alone.
function resetChecked()
  reconcileInit()
  AP_CHECKED = {}
  applyAll()
end
