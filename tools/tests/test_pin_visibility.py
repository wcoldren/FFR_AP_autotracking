"""The pin-visibility stamper: its classifier, and the trees it has stamped.

`tools/pin_visibility.py` decides which of the pack's 283 pins per overworld
tree can be switched off, and writes a `restrict_visibility_rules` onto each.
`tests/test_pins.lua` checks the result -- the counts, and what the real
`showPin` does with them. This checks the thing that produced it, which is a
different question and fails differently:

  * **the committed trees are what the stamper writes.** Editing `kind_of` and
    forgetting to rerun the tool leaves the trees carrying yesterday's policy
    with every suite green. `--check` is that guard and nothing ran it.
  * **the classifier still recognises everything.** `kind_of` reads two tables
    it does not own -- `extract_npcs.WANTED` and the ids under 512 in
    `location_mapping.lua` -- so a rename in either quietly demotes a pin to
    unclassified, which stamps no rule and hides nothing. A pin that cannot be
    switched off is a silent failure; the zero below is what says there are
    none.
  * **the incentive half of the classifier.** The five orb slots are named
    here rather than counted, because "every section must carry a flag" exists
    for them specifically: an orb pin that could be switched off would take the
    four fiends' own chests off the board, and a count moving by one is not
    something anyone would read as that.
"""
import copy
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import pin_visibility                                          # noqa: E402

# The five slots on the incentive sheet that stand for an orb, one per fiend
# plus the chest room. Each holds at least one section with no incentive flag,
# so no rule may be stamped on them -- and if one ever is, it is these names
# that say the "every section" requirement stopped holding rather than a count
# quietly moving by one.
ORB_SLOTS = ("I: Earth Cave", "I: Volcano", "I: Sky Palace", "I: Sea Shrine")

# Named separately because the two trees disagree about it: the standard sheet
# calls Bahamut's slot "I: Bahamut's Cave" and the No-Overworld one "I: Bahamut".
BAHAMUT_SLOT = {"locations/incentives.json": "I: Bahamut's Cave",
                "locations/NOverworld/incentives.json": "I: Bahamut"}

# (slots a rule can speak for, slots it cannot). The second number is the orb
# slots above plus the nodes holding no incentive slot at all -- Temple of
# Fiends and ToFR on both sheets, and Ryukahn Desert on the standard one.
#
# Shop Item left the second number for the first on 2026-09-03. It reads as a
# slot with no flag only if you look for a declared one: FFR computes the shop
# slot's incentive status as NPCItems AND IncentivizeFreeNPCs
# (FlagsCompute.cs:217) instead of putting a name in the flag string, so the
# slot is spoken for by npcsAreIncentive exactly as the six free NPCs are.
#
# Dr Unne left the first number entirely on 2026-09-03, rather than moving to
# the second: FFR has no IncentivizeUnne, so the slot was removed from both
# sheets instead of being kept as one no rule can speak for. docs/ISSUES.md.
INCENTIVE_EXPECTED = {
    "locations/incentives.json": (17, 8),
    "locations/NOverworld/incentives.json": (20, 7),
}


def nodes(tree):
    for node in tree:
        yield node
        yield from nodes(node.get("children") or [])


def load(rel):
    with open(os.path.join(PACK, rel)) as handle:
        return json.load(handle)


def main():
    fails = []

    def check(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")
        print(f"{'ok  ' if got == want else 'FAIL'} {label:<58} {got!r}")

    # 1. The committed trees are what the stamper writes.
    check("the committed trees are what pin_visibility.py stamps",
          _check_mode(), 0)

    # 2. The classifier, on the tree it stamps.
    tree = load("locations/overworld.json")
    markable = [n for n in nodes(tree)
                if any(ml["map"] != "overworld"
                       for ml in n.get("map_locations") or [])]
    check("nodes carrying a pin on a drawn map", len(markable), 244)
    # kind_of leans on this: a town node holds its NPC beside its chests, and
    # would read as an NPC pin if the single-section requirement went.
    check("all of them hold exactly one section",
          sum(1 for n in markable if len(n.get("sections") or []) == 1), 244)
    kinds = {}
    for node in markable:
        kind = pin_visibility.kind_of(node)
        kinds[kind] = kinds.get(kind, 0) + 1
    check("chest nodes", kinds.get("chest"), 241)
    check("npc nodes", kinds.get("npc"), 3)
    check("nodes the classifier could not place", kinds.get(None, 0), 0)

    # 3. The incentive half, which nothing on the board exercises yet.
    for rel, (want_ruled, want_bare) in INCENTIVE_EXPECTED.items():
        sheet = load(rel)
        pinned = [n for n in nodes(sheet) if n.get("map_locations")]
        ruled = [n for n in pinned if pin_visibility.flags_of(n)]
        check(f"{rel}: slots a rule can speak for", len(ruled), want_ruled)
        check(f"{rel}: slots it cannot", len(pinned) - len(ruled), want_bare)
        by_name = {n.get("name"): n for n in pinned}
        for name in ORB_SLOTS + (BAHAMUT_SLOT[rel],):
            node = by_name.get(name)
            if node is None:
                fails.append(f"{rel}: no slot named {name}")
                print(f"FAIL {rel}: {name} is not on the sheet")
                continue
            check(f"{rel}: no flag speaks for {name}",
                  pin_visibility.flags_of(node), None)
        # The stamped sheet agrees with the classifier. Both halves are
        # asserted, so a rule appearing where no flag speaks for one fails, and
        # so does a kind switched on with the sheets left unstamped -- either
        # is a drift between the gate and the trees.
        check(f"{rel}: pins carrying a rule", sum(
            1 for n in pinned
            for m in n.get("map_locations") or []
            if m.get("restrict_visibility_rules")), want_ruled)
    check("kinds that carry a rule",
          sorted(pin_visibility.ENABLED_KINDS), ["chest", "npc", "slot"])

    # 4. stamp() deletes as well as sets.
    #
    # Without the delete, --check is a ratchet: a rule that policy no longer
    # calls for would sit there for ever and the tool would report the tree
    # up to date. Demonstrated on a copy rather than argued.
    doubtful = copy.deepcopy(tree)
    stamped = 0
    for node in nodes(doubtful):
        for marker in node.get("map_locations") or []:
            marker["restrict_visibility_rules"] = ["$showPin|nonsense"]
            stamped += 1
    check("pins given a rule policy does not call for", stamped, 283)
    pin_visibility.stamp(doubtful)
    left = sum(1 for n in nodes(doubtful)
               for m in n.get("map_locations") or []
               if m.get("restrict_visibility_rules") == ["$showPin|nonsense"])
    check("bogus rules left after a stamp", left, 0)
    # Not just "the bogus rules went" -- the rules that replaced them are the
    # committed ones, so this is the round trip and not half of it. Compared by
    # digest because the trees are a quarter of a megabyte each and a mismatch
    # is read from --check's own diff, not from here.
    check("the stamped copy equals the committed tree",
          _digest(pin_visibility.render(doubtful)),
          _digest(pin_visibility.render(tree)))

    # 5. The regen path, without a cartridge.
    #
    # place_locations() keeps only the pins whose map it does not redraw and
    # rebuilds the rest through pixels(), which returns a fresh three-key dict.
    # So every dungeon rule in the tree is dropped on the way through, and an
    # override written without the stamp would carry none of them -- the pack
    # ships the toggles, the tracker serves a tree where they reach nothing, and
    # nothing says so. Reproduced here on the shipped tree rather than argued,
    # and with no ROM: the rebuild is spelled out, the stamp puts the rules back.
    # Every map the tree pins on except the overworld, whose art does not change
    # and whose markers place_locations keeps untouched. Read off the tree so
    # this needs neither the calibration file nor a cartridge.
    redrawn = {m["map"] for n in nodes(tree)
               for m in n.get("map_locations") or []
               if m["map"] != "overworld"}
    rebuilt = copy.deepcopy(tree)
    for node in nodes(rebuilt):
        markers = node.get("map_locations") or []
        for i, marker in enumerate(markers):
            if marker["map"] in redrawn:
                markers[i] = {k: marker[k] for k in ("map", "x", "y")}
    check("rules a regen drops before the stamp",
          _rules(rebuilt), 0)
    pin_visibility.stamp(rebuilt)
    check("rules the stamp puts back", _rules(rebuilt), 254)
    # The pins place_locations leaves alone keep their own shape, so this is
    # also the check that the stamp did not disturb the overworld.
    check("overworld pins still unruled", sum(
        1 for n in nodes(rebuilt)
        for m in n.get("map_locations") or []
        if m["map"] == "overworld" and m.get("restrict_visibility_rules")), 0)

    # 6. A comma in a flag cannot smuggle a second rule onto a pin.
    #
    # PopTracker commasplits a rule string before parsing it (rule.h:12), so
    # "$showPin|slot|a,b" is not one rule about a flag spelled "a,b" -- it is two
    # rules AND'd, and the pin then hides whenever item `b` is absent however the
    # toggle stands. incentive_slots.flags_of() cuts at the comma on both of its
    # readings -- the ^$incentiveSlot terms and the lone visibility_rules
    # fallback -- and tests/test_pins.lua cannot see the difference:
    # its flag scan stops at the comma and never names `b`. Nothing on either
    # sheet carries one today, which is why both halves are here -- the synthetic
    # slot is the guard, the count is the statement that it is still hypothetical.
    comma = {"name": "I: Comma",
             "map_locations": [{"map": pin_visibility.INCENTIVE_MAP}],
             "sections": [{"name": "Slot", "visibility_rules": ["Xcalber,b"]}]}
    check("a flag's comma tail is cut rather than ANDed on",
          pin_visibility.rules_for(pin_visibility.INCENTIVE_MAP, comma),
          ["$showPin|slot|Xcalber"])
    check("commas in the rules the trees carry", sum(
        1 for rel in pin_visibility.TREES for n in nodes(load(rel))
        for m in n.get("map_locations") or []
        for rule in m.get(pin_visibility.FIELD) or [] if "," in rule), 0)

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


def _rules(tree):
    return sum(1 for n in nodes(tree)
               for m in n.get("map_locations") or []
               if m.get("restrict_visibility_rules"))


def _digest(text):
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _check_mode():
    """pin_visibility --check, without its output on stdout."""
    argv, out = sys.argv, sys.stdout
    sys.argv = ["pin_visibility.py", "--check"]
    sys.stdout = open(os.devnull, "w")
    try:
        return pin_visibility.main()
    finally:
        sys.stdout.close()
        sys.argv, sys.stdout = argv, out


if __name__ == "__main__":
    sys.exit(main())
