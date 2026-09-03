"""Every flag FFR's logic consults is either modelled or declared not modelled.

This is the test `docs/FLAG_COVERAGE.md` asked for at the end of itself. The
page is compiled by hand from two greps over FFR's own source, and a page
compiled by hand from a file can miss a flag in that file: it missed
`FiendsRefights` and `ShortToFRFiendsRefights`, both of which decide whether the
four fiends stand in the Temple of Fiends Revisited, and it missed them for as
long as the page has existed. Running the greps is the whole check.

Two sets. **Consulted** comes from FFR's C# with the two patterns the page
publishes, byte for byte, so the page and the test cannot drift apart.
**Named** comes from `scripts/autotracking/flag_mapping.lua`, plus the two
files that call `ffrFlag()` -- `scripts/logic.lua` and
`scripts/autotracking/maptab.lua`. The mapping table is not the only place a
flag is read: OrbsRequiredCount and OrbsRequiredMode are read in logic.lua and
appear in the mapping table nowhere.

The named half is extracted *structurally* rather than by grepping the files for
a quoted string, and the difference is not cosmetic. A whole-file grep counts a
flag mentioned in a comment as modelled -- which is this pack's oldest failure
shape, something that looks compared and is not. Comments are stripped, and so
are the `why` and `measure` reasons, which are prose that cites identifiers for
a reader rather than code that acts on them. It also gets the answer wrong in
the other direction today: `GameMode` is read as `flags.GameMode` and appears as
a quoted literal nowhere, so a grep calls it unnamed when it is named.

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

# Every place flag_mapping.lua can name an FFR flag. TOGGLES and NOT_MODELLED
# carry `ffr = "..."`; a PROGRESSIVE names its sources inside its stage closure
# via `get("...")`, which is why it has no `ffr` field and why
# tests/test_flags.lua skips it for the same reason; and `flags.Name` is the
# apply path.
NAMED = [
    re.compile(r'ffr\s*=\s*"([A-Za-z]+)"'),
    re.compile(r'get\("([A-Za-z]+)"\)'),
    re.compile(r"\bflags\.([A-Z][A-Za-z]+)"),
]

# The fourth place is not in flag_mapping.lua at all. `ffrFlag("...")` is the
# runtime accessor, and every call to it lives somewhere else: `logic.lua` reads
# OrbsRequiredCount and OrbsRequiredMode, `maptab.lua` reads ShardHunt and
# ChestsKeyItems. Scanning only flag_mapping.lua for that pattern found nothing,
# which is a check that cannot fire -- and would have reported a flag modelled
# solely through `ffrFlag("X")` in logic.lua as unmodelled, a failure with no
# way to satisfy it but a redundant NOT_MODELLED entry.
#
# Only this one pattern is applied to the extra files, deliberately. `flags.X`
# and `get("X")` are shapes an unrelated local could wear outside the mapping
# table; `ffrFlag("X")` is unambiguous wherever it appears.
NAMED_ANYWHERE = re.compile(r'ffrFlag\(\s*"([A-Za-z]+)"')
ALSO_NAMES = [
    "scripts/logic.lua",
    "scripts/autotracking/maptab.lua",
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


_FIELD = re.compile(r"\b(?:why|measure)\s*=\s*")


def unprosed(text):
    """`text` with the `why =` / `measure =` reason strings emptied.

    Those reasons are prose, and prose names things: they cite C# call sites,
    quote FFR identifiers, and point at functions in other files of this pack.
    Matched along with the code they sit beside, a reason that happened to say
    `flags.SomeOtherFlag` would mark that flag modelled with nothing modelling
    it -- the same "looks compared and is not" shape the structural reading
    exists to prevent, arriving through the one door it left open. Nothing does
    that today; the entries only cite C# paths and line numbers. It is closed
    now rather than after a reason is written that trips it, because the miss
    would be silent.

    A value is a chain of string literals joined by `..`, so the chain is
    consumed as a unit and replaced by an empty string. Anything that is not
    that shape is left exactly as it was.
    """
    out, i, n = [], 0, len(text)
    while i < n:
        m = _FIELD.search(text, i)
        if m is None:
            out.append(text[i:])
            break
        out.append(text[i:m.end()])
        j, consumed = m.end(), False
        while j < n:
            c = text[j]
            if c in " \t\r\n":
                j += 1
                continue
            if text.startswith("..", j):
                # Only a concatenation onto another literal continues the chain.
                k = j + 2
                while k < n and text[k] in " \t\r\n":
                    k += 1
                if k < n and text[k] in "\"'":
                    j = k
                    continue
                break
            if c in "\"'":
                quote, j = c, j + 1
                while j < n:
                    if text[j] == "\\":
                        j += 2
                        continue
                    if text[j] == quote:
                        j += 1
                        break
                    j += 1
                consumed = True
                continue
            break
        out.append('""' if consumed else text[m.end():j])
        i = j
    return "".join(out)


def named(text, elsewhere=()):
    """The flag names the pack actually acts on.

    `text` is flag_mapping.lua, read with all of NAMED; `elsewhere` is the
    other pack files, read with NAMED_ANYWHERE alone. Both are decommented and
    deprosed first, so a name that survives is a name in a code position.
    """
    found = set()
    live = unprosed(uncommented(text))
    for pattern in NAMED:
        found |= set(pattern.findall(live))
    for other in elsewhere:
        found |= set(NAMED_ANYWHERE.findall(unprosed(uncommented(other))))
    return found


def read(*parts):
    with open(os.path.join(PACK, *parts), encoding="utf-8") as handle:
        return handle.read()


mapping = read("scripts/autotracking/flag_mapping.lua")

# ------------------------------------------------ the tally the page prints
# `docs/FLAG_COVERAGE.md` publishes a per-status tally of NOT_MODELLED and a
# total in the sentence above it, and nothing held either one: the sentence
# said 31 while the table a line beneath it summed to 32, because the only
# thing keeping the two in step was whoever last edited both.
#
# Read with the comments stripped, for the same reason the naming pass is: a
# status parked in a commented-out entry is not a row on that page. This runs
# before the checkout is asked for, since holding a page against the mapping
# needs neither FFR nor a cartridge.
TALLY_LINE = re.compile(r"^ {4}((?:[a-z]+ \d+ *)+)$", re.M)
TALLY_PAIR = re.compile(r"([a-z]+) (\d+)")
SAYS_TOTAL = re.compile(r"tally below is (\d+) rather than")
STATUS = re.compile(r'status = "([a-z]+)"')

live = uncommented(mapping)
entries = live[live.index("NOT_MODELLED"):live.index("toggles = TOGGLES")]
real_tally = {}
for status in STATUS.findall(entries):
    real_tally[status] = real_tally.get(status, 0) + 1

page = read("docs", "FLAG_COVERAGE.md")
row = TALLY_LINE.search(page)
said_tally = ({k: int(v) for k, v in TALLY_PAIR.findall(row.group(1))}
              if row else {})
said_total = SAYS_TOTAL.search(page)

print("-- the page's own tally")
check("the per-status tally the page prints matches the mapping",
      said_tally, real_tally)
check("and the total its sentence gives matches that tally",
      int(said_total.group(1)) if said_total else None,
      sum(real_tally.values()))

src = ffr_source.checkout(VERSION)
if src is None:
    print("SKIP  " + ffr_source.skip_reason(VERSION))
    # The rows above needed neither FFR nor a cartridge, so a skip here must
    # not swallow them. Exiting 0 over a real failure is the silent pass this
    # file spends its length arguing against.
    for f in fails:
        print("     " + f)
    sys.exit(1 if fails else 0)

others = [read(rel) for rel in ALSO_NAMES]

reads = consulted(src)
models = named(mapping, others)

# -------------------------------------------------------------- the check

print("-- coverage")
missing = sorted(reads - models)
check("every flag FFR's logic consults is named in the pack",
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
# The extra files have to contribute, or NAMED_ANYWHERE is decoration: these
# two are read through ffrFlag() in logic.lua and appear in flag_mapping.lua
# nowhere.
check("logic.lua's own ffrFlag reads are named",
      {"OrbsRequiredCount", "OrbsRequiredMode"} <= models, True)
check("and flag_mapping.lua alone does not name them",
      {"OrbsRequiredCount", "OrbsRequiredMode"} & named(mapping), set())

# -------------------------------------------------------------- it can bite
#
# A check that cannot fail is worthless, which this repo has learned twice
# (tests/test_maps.lua check 6, and test_crop's grouping of its own output). So
# the two ways this one could go quiet are demonstrated here rather than
# asserted about.

print("-- and it bites")
gutted = mapping.replace('ffr = "MapSardasForest"', 'ffr = "NotAFlagAtAll"', 1)
check("dropping an entry is reported",
      "MapSardasForest" in (reads - named(gutted, others)), True)

# The one a whole-file quoted grep would pass: the name is still in the file,
# still quoted, and no longer does anything.
commented = mapping.replace(
    '  { ffr = "MapSardasForest"',
    '  -- { ffr = "MapSardasForest"\n  { ffr = "NotAFlagAtAll"', 1)
check("a name left only in a comment is not named",
      "MapSardasForest" in (reads - named(commented, others)), True)
check("and the comment really is still in the file",
      '"MapSardasForest"' in commented, True)

# And the door unprosed() closes: the name is gone from every code position and
# survives only inside another entry's reason, where it means nothing.
prose = gutted.replace(
    'why = "starting inventory (FF1Lib',
    'why = "as flags.MapSardasForest is, starting inventory (FF1Lib', 1)
check("a name left only in a reason is not named",
      "MapSardasForest" in (reads - named(prose, others)), True)
check("and the reason really does still say it",
      "flags.MapSardasForest" in prose, True)

# unprosed() has to leave the code alone as well as blank the prose, or the
# check above would pass on a function that emptied the file.
check("deprosing keeps the entry it sits beside",
      'ffr = "FreeLute"' in unprosed(mapping), True)
check("and empties the reason",
      "starting inventory" in unprosed(mapping), False)

for f in fails:
    print("     " + f)
print("ALL PASS" if not fails else "%d FAILED" % len(fails))
sys.exit(1 if fails else 0)
