-- Rules that access_rules cannot say on their own.
--
-- PopTracker's access_rules are a list of alternatives, each a set of codes
-- that all have to be present. There is no way to write "and not this flag",
-- and no way to count. Both come up, so they live here and are called from a
-- rule as $name.
--
-- These return 0 or 1 rather than false or true: that is what PopTracker reads
-- as an accessibility level, and 0 is truthy in Lua, so a function that fell
-- back to returning a boolean would be read as accessible either way.

-- Whether Sarda's Cave sits in the open or in trees.
--
-- FFR's "Sarda's Forest" (MapSardasForest) replaces the clearing outside the
-- cave with forest, and the airship cannot land on forest. With it off the
-- airship reaches Sarda by itself; with it on the only ways in are through the
-- Titan's tunnel, which is what the Ruby buys. FFR's own logic for a
-- forested seed says so: Sarda needs (Ruby AND Canal AND Ship) OR (Ruby AND
-- Canoe AND Floater), where an unforested one drops the Ruby from the second.
--
-- The flag is read off the cartridge when the emulator bridge is connected and
-- is a click in the flags grid otherwise; either way it is the item that is
-- asked, so both paths behave the same.
function noSardasForest()
  local flag = Tracker:FindObjectForCode("sardasForest")
  if flag and flag.Active then
    return 0
  end
  return 1
end

-- Whether the Ship is worth anything on this seed.
--
-- FFR's "Ship Drydock" (ShipDrydock) moves every ship spawn to the Gaia
-- drydock -- MapExchange/ShipLocations.cs:52-60 rewrites all of them, and
-- OverworldMapEdits.cs:535-549 lays the dock tiles there. So the Ship launches
-- on the far eastern coast, which is behind the Canoe or the airship already,
-- and it opens nothing they did not. FFR's own logic agrees: on a drydock seed
-- 51 of the rules it exports lose their Ship alternative and not one gains
-- anything (docs/ORACLE.md, "The second corpus: 4.9.7").
--
-- Every alternative in the trees that names `ship` carries this call, so on a
-- drydock seed they all fall out and the Canoe and airship routes are what is
-- left. That is deliberately the strict direction: if some flag combination did
-- leave the drydocked Ship useful somewhere, the pack shows a red check that is
-- reachable rather than a green one that is not.
function noShipDrydock()
  local flag = Tracker:FindObjectForCode("shipDrydock")
  if flag and flag.Active then
    return 0
  end
  return 1
end

-- ShuffleObjectiveNPCs permutes Bahamut, Dr Unne and the Elf Doctor across
-- BahamutCave2, Melmond and Elfland Castle (NPCs.cs:277). The flag says the
-- shuffle happened; it does not say where anyone went, because the permutation
-- is rolled at generation and reaches neither the flag string nor the spoiler.
--
-- So with it on, "can I reach Dr Unne" has to mean "can I reach anywhere Dr
-- Unne might be", which is all three homes. Bahamut's Cave dominates the other
-- two under every one of its alternatives -- the airship reaches Melmond and
-- Elf Castle, and cardiaDock with the Ship and the Canal carries the Ship that
-- opens both -- so the conjunction of the three collapses to Bahamut's Cave's
-- own requirement, and that is what the two moved cells ask for.
--
-- This is the strict direction on purpose, the same call the Cardia gateway
-- roll got: a check held red that turns out reachable, rather than a green one
-- that is not. It also ignores the ChestsKeyItems conjunct FFR ANDs in at
-- NPCs.cs:135 -- with that flag off the shuffle does not run and this is
-- needlessly strict, which is the side to be wrong on until there is a code
-- for it.
function noObjectiveShuffle()
  local flag = Tracker:FindObjectForCode("objectiveNPCs")
  if flag and flag.Active then
    return 0
  end
  return 1
end

-- The two rolls, and the state where nothing has said.
--
-- scripts/autotracking/rolls_mapping.lua sets a toggle per half when the
-- bridge has read that permutation off the cartridge, and these are what the
-- strict alternatives carry so they fall out the moment it has. One guard per
-- half is enough because a half is all or nothing: the decoder refuses a
-- permutation it cannot account for entirely, so the pack either knows where
-- all three gateways go or knows nothing about any of them.
--
-- Unknown is the ordinary case, not an error. An Archipelago-only session has
-- no cartridge to read, a session with no bridge attached has nothing
-- publishing it, and every board is unknown until the emulator is up -- and
-- all three get exactly the rules the pack shipped before it could ask.
function gatewayRollUnknown()
  local item = Tracker:FindObjectForCode("gatewayRoll")
  if item and item.Active then
    return 0
  end
  return 1
end

-- Shard hunt: the goal is a count of shards rather than four lit orbs.
--
-- The variants are named in manifest.json, and the UID carries a leading digit
-- that fixes the order they appear in PopTracker's variant list. Matching the
-- bare string "shardHunt" matched none of them, so every shard-hunt seed was
-- quietly gated on orbs instead and hasEnoughShards never ran.
local function isShardHunt()
  return Tracker.ActiveVariantUID:find("shardHunt") ~= nil
end

-- No-Overworld: the mode swaps the overworld for an ocean stub and wires the
-- 61 maps together with a fixed table of teleporters, so none of the standard
-- geography -- ship, canal, the docks, the two mountain passes -- describes it.
-- Four of the eight variants are No-Overworld ones, and `shardHuntNOverworld`
-- is both, so this and isShardHunt() have to be able to hold at once.
--
-- :find for the same reason as above: every UID carries a leading digit that
-- fixes its place in PopTracker's variant list, so == matches none of them.
--
-- The variant, not the cartridge's GameMode. The variant is set before the
-- first rule is evaluated and never changes; ffrFlag("GameMode") is nil until
-- the bridge publishes a flag string, is nil forever on an Archipelago-only
-- session, and has no item behind it -- and PopTracker only re-evaluates rules
-- when an item changes, so a flag-driven branch would have nothing to fire it.
local function isNoOverworld()
  return Tracker.ActiveVariantUID:find("NOverworld") ~= nil
end

-- The two mode guards the location tree calls, so that one set of access_rules
-- can serve both modes. Every alternative carries one of them; PopTracker ORs
-- alternatives, so the other mode's alternatives fail closed and what is left
-- is exactly the rule for the mode in play.
--
-- The mode difference lives here rather than in a second set of rules. There
-- are still two of each location file, because the No-Overworld art crops
-- differently and a pin coordinate is a fact about the art -- but the two
-- carry the same access_rules, and tests/test_maps.lua checks 6 and 7 compare
-- them. That pairing is not optional: the guards below first landed on
-- locations/incentives.json alone, and the No-Overworld map variants, which
-- load locations/NOverworld/incentives.json, kept the old overworld geography
-- for as long as check 7 exempted that pair. Two files that have to agree and
-- are never compared is also how a missing location file survived here for
-- weeks.
function noOverworld()
  if isNoOverworld() then
    return 1
  end
  return 0
end

function standardWorld()
  if isNoOverworld() then
    return 0
  end
  return 1
end

-- The canoe and the floater, under either feed's name for them.
--
-- On a No-Overworld seed the two feeds disagree about what to call these. The
-- Archipelago exporter renames Canoe to "Mark" and Floater to "Sigil"
-- (Archipelago.cs:287-289,339-340), so an AP-fed session sets mark and sigil;
-- the Mesen bridge reads the game's own bytes and sets canoe and floater. Both
-- are the same item, so a rule naming only one of them is right for one feed
-- and wrong for the other.
--
-- ProviderCountForCode rather than FindObjectForCode().Active: it is the walk
-- that knows which codes a progressive's current stage hands out, and floater
-- is a progressive whose second stage is the airship.
local function provided(code)
  return Tracker:ProviderCountForCode(code) > 0
end

function hasCanoe()
  if provided("canoe") or provided("mark") then
    return 1
  end
  return 0
end

function hasFloater()
  if provided("floater") or provided("sigil") then
    return 1
  end
  return 0
end

function hasEnoughShards()
  local shards = Tracker:FindObjectForCode("shards")
  local required = Tracker:FindObjectForCode("shardsRequired")
  -- The Shards Required item starts counting at sixteen; its stage is the
  -- number above that.
  if shards.CurrentStage >= required.CurrentStage + 16 then
    return 1
  end
  return 0
end

local ORBS = { "earthorb", "fireorb", "waterorb", "airorb" }

local function orbsLit()
  local n = 0
  for _, code in ipairs(ORBS) do
    local orb = Tracker:FindObjectForCode(code)
    if orb and orb.CurrentStage > 0 then
      n = n + 1
    end
  end
  return n
end

-- How many orbs the black orb wants. FFR can ask for fewer than four, either
-- "any N of them" or N particular ones.
--
-- Only the count is in the flag string. Which orbs, in the specific mode, is
-- rolled from the seed and written into the game rather than into the flags,
-- so there is nothing here to read -- and "any three" would then be a rule
-- that turns the goal green while the wrong three are lit. All four is the
-- answer that is always sufficient, so that is what the specific mode gets;
-- the game tells you which three it wants when you get there.
local function orbsRequired()
  local count = ffrFlag and ffrFlag("OrbsRequiredCount", 4) or 4
  local mode = ffrFlag and ffrFlag("OrbsRequiredMode", 0) or 0
  if type(count) ~= "number" or count < 1 or count > 4 then
    return 4
  end
  if mode ~= 0 then
    return 4
  end
  return count
end

function canBreakOrb()
  if isShardHunt() then
    return hasEnoughShards()
  end
  if orbsLit() >= orbsRequired() then
    return 1
  end
  return 0
end

-- A slot this seed did not put in the incentive pool.
--
-- These are still checks. The NPC still hands you something, the chest is
-- still there and still holds an item -- so hiding them, which is what the
-- visibility_rules on the incentive map used to do, took a real check off the
-- board. Inspect draws them blue instead: visible, and visibly not somewhere a
-- key item can be.
--
-- Used as `^$incentiveSlot|<flag code>`, which needs PopTracker 0.25.6. The
-- argument is the flag item's own code, so the pairing lives in the location
-- file next to the section it describes and there is no second copy here to
-- drift out of step.
--
-- Note what this deliberately does not do. PopTracker ANDs the term into each
-- alternative and stops at the first failure (tracker.cpp:1126-1136), so a
-- slot that is both unincentivized and out of logic comes out None, not
-- Inspect: it stays red like any other unreachable check, and only goes blue
-- once it is actually reachable. That is the right way round -- "you cannot
-- get there yet" outranks "there is probably nothing good here".
--
-- ProviderCountForCode rather than FindObjectForCode().Active: the flags this
-- is asked about are not all toggles -- a progressive's Active says only that
-- it is off stage 0, and only the provider walk knows which codes its current
-- stage hands out. BahamutHoard was such a code until the cardia split; the
-- reason survives it, because nothing stops the next flag being a stage.
local INCENTIVE_WARNED = {}

function incentiveSlot(code)
  if Tracker:ProviderCountForCode(code) > 0 then
    return AccessibilityLevel.Normal
  end
  -- An unknown code counts zero exactly like an unset flag, so a typo would
  -- quietly paint a whole tab blue. Say it once and behave as the pack did
  -- before instead.
  if not Tracker:FindObjectForCode(code) then
    if not INCENTIVE_WARNED[code] then
      INCENTIVE_WARNED[code] = true
      print("logic: no incentive flag named " .. tostring(code)
            .. " -- treating the slot as incentivized")
    end
    return AccessibilityLevel.Normal
  end
  return AccessibilityLevel.Inspect
end

-- Whether a pin of a given kind is drawn.
--
-- Called from a pin's restrict_visibility_rules as `$showPin|<kind>[|<flag>...]`.
-- No `^`: a visibility rule reads the return as a count, so 1 shows and 0 hides.
-- restrict_visibility_rules hides only that one marker (location.cpp:265-279) --
-- the section stays in the tree, in the counts, and clearable from the location
-- list. That is deliberate: hiding a check was the bug the incentive map's old
-- visibility_rules had, and an off switch for a pin must not re-introduce it.
--
-- Every pin of a kind shares one rule string and _providerCountCache keys on
-- the whole string, so the 251 chest pins cost one call per cache generation
-- rather than 251.
--
-- One entry per section, and the outer rule array is OR'd (location.cpp:266),
-- so a pin draws if any section under it would draw and showPin folds nothing
-- itself. A section with no incentive flag always draws, which would make its
-- entry always true -- so a node holding one gets no rule at all rather than an
-- entry saying so. That is what keeps the five orb pins from ever being hidden.
--
-- Deliberately not applied to the overworld pins: those are aggregates, no one
-- kind describes them, and a player must not be able to empty the overworld.
--
-- The rules are written by tools/pin_visibility.py rather than by hand, and
-- tools/regen_maps.py stamps a regenerated tree through the same function, so
-- the committed tree and a regen output cannot drift apart on this.
local PIN_TOGGLE = {
  chest    = "show_chests",
  npc      = "show_npcs",
  slot     = "show_skipped",
  entrance = "entrance_pins",
}

-- Stages of the Entrance Pins control, in items/flags.json order. It is a
-- three-stage progressive rather than a switch because the useful default is
-- not the same on every cartridge, so "the seed decides" has to be a position
-- the player can leave it in as well as one they can overrule.
local ENTRANCE_AUTO, ENTRANCE_OFF, ENTRANCE_ON = 0, 1, 2

local PIN_WARNED = {}

local function warnOnce(key, msg)
  if not PIN_WARNED[key] then
    PIN_WARNED[key] = true
    print("logic: " .. msg)
  end
end

-- A code nothing defines counts zero exactly like a toggle switched off, so a
-- typo -- or a rule stamped before the item it names exists -- would empty a
-- whole tab and say nothing. Fail open: draw the pin, which is what the pack
-- did before any of these toggles existed, and say so once.
local function toggleOn(code)
  if Tracker:ProviderCountForCode(code) > 0 then
    return true
  end
  if not Tracker:FindObjectForCode(code) then
    warnOnce(code, "no pin toggle named " .. tostring(code) .. " -- drawing the pin")
    return true
  end
  return false
end

function showPin(kind, ...)
  local code = PIN_TOGGLE[kind]
  if not code then
    warnOnce(kind, "showPin does not know the pin kind " .. tostring(kind)
                   .. " -- drawing the pin")
    return 1
  end
  if kind == "entrance" then
    -- Auto is off on a plain standard seed and on when the doors have actually
    -- moved. Two questions, two sources, and either may be the only one there:
    --
    --   the variant       a No-Overworld board is doors all the way down, and
    --                     ActiveVariantUID is set before the first rule runs,
    --                     so this half answers with no cartridge in sight
    --   entranceShuffle   set by flag_mapping.lua from Entrances, Towns and
    --                     Floors. An item rather than an ffrFlag() call, for
    --                     the reason isNoOverworld() gives above: PopTracker
    --                     re-asks a rule when an item changes and at no other
    --                     time, so a rule reading only FFR_FLAGS would draw the
    --                     previous cartridge's answer until something else moved
    --
    -- Both halves can hold at once. No-Overworld's own full shuffle only runs
    -- with Entrances or Towns set, so a doubly shuffled seed is an ordinary
    -- cartridge rather than a contradiction to resolve.
    local obj = Tracker:FindObjectForCode(code)
    if not obj then
      warnOnce(code, "no pin toggle named " .. tostring(code) .. " -- drawing the pin")
      return 1
    end
    local stage = obj.CurrentStage or ENTRANCE_AUTO
    if stage == ENTRANCE_OFF then
      return 0
    end
    if stage == ENTRANCE_ON then
      return 1
    end
    if isNoOverworld() then
      return 1
    end
    if Tracker:ProviderCountForCode("entranceShuffle") > 0 then
      return 1
    end
    -- Fails open on the same reasoning as toggleOn, and needs saying separately
    -- because this is the one code in the branch that is not the pin toggle: an
    -- item nothing defines counts zero exactly like a seed that moved no doors,
    -- so a rename in flags.json would empty the Auto stage and say nothing.
    if not Tracker:FindObjectForCode("entranceShuffle") then
      warnOnce("entranceShuffle",
               "nothing defines entranceShuffle -- drawing the pin")
      return 1
    end
    return 0
  end
  if kind == "slot" then
    -- A slot this seed did incentivize is not a skipped one, so the toggle has
    -- no say over it. The flags are one section's own ^$incentiveSlot flags,
    -- passed in from the location file, so the pairing is not copied here.
    --
    -- These are ANDed, and the OR is the rule array's. A section can carry a
    -- conjunction -- FFR computes IncentivizeCaravan as
    -- (NPCItems && IncentivizeFreeNPCs) and each fetch incentive the same shape
    -- one flag along (FlagsCompute.cs:217, :220-226) -- so a slot speaking for
    -- two flags rings on both or not at all. A node holding several sections
    -- gets one entry each and PopTracker ORs them (location.cpp:266), which is
    -- what this docstring has claimed since it was written; the tool that
    -- writes these joined a node's sections into one entry instead, and folding
    -- the OR here is what made a conjunction inexpressible.
    --
    -- An undefined flag counts zero and falls through to the toggle rather than
    -- to a permanent hide; tests/test_pins.lua is what keeps one from existing.
    local incentivized = select("#", ...) > 0
    for _, flag in ipairs({ ... }) do
      if Tracker:ProviderCountForCode(flag) <= 0 then
        incentivized = false
        break
      end
    end
    if incentivized then
      return 1
    end
    -- Nor is any slot a skipped one on a run where the chests are the checks.
    -- "The seed did not incentivize this" means "there is probably nothing good
    -- here", and that stops being true the moment every chest can hold a shard
    -- or a key item: the sheet is the board then, not a poster, and a toggle
    -- that emptied it would take the run off the screen.
    --
    -- Two questions, not one. isShardHunt() reads the variant, which is set
    -- before the first rule is evaluated and is right on an Archipelago-only
    -- session with no cartridge in sight. chestsAreChecks() is maptab.lua's,
    -- and answers from the pool Archipelago reported or the cartridge's own
    -- flags -- neither of which exists until autotracking loads, which it may
    -- never do. Hence the type check rather than a call.
    if isShardHunt() then
      return 1
    end
    if type(chestsAreChecks) == "function" and chestsAreChecks() then
      return 1
    end
  end
  if toggleOn(code) then
    return 1
  end
  return 0
end
