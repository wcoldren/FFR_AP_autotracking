-- The hints the server already publishes, and where each one lands on this board.
--
-- A hint names an Archipelago location; the board calls it something else. That
-- is the defect this answers, and scripts/autotracking.lua's describeLocation is
-- what says the correspondence out loud.
--
-- **Not the scout handler**, which is the obvious wrong turning. PopTracker's
-- AddScoutHandler fires on LocationInfo -- replies to scouts this pack asked
-- for -- and LocationScouts is refused unless the manifest carries "apmanual"
-- or "aphintgame" (AUTOTRACKING.md:162), which this one deliberately does not:
-- those let a pack *create* hints, which is a different and far more invasive
-- feature than reading them.
--
-- Hints reach an ordinary client through data storage instead. The server keeps
-- them under "_read_hints_<team>_<slot>" (MultiServer.py:876), answers a Get on
-- it and rebroadcasts the whole list whenever it changes -- including after a
-- check, since register_location_checks calls recheck_hints and then
-- on_changed_hints. Archipelago's own CommonClient watches exactly this key.
--
-- The pack has had AddSetReplyHandler and AddRetrievedHandler registered since
-- long before this, and never called Get or SetNotify, so both were dead. They
-- are the channel now.

-- NetUtils.py:15-21. A found hint is kept rather than deleted, so the status is
-- the signal and disappearance is not.
local HINT_FOUND = 40

-- HintStatus is PopTracker's Highlight, colour for colour, which is why a hint
-- is not flatly gold. Archipelago paints unspecified white, no-priority
-- slateblue, avoid salmon and priority plum (NetUtils.status_colors), and
-- PopTracker's defaults are white, slateblue, red and gold for the same four
-- (mapwidget.cpp:54-59, whose comment says plum is hard to see so it is drawn
-- gold). So the status is carried straight through rather than flattened, and
-- a hint AP says to avoid does not read as one it says to chase.
local HINT_HIGHLIGHT = {
  [0] = "Unspecified", [10] = "NoPriority", [20] = "Avoid", [30] = "Priority",
}

-- Which status wins where two live hints land on the same pin -- several AP ids
-- can share one section path. Strongest statement first.
local STATUS_RANK = { [30] = 4, [20] = 3, [10] = 2, [0] = 1 }

-- Unspecified rather than Priority for a status this table does not know, and
-- the fallback is the whole point: AP has extended HintStatus once already, so
-- the next value it adds arrives here. Gold is the loudest thing this board can
-- say, and saying it about a status nobody has read yet is the same mistake as
-- flattening Avoid to gold, which the table above exists to avoid. It also puts
-- the two fallbacks in agreement -- STATUS_RANK gives an unknown status the
-- lowest rank, so painting it the strongest colour contradicted the rank in the
-- one case both are reached.
local function levelFor(status)
  local name = HINT_HIGHLIGHT[status] or "Unspecified"
  return Highlight and Highlight[name]
end

-- id -> {path, status} for every hint standing on this board.
local standing = {}
-- Which paths this owner currently holds, so one leaving can be put out.
local claimed = {}

-- Which ids have already been announced, so a rebroadcast -- and the server
-- sends the whole list every time -- does not reprint every standing hint.
local announced = {}
local unmapped = {}
local key = nil

-- "_read_hints_<team>_<slot>", or nil when there is no slot to ask about.
--
-- Cached per connect rather than per call because a reconnect to a different
-- slot changes it, and a stale key would go on matching payloads meant for the
-- board we are no longer tracking.
function hintsKey()
  local slot = Archipelago.PlayerNumber
  if type(slot) ~= "number" or slot < 0 then
    return nil
  end
  -- A host older than 0.25.2 answers nil for the team (AUTOTRACKING.md:147),
  -- and team 0 is the only team almost every room has.
  local team = Archipelago.TeamNumber
  if type(team) ~= "number" or team < 0 then
    team = 0
  end
  return string.format("_read_hints_%d_%d", team, slot)
end

-- Ask for the hints that already stand, and to be told about later ones.
--
-- Both, and neither is redundant: Get answers with the hints placed before this
-- tracker was ever opened, which is the common case, and SetNotify covers every
-- one after. Called from a clear handler because that is where PopTracker's own
-- documentation puts them, and because the slot number is not known before it.
function subscribeHints()
  key = hintsKey()
  if not key then
    return false
  end
  if type(Archipelago.SetNotify) == "function" then
    Archipelago:SetNotify({ key })
  end
  if type(Archipelago.Get) == "function" then
    Archipelago:Get({ key })
  end
  return true
end

-- Is this key the hints key?
function isHintsKey(k)
  return k ~= nil and k == (key or hintsKey())
end

local function warnUnmappedHint(id)
  if unmapped[id] then
    return
  end
  unmapped[id] = true
  -- Named rather than numbered, unlike reconcile's own warning: somebody is
  -- reading a hint that says this, and the id alone does not tell them what.
  -- These are the twelve Deep Dungeon locations the AP world carries and
  -- LOCATION_MAPPING does not; docs/ROADMAP.md section 3 has them.
  print(string.format('hint: no pin on this board for Archipelago\'s "%s"',
                      tostring(apLocationName(id) or id)))
end

-- Make one path show what the hints standing on it say, or nothing.
--
-- Recomputed from `standing` rather than tracked incrementally, because the
-- payload is a whole list each time and because a path can carry more than one
-- id -- reconcile.lua indexes path to a list for that reason, even though no two
-- ids share one in the mapping as it stands. The only reliable answer to "is
-- this pin still hinted?" is to ask every hint again.
local function reconcile(path)
  local best = nil
  for _, row in pairs(standing) do
    if row.path == path then
      local rank = STATUS_RANK[row.status] or 1
      if not best or rank > best.rank then
        best = { rank = rank, status = row.status }
      end
    end
  end
  if best then
    claimed[path] = true
    if type(claimHighlight) == "function" then
      claimHighlight("hint", path, levelFor(best.status))
    end
  elseif claimed[path] then
    claimed[path] = nil
    if type(releaseHighlight) == "function" then
      releaseHighlight("hint", path)
    end
  end
end

-- A check the board saw before the server got round to saying so.
--
-- register_location_checks rechecks hints and rebroadcasts, so the payload would
-- put this out on its own a moment later. This is worth having anyway: it costs
-- nothing, it removes a visible lag on a slow room, and it also covers a check
-- that arrived over the emulator bridge, where no payload is coming at all.
function hintChecked(id)
  local row = standing[id]
  if not row then
    return false
  end
  standing[id] = nil
  announced[id] = nil
  reconcile(row.path)
  return true
end

-- The whole payload, every time. Returns the number of live hints on this
-- board and the number of rows that were about somebody else's.
--
-- The server sends the complete list rather than a delta, so what is *not* in
-- it is as meaningful as what is: a hint removed, re-prioritised or found
-- leaves, and the pass below is what notices.
function onHints(value)
  -- A Get on a key the room has never written answers null, and a slot with no
  -- hints yet answers an empty list. Both are "nothing stands", not an error --
  -- but an empty list still has to run the pass, so absent and empty differ
  -- only in that the first cannot be trusted to be complete.
  if type(value) ~= "table" then
    return 0, 0
  end
  local slot = Archipelago.PlayerNumber
  local live, elsewhere = {}, 0
  for _, hint in ipairs(value) do
    if type(hint) ~= "table" then
      goto continue
    end
    -- A hint is filed under both the receiving and the finding player
    -- (MultiServer.py:816-830), so roughly half of what arrives is about
    -- another board and has no pin here to light.
    if hint.finding_player ~= slot then
      elsewhere = elsewhere + 1
      goto continue
    end
    do
      -- `found` alone was the signal before HintStatus existed; both are read
      -- so an older server still works.
      local status = type(hint.status) == "number" and hint.status or 0
      if hint.found == true or status == HINT_FOUND then
        goto continue
      end
      local id = hint.location
      if type(id) ~= "number" then
        goto continue
      end
      local v = LOCATION_MAPPING[id]
      if not v or not v[1] then
        warnUnmappedHint(id)
        goto continue
      end
      live[id] = { path = v[1], status = status }
    end
    ::continue::
  end

  -- Every path either list touches has to be reconciled: the ones that are
  -- hinted now, and the ones that were and are not, which is how a hint being
  -- found or withdrawn puts its pin out.
  local touched = {}
  for _, row in pairs(standing) do touched[row.path] = true end
  for _, row in pairs(live) do touched[row.path] = true end
  standing = live

  local count = 0
  for id, row in pairs(live) do
    count = count + 1
    if not announced[id] then
      announced[id] = true
      local said = describeLocation(id, row.path)
      if said then
        print("hint: " .. said)
      end
    end
  end
  for id in pairs(announced) do
    if not live[id] then
      announced[id] = nil
    end
  end
  for path in pairs(touched) do
    reconcile(path)
  end
  return count, elsewhere
end

-- A different slot is a different set of hints, and a reconnect must not carry
-- the last one's over.
function resetHints()
  announced = {}
  unmapped = {}
  standing = {}
  key = nil
  if type(releaseHighlightsFor) == "function" then
    releaseHighlightsFor("hint")
  end
  claimed = {}
end

-- Every pin a hint could ever light, registered at load rather than when the
-- first hint arrives.
--
-- That is what puts these paths inside the registry's load sweep, and the sweep
-- is the only thing that can put out gold restored from an autosave written
-- while a hint stood. A tracker opened on a bridge-only session, or on none,
-- never receives a payload -- so nothing here would otherwise ever run, and the
-- pin would stay lit for good.
if type(registerHighlightScope) == "function" and LOCATION_MAPPING then
  local paths, seen = {}, {}
  for _, v in pairs(LOCATION_MAPPING) do
    if v[1] and not seen[v[1]] then
      seen[v[1]] = true
      paths[#paths + 1] = v[1]
    end
  end
  registerHighlightScope("hint", paths)
end
