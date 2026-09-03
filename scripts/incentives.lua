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
    for _, flag in ipairs(slot.flags) do
      if not seen[flag] then
        seen[flag] = true
        out[#out + 1] = flag
      end
    end
  end
  return out
end

-- Does this seed's flag set speak for the slot?
--
-- `flags` is an AND, because two of FFR's incentive conditions are computed
-- conjunctions rather than stored flags: IncentivizeCaravan is
-- (NPCItems && IncentivizeFreeNPCs) and each fetch incentive is
-- (NPCFetchItems && IncentivizeFetchNPCs) -- FlagsCompute.cs:217, :220-226.
-- Ringing on either conjunct alone gilded seven slots FFR never incentivized.
local function slotIsIncentivized(slot)
  for _, flag in ipairs(slot.flags) do
    if Tracker:ProviderCountForCode(flag) <= 0 then
      return false
    end
  end
  return true
end

local highlightWarned = false
local ringsWarned = false

-- Does the player want the rings drawn at all?
--
-- This one toggle is Lua, and the three pin toggles are not: those are
-- `restrict_visibility_rules` on the pins themselves, stamped by
-- tools/pin_visibility.py. The difference is not a style choice: a Highlight is
-- not a pin state. PopTracker draws it as a glow around
-- a marker it is already drawing, so a visibility rule could only take the
-- whole pin away, and taking away the slots a key item can be in is the
-- opposite of what anyone means by turning the rings off.
--
-- An undefined code counts zero exactly like a toggle switched off, so a typo
-- would put every ring out for good with nothing said. Say it once and behave
-- as the pack did before, the way incentiveSlot() does in scripts/logic.lua.
local function wantRings()
  if Tracker:ProviderCountForCode("show_gold_rings") > 0 then
    return true
  end
  if not Tracker:FindObjectForCode("show_gold_rings") then
    if not ringsWarned then
      ringsWarned = true
      print("incentives: no toggle named show_gold_rings -- ringing anyway")
    end
    return true
  end
  return false
end

-- Guards against running inside itself. This is not hypothetical tidiness: the
-- watches below fire from PopTracker's own change dispatch, and a refresh that
-- ran again from inside one would recurse until the stack gave out.
local refreshing = false

-- Walk the table and set every ring. Cheap enough to do wholesale: it is
-- ~54 lookups, and it only runs when a flag actually moves.
--
-- Deliberately does NOT wrap the writes in Tracker.BulkUpdate, which is what
-- the first version of this did and what crashed PopTracker on open. Two
-- reasons, either of them enough:
--
--   * `Tracker.BulkUpdate = false` does not just clear a flag, it flushes the
--     queued changes and emits them (tracker.cpp:750-765). Those emits are what
--     run the watches below -- so this function would call itself, from inside
--     its own last line, with the queue not yet cleared. That is an unbounded
--     recursion and a segfault, not a slow path.
--   * the batch is not ours to close. reconcile.lua opens one around its own
--     writes; if an incentive flag moves inside it, ending the batch here would
--     flush someone else's half-finished board.
--
-- What the batch would have saved is 54 onLocationSectionChanged emits, which
-- are display-level. A Highlight write does not touch the provider cache or
-- mark accessibility stale, so there is no re-resolve to avoid.
function refreshIncentiveHighlights()
  if not INCENTIVE_SLOTS or refreshing then
    return 0
  end
  refreshing = true
  local marked = 0
  local ok, err = pcall(function()
    local rings = wantRings()
    for _, slot in ipairs(INCENTIVE_SLOTS) do
      -- Only one of the two incentive trees is loaded, so roughly a third of
      -- these are expected to be nil. tests/test_incentives.lua is what
      -- catches a path that resolves in neither.
      local section = Tracker:FindObjectForCode(slot.path)
      if section then
        if rings and slotIsIncentivized(slot) then
          section.Highlight = Highlight.Priority
          marked = marked + 1
        else
          -- Reached with the toggle off as well as for a slot this seed
          -- passed over, which is what puts the rings out on a click rather
          -- than leaving the last set of them painted.
          section.Highlight = Highlight.None
        end
      end
    end
  end)
  -- Cleared on the failure path too, or one error would stop every later
  -- refresh silently.
  refreshing = false
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
  -- And on the toggle itself, or turning it off would only take effect the
  -- next time some incentive flag happened to move.
  ScriptHost:AddWatchForCode("incentive:show_gold_rings", "show_gold_rings",
                             refreshIncentiveHighlights)
end

refreshIncentiveHighlights()
