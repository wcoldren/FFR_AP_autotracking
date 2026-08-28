-- End to end: real bridge emits Var JSON -> real pack decodes it.
local PACK = arg[1]

MEMORY = {}
local sent, inbox = {}, ""
local frameCb = nil
local pendingClient = nil
local fakeClient = {
  settimeout=function() return 1 end, setoption=function() return 1 end,
  close=function() end,
  send=function(self,d) sent[#sent+1]=d; return #d end,
  receive=function() local o=inbox; inbox=""; return nil,"timeout",o end,
}
emu = {
  memType={nesDebug=0x100}, eventType={endFrame=3,reset=4,stateLoaded=7},
  getRomInfo=function() return {name="seedA.nes",path="",fileSha1Hash="sha-A"} end,
  read=function(a) return MEMORY[a] or 0 end,
  log=function() end, displayMessage=function() end,
  addEventCallback=function(fn,ev) if ev==3 then frameCb=fn end end,
}
package.preload["socket.core"]=function() return { tcp=function() return {
  setoption=function() return 1 end, bind=function() return 1 end,
  listen=function() return 1 end, settimeout=function() return 1 end,
  close=function() end,
  accept=function() local c=pendingClient; pendingClient=nil
    if c then return c end; return nil,"timeout" end } end } end

assert(loadfile(PACK.."/bridge/ffr_uat_bridge.lua"))()

-- connect + handshake
pendingClient=fakeClient; frameCb()
inbox="GET / HTTP/1.1\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n"
frameCb(); sent={}

-- Matoya's Cave - Chest 1 is AP id 299 = byte 0x2B chest bit.
-- Bikke is AP id 516 = byte 0x04 event bit.
MEMORY[0x6102]=0x41
MEMORY[0x6200+0x2B]=0x04
MEMORY[0x6200+0x04]=0x02
-- Two of the chests that got map markers, one from each style: Ice Cave
-- Six-Pack Top Left is its own per-chest location (AP 371, flag byte 115),
-- Cardia Forest Chests is a group of six (AP 388, flag byte 132).
MEMORY[0x6200+115]=0x04
MEMORY[0x6200+132]=0x04
MEMORY[0x6202]=0x02            -- Garland defeated
MEMORY[0x6031]=1               -- Earth Orb lit
for _=1,60 do frameCb() end

-- pull the flags array straight off the wire
local blob=table.concat(sent)
-- the bridge sends a zeroed snapshot before the save is loaded, so take the
-- most recent mem var on the wire, not the first
local arr
for m in blob:gmatch('"ff1/mem","value":%[([^%]]+)%]') do arr=m end
assert(arr, "no mem var on the wire")
local mem={}
for v in arr:gmatch("[^,]+") do mem[#mem+1]=tonumber(v) end
local ready = blob:find('"ff1/ready","value":true',1,true)~=nil

-- now the pack side, fresh state
_G.emu=nil
local PopApi = dofile(PACK.."/tests/pop_api.lua")
local objects={}
local luaItems={}
-- Strict, and with CreateLuaItem on ScriptHost where PopTracker puts it. Without
-- the stub this suite loads uat.lua but silently skips both LuaItems, so the
-- full-stack path never built the ROM memo it depends on.
Tracker=PopApi.strict("Tracker",{BulkUpdate=false,
  FindObjectForCode=function(self,c)
    if objects[c] then return objects[c] end
    for _,it in ipairs(luaItems) do
      if it.CanProvideCodeFunc and it.CanProvideCodeFunc(it,c) then return it end
    end
  end})
local captured
ScriptHost=PopApi.strict("ScriptHost",{
  AddVariableWatch=function(self,n,v,cb) captured={cb=cb} end,
  CreateLuaItem=function(self) local it={} luaItems[#luaItems+1]=it return it end})
AUTOTRACKER_ENABLE_DEBUG_LOGGING=false
dofile(PACK.."/scripts/autotracking/location_mapping.lua")

-- Sections come from the real location JSON, resolved the way PopTracker
-- resolves them: "@" .. the location's own name .. "/" .. the section name,
-- with children flattened. Building these from LOCATION_MAPPING instead --
-- which is what this harness used to do -- meant every path answered for
-- itself, so a mapping pointing at a section the pack does not actually have
-- looked fine here and cleared nothing in the app.
local json = dofile(PACK.."/tests/json.lua")
local function addSections(nodes)
  for _,n in ipairs(nodes) do
    for _,sec in ipairs(n.sections or {}) do
      -- PopTracker: a section with hosted items and no explicit count is 0
      local count = sec.item_count or ((sec.hosted_item or sec.ref) and 0 or 1)
      objects["@"..n.name.."/"..sec.name]={ChestCount=count,AvailableChestCount=count}
    end
    addSections(n.children or {})
  end
end
for _,f in ipairs({"locations/overworld.json","locations/incentives.json"}) do
  addSections(json.load(PACK.."/"..f))
end
local hosted={}
for id,v in pairs(LOCATION_MAPPING) do
  if v[2] then hosted[v[2]]=true end
end
for c in pairs(hosted) do objects[c]={Active=false} end
dofile(PACK.."/scripts/autotracking/reconcile.lua")
dofile(PACK.."/scripts/autotracking/ram_mapping.lua")
dofile(PACK.."/scripts/autotracking/uat.lua")

-- Every code ram_mapping owns needs an object, or it iterates a board it
-- cannot write and says so 25 times.
for _,rule in ipairs(RAM_RULES) do
  objects[rule.code]=objects[rule.code] or {Active=false,CurrentStage=0}
end
objects[RAM_SHARDS.code]={Active=false,CurrentStage=0}

local rom = "sha-A"
local store={ReadVariable=function(self,n)
  if n=="ff1/ready" then return ready end
  if n=="ff1/mem" then return mem end
  if n=="ff1/rom" then return rom end
end}

local fail=0
local function check(name,got,want)
  if got~=want then print(string.format("FAIL %-46s got=%s want=%s",name,tostring(got),tostring(want))); fail=fail+1
  else print(string.format("ok   %-46s %s",name,tostring(got))) end
end

local sec=LOCATION_MAPPING[299][1]
local before=objects[sec].AvailableChestCount
captured.cb(store)
check("wire ready reached the pack", ready, true)
check("chest 299 cleared via the wire", objects[sec].AvailableChestCount, before-1)
check("Bikke event cleared via the wire", objects[LOCATION_MAPPING[516][2]].Active, true)
check("UAT_CHECKED holds 299", UAT_CHECKED[299], true)
check("UAT_CHECKED holds 516", UAT_CHECKED[516], true)
check("garland set from the wire", objects["garland"].Active, true)
check("earth orb lit from the wire", objects["earthorb"].CurrentStage, 1)

-- The mapped chests behind map markers have to clear through the same chain.
-- These resolve against the real location JSON, so a renamed node or a section
-- that moved fails here instead of in the app.
for _, t in ipairs({
  { id = 371, want = "@Ice Cave Six-Pack Top Left/Chest", label = "Ice Cave per-chest" },
  { id = 388, want = "@Cardia Forest Entrance Top/Chest", label = "Cardia Forest per-chest" },
}) do
  local path = LOCATION_MAPPING[t.id][1]
  check(t.label .. " path", path, t.want)
  local o = objects[path]
  if not o then
    print(string.format("FAIL %-46s no such section in the location JSON", t.label))
    fail = fail + 1
  else
    check(t.label .. " cleared one", o.AvailableChestCount, o.ChestCount - 1)
  end
end

-- replay the identical wire state: must not move anything
captured.cb(store)
check("replayed wire state is a no-op", objects[sec].AvailableChestCount, before-1)

-- and the AP feed reporting the same location must not double-clear
markAPChecked(299)
check("AP agreeing with UAT is a no-op", objects[sec].AvailableChestCount, before-1)

------------------------------------------------------------------
-- The 2026-08-19 regression, end to end: finish a seed, put a different one
-- in, and the board has to follow. Everything derived from RAM used to be
-- raise-only, so the finished run's orbs, key items, turn-ins and hosted codes
-- stayed on screen with nothing able to take them down.
------------------------------------------------------------------
AP_CHECKED = {}

-- Deepen the "finished seed" board first, from the same shape of data the real
-- save carried: four orbs lit, slab handed to Lefein, twelve shards.
local function put(addr, value) mem[addr - 0x6000 + 1] = value end
put(0x6031,1) put(0x6032,1) put(0x6033,1) put(0x6034,1)
put(0x6035,12)
put(0x6028,1) put(0x620B,0x02) put(0x620F,0x02)
put(0x6021,1)
captured.cb(store)
check("orbs lit on the finished seed", objects["airorb"].CurrentStage, 1)
check("slab at Lefein's stage", objects["slab"].CurrentStage, 3)
check("twelve shards", objects["shards"].CurrentStage, 12)
check("lute held", objects["lute"].Active, true)

-- A brand new game on a different cartridge: the flag page comes back as
-- lut_InitGameFlags (0x01 for 249 bytes, 0x00 for 7 -- no chest bit and no
-- event bit anywhere), and page 0 of unsram has no items in it.
local fresh = {}
for i = 1, 768 do fresh[i] = 0 end
for b = 0, 248 do fresh[0x200 + b + 1] = 0x01 end
mem = fresh
rom = "sha-B"
captured.cb(store)

check("new cartridge released the chest", objects[sec].AvailableChestCount, before)
check("new cartridge released Ice Cave", objects["@Ice Cave Six-Pack Top Left/Chest"].AvailableChestCount, 1)
check("new cartridge cleared Bikke", objects[LOCATION_MAPPING[516][2]].Active, false)
check("new cartridge emptied UAT_CHECKED", next(UAT_CHECKED), nil)
check("orbs went out", objects["airorb"].Active, false)
check("slab went out", objects["slab"].CurrentStage, 0)
check("shards went back to zero", objects["shards"].CurrentStage, 0)
check("key items went out", objects["lute"].Active, false)
check("garland went out", objects["garland"].Active, false)

------------------------------------------------------------------
-- The same story on the Archipelago side. PopTracker restores the board it
-- saved last session after the pack's scripts have run, so anyone who tracked
-- an earlier seed connects to a fresh multiworld with the old one on screen.
-- resetForNewGame has dropped that since the seed swap; the AP path goes
-- through resetChecked, which used to leave every hosted code standing --
-- and the hosted codes are what the Incentive Locations pins read.
------------------------------------------------------------------
local restoredSec = "@Ice Cave Six-Pack Top Left/Chest"
local bikke = LOCATION_MAPPING[516][2]
local astos = LOCATION_MAPPING[519][2]
local sages = LOCATION_MAPPING[533][2]

-- A restore writes straight onto the objects. reconcile is not consulted and
-- WRITTEN knows nothing about it, which is the whole difficulty.
objects[restoredSec].AvailableChestCount = 0
objects[bikke].Active = true
objects[astos].Active = true
objects[sages].Active = true

resetChecked()

check("AP connect released the chest", objects[restoredSec].AvailableChestCount, objects[restoredSec].ChestCount)
check("AP connect cleared Bikke", objects[bikke].Active, false)
check("AP connect cleared Astos", objects[astos].Active, false)
check("AP connect cleared the Sages", objects[sages].Active, false)

-- A reconnect mid-run must not cost the bridge anything: applyAll re-applies
-- the hosted codes for everything still in UAT_CHECKED.
setUATChecked({ [516] = true })
check("bridge set Bikke", objects[bikke].Active, true)
objects[astos].Active = true            -- stale, no feed reports it
resetChecked()
check("reconnect kept the bridge's Bikke", objects[bikke].Active, true)
check("reconnect dropped the stale Astos", objects[astos].Active, false)
check("reconnect left UAT_CHECKED alone", UAT_CHECKED[516], true)

-- The restore that lands *after* the connect, on a slot with nothing checked:
-- no location ever reaches markAPChecked, so absorbForPath never gets to
-- notice and only reassertBoard can put the board back.
local moved, seen = {}, {}
for id = 257, 400 do
  local v = LOCATION_MAPPING[id]
  local path = v and v[1]
  if path and path:sub(1,1) == "@" and objects[path] and not seen[path] and #moved < 6 then
    if objects[path].ChestCount > 0 then
      seen[path] = true
      moved[#moved+1] = path
    end
  end
end
check("found sections to move", #moved, 6)
for _, path in ipairs(moved) do objects[path].AvailableChestCount = 0 end

reassertBoard()

local restored = 0
for _, path in ipairs(moved) do
  if objects[path].AvailableChestCount == objects[path].ChestCount then restored = restored + 1 end
end
check("reassert put every moved section back", restored, #moved)
check("reassert kept the bridge's Bikke", objects[bikke].Active, true)

-- The hosted codes come back with that restore too, and resetChecked has
-- already been and gone. applyAll cannot lower them, so the reassert has to.
objects[astos].Active = true
reassertBoard()
check("reassert drops a hosted code the restore put back", objects[astos].Active, false)
check("reassert still kept the bridge's Bikke", objects[bikke].Active, true)

-- A move small enough to be a person is still a person: it is carried, not
-- overwritten. MANUAL_BULK_LIMIT is 3.
objects[moved[1]].AvailableChestCount = 0
reassertBoard()
check("a single hand clear survives reassert", objects[moved[1]].AvailableChestCount, 0)

print(fail==0 and "\nALL PASS" or string.format("\n%d FAILURE(S)",fail))
os.exit(fail==0 and 0 or 1)
