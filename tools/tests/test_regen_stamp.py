"""The stamp has to be readable by the thing that reads it, and able to say
"I cannot tell".

Needs no cartridge; the two it uses are synthesised, because what is under test
is the identity written down and not the art.

`.regen_stamp` exists for one reader -- Mesen's Lua, which has no JSON parser
and no sha256 -- so this file is as much a test of the format as of the code.
The three ways it could quietly stop working:

  - the line format drifts and the one pattern the bridge matches with stops
    matching, silently, because a bridge that finds no lines and a bridge that
    finds no mismatch both say nothing;
  - regenerating one mode drops the other mode's line, so a cartridge that has
    perfectly good art reads as having none;
  - a mode with no identity is left out instead of saying `unknown`, which
    turns "this file cannot tell you" into "your art is for another seed".
"""
import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import regen_maps                                              # noqa: E402

# The bridge matches one pattern per line. Written here as Python's spelling of
# Lua's `^(%S+) (%S+) (%S+)$` so that changing the format breaks this test
# rather than the emulator.
LINE = re.compile(r"^(\S+) (\S+) (\S+)$")


def rows(text):
    """Every line the bridge would take, as (mode, sha1, ffr)."""
    out = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        m = LINE.match(line)
        assert m, "line does not match the pattern the bridge uses: %r" % line
        out[m.group(1)] = (m.group(2), m.group(3))
    return out


def cart(seed="3B7E1C8A", flags="omlInJg6XzAlwLPjeZz.e4gJ", version="4-9-7",
         filler=b"\x00"):
    """A cartridge-shaped buffer carrying an FFRInfo record and nothing else.

    Full size because entrance_graph.Rom refuses anything shorter -- the
    extended teleport tables live near the end and a truncated image would read
    as another cartridge's bytes rather than as an error.
    """
    data = bytearray(filler * 524304)
    data[0:4] = b"NES\x1a"
    record = ("FFRInfo|Seed: %s|OW Seed: none|Res. Pack Hash: none|"
              "Flags: %s|Version: %s" % (seed, flags, version)).encode()
    at = 0x7BE00 + 16
    data[at:at + len(record)] = record
    data[at + len(record)] = 0
    return bytes(data)


# ---- 1. the record is read, and the seed alone is not the identity

std = regen_maps.cartridge_id(cart(), "<std>")
assert std["ffr"] == "4-9-7|3B7E1C8A|omlInJg6XzAlwLPjeZz.e4gJ", std
assert std["sha1"] == hashlib.sha1(cart()).hexdigest()

# The three 4.9.7 oracle cartridges really do share seed 3B7E1C8A and differ
# only in their flags, so an identity built on the seed would call them one
# cartridge. This is the check that says it does not.
drydock = regen_maps.cartridge_id(cart(flags="omlInJg6XzA6ypn7hzElNF7f"), "<dry>")
assert drydock["ffr"] != std["ffr"], "same seed, different flags, same identity"
assert drydock["sha1"] != std["sha1"]

# A cartridge with no FFRInfo record at all -- a vanilla image -- still has a
# sha1, and says so about the half it cannot answer.
plain = bytearray(b"\xEA" * 524304)
plain[0:4] = b"NES\x1a"
vanilla = regen_maps.cartridge_id(bytes(plain), "<vanilla>")
assert vanilla["ffr"] == regen_maps.STAMP_UNKNOWN, vanilla
assert len(vanilla["sha1"]) == 40

# ---- 2. both modes survive a run of one

modes = {"std": dict(std), "nov": {"sha1": "b" * 40, "ffr": "4-9-2|F2585541|omlY"}}
got = rows(regen_maps.stamp_text(modes))
assert set(got) == {"std", "nov"}, got
assert got["std"] == (std["sha1"], std["ffr"])
assert got["nov"] == ("b" * 40, "4-9-2|F2585541|omlY")

# ---- 3. a mode with no identity says so rather than vanishing

got = rows(regen_maps.stamp_text({"std": dict(std), "nov": {"rom": "old-style"}}))
assert "nov" in got, "a mode with no identity was left out: %r" % (got,)
assert got["nov"] == (regen_maps.STAMP_UNKNOWN, regen_maps.STAMP_UNKNOWN), got
# And `unknown` is not something a real identity could ever be mistaken for.
assert regen_maps.STAMP_UNKNOWN not in std.values()

# ---- 4. write_stamp says what happened, and only when something did

import tempfile                                                # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    assert regen_maps.write_stamp(tmp, modes) == "missing", "first write reported no change"
    assert regen_maps.write_stamp(tmp, modes) is None, "rewrote an identical stamp"
    # A stamp that is present but wrong is a different event from a deleted
    # one, and the caller prints a different line for each; a run that says
    # "rewrote the missing stamp" over a hand-edited file is telling the user
    # something that did not happen.
    moved = {"std": dict(std, sha1="c" * 40), "nov": modes["nov"]}
    assert regen_maps.write_stamp(tmp, moved) == "differs", "a changed identity went unwritten"
    with open(os.path.join(tmp, regen_maps.STAMP_NAME)) as f:
        assert rows(f.read())["std"][0] == "c" * 40

# ---- 5. an unwritable override does not take the run down with it

# The stamp is a record of what was drawn, not one of the drawings. The path
# that reaches it most often is the one that has just finished saying it has
# nothing to do, and turning that into a traceback would be a poor trade for a
# file whose absence readArt already handles.
with tempfile.TemporaryDirectory() as tmp:
    gone = os.path.join(tmp, "not-here")
    assert regen_maps.write_stamp(gone, modes) is None, "wrote into a directory that is not there"

print("stamp: format, both modes, unknown and write_stamp all hold")
