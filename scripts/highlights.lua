-- Who lit a pin, and what colour it should be.
--
-- Highlight is one of the two things a script may write to a section
-- (locationsection.cpp:262-294), and three separate features now want to write
-- it: a hint from Archipelago, the pin a click navigated to, and the gold ring
-- on an incentivized slot. Before this file they each wrote it directly, and
-- entrance_items.lua said in a comment that it was the only Lua in the pack
-- that touched Highlight at all. That was already untrue when it was written --
-- incentives.lua wrote it too -- and the sets were disjoint only by luck.
--
-- They are not disjoint any more. 25 section paths are in both INCENTIVE_SLOTS
-- and LOCATION_MAPPING -- Coneria Castle's King, Gaia's Fairy, Nerrick, the
-- Marsh Cave incentive and 21 others -- and refreshIncentiveHighlights writes
-- Highlight.None over every slot it does not ring. So a hint on any of those
-- would be put out by the next incentive refresh, which runs on every connect
-- and on every incentive toggle.
--
-- The fix is that nobody writes Highlight. Owners claim a path and this file
-- resolves the claims, so an owner can only ever turn its own light off.

-- Resolution order, strongest first. Anything not in this list loses to
-- everything in it.
--
-- A hint outranks a ring because a hint is a statement about this location made
-- this session, while a ring is an ambient property of the seed -- and because
-- AP's own status has colours of its own to say (see hints.lua), which a ring
-- painting over would contradict. Entrance never actually contends: its paths
-- are all "@Entrances/..." and disjoint from both. It is listed anyway so the
-- order is one readable line rather than something a reader has to derive.
HIGHLIGHT_OWNERS = { "hint", "entrance", "incentive" }

-- claims[path][owner] = level
local claims = {}
-- Every path any owner may ever light, which is what the sweep walks.
local scope = {}
local warned = false

-- What an owner may light. Called once per owner as its table loads.
--
-- Registered at load rather than at the moment of a claim, deliberately: the
-- sweep below has to be able to put out a path nobody has claimed *yet*, which
-- is exactly the autosave case. A scope that filled in as claims arrived would
-- be empty on the one pass that needs it.
function registerHighlightScope(owner, paths)
  local added = 0
  for _, path in ipairs(paths or {}) do
    if not scope[path] then
      scope[path] = true
      added = added + 1
    end
  end
  return added
end

-- The level this path resolves to, or Highlight.None where nobody claims it.
local function resolve(path)
  local held = claims[path]
  if held then
    for _, owner in ipairs(HIGHLIGHT_OWNERS) do
      if held[owner] ~= nil then
        return held[owner]
      end
    end
  end
  return Highlight and Highlight.None
end

-- Resolve one path and write it, if the write would change anything.
--
-- Compared against the section's own current value rather than a cache of what
-- we last wrote, because the value can change behind us: locationsection.cpp
-- writes Highlight into the autosave at :180-181 and restores it at :194-196,
-- so a board can come back lit with nothing in this file knowing. Reading is
-- what lets the sweep see that.
--
-- `~= nil` as well as `~= None` on the read, because a host that does not
-- answer the read will not accept the write either: Lua_NewIndex returns false
-- and PopTracker raises on the assignment. Reading nil is that host saying so.
function applyHighlight(path)
  if not Highlight then
    return false
  end
  local want = resolve(path)
  local ok, changed = pcall(function()
    local sec = Tracker:FindObjectForCode(path)
    if not sec then
      return false
    end
    local lit = sec.Highlight
    if lit == nil or lit == want then
      return false
    end
    sec.Highlight = want
    return true
  end)
  if not ok then
    -- Warn once and carry on. One host that rejects the assignment must not
    -- stop every later claim, and the board is still right -- it just has no
    -- colour on it. This is incentives.lua's own guard, moved to the one place
    -- that now needs it so all three owners degrade the same way.
    if not warned then
      warned = true
      print("highlights: cannot colour a pin (" .. tostring(changed)
            .. ") -- the board is right, it just has no highlight on it")
    end
    return false
  end
  return changed
end

-- Light `path` on behalf of `owner`. Level defaults to gold.
function claimHighlight(owner, path, level)
  if not path then
    return false
  end
  local held = claims[path]
  if not held then
    held = {}
    claims[path] = held
  end
  held[owner] = level or (Highlight and Highlight.Priority)
  return applyHighlight(path)
end

-- Put out this owner's claim on one path. Another owner's claim on the same
-- path survives, and is what the path resolves to next.
--
-- The re-apply happens even where this owner held nothing, and that is not a
-- wasted call: it is what "make this path show what its claims say" means. The
-- pin can be lit with no claim behind it -- a value restored from the autosave,
-- or a board that opened on something other than None -- and a release that
-- returned early on `we did not light this` would leave that standing for ever.
function releaseHighlight(owner, path)
  if not path then
    return false
  end
  local held = claims[path]
  if held and held[owner] ~= nil then
    held[owner] = nil
    if next(held) == nil then
      claims[path] = nil
    end
  end
  return applyHighlight(path)
end

-- Everything this owner holds, for a reset.
function releaseHighlightsFor(owner)
  local released = 0
  for path, held in pairs(claims) do
    if held[owner] ~= nil then
      held[owner] = nil
      if next(held) == nil then
        claims[path] = nil
      end
      applyHighlight(path)
      released = released + 1
    end
  end
  return released
end

-- Who this path is lit for, or nil. For the tests, and for reading a log.
function highlightOwnerOf(path)
  local held = claims[path]
  if not held then
    return nil
  end
  for _, owner in ipairs(HIGHLIGHT_OWNERS) do
    if held[owner] ~= nil then
      return owner
    end
  end
  return nil
end

-- Every registered path back to what its claims say.
--
-- This is the general form of the sweep entrance_items.lua used to do over its
-- own pins. Highlight is saved state and no deadline or claim is: a quit inside
-- a five-second navigation glow, or while a hint stood, reopens with the pin
-- gold and nothing left that knows to put it out.
--
-- The old sweep was safe only because it walked a set nothing else touched.
-- Extending that shape over LOCATION_MAPPING would have blanked every incentive
-- ring on load. Re-asserting from claims cannot: a path an owner has already
-- claimed resolves to that claim, and only a path nobody holds goes dark. That
-- also makes it order-independent -- whether the incentive watches fire before
-- or after this runs, both write the same value.
function sweepHighlights()
  local swept = 0
  for path in pairs(scope) do
    if applyHighlight(path) then
      swept = swept + 1
    end
  end
  return swept
end

-- On the first frame rather than as this file loads, and that is the whole
-- reason it is a frame handler. Tracker::loadState restores lua items before
-- sections (tracker.cpp:1422-1455) and the restore itself runs synchronously a
-- few lines after init.lua returns (poptracker.cpp:1436-1449), so anything
-- cleared from a LoadFunc, or from the bottom of a script, is put straight back
-- by the section pass. The first frame is the earliest moment at which the
-- restored board is the board -- and it is also after every other script has
-- registered its scope, which this one needs.
local SWEEP_HANDLER = "highlight sweep"

local function sweepOnce()
  ScriptHost:RemoveOnFrameHandler(SWEEP_HANDLER)
  sweepHighlights()
end

if type(ScriptHost.AddOnFrameHandler) == "function" then
  ScriptHost:AddOnFrameHandler(SWEEP_HANDLER, sweepOnce)
end
