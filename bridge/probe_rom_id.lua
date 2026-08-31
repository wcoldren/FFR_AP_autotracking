-- Step 1 for the stale-override branch: what can the bridge use to tell which
-- cartridge the drawn maps were drawn for?
--
-- `.regen_cache.json` records a sha256, which the bridge cannot compute.
-- `docs/IDEAS.md` concluded from that "the bridge has no hash", and proposed
-- recording the seed and flag strings instead. That conclusion is worth one
-- measurement before it becomes a design: readRom() already spends
-- `emu.getRomInfo().fileSha1Hash` as the cartridge id, so the bridge does have
-- a hash. The open question is what it covers -- the .nes file on disk, or the
-- PRG and CHR banks after Mesen has parsed the 16-byte iNES header off. Only
-- the first can be reproduced by a script that has the file and nothing else.
--
-- Measures only. Writes one file and runs no command.
--
-- Load in Mesen: Debug -> Script Window -> open this file -> Run, with any FFR
-- cartridge in the slot -- it identifies whichever one that is. Output goes to
-- the log and to /tmp/ffr_rom_id.txt, so it survives the window being closed.

local OUT = "/tmp/ffr_rom_id.txt"
local FLAGS_ROM_OFF, FLAGS_ROM_LEN = 0x7BE00, 512   -- as the bridge reads them

local lines = {}

local function say(text)
  emu.log(text)
  lines[#lines + 1] = text
end

say("=== rom id probe ===")

-- Every field, not the two the bridge happens to read: the hash that covers
-- the file may not be the one already in use.
local ok, info = pcall(emu.getRomInfo)
if not ok or type(info) ~= "table" then
  say("emu.getRomInfo() did not return a table")
else
  local keys = {}
  for k in pairs(info) do
    keys[#keys + 1] = tostring(k)
  end
  table.sort(keys)
  for _, k in ipairs(keys) do
    say(string.format("%-18s = %s", k, tostring(info[k])))
  end
end

-- The FFRInfo record, which is the fallback comparator if the hash turns out
-- to cover something a script cannot reproduce. The bridge already reads Flags
-- and Version off this; Seed is the field it does not.
--
-- Read through emu.read(.., PRG) exactly as EMU.readRom does, so a failure
-- here is a failure the bridge would have had too.
local prg = emu.memType and emu.memType.nesPrgRom or nil
if not prg then
  say("no emu.memType.nesPrgRom -- cannot read the FFRInfo record")
else
  local bytes = {}
  for i = 0, FLAGS_ROM_LEN - 1 do
    local b = emu.read(FLAGS_ROM_OFF + i, prg)
    if type(b) ~= "number" then
      break
    end
    bytes[#bytes + 1] = string.char(b & 0xFF)
  end
  local raw = table.concat(bytes)
  if raw:sub(1, 7) ~= "FFRInfo" then
    say("no FFRInfo record at 0x7BE00 -- not an FFR cartridge")
  else
    local record = raw:match("^[^%z]*")
    say(string.format("%-18s = %s", "FFRInfo Seed", tostring(record:match("|Seed: ([^|]+)"))))
    say(string.format("%-18s = %s", "FFRInfo Version", tostring(record:match("|Version: ([A-Za-z0-9%.%-]+)"))))
    say(string.format("%-18s = %s", "FFRInfo Flags", tostring(record:match("|Flags: ([A-Za-z0-9%.%-]+)"))))
  end
end

say("")
say("Then, in a shell, against the path printed above:")
say("  shasum -a 1 <path>")
say("A match means the cache can record that sha1 and the bridge can check it.")

local f = io.open(OUT, "w")
if f then
  f:write(table.concat(lines, "\n") .. "\n")
  f:close()
  emu.log("wrote " .. OUT)
else
  emu.log("could not write " .. OUT .. " -- read the log instead")
end
