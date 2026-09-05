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
                            -- worlds/ff1/Client.py treats as the goal.

-- ...but only on an Archipelago seed. FFR patches bank 0x0B $9ADF to `20 40 9B`
-- in FF1Lib/archipelago/Archipelago.cs:225-226, and the stub it lands on sets
-- $62FE bit 0x02 on its way to ChaosDeath. A solo seed keeps the vanilla
-- `JSR ChaosDeath` there and so never sets the bit at all, which left the clock
-- running forever and the tracker's Chaos check with nothing to clear it.
--
-- The battle engine says the same thing out loud, though, and it says it in
-- vanilla. BattleOver_ProcessResult (bank_0B.asm:571-574) is:
--
--     LDA a:btlformation / CMP #$7B / BNE :+
--       LDA #$FF / STA btl_result / JSR ChaosDeath
--
-- so on the winning frame the formation is Chaos's, btl_result is $FF, and a
-- battle is still running. btl_result keeps that value through the 110 frames
-- ChaosDeath spends waiting out the fanfare and well past, so a per-frame poll
-- cannot miss it. It is also the same instant the Archipelago stub sets its bit
-- -- before the JMP, not after the dissolve -- so reading it here does not move
-- an Archipelago seed's split by a frame.
--
-- ff1/goal is what carries the result to the tracker, and it is the only reason
-- that variable is worth publishing: byte 0xFE arrives inside ff1/mem anyway,
-- so on an Archipelago seed the pack could have read it there. It cannot on a
-- solo seed, so scripts/autotracking/uat.lua reads ff1/goal instead.
local BTL_FORMATION_ADDR = 0x006A   -- zero page; variables.inc btlformation
local BTL_RESULT_ADDR = 0x6B86      -- FF1Lib Assembly/Symbols.cs:2509
local CHAOS_FORMATION = 0x7B        -- FFR restyles it but never moves it
local CHAOS_RESULT = 0xFF           -- "pause after fadeout", set nowhere else

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

-- The two rolls, which are the two things about a cartridge that no flag
-- string can say. FFR picks both at generation and writes neither to the flag
-- record nor to the spoiler, so the ROM itself is the only source:
--
--   the gateway roll   in No-Overworld, three one-way teleporters out of
--                      Waterfall, Ice Cave B1 and Gaia are dealt two Cardia
--                      landings and Bahamut's Cave B1 in a shuffled order
--                      (MetroidVaniaMap.cs:717-736)
--   the objective roll ShuffleObjectiveNPCs permutes Bahamut, Dr Unne and the
--                      Elf Doctor across Melmond, Elfland Castle and Bahamut's
--                      Cave B2 (NPCs.cs:277)
--
-- Both are short reads at fixed offsets, which is what makes this a bridge
-- feature rather than a map decompressor: the gateways keep three fixed
-- teleport ids and only their destinations move, and the NPCs are three
-- records in one flat table. tools/entrance_graph.py --rolls is the same read
-- offline and is what these figures were measured with.
--
-- Offsets are PRG, header excluded, like FLAGS_ROM_OFF above: FFR's extended
-- teleport tables are bank $0F at $B000/$B100/$B200, and lut_MapObjects is
-- bank $00 at $B400. The Python tools quote the same addresses 0x10 higher,
-- because they index the file and count the iNES header.
local ROLLS_NORM_X = 0x3F000
local ROLLS_NORM_Y = 0x3F100
local ROLLS_NORM_MAP = 0x3F200
-- Consecutive on purpose: they are read as one 3-byte run per table, from the
-- first id. They come off a `teleportIDtracker++` at a fixed point in a
-- hand-authored table of 75, and were the same three on all five
-- No-Overworld cartridges measured.
local GATEWAY_FIRST_ID = 0x89
local GATEWAY_SOURCES = { "waterfall", "icecave", "gaia" }
-- Keyed "<map>:<x>,<y>" on the destination each gateway lands on. Reading the
-- destinations rather than the GameMode is what decides whether this cartridge
-- has gateways at all: all three have to land on these three tiles, one each.
-- So a cartridge whose flag record will not decode still answers, and an FFR
-- that moves a landing publishes nothing rather than something plausible.
local GATEWAY_LANDINGS = {
  ["16:58,55"] = "cardiaForest",
  ["16:43,29"] = "cardiaCaravan",
  ["17:2,2"] = "bahamutCave",
}
local COORD_MASK = 0x3F   -- the top bits of a teleport coordinate are flags

local MAP_OBJECTS_ROM = 0x3400
local OBJ_MAP_COUNT, OBJ_PER_MAP, OBJ_RECORD, OBJ_STRIDE = 61, 15, 3, 48
-- $05 is the Elf **Doctor**, not the Elf Prince at $06. The prince holds the
-- check and never moves; reading his object would report every cartridge as
-- unshuffled in that third of the permutation.
local OBJECTIVE_NPCS = { [0x05] = "elfdoc", [0x0B] = "unne", [0x0E] = "bahamut" }
local OBJECTIVE_HOMES = { [3] = "melmond", [9] = "elflandCastle", [39] = "bahamutCaveB2" }
-- Published in a fixed order, so the string is stable across scans and two
-- cartridges rolled the same way publish the same bytes.
local OBJECTIVE_ORDER = { "bahamut", "elfdoc", "unne" }

-- The shop key item, and why it takes two different reads.
--
-- FFR gives the item shop slot a synthetic object id of 0xFF so that buying a
-- key item out of a shop sets a flag like any other check. Its NewCheckForSpace
-- patch (FF1Lib/asm/0E_9F48_ItemShopCheckForSpace.asm:11-31) does
-- `LDA $6200,Y / ORA #$02 / STA $6200,Y` with Y = 0xFF whenever the purchased
-- item's id is below 0x16, i.e. a key item. That is exactly what Archipelago
-- location 767 (0x2FF) means -- worlds/ff1/Client.py resolves an id at or above
-- 0x200 to flag byte id-0x200 with mask 0x02.
--
-- On the 4.9.x line GlobalImprovements.cs installs that patch only under
-- `if (archipelagoenabled)`, so a solo seed never writes the byte: measured
-- across the cartridges in seeds/ff1/, every Archipelago one carries the patch
-- and every seed rolled on the public site has NOPs there instead.
--
-- So a solo seed is read the other way round: the shop's stock is in PRG ROM,
-- the key item is sitting in it, and since each key item is placed exactly once
-- per seed, that item's inventory byte going non-zero *is* the purchase.
local SHOP_BYTE = 0xFF      -- bit 0x02 within the flag array, Archipelago seeds
local ITEMS_OFF = 0x020     -- `items` within MEM: id N counts at $6020 + N
local SHOP_PTR_ROM = 0x38300  -- lut_ShopData, bank 0x0E $8300; entry 0 unused
-- lut_ShopTypes lives in the fixed bank, which is 0x0F on a 256K image and 0x1F
-- once FFR expands to 512K -- so a disassembly of the original gives the wrong
-- one of these. Both are tried and the one that reads back as six item shops
-- and a caravan wins, the same way readFlags insists on seeing FFRInfo rather
-- than searching for it.
local SHOP_TYPE_CANDIDATES = { 0x7EBB5, 0x3EBB5 }
local SHOP_IDS = { 61, 62, 63, 64, 65, 66, 70 }   -- six item shops, then the caravan
local SHOP_ID_MAX = 70
-- Ids 1-16 are the key items that can honestly be watched in inventory. 17-20
-- are the four orbs and 21 the Shard, which ram_mapping.lua already owns, and a
-- shop holding one of those on a cartridge with no Archipelago patch would mean
-- the decode is wrong rather than the seed strange. The canoe is not an item id
-- at all -- it is the vehicle byte $6012, which ram_mapping.lua reads directly.
local SHOP_KEY_ITEM_MAX = 16
-- NewCheckForSpace, the patch that writes SHOP_BYTE. Present only on an
-- Archipelago cartridge on the 4.9.x line; a solo seed has 0xEA all through
-- here. Probing it is what keeps the inventory watch off an Archipelago
-- cartridge, where the shop holds the FireOrb sentinel and its inventory byte
-- $6032 is the Fire Orb's own -- watching it there would tick this check the
-- moment the orb lit, and light the orb the moment the sentinel was bought.
local AP_SHOP_PATCH_ROM = 0x39F48
local AP_SHOP_PATCH_HEAD = "\xae\x0c\x03\xe0\x16"

-- In-game guard, matching worlds/ff1/Client.py and the EmoTracker pack's
-- isInGame(). All three bytes live inside MEM.
local GUARD_A_OFF = 0x102   -- first character's name; 0 = title / char creation
local GUARD_B_OFF = 0x0FC   -- see BATTLE_RUNNING
local GUARD_C_OFF = 0x0A3
-- What GUARD_B holds while a fight is on. Read two ways: as a reason to
-- distrust the save window, and as the corroboration the Chaos poll needs that
-- the formation and result bytes below it are a live battle's rather than
-- whatever was last left in cart RAM.
local BATTLE_RUNNING = { [0x0B] = true, [0x0C] = true }

-- Wall-clock markers for a run, appended to a file next to the ROM. Nothing
-- else on the machine can answer "how long did that seed take": FF1 keeps no
-- play-time counter in SRAM, FFR adds no timer flag, Mesen does not track time
-- per game, and the script log window is gone the moment Mesen restarts. One
-- line per event with an absolute timestamp. A seed played over several
-- sittings leaves one `start` line per sitting and a single `chaos` line, so
-- the elapsed total is the last stamp minus the first.
local TIMES_FILE = "ffr_times.log"

-- The run clock, kept beside the ROM so a seed picked up tomorrow resumes
-- rather than restarting. One line, rewritten in place rather than appended,
-- and named after the cartridge rather than after the directory: seeds share
-- an output directory, and a single shared file would have each seed's
-- checkpoint truncate the other seed's run. ffr_times.log gets away with one
-- shared file only because it is append-only with the ROM name on every line.
local TIMER_FILE = "ffr_timer.%s.state"

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

-- What the run clock's new-game debounce costs, and therefore what it owes the
-- run back when it arms. The clock starts on the GUARD_STABLE_SCANS'th
-- consecutive fresh-game read, which lands GUARD_STABLE_SCANS - 1 scan
-- intervals after the first one: every frame of that window is play, and
-- starting from zero threw all of it away. The frames before the first read
-- are not credited -- the scan cadence cannot see them, and guessing at them
-- would trade a bounded under-count for an unbounded over-count.
local START_DEBOUNCE_FRAMES = (GUARD_STABLE_SCANS - 1) * SCAN_INTERVAL_FRAMES

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

-- Last state actually put on the wire, for diffing. A table rather than nine
-- parallel locals: the caller passes the same shape, so a field added here is
-- one line in each of the two places rather than a positional list to keep in
-- step at four call sites.
local sent = {}
local STATE_KEYS = { "mem", "ready", "goal", "map", "rom", "flags", "art",
                     "shop", "rolls" }

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

local function sendState(state, force)
  local msgs = {}
  local function changed(key)
    return force or state[key] ~= sent[key]
  end
  if changed("mem") then
    msgs[#msgs + 1] = varMem(state.mem)
  end
  if changed("ready") then
    msgs[#msgs + 1] = varBool("ff1/ready", state.ready)
  end
  if changed("goal") then
    msgs[#msgs + 1] = varBool("ff1/goal", state.goal)
  end
  -- Whether the shop key item has been bought. A boolean and nothing else: the
  -- bridge knows which shop and which item, and publishing either would hand
  -- over the shop hunt.
  if changed("shop") then
    msgs[#msgs + 1] = varBool("ff1/shopitem", state.shop)
  end
  if changed("map") then
    msgs[#msgs + 1] = varNum("ff1/map", state.map)
  end
  -- Sent whatever ff1/ready says. This is which cartridge is in the slot, not
  -- game state, and the pack needs it before the save-loaded guard passes --
  -- that is the whole window in which a ROM swap has to be noticed.
  if changed("rom") then
    msgs[#msgs + 1] = varStr("ff1/rom", state.rom)
  end
  -- Same reasoning as ff1/rom: this describes the cartridge, not the save, so
  -- it goes out whether or not a save is loaded. The pack needs it to configure
  -- its flag grid before there is any progress to show.
  if changed("flags") then
    msgs[#msgs + 1] = varStr("ff1/flags", state.flags)
  end
  -- And on the same terms: the two permutations FFR rolled into this cartridge
  -- are a property of the cartridge, and the rules that read them want them
  -- before a save is loaded, the way the flag grid does.
  if changed("rolls") then
    msgs[#msgs + 1] = varStr("ff1/rolls", state.rolls)
  end
  -- And on the same terms again: which cartridge the art on disk was drawn for
  -- is a fact about the installation, not about the save.
  if changed("art") then
    msgs[#msgs + 1] = varStr("ff1/art", state.art)
  end
  if #msgs == 0 then
    return
  end
  if send(wsEncodeText("[" .. table.concat(msgs, ",") .. "]")) then
    -- The named keys and not pairs(state): a caller that left one out would
    -- otherwise leave the previous cartridge's value standing in `sent`, and
    -- the next frame carrying it would read as unchanged.
    for _, key in ipairs(STATE_KEYS) do
      sent[key] = state[key]
    end
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
-- The two permutations this cartridge rolled, or "". Beside lastFlags for the
-- same reason: a fact about the cartridge, published on the same terms.
local lastRolls = ""
-- Why the drawn maps are not this cartridge's, or "". Kept beside lastFlags
-- because it describes the cartridge rather than the save, and goes out on the
-- same terms.
local lastArt = ""
-- Whether this cartridge's shop key item has been bought. Latched by
-- shopItemBought against the turn-in that spends the item, and released there
-- on a new game, a cartridge swap, or the save itself saying otherwise.
local lastShop = false

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
-- The cartridge's full FFRInfo identity, and the two fields of it worth saying
-- out loud. Set by readFlags alongside flagsValue and memoised with it.
local ffrValue, ffrSeed, ffrVersion = "", "", ""

local function readFlags(rom)
  if flagsFor == rom then
    return flagsValue
  end
  flagsFor, flagsValue = rom, ""
  -- Cleared on the same statement, so every early return below leaves the
  -- identity empty rather than the previous cartridge's.
  ffrValue, ffrSeed, ffrVersion = "", "", ""

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
  -- The same record's Seed field, which the flag grid has no use for and the
  -- art check does. Kept beside flagsValue rather than folded into it: the pack
  -- parses ff1/flags as "<version>|<flags>" and a third field would break it.
  --
  -- The seed on its own is not an identity -- the three 4.9.7 oracle cartridges
  -- all carry seed 3B7E1C8A and differ only in flags -- so what gets compared
  -- is all three fields. The flag string ends in the FFR build sha, so three
  -- matching fields mean the same generator run on the same settings, which is
  -- the same bytes.
  local seed = record:match("|Seed: ([^|]+)") or "?"
  ffrValue = version .. "|" .. seed .. "|" .. flags
  ffrSeed, ffrVersion = seed, version
  EMU.log("seed flags: FFR " .. version .. ", seed " .. seed .. ", "
          .. #flags .. " characters")
  return flagsValue
end

------------------------------------------------------------------
-- The two rolls, read off the cartridge.
------------------------------------------------------------------

-- The gateway roll as "waterfall:<landing>,icecave:<landing>,gaia:<landing>",
-- or "" when this cartridge has none -- every mode but No-Overworld, and every
-- image FFR did not write.
local function readGatewayRoll()
  local n = #GATEWAY_SOURCES
  local okX, xs = pcall(EMU.readRom, ROLLS_NORM_X + GATEWAY_FIRST_ID, n)
  local okY, ys = pcall(EMU.readRom, ROLLS_NORM_Y + GATEWAY_FIRST_ID, n)
  local okM, ms = pcall(EMU.readRom, ROLLS_NORM_MAP + GATEWAY_FIRST_ID, n)
  if not (okX and okY and okM) then
    return ""
  end
  if type(xs) ~= "string" or type(ys) ~= "string" or type(ms) ~= "string" then
    return ""
  end
  if #xs < n or #ys < n or #ms < n then
    return ""
  end
  local parts, seen = {}, {}
  for i = 1, n do
    local key = string.format("%d:%d,%d", ms:byte(i),
                              xs:byte(i) & COORD_MASK, ys:byte(i) & COORD_MASK)
    local landing = GATEWAY_LANDINGS[key]
    -- One landing each. Two gateways on one tile is not a permutation, and
    -- would mean these ids are carrying something else entirely.
    if landing == nil or seen[landing] then
      return ""
    end
    seen[landing] = true
    parts[i] = GATEWAY_SOURCES[i] .. ":" .. landing
  end
  return table.concat(parts, ",")
end

-- The objective roll as "bahamut:<home>,elfdoc:<home>,unne:<home>", or "".
--
-- The whole object table is walked rather than the three homes, so "they only
-- ever stand on three maps" is measured on the cartridge in the slot rather
-- than assumed: an objective NPC found anywhere else publishes nothing instead
-- of two thirds of an answer. It is 2928 bytes, read once per cartridge.
local function readObjectiveRoll()
  local want = OBJ_MAP_COUNT * OBJ_STRIDE
  local ok, raw = pcall(EMU.readRom, MAP_OBJECTS_ROM, want)
  if not ok or type(raw) ~= "string" or #raw < want then
    return ""
  end
  local home = {}
  for mapId = 0, OBJ_MAP_COUNT - 1 do
    local base = mapId * OBJ_STRIDE
    for i = 0, OBJ_PER_MAP - 1 do
      local name = OBJECTIVE_NPCS[raw:byte(base + i * OBJ_RECORD + 1)]
      if name ~= nil then
        if home[name] ~= nil or OBJECTIVE_HOMES[mapId] == nil then
          return ""
        end
        home[name] = OBJECTIVE_HOMES[mapId]
      end
    end
  end
  local parts, seen = {}, {}
  for i, name in ipairs(OBJECTIVE_ORDER) do
    local where = home[name]
    if where == nil or seen[where] then
      return ""
    end
    seen[where] = true
    parts[i] = name .. ":" .. where
  end
  return table.concat(parts, ",")
end

-- Both rolls as one record, "gateways=<...>|npcs=<...>", or "" when neither
-- half could be read.
--
-- One key with two fields rather than two keys: they are one read on one
-- channel, and a pack that has to know whether it has heard yet would
-- otherwise have two answers to reconcile. An empty field is its own answer --
-- "this cartridge has no gateways" is what every standard seed says, and the
-- rules that name them stay strict on it.
--
-- Memoised on the cartridge id for the same reason readFlags is: none of this
-- can change while a ROM is loaded, and a swap changes the id.
local rollsFor, rollsValue = nil, ""

local function readRolls(rom)
  if rollsFor == rom then
    return rollsValue
  end
  rollsFor, rollsValue = rom, ""
  if not EMU.readRom then
    return rollsValue
  end
  local gateways, npcs = readGatewayRoll(), readObjectiveRoll()
  if gateways ~= "" or npcs ~= "" then
    rollsValue = "gateways=" .. gateways .. "|npcs=" .. npcs
  end
  return rollsValue
end

------------------------------------------------------------------
-- Are the drawn maps this cartridge's?
--
-- tools/regen_maps.py renders 61 maps off a cartridge into PopTracker's
-- user-override tree, and PopTracker serves that tree ahead of the pack's own
-- hand-drawn art. Rendered from one seed and read under another, the art looks
-- entirely normal and is wrong about every staircase -- which is worse than the
-- hand art, because the hand art at least never claims to be this seed's.
--
-- Nothing in the tracker can notice: PopTracker's Lua has no io and no os, so
-- the pack cannot read the override it is being served from. The bridge can,
-- and it is already holding the cartridge, so the comparison lands here.
--
-- What it reads is .regen_stamp, written beside .regen_cache.json for this
-- reader specifically: the cache records a sha256 and is JSON, and there is
-- neither a sha256 nor a JSON parser in here.
------------------------------------------------------------------

local PACK_UID = "ff1_rando_ap_uat"      -- manifest.json, package_uid
                                         -- held against it by tests/test_bridge.lua
local STAMP_NAME = ".regen_stamp"
local ART_DIR_ENV = "FFR_ART_DIR"        -- for a PopTracker installed elsewhere

-- ~/PopTracker/user-override/<uid>/, the same default regen_maps.py --out has.
local function stampPath()
  if type(os) ~= "table" or type(os.getenv) ~= "function" then
    return nil
  end
  local override = os.getenv(ART_DIR_ENV)
  if override and override ~= "" then
    return override .. "/" .. STAMP_NAME
  end
  local home = os.getenv("HOME") or os.getenv("USERPROFILE")
  if not home or home == "" then
    return nil
  end
  return home .. "/PopTracker/user-override/" .. PACK_UID .. "/" .. STAMP_NAME
end

-- Why the art on disk is not this cartridge's, or "" when there is nothing to
-- say. "Nothing to say" covers four different silences and they are all
-- deliberate: no override installed, no stamp in it, a cartridge with no
-- FFRInfo record to compare, and art whose own identity was never recorded.
-- Each of those is a question this cannot answer, and answering "stale" to a
-- question you cannot answer is how a warning light stops being read.
--
-- Memoised on the cartridge, like the flags: a regen while the emulator is
-- running is not something to poll for, because picking the new art up needs
-- PopTracker restarted anyway.
local artFor, artValue = nil, ""

local function readArt(rom)
  if artFor == rom then
    return artValue
  end
  artFor, artValue = rom, ""

  local path = stampPath()
  if not path or not EMU.readFile then
    return artValue
  end
  local ok, text = pcall(EMU.readFile, path)
  if not ok or type(text) ~= "string" then
    return artValue         -- no override installed: the pack's own art, which
  end                       -- is always honest about not being a seed's

  readFlags(rom)            -- fills ffrValue for this cartridge, or leaves it ""

  local known, unknown = {}, 0
  for line in text:gmatch("[^\r\n]+") do
    if line:sub(1, 1) ~= "#" then
      local mode, sha1, ffr = line:match("^(%S+) (%S+) (%S+)$")
      if mode then
        -- A sha1 match silences and never warns. Mesen's fileSha1Hash is the
        -- cartridge id readRom() already publishes, but what it covers -- the
        -- .nes file, or the banks with the iNES header parsed off -- is the
        -- emulator's business and not written down anywhere here. Used only to
        -- agree, a wrong guess about that costs nothing; used to disagree it
        -- would warn on every seed.
        if sha1 == rom or (ffrValue ~= "" and ffr == ffrValue) then
          return artValue
        end
        if ffr == "unknown" then
          unknown = unknown + 1
        else
          known[#known + 1] = mode .. " " .. (ffr:match("^([^|]*|[^|]*)") or ffr)
        end
      end
    end
  end

  -- A mode whose art predates the stamp could be this cartridge's -- nothing
  -- here can rule it out, and the matching line above is the only thing that
  -- could have. So one unrecorded mode makes the whole file unable to answer,
  -- rather than making the recorded modes speak for it.
  if ffrValue == "" or unknown > 0 or #known == 0 then
    return artValue
  end

  artValue = "the drawn maps are another cartridge's: " .. table.concat(known, ", ")
             .. " -- this one is " .. ffrVersion .. "|" .. ffrSeed
  EMU.log(artValue)
  return artValue
end

local function readMem()
  local bytes = {}
  for i = 0, MEM_LEN - 1 do
    bytes[i + 1] = string.char(EMU.readByte(MEM_ADDR + i) & 0xFF)
  end
  return table.concat(bytes)
end

-- The same buffer readMem() returns, but with only the bytes the new-game test
-- actually looks at fetched off the bus: the flag page and the three guard
-- bytes. Everything else reads as zero, which none of inGame(),
-- looksUninitialised() or freshGame() consults -- so those three stay the one
-- definition of each test rather than being restated here in cheaper form.
-- A third of readMem()'s traffic, which is worth having because this runs on
-- the same frames the scan does and used to double them.
local START_OFFSETS = { GUARD_A_OFF, GUARD_B_OFF, GUARD_C_OFF }

local function readStartMem()
  local bytes = {}
  for i = 1, MEM_LEN do
    bytes[i] = "\0"
  end
  for i = 0, FLAGS_LEN - 1 do
    bytes[FLAGS_OFF + i + 1] = string.char(EMU.readByte(MEM_ADDR + FLAGS_OFF + i) & 0xFF)
  end
  for _, off in ipairs(START_OFFSETS) do
    bytes[off + 1] = string.char(EMU.readByte(MEM_ADDR + off) & 0xFF)
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

-- { item = <id> } for the key item a shop holds, { item = nil, ap = true } on an
-- Archipelago cartridge, or nil when the cartridge cannot be read. Memoised on
-- the cartridge id for the same reason readFlags is: shop stock is in ROM and
-- cannot move while a cartridge is loaded.
--
-- Deliberately bridge-local: the shop and the item are never published, logged
-- or exposed under debug logging, and only the one boolean below leaves here.
-- Naming the town or the item would hand over the shop hunt, which on a seed
-- that has one is most of what the slot is for.
local shopFor, shopSlot = nil, nil

-- The offset lut_ShopTypes actually sits at on this image, validated by reading
-- it: the six item shops must come back as type 6 and the caravan as 7.
local function shopTypeBase()
  for _, base in ipairs(SHOP_TYPE_CANDIDATES) do
    local ok, types = pcall(EMU.readRom, base, SHOP_ID_MAX + 1)
    if ok and type(types) == "string" and #types > SHOP_ID_MAX then
      local good = true
      for n, id in ipairs(SHOP_IDS) do
        local want = (id == 70) and 7 or 6
        local got = types:byte(id + 1)
        if not got or (got & 0x07) ~= want then
          good = false
          break
        end
      end
      if good then
        return base
      end
    end
  end
  return nil
end

local function readShopSlot(rom)
  if shopFor == rom then
    return shopSlot
  end
  shopFor, shopSlot = rom, nil

  if not EMU.readRom then
    return nil
  end

  -- An Archipelago cartridge is answered by SHOP_BYTE and must not be answered
  -- by inventory, so this probe comes first and short-circuits the rest.
  local okAp, head = pcall(EMU.readRom, AP_SHOP_PATCH_ROM, #AP_SHOP_PATCH_HEAD)
  if okAp and head == AP_SHOP_PATCH_HEAD then
    shopSlot = { item = nil, ap = true }
    return shopSlot
  end

  if not shopTypeBase() then
    -- Not an FFR image, or a build that lays its shop tables out differently.
    -- Say nothing and leave the pin manual rather than read arbitrary bytes as
    -- item ids.
    return nil
  end

  local okPtrs, ptrs = pcall(EMU.readRom, SHOP_PTR_ROM, (SHOP_ID_MAX + 1) * 2)
  if not okPtrs or type(ptrs) ~= "string" then
    return nil
  end

  local found = nil
  for _, id in ipairs(SHOP_IDS) do
    local lo, hi = ptrs:byte(id * 2 + 1), ptrs:byte(id * 2 + 2)
    local addr = (lo and hi) and (lo | (hi << 8)) or 0
    if addr >= 0x8000 and addr < 0xC000 then
      local okEnt, entries = pcall(EMU.readRom, 0x38000 + (addr - 0x8000), 5)
      if okEnt and type(entries) == "string" then
        for k = 1, 5 do
          local b = entries:byte(k)
          if not b or b == 0 then
            break
          end
          if b >= 1 and b <= SHOP_KEY_ITEM_MAX then
            -- FFR places exactly one item in the slot, so a second reading
            -- means the decode is wrong rather than the seed unusual. Refuse,
            -- and the pin stays manual for this cartridge.
            if found then
              EMU.log("more than one shop holds a key item -- shop check stays manual")
              return nil
            end
            found = b
          end
        end
      end
    end
  end

  -- Nothing found is an ordinary outcome, not a failure: roughly half of solo
  -- seeds put a plain consumable in the slot, which nobody can be seen to buy.
  -- Ten rolls on one played cartridge's flags gave five with no key item in any
  -- shop. Those seeds keep a pin that only a click will clear.
  shopSlot = { item = found, ap = false }
  return shopSlot
end

-- Has the shop key item been bought?
--
-- An Archipelago cartridge carries the patch that writes SHOP_BYTE, so it keeps
-- its own record and that record is part of the save. It is read fresh every
-- tick, including back to false -- the same reasoning as goalReached: where the
-- save remembers, the save has to win, or loading one from before the purchase
-- leaves the pin lit for the rest of the run.
--
-- A solo cartridge has nothing that remembers, so the purchase is latched
-- there: several key items are spent on the turn-in that follows -- ElfDoc
-- decrements the Herb, and Ruby, Adamant, Slab, Tail, Bottle and Crystal go the
-- same way. The pack replaces its whole checked set every tick, so an unlatched
-- read would clear the pin on the purchase and un-clear it on the hand-over.
-- The Herb is the shop item on two of the eight cartridges in seeds/ff1/, so
-- that is the ordinary case rather than a corner of one.
--
-- The latch is released on a cartridge swap and on a new game. A practice run
-- or a race-night restart is the ordinary way a second run happens on the same
-- seed, and it starts with the item unbought.
--
-- Holding the item is read as having bought it. FFR places exactly one copy and
-- it is in the shop, so the two coincide -- except when attaching mid-run to a
-- save whose starting inventory was given the item outright.
local shopBoughtFor, shopBought = nil, false

local function shopItemBought(mem, rom)
  if shopBoughtFor ~= rom then
    shopBoughtFor, shopBought = rom, false
  end
  if freshGame(mem) then
    -- A new game starts with the item unbought. Safe to do while the page still
    -- reads fresh: the item is either in inventory, where the read below finds
    -- it without help, or it has been handed over -- and every turn-in that
    -- spends it sets the event bit that ends a fresh page.
    shopBought = false
  end

  -- An Archipelago seed says so directly, in a byte we are already holding.
  if (at(mem, FLAGS_OFF + SHOP_BYTE) & 0x02) ~= 0 then
    return true
  end

  local slot = readShopSlot(rom)
  if slot and slot.ap then
    -- The byte above is this cartridge's own record of the purchase, and it is
    -- clear. Nothing to latch, and nothing a latch could say that the save has
    -- not already said better.
    return false
  end

  if shopBought then
    return true
  end
  if slot and slot.item and at(mem, ITEMS_OFF + slot.item) ~= 0 then
    shopBought = true
  end
  return shopBought
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
  if BATTLE_RUNNING[b] then
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
-- Latched, per cartridge. The kill is a moment rather than a state: nothing in
-- a solo seed's save records it afterwards, so the one frame it is visible on
-- has to be remembered.
local chaosSeen = false
-- ...but only on the cartridges that need it. FFR patches the goal bit into
-- byte $FE for Archipelago and nowhere else, so a cartridge that has ever shown
-- that bit keeps its own record of the kill in the save file -- and there the
-- save has to win, or loading one from before the fight would leave the check
-- lit for a Chaos who is standing up again. Set once, per cartridge, and
-- persisted with the latch it disarms.
local goalBitSeen = false
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

-- Where one cartridge's clock lives, or nil when the emulator will not say
-- which cartridge that is. That nil is load-bearing twice over: it keeps a
-- teardown write from landing on a file named after nobody, and it is why two
-- seeds in one directory can no longer overwrite each other.
local function timerPath(rom)
  rom = rom or runRom
  if type(rom) ~= "string" or rom == "" then
    return nil
  end
  -- The id is a SHA-1 where the emulator gives one and the cartridge's file
  -- name where it does not, so it has to survive being part of a file name.
  local safe = (rom:gsub("[^%w%-%.]", "_"))
  return besideRom(string.format(TIMER_FILE, safe))
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
  -- nil when we do not know which cartridge this is -- the teardown hook can
  -- reach here before the first scan has adopted one, and a write then would
  -- be a run with no name.
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
  -- The kill is its own field rather than a reading of `state`, because the
  -- clock and the kill are not the same fact. A seed picked up from a mid-run
  -- save never arms the clock, so its state stays "waiting" for a run that
  -- reaches Chaos all the same -- and on a solo seed this file is the only
  -- witness to the kill that outlives the emulator.
  local called, ok = pcall(EMU.writeFile, path,
    string.format("%s\t%d\t%s\t%d\t%d\t%d\n", runRom, runFrames, state,
      nowSeconds() or 0, chaosSeen and 1 or 0, goalBitSeen and 1 or 0))
  if called and ok then
    return
  end
  if not timerWarned then
    timerWarned = true
    EMU.log("cannot write " .. path .. " -- a power cycle will lose this run")
  end
end

-- Only ever adopted when the file names the cartridge in the slot. The file
-- name says the same thing now, so this is the second lock rather than the
-- first -- but it still catches a state file copied or renamed by hand, and a
-- run adopted by the wrong seed is not a mistake worth being relaxed about.
local function loadTimer(rom)
  local path = timerPath(rom)
  if not path or not EMU.readFile then
    return
  end
  local called, text = pcall(EMU.readFile, path)
  if not called or type(text) ~= "string" then
    return
  end
  local savedRom, frames, state, stamp, chaos, apGoal =
      text:match("^([^\t]*)\t(%d+)\t(%a+)\t?(%d*)\t?(%d*)\t?(%d*)")
  if not savedRom or savedRom ~= rom then
    return
  end
  runFrames = tonumber(frames) or 0
  runFinished = (state == "done")
  runRunning = (state == "running")
  -- Ahead of the early return below: a cartridge whose clock never started can
  -- still have had its Chaos killed. "done" stands in for the field on files
  -- written before it existed, where a finished clock is the only record.
  chaosSeen = (chaos == "1") or runFinished
  -- Absent on files written before this field existed, which reads as false --
  -- the pre-existing behaviour, and the safe way round: the latch keeps
  -- speaking until the flag bit is seen for itself.
  goalBitSeen = (apGoal == "1")
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
  chaosSeen, goalBitSeen = false, false
  loadTimer(rom)
end

-- Watch for a new game. Start only: once a run is going, a mid-run save load
-- cannot satisfy freshGame, so loading a save resumes rather than restarts.
--
-- A finished run does not close the cartridge out either. Practice runs, a
-- second attempt on race night, a reset after a bad start past the goal -- all
-- of them are a new game on the same seed, and only a new game can get here,
-- so the finished clock is replaced rather than frozen for good.
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
  if runRunning or not runRom or runRom == "" then
    startScans = 0
    return
  end
  local mem = readStartMem()
  if not inGame(mem) or looksUninitialised(mem) or not freshGame(mem) then
    startScans = 0
    return
  end
  startScans = startScans + 1
  if startScans < GUARD_STABLE_SCANS then
    return
  end
  -- Not zero: the scans above spanned four tenths of a second of a real run,
  -- and the clock is advertised as exact at the split.
  runFrames, runRunning, runFinished = START_DEBOUNCE_FRAMES, true, false
  chaosSeen, goalBitSeen = false, false
                      -- a new game on a finished seed is a fresh run, not a
                      -- clock that stops on its first frame
  EMU.log("new game -- run clock started")
  saveTimer()
end

-- Watch for the Chaos kill in the battle engine, and latch it. Runs every
-- frame and ahead of the clock's own gate, because the tracker's Chaos check
-- needs this whether or not the run was ever timed -- a seed picked up from a
-- mid-run save never arms the clock at all.
--
-- Cheap by construction: three byte reads, and none of them once the latch is
-- set. The battle guard is tested first because it is false almost always.
local function pollChaosKill()
  if chaosSeen or not EMU.readByte then
    return
  end
  if not BATTLE_RUNNING[EMU.readByte(MEM_ADDR + GUARD_B_OFF)] then
    return
  end
  if EMU.readByte(BTL_FORMATION_ADDR) ~= CHAOS_FORMATION then
    return
  end
  if EMU.readByte(BTL_RESULT_ADDR) ~= CHAOS_RESULT then
    return
  end
  chaosSeen = true
  EMU.log("Chaos is down")
  -- Written down here rather than left to the clock's checkpoint, which only
  -- runs while the clock is running. Once per cartridge, so the cost is not
  -- worth weighing against losing the kill to a power cycle.
  saveTimer()
end

-- Both ways the cartridge can say the goal is reached: the flag bit, which only
-- an Archipelago seed ever sets, and the battle read above, which is all a solo
-- seed has. On an Archipelago seed they land on the same frame.
--
-- They are not simply OR'd, because they walk back differently. The flag bit is
-- part of the save, so on a seed that carries it, loading a save from before
-- the fight is the cartridge saying Chaos is alive -- and the latch must not
-- argue. The latch is for the seeds where nothing in the save remembers: it
-- speaks only until the bit has been seen set once on this cartridge, which is
-- the moment we learn this is a seed that keeps its own record.
local function goalReached(flagByte)
  if type(flagByte) == "number" and (flagByte & 0x02) ~= 0 then
    if not goalBitSeen then
      -- Written down the moment we learn it, and only then: without this a
      -- power cycle would come back with the latch in charge again on a seed
      -- whose save is the better witness.
      goalBitSeen = true
      saveTimer()
    end
    return true
  end
  if goalBitSeen then
    return false
  end
  return chaosSeen
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
    if not runRunning then
      pollForStart()
    end
  end

  -- Before the gate below: the latch has to be kept for the tracker even on a
  -- cartridge whose clock never started.
  pollChaosKill()

  if not runRunning then
    return
  end
  runFrames = runFrames + 1

  -- The split is sampled here rather than on the 10Hz scan so it lands on the
  -- frame the goal actually arrives. Four bytes at worst, not the whole 0x300
  -- window.
  local byte = EMU.readByte and EMU.readByte(MEM_ADDR + FLAGS_OFF + GOAL_BYTE)
  if goalReached(byte) then
    runRunning, runFinished = false, true
    local stamp = (type(os) == "table" and os.date) and os.date("%Y-%m-%d %H:%M:%S") or "?"
    local _, romName = timesPath()
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

-- Everything sendState diffs, in one place. `ready` is the only field that
-- differs between the four calls below, which is why it is the argument.
local function currentState(ready)
  return {
    mem = lastMem, ready = ready, goal = lastGoal, map = lastMap,
    rom = lastRom, flags = lastFlags, art = lastArt, shop = lastShop,
    rolls = lastRolls,
  }
end

local function scan()
  local mem = readMem()
  lastRom = readRom()
  lastFlags = readFlags(lastRom)
  lastRolls = readRolls(lastRom)
  lastArt = readArt(lastRom)

  if not inGame(mem) or looksUninitialised(mem) then
    invalidate()
    sendState(currentState(false))
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
    sendState(currentState(false))
    return
  end

  lastMem = mem
  lastGoal = goalReached(at(mem, FLAGS_OFF + GOAL_BYTE))
  lastShop = shopItemBought(mem, lastRom)
  lastMap = readMap()
  noteRunProgress(lastRom, lastGoal)
  sendState(currentState(true))
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
  sent = {}
  -- A client can connect and Sync before the first scan tick, and the very
  -- first thing it needs is which cartridge this is.
  lastRom = readRom()
  lastFlags = readFlags(lastRom)
  lastRolls = readRolls(lastRom)
  lastArt = readArt(lastRom)
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
        sendState(currentState(isReady()), true)
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
