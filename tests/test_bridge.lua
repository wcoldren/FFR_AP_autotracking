-- Load the bridge with stubbed emu/socket so the pure-Lua half runs offline.
local PACK = arg[1]

local logged = {}
local frameCb, resetCb = nil, nil
emu = {
  memType = { nesDebug = 0x100 },
  eventType = { endFrame = 3, reset = 4, stateLoaded = 7 },
  read = function(addr, t) return MEMORY and (MEMORY[addr] or 0) or 0 end,
  log = function(m) logged[#logged+1] = m end,
  displayMessage = function(c, m) end,
  addEventCallback = function(fn, ev)
    if ev == 3 then frameCb = fn elseif ev == 4 then resetCb = fn end
  end,
}

-- minimal socket stub: never accepts, so pump() just sits in listen state
local FAKE = {
  tcp = function()
    return {
      setoption=function() return 1 end,
      bind=function() return 1 end,
      listen=function() return 1 end,
      settimeout=function() return 1 end,
      accept=function() return nil, "timeout" end,
      close=function() end,
    }
  end,
}
package.preload["socket.core"] = function() return FAKE end

-- Load the file once so the adapter's require/callback wiring is exercised,
-- then load it a second time with the tail replaced by a return, to get at the
-- internals. They are locals by design; this is the least invasive way to
-- reach them without adding test-only exports to the shipped script.
assert(loadfile(PACK .. "/bridge/ffr_uat_bridge.lua"))()

local src = io.open(PACK .. "/bridge/ffr_uat_bridge.lua"):read("a")
local cut = src:find("\n-- EMULATOR ADAPTER", 1, true)
assert(cut, "adapter banner moved; update this harness")
local T = assert(load(src:sub(1, cut) .. [[
return {
  sha1 = sha1, b64encode = b64encode, wsAccept = wsAccept,
  wsEncodeText = wsEncodeText, wsEncodeControl = wsEncodeControl,
  wsDecode = wsDecode, clockText = clockText, TIMER_FPS = TIMER_FPS,
}
]], "bridge-internals"))()

local fail = 0
local function check(name, got, want)
  if got ~= want then
    print(string.format("FAIL %-44s\n  got  %s\n  want %s", name, tostring(got), tostring(want)))
    fail = fail + 1
  else
    print(string.format("ok   %-44s %s", name, tostring(got)))
  end
end
local function hex(s) return (s:gsub(".", function(c) return string.format("%02x", c:byte()) end)) end

-- SHA-1, RFC 3174 vectors
check("sha1('abc')", hex(T.sha1("abc")), "a9993e364706816aba3e25717850c26c9cd0d89d")
check("sha1('')", hex(T.sha1("")), "da39a3ee5e6b4b0d3255bfef95601890afd80709")
check("sha1(abcdbcde...)", hex(T.sha1("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq")),
  "84983e441c3bd26ebaae4aa1f95129e5e54670f1")
check("sha1(1M 'a') len", #T.sha1(string.rep("a", 1000000)), 20)
check("sha1(1M 'a')", hex(T.sha1(string.rep("a", 1000000))), "34aa973cd4c4daa4f61eeb2bdbad27316534016f")

-- base64
check("b64('')", T.b64encode(""), "")
check("b64('f')", T.b64encode("f"), "Zg==")
check("b64('fo')", T.b64encode("fo"), "Zm8=")
check("b64('foo')", T.b64encode("foo"), "Zm9v")
check("b64('foobar')", T.b64encode("foobar"), "Zm9vYmFy")

-- RFC 6455 section 1.3 worked example
check("ws accept (RFC 6455 example)", T.wsAccept("dGhlIHNhbXBsZSBub25jZQ=="), "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=")

-- frame encode: short, 16-bit extended, and the ~1KB flags payload path
local short = T.wsEncodeText("hi")
check("short frame header", string.format("%02x%02x", short:byte(1), short:byte(2)), "8102")
local mid = T.wsEncodeText(string.rep("x", 200))
check("200B frame uses 126 len", string.format("%02x%02x", mid:byte(1), mid:byte(2)), "817e")
check("200B frame extended len", string.unpack(">I2", mid, 3), 200)
check("200B total size", #mid, 4 + 200)

-- decode round-trip, unmasked
local op, pl, rest = T.wsDecode(T.wsEncodeText("hello"))
check("decode opcode", op, 0x1)
check("decode payload", pl, "hello")
check("decode leaves no rest", rest, "")

-- decode a MASKED client frame, which is what PopTracker actually sends
local function maskFrame(payload)
  local key = {0xDE, 0xAD, 0xBE, 0xEF}
  local out = {}
  for i = 1, #payload do out[i] = string.char(payload:byte(i) ~ key[((i-1)%4)+1]) end
  return string.pack(">BB", 0x81, 0x80 | #payload)
    .. string.char(key[1], key[2], key[3], key[4]) .. table.concat(out)
end
local sync = '[{"cmd":"Sync","slot":""}]'
local op2, pl2 = T.wsDecode(maskFrame(sync))
check("masked frame unmasks", pl2, sync)
check("Sync is detectable", pl2:find('"Sync"', 1, true) ~= nil, true)

-- incomplete frames must return nil, not crash or half-consume
check("truncated header -> nil", T.wsDecode("\129"), nil)
check("truncated payload -> nil", T.wsDecode(T.wsEncodeText("hello"):sub(1, 4)), nil)
check("truncated ext len -> nil", T.wsDecode(mid:sub(1, 3)), nil)

-- two frames back to back
local two = T.wsEncodeText("aaa") .. T.wsEncodeText("bbb")
local o1, p1, r1 = T.wsDecode(two)
local o2, p2, r2 = T.wsDecode(r1)
check("pipelined frame 1", p1, "aaa")
check("pipelined frame 2", p2, "bbb")
check("pipelined drained", r2, "")

-- control frames
local ping = T.wsEncodeControl(0x9, "pp")
local po, pp = T.wsDecode(ping)
check("ping opcode", po, 0x9)
check("ping payload", pp, "pp")

-- The run clock's readout. Frames rather than seconds, so these are exact
-- rather than approximate -- which is the point of counting frames.
local FPS = T.TIMER_FPS
check("zero frames", T.clockText(0), "0:00:00.00")
check("one frame", T.clockText(1), "0:00:00.02")
-- 120 frames of NTSC is 1.9967s. Truncating would read 0:00:01.99, which is
-- the wrong answer to "how long is two seconds of gameplay".
check("two seconds", T.clockText(120), "0:00:02.00")
check("one minute", T.clockText(math.floor(60 * FPS + 0.5)), "0:01:00.00")
-- No whole frame lands exactly on the hour -- 3600s is 216355.68 frames -- so
-- the rollover is asserted on the two frames either side of it rather than on
-- a round number that cannot occur.
check("last frame under the hour", T.clockText(216355), "0:59:59.99")
check("first frame past it", T.clockText(216356), "1:00:00.01")
check("a realistic run", T.clockText(math.floor((2*3600 + 40*60 + 54) * FPS + 0.5)),
  "2:40:54.00")
check("hours are not zero padded away", T.clockText(math.floor(10 * 3600 * FPS + 0.5)),
  "10:00:00.00")

print(fail == 0 and "\nALL PASS" or string.format("\n%d FAILURE(S)", fail))
os.exit(fail == 0 and 0 or 1)
