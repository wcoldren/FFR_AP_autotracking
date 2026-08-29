#!/usr/bin/env python3
"""Turn the incentive map's hiding into a colour.

The incentive tab used to drop a slot's pin entirely when the seed had not
incentivized it -- a `visibility_rules` naming the flag, and nothing drawn. That
loses a real check: the NPC still hands you something and the chest is still
there. This rewrites each of those sections so the slot reports Inspect instead,
which PopTracker draws blue, and deletes the visibility rule that hid it.

    "access_rules"     : [ "earlyKing", "garland" ],
    "visibility_rules" : [ "npcsAreIncentive" ],
->
    "access_rules"     : [ "earlyKing,^$incentiveSlot|npcsAreIncentive",
                           "garland,^$incentiveSlot|npcsAreIncentive" ],

The rewrite is mechanical but not uniform, which is why it is a script rather
than a morning of hand edits. `access_rules` is an OR of comma-joined ANDs
(locationsection.cpp:74-94), so the term has to go on *every* alternative;
appending to the first one only would leave the rest ungated, and would look
right in the diff. Of the 49, six have more than one alternative, 26 end up with
the term as their only rule, two have no `access_rules` key to merge into, and
three write `visibility_rules` above `access_rules` instead of below it.

An absent or empty `access_rules` inherits the parent's verbatim
(locationsection.cpp:102). Writing a single-term list in its place is still
right: PopTracker ANDs a section's rules onto each of the parent's alternatives,
so `["^$incentiveSlot|X"]` comes out as parent AND X either way.

One flag is deliberately left hiding. `BahamutHoard` is stage 2 of the
cardiaIsIncentive progressive and it stands for MapDragonsHoard -- a map edit,
not an incentive category (scripts/autotracking/flag_mapping.lua:74-83). With it
off those chests are not in the cartridge at all, so a blue "there is a check
here" pin would be a lie rather than a demotion.

Edits the files as text rather than reserialising them. The location files are
tab-indented with spaces around their colons, and a json.dumps round-trip would
rewrite all 1300 lines to say 49 things.

Usage:
    tools/incentives_to_inspect.py --check     # exit 1 if a file needs rewriting
    tools/incentives_to_inspect.py --apply     # rewrite in place

Exit status: 0 all good, 1 --check found work to do, 2 the files are not in a
shape this script recognises.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)

FILES = ("locations/incentives.json", "locations/NOverworld/incentives.json")

TERM = "^$incentiveSlot|%s"

VIS = re.compile(r'^(?P<indent>\s*)"visibility_rules"\s*:\s*\[\s*"(?P<code>\w+)"\s*\]'
                 r'(?P<comma>,?)\s*$')
ACC = re.compile(r'^(?P<indent>\s*)"access_rules"\s*:\s*\[(?P<body>.*)\](?P<comma>,?)\s*$')
ALT = re.compile(r'"([^"]*)"')

# Every flag a section may be gated on, so a renamed or typo'd one is refused
# rather than written into a rule that would then read as "not incentivized"
# forever. Matches the TOGGLES table in scripts/autotracking/flag_mapping.lua
# plus the cardia progressive's two stage codes.
KNOWN = {
    "npcsAreIncentive", "fetchQuestsAreIncentive", "iceCaveIsIncentive",
    "ordealsIsIncentive", "marshIsIncentive", "marshLockedIsIncentive",
    "titansTroveIsIncentive", "earthIsIncentive", "volcanoIsIncentive",
    "skyIsIncentive", "seaIsIncentive", "coneriaLockedIsIncentive",
    "cardiaIsIncentive", "BahamutHoard",
}

KEEP_HIDDEN = {"BahamutHoard": "MapDragonsHoard is a map edit -- with it off "
                               "those chests are not in the cartridge"}


def rewrite_access(line, code):
    """Put the term on every alternative of an existing access_rules line."""
    m = ACC.match(line)
    if not m:
        return None
    alts = ALT.findall(m.group("body"))
    term = TERM % code
    if not alts:
        alts = [term]
    else:
        alts = [alt + "," + term for alt in alts]
    joined = ", ".join('"%s"' % a for a in alts)
    return '%s"access_rules" : [ %s ]%s\n' % (m.group("indent"), joined,
                                             m.group("comma"))


def convert(text):
    """Returns (new text, [(flag, how), ...])."""
    lines = text.splitlines(keepends=True)
    out = []
    done = []
    skip = -1
    for i, line in enumerate(lines):
        if i == skip:
            continue
        m = VIS.match(line)
        if not m:
            out.append(line)
            continue
        code = m.group("code")
        if code not in KNOWN:
            sys.exit("unknown incentive flag %r in %s" % (code, line.strip()))
        if code in KEEP_HIDDEN:
            out.append(line)
            continue

        # The access_rules line sits directly above in all but three sections,
        # where the two keys are written the other way round -- both Cardia
        # Incentives and the NOverworld one. Look both ways rather than trust
        # the common order: guessing wrong writes a second access_rules key
        # into the object, which is valid JSON that silently drops the rule.
        above = rewrite_access(out[-1], code) if out else None
        if above is not None:
            out[-1] = above
            done.append((code, "merged"))
            continue
        below = rewrite_access(lines[i + 1], code) if i + 1 < len(lines) else None
        if below is not None:
            out.append(below)
            skip = i + 1
            done.append((code, "merged"))
            continue
        out.append('%s"access_rules" : [ "%s" ]%s\n'
                   % (m.group("indent"), TERM % code, m.group("comma")))
        done.append((code, "added"))
    return "".join(out), done


def no_duplicate_keys(pairs):
    """json object hook that refuses a repeated key.

    Writing a second "access_rules" into an object is valid JSON -- the last one
    wins -- so a misplaced insert parses cleanly and quietly throws the rule
    away. That is how the first draft of this script got the three sections
    that write visibility_rules above access_rules wrong.
    """
    seen = set()
    for key, _ in pairs:
        if key in seen:
            sys.exit("duplicate %r key in the same object -- the rewrite is wrong" % key)
        seen.add(key)
    return dict(pairs)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true",
                      help="report what would change, change nothing")
    mode.add_argument("--apply", action="store_true", help="rewrite in place")
    args = ap.parse_args()

    work = 0
    for rel in FILES:
        path = os.path.join(PACK, rel)
        with open(path) as handle:
            text = handle.read()
        new, done = convert(text)
        json.loads(new, object_pairs_hook=no_duplicate_keys)
        if not done:
            print("%s: nothing to convert" % rel)
            continue
        work += len(done)
        merged = sum(1 for _, how in done if how == "merged")
        print("%s: %d sections (%d merged into existing rules, %d given new ones)"
              % (rel, len(done), merged, len(done) - merged))
        if args.apply:
            with open(path, "w") as handle:
                handle.write(new)

    for code, why in sorted(KEEP_HIDDEN.items()):
        print("left hiding: %s -- %s" % (code, why))

    if args.check and work:
        print("\n%d sections still hide instead of reporting Inspect;"
              " run with --apply" % work, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
