-- Drive the real bridge through a simulated PopTracker connection.
local PACK = arg[1]

MEMORY = {}
local sent, inbox = {}, ""
local frameCb, resetCb = nil, nil
local pendingClient = nil

local fakeClient = {
  settimeout=function() return 1 end,
  setoption=function() return 1 end,
  close=function() end,
  send=function(self, d) sent[#sent+1] = d; return #d end,
  receive=function(self, pat)
    local out = inbox; inbox = ""
    if #out == 0 then return nil, "timeout", "" end
    return nil, "timeout", out
  end,
}

local LOGS = {}
local scriptEndedCb = nil

-- What emu.getRomInfo() will answer. Set to nil to simulate a build that does
-- not provide it at all.
ROM_INFO = { name = "seedA.nes", path = "/roms/seedA.nes", fileSha1Hash = "sha-A" }

-- PRG ROM, addressed by file offset rather than through the CPU bus. Empty
-- until a test puts an FFRInfo record in it; a zeroed PRG is what a non-FFR
-- cartridge looks like.
PRGROM = {}

-- Write "FFRInfo|...|Flags: <flags>|Version: <version>" where FF1Lib puts it.
function putFlagRecord(version, flags)
  PRGROM = {}
  if not version then return end
  local record = "FFRInfo|Seed: DEADBEEF|OW Seed: none|Res. Pack Hash: none|Flags: "
      .. flags .. "|Version: " .. version .. "\0"
  for i = 1, #record do
    PRGROM[0x7BE00 + i - 1] = record:byte(i)
  end
end

emu = {
  memType = { nesDebug = 0x100, nesPrgRom = 0x101 },
  getRomInfo = function()
    if ROM_INFO == nil then error("getRomInfo unavailable") end
    return ROM_INFO
  end,
  -- Real ordinals, from the eventType enum in Mesen's embedded API docs:
  -- nmi, irq, startFrame, endFrame, reset, scriptEnded, inputPolled,
  -- stateLoaded, stateSaved, codeBreak. scriptEnded is 5; 9 is codeBreak.
  eventType = { endFrame = 3, reset = 4, scriptEnded = 5, stateLoaded = 7 },
  read = function(addr, t)
    if t == 0x101 then return PRGROM[addr] or 0 end
    return MEMORY[addr] or 0
  end,
  log = function(m) LOGS[#LOGS+1] = m end,
  displayMessage = function() end,
  addEventCallback = function(fn, ev)
    if ev == 3 then frameCb = fn
    elseif ev == 4 or ev == 7 then resetCb = fn
    elseif ev == 5 then scriptEndedCb = fn end
  end,
  -- The run clock's HUD. Every draw is captured so a test can assert on the
  -- text that would have been on screen that frame.
  drawSurface = { consoleScreen = 0, scriptHud = 1 },
  selectDrawSurface = function() end,
  getDrawSurfaceSize = function() return { width = 256, height = 240 } end,
  measureString = function(text) return 8 * #text end,
  drawString = function(x, y, text, fg, bg)
    DRAWN[#DRAWN+1] = { x = x, y = y, text = text, fg = fg, bg = bg }
  end,
}

-- Whatever the HUD drew, most recent last. Cleared by lastDrawn().
DRAWN = {}

-- Everything the bridge writes beside the ROM, captured in memory: the times
-- log it appends to, and the run clock's state file, which it truncates and
-- rewrites. Keyed on the /roms/ prefix rather than on the mode, so a real read
-- somewhere else in the harness still reaches the real filesystem.
FILES = {}
local realIo = io
io = setmetatable({
  open = function(path, mode)
    if type(path) ~= "string" or not path:find("^/roms/") then
      return realIo.open(path, mode)
    end
    if mode == "r" then
      if not FILES[path] then
        return nil, path .. ": no such file"
      end
      local text = FILES[path]
      return { read = function() return text end, close = function() end }
    end
    if mode == "w" then
      FILES[path] = ""
    end
    return {
      write = function(_, text) FILES[path] = (FILES[path] or "") .. text end,
      close = function() end,
    }
  end,
}, { __index = realIo })

-- Server-socket bookkeeping, for the bind-retry and shutdown cases.
local bindFails = false
local bindAttempts, serverClosed = 0, 0

package.preload["socket.core"] = function()
  return { tcp = function() return {
    setoption=function() return 1 end,
    bind=function()
      bindAttempts = bindAttempts + 1
      if bindFails then return nil, "address already in use" end
      return 1
    end,
    listen=function() return 1 end, settimeout=function() return 1 end,
    close=function() serverClosed = serverClosed + 1 end,
    accept=function() local c = pendingClient; pendingClient = nil
      if c then return c end; return nil, "timeout" end,
  } end }
end

assert(loadfile(PACK .. "/bridge/ffr_uat_bridge.lua"))()

local fail = 0
local function check(name, got, want)
  if got ~= want then print(string.format("FAIL %-46s got=%s want=%s", name, tostring(got), tostring(want))); fail=fail+1
  else print(string.format("ok   %-46s %s", name, tostring(got))) end
end
local function frames(n) for _=1,(n or 1) do frameCb() end end
local function allSent() local s = table.concat(sent); sent = {}; return s end
local function allLogs() local l = LOGS; LOGS = {}; return l end
local function logsMatching(logs, pat)
  local n = 0
  for _, l in ipairs(logs) do if l:find(pat, 1, true) then n = n + 1 end end
  return n
end
local TIMES = "/roms/ffr_times.log"
local function timesMatching(pat)
  local n = 0
  for line in (FILES[TIMES] or ""):gmatch("[^\n]+") do
    if line:find(pat, 1, true) then n = n + 1 end
  end
  return n
end

-- decode every text frame in a blob
local function textFrames(blob)
  local out = {}
  local i = 1
  while i <= #blob do
    local b1, b2 = blob:byte(i, i+1)
    if not b2 then break end
    local len = b2 & 0x7F
    local pos = i + 2
    if len == 126 then len = string.unpack(">I2", blob, i+2); pos = i + 4
    elseif len == 127 then len = string.unpack(">I8", blob, i+2); pos = i + 10 end
    out[#out+1] = blob:sub(pos, pos+len-1)
    i = pos + len
  end
  return out
end

-- 1. server comes up, no client
frames(1)
check("no output before a client", #allSent(), 0)

-- 2. client connects and sends the upgrade
pendingClient = fakeClient
frames(1)
inbox = "GET / HTTP/1.1\r\nHost: localhost:65399\r\nUpgrade: websocket\r\n"
     .. "Connection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
     .. "Sec-WebSocket-Version: 13\r\n"
     .. "Sec-WebSocket-Extensions: permessage-deflate\r\n\r\n"
frames(1)
local out = allSent()
check("replies 101", out:find("HTTP/1.1 101 Switching Protocols", 1, true) ~= nil, true)
check("correct accept key", out:find("s3pPLMBiTxaQ9kYGzzhZRbK+xOo=", 1, true) ~= nil, true)
check("declines permessage-deflate", out:lower():find("sec%-websocket%-extensions") == nil, true)
local body = out:sub((out:find("\r\n\r\n", 1, true)) + 4)
local msgs = textFrames(body)
check("sends Info unprompted", msgs[1] and msgs[1]:find('"cmd":"Info"', 1, true) ~= nil, true)
check("Info has protocol", msgs[1]:find('"protocol":0', 1, true) ~= nil, true)
check("Info advertises no slots", msgs[1]:find("slots", 1, true) == nil, true)

-- 3. Sync before a save is loaded -> ready must be false
local function clientSend(payload)
  local key = {1,2,3,4}
  local o = {}
  for i=1,#payload do o[i] = string.char(payload:byte(i) ~ key[((i-1)%4)+1]) end
  local hdr
  if #payload < 126 then hdr = string.pack(">BB", 0x81, 0x80 | #payload)
  else hdr = string.pack(">BBI2", 0x81, 0x80 | 126, #payload) end
  inbox = inbox .. hdr .. string.char(1,2,3,4) .. table.concat(o)
end
clientSend('[{"cmd":"Sync","slot":""}]')
frames(1)
local m = textFrames(allSent())
local joined = table.concat(m)
check("Sync answered", #m > 0, true)
check("ready false with no save", joined:find('"ff1/ready","value":false', 1, true) ~= nil, true)
check("Sync sends mem too", joined:find('"ff1/mem"', 1, true) ~= nil, true)
-- ff1/rom is what tells the pack it is looking at a different cartridge, and
-- it has to arrive before a save is loaded: that window -- ROM swapped, guard
-- unhappy -- is exactly when the old board needs dropping.
check("rom id sent while not ready", joined:find('"ff1/rom","value":"sha-A"', 1, true) ~= nil, true)

-- 4. load a save: guard byte nonzero, one chest opened at byte 0x2B
MEMORY[0x6102] = 0x41
MEMORY[0x6200 + 0x2B] = 0x04
frames(60)   -- past GUARD_STABLE_FRAMES (30) and several scan ticks
local j2 = table.concat(textFrames(allSent()))
check("ready flips true", j2:find('"ff1/ready","value":true', 1, true) ~= nil, true)
local arr
for m in j2:gmatch('"ff1/mem","value":%[([^%]]+)%]') do arr=m end
check("flags array present", arr ~= nil, true)
local vals = {}
for v in arr:gmatch("[^,]+") do vals[#vals+1] = tonumber(v) end
check("mem array is 768 long", #vals, 768)
check("flag byte 0x2B == 0x04", vals[0x200 + 0x2B + 1], 4)
check("mem byte 0x00 == 0", vals[1], 0)

-- 4b. the run clock starts with the first trusted scan, and lands in a file
--     beside the ROM -- the script log does not survive a Mesen restart.
check("run start recorded", timesMatching("  start  seedA.nes"), 1)
check("no goal line yet", timesMatching("  chaos  "), 0)

-- 5. no change -> nothing resent (the diff actually diffs)
frames(30)
check("idle sends nothing", #allSent(), 0)
check("start is not re-recorded while idle", timesMatching("  start  "), 1)

-- 6. another chest -> only the flags var moves
MEMORY[0x6200 + 0x30] = 0x04
frames(12)
local j3 = table.concat(textFrames(allSent()))
check("new chest resends mem", j3:find('"ff1/mem"', 1, true) ~= nil, true)
check("ready not resent unchanged", j3:find('"ff1/ready"', 1, true) == nil, true)

-- 7. goal bit
MEMORY[0x6200 + 0xFE] = 0x02
frames(12)
check("goal reported", table.concat(textFrames(allSent())):find('"ff1/goal","value":true', 1, true) ~= nil, true)
check("chaos time recorded", timesMatching("  chaos  seedA.nes"), 1)
frames(12)
check("chaos is recorded once, not per scan", timesMatching("  chaos  "), 1)

-- 8. hard reset: guard clears, ready must drop and NOT report an empty array
--    as a legitimate "everything unopened" state
resetCb()
MEMORY[0x6102] = 0
for a = 0x6200, 0x62FF do MEMORY[a] = 0 end
frames(12)
local j4 = table.concat(textFrames(allSent()))
check("reset drops ready", j4:find('"ff1/ready","value":false', 1, true) ~= nil, true)
local arr4 = j4:match('"ff1/mem","value":%[([^%]]+)%]')
check("reset does not wipe mem", arr4, nil)

-- 9. save reloaded: ready returns, previous chests still reported
MEMORY[0x6102] = 0x41
MEMORY[0x6200 + 0x2B] = 0x04
MEMORY[0x6200 + 0x30] = 0x04
frames(60)
local j5 = table.concat(textFrames(allSent()))
check("ready returns after reload", j5:find('"ff1/ready","value":true', 1, true) ~= nil, true)
-- The save guard drops on every battle and every reset, so `ready` flaps all
-- through normal play. The clock is latched per cartridge: a flap must not
-- restart the run or re-announce a goal already reached.
check("a reset does not restart the clock", timesMatching("  start  "), 1)
check("a reset does not re-record chaos", timesMatching("  chaos  "), 1)

-- 10. all-FF frame (power cycle garbage) is rejected
for a = 0x6200, 0x62FF do MEMORY[a] = 0xFF end
frames(12)
check("all-FF rejected", table.concat(textFrames(allSent())):find('"ff1/ready","value":false', 1, true) ~= nil, true)

-- 11. battle guard: $60FC == 0x0B / 0x0C must read as not-in-game
MEMORY[0x6102] = 0x41
for a = 0x6200, 0x62FF do MEMORY[a] = 0 end
MEMORY[0x6200 + 0x2B] = 0x04
frames(60)
allSent()
for _, bad in ipairs({0x0B, 0x0C}) do
  MEMORY[0x60FC] = bad
  frames(12)
  check(string.format("battle state 0x%02X drops ready", bad),
    table.concat(textFrames(allSent())):find('"ff1/ready","value":false', 1, true) ~= nil, true)
  MEMORY[0x60FC] = 0
  frames(60)
  allSent()
end

-- 12. the all-0xF2 reset-garbage pattern
MEMORY[0x6102], MEMORY[0x60FC], MEMORY[0x60A3] = 0xF2, 0xF2, 0xF2
frames(12)
check("all-F2 pattern drops ready",
  table.concat(textFrames(allSent())):find('"ff1/ready","value":false', 1, true) ~= nil, true)

-- 13. ff1/map. mapflags ($2D) bit 0 says we are in a standard map; cur_map
--     ($48) is the id. Off the overworld the id is stale, so the flag decides.
MEMORY[0x6102], MEMORY[0x60FC], MEMORY[0x60A3] = 0x41, 0, 0
for a = 0x6200, 0x62FF do MEMORY[a] = 0 end
MEMORY[0x6200 + 0x2B] = 0x04
MEMORY[0x002D], MEMORY[0x0048] = 0x00, 15    -- overworld, stale id
frames(60)
allSent()

MEMORY[0x002D], MEMORY[0x0048] = 0x01, 15    -- Ice Cave exit floor
frames(12)
check("entering a standard map publishes its id",
  table.concat(textFrames(allSent())):find('"ff1/map","value":15', 1, true) ~= nil, true)

MEMORY[0x002D] = 0x00                        -- back out to the overworld
frames(12)
check("leaving for the overworld publishes -1",
  table.concat(textFrames(allSent())):find('"ff1/map","value":-1', 1, true) ~= nil, true)

MEMORY[0x002D], MEMORY[0x0048] = 0x01, 15
frames(12)
allSent()

-- staying put must not resend it -- the pack re-activates a tab on every
-- change, so a chatty var would fight the user ten times a second
frames(30)
check("standing still does not resend map", #allSent(), 0)

MEMORY[0x0048] = 38                          -- walk down to the bottom floor
frames(12)
check("changing floor publishes the new id",
  table.concat(textFrames(allSent())):find('"ff1/map","value":38', 1, true) ~= nil, true)

-- an id outside the 61 standard maps is not something MAP_VALUE can name
MEMORY[0x0048] = 200
frames(12)
check("out-of-range id falls back to overworld",
  table.concat(textFrames(allSent())):find('"ff1/map","value":-1', 1, true) ~= nil, true)

-- and a reset must hold the last map rather than announce a move
MEMORY[0x002D], MEMORY[0x0048] = 0x01, 22
frames(12)
allSent()
resetCb()
MEMORY[0x6102] = 0
frames(12)
check("reset does not move the map",
  table.concat(textFrames(allSent())):find('"ff1/map"', 1, true) == nil, true)

-- 14. a partial write is a half-delivered frame, not a retryable nothing.
--     LuaSocket reports it as `nil, "timeout", n`, and the send diff has no
--     way to re-send a tail, so the connection has to go.
MEMORY[0x6102] = 0x41
frames(60)
allSent()
local closed = false
local realClose = fakeClient.close
fakeClient.close = function() closed = true end
fakeClient.send = function(self, d) sent[#sent+1] = d; return nil, "timeout", 5 end
MEMORY[0x6200 + 0x31] = 0x04                 -- something new to report
frames(12)
check("partial write closes the client", closed, true)

-- with the client gone nothing more goes out, however much state moves
fakeClient.close = realClose
fakeClient.send = function(self, d) sent[#sent+1] = d; return #d end
allSent()
MEMORY[0x6200 + 0x32] = 0x04
frames(12)
check("nothing sent after the drop", #allSent(), 0)

-- 15. PopTracker restarted mid-run. The fresh connection knows nothing, so
--     every var has to go out again -- including the map, which has not
--     changed value and would otherwise be diffed away.
pendingClient = fakeClient
frames(1)
inbox = "GET / HTTP/1.1\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
     .. "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n"
frames(13)
local blob = allSent()
local re = table.concat(textFrames(blob:sub((blob:find("\r\n\r\n", 1, true)) + 4)))
check("reconnect resends mem", re:find('"ff1/mem"', 1, true) ~= nil, true)
check("reconnect resends ready", re:find('"ff1/ready","value":true', 1, true) ~= nil, true)
check("reconnect resends the unchanged map", re:find('"ff1/map","value":22', 1, true) ~= nil, true)

-- 16. Mesen fires scriptEnded when it stops the script, which is what happens
--     on a power cycle before it starts a fresh one. Both sockets have to go
--     here: leaving the listening one to be collected is what makes the
--     restarted script lose the race for the port.
local clientClosed = false
local realClose = fakeClient.close
fakeClient.close = function() clientClosed = true end
allSent()
allLogs()
check("scriptEnded callback registered", type(scriptEndedCb), "function")
if type(scriptEndedCb) ~= "function" then scriptEndedCb = function() end end
scriptEndedCb()
local bye = allSent()
check("scriptEnded sends a close frame",
  #bye == 2 and bye:byte(1) == 0x88 and bye:byte(2) == 0x00, true)
check("scriptEnded closes the client", clientClosed, true)
check("scriptEnded closes the server", serverClosed > 0, true)
fakeClient.close = realClose

-- 17. the restarted script finds the port still held. It must keep trying,
--     but a per-frame retry would put sixty lines a second in the Script
--     Window, so failures back off and a streak says its piece once.
bindFails = true
bindAttempts = 0
MEMORY[0x6200 + 0x33] = 0x04                 -- state moves while we are down
frames(1)
check("nothing served after shutdown", #allSent(), 0)
check("first attempt is immediate", bindAttempts, 1)
check("bind failure logs once", logsMatching(allLogs(), "could not bind port"), 1)

frames(59)                                   -- inside the one-second backoff
check("no retry during the backoff", bindAttempts, 1)
check("and nothing logged either", #allLogs(), 0)

frames(2)                                    -- backoff expired
check("retries after the backoff", bindAttempts, 2)
check("the repeat does not log again", logsMatching(allLogs(), "could not bind port"), 0)

-- the port frees up: the next attempt takes, and says so exactly once
bindFails = false
frames(61)
check("bind eventually succeeds", bindAttempts, 3)
check("recovery is announced once", logsMatching(allLogs(), "listening for PopTracker"), 1)

-- and the server that came out of the retry path is a working one
pendingClient = fakeClient
frames(1)
inbox = "GET / HTTP/1.1\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
     .. "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n"
frames(1)
local back = allSent()
check("rebound server completes a handshake",
  back:find("HTTP/1.1 101 Switching Protocols", 1, true) ~= nil, true)
check("rebound server sends Info",
  table.concat(textFrames(back:sub((back:find("\r\n\r\n", 1, true)) + 4)))
    :find('"cmd":"Info"', 1, true) ~= nil, true)

------------------------------------------------------------------
-- ff1/rom over a live connection. The client from the retry case above is
-- connected and handshaked, so scan ticks reach the wire.
------------------------------------------------------------------
MEMORY[0x6102] = 0x41
for a = 0x6200, 0x62FF do MEMORY[a] = 0 end
MEMORY[0x6200 + 0x2B] = 0x04
frames(60)
allSent()

-- steady state: the id is diffed like everything else
frames(12)
check("rom id not resent when unchanged",
  table.concat(textFrames(allSent())):find('"ff1/rom"', 1, true) == nil, true)

-- the swap
ROM_INFO = { name = "seedB.nes", path = "/roms/seedB.nes", fileSha1Hash = "sha-B" }
frames(12)
check("a ROM swap is published",
  table.concat(textFrames(allSent())):find('"ff1/rom","value":"sha-B"', 1, true) ~= nil, true)

-- a build without the call, or one that throws, must degrade rather than take
-- the scan down with it -- "" is what the pack reads as "cannot tell"
ROM_INFO = nil
frames(12)
check("a failing getRomInfo degrades to empty",
  table.concat(textFrames(allSent())):find('"ff1/rom","value":""', 1, true) ~= nil, true)
MEMORY[0x6200 + 0x30] = 0x04
frames(12)
check("and the scan still runs",
  table.concat(textFrames(allSent())):find('"ff1/mem"', 1, true) ~= nil, true)

-- no hash, only a name: still an identity worth comparing
ROM_INFO = { name = "seedC.nes", path = "/roms/seedC.nes" }
frames(12)
check("falls back to the file name",
  table.concat(textFrames(allSent())):find('"ff1/rom","value":"seedC.nes"', 1, true) ~= nil, true)

------------------------------------------------------------------
-- 19. ff1/flags. FFR stamps the flag string it rolled with into PRG ROM, and
--     that is the only place the seed's settings exist -- Archipelago sends no
--     slot data for Final Fantasy and cart RAM holds progress, not settings.
--     Like ff1/rom this describes the cartridge, so it goes out whether or not
--     a save is loaded, and it is read once per cartridge rather than every
--     scan.
------------------------------------------------------------------
local SAMPLE = "g5jrLtdMmcv8HX6L"

ROM_INFO = { name = "seedD.nes", path = "/roms/seedD.nes", fileSha1Hash = "sha-D" }
putFlagRecord("4-9-7", SAMPLE)
frames(12)
check("the flag record is published",
  table.concat(textFrames(allSent())):find('"ff1/flags","value":"4-9-7|' .. SAMPLE .. '"', 1, true) ~= nil, true)

frames(12)
check("and not resent while the cartridge sits still",
  table.concat(textFrames(allSent())):find('"ff1/flags"', 1, true) == nil, true)

-- A new cartridge is a new record. The memo is keyed on the ROM id, so this is
-- also the check that a swap drops it.
ROM_INFO = { name = "seedE.nes", path = "/roms/seedE.nes", fileSha1Hash = "sha-E" }
putFlagRecord("4-9-7", "zzzzTOPHAT")
frames(12)
check("a swap republishes the flags",
  table.concat(textFrames(allSent())):find('"ff1/flags","value":"4-9-7|zzzzTOPHAT"', 1, true) ~= nil, true)
-- A different cartridge is a different run, so the clock restarts for it. The
-- times file is shared, hence the ROM name on every line.
check("a new cartridge starts its own run", timesMatching("  start  seedE.nes"), 1)
check("the finished seed keeps its own lines", timesMatching("  chaos  seedA.nes"), 1)

-- Anything that is not an FFR ROM, or an FFR build old enough to predate the
-- record, has to read as "cannot tell" rather than taking the scan down.
ROM_INFO = { name = "vanilla.nes", path = "/roms/vanilla.nes", fileSha1Hash = "sha-V" }
putFlagRecord(nil)
MEMORY[0x6200 + 0x31] = 0x04   -- something to make the mem diff fire
frames(12)
local blob = table.concat(textFrames(allSent()))
check("no record reads as empty", blob:find('"ff1/flags","value":""', 1, true) ~= nil, true)
check("a non-FFR cart still scans", blob:find('"ff1/mem"', 1, true) ~= nil, true)

------------------------------------------------------------------
-- The run clock.
--
-- Counted in emulated frames, so this suite can state exact times: frames(n)
-- calls the endFrame callback n times and that is the only clock involved. A
-- wall-clock timer could not be asserted on at all, which is a large part of
-- why the bridge counts frames -- the other part being that frames stop when
-- the emulator pauses, which is the only auto-pause Mesen's Lua API allows.
------------------------------------------------------------------

-- The state file is named after the cartridge rather than just parked in its
-- directory. Seeds share an output directory, so one shared file would have
-- each seed's checkpoint truncate the other seed's run -- and unlike
-- ffr_times.log, which is append-only with the ROM name on every line, this
-- one is rewritten in place.
local function timerFile(rom) return "/roms/ffr_timer." .. rom .. ".state" end

-- What the HUD has on screen right now. DRAWN is cleared before each
-- measurement rather than by reading, so a frame that drew nothing reads as
-- nil instead of quietly returning the previous instance's last draw.
local function shown()
  local d = DRAWN[#DRAWN]
  return d and d.text
end
local function csOf(text)
  local h, m, s, c = (text or ""):match("^(%d+):(%d%d):(%d%d)%.(%d%d)$")
  if not h then return nil end
  return (tonumber(h) * 3600 + tonumber(m) * 60 + tonumber(s)) * 100 + tonumber(c)
end
-- A reading back to the frame count that produced it. One NTSC frame is 1.66
-- hundredths, so no two frame counts round to the same reading and this inverse
-- is exact. Subtracting two *readings* would not be: each is rounded on its own
-- and the errors compound into a frame either way. The formatting itself is
-- asserted exactly in test_bridge.lua.
local function framesOf(text)
  local cs = csOf(text)
  if not cs then return nil end
  return math.floor((cs / 100) * 60.0988 + 0.5)        -- NES NTSC
end
local function framesBetween(before, after)
  local a, b = framesOf(before), framesOf(after)
  if not a or not b then return nil end
  return b - a
end
-- Advance n frames and report how many the clock thinks went by.
local function advance(n)
  local before = shown()
  DRAWN = {}
  frames(n)
  return framesBetween(before, shown())
end

-- A save that is mid-run does not start a run. seedA at the top of this file
-- was loaded with a chest already open at byte 0x2B, so the clock never armed
-- for it. Its state file exists by now -- the teardown at scriptEnded wrote one
-- -- so the thing to assert is what it says, which is "waiting" rather than
-- "running". Those have to be distinct: resuming a "running" clock starts it
-- ticking, and a run nobody began must not tick.
check("a mid-run save leaves the clock waiting",
  (FILES[timerFile("sha-A")] or ""):find("\twaiting\t", 1, true) ~= nil, true)
-- And it is seedA's own file. Five more cartridges have been through the slot
-- since, none of them touching this line.
check("the waiting clock names its own cartridge",
  (FILES[timerFile("sha-A")] or ""):find("^sha%-A\t") ~= nil, true)

-- A brand new game: the flag page back at lut_InitGameFlags, which is 0x01
-- almost everywhere -- visible objects, nothing opened and nobody talked to.
-- All-zero would read as uninitialised cart RAM and never be trusted at all.
ROM_INFO = { name = "seedF.nes", path = "/roms/seedF.nes", fileSha1Hash = "sha-F" }
putFlagRecord("4-9-7", "freshseed")
for i = 0, 0xFF do MEMORY[0x6200 + i] = 0x01 end
MEMORY[0x6102] = 0x41
frames(60)
check("a new game starts the clock", logsMatching(allLogs(), "run clock started"), 1)
check("the clock is checkpointed to disk",
  (FILES[timerFile("sha-F")] or ""):find("\trunning\t", 1, true) ~= nil, true)

DRAWN = {}
frames(1)
check("the clock is on screen", csOf(shown()) ~= nil, true)
check("120 frames advance it by 120", advance(120), 120)
check("and it keeps counting", advance(60), 60)

-- A soft reset drops the save guard but must not lose the run.
local beforeReset = shown()
resetCb()
DRAWN = {}
frames(60)
check("a reset does not zero the clock", framesBetween(beforeReset, shown()), 60)

-- The split is sampled every frame rather than on the 10Hz scan, so it lands
-- on the frame the flag flips rather than up to six frames later.
MEMORY[0x6200 + 0xFE] = 0x02
check("the goal frame is the last one counted", advance(1), 1)
local stopped = shown()
check("a stopped clock does not resume", advance(120), 0)
check("the final time is recorded", timesMatching("  clock  seedF.nes  " .. stopped), 1)
frames(120)
check("and recorded once, not per frame", timesMatching("  clock  "), 1)

-- Mesen restarts the script on a power cycle, so the clock has to come back off
-- disk -- and with PopTracker shut, since scan() never runs without a client.
-- Re-running the file gives a fresh set of locals and re-registers the
-- callbacks, which is what a restart looks like from in here.
-- The cartridge is re-read at the scan cadence, so give the restarted script
-- more than one tick to notice which seed it is looking at.
local savedState = FILES[timerFile("sha-F")]
assert(loadfile(PACK .. "/bridge/ffr_uat_bridge.lua"))()
DRAWN = {}
frames(12)
check("a restart resumes the run off disk", shown(), stopped)

-- ...but only for the cartridge the file names. The file name says that too
-- now, so this is the copied-or-renamed-by-hand case: seedF's line sitting in
-- seedG's file is still somebody else's run.
FILES[timerFile("sha-G")] = savedState
ROM_INFO = { name = "seedG.nes", path = "/roms/seedG.nes", fileSha1Hash = "sha-G" }
assert(loadfile(PACK .. "/bridge/ffr_uat_bridge.lua"))()
DRAWN = {}
frames(12)
check("another cartridge does not adopt it", shown(), "0:00:00.00")

-- Two seeds in one directory, which is how seeds actually sit on disk: an
-- evening spent alternating between them must not cost either one its clock.
-- The state file is truncated on every write, so a shared name would have
-- seedN's first checkpoint delete seedM's run outright.
local function loadCart(rom)
  ROM_INFO = { name = rom .. ".nes", path = "/roms/" .. rom .. ".nes", fileSha1Hash = rom }
  DRAWN = {}
  frames(12)
end
for i = 0, 0xFF do MEMORY[0x6200 + i] = 0x01 end
MEMORY[0x6102] = 0x41
loadCart("sha-M")
frames(120)                                  -- a short run on the first seed
local mFrames = framesOf(shown())
check("the first seed is running", mFrames > 0, true)
loadCart("sha-N")
frames(600)                                  -- a much longer one on the second
local nFrames = framesOf(shown())
check("the second seed runs its own clock", nFrames > mFrames + 300, true)
-- Back to the first seed. It resumes from its own last checkpoint, so it lands
-- a little behind where it was and nowhere near the second seed's time. With a
-- shared state file the second seed's line is all that is left, this cartridge
-- refuses to adopt it, and the flag page still reading new-game arms a *fresh*
-- run -- a clock that has quietly restarted rather than one that reads zero,
-- which is why the bound below is a checkpoint interval rather than nonzero.
loadCart("sha-M")
local mBack = framesOf(shown())
check("the first seed's clock survived the other seed",
  mBack >= 60 and mBack < mFrames, true)
check("both seeds have a file of their own",
  (FILES[timerFile("sha-M")] or ""):find("^sha%-M\t") ~= nil
  and (FILES[timerFile("sha-N")] or ""):find("^sha%-N\t") ~= nil, true)

-- A finished seed is not closed out for good. Practice runs, a second attempt
-- on race night, a reset after a bad start past the goal -- each is a new game
-- on a cartridge whose state file says "done", and each deserves a clock.
MEMORY[0x6200 + 0xFE] = 0x02
frames(2)
check("the replayed seed is finished for now", advance(60), 0)
for i = 0, 0xFF do MEMORY[0x6200 + i] = 0x01 end   -- start it again
allLogs()
frames(60)
check("a new game re-arms a finished clock", logsMatching(allLogs(), "run clock started"), 1)
check("and it is ticking again", advance(60), 60)

------------------------------------------------------------------
-- The restart gap.
--
-- A power cycle destroys the Lua state without firing scriptEnded, and Mesen
-- keeps emulating while the replacement script starts up. Those frames are
-- real run time and nothing counts them, so a resume adds the wall-clock gap
-- back -- bounded, because the same "script started and found a state file"
-- situation is also what closing Mesen and reopening it tomorrow looks like.
------------------------------------------------------------------

local function stateLine(rom, frameCount, state, stamp)
  return string.format("%s\t%d\t%s\t%d\n", rom, frameCount, state, stamp)
end
local function restartWith(rom, line)
  FILES[timerFile(rom)] = line
  ROM_INFO = { name = rom .. ".nes", path = "/roms/" .. rom .. ".nes", fileSha1Hash = rom }
  assert(loadfile(PACK .. "/bridge/ffr_uat_bridge.lua"))()
  DRAWN = {}
  frames(12)
  return framesOf(shown())
end

-- 600 frames banked, three seconds down: about 180 frames of NTSC come back,
-- plus the handful this harness itself advances before reading the HUD.
local short = restartWith("sha-H", stateLine("sha-H", 600, "running", os.time() - 3))
check("a power cycle's gap is added back", short >= 770 and short <= 800, true)

-- An hour is not a power cycle.
local long = restartWith("sha-I", stateLine("sha-I", 600, "running", os.time() - 3600))
check("an overnight gap is not", long >= 600 and long <= 615, true)

-- A run that already stopped does not gain time from either.
local done = restartWith("sha-J", stateLine("sha-J", 600, "done", os.time() - 3))
check("a finished run is never advanced", done, 600)

-- A cartridge seen but never started stays at zero rather than resuming into a
-- run nobody began.
local waiting = restartWith("sha-K", stateLine("sha-K", 0, "waiting", os.time() - 3))
check("a waiting clock does not start itself", waiting, 0)

-- The debounce is real run time, not overhead. The clock arms on the fifth
-- consecutive fresh-game read, six frames apart, so four scan intervals of
-- actual play go by first -- they used to be thrown away, and the clock is
-- advertised as exact at the split. Frame 30 is the arming scan and counts
-- itself, hence 25 rather than 24.
ROM_INFO = { name = "seedP.nes", path = "/roms/seedP.nes", fileSha1Hash = "sha-P" }
for i = 0, 0xFF do MEMORY[0x6200 + i] = 0x01 end
MEMORY[0x6102] = 0x41
assert(loadfile(PACK .. "/bridge/ffr_uat_bridge.lua"))()
DRAWN = {}
frames(30)
check("the debounce window is credited to the run", framesOf(shown()), 25)

-- The teardown write. It cannot be counted on for a power cycle, but a manual
-- stop does route through it, and it costs nothing to have.
for i = 0, 0xFF do MEMORY[0x6200 + i] = 0x01 end
MEMORY[0x6102] = 0x41
ROM_INFO = { name = "seedL.nes", path = "/roms/seedL.nes", fileSha1Hash = "sha-L" }
FILES[timerFile("sha-L")] = nil
assert(loadfile(PACK .. "/bridge/ffr_uat_bridge.lua"))()
frames(45)                       -- starts the clock, still short of a checkpoint
local beforeStop = FILES[timerFile("sha-L")]
scriptEndedCb()
check("the clock was not checkpointed yet", beforeStop ~= FILES[timerFile("sha-L")], true)
check("teardown wrote it",
  (FILES[timerFile("sha-L")] or ""):find("^sha%-L\t") ~= nil, true)

-- ...and a teardown before any cartridge has been adopted writes nothing at
-- all. A script stopped inside the first six frames used to leave a state file
-- named after the directory with an empty cartridge id on its line, which then
-- sat where a real seed's file belonged.
ROM_INFO = { name = "seedQ.nes", path = "/roms/seedQ.nes", fileSha1Hash = "sha-Q" }
local before = {}
for k, v in pairs(FILES) do before[k] = v end
assert(loadfile(PACK .. "/bridge/ffr_uat_bridge.lua"))()
frames(3)                        -- short of the first scan, so no cartridge yet
scriptEndedCb()
local wrote = 0
for k, v in pairs(FILES) do if before[k] ~= v then wrote = wrote + 1 end end
check("a teardown with no cartridge writes nothing", wrote, 0)

print(fail == 0 and "\nALL PASS" or string.format("\n%d FAILURE(S)", fail))
os.exit(fail == 0 and 0 or 1)
