------------------------------------------------------------------
-- The seed's own flag string, decoded.
--
-- FFR stamps the flags it rolled with into the cartridge in plain ASCII, and
-- bridge/ffr_uat_bridge.lua publishes it as ff1/flags. This turns it back into
-- named settings. See tools/ffr_flags/README.md for the ROM offset and the
-- encoding; the short version is that the whole flag set is one big integer in
-- FFR's own base-64 alphabet, and decoding is one division per setting.
--
-- Lua has no big integers, so the value is carried as an array of base-64
-- digits, most significant first, and each step is a schoolbook long division.
-- The widest intermediate is the trailing SHA divisor (~7e16) times 64, which
-- is 4.5e18 -- inside a 64-bit signed integer, with room to spare.
--
-- FF1Lib mixes the seven-character build SHA in first, so it falls out last.
-- That is the checksum. A schema from a different FFR build leaves the trailing
-- characters as garbage and usually a remainder behind, and this refuses the
-- whole decode rather than reporting settings that are quietly shifted by one
-- property -- which would be worse than not reading them at all, because the
-- board would look configured.
------------------------------------------------------------------

local B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.-"

-- FF1Lib computes this as Math.Pow(0xFF, 7) - 1 in double precision and then
-- truncates it to a BigInteger, so it is the nearest double to 255^7 rather
-- than 255^7 - 1. Reproducing the rounding matters: the SHA check is only a
-- check if this divisor is the same one FFR used.
local SHA_DIVISOR = 70110209207109376

-- Populated by scripts/flags/schema_*.lua, keyed by version as the ROM spells
-- it ("4-9-7"). Generated files; see tools/ffr_flags/gen_schema.py.
FFR_FLAG_SCHEMAS = FFR_FLAG_SCHEMAS or {}

local DIGIT = {}
for i = 1, #B64 do
  DIGIT[B64:sub(i, i)] = i - 1
end

-- The flag string is written least significant digit first; long division wants
-- the other order.
local function toDigits(flagstring)
  local digits = {}
  local n = #flagstring
  for i = n, 1, -1 do
    local d = DIGIT[flagstring:sub(i, i)]
    if not d then
      return nil, string.format("%q is not FFR-style base64", flagstring:sub(i, i))
    end
    digits[n - i + 1] = d
  end
  return digits
end

-- Divide in place by radix and return the remainder, which is the next
-- setting's value. `first` is the index of the leading non-zero digit; it only
-- ever moves right, so the number shrinks as the decode goes and the later
-- divisions are cheap.
local function divmod(digits, first, radix)
  local rem = 0
  for i = first, #digits do
    local cur = rem * 64 + digits[i]
    digits[i] = cur // radix
    rem = cur % radix
  end
  while first < #digits and digits[first] == 0 do
    first = first + 1
  end
  return rem, first
end

local function isZero(digits, first)
  for i = first, #digits do
    if digits[i] ~= 0 then return false end
  end
  return true
end

-- Little-endian bytes, the way BigInteger.ToByteArray hands them to
-- Encoding.ASCII.GetString.
local function toAscii(value)
  local out = {}
  while value > 0 do
    out[#out + 1] = string.char(value & 0xFF)
    value = value >> 8
  end
  return table.concat(out)
end

-- Returns a table of setting name -> value, or nil and a reason.
--
-- Values are true/false for a bool, true/false/nil for a tri-state -- nil being
-- "left random, rolled at generation", which is not the same as off and must
-- not be treated as off -- and a number for an enum, int or double.
function decodeFFRFlags(version, flagstring)
  local schema = FFR_FLAG_SCHEMAS[version]
  if not schema then
    return nil, "no schema for FFR " .. tostring(version)
  end
  if type(flagstring) ~= "string" or flagstring == "" then
    return nil, "no flag string"
  end

  local digits, err = toDigits(flagstring)
  if not digits then
    return nil, err
  end

  local first = 1
  local flags = {}
  for _, entry in ipairs(schema.properties) do
    local raw
    raw, first = divmod(digits, first, entry.radix)
    local kind = entry.kind
    if kind == "tristate" then
      -- 2 is "random"; leave it nil so callers have to decide what unknown means.
      if raw == 0 then flags[entry.name] = false
      elseif raw == 1 then flags[entry.name] = true end
    elseif kind == "bool" then
      flags[entry.name] = raw ~= 0
    elseif kind == "enum" then
      flags[entry.name] = raw
    elseif kind == "int" or kind == "double" then
      flags[entry.name] = raw * entry.step + entry.min
    else
      return nil, "unknown kind " .. tostring(kind) .. " for " .. tostring(entry.name)
    end
  end

  local sha
  sha, first = divmod(digits, first, SHA_DIVISOR)
  sha = toAscii(sha)
  if sha ~= schema.build_sha then
    return nil, string.format("build sha came out %q, not %q -- wrong schema for this seed, or a damaged flag string",
                              sha, schema.build_sha)
  end
  if not isZero(digits, first) then
    return nil, "flag string has more in it than the schema accounts for"
  end

  return flags
end
