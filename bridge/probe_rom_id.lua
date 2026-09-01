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
-- It does not read the FFRInfo record. `ffr_uat_bridge.lua` is the one reader
-- of that record on the Lua side, so a second parse here would be a second
-- statement of where the record sits and what its fields are called -- the
-- duplication that `9148fdd` removed on the Python side. What it attaches
-- with is not all three fields: `readFlags` logs "seed flags: FFR <version>,
-- seed <seed>, <n> characters", so the version and the seed are in the log
-- and the flag string is there only as a length. The string itself reaches
-- the pack as `ff1/flags`, not through the log. Run the bridge for those and
-- this for the hash.
--
-- Load in Mesen: Debug -> Script Window -> open this file -> Run, with any FFR
-- cartridge in the slot -- it identifies whichever one that is. Output goes to
-- the log and to /tmp/ffr_rom_id.txt, so it survives the window being closed.

local OUT = "/tmp/ffr_rom_id.txt"
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
