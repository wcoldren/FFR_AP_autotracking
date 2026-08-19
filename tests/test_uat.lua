local PACK = arg[1]
AUTOTRACKER_ENABLE_DEBUG_LOGGING = false

local objects = {}
Tracker = { BulkUpdate=false, FindObjectForCode=function(self,c) return objects[c] end }

local captured = nil
ScriptHost = { AddVariableWatch = function(self,n,vars,cb) captured = {n=n,vars=vars,cb=cb} end }

dofile(PACK .. "/scripts/autotracking/location_mapping.lua")
local counts, hosted = {}, {}
for id,v in pairs(LOCATION_MAPPING) do
  if v[1] then counts[v[1]]=(counts[v[1]] or 0)+1 end
  if v[2] then hosted[v[2]]=true end
end
for p,n in pairs(counts) do objects[p]={ChestCount=n,AvailableChestCount=n} end
for c in pairs(hosted) do objects[c]={Active=false} end

dofile(PACK .. "/scripts/autotracking/reconcile.lua")
dofile(PACK .. "/scripts/autotracking/uat.lua")

local fail=0
local function check(name,got,want)
  if got~=want then print(string.format("FAIL %-48s got=%s want=%s",name,tostring(got),tostring(want))); fail=fail+1
  else print(string.format("ok   %-48s %s",name,tostring(got))) end
end

check("watch registered", captured and captured.n, "ff1flags")
check("watches ff1/flags", captured.vars[1], "ff1/flags")
check("watches ff1/ready", captured.vars[2], "ff1/ready")

-- build a store stub
local function store(ready, flags)
  return { ReadVariable = function(self,name)
    if name=="ff1/ready" then return ready end
    if name=="ff1/flags" then return flags end
  end }
end
local function blank() local t={} for i=1,256 do t[i]=0 end return t end

-- not ready -> nothing happens
local f = blank()
f[1+0x2B] = 0x04                       -- byte 0x2B chest -> id 0x12B = 299
captured.cb(store(false, f))
local sec299 = LOCATION_MAPPING[299][1]
check("not ready leaves section alone", objects[sec299].AvailableChestCount, objects[sec299].ChestCount)

-- ready -> chest marked. AP id 299 is "Matoya's Cave - Chest 1" per worlds/ff1
captured.cb(store(true, f))
check("chest bit 0x04 on byte 0x2B marks id 299", objects[sec299].AvailableChestCount, objects[sec299].ChestCount-1)

-- idempotent: same state again
captured.cb(store(true, f))
check("same flags twice is a no-op", objects[sec299].AvailableChestCount, objects[sec299].ChestCount-1)

-- event bit on a mapped NPC byte: 0x04 -> id 0x204 = 516 (Bikke)
local f2 = blank()
f2[1+0x04] = 0x02
captured.cb(store(true, f2))
check("event bit on byte 0x04 sets Bikke hosted item", objects[LOCATION_MAPPING[516][2]].Active, true)
check("chest 299 released when flags cleared", objects[sec299].AvailableChestCount, objects[sec299].ChestCount)

-- goal bit: byte 0xFE bit 0x02 must NOT invent id 766
local f3 = blank()
f3[1+0xFE] = 0x02
captured.cb(store(true, f3))
check("goal bit does not invent id 766", LOCATION_MAPPING[766], nil)
local n=0 for _ in pairs(UAT_CHECKED) do n=n+1 end
check("goal-only frame checks nothing", n, 0)

-- chest bit on the same byte 0xFE IS a real location (0x1FE = 510)
local f4 = blank()
f4[1+0xFE] = 0x04 | 0x02
captured.cb(store(true, f4))
check("byte 0xFE chest bit marks id 510", UAT_CHECKED[510], true)
check("byte 0xFE event bit still ignored", UAT_CHECKED[766], nil)

-- sparse event bits on untracked bytes are silently ignored
local f5 = blank()
for _,b in ipairs({0x20,0x30,0x40,0x50}) do f5[1+b]=0x02 end
captured.cb(store(true, f5))
local n2=0 for _ in pairs(UAT_CHECKED) do n2=n2+1 end
check("untracked event bytes ignored", n2, 0)

print(fail==0 and "\nALL PASS" or string.format("\n%d FAILURE(S)",fail))
os.exit(fail==0 and 0 or 1)
