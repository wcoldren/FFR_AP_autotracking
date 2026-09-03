#!/usr/bin/env python3
"""Diff two FFR Archipelago exports and attribute what moved to the flag.

Roll two cartridges one flag apart, diff their exports, and the rules that moved
are that flag's doing. That is how every flag row in `docs/ORACLE.md` was
produced -- about fifteen times, by hand, with no committed tool. This is the
tool.

    export_diff.py A B                0 = same, 1 = differs, 2 = incomparable

A and B are FFR's own Archipelago export (`<seed>.yaml`), or a directory holding
exactly one -- which is how `seeds/ff1/oracle-4.9.7/` is laid out, one cartridge
per directory. `check_logic.parse_ap_rules` reads them, so the Archipelago-side
spellings (a generated yaml, a spoiler) are read too.

## What is signal and what is roll

The corpus README says "anything that moves between one of those exports and
`std497`'s is the flag and not the roll". **That is true of the rules and not of
the pool**, and the difference is the whole reason this tool draws the line where
it does. Changing a flag changes the RNG stream, so which chests hold gold moves
even when the logic does not, and FFR exports only the locations holding pool
items. Measured across all fifteen 4.9.7 one-flag variants against `std497`:

    variant             pool +   pool -   rules moved
    hoard497                17       20             0
    dock497                 21       22             1
    objnpc497               21       23             1
    extended497             20       20            20
    airship497              17       19           124

Every pair churns seventeen to twenty-three locations in *both* directions,
including `hoard497`, which moves no rule at all. A differ that reported that
churn as the flag's effect would be wrong on all fifteen, and would report a
finding for a flag that changed nothing. So the pool difference is printed under
its own heading, called what it is, and is not counted.

The three things that are signal, and were stable across all fifteen pairs where
they were not the flag's own doing:

  rules       on locations both exports carry. The comparison is a set of sets
              -- OR of ANDs, and neither order means anything -- so a rule
              printed in a different order is not a difference.
  location ids  never moved in fifteen pairs. `LOCATION_MAPPING` is keyed on the
              id, so one that moves breaks the address book silently, which is
              worth a row of its own even though nothing has ever tripped it.
  priority_locations  the incentive pool. Identical across all fifteen, so it
              is not roll noise, and it is where a flag like the computed
              `IncentivizeCaravan` lands.

## Three answers, not two

Attribution is only sound between two cartridges of the same seed -- that is the
precondition the corpus was built on, not a nicety -- so a pair that cannot be
certified as one seed is `incomparable` and exits 2 rather than reporting a
difference count. An export that cannot be read is the same answer: this tool
would otherwise inherit `parse_ap_rules`'s empty dict and report "no changes"
for a file it never read, which is the cheerful zero `ap_location_paths` was
just fixed for (`docs/ROADMAP.md` section 5).
"""

import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "ffr_flags"))

import check_logic                                              # noqa: E402
import ffr_flags                                                # noqa: E402

# `4-9-7.finalfantasyrandomizer.com/?s=3B7E1C8A&f=oml...`. The version label is
# how the ROM spells it too, so it indexes ffr_flags' schemas directly.
PERMALINK = re.compile(r"^(\d+-\d+-\d+)\.")
SEED = re.compile(r"[?&]s=([0-9A-Fa-f]+)")


def refuse(message):
    """Exit 2, not 1. An export this tool cannot read and a pair it cannot
    compare are both "I cannot tell", and 1 means "these differ" -- the one
    reading that turns a tool that never ran into a finding."""
    print("export_diff: " + message, file=sys.stderr)
    raise SystemExit(2)


def find_export(path):
    """The export at `path`, or the single one inside it if it is a directory.

    Two in one directory is a refusal rather than a pick. `check_logic` globs
    `*.yaml` beside a ROM and folds two exports together into divergences that
    are not real, which is why the corpus is one cartridge per directory; making
    the same mistake quietly here would be worse, since there is no cartridge to
    say which of the two was meant.
    """
    path = os.path.expanduser(path)
    if not os.path.isdir(path):
        if not os.path.exists(path):
            refuse("no such export: %s" % path)
        return path
    found = sorted(glob.glob(os.path.join(path, "*.yaml")))
    if len(found) == 1:
        return found[0]
    refuse("%s holds %d *.yaml files, name one" % (path, len(found)))


def normalise(rules):
    """{location: set of alternatives}, each alternative a frozenset of terms.

    Both levels are unordered: the clause list is an OR and each clause is an
    AND. Comparing the printed lists instead would report a rule FFR emitted in
    another order as a difference, which is the noisiest possible false finding.
    """
    return {name: frozenset(frozenset(clause) for clause in clauses)
            for name, clauses in rules.items()}


def read(path):
    """Everything this tool compares about one export.

    `rules` is required and an empty one is fatal. Every other section is
    optional and its absence is recorded as absence, not as an empty set -- an
    Archipelago spoiler carries the rules and nothing else, and reporting "21
    priority locations removed" because the other shape does not carry them
    would be a finding invented out of a file format.
    """
    name = os.path.basename(path)
    rules = check_logic.parse_ap_rules(path)
    if not rules:
        refuse("no rules could be read from %s\n"
               "  an export this tool cannot read is not an export with "
               "nothing in it" % path)

    blob = None
    try:
        with open(path, errors="replace") as handle:
            blob = json.load(handle)
    except ValueError:
        pass
    game = {}
    if isinstance(blob, dict):
        for scope in (blob, *(v for v in blob.values() if isinstance(v, dict))):
            if isinstance(scope, dict) and "rules" in scope:
                game = scope
                break

    out = {
        "name": name,
        "rules": normalise(rules),
        "locations": game.get("locations") if isinstance(game.get("locations"), dict) else None,
        "priority": (set(game["priority_locations"])
                     if isinstance(game.get("priority_locations"), list) else None),
        "version": None, "seed": None, "flags": None, "why": None,
    }

    permalink = blob.get("permalink") if isinstance(blob, dict) else None
    if not permalink:
        out["why"] = "no permalink in this export"
        return out
    match, seed = PERMALINK.match(permalink), SEED.search(permalink)
    out["version"] = match.group(1) if match else None
    out["seed"] = seed.group(1) if seed else None
    if out["version"] is None:
        out["why"] = "no FFR version in the permalink"
        return out
    schema = ffr_flags.load_schema(out["version"])
    if schema is None:
        out["why"] = ("no schema for FFR %s (see tools/ffr_flags/README.md)"
                      % out["version"])
        return out
    try:
        out["flags"] = ffr_flags.decode(ffr_flags.permalink_flags(permalink), schema)
    except ffr_flags.DecodeError as err:
        out["why"] = "cannot decode the flags: %s" % err
    return out


def comparable(a, b):
    """Why these two exports cannot be compared, or None if they can.

    One question, asked in the one place that can answer it. Two cartridges of
    different seeds differ in every rule that the placement touches, so nothing
    that moves between them can be laid at a flag's door -- and an export that
    does not say which seed it is cannot certify that it is the same one. Both
    are "I cannot tell", which is a different answer from "nothing moved".
    """
    if a["seed"] is None or b["seed"] is None:
        which = a["name"] if a["seed"] is None else b["name"]
        return ("%s does not say which seed it is, so nothing that moved can be "
                "attributed to a flag rather than to the roll." % which)
    if a["seed"] != b["seed"]:
        return ("the seeds differ (%s vs %s) -- a flag can only be blamed for "
                "what moved when the roll is held still." % (a["seed"], b["seed"]))
    return None


def flag_diff(a, b):
    """(changed, only_in_a_schema, only_in_b_schema) between two flag dicts."""
    if a["flags"] is None or b["flags"] is None:
        return None, (), ()
    fa, fb = a["flags"], b["flags"]
    shared = set(fa) & set(fb)
    changed = {k: (fa[k], fb[k]) for k in shared if fa[k] != fb[k]}
    return changed, sorted(set(fa) - shared), sorted(set(fb) - shared)


def show_alt(alt):
    """One alternative, as FFR means it. `(always)` rather than `()`.

    `check_logic.show_rules` prints a whole rule and spells the empty clause
    `()`; on a diff line, where the surrounding text is already parentheses and
    item names, that reads as a printing bug rather than as "no requirement".
    """
    return "(" + " AND ".join(sorted(alt)) + ")" if alt else "(always)"


def report(a, b, ap_paths=None, pool=False):
    """Print the comparison; return the number of differences, or None.

    None means incomparable, which is neither zero nor a count.
    """
    print("A  %s   FFR %s   seed %s" % (a["name"], a["version"], a["seed"]))
    print("B  %s   FFR %s   seed %s" % (b["name"], b["version"], b["seed"]))
    for side in (a, b):
        if side["why"]:
            print("   %s: %s" % (side["name"], side["why"]))

    why = comparable(a, b)
    if why is not None:
        print("\nincomparable: %s" % why)
        return None

    if a["version"] != b["version"]:
        print("\nnote: different FFR versions, so a flag present in one schema "
              "and not the other is a version difference and not a setting.")

    changed, only_a, only_b = flag_diff(a, b)
    print()
    if changed is None:
        print("flags: not decoded on both sides, so nothing here is attributed.")
    elif changed:
        for name in sorted(changed):
            was, now = changed[name]
            print("flag: %-34s %s -> %s" % (name, was, now))
        for name in only_a:
            print("flag: %-34s only in %s's schema" % (name, a["version"]))
        for name in only_b:
            print("flag: %-34s only in %s's schema" % (name, b["version"]))
    else:
        print("flags: identical on both sides.")

    n = 0

    # The signal. Locations both exports carry, whose rule is not the same set.
    shared = sorted(set(a["rules"]) & set(b["rules"]))
    moved = [name for name in shared if a["rules"][name] != b["rules"][name]]
    print("\nrules that moved, on the %d locations both exports carry" % len(shared))
    for name in moved:
        where = (ap_paths or {}).get(name)
        print("  %s%s" % (name, "   @" + where if where else ""))
        for alt in sorted(a["rules"][name] - b["rules"][name], key=sorted):
            print("      A only  %s" % show_alt(alt))
        for alt in sorted(b["rules"][name] - a["rules"][name], key=sorted):
            print("      B only  %s" % show_alt(alt))
    if not moved:
        print("  none")
    n += len(moved)

    # Never tripped in fifteen pairs, and silent if it ever does: the pack's
    # LOCATION_MAPPING is keyed on the id, so a location that kept its name and
    # changed its id would be read as a different place with no complaint.
    if a["locations"] is None or b["locations"] is None:
        print("\nlocation ids: not carried by both export shapes, so not "
              "compared.")
    else:
        ids = sorted(name for name in set(a["locations"]) & set(b["locations"])
                     if a["locations"][name] != b["locations"][name])
        if ids:
            print("\nlocation ids that moved -- LOCATION_MAPPING is keyed on these")
            for name in ids:
                print("  %-50s %s -> %s"
                      % (name, a["locations"][name], b["locations"][name]))
            n += len(ids)

    # The incentive pool. A location set like the pool below, but stable across
    # all fifteen one-flag pairs, so a change here is the flag and gets counted.
    if a["priority"] is None or b["priority"] is None:
        print("\npriority_locations: not carried by both export shapes, so not "
              "compared.")
    else:
        gained, lost = b["priority"] - a["priority"], a["priority"] - b["priority"]
        if gained or lost:
            print("\npriority_locations (the incentive pool)")
            for name in sorted(lost):
                print("      A only  %s" % name)
            for name in sorted(gained):
                print("      B only  %s" % name)
            n += len(gained) + len(lost)

    # Not counted, and said out loud. See the module docstring for the figures.
    gained = sorted(set(b["rules"]) - set(a["rules"]))
    lost = sorted(set(a["rules"]) - set(b["rules"]))
    print("\npool: %d locations only in A, %d only in B. Not counted -- changing "
          "a flag\n      moves the RNG stream, so which chests hold gold churns "
          "by about twenty\n      either way even on a pair whose rules do not "
          "move at all." % (len(lost), len(gained)))
    if pool:
        for name in lost:
            print("      A only  %s" % name)
        for name in gained:
            print("      B only  %s" % name)

    print("\n%d difference%s" % (n, "" if n == 1 else "s"))
    if n and changed is not None and not changed:
        print("...and the flags are identical, so nothing here has anything to "
              "be attributed to.\nTwo cartridges of one seed and one flagset "
              "should produce one export.")
    return n


def main():
    ap = argparse.ArgumentParser(
        description="Diff two FFR Archipelago exports one flag apart")
    ap.add_argument("export_a", help="an export, or a directory holding one")
    ap.add_argument("export_b", help="an export, or a directory holding one")
    ap.add_argument("--pool", action="store_true",
                    help="also list the pool churn, which is roll and not flag")
    ap.add_argument("--ff1-world", default=None,
                    help="Archipelago worlds/ff1, to name the pack section each "
                         "moved rule belongs to")
    args = ap.parse_args()

    a = read(find_export(args.export_a))
    b = read(find_export(args.export_b))
    # Same policy as check_logic: a path given and not found is a typo and
    # refuses, the default being absent is an ordinary machine and skips.
    paths = check_logic.ap_location_paths(ff1=args.ff1_world)
    n = report(a, b, paths, args.pool)
    return 2 if n is None else (1 if n else 0)


if __name__ == "__main__":
    # A hundred moved rules is a normal answer here, so being piped into head is
    # the normal way to read one. Same guard as check_logic.py.
    try:
        import signal
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (ImportError, AttributeError, ValueError):
        pass
    sys.exit(main())
