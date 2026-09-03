"""The export diff has to be able to fail, and must not fire on the roll.

Needs no cartridge and no export. Every check builds two `read()` results by
hand and asserts the report moves, or does not.

The five ways this tool could quietly be wrong:

  - it compares nothing, and every pair of exports looks identical;
  - it compares the printed rule rather than the rule, so FFR emitting the same
    or-of-ands in another order reads as every location having moved;
  - it counts the pool churn, and then every pair is a finding -- changing a
    flag moves the RNG stream, so which chests hold gold churns by about twenty
    either way even on a pair whose rules do not move at all. This is the one
    that would look like a working tool: fifteen flags, fifteen answers, all of
    them the roll;
  - it treats a section one export shape does not carry as an empty one, and
    reports twenty-one priority locations removed because the file is a spoiler
    rather than an FFR export;
  - it reports a pair it cannot compare as agreement, when attribution is only
    sound at one seed and an export that does not name its seed cannot certify
    even that.
"""
import contextlib
import io
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import export_diff as ed                                        # noqa: E402


def side(name="a", seed="3B7E1C8A", version="4-9-7", rules=None, locations=None,
         priority=None, flags=None, why=None):
    """A read() result, built by hand rather than off an export."""
    return {
        "name": name, "seed": seed, "version": version, "why": why,
        "flags": flags if flags is not None else {"MapDragonsHoard": False},
        "rules": ed.normalise(rules if rules is not None else BASE_RULES),
        "locations": locations, "priority": priority,
    }


# The shapes FFR actually emits: an or-of-ands per location, `[[]]` for a
# location with no requirement at all -- which is a real value in std497's
# export and not a stand-in for "missing".
BASE_RULES = {
    "Coneria Castle - Treasury 2": [["Key"]],
    "Cardia Forest Island - Entrance 1": [["Canoe", "Floater"], ["Ship"]],
    "Shop Item": [[]],
}
BASE_LOCS = {"Coneria Castle - Treasury 2": 258,
             "Cardia Forest Island - Entrance 1": 300, "Shop Item": 400}
BASE_PRIO = {"Coneria Castle - Treasury 2"}


def run(a, b, **kw):
    """(differences, what it printed). Captured so the ok/FAIL lines are
    readable; the text is asserted on where the message is the point."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        n = ed.report(a, b, **kw)
    return n, buf.getvalue()


def main():
    fails = []

    def check(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")
        print(f"{'ok  ' if got == want else 'FAIL'} {label}")

    a = side("a", locations=BASE_LOCS, priority=set(BASE_PRIO))

    check("an export against itself is 0",
          run(a, side("b", locations=BASE_LOCS, priority=set(BASE_PRIO)))[0], 0)

    # An alternative the flag added -- the whole point of the tool.
    opened = dict(BASE_RULES)
    opened["Cardia Forest Island - Entrance 1"] = [["Canoe", "Floater"], ["Ship"],
                                                   ["Floater", "Ship"]]
    n, text = run(a, side("b", rules=opened, locations=BASE_LOCS,
                          priority=set(BASE_PRIO)))
    check("a rule that gained an alternative is 1 difference", n, 1)
    check("...and the report says which alternative, and on which side",
          "B only  (Floater AND Ship)" in text, True)

    # Order means nothing at either level: the clause list is an OR, each clause
    # an AND. Reporting either as a change would flag every location.
    shuffled = {
        "Coneria Castle - Treasury 2": [["Key"]],
        "Cardia Forest Island - Entrance 1": [["Ship"], ["Floater", "Canoe"]],
        "Shop Item": [[]],
    }
    check("the same rule in another order is not a difference",
          run(a, side("b", rules=shuffled, locations=BASE_LOCS,
                      priority=set(BASE_PRIO)))[0], 0)

    # The load-bearing one. Only the pool moved: one location gone, one arrived,
    # and every shared rule identical. That is the roll, and it happens on every
    # pair including one whose rules do not move.
    churned = {k: v for k, v in BASE_RULES.items() if k != "Shop Item"}
    churned["Ice Cave Bottom (B3) - Six-Pack 4"] = [["Tnt"]]
    churn_locs = {k: v for k, v in BASE_LOCS.items() if k != "Shop Item"}
    churn_locs["Ice Cave Bottom (B3) - Six-Pack 4"] = 500
    n, text = run(a, side("b", rules=churned, locations=churn_locs,
                          priority=set(BASE_PRIO)))
    check("pool churn alone is 0 differences", n, 0)
    check("...and is still printed, under its own heading",
          "1 locations only in A, 1 only in B" in text, True)

    # Keyed on by LOCATION_MAPPING, so a name that keeps its place and changes
    # its id is read as a different location by everything downstream.
    moved_id = dict(BASE_LOCS, **{"Shop Item": 401})
    check("a location id that moved is a difference",
          run(a, side("b", locations=moved_id, priority=set(BASE_PRIO)))[0], 1)

    # The incentive pool -- identical across all fifteen one-flag pairs, so a
    # change in it is the flag and not the roll.
    check("a priority location that moved is a difference",
          run(a, side("b", locations=BASE_LOCS,
                      priority={"Shop Item"}))[0], 2)

    # An Archipelago spoiler carries rules and neither of the other two. Absence
    # is not an empty set: this must not read as three locations removed.
    n, text = run(a, side("b", locations=None, priority=None))
    check("a section one shape does not carry is not an empty one", n, 0)
    check("...and both such sections say so rather than going quiet",
          text.count("not carried by both export shapes"), 2)

    # Incomparable is its own answer -- not 0, and not a count.
    check("a different seed is incomparable, not agreement",
          run(a, side("b", seed="1D0BE11E", locations=BASE_LOCS,
                      priority=set(BASE_PRIO)))[0], None)
    check("an export that does not name its seed is incomparable",
          run(a, side("b", seed=None, locations=BASE_LOCS,
                      priority=set(BASE_PRIO)))[0], None)

    # Same seed, same flags, and yet the rules moved. That is not a finding
    # about a flag, it is a contradiction, and saying so is the only useful
    # thing the tool can do with it.
    n, text = run(a, side("b", rules=opened, locations=BASE_LOCS,
                          priority=set(BASE_PRIO),
                          flags={"MapDragonsHoard": False}))
    check("identical flags and moved rules is called out as a contradiction",
          "nothing here has anything to be attributed to" in text, True)

    # The flag is named, which is the whole output anybody reads.
    n, text = run(a, side("b", rules=opened, locations=BASE_LOCS,
                          priority=set(BASE_PRIO),
                          flags={"MapDragonsHoard": True}))
    check("the differing flag is named", "MapDragonsHoard" in text
          and "False -> True" in text, True)

    # A file this tool cannot read must refuse, not inherit parse_ap_rules'
    # empty dict and report that nothing moved.
    with tempfile.TemporaryDirectory() as tmp:
        junk = os.path.join(tmp, "not-an-export.yaml")
        with open(junk, "w") as handle:
            handle.write("this is not an export\n")
        code = None
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                ed.read(junk)
        except SystemExit as err:
            code = err.code
        check("an unreadable export refuses with 2, not 0 differences", code, 2)

        # Two in one directory: the mistake check_logic's glob makes beside a
        # ROM, which the corpus layout exists to avoid.
        open(os.path.join(tmp, "second.yaml"), "w").close()
        code = None
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                ed.find_export(tmp)
        except SystemExit as err:
            code = err.code
        check("two exports in one directory refuses rather than picking", code, 2)

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
