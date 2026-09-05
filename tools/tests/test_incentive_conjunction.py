#!/usr/bin/env python3
"""Grade the gold rings against what FFR actually incentivized.

check_logic grades the pack's access rules against FFR's reachability. Nothing
graded the *rings*, and they answer to a different part of FFR: the incentive
pool, which the Archipelago export publishes as `priority_locations`. That gap
is why two flags could be modelled by one conjunct each for as long as they
were -- `test_flag_coverage`'s `consulted()` greps FFR's reachability logic, and
a flag that only ever moves a ring never appears in it.

So this asks the one question that catches the whole family: for every slot the
pack would ring on this seed's flags, did FFR put that location in the incentive
pool? Four ways round, because the family has four shapes:

  1. the ring        -- pack rings it iff FFR incentivized it
  2. existence       -- a slot FFR did not create is not shown at all
  3. ghosts          -- nothing is ringed for a location the seed does not have
  4. coverage        -- every incentivized location the pack knows has a row

What it cost to have none of this: seven slots ringed gold on a seed FFR
dropped them from, on each of two flags, for as long as the pack has had rings.

Reads exports only -- no ROM. `export_diff.read` carries the seed's own decoded
flags beside its rules, locations and priority pool, and `check_logic.flag_codes`
turns those into the codes the board would be showing -- defaults included, so a
flag the generator rolled predicts what a fresh grid shows rather than off. The
prediction is the pack's own reading rather than a second copy of it here.

Usage:
    tools/tests/test_incentive_conjunction.py

Skips without the corpus or without an Archipelago checkout, like the pack's
other seed-tree tests. FF1_SEEDS and FF1_WORLD override the paths.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)

sys.path.insert(0, TOOLS)

import check_logic                      # noqa: E402
import export_diff                      # noqa: E402
import incentive_slots                  # noqa: E402

SEEDS = os.environ.get("FF1_SEEDS", os.path.expanduser("~/repos/AP/seeds/ff1"))
WORLD = os.environ.get("FF1_WORLD", "")

# Slot rows that are not Archipelago locations, and why. Named rather than
# counted: a row silently dropping out of the comparison is how this check would
# stop biting, and the one left is a finding in its own right.
#
#   Cardia - Hoard  Bahamut's Cave has no location of its own; the hoard moves
#                   the Cardia chest tiles into it. docs/ORACLE.md has it.
#
# `@Melmond/Dr Unne` was the other one until 2026-09-03, and is not waived here
# now because it is not a row: FFR has no IncentivizeUnne, so the pack's
# incentive section for him was removed rather than excused. docs/ISSUES.md.
NOT_AP_LOCATIONS = {
    "@Bahamut's Cave/Cardia Incentive - Hoard",
}

# What the pool gate is for, on the cartridges that show it.
#
# A slot whose incentive name the seed did not use: the pack's row points at an
# id the pool does not contain, so the flags speak for a slot the seed has not
# got. notail's Sea Shrine incentives are `Incentive 1` and `Incentive 2`, and
# there is no `Incentive Major` -- FFR incentivized nothing in the Sea Shrine
# there, and the pack rang it gold until 2026-09-05. docs/ISSUES.md.
#
# Named and asserted rather than waived, and that is the difference this
# constant carries. A waiver says "known, ignore it" and goes on saying it after
# the finding is fixed; this says "the gate has something to bite on here", so
# the row below fails if the corpus stops showing the case at all -- which is
# how a gate quietly stops being tested. The ghost row underneath it is what
# says the gate holds.
#
# There were three. The caravan slot left in 2026-09-03's conjunction work, when
# it got a gate on its own existence. `hoarddockbridge497`'s Cardia chest left
# the same day with the cardia split, and left differently: it has stopped being
# reachable rather than being fixed. That row was only ever a ghost because the
# pack ringed a Cardia slot on a hoard seed, and it no longer does -- the ring is
# decided by IncentivizeCardia, which that cartridge has off, so the comparison
# ends before the missing id is looked for. A seed that incentivized Cardia *and*
# rolled the hoard would show it again.
DEMONSTRATED_GHOSTS = [
    ("notail", "Sea Shrine Mermaids (B1) - Incentive Major"),
]

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s: got %r, want %r" % (label, got, want))
    print("%s %s" % ("ok  " if got == want else "FAIL", label))


def exports():
    """(slug, read export) for every cartridge in both corpora."""
    for corpus in sorted(os.listdir(SEEDS)):
        root = os.path.join(SEEDS, corpus)
        if not corpus.startswith("oracle-") or not os.path.isdir(root):
            continue
        for slug in sorted(os.listdir(root)):
            here = os.path.join(root, slug)
            if not os.path.isdir(here):
                continue
            if not [f for f in os.listdir(here) if f.endswith(".yaml")]:
                continue        # the shared `flags` directory holds presets
            yield slug, export_diff.read(export_diff.find_export(here))


def main():
    if not os.path.isdir(SEEDS):
        print("SKIP  no seed tree at %s -- set FF1_SEEDS" % SEEDS)
        return 0
    paths = check_logic.ap_location_paths(PACK, WORLD or None)
    if not paths:
        print("SKIP  no Archipelago worlds/ff1 -- set FF1_WORLD")
        return 0

    rows = incentive_slots.collect()
    by_name = {}
    unmapped = set()
    for row in rows:
        # A path is "@node/section"; ap_location_paths gives name -> path.
        for name, path in paths.items():
            if path == row["path"][1:]:
                by_name[name] = row
                break
        else:
            if not row["path"].startswith("@I: "):
                unmapped.add(row["path"])

    print("-- the rows this can speak for")
    check("board rows that are Archipelago locations", len(by_name), 25)
    check("and the one that is not is the known one", unmapped,
          NOT_AP_LOCATIONS)

    seen = 0
    wrong, ungated, missing = [], [], []
    for slug, e in exports():
        if not e.get("priority") or not e.get("locations"):
            continue
        seen += 1
        codes = check_logic.flag_codes(e["flags"], PACK)
        noverworld = e["flags"].get("GameMode") == 2
        for name, row in by_name.items():
            # Two questions in the order the pack asks them, and the second is
            # not a flag. FFR's IncentivizeNerrick ends `&& !NoOverworld`; every
            # other slot is its flags and nothing else -- and then the seed has
            # to contain the location those flags speak for, which is what
            # scripts/incentives.lua reads out of the Archipelago pool.
            flags_say = (all(f in codes for f in row["flags"])
                         and not (row.get("standardOnly") and noverworld))
            present = name in e["locations"]
            rings = flags_say and present
            if not present:
                # `ungated` is what the flags alone would have rung: the case
                # the pool gate exists for, kept so the gate is shown biting
                # rather than merely asserted.
                if flags_say:
                    ungated.append((slug, name))
                continue
            if rings != (name in e["priority"]):
                wrong.append("%s: %s %s" % (
                    slug, name, "ringed, FFR did not" if rings
                    else "not ringed, FFR did"))
        for name in e["priority"]:
            if name in paths and name not in by_name:
                missing.append("%s: %s" % (slug, name))

    print("-- and the corpus it grades them on")
    # A sweep over nothing agrees with everything, which is the one result this
    # must not report as a pass.
    check("cartridges graded", seen >= 20, True)
    check("every ring the pack would draw is one FFR drew", wrong, [])
    check("the corpus still holds a slot whose location a seed lacks",
          sorted(ungated), sorted(DEMONSTRATED_GHOSTS))
    # There was a third check here -- "nothing is ringed for a location the
    # seed does not have" -- and it could not fail. `rings` is `flags_say and
    # present`, so inside `if not present:` it is False by construction and its
    # list could never be appended to. It read as live evidence that the gate
    # bites, which is exactly what this file's header refuses.
    #
    # No check of that shape can live here: the model above *is* the gate, so
    # asserting it against itself is always a tautology. What can fail is the
    # row above, which asserts the corpus still contains the case, and the Lua
    # end in tests/test_incentives.lua -- "a pool without it puts the ring out"
    # -- which drives the real refreshIncentiveHighlights.
    check("no incentivized location the pack knows is missing a row",
          missing, [])

    print("-- and the generated table is the one that was graded")
    # A row that names no location must say `nil` and not the string "None".
    # Every one of the 54 carries a real code today, so the generator cannot
    # demonstrate this on its own output; the assertion is on the renderer.
    # scripts/incentives.lua rings a row with no code on its flags alone, and
    # "None" is a code -- it would join to no location and put the ring out on
    # every seed that states a pool.
    check("a row with no hosted code renders as nil",
          incentive_slots.hosted_literal({"hosted": None}), "hosted = nil,")
    check("scripts/incentive_slots.lua is up to date",
          os.system("%s %s --check >/dev/null"
                    % (sys.executable,
                       os.path.join(TOOLS, "incentive_slots.py"))), 0)

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else "%d FAILED" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
