------------------------------------------------------------------
-- Ring the slots this seed put an incentive in.
--
-- Since the incentive map stopped hiding a skipped slot and started drawing it
-- blue, both overworld tabs show every slot there is. That answers "is this
-- still a check" -- it always was -- but it loses the thing the incentive map
-- was for, which is "where can a key item actually be". A gold ring says it,
-- on both tabs at once, and it says it without spending the pin's own colour:
-- green still means reachable and red still means not.
--
-- PopTracker draws Highlight as a glow around the pin, from a fixed palette --
-- Priority is gold (mapwidget.cpp:53). The pack cannot choose the colour, only
-- the state. Needs 0.32.0, which manifest.json now asks for.
--
-- Two things fall out of the way PopTracker aggregates this, both wanted:
--
--   * the glow is per pin, not per section. Gilding King gilds the whole
--     Coneria Castle pin, chests included -- which reads as "there is an
--     incentive in here", the question the overworld tab is asked.
--   * a cleared section is skipped (trackerview.cpp:1241-1250), so the ring
--     goes out by itself once the slot is collected, with nothing to reset.
--
-- The slot list is generated -- see scripts/incentive_slots.lua and the tool
-- that writes it. It is read out of the location files rather than typed here,
-- so it cannot drift from the sections it names.
------------------------------------------------------------------

-- Every flag the table mentions, once. Derived rather than listed, for the
-- same reason the table is generated.
local function incentiveFlags()
  local seen, out = {}, {}
  for _, slot in ipairs(INCENTIVE_SLOTS or {}) do
    if not seen[slot.flag] then
      seen[slot.flag] = true
      out[#out + 1] = slot.flag
    end
  end
  return out
end

local highlightWarned = false

-- Walk the table and set every ring. Cheap enough to do wholesale: it is
-- ~54 lookups, and it only runs when a flag actually moves.
function refreshIncentiveHighlights()
  if not INCENTIVE_SLOTS then
    return 0
  end
  -- Every Highlight write raises the same onChange a chest clear does, which
  -- drops the provider cache and marks accessibility stale (tracker.cpp:463).
  -- Without the batch that is a full re-resolve of the board per slot.
  Tracker.BulkUpdate = true
  local marked = 0
  local ok, err = pcall(function()
    for _, slot in ipairs(INCENTIVE_SLOTS) do
      -- Only one of the two incentive trees is loaded, so roughly a third of
      -- these are expected to be nil. tests/test_incentives.lua is what
      -- catches a path that resolves in neither.
      local section = Tracker:FindObjectForCode(slot.path)
      if section then
        if Tracker:ProviderCountForCode(slot.flag) > 0 then
          section.Highlight = Highlight.Priority
          marked = marked + 1
        else
          section.Highlight = Highlight.None
        end
      end
    end
  end)
  -- Restored on the failure path too: PopTracker leaves the board frozen if
  -- this is left true.
  Tracker.BulkUpdate = false
  if not ok then
    if not highlightWarned then
      highlightWarned = true
      print("incentives: cannot ring the incentivized slots (" .. tostring(err)
            .. ") -- the board is right, it just has no gold on it")
    end
    return 0
  end
  if AUTOTRACKER_ENABLE_DEBUG_LOGGING then
    print(string.format("incentives: %d slots ringed", marked))
  end
  return marked
end

-- One watch per flag, which covers every way a flag can move: the cartridge's
-- own settings arriving over the bridge, a resync, a new cartridge, a hand
-- click in the incentives grid -- and PopTracker's own state restore a moment
-- after the pack loads, which no explicit call site would catch.
if ScriptHost.AddWatchForCode then
  for _, flag in ipairs(incentiveFlags()) do
    ScriptHost:AddWatchForCode("incentive:" .. flag, flag,
                               refreshIncentiveHighlights)
  end
end

refreshIncentiveHighlights()
