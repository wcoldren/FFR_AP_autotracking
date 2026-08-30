-- A stand-in for PopTracker's JsonItem that behaves like the real thing.
--
-- The naive version of this (a table with Active and CurrentStage fields) is
-- what let the turn-in stage bug through: it agreed with whatever the pack
-- code did instead of with PopTracker. The semantics below are transcribed
-- from src/core/jsonitem.{h,cpp}:
--
--   allow_disabled defaults to true                        (jsonitem.cpp:59)
--   inherit_codes  defaults to true                        (jsonitem.cpp:161)
--   progressive + allow_disabled gets a synthetic 0-stage, so the Lua-visible
--   CurrentStage is one above the stages[] index           (jsonitem.cpp:381, :473)
--   providesCode walks DOWN from the current stage while inherit_codes holds,
--   and yields nothing at all unless the item is active    (jsonitem.h:188-198)
--   initial_active_state starts a toggle switched ON, and is read for toggle,
--   toggle_badged and progressive_toggle only -- a plain progressive ignores
--   it entirely                                            (jsonitem.cpp:118-121)
local M = {}

local function splitCodes(s)
  local out = {}
  for c in tostring(s or ""):gmatch("[^,]+") do
    out[#out + 1] = c:match("^%s*(.-)%s*$")
  end
  return out
end

local function has(list, code)
  for _, c in ipairs(list) do
    if c == code then return true end
  end
  return false
end

-- def is a decoded entry from one of the pack's items/*.json files.
function M.new(def)
  local self = {
    progressive = def.type == "progressive",
    allowDisabled = def.allow_disabled ~= false,   -- default true
    codes = splitCodes(def.codes),
    stages = {},
    -- Off unless the item asks to start on, which only these three types may
    -- do; a "progressive" carrying the key is ignored, as PopTracker ignores it.
    stage1 = (def.type == "toggle" or def.type == "toggle_badged"
              or def.type == "progressive_toggle")
             and def.initial_active_state == true or false,
    stage2 = 0,                                     -- index into stages
  }
  for _, st in ipairs(def.stages or {}) do
    self.stages[#self.stages + 1] = {
      codes = splitCodes(st.codes),
      inherit = st.inherit_codes ~= false,          -- default true
    }
  end

  local proxy = {}
  return setmetatable(proxy, {
    __index = function(_, key)
      if key == "Active" then
        return self.stage1
      elseif key == "CurrentStage" then
        if self.progressive and self.allowDisabled then
          return self.stage1 and (self.stage2 + 1) or 0
        end
        return self.stage2
      elseif key == "providesCode" then
        return function(_, code)
          if #self.stages > self.stage2 then
            if self.allowDisabled and not self.stage1 then return 0 end
            for i = self.stage2, 0, -1 do
              local st = self.stages[i + 1]
              if st and has(st.codes, code) then return 1 end
              if not (st and st.inherit) then break end
            end
            return 0
          end
          if self.stage1 and has(self.codes, code) then return 1 end
          return 0
        end
      elseif key == "canProvideCode" then
        return function(_, code)
          if has(self.codes, code) then return true end
          for _, st in ipairs(self.stages) do
            if has(st.codes, code) then return true end
          end
          return false
        end
      elseif key == "_debug" then
        return { stage1 = self.stage1, stage2 = self.stage2, allowDisabled = self.allowDisabled }
      end
      return nil
    end,
    __newindex = function(_, key, val)
      if key == "Active" then
        if self.progressive and self.allowDisabled and not val then
          self.stage2 = 0
        elseif not self.allowDisabled then
          val = true
        end
        self.stage1 = val and true or false
      elseif key == "CurrentStage" then
        val = math.max(0, math.floor(val))
        local en = self.stage1
        if self.progressive and self.allowDisabled then
          if val == 0 then
            en, val = false, 0
          else
            en, val = true, val - 1
          end
        end
        if #self.stages > 0 and val >= #self.stages then
          val = #self.stages - 1
        end
        self.stage2, self.stage1 = val, en
      else
        rawset(proxy, key, val)
      end
    end,
  })
end

-- Loads every item the pack defines, keyed by every code it can provide.
function M.loadPack(json, PACK, files)
  local byCode, all = {}, {}
  for _, file in ipairs(files) do
    for _, def in ipairs(json.load(PACK .. "/" .. file)) do
      local item = M.new(def)
      all[#all + 1] = item
      for _, c in ipairs(splitCodes(def.codes)) do byCode[c] = item end
      for _, st in ipairs(def.stages or {}) do
        for _, c in ipairs(splitCodes(st.codes)) do
          if not byCode[c] then byCode[c] = item end
        end
      end
    end
  end
  return byCode, all
end

return M
