-- Every Tracker.* / ScriptHost.* name the pack reaches for must actually exist
-- on that object in PopTracker.
--
-- The strict mocks in test_uat.lua only guard the scripts that file loads. This
-- reads the sources directly, so a wrong-object call anywhere in the pack is
-- caught even if no suite exercises that line -- which matters because every
-- call site is behind a `type(X.Method) ~= "function"` check, and a wrong object
-- makes that check quietly disable the feature instead of failing.
--
-- The whitelists live in tests/pop_api.lua, transcribed from doc/PACKS.md and
-- the Lua method tables in tracker.cpp / scripthost.cpp.

local PACK = arg[1]
local PopApi = dofile(PACK .. "/tests/pop_api.lua")

local fail = 0
local function check(name, got, want)
  if got ~= want then
    print(string.format("FAIL %-48s got=%s want=%s", name, tostring(got), tostring(want)))
    fail = fail + 1
  else
    print(string.format("ok   %-48s %s", name, tostring(got)))
  end
end

-- The scripts PopTracker actually runs. bridge/ runs under Mesen and has no
-- PopTracker globals at all, so it is deliberately out of scope.
local SOURCES = {
  "scripts/init.lua", "scripts/settings.lua", "scripts/logic.lua",
  "scripts/autotracking.lua",
  "scripts/autotracking/item_mapping.lua", "scripts/autotracking/location_mapping.lua",
  "scripts/autotracking/reconcile.lua", "scripts/autotracking/ram_mapping.lua",
  "scripts/autotracking/mapValues.lua", "scripts/autotracking/maptab.lua",
  "scripts/autotracking/uat.lua", "scripts/autotracking/flag_mapping.lua",
  "scripts/autotracking/flags_decode.lua",
  "scripts/flags/schemas.lua", "scripts/flags/schema_4-9-7.lua",
}

local GLOBALS = { Tracker = PopApi.TRACKER, ScriptHost = PopApi.SCRIPTHOST }

local bad, checked = {}, 0
for _, rel in ipairs(SOURCES) do
  local fh = assert(io.open(PACK .. "/" .. rel, "r"), "missing source: " .. rel)
  local lineno = 0
  for line in fh:lines() do
    lineno = lineno + 1
    -- Comments describe the host's API as often as they use it; skip them so a
    -- note like "it is ScriptHost:CreateLuaItem" is not read as a call.
    if not line:match("^%s*%-%-") then
      for global, allowed in pairs(GLOBALS) do
        -- %f[%w_] pins the match to a word boundary, so the "Tracker.json" inside
        -- a path like "layouts/NOverworld/shardsTracker.json" is not read as a
        -- member access.
        for name in line:gmatch("%f[%w_]" .. global .. "[%.:]([A-Za-z_][A-Za-z_0-9]*)") do
          checked = checked + 1
          if not allowed[name] then
            bad[#bad + 1] = string.format("%s:%d  %s.%s", rel, lineno, global, name)
          end
        end
      end
    end
  end
  fh:close()
end

for _, b in ipairs(bad) do print("     off-surface: " .. b) end
check("names checked", checked > 40, true)
check("every Tracker/ScriptHost name exists on that object", #bad, 0)

-- The specific mix-up that started this, kept as a named case so the whitelist
-- cannot be "fixed" by adding CreateLuaItem to Tracker.
check("CreateLuaItem is not a Tracker method", PopApi.TRACKER.CreateLuaItem, nil)
check("CreateLuaItem is a ScriptHost method", PopApi.SCRIPTHOST.CreateLuaItem, true)

print(fail == 0 and "\nALL PASS" or string.format("\n%d FAILURE(S)", fail))
os.exit(fail == 0 and 0 or 1)
