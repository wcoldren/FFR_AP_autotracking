"""The FFR revision the schemas were built from is the one the workspace pins.

A flag schema is only meaningful against the FFR build it was generated from:
ffr_flags.py:102 refuses a cartridge whose stamped SHA disagrees with the
schema's `build_sha`, which is the check that stops a 4.9.8 seed being read with
4.9.7's layout. That refusal compares the *ROM* to the schema. Nothing compared
either of them to the checkout on disk, so the chain that makes the whole thing
reproducible was three hops long and enforced at one of them:

    pins.yaml pinned_commit  ==  FFRVersion.cs's stamped Sha  ==  schema build_sha

The middle term is hand-typed -- FFR substitutes `Sha` during its own deploy and
leaves the literal "SHA" in source, so an oracle worktree has to stamp it -- and
a hand-typed value that nothing checks is a value that drifts.

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
          build_sha, pinned)

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
          ffr_source.stamped_sha(src), pinned)

# ------------------------------------------------------------------ not vacuous
#
# Every check above is inside a loop that a missing file skips, so an empty run
# and a clean run print the same "ALL PASS". This is what tells them apart.
print("-- the run was not empty")
check("at least one FFR checkout was actually compared", checked >= 1, True)

# ------------------------------------------------------------------ it bites
#
# The failure this exists for is a schema regenerated against a moved checkout,
# so that is the mutation worth demonstrating rather than describing.
print("-- and it bites")
src = ffr_source.checkout("4-9-7")
if src is None:
    print("SKIP  " + ffr_source.skip_reason("4-9-7"))
else:
    other = ffr_source.pinned_commit("4-9-2")
    check("a pin from the wrong FFR version is not an ancestor",
          ffr_source.is_ancestor(src, other) and other == ffr_source.stamped_sha(src),
          False)
    check("and a commit that is in no history at all is rejected",
          ffr_source.is_ancestor(src, "0" * 40), False)

for f in fails:
    print("     " + f)
print("ALL PASS" if not fails else "%d FAILED" % len(fails))
sys.exit(1 if fails else 0)
