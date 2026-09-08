#!/usr/bin/env python3
"""Every airship alternative in the trees keeps its AirBoat sibling.

On an AirBoat cartridge the airship is not raised at Ryukahn Desert -- FFR
patches the turn-in out (`Hacks.cs:107`) and moves the take-off to the A button
aboard the Ship -- so `airship` is a code that seed never provides. What stands
in for it is a sibling alternative naming the conjunction FFR's own checker uses
(`SanityCheckerV2.cs:736-742,754-760`): the flag, the Floater and the Ship,
under the drydock guard every alternative naming the Ship carries.

There are 102 of them across the four trees, and nothing was watching them.
The Lua suite reaches its checks through the *pre-existing* `airship`
alternative -- `ram_mapping.lua` raises the Floater to its airship stage on an
AirBoat cartridge, so `airship` is provided and the sibling never has to fire --
and `check_logic` grades only the two 4.9.2 cartridges in `verify.sh`, which
have no AirBoat between them. Deleting all 102 sibling lines left the whole
suite green. Only the manual 4.9.7 sweep in `docs/ORACLE.md` said otherwise, and
a sweep somebody has to remember to run is not a gate.

So this is the gate: a structural invariant over the JSON, needing no cartridge,
no corpus and no Archipelago checkout.

    for every alternative naming `airship`,
    the same alternative with `airship` swapped for
    `airBoat`, `$noShipDrydock`, `floater`, `ship`
    is also in the list

Not asserted the other way round. Five `airBoat` alternatives have no `airship`
partner and are right not to: the Sea Shrine's northern-docks route is reached
on `ship,canal` rather than on the airship, and the welded vehicle flies the
canal, so its sibling answers a rule that never named `airship` at all.

Usage:
    tools/tests/test_airboat_siblings.py
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)

TREES = [
    "locations/overworld.json",
    "locations/incentives.json",
    "locations/NOverworld/overworld.json",
    "locations/NOverworld/incentives.json",
]

# What the sibling says instead of `airship`.
SWAP = frozenset({"airBoat", "$noShipDrydock", "floater", "ship"})


def rule_lists(node, path=""):
    """Every access_rules list in a tree, with the path that names it."""
    if isinstance(node, list):
        for child in node:
            yield from rule_lists(child, path)
        return
    if not isinstance(node, dict):
        return
    here = path + "/" + str(node.get("name", "?"))
    if "access_rules" in node:
        yield here, node["access_rules"]
    for key in ("children", "sections"):
        for child in node.get(key, []):
            yield from rule_lists(child, here)


def main():
    checked = 0
    missing = []

    for rel in TREES:
        path = os.path.join(PACK, rel)
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        for where, rules in rule_lists(doc):
            alts = [frozenset(r.split(",")) for r in rules]
            for text, alt in zip(rules, alts):
                if "airship" not in alt:
                    continue
                checked += 1
                if ((alt - {"airship"}) | SWAP) not in alts:
                    missing.append((rel, where, text))

    if checked == 0:
        print("FAIL: no airship alternatives found at all -- the trees moved,")
        print("      or rule_lists stopped walking them. Either way this test")
        print("      read nothing and must not report a pass.")
        return 1

    for rel, where, text in missing:
        print("FAIL: %s %s" % (rel, where))
        print("      %s" % text)
        print("      has no airBoat sibling")

    if missing:
        print("%d of %d airship alternatives have no sibling"
              % (len(missing), checked))
        return 1

    print("ok: %d airship alternatives, each with its airBoat sibling" % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
