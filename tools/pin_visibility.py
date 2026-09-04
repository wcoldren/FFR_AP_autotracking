#!/usr/bin/env python3
"""Stamp restrict_visibility_rules onto the pins the Pins toggles switch off.

Every pin the pack draws is drawn always. The Pins group in the left dock gives
four of those sets an off switch, and a switch reaches a pin through a
`restrict_visibility_rules` entry on its `map_locations` entry -- which hides
that one marker and nothing else. The section stays in the tree, in the counts,
and clearable from the location list; the old incentive-map `visibility_rules`
took the check off the board entirely, and that is the bug this must not repeat.

The rules are generated rather than typed because there are 254 of them and
because tools/regen_maps.py rewrites these same files from a cartridge -- it
calls stamp() on its own output, so a regenerated tree carries the same rules as
the committed one, including on pins the cartridge places that the committed
tree has never had.

What gets which rule:

    a dungeon or town map      the pin's kind -- $showPin|chest or $showPin|npc
    the `incentives` sheet     $showPin|slot|<flag>... , the section's own flags
    `overworld`                nothing
    under the Entrances group  $showPin|entrance, on whichever map it sits

The overworld pins are left alone on purpose. They are aggregates -- a town pin
stands for its chests, its NPC and its shop at once -- so no one kind describes
them, and a player who could switch them off could empty the overworld tab.

A node whose sections do not ALL carry an incentive flag gets no slot rule
either, because the outer rule array is OR'd (location.cpp:266): an unflagged
section is always visible, so its entry would be always true and the rule would
be a lie. That is what keeps the five orb pins on the incentive sheet.

stamp() deletes the key where it does not set one, so --check is an invariant in
both directions rather than a ratchet that can only add.

Usage:
    tools/pin_visibility.py            # rewrite the location trees
    tools/pin_visibility.py --check    # exit 1 if any is out of date
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)

sys.path.insert(0, HERE)

import extract_npcs        # noqa: E402  -- WANTED, the NPCs worth a pin
import incentive_slots     # noqa: E402  -- flags_of, one reading of a flag
import render_maps         # noqa: E402  -- MAP_FILES, the 61 drawn maps
import split_locations     # noqa: E402  -- load_mapping, leaf_of

# The trees this rewrites -- all four, so --check speaks for all four. Which of
# them actually gain rules is ENABLED_KINDS' business, not this list's.
TREES = (
    "locations/overworld.json",
    "locations/NOverworld/overworld.json",
    "locations/incentives.json",
    "locations/NOverworld/incentives.json",
)

# The kinds that carry a rule. All three, now that items/flags.json defines a
# toggle for each -- a rule naming an item that does not exist would be inert,
# because showPin fails open and draws the pin, and an inert rule that looks
# live is worse than none.
#
# One constant rather than two, because tools/regen_maps.py stamps its own
# output through the same function: a gate the tool honoured and the regen did
# not would show up as a committed tree and an override that disagree, which is
# the whole thing this arrangement exists to make impossible.
ENABLED_KINDS = frozenset({"chest", "npc", "slot", "entrance"})

# Entrance pins are the one kind that is not classified from the node. A door
# and a staircase are the cartridge's, not the committed tree's, so regen_maps
# injects them under a single group and this reads the group rather than the
# marker: keying on `shape == "trapezoid"` instead would make the shape the
# source of truth for what a pin means, which is the reading docs/ISSUES.md,
# "What a diamond means", just closed.
#
# The rule string lives here rather than being spelled again at the injection
# site, so this file goes on owning every rule the trees carry.
ENTRANCES_GROUP = "Entrances"
ENTRANCE_RULE = "$showPin|entrance"

FIELD = "restrict_visibility_rules"

# The maps regen_maps.py draws, by name. `overworld` is not among them, which is
# what makes the dispatch below a lookup rather than a list of exceptions.
DRAWN_MAPS = frozenset(render_maps.MAP_FILES.values())

INCENTIVE_MAP = "incentives"

# The NPCs the cartridge reader places, by hosted code. Read from extract_npcs
# rather than retyped, so an NPC added there gets a pin rule with no edit here.
NPC_CODES = frozenset(extract_npcs.WANTED.values())


def chest_names():
    """Node names that stand for a shuffled chest.

    location_mapping.lua is the multiworld's own id table, and ids below 512 are
    the chests -- which is the same cut split_locations.py makes when it splits a
    grouped section, so the names line up with the nodes by construction.
    """
    return frozenset(split_locations.leaf_of(path)
                     for path, _ in split_locations.load_mapping(512).values())


CHEST_NAMES = None      # filled on first use; reading it costs a file open


def kind_of(node):
    """"chest", "npc", or None -- what one pin on this node stands for."""
    global CHEST_NAMES
    sections = node.get("sections") or []
    # An NPC node holds exactly one section, and that section names the NPC as
    # its hosted_item. Requiring the single section is what stops a town node --
    # which holds its NPC alongside its chests -- from reading as an NPC pin.
    if len(sections) == 1 and sections[0].get("hosted_item") in NPC_CODES:
        return "npc"
    if CHEST_NAMES is None:
        CHEST_NAMES = chest_names()
    if node.get("name") in CHEST_NAMES:
        return "chest"
    return None


def flags_of(node):
    """One sorted flag list per section, or None.

    A list of lists rather than one flattened set, because the two are not the
    same question. Within a section the flags are an AND -- FFR computes two of
    these conditions as conjunctions (FlagsCompute.cs:217, :220-226) -- and
    across sections they are an OR, since a pin draws if any section under it
    would draw. Flattening folded the AND into the OR and made a conjunction
    impossible to state; the rule array is where the OR belongs, and
    location.cpp:266 is what ORs it.

    None unless EVERY section carries a flag: a node with an unflagged section
    is visible through that section whatever the flags say, so a rule on it
    would claim a hide it cannot perform.
    """
    sections = node.get("sections") or []
    if not sections:
        return None
    out = []
    for section in sections:
        flags = incentive_slots.flags_of(section)
        if not flags:
            return None
        out.append(flags)
    # Sorted so two sections naming the same set produce one entry rather than
    # two identical ones, and so the output does not depend on section order.
    return sorted({tuple(flags) for flags in out})


def rules_for(map_name, node, in_entrances=False):
    """The rule strings a pin on `map_name` gets, or None.

    A list because one entry per section is what the OR above wants.

    `in_entrances` is set for every node under the injected Entrances group, and
    is asked first because those pins sit on both kinds of map: a door on
    `overworld`, which gets no rule otherwise, and a staircase on a drawn map,
    where kind_of would read the node as neither chest nor NPC and return None.
    """
    if in_entrances:
        if "entrance" not in ENABLED_KINDS:
            return None
        return [ENTRANCE_RULE]
    if map_name in DRAWN_MAPS:
        kind = kind_of(node)
        if kind in ENABLED_KINDS:
            return ["$showPin|%s" % kind]
        return None
    if map_name == INCENTIVE_MAP and "slot" in ENABLED_KINDS:
        groups = flags_of(node)
        if not groups:
            return None
        return ["$showPin|slot|" + "|".join(flags) for flags in groups]
    return None


def stamp(doc):
    """Set or delete every pin's rule in place. Returns a {rule: count} tally."""
    tally = {}

    def walk(nodes, in_entrances=False):
        for node in nodes:
            here = in_entrances or node.get("name") == ENTRANCES_GROUP
            for marker in node.get("map_locations") or []:
                rules = rules_for(marker.get("map"), node, here)
                if rules:
                    marker[FIELD] = rules
                    # Tallied by the whole rule list, so a marker carrying two
                    # entries is one pin rather than two.
                    key = " ".join(rules)
                    tally[key] = tally.get(key, 0) + 1
                else:
                    marker.pop(FIELD, None)
                    tally[None] = tally.get(None, 0) + 1
            walk(node.get("children") or [], here)

    walk(doc)
    return tally


def render(doc):
    return json.dumps(doc, indent=4) + "\n"


def describe(tally):
    parts = ["%d %s" % (n, rule)
             for rule, n in sorted(tally.items(), key=lambda kv: kv[0] or "")
             if rule]
    if tally.get(None):
        parts.append("%d unruled" % tally[None])
    return ", ".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if any tree is out of date")
    args = ap.parse_args()

    status = 0
    for rel in TREES:
        path = os.path.join(PACK, rel)
        with open(path) as handle:
            before = handle.read()
        doc = json.loads(before)
        tally = stamp(doc)
        after = render(doc)

        if args.check:
            if before != after:
                print("%s is out of date -- rerun tools/pin_visibility.py" % rel,
                      file=sys.stderr)
                status = 1
            else:
                print("%s: %s, up to date" % (rel, describe(tally)))
            continue

        with open(path, "w") as handle:
            handle.write(after)
        print("%s: %s" % (rel, describe(tally)))
    return status


if __name__ == "__main__":
    sys.exit(main())
