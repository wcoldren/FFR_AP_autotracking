-- Minimal JSON reader for the test harness. Handles the subset the pack's
-- location files use, and tolerates the trailing commas PopTracker's own
-- parser accepts (locations/overworld.json has one).
local M = {}

local function skip(s, i)
  while true do
    local c = s:sub(i, i)
    if c == " " or c == "\t" or c == "\n" or c == "\r" then
      i = i + 1
    elseif c == "/" and s:sub(i + 1, i + 1) == "/" then
      i = (s:find("\n", i, true) or #s) + 1
    else
      return i
    end
  end
end

local parseValue

local function parseString(s, i)
  local out = {}
  i = i + 1
  while true do
    local c = s:sub(i, i)
    if c == '"' then
      return table.concat(out), i + 1
    elseif c == "\\" then
      local e = s:sub(i + 1, i + 1)
      local map = { n = "\n", t = "\t", r = "\r", b = "\b", f = "\f" }
      if e == "u" then
        out[#out + 1] = utf8.char(tonumber(s:sub(i + 2, i + 5), 16))
        i = i + 6
      else
        out[#out + 1] = map[e] or e
        i = i + 2
      end
    elseif c == "" then
      error("unterminated string")
    else
      out[#out + 1] = c
      i = i + 1
    end
  end
end

parseValue = function(s, i)
  i = skip(s, i)
  local c = s:sub(i, i)
  if c == "{" then
    local obj = {}
    i = skip(s, i + 1)
    if s:sub(i, i) == "}" then return obj, i + 1 end
    while true do
      i = skip(s, i)
      if s:sub(i, i) == "}" then return obj, i + 1 end   -- trailing comma
      local k
      k, i = parseString(s, i)
      i = skip(s, i) + 1                                  -- ':'
      obj[k], i = parseValue(s, i)
      i = skip(s, i)
      local d = s:sub(i, i)
      i = i + 1
      if d == "}" then return obj, i end
      if d ~= "," then error("expected , or } at " .. i) end
    end
  elseif c == "[" then
    local arr = {}
    i = skip(s, i + 1)
    if s:sub(i, i) == "]" then return arr, i + 1 end
    while true do
      i = skip(s, i)
      if s:sub(i, i) == "]" then return arr, i + 1 end     -- trailing comma
      local v
      v, i = parseValue(s, i)
      arr[#arr + 1] = v
      i = skip(s, i)
      local d = s:sub(i, i)
      i = i + 1
      if d == "]" then return arr, i end
      if d ~= "," then error("expected , or ] at " .. i) end
    end
  elseif c == '"' then
    return parseString(s, i)
  elseif s:sub(i, i + 3) == "true" then
    return true, i + 4
  elseif s:sub(i, i + 4) == "false" then
    return false, i + 5
  elseif s:sub(i, i + 3) == "null" then
    return nil, i + 4
  else
    local num = s:match("^-?%d+%.?%d*[eE]?[-+]?%d*", i)
    if not num or num == "" then error("bad value at " .. i .. ": " .. s:sub(i, i + 20)) end
    return tonumber(num), i + #num
  end
end

function M.decode(str)
  local v = parseValue(str, 1)
  return v
end

function M.load(path)
  local f = assert(io.open(path, "r"))
  local s = f:read("a")
  f:close()
  return M.decode(s)
end

return M
