#!/usr/bin/env python3
"""Write scripts/incentive_slots.lua -- every slot a seed's incentive flags speak for.

The gold ring that marks an incentivized slot is set from Lua, one section at a
time, so something has to know which sections those are. That list lives in the
location files already -- as the `^$incentiveSlot|<flag>` terms on the incentive
map, and as the matching `hosted_item` on the real board -- so it is read back
out of them rather than typed a second time and left to drift.

Three files contribute:

  locations/incentives.json           the incentive tab's own pins
  locations/NOverworld/incentives.json  the same tab on the NOverworld art,
                                      which renames several of its nodes
  locations/overworld.json            the same slots where the player actually
                                      walks, on the overworld and dungeon tabs

Only one of the two incentive files is loaded per variant, so a path that does
not resolve at runtime is expected rather than an error -- the pass skips it.

Usage:
    tools/incentive_slots.py            # write the file
    tools/incentive_slots.py --check    # exit 1 if it is out of date
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)

OUT = "scripts/incentive_slots.lua"

INCENTIVE_FILES = ("locations/incentives.json",
                   "locations/NOverworld/incentives.json")
BOARD_FILE = "locations/overworld.json"

TERM = "^$incentiveSlot|"

# cardiaIncentive is hosted by two different slots -- the Cardia forest chest
# and Bahamut's hoard -- and both answer to the same incentive flag. The hoard
# also names MapDragonsHoard in a visibility rule, but that says the chests are
# in the cartridge rather than that they are incentivized, so it is not the ring
# flag and EXISTENCE_FLAGS below keeps flags_of from reading it as one.
HOSTED_OVERRIDE = {"cardiaIncentive": "cardiaIsIncentive"}

# Codes that gate whether a slot exists rather than whether it is incentivized.
#
# Both members are here for the same reason and it took two goes to see it. The
# caravan slot is hidden because FFR did not create the location at all --
# NPCItems off drops Shop Item from `rules` and `locations`, 227 to 224 on
# nonpcitems497 -- and reading npcItems off that rule would say the slot rings
# on npcItems alone, which is half of its actual condition.
#
# BahamutHoard was read as a ring flag until 2026-09-03, on the argument that
# the hoard is a map edit whose flag *is* its incentive condition. It is not:
# MapDragonsHoard says the Cardia chests are duplicated into Bahamut's Cave, and
# IncentivizeCardia says whether they are incentivized. While those two facts
# shared one progressive there was no way to tell them apart, so the wrong
# reading cost nothing; once they were split it rang the hoard slot gold on
# five cartridges FFR incentivized nothing on. Its ring flag now comes from
# HOSTED_OVERRIDE like every other cardiaIncentive slot, and its visibility rule
# does only what a visibility rule should. docs/ISSUES.md.
#
# Today the board's caravan section is deduped away by the sheet's, whose path
# is the same string, so the wrong reading never reaches a row. That is load
# order doing the work of a decision, and it would flip silently if either tree
# were renamed.
EXISTENCE_FLAGS = frozenset({"npcItems", "BahamutHoard"})


def sections(tree):
    """(node name, section) for every section in the file."""
    out = []

    def walk(nodes):
        for node in nodes:
            for section in node.get("sections", []):
                out.append((node.get("name"), section))
            walk(node.get("children", []))

    walk(tree)
    return out


def load(rel):
    with open(os.path.join(PACK, rel)) as handle:
        return json.load(handle)


def flags_of(section):
    """Every incentive flag a section is spoken for by, sorted, or None.

    A list rather than one flag because FFR computes two of these conditions as
    conjunctions -- IncentivizeCaravan is (NPCItems && IncentivizeFreeNPCs) and
    each fetch incentive is (NPCFetchItems && IncentivizeFetchNPCs), per
    FlagsCompute.cs:217 and :220-226 -- and a conjunction is written as two
    `^$incentiveSlot|` terms ANDed into the same alternative. Reading only the
    first would model a conjunction by whichever conjunct came first in the
    string, which is the defect this exists to end.

    The first alternative that carries any term speaks for the section.
    tests/test_incentives.lua is what holds every alternative to naming the same
    set, so reading one of them here is not a shortcut past that check.

    The visibility_rules fallback is for a slot whose own rule names its ring
    flag. Every section that does today names an EXISTENCE_FLAGS code instead --
    a rule about whether the slot exists, not whether it is incentivized -- so
    the fallback returns nothing and those slots take their flag from
    HOSTED_OVERRIDE. It is kept because a future sheet may gate a ring that way
    and the alternative is silently dropping the row. Cut at the comma, because
    a rule string is commasplit before it is parsed (rule.h:12) and a tail read
    as part of a flag name would name no item at all.
    """
    for alt in section.get("access_rules") or []:
        found = [term[len(TERM):] for term in alt.split(",")
                 if term.startswith(TERM)]
        if found:
            return sorted(set(found))
    vis = section.get("visibility_rules") or []
    if len(vis) == 1:
        flag = vis[0].split(",")[0]
        if flag not in EXISTENCE_FLAGS:
            return [flag]
    return None


def collect():
    """One row per section a seed's incentive flags speak for.

    A row is {"path", "flags", "hosted"}; `flags` is an AND -- every one of them
    has to be provided before the slot rings. Two of FFR's incentive conditions
    are conjunctions rather than flags, so one flag per row could only ever have
    modelled half of each.

    `hosted` is the section's own `hosted_item`, and it is what lets a row be
    matched to an Archipelago location: `LOCATION_MAPPING` carries the hosted
    code beside the id, every one of the 26 it names belongs to exactly one id,
    and the sheet row and the board row for a slot host the same code. So the
    id is joined at runtime rather than written here, which keeps the ids in
    the one file that already owns them. scripts/incentives.lua reads it.
    """
    rows = []
    seen = set()
    hosted_flag = {}
    spoken_for = {rel: set() for rel in INCENTIVE_FILES}

    for rel in INCENTIVE_FILES:
        for node, section in sections(load(rel)):
            flags = flags_of(section)
            if not flags:
                continue
            hosted = section.get("hosted_item")
            if hosted:
                hosted_flag.setdefault(hosted, flags)
                spoken_for[rel].add(hosted)
            path = "@%s/%s" % (node, section["name"])
            if path not in seen:
                seen.add(path)
                rows.append({"path": path, "flags": flags, "hosted": hosted})

    for hosted, override in HOSTED_OVERRIDE.items():
        hosted_flag[hosted] = [override]

    # A slot the standard sheet speaks for and the No-Overworld sheet does not.
    #
    # Read rather than listed, because the sheets already record it: FFR's
    # IncentivizeNerrick is (NPCFetchItems && IncentivizeFetchNPCs &&
    # !NoOverworld) -- FlagsCompute.cs:224, and IncentivizedLocationCountMin at
    # :229 counts seven fetch slots or six under No-Overworld -- and the
    # No-Overworld sheet answers that by having no Nerrick section at all.
    # Deriving it from that keeps the fact in one place instead of two.
    #
    # It matters only on the board rows below. The two sheets' own rows are
    # already right: a sheet the variant does not load resolves nowhere. The
    # board tree is the problem, because locations/overworld.json and its
    # NOverworld twin are byte-identical -- tests/test_maps.lua holds them that
    # way and check_logic's --derived path depends on it -- so the board's
    # Nerrick row exists on both modes and cannot be told apart by its file.
    standard_only = spoken_for[INCENTIVE_FILES[0]] - spoken_for[INCENTIVE_FILES[1]]

    for node, section in sections(load(BOARD_FILE)):
        hosted = section.get("hosted_item")
        if not hosted or hosted not in hosted_flag:
            continue
        # The hoard keeps its own visibility rule on the real board too, and
        # that rule is about existence, so flags_of declines it and the override
        # is what answers -- the same flag the sheet's copy of the slot rings on.
        flags = flags_of(section) or hosted_flag[hosted]
        path = "@%s/%s" % (node, section["name"])
        if path not in seen:
            seen.add(path)
            row = {"path": path, "flags": flags, "hosted": hosted}
            if hosted in standard_only:
                row["standardOnly"] = True
            rows.append(row)

    return rows


def literal(flags):
    return "{ %s }," % ", ".join('"%s"' % flag for flag in flags)


def hosted_literal(row):
    return 'hosted = "%s",' % row["hosted"]


def render(rows):
    width = max(len(literal(row["flags"])) for row in rows) + 1
    hwidth = max(len(hosted_literal(row)) for row in rows) + 1
    lines = [
        "-- Generated by tools/incentive_slots.py. Do not edit by hand.",
        "--",
        "-- Every section a seed's incentive flags speak for, and the flags that",
        "-- speak for it. scripts/incentives.lua rings the ones a seed kept.",
        "--",
        "-- `flags` is an AND: FFR computes two of these conditions as",
        "-- conjunctions rather than storing them (FlagsCompute.cs:217, :220-226),",
        "-- so a slot can answer to more than one flag and rings only on all of",
        "-- them.",
        "--",
        "-- Both incentive trees are listed and only one loads per variant, so a",
        "-- path that does not resolve is expected rather than an error.",
        "--",
        "-- `standardOnly` is FFR's third term on IncentivizeNerrick",
        "-- (FlagsCompute.cs:224, `&& !NoOverworld`). It sits on a board row",
        "-- because both variants load the same board tree, so the file cannot",
        "-- say it and the row has to.",
        "--",
        "-- `hosted` is the section's hosted item code, which is also what",
        "-- LOCATION_MAPPING carries beside each Archipelago location id. It is",
        "-- how a ring asks whether this seed has the location at all: the flags",
        "-- can say a slot is incentivized on a seed that does not contain it.",
        "INCENTIVE_SLOTS = {",
    ]
    for row in rows:
        lines.append('  { flags = %-*s %-*s path = "%s"%s },'
                     % (width, literal(row["flags"]),
                        hwidth, hosted_literal(row), row["path"],
                        ", standardOnly = true" if row.get("standardOnly")
                        else ""))
    lines.append("}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the generated file is out of date")
    args = ap.parse_args()

    rows = collect()
    text = render(rows)
    path = os.path.join(PACK, OUT)

    if args.check:
        current = open(path).read() if os.path.exists(path) else None
        if current != text:
            print("%s is out of date -- rerun tools/incentive_slots.py" % OUT,
                  file=sys.stderr)
            return 1
        print("%s: %d slots, up to date" % (OUT, len(rows)))
        return 0

    with open(path, "w") as handle:
        handle.write(text)
    print("%s: %d slots" % (OUT, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
