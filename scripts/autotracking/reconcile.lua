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
--                emulator bridge, so loading an older save un-marks chests --
--                and, through retractedHostedCode, the NPC and incentive cells
--                whose sections clear from a hosted code rather than a count
------------------------------------------------------------------

AP_CHECKED = {}
UAT_CHECKED = {}

-- Whether the bridge's first full snapshot of this session has landed. Global
-- so the tests can rewind a session, and so a reload of this script cannot
-- quietly re-arm it mid-run.
UAT_REASSERTED = false

local SECTION_IDS = nil
local SECTION_PATHS = nil   -- the same keys as an array, for ordered passes
local UNMAPPED_WARNED = {}
local UNRESOLVED_WARNED = {}

-- Sections are shared with the player, who is free to clear one we have not
-- seen cleared: a location behind a flag the game never sets, or one the
-- feeds simply have not reported yet. Recomputing from the union alone would
-- undo that on the next RAM tick, which during play arrives every few
-- seconds. So remember our own last write per section; anything that moved
-- since is the player, and it is carried forward as an offset. The feeds
-- still own everything they report -- an older save really does un-mark its
-- chests -- and the manual clears ride on top of that.
--
--   WRITTEN  path -> the value this file last assigned
--   MANUAL   path -> the player's deviation: a count for "@" sections,
--                    a boolean for the rest
local WRITTEN = {}
local MANUAL = {}

-- We are not the only writer. PopTracker restores its own saved state after
-- the pack's scripts have run, and a pack reload or a state file does the same
-- mid-session -- all of which move sections behind our back. Read as player
-- edits those become offsets that outlive every later feed update, and since
-- a restore moves the whole board at once the result is every section pinned
-- cleared for the rest of the session, with correct RAM unable to correct it.
--
-- A person clears one section at a time, so the giveaway is how many moved in
-- the same pass. Past a handful it is not a person, and the deviations are
-- ignored -- the recompute below then overwrites them with what the feeds
-- actually say, which is the right answer after a restore.
local MANUAL_BULK_LIMIT = 3

local function clamp(v, lo, hi)
  if v < lo then return lo end
  if v > hi then return hi end
  return v
end

-- path -> list of every AP location id that maps to it
local function buildSectionIndex()
  SECTION_IDS = {}
  SECTION_PATHS = {}
  for id, v in pairs(LOCATION_MAPPING) do
    local path = v[1]
    if path then
      local ids = SECTION_IDS[path]
      if not ids then
        ids = {}
        SECTION_IDS[path] = ids
        SECTION_PATHS[#SECTION_PATHS + 1] = path
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
    -- Not behind the debug flag on purpose. A path that does not resolve is a
    -- pack bug -- a renamed location, a section that moved -- and its whole
    -- failure mode is that checks quietly stop clearing. Someone has to be
    -- told, and the person watching is the one whose chest just did nothing.
    if not UNRESOLVED_WARNED[path] then
      UNRESOLVED_WARNED[path] = true
      print(string.format("reconcile: no location section named %s -- checks for it cannot clear", path))
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
    -- No separate cap on the offset: the clamp already floors the result at
    -- zero, so an offset larger than the slots the feeds leave unreported
    -- lands on "fully cleared" either way.
    local target = clamp(obj.ChestCount - n - (MANUAL[path] or 0), 0, obj.ChestCount)
    obj.AvailableChestCount = target
    WRITTEN[path] = target
  else
    local target = n > 0 or MANUAL[path] == true
    obj.Active = target
    WRITTEN[path] = target
  end
end

-- How far a section has moved since we last wrote it: a count for "@"
-- sections (positive = cleared by hand), the new value for the rest. nil when
-- it has not moved, or when we have never written it.
local function deviation(path, obj)
  local written = WRITTEN[path]
  if written == nil then
    return nil
  end
  if path:sub(1, 1) == "@" then
    local current = obj.AvailableChestCount
    if current == written then
      return nil
    end
    return written - current
  end
  if obj.Active == written then
    return nil
  end
  return obj.Active
end

-- Take note of what the player changed by hand, before a recompute overwrites
-- it. Bulk movement is somebody else writing (see MANUAL_BULK_LIMIT) and is
-- deliberately dropped on the floor.
--
-- The count that decides that has to be taken across the whole board. An
-- earlier version let markAPChecked pass a one-element list, which meant the
-- limit could never be reached on that path: an AP session replaying its
-- checks one id at a time after a state restore absorbed every restored
-- section as a hand clear, and pinned the lot.
local function absorbPlayerEdits(paths)
  local edits, n = {}, 0
  for _, path in ipairs(paths) do
    local obj = Tracker:FindObjectForCode(path)
    if obj then
      local d = deviation(path, obj)
      if d ~= nil then
        edits[path] = d
        n = n + 1
      end
    end
  end
  if n == 0 or n > MANUAL_BULK_LIMIT then
    if n > MANUAL_BULK_LIMIT then
      print(string.format("reconcile: %d sections moved at once -- treating that as a state "
        .. "restore rather than %d hand clears, and re-asserting what the feeds report", n, n))
    end
    return
  end
  for path, d in pairs(edits) do
    if type(d) == "boolean" then
      MANUAL[path] = d
    else
      local obj = Tracker:FindObjectForCode(path)
      MANUAL[path] = clamp((MANUAL[path] or 0) + d, 0, obj.ChestCount)
    end
  end
end

-- Hosted items are set here and never cleared here. What takes one down is a
-- whole-board reassert -- reassertBoard, or resetForNewGame -- and the reason
-- for the split is timing rather than direction: a code the player toggled by
-- hand has to survive the next RAM tick, which during play is a second or two
-- away, and a per-id clear on every tick is exactly what would not let it.
--
-- retractedHostedCode below is what asks for the reassert. It fires only on a
-- tick where the cartridge itself took a check back, which is a save being
-- reloaded rather than anything that happens during ordinary play.
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

-- Every hosted code any location can provide. These are what clear the
-- hosted_item-only sections in locations/incentives.json -- those carry no
-- item_count, so PopTracker greys the pin as soon as the code has a provider.
local function hostedCodes()
  local codes = {}
  for _, v in pairs(LOCATION_MAPPING) do
    if v[2] then
      codes[v[2]] = true
    end
  end
  return codes
end

-- The counterpart to applyHostedItem's one-way set. Only reachable from
-- resetForNewGame: within a session these stay monotonic, so a code the player
-- toggled by hand is not undone by the next RAM tick.
local function clearHostedItems()
  for code in pairs(hostedCodes()) do
    local obj = Tracker:FindObjectForCode(code)
    if obj then
      obj.Active = false
      if obj.CurrentStage ~= nil and obj.CurrentStage ~= 0 then
        obj.CurrentStage = 0
      end
    end
  end
end

-- Did the cartridge just take back a check whose section clears from a hosted
-- code? Those are the 26 rows in LOCATION_MAPPING that carry a second element:
-- the NPC turn-ins and the Incentive Locations pins, which have no item_count
-- and so grey out on the code having a provider rather than on a count.
--
-- Every other id in the mapping already walks back on its own, because
-- recomputeSection reads the union afresh and UAT_CHECKED is replaced wholesale
-- -- an older save really does un-mark its chests. A hosted code cannot follow
-- it, because the set is one-way (see applyHostedItem), so the Fairy stayed
-- turned in on a board where the Bottle was back in the bag and the turn-in was
-- open again. Reported from play on a reset, and it is every one of those 26
-- cells rather than that one.
--
-- AP_CHECKED is the exclusion rather than an afterthought. The server owns its
-- own retractions through onClear and never sends one otherwise, so an id it
-- has reported is not retracted by the cartridge disagreeing with it -- which
-- is what keeps a session with both feeds connected behaving the way an
-- Archipelago session does.
local function retractedHostedCode(previous)
  for id in pairs(previous) do
    if not UAT_CHECKED[id] and not AP_CHECKED[id] then
      local v = LOCATION_MAPPING[id]
      if v and v[2] then
        return id, v[2]
      end
    end
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
  absorbPlayerEdits(SECTION_PATHS)
  for _, path in ipairs(SECTION_PATHS) do
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

-- One id at a time, from the Archipelago feed. Scanning all ~256 sections per
-- id would be wasteful, and scanning only this one cannot see a bulk move, so
-- do the cheap check first and fall back to the whole board when this section
-- has actually moved since we wrote it.
--
-- The fallback re-asserts as well as counts. A replay walks hundreds of ids
-- through here; without recomputing in the same pass, every one of them would
-- rediscover the same untouched restore and log it again.
local function absorbForPath(path)
  local obj = Tracker:FindObjectForCode(path)
  if not obj or deviation(path, obj) == nil then
    return
  end
  applyAll()
end

-- One-shot audit the first time either feed sends anything. By then the
-- locations are loaded, so every path in the mapping can be resolved once and
-- the whole list of broken ones reported together -- rather than dribbling out
-- one at a time as the player happens to open the chests behind them.
local function auditSections()
  local broken, n = {}, 0
  for path in pairs(SECTION_IDS) do
    if not Tracker:FindObjectForCode(path) then
      broken[#broken + 1] = path
      UNRESOLVED_WARNED[path] = true
      n = n + 1
    end
  end
  if n == 0 then
    return
  end
  table.sort(broken)
  print(string.format("reconcile: %d location section(s) in LOCATION_MAPPING do not exist; "
    .. "checks for them cannot clear:", n))
  for _, path in ipairs(broken) do
    print("  " .. path)
  end
end

function reconcileInit()
  if not SECTION_IDS then
    buildSectionIndex()
    auditSections()
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
    absorbForPath(v[1])
    recomputeSection(v[1])
  end
  applyHostedItem(id)
  -- A hint on a location that has just been checked has stopped being a place
  -- to look. The server says so too, a moment later, but this is also the only
  -- signal on a check that came over the emulator bridge.
  if type(hintChecked) == "function" then
    hintChecked(id)
  end
end

-- UAT feed: full state, replaces whatever the bridge reported last time.
function setUATChecked(checked)
  reconcileInit()
  -- No unmapped warning here: the UAT feed screens its own ids and reports
  -- them with the byte index attached, which is more useful than an id alone.
  local had = next(UAT_CHECKED) ~= nil
  local previous = UAT_CHECKED
  UAT_CHECKED = checked or {}

  -- Going from checks to no checks at all, on a ROM we are already tracking,
  -- means a new file on the same seed (or a save from before the first chest).
  -- The flag page is back at lut_InitGameFlags, which carries no chest bit and
  -- no event bit anywhere, so this is what a fresh game genuinely looks like --
  -- and it wants the same wipe a different cartridge gets. Sections and RAM
  -- items would follow on their own; the hosted codes behind the Incentive
  -- Locations pins would not, because applyHostedItem is one-way.
  --
  -- On the edge only. Holding it every tick would keep re-clearing the board
  -- through the first few minutes of a run, before anything has been opened.
  if had and next(UAT_CHECKED) == nil then
    print("uat: the feed went from checks to none -- treating that as a new game")
    resetForNewGame()
    return
  end

  -- The bridge's first snapshot of the session, which is the counterpart of the
  -- one-shot the AP feed arms in scripts/autotracking.lua. Whatever is on the
  -- board at this point came from PopTracker's restore, not from a feed, and the
  -- bridge is now reporting ground truth for every chest, event and NPC -- so
  -- this is the moment to let it win. See reassertBoard.
  --
  -- Once only. Holding it every tick would undo a hosted code the player set by
  -- hand a second after they set it, which is the behaviour applyHostedItem's
  -- one-way rule exists to protect.
  if not UAT_REASSERTED then
    UAT_REASSERTED = true
    reassertBoard()
    return
  end

  -- A check the cartridge has taken back, on a cell that clears from a hosted
  -- code. applyAll cannot lower one, so the whole board is re-asserted instead:
  -- clearHostedItems drops the lot and applyAll puts back everything still in
  -- either feed, which leaves exactly the ones the cartridge and the server
  -- still report.
  --
  -- The cost is the hand-set hosted codes, which go with it -- the same deal
  -- reassertBoard already makes at the bridge's first snapshot. It is paid only
  -- on a tick where a save was reloaded, rather than on every tick, which is
  -- what makes it a different bargain from lowering the codes in applyAll.
  local id, code = retractedHostedCode(previous)
  if id then
    print(string.format("uat: the feed took back location %s (%s) -- re-asserting the board", tostring(id), code))
    reassertBoard()
    return
  end

  applyAll()
end

-- Called from onClear: a new AP session replays its checks from scratch.
-- UAT state is independent of the AP server and is deliberately left alone.
-- The manual offsets do go, though: onClear wipes every item too, so this is
-- a fresh board rather than a mid-session update the player might be reading.
--
-- The hosted codes go with them. They are the one thing here applyAll cannot
-- take back down on its own, because applyHostedItem is one-way, so without
-- this the previous seed's NPCs and incentive pins survive an AP connect for
-- the rest of the session. PopTracker restores its own saved state on load,
-- which makes "the previous seed" the ordinary case for anyone who tracked one
-- before, and Incentive Locations is the tab the pack opens on -- so a seed
-- that had not been started came up looking finished. resetForNewGame has
-- cleared these since the 2026-08-19 seed swap; this path was left out, and
-- connecting the bridge was the only way to get a clean board.
--
-- Nothing a live feed owns is lost: applyAll re-applies the hosted codes for
-- everything still in AP_CHECKED and UAT_CHECKED, and AP replays its own
-- checks through markAPChecked straight after. A code the player set by hand
-- does go, which is the same deal the manual offsets get just above.
function resetChecked()
  reconcileInit()
  AP_CHECKED = {}
  WRITTEN = {}
  MANUAL = {}
  Tracker.BulkUpdate = true
  clearHostedItems()
  Tracker.BulkUpdate = false
  applyAll()
end

-- Re-assert the whole board from the feeds, for a caller with reason to think
-- something else moved it.
--
-- PopTracker restores its own saved state after the pack's scripts have run,
-- and nothing tells a pack when that has happened. resetChecked's recompute
-- runs on connect, so a restore landing after it gets the last word -- and on
-- a slot with no checks yet there is nothing to replay, so markAPChecked never
-- runs and absorbForPath never gets to notice. The restored board then stands
-- with no feed event able to correct it.
--
-- applyAll is nearly the right answer: absorbPlayerEdits sees the whole board
-- moved in one pass, drops the deviations as a restore rather than as hand
-- clears, and the recompute puts back what the feeds actually report.
--
-- The hosted codes are the exception, for the same reason resetChecked has to
-- clear them: applyHostedItem is one-way, so a code the restore brought back is
-- one applyAll cannot take down again. Without this the AP path only looked
-- fixed -- resetChecked clears them on connect and the restore lands after it --
-- and the UAT path had nothing at all, so a hosted code left over from an older
-- board greyed its Incentive Locations pin for the rest of the session. That is
-- what hid the Dwarf Cave Adamant turn-in on 2026-08-28, with the bridge
-- connected, the ROM unchanged and no AP session to run onClear.
--
-- Nothing a live feed owns is lost: applyAll re-applies the hosted codes for
-- everything in AP_CHECKED and UAT_CHECKED on the way back up. A code set by
-- hand does go, which is the deal the manual offsets get in resetChecked.
function reassertBoard()
  reconcileInit()
  Tracker.BulkUpdate = true
  clearHostedItems()
  Tracker.BulkUpdate = false
  applyAll()
end

-- Called when the bridge reports a different cartridge than the one we have
-- been tracking. Everything the UAT feed owns goes: the chest/event set, the
-- manual offsets taken against the old board, the RAM-derived items, and the
-- hosted codes that grey out the Incentive Locations pins. Without this the
-- raise-only halves of the pack carry the finished seed straight into the next
-- one -- which is exactly what they did, in full, on 2026-08-19.
--
-- AP_CHECKED is deliberately untouched. An Archipelago session owns its own
-- reset through onClear and replays every check from scratch there; wiping it
-- here would drop checks the server is not going to send again.
function resetForNewGame()
  reconcileInit()
  UAT_CHECKED = {}
  WRITTEN = {}
  MANUAL = {}
  Tracker.BulkUpdate = true
  if clearRamDerivedItems then
    clearRamDerivedItems()
  end
  clearHostedItems()
  -- The entrance pins are not in SECTION_PATHS -- that index is built from
  -- LOCATION_MAPPING, which is Archipelago location ids, and a door is not one.
  -- So nothing else here reaches them, and a new cartridge would otherwise open
  -- on the previous seed's doors.
  if clearEntranceMarks then
    clearEntranceMarks()
  end
  Tracker.BulkUpdate = false
  applyAll()
end
