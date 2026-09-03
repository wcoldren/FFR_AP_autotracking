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

# Rings that are wrong for a reason this suite is not about, waived by name so
# the count above stays honest and the reason stays visible.
#
# The cardia progressive's stage 2 is Bahamut's Hoard and inherits stage 1's
# code, so MapDragonsHoard provides `cardiaIsIncentive` whatever
# IncentivizeCardia says -- and the pack rings Cardia Forest on the six hoard
# cartridges, where FFR incentivized nothing there. Not a conjunction and not
# fixed by one; it wants a way to say "the hoard exists and Cardia is not
# incentivized", which a progressive cannot say. docs/ISSUES.md.
CARDIA_HOARD = "Cardia Forest Island - Incentive Major"
WAIVED_RINGS = {CARDIA_HOARD}

# Slots the pack shows for a location the seed does not have. The caravan slot
# was the third of these until it got its existence gate; these two remain, and
# both are a chest whose incentive name the seed did not use -- notail's Sea
# Shrine incentive is `Incentive 1`/`Incentive 2` rather than `Incentive Major`.
# Same family as the caravan, different cause. docs/ISSUES.md.
WAIVED_GHOSTS = {
    ("notail", "Sea Shrine Mermaids (B1) - Incentive Major"),
    ("hoarddockbridge497", CARDIA_HOARD),
}

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
    wrong, ghosts, missing = [], [], []
    for slug, e in exports():
        if not e.get("priority") or not e.get("locations"):
            continue
        seen += 1
        codes = check_logic.flag_codes(e["flags"], PACK)
        noverworld = e["flags"].get("GameMode") == 2
        for name, row in by_name.items():
            # FFR's IncentivizeNerrick ends `&& !NoOverworld`; every other slot
            # is its flags and nothing else.
            rings = (all(f in codes for f in row["flags"])
                     and not (row.get("standardOnly") and noverworld))
            if name not in e["locations"]:
                if rings and (slug, name) not in WAIVED_GHOSTS:
                    ghosts.append("%s: %s" % (slug, name))
                continue
            if rings != (name in e["priority"]) and name not in WAIVED_RINGS:
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
    check("nothing is ringed for a location the seed does not have", ghosts, [])
    check("no incentivized location the pack knows is missing a row",
          missing, [])

    print("-- and the generated table is the one that was graded")
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
