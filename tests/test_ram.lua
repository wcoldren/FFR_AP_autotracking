-- RAM-derived codes, checked against a PopTracker-faithful item model.
--
-- Assertions are on the CODES an item ends up providing, not on stage numbers.
-- Codes are what actually drive the UI: an item icon shows its stage's art,
-- and a hosted-item section clears when every code it hosts has a provider
-- (locationsection.cpp:236-247). Testing stage numbers instead is what let the
-- turn-in off-by-one ship.
local PACK = arg[1]
local json = dofile(PACK .. "/tests/json.lua")
local ItemModel = dofile(PACK .. "/tests/item_model.lua")

AUTOTRACKER_ENABLE_DEBUG_LOGGING = false

local ITEM_FILES = {
  "items/items.json", "items/hosted_items.json",
  "items/flags.json", "items/shards.json",
}
local byCode, allItems

local function rebuild()
  byCode, allItems = ItemModel.loadPack(json, PACK, ITEM_FILES)
end
rebuild()

Tracker = {
  ActiveVariantUID = "5standard",
  FindObjectForCode = function(self, code) return byCode[code] end,
  ProviderCountForCode = function(self, code)
    local n = 0
    for _, item in ipairs(allItems) do n = n + item:providesCode(code) end
    return n
  end,
}

dofile(PACK .. "/scripts/autotracking/ram_mapping.lua")
dofile(PACK .. "/scripts/logic.lua")

local MEM = {}
local function byteAt(addr) return MEM[addr] or 0 end

-- Game flags that a freshly initialised save does NOT start at zero, so a test
-- that says nothing about them describes a real new game rather than an
-- impossible one. Read out of lut_InitGameFlags ($AF00, BANK_STARTUPINFO, bank
-- 0 -> file offset 0x2F10): object $14 starts at 0x01, GMFLG_OBJVISIBLE.
--
-- It matters because Titan is read as "the object is gone" rather than as an
-- event bit -- see the ruby rules in ram_mapping.lua. Defaulting him to 0 would
-- have every case here open with the Ruby already eaten.
local INIT_FLAGS = { [0x6214] = 0x01 }   -- Titan, visible

local function reset()
  MEM = {}
  for addr, v in pairs(INIT_FLAGS) do MEM[addr] = v end
  rebuild()
  -- Each case is a different cartridge, not the next scan of the last one, so
  -- drop the derived-stage history too. clearRamDerivedItems() does this in
  -- production; doing it by hand here keeps the item model rebuild above as the
  -- only thing reset() owns.
  LAST_RAM_STAGE, VANISH_WARNED = {}, {}
end
reset()

local fail = 0
local function check(name, got, want)
  if got ~= want then
    print(string.format("FAIL %-52s got=%s want=%s", name, tostring(got), tostring(want)))
    fail = fail + 1
  else
    print(string.format("ok   %-52s %s", name, tostring(got)))
  end
end
local function provided(code) return Tracker:ProviderCountForCode(code) >= 1 end

-- Mirrors locationsection.cpp:236-247 for a section with no item_count:
-- CLEARED once every hosted code has a provider.
local function markerCleared(...)
  for _, code in ipairs({ ... }) do
    if not provided(code) then return false end
  end
  return true
end

------------------------------------------------------------------
-- The turn-ins that prompted this
------------------------------------------------------------------

-- Bahamut's Tail
reset()
MEM[0x602D] = 1                                  -- holding the Tail
applyRamRules(byteAt)
check("tail held provides 'tail'", provided("tail"), true)
check("tail held does NOT provide 'bahamut'", provided("bahamut"), false)
MEM[0x602D] = 0                                  -- consumed by the class change
MEM[0x620E] = 0x02                               -- Bahamut event flag
applyRamRules(byteAt)
check("Bahamut done provides 'bahamut'", provided("bahamut"), true)
check("Bahamut's Cave marker clears", markerCleared("bahamut"), true)

-- The airship
reset()
MEM[0x602B] = 1                                  -- holding the Floater
applyRamRules(byteAt)
check("floater held provides 'inactiveFloater'", provided("inactiveFloater"), true)
check("floater held does NOT provide 'airship'", provided("airship"), false)
MEM[0x6004] = 1                                  -- airship_vis
applyRamRules(byteAt)
check("airship provides 'airship'", provided("airship"), true)
check("Floater Turn In marker clears", markerCleared("airship"), true)

-- The rest of the turn-in family
reset()
MEM[0x6207] = 0x02  -- Astos
MEM[0x620A] = 0x02  -- Matoya
MEM[0x6205] = 0x02  -- Elf Doctor
MEM[0x6208] = 0x02  -- Nerrick
MEM[0x6209] = 0x02  -- Smith
MEM[0x6214] = 0x00  -- Titan fed: the object goes away, no event bit is set
MEM[0x6213] = 0x02  -- Fairy
applyRamRules(byteAt)
check("Astos  -> crownDone",    provided("crownDone"), true)
check("Matoya -> crystalDone",  provided("crystalDone"), true)
check("ElfDoc -> herbDone",     provided("herbDone"), true)
check("Nerrick-> tntDone",      provided("tntDone"), true)
check("Smith  -> adamantDone",  provided("adamantDone"), true)
check("Titan  -> titan",        provided("titan"), true)
check("Fairy  -> bottlepopped", provided("bottlepopped"), true)

-- Slab: two turn-ins, and the earlier code must survive the later one
reset()
MEM[0x6028] = 1
applyRamRules(byteAt)
check("slab held provides 'slab'", provided("slab"), true)
check("slab held does NOT provide 'slabTranslated'", provided("slabTranslated"), false)
MEM[0x620B] = 0x02                               -- Unne translates it
applyRamRules(byteAt)
check("Unne -> slabTranslated", provided("slabTranslated"), true)
check("Dr Unne marker clears", markerCleared("slabTranslated"), true)
MEM[0x620F] = 0x02                               -- Lefein takes it
applyRamRules(byteAt)
check("Lefein -> slabDone", provided("slabDone"), true)
check("Lefein -> slabTurnIn", provided("slabTurnIn"), true)
-- inherit_codes defaults true, so stage 2 still provides stage 1's codes and
-- the Dr Unne marker does not revert to green
check("slabTranslated survives stage 2", provided("slabTranslated"), true)
check("Dr Unne marker stays cleared", markerCleared("slabTranslated"), true)

-- The Bottle is the one item spent by using it rather than by a turn-in: the
-- inventory byte clears the moment it is popped, while the Fairy's event bit
-- does not arrive until she is talked to, potentially hours later. @Gaia/Fairy
-- is gated on the bare `bottle` code, so the popped state has to hold that
-- code across the whole gap or the check falls out of logic while it is open.
reset()
MEM[0x602F] = 1
applyRamRules(byteAt)
check("bottle held provides 'bottle'", provided("bottle"), true)
check("bottle held is not popped yet", provided("bottlepopped"), false)
MEM[0x602F] = 0                                  -- UseItem_Bottle empties it
MEM[0x6213] = 0x01                               -- ShowMapObject(OBJID_FAIRY)
applyRamRules(byteAt)
check("popped bottle keeps 'bottle'", provided("bottle"), true)
check("popped bottle provides 'bottlepopped'", provided("bottlepopped"), true)
MEM[0x6213] = 0x03                               -- then the Fairy hands over
applyRamRules(byteAt)
check("fairy turn-in keeps 'bottle'", provided("bottle"), true)
check("fairy turn-in keeps 'bottlepopped'", provided("bottlepopped"), true)

-- The Ruby's consequence outlives the item by the widest margin of any turn-in:
-- Talk_Titan takes it, and from that moment Titan's Tunnel is simply open for
-- the rest of the seed. Both Titan's Trove and Sarda's Cave gate on the bare
-- `ruby` code, so if the spent Ruby stopped providing it, the chests behind
-- Titan would go red on the seed where they had just opened -- the same shape
-- of bug as the Bottle above, but on four chests and Sarda rather than one NPC.
--
-- Stage 1 carries "ruby,titan" for exactly this reason. These cases pin the
-- real access_rules out of locations/overworld.json to it rather than asserting
-- on the code alone, so a later edit that swaps `ruby` for a code the consumed
-- state does not provide fails here instead of in someone's run.
local OVERWORLD = json.load(PACK .. "/locations/overworld.json")

-- First node with this name, depth first. Names are unique in the tree.
local function findLocation(nodes, name)
  for _, node in ipairs(nodes or {}) do
    if node.name == name then return node end
    local hit = findLocation(node.children, name)
    if hit then return hit end
  end
end

-- One access_rules entry: comma-separated terms, all of which must hold.
-- Only the two forms these locations use are understood; anything else is a
-- hard error rather than a quiet pass, so the day a rule grows a `@section`
-- or a `count:` term this stops claiming to have checked it.
local function ruleHolds(rule)
  for raw in string.gmatch(rule, "[^,]+") do
    local term = raw:match("^%s*(.-)%s*$")
    local held
    if term:sub(1, 1) == "$" then
      local fn = _G[term:sub(2)]
      if not fn then error("access rule calls unknown logic function " .. term) end
      held = (fn() or 0) > 0
    elseif term:match("^[%w_]+$") then
      held = provided(term)
    else
      error("test cannot evaluate access rule term: " .. term)
    end
    if not held then return false end
  end
  return true
end

-- The chain of nodes from the tree root down to `name`, or nil.
local function chainTo(nodes, name, acc)
  for _, node in ipairs(nodes or {}) do
    acc[#acc + 1] = node
    if node.name == name then return acc end
    if chainTo(node.children, name, acc) then return acc end
    acc[#acc] = nil
  end
end

-- PopTracker takes a location as reachable if ANY of its access_rules holds --
-- but a child's rules are not its own. At load it builds the cross product of
-- its parent's alternatives with its own, appending the terms
-- (PopTracker src/core/location.cpp:103-134): AND within an alternative, OR
-- across them, all the way down. A node with no rules of its own inherits its
-- parent's unchanged.
--
-- Reading only the named node's rules is what this did until 2026-08-31, and it
-- made every check on a rule-less node vacuous: the seven ToFR chests hang off
-- a parent that carries the whole gate, so inLogic on one of them answered
-- "reachable" no matter what was held. A check that cannot fail is worth
-- nothing, and these are the checks the ToFR work needs.
--
-- `sectionRules` is the extra alternatives a section carries; PopTracker merges
-- those the same way, which is how a section is gated more tightly than the
-- node it sits on.
local function inLogic(name, sectionRules)
  local chain = chainTo(OVERWORLD, name, {})
  if not chain then error("no location named " .. name .. " in overworld.json") end
  local alts = {{}}
  local function mergeIn(rules)
    if not rules or #rules == 0 then return end
    local out = {}
    for _, old in ipairs(alts) do
      for _, rule in ipairs(rules) do
        local merged = {}
        for _, t in ipairs(old) do merged[#merged + 1] = t end
        merged[#merged + 1] = rule
        out[#out + 1] = merged
      end
    end
    alts = out
  end
  for _, node in ipairs(chain) do mergeIn(node.access_rules) end
  mergeIn(sectionRules)
  for _, alt in ipairs(alts) do
    local held = true
    for _, rule in ipairs(alt) do
      if not ruleHolds(rule) then held = false break end
    end
    if held then return true end
  end
  return false
end

reset()
-- A forested seed, so the one Sarda route that does not need the Ruby
-- ($noSardasForest,airship) is closed and both locations really do hang on it.
byCode["sardasForest"].Active = true
MEM[0x602B] = 1                                  -- Floater
MEM[0x6004] = 1                                  -- airship flying
MEM[0x6029] = 1                                  -- Ruby in the bag
applyRamRules(byteAt)
check("ruby held provides 'ruby'", provided("ruby"), true)
check("ruby held does NOT provide 'titan'", provided("titan"), false)
check("ruby held: Titan's Trove in logic", inLogic("Titan's Trove"), true)
check("ruby held: Sarda's Cave in logic", inLogic("Sarda's Cave"), true)

MEM[0x6029] = 0                                  -- Talk_Titan eats the Ruby
MEM[0x6214] = 0x00                               -- and hides him; no flag is set
applyRamRules(byteAt)
check("spent ruby keeps 'ruby'", provided("ruby"), true)
check("Titan done provides 'titan'", provided("titan"), true)
check("spent ruby: Titan's Trove stays in logic", inLogic("Titan's Trove"), true)
check("spent ruby: Sarda's Cave stays in logic", inLogic("Sarda's Cave"), true)

-- Attaching the tracker to a save that is already past Titan never sees the
-- stage-0 sighting at all, so stage 1 has to stand on the event flag alone.
reset()
byCode["sardasForest"].Active = true
MEM[0x602B] = 1
MEM[0x6004] = 1
MEM[0x6214] = 0x00                               -- only his absence survives
applyRamRules(byteAt)
check("cold start past Titan provides 'ruby'", provided("ruby"), true)
check("cold start past Titan: Titan's Trove in logic", inLogic("Titan's Trove"), true)
check("cold start past Titan: Sarda's Cave in logic", inLogic("Sarda's Cave"), true)

-- The negative: without the Ruby a forested Sarda and the Trove are both shut,
-- so the cases above are not passing on some unrelated always-true route.
reset()
byCode["sardasForest"].Active = true
MEM[0x602B] = 1
MEM[0x6004] = 1
applyRamRules(byteAt)
check("no ruby: Titan's Trove out of logic", inLogic("Titan's Trove"), false)
check("no ruby: Sarda's Cave out of logic", inLogic("Sarda's Cave"), false)

-- $6214 is not Titan's byte alone. The flag array is a shared id space: byte i
-- carries chest i's opened bit (0x04) as well as event i's (0x02), and index
-- $14 is both OBJID_TITAN and chest $14. Every case above leaves that chest
-- shut, which is why a rule reading the whole byte passed here for months and
-- still blanked the Ruby on a real save the moment the chest was looted.
--
-- The two states below are transcribed from saves: 0x04 is fed-with-the-chest-
-- open, 0x05 is still-standing-with-the-chest-open.
reset()
byCode["sardasForest"].Active = true
MEM[0x602B] = 1
MEM[0x6004] = 1
MEM[0x6029] = 0                                  -- Ruby eaten
MEM[0x6214] = 0x04                               -- Titan gone, chest $14 looted
applyRamRules(byteAt)
check("fed Titan with chest $14 open keeps 'ruby'", provided("ruby"), true)
check("fed Titan with chest $14 open provides 'titan'", provided("titan"), true)
check("fed + chest open: Titan's Trove in logic", inLogic("Titan's Trove"), true)
check("fed + chest open: Sarda's Cave in logic", inLogic("Sarda's Cave"), true)

-- The other half of the same trap. Reading 0x04 as the turn-in -- by masking
-- 0x04, or 0x06 -- would call Titan fed here, while he is still standing and
-- the Ruby is still in the bag.
reset()
byCode["sardasForest"].Active = true
MEM[0x602B] = 1
MEM[0x6004] = 1
MEM[0x6029] = 1                                  -- Ruby still held
MEM[0x6214] = 0x05                               -- Titan visible, chest $14 looted
applyRamRules(byteAt)
check("chest $14 alone does NOT feed Titan", provided("titan"), false)
check("chest $14 alone leaves 'ruby' held", provided("ruby"), true)

------------------------------------------------------------------
-- Bosses
------------------------------------------------------------------
reset()
MEM[0x6202] = 0x01                               -- visible, not yet fought
applyRamRules(byteAt)
check("garland: visible bit alone does nothing", provided("garland"), false)
MEM[0x6202] = 0x02                               -- defeated
applyRamRules(byteAt)
check("garland: event bit sets it", provided("garland"), true)
check("Temple of Fiends Garland marker clears", markerCleared("garland"), true)

reset()
MEM[0x620C] = 0x02
applyRamRules(byteAt)
check("vampire set by event bit", provided("vampire"), true)

------------------------------------------------------------------
-- Orbs. These take the other path -- allow_disabled is false, so no offset --
-- which is why they worked while every turn-in did not.
------------------------------------------------------------------
reset()
check("canBreakOrb 0 with no orbs", canBreakOrb(), 0)
MEM[0x6031], MEM[0x6032], MEM[0x6033] = 1, 1, 1
applyRamRules(byteAt)
check("three orbs is not enough", canBreakOrb(), 0)
MEM[0x6034] = 1
applyRamRules(byteAt)
check("earth orb lit provides 'earthorblit'", provided("earthorblit"), true)
check("air orb lit provides 'airorblit'", provided("airorblit"), true)
check("lit orb still provides base 'earthorb'", provided("earthorb"), true)
check("canBreakOrb 1 with all four lit", canBreakOrb(), 1)
check("I: Earth Orb incentive marker clears", markerCleared("earthorblit"), true)

------------------------------------------------------------------
-- ChaosRush. ToFR's chests and the Chaos fight sit behind the lute plate and
-- a key-locked door; EnableChaosRush rewrites that door's tile properties as
-- an ordinary door (FF1Lib/TempleOfFiends.cs:496-500, tileset ToFR only), so
-- the Key stops being the thing that opens the floor. The Lute is not touched
-- -- the plate is an object gate, not this tile.
------------------------------------------------------------------
reset()
MEM[0x6031], MEM[0x6032], MEM[0x6033], MEM[0x6034] = 1, 1, 1, 1   -- four orbs lit
MEM[0x6021] = 1                                  -- Lute
applyRamRules(byteAt)
check("orbs and lute, no key: ToFR out of logic", inLogic("ToFR"), false)
byCode["chaosRush"].Active = true
check("chaosRush opens ToFR without the key", inLogic("ToFR"), true)

-- And the ordinary route is untouched: the Key still opens it on a seed that
-- did not roll the flag.
byCode["chaosRush"].Active = false
MEM[0x6025] = 1                                  -- Key
applyRamRules(byteAt)
check("the key still opens ToFR without chaosRush", inLogic("ToFR"), true)

-- The Lute is not what ChaosRush buys, so it is still required either way.
reset()
MEM[0x6031], MEM[0x6032], MEM[0x6033], MEM[0x6034] = 1, 1, 1, 1
MEM[0x6025] = 1                                  -- Key but no Lute
applyRamRules(byteAt)
byCode["chaosRush"].Active = true
check("chaosRush does not replace the lute", inLogic("ToFR"), false)
byCode["chaosRush"].Active = false

------------------------------------------------------------------
-- ToFRMode = Short. ShortenToFR repoints the Black Orb warp straight at
-- tofrChaos (15,3) and lays the seven chests at cols 12-18, rows 1-2 -- in
-- front of the landing tile, with the lute-gated object 23 at (15,5) two tiles
-- past it (NOVERWORLD.md, "what the shortcut drops you into", measured on two
-- Short cartridges). So the chests want the orbs and nothing else, while Chaos
-- is still behind the gate.
--
-- The oracle agrees and needs no new cartridge: oracle-4.9.2/nov rolls
-- ToFRMode 2, and its derived_nov.json gives all seven [["orbs"]].
------------------------------------------------------------------
local TOFR_CHESTS = {
  "ToFR Kary Floor 1", "ToFR Kary Floor 2", "ToFR Kary Floor 3",
  "ToFR Kary Floor 4", "ToFR Lute Plate Room 1", "ToFR Lute Plate Room 2",
  "ToFR Vanilla Masa",
}

-- Chaos is a section of the ToFR node, so its gate is the node's alternatives
-- crossed with its own. Read them out of the tree rather than restating them,
-- so this tracks the file.
local function chaosRules()
  local node = findLocation(OVERWORLD, "ToFR")
  for _, sec in ipairs(node.sections or {}) do
    if sec.name == "Chaos" then return sec.access_rules end
  end
  error("no Chaos section on the ToFR node")
end

local function allChests()
  for _, name in ipairs(TOFR_CHESTS) do
    if not inLogic(name) then return false end
  end
  return true
end

reset()
MEM[0x6031], MEM[0x6032], MEM[0x6033], MEM[0x6034] = 1, 1, 1, 1   -- four orbs lit
applyRamRules(byteAt)
check("orbs alone: no ToFR chest is in logic", allChests(), false)
check("and Chaos is not either", inLogic("ToFR", chaosRules()), false)

byCode["shortToFR"].CurrentStage = 1
check("Short: the orbs alone reach all seven chests", allChests(), true)
check("but Short does not open Chaos", inLogic("ToFR", chaosRules()), false)

MEM[0x6021], MEM[0x6025] = 1, 1                  -- Lute and Key
applyRamRules(byteAt)
check("Short: lute and key open Chaos", inLogic("ToFR", chaosRules()), true)

-- Long and Mid ask for exactly the same thing, so a non-Short seed is unmoved.
reset()
MEM[0x6031], MEM[0x6032], MEM[0x6033], MEM[0x6034] = 1, 1, 1, 1
applyRamRules(byteAt)
byCode["shortToFR"].CurrentStage = 0
check("not Short: the orbs alone still reach nothing", allChests(), false)
byCode["shortToFR"].CurrentStage = 0

------------------------------------------------------------------
-- RAM is authoritative, in both directions. This used to be raise-only, which
-- is how a finished seed's orbs, key items and turn-ins survived into the next
-- one: the new game's zeroed bytes had no way to take them back down.
------------------------------------------------------------------
reset()
MEM[0x6028] = 1
MEM[0x620B] = 0x02
MEM[0x620F] = 0x02
applyRamRules(byteAt)
check("slab reaches Lefein's stage", provided("slabDone"), true)
MEM[0x6028], MEM[0x620B], MEM[0x620F] = 0, 0, 0
applyRamRules(byteAt)
check("stage clears when RAM bits clear", provided("slabDone"), false)
check("and the base code goes with it", provided("slab"), false)

-- Partway back, not all the way: still translated, no longer handed in.
reset()
MEM[0x6028], MEM[0x620B], MEM[0x620F] = 1, 0x02, 0x02
applyRamRules(byteAt)
MEM[0x620F] = 0
applyRamRules(byteAt)
check("slab walks back one stage", provided("slabDone"), false)
check("slab keeps the stage RAM still proves", provided("slabTranslated"), true)

reset()
byCode["crown"].Active = true
byCode["crown"].CurrentStage = 2                 -- advanced to crownDone
MEM[0x6022] = 1                                  -- RAM only proves "holding"
applyRamRules(byteAt)
check("crownDone walked back to what RAM says", provided("crownDone"), false)
check("crown still held", provided("crown"), true)

-- The whole-board wipe reconcile uses on a ROM change.
reset()
MEM[0x6031], MEM[0x6032], MEM[0x6033], MEM[0x6034] = 1, 1, 1, 1
MEM[0x6021], MEM[0x6035] = 1, 12
applyRamRules(byteAt)
check("board lit before the wipe", provided("earthorblit"), true)
clearRamDerivedItems()
check("orbs wiped", provided("earthorblit"), false)
check("key items wiped", provided("lute"), false)
-- Every shard stage provides the same "shards" code -- logic.lua reads the
-- count off CurrentStage -- so this one is asserted on the number.
check("shards wiped", byCode["shards"].CurrentStage, 0)

------------------------------------------------------------------
-- Archipelago carve-out. AP grants items through onItem and replays them only
-- on onClear, so while a session is live RAM must not clear anything AP owns.
-- Codes RAM alone owns keep following it down.
------------------------------------------------------------------
dofile(PACK .. "/scripts/autotracking/item_mapping.lua")
reset()
MEM[0x6021] = 1                                  -- lute, also an AP item
MEM[0x6202] = 0x02                               -- garland, RAM-only
MEM[0x6031] = 1                                  -- earth orb, RAM-only
applyRamRules(byteAt)
check("lute lit", provided("lute"), true)
check("garland lit", provided("garland"), true)
AP_ITEM_FEED_ACTIVE = true
MEM[0x6021], MEM[0x6202], MEM[0x6031] = 0, 0, 0
applyRamRules(byteAt)
check("AP-owned code is not cleared by RAM", provided("lute"), true)
check("RAM-only boss still clears", provided("garland"), false)
check("RAM-only orb still clears", provided("earthorblit"), false)
AP_ITEM_FEED_ACTIVE = false
applyRamRules(byteAt)
check("and clears once the AP feed is gone", provided("lute"), false)

------------------------------------------------------------------
-- sigil and mark are the floater and the canoe under Archipelago's names for
-- them on a No-Overworld seed, so the bridge sets them off the same two bytes.
--
-- This block used to assert the opposite -- that nothing here writes them --
-- on the reading that they were the item screen's renames and so had no byte
-- of their own. That is half right. The item screen renames Floater to SIGIL
-- and the *Earth Orb* to MARK, but the pack's two codes are fed by AP item ids
-- 499 and 500, and the exporter renames Floater to Sigil and the *Canoe* to
-- Mark (Archipelago.cs:287-289,339-340). Following the exporter is what makes
-- the NOverworld grid's only two gate boxes light for a bridge-fed player.
------------------------------------------------------------------
reset()
MEM[0x602B], MEM[0x6012] = 1, 1
applyRamRules(byteAt)
check("sigil follows floater's byte", provided("sigil"), true)
check("mark follows canoe's byte", provided("mark"), true)
check("floater still set alongside sigil", provided("floater"), true)
check("canoe still set alongside mark", provided("canoe"), true)
MEM[0x602B], MEM[0x6012] = 0, 0
applyRamRules(byteAt)
check("sigil clears with its byte", provided("sigil"), false)
check("mark clears with its byte", provided("mark"), false)
reset()
MEM[0x602B], MEM[0x6012] = 1, 1
applyRamRules(byteAt)
clearRamDerivedItems()
check("sigil is wiped on a ROM change", provided("sigil"), false)
check("mark is wiped on a ROM change", provided("mark"), false)

------------------------------------------------------------------
-- Vehicles, canal inversion, shards
------------------------------------------------------------------
reset()
MEM[0x600C] = 1
applyRamRules(byteAt)
check("canal NOT set while byte nonzero", provided("canal"), false)
MEM[0x600C] = 0
MEM[0x6000], MEM[0x6008], MEM[0x6012] = 1, 1, 1
applyRamRules(byteAt)
check("canal set when byte reads zero", provided("canal"), true)
check("ship", provided("ship"), true)
check("bridge", provided("bridge"), true)
check("canoe", provided("canoe"), true)

-- shards has allow_disabled:false, so RAM_NO_STAGE_OFFSET holds and the stage
-- is the count itself. Both feeds used to sit one low; see ITEM_MAPPING type
-- "count".
reset()
MEM[0x6035] = 12
applyRamRules(byteAt)
check("shards follows the count up", byCode["shards"].CurrentStage, 12)
MEM[0x6035] = 3
applyRamRules(byteAt)
check("shards follows the count down", byCode["shards"].CurrentStage, 3)
MEM[0x6035] = 0
applyRamRules(byteAt)
check("shards clears at zero", byCode["shards"].CurrentStage, 0)

reset()
MEM[0x6035] = 1
applyRamRules(byteAt)
check("1 shard -> stage 1", byCode["shards"].CurrentStage, 1)
MEM[0x6035] = 25
applyRamRules(byteAt)
check("25 shards -> stage 25", byCode["shards"].CurrentStage, 25)
MEM[0x6035] = 99
applyRamRules(byteAt)
check("99 shards clamps to max stage", byCode["shards"].CurrentStage, RAM_SHARDS.maxStage)

------------------------------------------------------------------
-- MapAirshipHike and MapCardiaLandBridge, the two 4.9.7-only overworld-shape
-- flags. Both of them loosen. Each adds a route FFR's own exported rules gain
-- and the pack did not have, so before these codes existed the board held pins
-- red that FFR calls reachable -- 134 locations on an airship497 seed and 46 on
-- a landbridge497 one, against 226 of 226 clean on the std497 baseline they
-- differ from by one flag value (docs/ORACLE.md).
--
-- Cardia Forest is the one node that carries both new alternatives, so both
-- gates can be demonstrated on it and neither can pass by accident.
--
-- MapAirshipHike lets the Floater and the Ship stand in for having raised the
-- airship: OverworldMap.cs:62 adds the AirshipHike map edit, and every rule
-- FFR rewrites for it gains a (Floater AND Ship) alternative.
------------------------------------------------------------------
reset()
MEM[0x600C] = 1                                  -- canal not dug
MEM[0x602B] = 1                                  -- Floater held, airship not raised
MEM[0x6000] = 1                                  -- Ship
applyRamRules(byteAt)
check("floater and ship, no airship: Cardia Forest is out", inLogic("Cardia Forest"), false)
byCode["airshipHike"].Active = true
check("airshipHike opens it on the Floater and the Ship", inLogic("Cardia Forest"), true)

-- The Ship half is real. The hike is a walk from where the Ship can dock, so
-- the Floater on its own does not buy it.
reset()
MEM[0x600C] = 1
MEM[0x602B] = 1                                  -- Floater, no Ship
applyRamRules(byteAt)
byCode["airshipHike"].Active = true
check("airshipHike does not open it on the Floater alone", inLogic("Cardia Forest"), false)

-- A drydocked Ship opens nothing, which is why this alternative carries
-- $noShipDrydock like every other one that names the Ship.
reset()
MEM[0x600C] = 1
MEM[0x602B], MEM[0x6000] = 1, 1
applyRamRules(byteAt)
byCode["airshipHike"].Active = true
byCode["shipDrydock"].Active = true
check("a drydocked ship takes the hike away again", inLogic("Cardia Forest"), false)
byCode["airshipHike"].Active = false
byCode["shipDrydock"].Active = false

------------------------------------------------------------------
-- MapCardiaLandBridge puts the Cardia islands on reachable land and moves
-- their overworld teleport coordinates with them (OverworldMap.cs:64 and :392),
-- so the rules FFR rewrites for it gain a (Canoe AND Canal AND Ship)
-- alternative instead.
------------------------------------------------------------------
reset()
MEM[0x600C] = 0                                  -- canal dug; the byte reads zero
MEM[0x6012] = 1                                  -- Canoe
MEM[0x6000] = 1                                  -- Ship
applyRamRules(byteAt)
check("canoe, canal and ship: Cardia Forest is out", inLogic("Cardia Forest"), false)
byCode["cardiaLandBridge"].Active = true
check("cardiaLandBridge opens it on canoe, canal and ship", inLogic("Cardia Forest"), true)

-- The Canoe is the half the land bridge does not replace.
reset()
MEM[0x600C] = 0
MEM[0x6000] = 1                                  -- canal and Ship, no Canoe
applyRamRules(byteAt)
byCode["cardiaLandBridge"].Active = true
check("cardiaLandBridge still wants the canoe", inLogic("Cardia Forest"), false)
byCode["cardiaLandBridge"].Active = false


------------------------------------------------------------------
-- Sanity on the rule table itself
------------------------------------------------------------------
local unknown = {}
for _, rule in ipairs(RAM_RULES) do
  if not byCode[rule.code] then unknown[rule.code] = true end
end
if not byCode[RAM_SHARDS.code] then unknown[RAM_SHARDS.code] = true end
local list = {}
for c in pairs(unknown) do list[#list + 1] = c end
table.sort(list)
check("all rule codes exist in the pack", #list == 0 and "none" or table.concat(list, ","), "none")

local mentionsChaos = false
for _, rule in ipairs(RAM_RULES) do
  if rule.code == "chaos" then mentionsChaos = true end
end
check("chaos is not RAM-derived", mentionsChaos, false)

print(fail == 0 and "\nALL PASS" or string.format("\n%d FAILURE(S)", fail))
os.exit(fail == 0 and 0 or 1)
