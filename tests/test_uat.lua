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
dofile(PACK .. "/scripts/autotracking/ram_mapping.lua")
dofile(PACK .. "/scripts/autotracking/uat.lua")

local fail=0
local function check(name,got,want)
  if got~=want then print(string.format("FAIL %-48s got=%s want=%s",name,tostring(got),tostring(want))); fail=fail+1
  else print(string.format("ok   %-48s %s",name,tostring(got))) end
end

check("watch registered", captured and captured.n, "ff1mem")
check("watches ff1/mem", captured.vars[1], "ff1/mem")
check("watches ff1/ready", captured.vars[2], "ff1/ready")

-- build a store stub
local function store(ready, mem)
  return { ReadVariable = function(self,name)
    if name=="ff1/ready" then return ready end
    if name=="ff1/mem" then return mem end
  end }
end
-- 768-byte image; the flag array lives at offset 0x200, so flag byte B is
-- element 0x200 + B + 1. Everything below indexes through this helper so a
-- regression in the offset shows up as a test failure, not a silent miss.
local FLAGS_OFF = 0x200
local function blank() local t={} for i=1,768 do t[i]=0 end return t end
local function setflag(t, byte, val) t[FLAGS_OFF + byte + 1] = val end

-- not ready -> nothing happens
local f = blank()
setflag(f, 0x2B, 0x04)                       -- byte 0x2B chest -> id 0x12B = 299
captured.cb(store(false, f))
local sec299 = LOCATION_MAPPING[299][1]
check("not ready leaves section alone", objects[sec299].AvailableChestCount, objects[sec299].ChestCount)

-- ready -> chest marked. AP id 299 is "Matoya's Cave - Chest 1" per worlds/ff1
captured.cb(store(true, f))
check("chest bit 0x04 on byte 0x2B marks id 299", objects[sec299].AvailableChestCount, objects[sec299].ChestCount-1)

-- Same bit written at the WRONG offset (as if FLAGS_OFF were dropped) must do
-- nothing -- this is the off-by-0x200 guard for the ff1/mem migration.
local fwrong = blank()
fwrong[1 + 0x2B] = 0x04
captured.cb(store(true, fwrong))
check("bit at offset 0 is not a flag", objects[sec299].AvailableChestCount, objects[sec299].ChestCount)
captured.cb(store(true, f))

-- idempotent: same state again
captured.cb(store(true, f))
check("same flags twice is a no-op", objects[sec299].AvailableChestCount, objects[sec299].ChestCount-1)

-- event bit on a mapped NPC byte: 0x04 -> id 0x204 = 516 (Bikke)
local f2 = blank()
setflag(f2, 0x04, 0x02)
captured.cb(store(true, f2))
check("event bit on byte 0x04 sets Bikke hosted item", objects[LOCATION_MAPPING[516][2]].Active, true)
check("chest 299 released when flags cleared", objects[sec299].AvailableChestCount, objects[sec299].ChestCount)

-- goal bit: byte 0xFE bit 0x02 is Chaos, the same flag AP's client calls the
-- goal. It is a mapped event now, so it must check exactly id 766 and nothing
-- else -- the chest bit on the same byte is a different location.
local f3 = blank()
setflag(f3, 0xFE, 0x02)
captured.cb(store(true, f3))
check("goal bit is a mapped location", LOCATION_MAPPING[766] ~= nil, true)
check("goal bit checks id 766", UAT_CHECKED[766], true)
check("goal bit sets the chaos item", objects["chaos"].Active, true)
local n=0 for _ in pairs(UAT_CHECKED) do n=n+1 end
check("goal-only frame checks just the goal", n, 1)

-- chest bit on the same byte 0xFE IS a real location (0x1FE = 510)
local f4 = blank()
setflag(f4, 0xFE, 0x04 | 0x02)
captured.cb(store(true, f4))
check("byte 0xFE chest bit marks id 510", UAT_CHECKED[510], true)
check("byte 0xFE event bit marks id 766", UAT_CHECKED[766], true)

-- sparse event bits on untracked bytes are silently ignored
local f5 = blank()
for _,b in ipairs({0x20,0x30,0x40,0x50}) do f5[1+b]=0x02 end
captured.cb(store(true, f5))
local n2=0 for _ in pairs(UAT_CHECKED) do n2=n2+1 end
check("untracked event bytes ignored", n2, 0)

print(fail==0 and "\nALL PASS" or string.format("\n%d FAILURE(S)",fail))
os.exit(fail==0 and 0 or 1)
