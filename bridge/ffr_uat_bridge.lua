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

-- Wall-clock markers for a run, appended to a file next to the ROM. Nothing
-- else on the machine can answer "how long did that seed take": FF1 keeps no
-- play-time counter in SRAM, FFR adds no timer flag, Mesen does not track time
-- per game, and the script log window is gone the moment Mesen restarts. One
-- line per event with an absolute timestamp. A seed played over several
-- sittings leaves one `start` line per sitting and a single `chaos` line, so
-- the elapsed total is the last stamp minus the first.
local TIMES_FILE = "ffr_times.log"

-- The run clock, kept beside the ROM so a seed picked up tomorrow resumes
-- rather than restarting. One line, rewritten in place rather than appended.
local TIMER_FILE = "ffr_timer.state"

-- Frames to seconds. The Lua API reports no frame rate, so this is the NES
-- NTSC figure written down; a PAL cartridge would want 50.007.
local TIMER_FPS = 60.0988
-- How often the clock is written down, and how much a power cycle can cost.
-- A power cycle destroys the Lua state through ~Debugger -> ~ScriptManager,
-- which -- unlike ScriptManager::RemoveScript -- emits no scriptEnded, so the
-- teardown hook cannot be relied on to get a last write in. The checkpoint
-- interval is therefore the real bound on what a hard reset loses, and one
-- second of a run is worth more than one small file write per second.
local TIMER_SAVE_FRAMES = 60

-- How long a gap the clock will bridge when it resumes. A power cycle has the
-- script back in well under this; anything longer is the emulator having been
-- closed, and that time is not part of the run.
local TIMER_RESUME_MAX_SECONDS = 15

-- ARGB, matching the pairing Mesen's own bundled example script uses.
local TIMER_FG_RUNNING = 0xFFFFFF
local TIMER_FG_DONE = 0x7CFC7C
local TIMER_BG = 0xFF000000
local TIMER_MARGIN = 4

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
  romPath = nil,    -- function() -> string, nil when the emulator will not say
  appendFile = nil, -- function(path, text) -> ok, err
  writeFile = nil,  -- function(path, text) -> ok, err   truncating, for state
  readFile = nil,   -- function(path) -> string, nil when there is no such file
  drawText = nil,   -- function(text, done) one frame's worth of HUD, nil when
                    -- the emulator cannot draw
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

------------------------------------------------------------------
-- Run timing. Two markers: the first scan this sitting that the save guard
-- trusts, and the moment the goal flag appears.
------------------------------------------------------------------

local timedRom = nil        -- the cartridge the two below belong to
local runStart = nil        -- os.time() of the first trusted scan this sitting
local goalRecorded = false
local timesWarned = false

-- The ROM's own directory, so a seed's files land beside the seed. Both
-- separators, because the path comes from the emulator rather than from us.
-- Returns the full path and the cartridge's file name.
local function besideRom(name)
  if not EMU.romPath then
    return nil
  end
  local ok, romPath = pcall(EMU.romPath)
  if not ok or type(romPath) ~= "string" then
    return nil
  end
  local dir, sep = romPath:match("^(.*)([/\\])[^/\\]*$")
  if not dir then
    return nil
  end
  return dir .. sep .. name, romPath:match("([^/\\]*)$")
end

local function timesPath()
  return besideRom(TIMES_FILE)
end

local function hms(seconds)
  return string.format("%d:%02d:%02d",
    seconds // 3600, (seconds % 3600) // 60, seconds % 60)
end

-- Always to the script log, so the number is visible while playing; to the file
-- as well when the emulator will say where the ROM lives. A write that fails
-- warns once and is then left alone -- a read-only ROM directory is a reason to
-- lose the file, not a reason to spam the log sixty times a second.
local function record(line)
  EMU.log(line)
  local path = timesPath()
  if not path or not EMU.appendFile then
    return
  end
  local called, ok = pcall(EMU.appendFile, path, line .. "\n")
  if called and ok then
    return
  end
  if not timesWarned then
    timesWarned = true
    EMU.log("cannot append to " .. path .. " -- run times stay in this log only")
  end
end

-- Called once per trusted scan. The guard drops on every battle, so `ready`
-- flaps throughout normal play: the start is latched per cartridge rather than
-- recorded on each transition, and only a ROM swap starts a new run.
local function noteRunProgress(rom, goal)
  -- "Allow network access" and "Allow access to I/O and OS functions" are
  -- separate toggles, so a clock is not guaranteed just because sockets work.
  -- Say so once and carry on; timing is not worth taking the scan down for.
  if type(os) ~= "table" or not os.time or not os.date then
    if not timesWarned then
      timesWarned = true
      EMU.log("no os.date -- run times need Restrictions -> "
        .. "'Allow access to I/O and OS functions'")
    end
    return
  end
  if rom ~= timedRom then
    timedRom, runStart, goalRecorded = rom, nil, false
  end
  local _, romName = timesPath()
  romName = romName or (rom ~= "" and rom) or "unknown cartridge"
  if not runStart then
    runStart = os.time()
    record(string.format("%s  start  %s", os.date("%Y-%m-%d %H:%M:%S"), romName))
  end
  if goal and not goalRecorded then
    goalRecorded = true
    record(string.format("%s  chaos  %s  %s this sitting",
      os.date("%Y-%m-%d %H:%M:%S"), romName,
      hms(math.floor(os.difftime(os.time(), runStart)))))
  end
end

------------------------------------------------------------------
-- The run clock: starts on a new game, stops on the goal flag, drawn on the
-- emulator's own screen.
--
-- Counted in frames rather than seconds, and that is the whole design. Mesen's
-- Lua API exposes no pause state and no window focus -- there is no isPaused,
-- no hasFocus, and no eventType for either -- so a wall-clock timer cannot tell
-- a tabbed-away emulator from a running one. Frames can: endFrame stops firing
-- the moment emulation stops, so the clock holds by itself through Preferences
-- -> "Pause when in background", a manual pause, the menus and a debugger
-- break, and resumes without being told. It is also exact at the split, and it
-- makes the whole thing testable, because the test harness drives time by
-- calling the frame callback rather than by sleeping.
--
-- ffr_times.log above is untouched by any of this. It answers "which evenings
-- did I play this seed"; the clock here answers "how long has the run taken".
------------------------------------------------------------------

local runRom = nil
local runFrames = 0
local runRunning = false
local runFinished = false
local runSinceSave = 0
local startScans = 0
local clockScan = 0
-- One flag per failure class. Sharing one silences the other two diagnostics
-- the first time any of them trips.
local timerWarned = false     -- the state file
local drawWarned = false      -- the HUD
local clockWarned = false     -- the tick itself

local function nowSeconds()
  if type(os) ~= "table" or not os.time then
    return nil
  end
  local ok, t = pcall(os.time)
  return ok and type(t) == "number" and t or nil
end

local function timerPath()
  return besideRom(TIMER_FILE)
end

-- Frames to h:mm:ss.cc. Rounded to the nearest hundredth rather than truncated,
-- so a whole number of seconds reads as one: 120 frames is 1.9967s of NTSC and
-- would otherwise show 0:00:01.99.
local function clockText(frames)
  local cs = math.floor((frames / TIMER_FPS) * 100 + 0.5)
  return string.format("%d:%02d:%02d.%02d",
    cs // 360000, (cs % 360000) // 6000, (cs % 6000) // 100, cs % 100)
end

local function saveTimer()
  runSinceSave = 0
  local path = timerPath()
  if not path or not EMU.writeFile then
    return
  end
  -- The stamp is what lets a resume bridge the restart. 0 when there is no
  -- clock to read, which reads back as "cannot tell" rather than as 1970.
  -- Three states, not two. "waiting" is a cartridge whose run has not begun,
  -- and it has to be distinct from "running" or a resume would set a clock
  -- ticking for a run nobody started.
  local state = runFinished and "done" or (runRunning and "running" or "waiting")
  local called, ok = pcall(EMU.writeFile, path,
    string.format("%s\t%d\t%s\t%d\n", runRom or "", runFrames, state,
      nowSeconds() or 0))
  if called and ok then
    return
  end
  if not timerWarned then
    timerWarned = true
    EMU.log("cannot write " .. path .. " -- a power cycle will lose this run")
  end
end

-- Only ever adopted when the file names the cartridge in the slot. A state file
-- left behind by another seed is somebody else's run, not this one's.
local function loadTimer(rom)
  local path = timerPath()
  if not path or not EMU.readFile then
    return
  end
  local called, text = pcall(EMU.readFile, path)
  if not called or type(text) ~= "string" then
    return
  end
  local savedRom, frames, state, stamp = text:match("^([^\t]*)\t(%d+)\t(%a+)\t?(%d*)")
  if not savedRom or savedRom ~= rom then
    return
  end
  runFrames = tonumber(frames) or 0
  runFinished = (state == "done")
  runRunning = (state == "running")
  if not runRunning and not runFinished then
    return          -- a cartridge we had seen but never started timing
  end

  -- Bridge the restart. Emulation was running for that window and we were not
  -- listening, so those frames are real run time -- but only up to a point:
  -- past the cap this is the emulator having been closed and reopened, and
  -- that is not the run. A finished run is never advanced.
  local wrote, now = tonumber(stamp) or 0, nowSeconds()
  local gap = (runRunning and now and wrote > 0) and (now - wrote) or 0
  if gap > 0 and gap <= TIMER_RESUME_MAX_SECONDS then
    runFrames = runFrames + math.floor(gap * TIMER_FPS + 0.5)
    EMU.log(string.format("resuming the run clock at %s (+%ds across the restart)",
      clockText(runFrames), gap))
  else
    EMU.log("resuming the run clock at " .. clockText(runFrames))
  end
end

local function ensureTimerFor(rom)
  if runRom == rom then
    return
  end
  runRom, runFrames, runRunning, runFinished = rom, 0, false, false
  loadTimer(rom)
end

-- A flag page carrying no chest bit and no event bit anywhere is a game that
-- has just been started: FF1 re-seeds the page from lut_InitGameFlags on the
-- way to a new file, and nothing has been opened or talked to yet. It is the
-- same test the pack uses on its side for "the feed went from checks to none".
local function freshGame(mem)
  local flags = flagsOf(mem)
  for i = 1, #flags do
    if (flags:byte(i) & 0x06) ~= 0 then     -- 0x02 event, 0x04 chest
      return false
    end
  end
  return true
end

-- Watch for a new game. Start only: once a run is going, a mid-run save load
-- cannot satisfy freshGame, so loading a save resumes rather than restarts.
--
-- This used to hang off scan(), which only runs while PopTracker is connected
-- -- so starting a new game with the tracker shut left the run untimed
-- altogether. It reads the flag page itself instead, at the scan cadence
-- because that is what it costs and because a run only starts once.
--
-- The stability count is its own rather than the scan's `guardScans`, which
-- only advances from scan() and would have carried the same dependency. Same
-- purpose: a half-initialised frame on the way out of a reset must not read as
-- a new game.
local function pollForStart()
  if runRunning or runFinished or not runRom or runRom == "" then
    startScans = 0
    return
  end
  local mem = readMem()
  if not inGame(mem) or looksUninitialised(mem) or not freshGame(mem) then
    startScans = 0
    return
  end
  startScans = startScans + 1
  if startScans < GUARD_STABLE_SCANS then
    return
  end
  runFrames, runRunning = 0, true
  EMU.log("new game -- run clock started")
  saveTimer()
end

-- Every frame, and deliberately not behind the socket gate: the clock is worth
-- having whether or not PopTracker is up.
local function tickRunClock()
  -- Adopt the cartridge here rather than waiting for a trusted scan: scan()
  -- only runs while PopTracker is connected, and a script restarted by a power
  -- cycle has to be able to pick its own run back up off disk with the tracker
  -- closed. "" is the emulator declining to say, so keep asking.
  -- Everything that needs more than a byte runs at the scan cadence rather
  -- than every frame: which cartridge is in the slot, and whether a new game
  -- has begun. Both used to hang off scan(), which only runs while PopTracker
  -- is connected -- so a swap went unnoticed and a new game with the tracker
  -- shut was never timed at all.
  clockScan = clockScan + 1
  if clockScan >= SCAN_INTERVAL_FRAMES then
    clockScan = 0
    -- "" is the emulator declining to answer, usually for a frame or two around
    -- a load. Adopting it would zero the clock and then read it back off disk,
    -- which costs a checkpoint interval of run time for nothing.
    local rom = EMU.romId and EMU.romId() or ""
    if rom ~= "" then
      ensureTimerFor(rom)     -- a no-op unless the cartridge actually changed
    end
    if not runRunning and not runFinished then
      pollForStart()
    end
  end

  if not runRunning then
    return
  end
  runFrames = runFrames + 1

  -- The split is sampled here rather than on the 10Hz scan so it lands on the
  -- frame the flag actually flips. One byte, not the whole 0x300 window.
  local byte = EMU.readByte and EMU.readByte(MEM_ADDR + FLAGS_OFF + GOAL_BYTE)
  if type(byte) == "number" and (byte & 0x02) ~= 0 then
    runRunning, runFinished = false, true
    local stamp = (type(os) == "table" and os.date) and os.date("%Y-%m-%d %H:%M:%S") or "?"
    local _, romName = timerPath()
    record(string.format("%s  clock  %s  %s",
      stamp, romName or runRom or "unknown cartridge", clockText(runFrames)))
    saveTimer()
    return
  end

  runSinceSave = runSinceSave + 1
  if runSinceSave >= TIMER_SAVE_FRAMES then
    saveTimer()
  end
end

-- Drawn every frame because Mesen's draw calls last exactly one frame by
-- default, so a stale readout is not a state this can get into.
local function drawRunClock()
  if not EMU.drawText or not runRom then
    return
  end
  local ok = pcall(EMU.drawText, clockText(runFrames), runFinished)
  if ok or drawWarned then
    return
  end
  drawWarned = true
  EMU.log("cannot draw the run clock -- it is still being kept and logged")
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
  noteRunProgress(lastRom, lastGoal)
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
-- Where the cartridge came from, for parking the run-times file beside it.
EMU.romPath = function()
  local ok, info = pcall(emu.getRomInfo)
  if not ok or type(info) ~= "table" then
    return nil
  end
  return type(info.path) == "string" and info.path or nil
end
-- Needs Script -> Settings -> Restrictions -> "Allow access to I/O and OS
-- functions", which this script already requires for sockets.
EMU.appendFile = function(path, text)
  if type(io) ~= "table" or not io.open then
    return false
  end
  local f = io.open(path, "a")
  if not f then
    return false
  end
  f:write(text)
  f:close()
  return true
end
-- Truncating, for the run clock's one-line state file. Separate from
-- appendFile because that one is open("a") and this has to replace.
EMU.writeFile = function(path, text)
  if type(io) ~= "table" or not io.open then
    return false
  end
  local f = io.open(path, "w")
  if not f then
    return false
  end
  f:write(text)
  f:close()
  return true
end
EMU.readFile = function(path)
  if type(io) ~= "table" or not io.open then
    return nil
  end
  local f = io.open(path, "r")
  if not f then
    return nil            -- no state file yet is the ordinary first run
  end
  local text = f:read("a")
  f:close()
  return text
end
-- The run clock, top right. Positioned off the surface rather than off a
-- hardcoded 256x240 so an overscan setting cannot push it off the edge.
-- consoleScreen rather than scriptHud so it lands in screenshots and video,
-- which is the point of a run timer.
EMU.drawText = function(text, done)
  local surface = emu.drawSurface and emu.drawSurface.consoleScreen
  if surface and emu.selectDrawSurface then
    pcall(emu.selectDrawSurface, surface)
  end
  local width = 256
  if emu.getDrawSurfaceSize then
    local okSize, size = pcall(emu.getDrawSurfaceSize, surface)
    if okSize and type(size) == "table" and type(size.width) == "number" then
      width = size.width
    end
  end
  local textWidth = 8 * #text     -- the default font is 8px wide per glyph
  if emu.measureString then
    local okM, measured = pcall(emu.measureString, text)
    if okM and type(measured) == "number" then
      textWidth = measured
    end
  end
  emu.drawString(width - textWidth - TIMER_MARGIN, TIMER_MARGIN, text,
    done and TIMER_FG_DONE or TIMER_FG_RUNNING, TIMER_BG)
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
  -- Ahead of the pump and outside the client gate: the run clock follows the
  -- emulator, not PopTracker.
  local okClock, errClock = pcall(tickRunClock)
  if not okClock and not clockWarned then
    clockWarned = true
    EMU.log("run clock error: " .. tostring(errClock))
  end
  drawRunClock()
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
emu.addEventCallback(function()
  -- Clock first: the socket close is a courtesy to PopTracker, losing the run
  -- time is not recoverable. Note this does NOT fire on a power cycle -- that
  -- tears the Lua state down through ~ScriptManager, which emits nothing -- so
  -- it covers a manual stop and a reloaded script, and TIMER_SAVE_FRAMES is
  -- what bounds the loss on a hard reset.
  pcall(saveTimer)
  pcall(shutdown)
end, emu.eventType.scriptEnded)

EMU.log("ready -- waiting for PopTracker on ws://127.0.0.1:" .. UAT_PORT)
