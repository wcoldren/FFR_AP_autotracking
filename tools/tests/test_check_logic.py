#!/usr/bin/env python3
"""tools/check_logic.py -- the adapter that lets it check derived rules.

None of this needs a cartridge. What it covers is the handful of joins and
encodings between the derivation and the checker, every one of which fails
*silently* rather than loudly: a wrong answer here reads as a clean run or as a
catastrophic one, and neither looks like a bug in the glue.
"""

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)

import check_logic as c             # noqa: E402

fails = []


def ok(cond, label, got=""):
    print(f"{'ok  ' if cond else 'FAIL'} {label:64} {got}")
    if not cond:
        fails.append(label)


# --- "free" must mean always open ----------------------------------------
#
# The obvious encoding of an empty requirement is ",".join([]) -> [[""]], and it
# evaluates to False: "".split(",") is [""], and "" is never in `provided`. That
# spelling reports every one of the 167 free No-Overworld locations as stricter
# than FFR, which looks like the derivation failing catastrophically rather than
# like the adapter being wrong by one character.
have = {"key", "cube"}
ok(c.satisfied([[""]], have) is False,
   'the naive free encoding [[""]] evaluates False -- do not use it')
ok(c.satisfied(c.as_chain([[]]), have) is True,
   "as_chain makes a free rule always satisfied")
ok(c.as_chain([[]]) == [],
   "a free rule is an empty chain, not an empty alternative", c.as_chain([[]]))
ok(c.satisfied(c.as_chain([["cube"]]), have) is True,
   "a single held item is satisfied")
ok(c.satisfied(c.as_chain([["rod"]]), have) is False,
   "a single missing item is not")
ok(c.satisfied(c.as_chain([["rod"], ["cube"]]), have) is True,
   "an or-of-ands is satisfied by either alternative")
ok(c.satisfied(c.as_chain([["cube", "rod"]]), have) is False,
   "a conjunction needs both")
# A rule that is free *and* lists alternatives is still free; minimisation
# should have collapsed it, but the encoding must not depend on that.
ok(c.satisfied(c.as_chain([[], ["rod"]]), have) is True,
   "a free alternative wins over an unmet one")


# --- the derived name joins on the node, not on a path suffix -------------
#
# Derived rules key on a node name; sections key on "Area/Node/Section", and a
# chest's section is generically called "Chest". find_section matches suffixes
# and resolves 0 of 241 real chest names, so the join has to be on the
# second-to-last component.
TREE = [{
    "name": "Some Area",
    "children": [
        {"name": "Lone Node", "sections": [{"name": "Chest"}]},
        {"name": "Two Section Node",
         "sections": [{"name": "Chest"}, {"name": "NPC"}]},
    ],
}]


def derived_against(tree, rules, extra=None):
    with tempfile.TemporaryDirectory() as tmp:
        pack = os.path.join(tmp, "pack")
        os.makedirs(os.path.join(pack, "locations"))
        with open(os.path.join(pack, "locations", "overworld.json"), "w") as f:
            json.dump(tree, f)
        if extra is not None:
            with open(os.path.join(pack, "locations", "incentives.json"), "w") as f:
                json.dump(extra, f)
        else:
            with open(os.path.join(pack, "locations", "incentives.json"), "w") as f:
                json.dump([], f)
        sections = c.load_pack_rules(pack=pack)
        path = os.path.join(tmp, "rules.json")
        with open(path, "w") as f:
            json.dump({"rules": rules, "unreachable": []}, f)
        return c.load_derived_rules(path, sections), sections


(chains, report), sections = derived_against(TREE, {"Lone Node": [["key"]]})
ok(list(chains) == ["Some Area/Lone Node/Chest"],
   "a node name resolves to the section beneath it", list(chains))
ok(report["unmatched"] == [] and report["ambiguous"] == [],
   "and is not reported as a problem")
ok(c.find_section(sections, "Lone Node") is None,
   "find_section's suffix match does NOT resolve a bare node name")

# The same pin is written into the board tree and the incentive poster, so a ref
# matches twice. PopTracker resolves that to the board one -- getLocation takes
# the first hit and init.lua loads overworld.json before incentives.json -- and
# the harness has to agree, or the pin goes ungraded. Two board hits stay a
# genuine ambiguity and still refuse.
both = {
    "Onrac Continent/I: Shop Item/I: Shop Item": {"chain": [], "hosted": "shopItem"},
    "I: Onrac Continent/I: Shop Item/I: Shop Item": {"chain": [], "hosted": "shopItem"},
}
ok(c.find_section(both, "I: Shop Item/I: Shop Item")
   == "Onrac Continent/I: Shop Item/I: Shop Item",
   "find_section prefers the board tree when the incentive poster also matches")

twice_on_board = {
    "A/Shop/Shop": {"chain": [], "hosted": None},
    "B/Shop/Shop": {"chain": [], "hosted": None},
}
ok(c.find_section(twice_on_board, "Shop/Shop") is None,
   "find_section still refuses when the board tree itself is ambiguous")

# A node with two sections: the derived rule is about the tiles beside one map
# cell, which is equally true of every section that node hosts. Attaching to the
# first would leave the other on a stale rule silently.
(chains, report), _ = derived_against(TREE, {"Two Section Node": [["cube"]]})
ok(sorted(chains) == ["Some Area/Two Section Node/Chest",
                      "Some Area/Two Section Node/NPC"],
   "a node with two sections fans the rule to both", sorted(chains))
ok(report["fanned"] == [("Two Section Node", 2)],
   "and says so, because no real derived name triggers this today",
   report["fanned"])

# A name that matches nothing must be counted, never dropped.
(chains, report), _ = derived_against(TREE, {"No Such Node": [["key"]]})
ok(chains == {} and report["unmatched"] == ["No Such Node"],
   "an unmatched derived name is reported, not silently skipped", report)

# The same node name under two different parents is refused rather than
# resolving to whichever came first.
DUPE = [{"name": "A", "children": [{"name": "Dup", "sections": [{"name": "Chest"}]}]},
        {"name": "B", "children": [{"name": "Dup", "sections": [{"name": "Chest"}]}]}]
(chains, report), _ = derived_against(DUPE, {"Dup": [["key"]]})
ok(chains == {} and len(report["ambiguous"]) == 1,
   "a duplicated node name is refused, not resolved to the first hit", report)

# unreachable names are carried through so the summary can say they kept their
# old rules rather than losing them.
with tempfile.TemporaryDirectory() as tmp:
    p = os.path.join(tmp, "r.json")
    with open(p, "w") as f:
        json.dump({"rules": {}, "unreachable": ["Somewhere"]}, f)
    _, rep = c.load_derived_rules(p, {})
ok(rep["unreachable"] == ["Somewhere"],
   "the unreachable list is carried into the report")


# --- FFR's No-Overworld exporter renames two requirements ------------------
#
# Archipelago.cs:311-314 prints "Mark" for the Canoe and "Sigil" for the Floater
# on a GameMode 2 seed. Left alone, "Sigil" is filtered out of a clause by the
# `in FFR_ITEMS` guards (FFR reads weaker than it is) while "Mark" survives as a
# literal that is never in `held` (FFR reads permanently closed) -- wrong in both
# directions at once. The spoiler .txt does not rename, so this is per-source.
aliased, n = c.alias_noverworld({"X": [["Mark"], ["Chime", "Sigil"]]})
ok(aliased == {"X": [["Canoe"], ["Chime", "Floater"]]},
   "Mark becomes Canoe and Sigil becomes Floater", aliased)
ok(n == 2, "and the substitutions are counted so a zero can be noticed", n)
ok(c.alias_noverworld({"X": [["Key"]]}) == ({"X": [["Key"]]}, 0),
   "an unaliased clause is untouched")
ok(c.FFR_ITEMS.get("Orbs") == "orbs",
   "Orbs is in the item vocabulary, so an orb gate is not dropped silently")


# --- FFR's own export is pretty-printed JSON, not a one-line dict ----------
#
# FF1R writes the Archipelago export with Formatting.Indented and the payload
# under the game name. The line-oriented scan finds `"rules": {` on its own
# line, takes the empty remainder and returns {} -- which check_seed used to skip
# without a word, so the intended ground truth was invisible and the run
# reported on whatever else it happened to find.
with tempfile.TemporaryDirectory() as tmp:
    p = os.path.join(tmp, "export.yaml")
    with open(p, "w") as f:
        json.dump({"game": "Final Fantasy",
                   "Final Fantasy": {"rules": {"Somewhere": [["Key"]]}}}, f, indent=2)
    got = c.parse_ap_rules(p)
ok(got == {"Somewhere": [["Key"]]},
   "the indented FFR export parses", got)

with tempfile.TemporaryDirectory() as tmp:
    p = os.path.join(tmp, "player.yaml")
    with open(p, "w") as f:
        f.write("rules: {Somewhere: [['Key']], Else: [[]]}\n")
    got = c.parse_ap_rules(p)
ok(got == {"Somewhere": [["Key"]], "Else": [[]]},
   "and Archipelago's own one-line form still does", got)


# --- the swept vocabulary is the derivation's, and is named honestly -------
import entrance_graph as e          # noqa: E402
ok(c.SWEPT_ITEMS == set(e.ITEM_NAMES),
   "SWEPT_ITEMS matches entrance_graph.ITEM_NAMES exactly",
   sorted(c.SWEPT_ITEMS ^ set(e.ITEM_NAMES)) or "identical")
# Oxyale and the Ruby are inside it since SubEngineer and Titan became gates.
# Pinned by name rather than left to the identity above, because they are the
# two the off-vocabulary grant used to hand away 161 times on one cartridge, and
# a quiet removal from ITEM_NAMES would take them back out with nothing said.
ok("oxyale" in c.SWEPT_ITEMS and "ruby" in c.SWEPT_ITEMS,
   "Oxyale and the Ruby are inside it -- the walk gates on both now")


# --- an off-vocabulary item is granted free from whichever side names it ----
#
# The trade reader gave the derived side its own off-vocabulary vocabulary:
# Adamant, Crystal, Slab and Ruby are what NPCs want handed over, and every one
# of them is in FFR_ITEMS.values(), so compare() varies them. Computing the
# free set from FFR's clauses alone -- which is what this did -- leaves a
# derived rule naming Adamant failing on every combination without it, on a
# seed where FFR's own rule for that location never asks for it. The location
# reports `strict` and the divergence belongs to the harness.
offvocab_of = c.offvocab_items

trade = c.as_chain([["key", "adamant"]])
only_key = [["Key"]]
free = offvocab_of(trade, only_key)
ok(free == {"adamant"},
   "a trade item only the derived rule names is granted free", sorted(free))
ok(c.compare(trade, only_key, free, {}, (), free)[0] == "match",
   "so the location matches instead of reading as strict",
   str(c.compare(trade, only_key, free, {}, (), free)))
ok(c.compare(trade, only_key, set(), {}, (), set())[0] == "strict",
   "which is exactly what it did read as before")

# And the grant is only ever off-vocabulary: an extra item the walk *can*
# express is a real divergence and has to survive.
swept = c.as_chain([["key", "crown"]])
ok(offvocab_of(swept, only_key) == set(),
   "an extra swept item is granted nothing")
ok(c.compare(swept, only_key, set(), {}, (), set())[0] == "strict",
   "and still reports strict")


print()
if fails:
    print("FAILED: " + ", ".join(fails))
    sys.exit(1)
print("check_logic adapter tests passed")
