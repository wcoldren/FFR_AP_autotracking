------------------------------------------------------------------
-- FF1R chest autotracking bridge: MesenCE -> PopTracker over UAT.
--
-- Mirrors Final Fantasy's location-flag array out of cart RAM and serves it
-- to PopTracker as UAT variables, so chests track with no Archipelago server
-- involved. Runs happily alongside an AP session; the two feeds are
-- reconciled inside the tracker pack.
--
-- SETUP
--   1. Mesen: Script -> Settings -> Script Window -> Restrictions.
--      Tick "Allow access to I/O and OS functions" FIRST, then
--      "Allow network access" (the second box only becomes real once the
--      first is ticked). Both default to off.
--   2. Load your ROM, then open this script in the Script Window and run it.
--      Or launch both from the command line -- see launch_mesen_ffr.sh.
--   3. In PopTracker, load the FFR pack and click the "UAT" label.
--
-- WHAT IT READS
--   Final Fantasy keeps its location flags in cart battery RAM. Per
--   worlds/ff1/Client.py in Archipelago, the array is at WRAM offset 0x200
--   length 0x100, which is CPU $6200-$62FF, and the save-loaded guard byte is
--   at offset 0x102 = CPU $6102. This script does not interpret those bits at
--   all -- it ships the raw bytes and lets the tracker pack decode them.
--
-- STRUCTURE
--   Everything above the "EMULATOR ADAPTER" banner is plain Lua plus
--   LuaSocket and knows nothing about Mesen. The adapter at the bottom is the
--   only emulator-aware part, so a BizHawk flavor is a swap of that block.
------------------------------------------------------------------

-- The whole live save working copy: vehicles and inventory at $6000, character
-- blocks at $6100, the object/chest flag array at $6200. This is the same
-- window the EmoTracker FFR pack watches (AddMemoryWatch 0x6000 len 0x300).
-- $6400-$67FF mirrors all of it but is only written when the player saves, so
-- it lags and is not what we read.
local MEM_ADDR = 0x6000
local MEM_LEN = 0x300
local FLAGS_OFF = 0x200     -- object/chest flag array, 256 bytes, within MEM
local FLAGS_LEN = 0x100
local GOAL_BYTE = 0xFE      -- bit 0x02 = Chaos defeated, the same flag
                            -- worlds/ff1/Client.py treats as the goal. The pack
                            -- does not read ff1/goal: byte 0xFE arrives inside
                            -- ff1/mem anyway, and Chaos is mapped there as an
                            -- ordinary event location (see location_mapping).
                            -- It is still published for any other UAT client.

-- Where the player is standing. These two live in work RAM rather than the
-- save window, so they are read on their own rather than out of MEM. Both come
-- from BenWenger's disassembly (variables.inc): mapflags bit 0 is set while in
-- a standard map, and cur_map is the standard-map id the tracker's MAP_VALUE
-- table is keyed by. On the overworld cur_map is stale, so the flag decides
-- whether it means anything.
local MAPFLAGS_ADDR = 0x002D
local CUR_MAP_ADDR = 0x0048
local MAP_OVERWORLD = -1    -- what we publish when not in a standard map

-- The seed's own flag string. FF1Rom.WriteSeedAndFlags stamps a plain-ASCII
-- record into bank 0x1E at 0xBE00, which is PRG offset 0x7BE00 -- PRG
-- addressing does not count the 16-byte iNES header, so this is 0x10 below the
-- file offset. It reads:
--
--   FFRInfo|Seed: D0E0CDBF|OW Seed: none|Res. Pack Hash: none|Flags: g5jr...|Version: 4-9-7
--
-- This is the only thing that tells anyone what the seed was rolled with: the
-- Archipelago FF1 world sends no slot data, and cart RAM holds progress, not
-- settings. See tools/ffr_flags/README.md.
local FLAGS_ROM_OFF = 0x7BE00
local FLAGS_ROM_LEN = 512   -- comfortably past the longest record
local FLAGS_MARKER = "FFRInfo"

-- In-game guard, matching worlds/ff1/Client.py and the EmoTracker pack's
-- isInGame(). All three bytes live inside MEM.
local GUARD_A_OFF = 0x102   -- first character's name; 0 = title / char creation
local GUARD_B_OFF = 0x0FC   -- 0x0B / 0x0C mean a battle is running
local GUARD_C_OFF = 0x0A3

local UAT_PORT = 65399      -- PopTracker's default; fallback is 44444
local SCAN_INTERVAL_FRAMES = 6   -- ~10Hz memory scan; sockets poll every frame
local GUARD_STABLE_SCANS = 5     -- consecutive scans, so ~0.5s of a valid save
                                 -- before reads are trusted

------------------------------------------------------------------
-- EMULATOR SEAM
-- The adapter at the bottom of this file fills these in.
------------------------------------------------------------------

local EMU = {
  readByte = nil,   -- function(addr) -> 0..255
  readRom = nil,    -- function(offset, len) -> string, nil when unsupported
  romId = nil,      -- function() -> string, "" when the emulator will not say
  log = nil,        -- function(msg)
  notify = nil,     -- function(msg)  on-screen
}

------------------------------------------------------------------
-- SHA-1 and base64, for the WebSocket handshake.
-- LuaSocket ships base64 in mime.core, but its chunked form needs a
-- finalizing call and we only ever encode 20 bytes, so it is cheaper to
-- inline both than to depend on those semantics.
------------------------------------------------------------------

local M32 = 0xFFFFFFFF

local function rol(x, n)
  x = x & M32
  return ((x << n) | (x >> (32 - n))) & M32
end

local function sha1(msg)
  local h0, h1, h2, h3, h4 = 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0
  local bitlen = #msg * 8
  msg = msg .. "\128"
  while (#msg % 64) ~= 56 do
    msg = msg .. "\0"
  end
  msg = msg .. string.pack(">I8", bitlen)

  local w = {}
  for chunk = 1, #msg, 64 do
    for j = 0, 15 do
      w[j] = string.unpack(">I4", msg, chunk + j * 4)
    end
    for j = 16, 79 do
      w[j] = rol(w[j - 3] ~ w[j - 8] ~ w[j - 14] ~ w[j - 16], 1)
    end

    local a, b, c, d, e = h0, h1, h2, h3, h4
    for j = 0, 79 do
      local f, k
      if j < 20 then
        f = (b & c) | ((~b & M32) & d)
        k = 0x5A827999
      elseif j < 40 then
        f = b ~ c ~ d
        k = 0x6ED9EBA1
      elseif j < 60 then
        f = (b & c) | (b & d) | (c & d)
        k = 0x8F1BBCDC
      else
        f = b ~ c ~ d
        k = 0xCA62C1D6
      end
      local temp = (rol(a, 5) + f + e + k + w[j]) & M32
      e = d
      d = c
      c = rol(b, 30)
      b = a
      a = temp
    end

    h0 = (h0 + a) & M32
    h1 = (h1 + b) & M32
    h2 = (h2 + c) & M32
    h3 = (h3 + d) & M32
    h4 = (h4 + e) & M32
  end

  return string.pack(">I4I4I4I4I4", h0, h1, h2, h3, h4)
end

local B64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

local function b64encode(data)
  local out = {}
  for i = 1, #data, 3 do
    local a, b, c = data:byte(i, i + 2)
    local n = (a << 16) | ((b or 0) << 8) | (c or 0)
    local s = B64_ALPHABET:sub(((n >> 18) & 63) + 1, ((n >> 18) & 63) + 1)
        .. B64_ALPHABET:sub(((n >> 12) & 63) + 1, ((n >> 12) & 63) + 1)
    if b then
      s = s .. B64_ALPHABET:sub(((n >> 6) & 63) + 1, ((n >> 6) & 63) + 1)
    else
      s = s .. "="
    end
    if c then
      s = s .. B64_ALPHABET:sub((n & 63) + 1, (n & 63) + 1)
    else
      s = s .. "="
    end
    out[#out + 1] = s
  end
  return table.concat(out)
end

------------------------------------------------------------------
-- WebSocket framing (RFC 6455). Server side: we send unmasked, the client
-- always masks.
------------------------------------------------------------------

local WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

local function wsAccept(key)
  return b64encode(sha1(key .. WS_GUID))
end

local function wsEncodeText(payload)
  local n = #payload
  if n < 126 then
    return string.pack(">BB", 0x81, n) .. payload
  elseif n < 65536 then
    return string.pack(">BBI2", 0x81, 126, n) .. payload
  end
  return string.pack(">BBI8", 0x81, 127, n) .. payload
end

local function wsEncodeControl(opcode, payload)
  payload = payload or ""
  return string.pack(">BB", 0x80 | opcode, #payload) .. payload
end

-- Pull one frame off the front of buf.
-- Returns opcode, payload, rest -- or nil when the frame is still incomplete.
local function wsDecode(buf)
  if #buf < 2 then
    return nil
  end
  local b1, b2 = buf:byte(1, 2)
  local opcode = b1 & 0x0F
  local masked = (b2 & 0x80) ~= 0
  local len = b2 & 0x7F
  local pos = 3

  if len == 126 then
    if #buf < 4 then return nil end
    len = string.unpack(">I2", buf, 3)
    pos = 5
  elseif len == 127 then
    if #buf < 10 then return nil end
    len = string.unpack(">I8", buf, 3)
    pos = 11
  end

  local mask
  if masked then
    if #buf < pos + 3 then return nil end
    mask = { buf:byte(pos, pos + 3) }
    pos = pos + 4
  end

  if #buf < pos + len - 1 then
    return nil
  end

  local payload = buf:sub(pos, pos + len - 1)
  if masked then
    local out = {}
    for i = 1, #payload do
      out[i] = string.char(payload:byte(i) ~ mask[((i - 1) % 4) + 1])
    end
    payload = table.concat(out)
  end

  return opcode, payload, buf:sub(pos + len)
end

------------------------------------------------------------------
-- Non-blocking server.
--
-- Every socket call is non-blocking and driven from the frame callback. A
-- blocking accept or receive would stall emulation, which is the failure mode
-- users report as "the script froze Mesen".
------------------------------------------------------------------

local socket = nil
local server, client = nil, nil
local rxbuf = ""
local handshaked = false

-- Bind retry. A power cycle restarts this script (see the scriptEnded note
-- below) and the previous instance's listening socket may not have been
-- released yet, so the first bind can lose the race. Retrying is right;
-- retrying sixty times a second and logging each attempt is not.
local BIND_RETRY_FRAMES = 60
local retryIn = 0
local bindFailure = nil     -- last failure text, so a streak logs once

local function closeClient(why)
  if client then
    pcall(function() client:close() end)
    client = nil
  end
  rxbuf = ""
  handshaked = false
  if why then
    EMU.log("client disconnected: " .. tostring(why))
  end
end

local function closeServer()
  if server then
    pcall(function() server:close() end)
    server = nil
  end
  retryIn = 0
  bindFailure = nil
end

-- Returns true on success, or false plus a message. Says nothing itself --
-- ensureServer decides what is worth logging.
local function createServer()
  local sock, err = socket.tcp()
  if not sock then
    return false, "socket.tcp failed: " .. tostring(err)
  end
  sock:setoption("reuseaddr", true)
  local ok
  ok, err = sock:bind("127.0.0.1", UAT_PORT)
  if not ok then
    pcall(function() sock:close() end)
    return false, "could not bind port " .. UAT_PORT .. ": " .. tostring(err)
  end
  ok, err = sock:listen(1)
  if not ok then
    pcall(function() sock:close() end)
    return false, "listen failed: " .. tostring(err)
  end
  sock:settimeout(0)
  server = sock
  return true
end

-- Called once a frame while there is no client. Holds off for a second
-- between failed attempts and logs one line per failure streak, so a port
-- that is briefly still held reads as one message rather than a wall of them.
-- The "listening" line on the way back out doubles as the recovery notice.
local function ensureServer()
  if server then
    return true
  end
  if retryIn > 0 then
    retryIn = retryIn - 1
    return false
  end
  local ok, err = createServer()
  if ok then
    bindFailure = nil
    EMU.log("listening for PopTracker on ws://127.0.0.1:" .. UAT_PORT)
    return true
  end
  retryIn = BIND_RETRY_FRAMES
  if err ~= bindFailure then
    bindFailure = err
    EMU.log(err .. " -- retrying once a second")
  end
  return false
end

local function tryAccept()
  local newClient, err = server:accept()
  if not newClient then
    if err ~= "timeout" then
      EMU.log("accept failed: " .. tostring(err))
    end
    return
  end
  client = newClient
  client:settimeout(0)
  client:setoption("tcp-nodelay", true)
  rxbuf = ""
  handshaked = false
end

local function send(data)
  if not client then
    return false
  end
  local sent, err, lastByte = client:send(data)
  if not sent then
    -- A non-blocking send reports a partial write as `nil, "timeout", n`, so
    -- a timeout here is not "nothing happened" -- it is a frame left half on
    -- the wire. Treat it as fatal for this connection rather than trying to
    -- resume mid-frame: sendState has no way to re-send a tail, and a client
    -- holding half a frame would parse the next one as its remainder. The
    -- reconnect costs a Sync, which restores the whole state anyway.
    if err == "timeout" then
      closeClient(string.format("partial write, %d of %d bytes",
        tonumber(lastByte) or 0, #data))
    else
      closeClient(err)
    end
    return false
  end
  return true
end

-- Mesen stops this script and starts a fresh one on a power cycle (Script
-- Window -> Settings -> "Auto-restart script after power cycle", on by
-- default), and fires scriptEnded on the way out. Releasing the port here
-- rather than leaving it to the dying Lua state being collected is what lets
-- the restarted script bind first time. The close frame is a courtesy: it
-- tells PopTracker to drop us now instead of noticing a bare FIN.
local function shutdown()
  if client then
    send(wsEncodeControl(0x8))
  end
  closeClient()
  closeServer()
end

------------------------------------------------------------------
-- UAT protocol.
--
-- Each message is a JSON array of command objects. PopTracker expects the
-- server to send Info unprompted on connect and drops the connection if it
-- has not arrived within 5s; it then replies with Sync, and we answer with
-- Var messages. We advertise no slots, so PopTracker uses the empty slot and
-- matches Vars that carry no slot of their own.
------------------------------------------------------------------

local INFO_MSG =
  '[{"cmd":"Info","protocol":0,"name":"FF1R Mesen Bridge","version":"1.0.0"}]'

-- Last state actually put on the wire, for diffing.
local sentMem, sentReady, sentGoal, sentMap, sentRom, sentFlags =
    nil, nil, nil, nil, nil, nil

local function varMem(mem)
  local parts = {}
  for i = 1, MEM_LEN do
    parts[i] = tostring(mem:byte(i))
  end
  return '{"cmd":"Var","name":"ff1/mem","value":[' .. table.concat(parts, ",") .. "]}"
end

local function varBool(name, value)
  return '{"cmd":"Var","name":"' .. name .. '","value":' .. tostring(value) .. "}"
end

local function varNum(name, value)
  return '{"cmd":"Var","name":"' .. name .. '","value":' .. string.format("%d", value) .. "}"
end

-- Both strings we publish -- the ROM id and the flag record -- are escaped.
-- The flag record cannot contain anything that needs it, but the ROM id can:
-- emu.getRomInfo() falls back to the file name on a build that does not hash,
-- and a quote or a backslash in that would produce a malformed frame.
local function varStr(name, value)
  local escaped = tostring(value):gsub('[\\"]', '\\%0'):gsub("%c", "")
  return '{"cmd":"Var","name":"' .. name .. '","value":"' .. escaped .. '"}'
end

local function sendState(mem, ready, goal, map, rom, flags, force)
  local msgs = {}
  if force or mem ~= sentMem then
    msgs[#msgs + 1] = varMem(mem)
  end
  if force or ready ~= sentReady then
    msgs[#msgs + 1] = varBool("ff1/ready", ready)
  end
  if force or goal ~= sentGoal then
    msgs[#msgs + 1] = varBool("ff1/goal", goal)
  end
  if force or map ~= sentMap then
    msgs[#msgs + 1] = varNum("ff1/map", map)
  end
  -- Sent whatever ff1/ready says. This is which cartridge is in the slot, not
  -- game state, and the pack needs it before the save-loaded guard passes --
  -- that is the whole window in which a ROM swap has to be noticed.
  if force or rom ~= sentRom then
    msgs[#msgs + 1] = varStr("ff1/rom", rom)
  end
  -- Same reasoning as ff1/rom: this describes the cartridge, not the save, so
  -- it goes out whether or not a save is loaded. The pack needs it to configure
  -- its flag grid before there is any progress to show.
  if force or flags ~= sentFlags then
    msgs[#msgs + 1] = varStr("ff1/flags", flags)
  end
  if #msgs == 0 then
    return
  end
  if send(wsEncodeText("[" .. table.concat(msgs, ",") .. "]")) then
    sentMem, sentReady, sentGoal, sentMap, sentRom, sentFlags =
        mem, ready, goal, map, rom, flags
  end
end

------------------------------------------------------------------
-- Game state: read, guard, diff.
--
-- The guard mirrors what the Archipelago client does. worlds/ff1/Client.py
-- reads the same byte at 0x102 and refuses every read and write while it is
-- zero, because that means the title screen or character creation rather than
-- a loaded save. We additionally require it to hold steady for a while, and
-- treat an all-00 or all-FF array as untrustworthy, so a reset or a
-- power-cycle cannot flush through as "every chest just became unopened".
------------------------------------------------------------------

local guardValue, guardScans = nil, 0
local lastMem = string.rep("\0", MEM_LEN)
local lastGoal = false
local lastMap = MAP_OVERWORLD
local lastRom = ""
local lastFlags = ""

-- Which cartridge is in the slot. The pack uses this to notice that it is
-- looking at a different game and drop the previous one's board -- without it,
-- raise-only state (orbs, key items, turn-ins, hosted codes) carries across a
-- ROM swap and the tracker keeps showing the seed you just finished.
--
-- Re-read every scan rather than cached once: loading another ROM does not
-- always tear down the Lua state, and when it does not, a cached value would
-- report the old cartridge forever. It is a table lookup, not a memory sweep.
local function readRom()
  if not EMU.romId then
    return ""
  end
  local ok, id = pcall(EMU.romId)
  if not ok or type(id) ~= "string" then
    return ""
  end
  return id
end

-- The flag record, as "<version>|<flagstring>", or "" when it cannot be read.
--
-- Memoised on the cartridge id, because unlike the RAM mirror this cannot
-- change while a ROM is loaded -- and re-reading 512 bytes of PRG ten times a
-- second to watch a constant would be silly. A swap changes the id, which
-- drops the memo.
local flagsFor, flagsValue = nil, ""
local flagsWarned = false

local function readFlags(rom)
  if flagsFor == rom then
    return flagsValue
  end
  flagsFor, flagsValue = rom, ""

  if not EMU.readRom then
    return flagsValue
  end
  local ok, raw = pcall(EMU.readRom, FLAGS_ROM_OFF, FLAGS_ROM_LEN)
  if not ok or type(raw) ~= "string" then
    if not flagsWarned then
      flagsWarned = true
      EMU.log("cannot read PRG ROM -- the flag grid stays manual")
    end
    return flagsValue
  end

  -- Only the documented offset. A wider search would mean sweeping half a
  -- megabyte a byte at a time, and every FFR build that writes this record at
  -- all writes it here.
  if raw:sub(1, #FLAGS_MARKER) ~= FLAGS_MARKER then
    EMU.log("no FFRInfo record at 0x" .. string.format("%X", FLAGS_ROM_OFF)
            .. " -- not an FFR ROM, or too old a build")
    return flagsValue
  end

  local record = raw:match("^[^%z]*")
  local flags = record:match("|Flags: ([A-Za-z0-9%.%-]+)")
  local version = record:match("|Version: ([A-Za-z0-9%.%-]+)")
  if not flags or not version then
    EMU.log("FFRInfo record has no Flags/Version field")
    return flagsValue
  end

  flagsValue = version .. "|" .. flags
  EMU.log("seed flags: FFR " .. version .. ", " .. #flags .. " characters")
  return flagsValue
end

local function readMem()
  local bytes = {}
  for i = 0, MEM_LEN - 1 do
    bytes[i + 1] = string.char(EMU.readByte(MEM_ADDR + i) & 0xFF)
  end
  return table.concat(bytes)
end

-- 1-based byte at a MEM offset.
local function at(mem, off)
  return mem:byte(off + 1)
end

local function flagsOf(mem)
  return mem:sub(FLAGS_OFF + 1, FLAGS_OFF + FLAGS_LEN)
end

-- The flag array initialises to 0x01 almost everywhere, so all-00 is never a
-- state the game produces; all-FF is uninitialised cart RAM.
local function looksUninitialised(mem)
  local flags = flagsOf(mem)
  return flags == string.rep("\0", FLAGS_LEN) or flags == string.rep("\255", FLAGS_LEN)
end

local function inGame(mem)
  local a, b, c = at(mem, GUARD_A_OFF), at(mem, GUARD_B_OFF), at(mem, GUARD_C_OFF)
  if a == 0 then
    return false                      -- title screen or character creation
  end
  if b == 0x0B or b == 0x0C then
    return false                      -- battle in progress
  end
  if a == 0xF2 and b == 0xF2 and c == 0xF2 then
    return false                      -- known garbage pattern during resets
  end
  return true
end

-- Called on reset / state load: drop trust immediately, so nothing that
-- happens during the reset window reaches the tracker.
local function invalidate()
  guardValue, guardScans = nil, 0
end

local function isReady()
  return guardScans >= GUARD_STABLE_SCANS
end

-- Which map the player is on, or MAP_OVERWORLD. Only meaningful once the save
-- guard is happy, so scan() holds the last value rather than reading this while
-- the game is mid-reset.
local function readMap()
  local flags = EMU.readByte(MAPFLAGS_ADDR)
  if not flags or (flags & 0x01) == 0 then
    return MAP_OVERWORLD
  end
  local id = EMU.readByte(CUR_MAP_ADDR)
  if not id or id > 60 then
    return MAP_OVERWORLD
  end
  return id
end

local function scan()
  local mem = readMem()
  lastRom = readRom()
  lastFlags = readFlags(lastRom)

  if not inGame(mem) or looksUninitialised(mem) then
    invalidate()
    sendState(lastMem, false, lastGoal, lastMap, lastRom, lastFlags)
    return
  end

  -- Require the party marker to hold steady for a few scans before trusting
  -- anything, so a reset cannot flush a half-initialised frame through.
  local guard = at(mem, GUARD_A_OFF)
  if guard ~= guardValue then
    guardValue = guard
    guardScans = 1
  elseif guardScans < GUARD_STABLE_SCANS then
    guardScans = guardScans + 1
  end

  if not isReady() then
    sendState(lastMem, false, lastGoal, lastMap, lastRom, lastFlags)
    return
  end

  lastMem = mem
  lastGoal = (at(mem, FLAGS_OFF + GOAL_BYTE) & 0x02) ~= 0
  lastMap = readMap()
  sendState(lastMem, true, lastGoal, lastMap, lastRom, lastFlags)
end

------------------------------------------------------------------
-- Connection pump.
------------------------------------------------------------------

local function handleHandshake()
  local headEnd = rxbuf:find("\r\n\r\n", 1, true)
  if not headEnd then
    return
  end
  local head = rxbuf:sub(1, headEnd + 1)
  rxbuf = rxbuf:sub(headEnd + 4)

  local key = head:match("[Ss]ec%-[Ww]eb[Ss]ocket%-[Kk]ey:%s*([^\r\n]+)")
  if not key then
    closeClient("handshake had no Sec-WebSocket-Key")
    return
  end

  -- Deliberately no Sec-WebSocket-Extensions in the reply: declining
  -- permessage-deflate keeps every frame plain, which is the whole reason
  -- this file needs no compression code.
  local response = "HTTP/1.1 101 Switching Protocols\r\n"
      .. "Upgrade: websocket\r\n"
      .. "Connection: Upgrade\r\n"
      .. "Sec-WebSocket-Accept: " .. wsAccept(key) .. "\r\n\r\n"
  if not send(response) then
    return
  end

  handshaked = true
  sentMem, sentReady, sentGoal, sentMap, sentRom, sentFlags =
      nil, nil, nil, nil, nil, nil
  -- A client can connect and Sync before the first scan tick, and the very
  -- first thing it needs is which cartridge this is.
  lastRom = readRom()
  lastFlags = readFlags(lastRom)
  EMU.log("PopTracker connected")
  EMU.notify("PopTracker connected")
  send(wsEncodeText(INFO_MSG))
end

local function handleFrames()
  while client do
    local opcode, payload, rest = wsDecode(rxbuf)
    if not opcode then
      return
    end
    rxbuf = rest

    if opcode == 0x8 then
      send(wsEncodeControl(0x8))
      closeClient("client closed")
      return
    elseif opcode == 0x9 then
      send(wsEncodeControl(0xA, payload))
    elseif opcode == 0x1 then
      -- Sync is the only command that matters to us, and a full-state reply
      -- is correct for it, so match on the name rather than carrying a JSON
      -- parser for one string.
      if payload:find('"Sync"', 1, true) then
        sendState(lastMem, isReady(), lastGoal, lastMap, lastRom, lastFlags, true)
      end
    end
  end
end

local function pump()
  if not client then
    if ensureServer() then
      tryAccept()
    end
    return
  end

  local data, err, partial = client:receive("*a")
  local chunk = data or partial
  if chunk and #chunk > 0 then
    rxbuf = rxbuf .. chunk
  end
  if err and err ~= "timeout" then
    closeClient(err)
    return
  end

  if not handshaked then
    handleHandshake()
  end
  if handshaked then
    handleFrames()
  end
end

------------------------------------------------------------------
-- EMULATOR ADAPTER (Mesen)
-- The only emulator-aware code in this file.
------------------------------------------------------------------

local ok, sock = pcall(require, "socket.core")
if not ok then
  emu.log("ERROR: could not load socket.core: " .. tostring(sock))
  emu.log("Enable Script -> Settings -> Script Window -> Restrictions ->")
  emu.log("  'Allow access to I/O and OS functions' AND 'Allow network access',")
  emu.log("  then reload this script.")
  error("socket.core unavailable")
end
socket = sock

-- nesDebug is the NES CPU bus with side effects suppressed, so $6200 and
-- $6102 are read directly and it makes no difference whether the cart's
-- $6000 space is backed by work RAM or save RAM.
local MEM = emu.memType.nesDebug

EMU.readByte = function(addr)
  return emu.read(addr, MEM)
end
-- PRG ROM, addressed by offset into the file's PRG area rather than through the
-- CPU bus -- the flag record lives in bank 0x1E, which is not the bank mapped at
-- $8000 most of the time. Read once per cartridge, so the byte-at-a-time loop
-- costs nothing worth optimising away.
local PRG = emu.memType.nesPrgRom

EMU.readRom = function(offset, len)
  if not PRG then
    return nil
  end
  local bytes = {}
  for i = 0, len - 1 do
    local b = emu.read(offset + i, PRG)
    if type(b) ~= "number" then
      return nil
    end
    bytes[i + 1] = string.char(b & 0xFF)
  end
  return table.concat(bytes)
end
-- emu.getRomInfo() -> { name, path, fileSha1Hash }. The hash is the identity we
-- want; the name is a usable stand-in on a build that does not provide it, and
-- "" means "cannot tell", which the pack reads as "do not reset".
EMU.romId = function()
  local ok, info = pcall(emu.getRomInfo)
  if not ok or type(info) ~= "table" then
    return ""
  end
  local id = info.fileSha1Hash or info.name
  return type(id) == "string" and id or ""
end
EMU.log = function(msg)
  emu.log("[ffr-uat] " .. msg)
end
EMU.notify = function(msg)
  emu.displayMessage("FFR UAT", msg)
end

local frame = 0

local function onFrame()
  frame = frame + 1
  local okPump, errPump = pcall(pump)
  if not okPump then
    EMU.log("pump error: " .. tostring(errPump))
    closeClient("internal error")
  end
  if client and handshaked and (frame % SCAN_INTERVAL_FRAMES == 0) then
    local okScan, errScan = pcall(scan)
    if not okScan then
      EMU.log("scan error: " .. tostring(errScan))
    end
  end
end

emu.addEventCallback(onFrame, emu.eventType.endFrame)
emu.addEventCallback(invalidate, emu.eventType.reset)
emu.addEventCallback(invalidate, emu.eventType.stateLoaded)
-- pcall'd like the frame callback: this runs while the script is being torn
-- down, and a Lua error here would surface as a stop-time error dialog rather
-- than anything useful.
emu.addEventCallback(function() pcall(shutdown) end, emu.eventType.scriptEnded)

EMU.log("ready -- waiting for PopTracker on ws://127.0.0.1:" .. UAT_PORT)
