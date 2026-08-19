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
local objects={}
Tracker={BulkUpdate=false,FindObjectForCode=function(self,c) return objects[c] end}
local captured
ScriptHost={AddVariableWatch=function(self,n,v,cb) captured={cb=cb} end}
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

-- ram_mapping needs these two codes present
objects["garland"]={Active=false,CurrentStage=0}
objects["earthorb"]={Active=false,CurrentStage=0}

local store={ReadVariable=function(self,n)
  if n=="ff1/ready" then return ready end
  if n=="ff1/mem" then return mem end
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
  { id = 388, want = "@Cardia Forest Chests/Chests",      label = "Cardia Forest group" },
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

print(fail==0 and "\nALL PASS" or string.format("\n%d FAILURE(S)",fail))
os.exit(fail==0 and 0 or 1)
