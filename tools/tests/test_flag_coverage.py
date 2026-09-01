"""Every flag FFR's logic consults is either modelled or declared not modelled.

This is the test `docs/FLAG_COVERAGE.md` asked for at the end of itself. The
page is compiled by hand from two greps over FFR's own source, and a page
compiled by hand from a file can miss a flag in that file: it missed
`FiendsRefights` and `ShortToFRFiendsRefights`, both of which decide whether the
four fiends stand in the Temple of Fiends Revisited, and it missed them for as
long as the page has existed. Running the greps is the whole check.

Two sets. **Consulted** comes from FFR's C# with the two patterns the page
publishes, byte for byte, so the page and the test cannot drift apart.
**Named** comes from `scripts/autotracking/flag_mapping.lua`.

The named half is extracted *structurally* rather than by grepping the file for
a quoted string, and the difference is not cosmetic. A whole-file grep counts a
flag mentioned in a comment as modelled -- which is this pack's oldest failure
shape, something that looks compared and is not. It also gets the answer wrong
in the other direction today: `GameMode` is read as `flags.GameMode` and appears
as a quoted literal nowhere, so a grep calls it unnamed when it is named. The
two readings disagree by exactly that one flag.

Needs the FFR checkout; without one this skips rather than passing quietly.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import ffr_source                                              # noqa: E402

VERSION = "4-9-7"

# The two greps docs/FLAG_COVERAGE.md publishes. Kept as the page spells them.
#
#   grep -ohE 'victoryConditions\.[A-Za-z]+' FF1Lib/Sanity/*.cs
#   grep -ohE '\bflags\.[A-Z][A-Za-z]+' \
#       FF1Lib/{OverworldMap,NPCs,MetroidVaniaMap,TempleOfFiends}.cs
#
# The first is what SanityCheckerV2 asks directly; the second is the flags that
# reach it by rewriting the ROM, which the checker then walks without ever
# seeing the flag. The pack needs a code for the second kind and usually not for
# the first.
CONSULTED_SANITY = re.compile(r"victoryConditions\.([A-Za-z]+)")
CONSULTED_MAPS = re.compile(r"\bflags\.([A-Z][A-Za-z]+)")
MAP_FILES = ["OverworldMap.cs", "NPCs.cs", "MetroidVaniaMap.cs",
             "TempleOfFiends.cs"]

# Every place flag_mapping.lua can name an FFR flag, and there are four.
# TOGGLES and NOT_MODELLED carry `ffr = "..."`; a PROGRESSIVE names its sources
# inside its stage closure via `get("...")`, which is why it has no `ffr` field
# and why tests/test_flags.lua skips it for the same reason; `ffrFlag("...")` is
# the runtime accessor the logic calls; and `flags.Name` is the apply path.
NAMED = [
    re.compile(r'ffr\s*=\s*"([A-Za-z]+)"'),
    re.compile(r'get\("([A-Za-z]+)"\)'),
    re.compile(r'ffrFlag\("([A-Za-z]+)"'),
    re.compile(r"\bflags\.([A-Z][A-Za-z]+)"),
]

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s: got %r, want %r" % (label, got, want))
    print("%s %s" % ("ok  " if got == want else "FAIL", label))


def consulted(src):
    """The flag names FFR's logic reads, off a checkout."""
    found = set()
    sanity = os.path.join(src, "FF1Lib", "Sanity")
    for name in sorted(os.listdir(sanity)):
        if name.endswith(".cs"):
            with open(os.path.join(sanity, name), encoding="utf-8",
                      errors="replace") as handle:
                found |= set(CONSULTED_SANITY.findall(handle.read()))
    for name in MAP_FILES:
        path = os.path.join(src, "FF1Lib", name)
        with open(path, encoding="utf-8", errors="replace") as handle:
            found |= set(CONSULTED_MAPS.findall(handle.read()))
    return found


def uncommented(text):
    """`text` with its Lua comments removed and its string literals kept.

    Stripping is what makes the structural reading honest: without it a name
    parked in a commented-out entry still matches `ffr = "..."` and reads as
    modelled, which is the exact failure this test exists to catch. Quote state
    is tracked because `--` occurs inside the `why` strings in NOT_MODELLED, and
    cutting at the first one would eat the rest of a line that is code.
    """
    out, i, n = [], 0, len(text)
    quote = None
    while i < n:
        c = text[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "\"'":
            quote = c
            out.append(c)
            i += 1
            continue
        if text.startswith("--[[", i):
            end = text.find("]]", i)
            i = n if end < 0 else end + 2
            continue
        if text.startswith("--", i):
            end = text.find("\n", i)
            i = n if end < 0 else end
            continue
        out.append(c)
        i += 1
    return "".join(out)


def named(text):
    """The flag names flag_mapping.lua actually acts on."""
    found = set()
    live = uncommented(text)
    for pattern in NAMED:
        found |= set(pattern.findall(live))
    return found


src = ffr_source.checkout(VERSION)
if src is None:
    print("SKIP  " + ffr_source.skip_reason(VERSION))
    sys.exit(0)

mapping_path = os.path.join(PACK, "scripts/autotracking/flag_mapping.lua")
mapping = open(mapping_path, encoding="utf-8").read()

reads = consulted(src)
models = named(mapping)

# -------------------------------------------------------------- the check

print("-- coverage")
missing = sorted(reads - models)
check("every flag FFR's logic consults is named in flag_mapping.lua",
      missing, [])
for name in missing:
    print("     unmodelled: " + name)
print("     (%d consulted, %d of them named)" % (len(reads), len(reads & models)))

# -------------------------------------------------------------- not vacuous
#
# Both halves of a set difference can be empty for the wrong reason: a grep that
# matches nothing and a file that names everything look identical from here.
# These say the inputs are real before the difference above is believed.

print("-- the inputs are real")
check("the C# grep found the flags the page counted", len(reads) >= 50, True)
check("Sanity's own ten are in there", "AirBoat" in reads, True)
check("the map rewrites are in there", "MapSardasForest" in reads, True)
check("flag_mapping names something", len(models) >= 30, True)
check("a modelled flag reads as named", "MapSardasForest" in models, True)

# -------------------------------------------------------------- it can bite
#
# A check that cannot fail is worthless, which this repo has learned twice
# (tests/test_maps.lua check 6, and test_crop's grouping of its own output). So
# the two ways this one could go quiet are demonstrated here rather than
# asserted about.

print("-- and it bites")
gutted = mapping.replace('ffr = "MapSardasForest"', 'ffr = "NotAFlagAtAll"', 1)
check("dropping an entry is reported",
      "MapSardasForest" in (reads - named(gutted)), True)

# The one a whole-file quoted grep would pass: the name is still in the file,
# still quoted, and no longer does anything.
commented = mapping.replace(
    '  { ffr = "MapSardasForest"',
    '  -- { ffr = "MapSardasForest"\n  { ffr = "NotAFlagAtAll"', 1)
check("a name left only in a comment is not named",
      "MapSardasForest" in (reads - named(commented)), True)
check("and the comment really is still in the file",
      '"MapSardasForest"' in commented, True)

for f in fails:
    print("     " + f)
print("ALL PASS" if not fails else "%d FAILED" % len(fails))
sys.exit(1 if fails else 0)
