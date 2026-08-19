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
for _=1,60 do frameCb() end

-- pull the flags array straight off the wire
local blob=table.concat(sent)
-- the bridge sends a zeroed snapshot before the save is loaded, so take the
-- most recent flags var on the wire, not the first
local arr
for m in blob:gmatch('"ff1/flags","value":%[([^%]]+)%]') do arr=m end
assert(arr, "no flags var on the wire")
local flags={}
for v in arr:gmatch("[^,]+") do flags[#flags+1]=tonumber(v) end
local ready = blob:find('"ff1/ready","value":true',1,true)~=nil

-- now the pack side, fresh state
_G.emu=nil
local objects={}
Tracker={BulkUpdate=false,FindObjectForCode=function(self,c) return objects[c] end}
local captured
ScriptHost={AddVariableWatch=function(self,n,v,cb) captured={cb=cb} end}
AUTOTRACKER_ENABLE_DEBUG_LOGGING=false
dofile(PACK.."/scripts/autotracking/location_mapping.lua")
local counts,hosted={},{}
for id,v in pairs(LOCATION_MAPPING) do
  if v[1] then counts[v[1]]=(counts[v[1]] or 0)+1 end
  if v[2] then hosted[v[2]]=true end
end
for p,n in pairs(counts) do objects[p]={ChestCount=n,AvailableChestCount=n} end
for c in pairs(hosted) do objects[c]={Active=false} end
dofile(PACK.."/scripts/autotracking/reconcile.lua")
dofile(PACK.."/scripts/autotracking/uat.lua")

local store={ReadVariable=function(self,n)
  if n=="ff1/ready" then return ready end
  if n=="ff1/flags" then return flags end
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

-- replay the identical wire state: must not move anything
captured.cb(store)
check("replayed wire state is a no-op", objects[sec].AvailableChestCount, before-1)

-- and the AP feed reporting the same location must not double-clear
markAPChecked(299)
check("AP agreeing with UAT is a no-op", objects[sec].AvailableChestCount, before-1)

print(fail==0 and "\nALL PASS" or string.format("\n%d FAILURE(S)",fail))
os.exit(fail==0 and 0 or 1)
