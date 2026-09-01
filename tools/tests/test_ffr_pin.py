"""The FFR revision the schemas were built from is the one the workspace pins.

A flag schema is only meaningful against the FFR build it was generated from:
ffr_flags.py:102 refuses a cartridge whose stamped SHA disagrees with the
schema's `build_sha`, which is the check that stops a 4.9.8 seed being read with
4.9.7's layout. That refusal compares the *ROM* to the schema. Nothing compared
either of them to the checkout on disk, so the chain that makes the whole thing
reproducible was three hops long and enforced at one of them:

    pins.yaml pinned_commit  ==  FFRVersion.cs's stamped Sha  ==  schema build_sha

**Three links, two independent sources.** `gen_schema.py`'s `git_sha()` derives
`build_sha` from `stamped_sha()`, so the right-hand pair cannot disagree once a
schema has been regenerated from the checkout it names -- they are one value
read twice. The term that can drift is the left one, `pins.yaml`'s hand-typed
`pinned_commit`: FFR substitutes `Sha` during its own deploy and leaves the
literal "SHA" in source, so an oracle worktree has to stamp it, and a
hand-typed value that nothing checks is a value that drifts. Holding both
right-hand terms against it is the check; the redundancy between them is kept
because a schema regenerated from a *different* tree than the one it claims
would break it.

Ancestry, not equality, for the checkout itself: both oracle worktrees sit two
local commits above their pin (the FF1R export commit and the FFRVersion stamp),
so comparing HEADs would fail on a tree that is exactly right.

Needs the workspace and the FFR checkouts; without them this skips. Somebody who
installed the pack as a PopTracker pack has neither and must not see a failure.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import ffr_source                                              # noqa: E402

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s: got %r, want %r" % (label, got, want))
    print("%s %-52s %s" % ("ok  " if got == want else "FAIL", label, got))


# The ROM carries exactly seven characters of SHA -- ffr_flags.py sizes the
# field as 255**7 -- while pins.yaml abbreviates at whatever length git handed
# whoever wrote the block, and 7, 8 and 9 all occur in the file today. Exact
# equality would make this test unsatisfiable the day either FFR pin is
# rewritten at git's auto-abbreviated length: no correct value would exist.
MIN_ABBREV = 7


def same_commit(a, b):
    """Do two abbreviated SHAs name the same commit, to the shorter's length?"""
    if not a or not b:
        return False
    n = min(len(a), len(b))
    return n >= MIN_ABBREV and a[:n] == b[:n]


pins = ffr_source.pins_file()
if pins is None:
    print("SKIP  no workspace pins.yaml -- set AP_PINS to one")
    sys.exit(0)

checked = 0
for version in sorted(ffr_source.VERSIONS):
    schema_path = os.path.join(TOOLS, "ffr_flags", "schemas", version + ".json")
    if not os.path.exists(schema_path):
        continue
    with open(schema_path) as handle:
        build_sha = json.load(handle)["build_sha"]

    pinned = ffr_source.pinned_commit(version)
    check("%s: pins.yaml claims the worktree" % version, pinned is not None, True)
    if pinned is None:
        continue
    check("%s: schema build_sha is the pinned commit" % version,
          same_commit(build_sha, pinned), True)
    if not same_commit(build_sha, pinned):
        print("     schema %r vs pin %r" % (build_sha, pinned))

    src = ffr_source.checkout(version)
    if src is None:
        print("SKIP  " + ffr_source.skip_reason(version))
        continue
    checked += 1

    # Ancestry, because the worktree carries local commits the pin does not.
    check("%s: the pinned commit is in the checkout's history" % version,
          ffr_source.is_ancestor(src, pinned), True)
    # And the stamp, which is the term that ties a built ROM to the schema.
    check("%s: FFRVersion.cs stamps that same commit" % version,
          same_commit(ffr_source.stamped_sha(src), pinned), True)

# ------------------------------------------------------------------ what ran
#
# Every checkout-dependent check above sits inside a loop that a missing
# worktree skips, so an empty run and a clean run would otherwise print the same
# "ALL PASS". This says which happened. It is not a failure when the answer is
# "none": `vendor/` is gitignored and these are `git worktree`s, so a fresh
# workspace clone has the pins and not the trees, and ffr_source is built around
# a missing checkout being a skip. The pins.yaml-to-schema half above ran either
# way, and that half is the one that catches a hand-typed pin drifting.
print("-- what actually ran")
if checked:
    check("at least one FFR checkout was compared", checked >= 1, True)
else:
    print("SKIP  no FFR checkout on disk -- only the pins.yaml/schema half ran")

# ------------------------------------------------------------------ it bites
#
# The failure this exists for is a schema regenerated against a moved checkout,
# so that is the mutation worth demonstrating rather than describing. Each row
# below demonstrates one term, because the two terms bite in opposite
# directions and a conjunction of them would hide which one fired.

print("-- and it bites")

# Ancestry discriminates one way round only, and this is that way round: 4.9.7's
# release commit is not in the 4.9.2 worktree's history. The mirror row would
# prove nothing -- 4.9.2's release commit genuinely *is* an ancestor of the
# 4.9.7 worktree, so is_ancestor(4-9-7, pin(4-9-2)) is True. Measured
# 2026-09-01; a rewound 4.9.7 tree is caught by the stamp row, not by this one.
older = ffr_source.checkout("4-9-2")
newer_pin = ffr_source.pinned_commit("4-9-7")
if older is None:
    print("SKIP  " + ffr_source.skip_reason("4-9-2"))
elif newer_pin is None:
    print("SKIP  pins.yaml has no ff1_randomizer_497 pinned_commit")
else:
    check("a later version's pin is not in an earlier checkout's history",
          ffr_source.is_ancestor(older, newer_pin), False)

# The stamp discriminates the other way round, and is the term that ties a built
# ROM to a schema, so a 4.9.7 tree rewound to 4.9.2 fails here.
src = ffr_source.checkout("4-9-7")
older_pin = ffr_source.pinned_commit("4-9-2")
if src is None:
    print("SKIP  " + ffr_source.skip_reason("4-9-7"))
else:
    if older_pin is None:
        print("SKIP  pins.yaml has no ff1_randomizer_492 pinned_commit")
    else:
        check("the wrong version's pin is not what 4.9.7 stamps",
              same_commit(ffr_source.stamped_sha(src), older_pin), False)
    check("and a commit that is in no history at all is rejected",
          ffr_source.is_ancestor(src, "0" * 40), False)

# The prefix comparison has to reject as well as accept, or the two rows above
# would pass on a helper that always said False.
check("a SHA that shares no prefix is not the same commit",
      same_commit("1f31434", "01272d4"), False)
check("and abbreviations of different length still agree",
      same_commit("1f31434", "1f314349a"), True)
check("but a stub too short to mean anything does not",
      same_commit("1f3", "1f31434"), False)

for f in fails:
    print("     " + f)
print("ALL PASS" if not fails else "%d FAILED" % len(fails))
sys.exit(1 if fails else 0)
