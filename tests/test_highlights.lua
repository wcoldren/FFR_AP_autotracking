-- Who lit a pin, and what happens when two features want the same one.
--
-- The registry exists because 25 section paths are in both INCENTIVE_SLOTS and
-- LOCATION_MAPPING, so a hint and a gold ring can land on the same pin. The
-- rows below are that case in miniature: the contention, and the load sweep
-- that used to live in entrance_items.lua and could not be pointed at those 25
-- without blanking every ring on the board.
local PACK = arg[1]
local popapi = dofile(PACK .. "/tests/pop_api.lua")

-- The host's own values (locationsection.h:12-18). Sections start on
-- Unspecified rather than None so a row can tell "written to None" apart from
-- "never touched", which is the same trick tests/test_incentives.lua uses.
Highlight = { Avoid = -1, None = 0, NoPriority = 1, Unspecified = 2, Priority = 3 }

local RING = "@Coneria Castle King/King"       -- in both scopes: the contended one
local CHEST = "@Marsh Cave Bottom Floor 2,2 2/Chest"
local PIN = "@Entrances/Entrance: Coneria/Coneria"

local writes = {}
local SECTIONS = {}
local function section(path)
  local store = { Highlight = Highlight.Unspecified }
  SECTIONS[path] = setmetatable({}, {
    __index = store,
    __newindex = function(_, k, v)
      if k == "Highlight" then
        writes[path] = (writes[path] or 0) + 1
      end
      store[k] = v
    end,
  })
end
section(RING)
section(CHEST)
section(PIN)

Tracker = popapi.strict("Tracker", {
  FindObjectForCode = function(_, code) return SECTIONS[code] end,
})
local frameHandlers = {}
ScriptHost = popapi.strict("ScriptHost", {
  AddOnFrameHandler = function(_, name, fn) frameHandlers[name] = fn end,
  RemoveOnFrameHandler = function(_, name) frameHandlers[name] = nil end,
})

local fail = 0
local function check(label, got, want)
  local ok = got == want
  if not ok then fail = fail + 1 end
  print(string.format("%s %-54s %s", ok and "ok  " or "FAIL", label, tostring(got)))
  if not ok then print(string.format("     wanted %s", tostring(want))) end
end

dofile(PACK .. "/scripts/highlights.lua")

-- 1. One owner.
registerHighlightScope("incentive", { RING })
registerHighlightScope("hint", { RING, CHEST })
registerHighlightScope("entrance", { PIN })

claimHighlight("incentive", RING)
check("a claim lights the pin", SECTIONS[RING].Highlight, Highlight.Priority)
check("and says who it is lit for", highlightOwnerOf(RING), "incentive")

releaseHighlight("incentive", RING)
check("releasing the only claim puts it out", SECTIONS[RING].Highlight, Highlight.None)
check("and nobody owns it now", highlightOwnerOf(RING), nil)

-- 2. Two owners on one path -- the 25-path case.
claimHighlight("incentive", RING)
claimHighlight("hint", RING, Highlight.Avoid)
check("a hint outranks a ring on the same pin",
  SECTIONS[RING].Highlight, Highlight.Avoid)
check("and is the owner of record", highlightOwnerOf(RING), "hint")

-- This is the regression the whole file exists for: before the registry,
-- refreshIncentiveHighlights asserted Highlight.None over every slot it did not
-- ring, which put out any hint sharing the path.
releaseHighlight("incentive", RING)
check("the ring going out leaves the hint standing",
  SECTIONS[RING].Highlight, Highlight.Avoid)
check("and the hint still owns it", highlightOwnerOf(RING), "hint")

claimHighlight("incentive", RING)
releaseHighlight("hint", RING)
check("and the hint going out reveals the ring underneath",
  SECTIONS[RING].Highlight, Highlight.Priority)

-- 3. Only the claim's own owner can drop it.
claimHighlight("hint", CHEST)
releaseHighlight("entrance", CHEST)
check("releasing a claim you do not hold changes nothing",
  SECTIONS[CHEST].Highlight, Highlight.Priority)

check("releaseHighlightsFor drops every path an owner holds",
  releaseHighlightsFor("hint"), 1)
check("  and the pin goes dark", SECTIONS[CHEST].Highlight, Highlight.None)

-- 4. No redundant writes. A 256-path sweep that wrote every path would emit an
-- onLocationSectionChanged for each; the registry writes only on a change.
writes[PIN] = 0
claimHighlight("entrance", PIN)
check("the first claim writes once", writes[PIN], 1)
claimHighlight("entrance", PIN)
check("re-claiming the same level writes nothing more", writes[PIN], 1)
releaseHighlight("entrance", PIN)
check("and releasing writes once", writes[PIN], 2)

-- 5. The load sweep.
check("the sweep is armed at load", frameHandlers["highlight sweep"] ~= nil, true)

-- A board restored from an autosave: gold on two pins, a claim behind only one
-- of them. The old entrance-only sweep put out everything it walked, which is
-- why it could never be pointed at the incentive rings.
releaseHighlightsFor("incentive")
releaseHighlightsFor("hint")
releaseHighlightsFor("entrance")
SECTIONS[RING].Highlight = Highlight.Priority
SECTIONS[CHEST].Highlight = Highlight.Priority
claimHighlight("incentive", RING)
frameHandlers["highlight sweep"](0.016)
check("the sweep puts out a pin nobody claims",
  SECTIONS[CHEST].Highlight, Highlight.None)
check("and leaves a claimed one lit", SECTIONS[RING].Highlight, Highlight.Priority)
check("then takes itself off, being a load-time job",
  frameHandlers["highlight sweep"], nil)

-- 6. A host with no Highlight must not take the board down.
local savedHighlight = Highlight
Highlight = nil
local ok = pcall(function()
  claimHighlight("hint", CHEST)
  releaseHighlight("hint", CHEST)
  sweepHighlights()
end)
check("no Highlight support is a no-op, not an error", ok, true)
Highlight = savedHighlight

print("")
if fail > 0 then
  print(string.format("%d FAILED", fail))
  os.exit(1)
end
print("ALL PASS")
