"""The ToFR diff has to be able to fail, and has to know when it cannot answer.

Needs no cartridge. A comparison tool that reports "0 differences" is worth
exactly as much as its ability to report a difference, and this one covers a
region the oracle cannot see at all -- so nothing else would catch it going
blind. Every check below mutates one thing and asserts the report moves.

The three ways this tool could quietly be wrong:

  - it compares nothing, and every pair looks identical;
  - it uses sets, so a chest that gained or lost a twin on the same map reads
    as no change (six treasure indices really do sit on more than one tile);
  - it treats a shape difference as a shuffle difference, or worse as
    agreement, when GameMode and ToFRMode decide which floors exist in the
    first place and how they are wired in -- including ToFRMode Random, which
    records the setting and not the roll, so equal flags mean nothing.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import tofr_diff as td                                         # noqa: E402


def cart(tofr_mode=2, game_mode=2, teleports=None, chests=None, inbound=None):
    """A read() result, built by hand rather than off a cartridge."""
    maps = {}
    for name in td.TOFR_MAPS:
        maps[name] = {
            "teleports": collections.Counter((teleports or {}).get(name, [])),
            "chests": collections.Counter((chests or {}).get(name, [])),
        }
    return {"game_mode": game_mode, "tofr_mode": tofr_mode, "maps": maps,
            "inbound": collections.Counter(inbound or [])}


CHAOS = "TempleOfFiendsRevisitedChaos"
AIR = "TempleOfFiendsRevisitedAir"

# Rows carry the shapes read() actually builds: a chest is (index, col, row) and
# an inbound link is (source, destination, arrival x, arrival y). Fixtures that
# drift from the real shapes still pass, and stop meaning anything.
BASE = dict(
    teleports={CHAOS: [(15, 5, "norm", "TempleOfFiends", 7, 7)],
               AIR: [(2, 2, "norm", CHAOS, 15, 3)]},
    # 248-254 in a block, which is what ToFRMode 2 actually puts there, plus a
    # deliberate twin: one index on two tiles of the same map.
    chests={CHAOS: [(248, 12, 1), (249, 13, 1), (250, 14, 1), (251, 15, 1),
                    (252, 16, 1), (253, 17, 1), (254, 18, 1)],
            AIR: [(200, 4, 4), (200, 9, 9)]},
    inbound=[("TempleOfFiends (3,3)", CHAOS, 15, 3)],
)


def main():
    fails = []

    def check(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")
        print(f"{'ok  ' if got == want else 'FAIL'} {label}")

    a = cart(**BASE)

    check("a cartridge against itself is 0",
          td.report(a, cart(**BASE), "a", "a"), 0)

    # A staircase repointed at a different floor.
    moved = dict(BASE, teleports=dict(BASE["teleports"],
                                      **{AIR: [(2, 2, "norm", "TempleOfFiends", 7, 7)]}))
    check("a staircase that moved is 2 rows (gone from A, new in B)",
          td.report(a, cart(**moved), "a", "b"), 2)

    # A chest that moved to another ToFR floor.
    lost = dict(BASE, chests=dict(BASE["chests"],
                                  **{CHAOS: BASE["chests"][CHAOS][:-1],
                                     AIR: BASE["chests"][AIR] + [(254, 18, 1)]}))
    check("a chest that moved floors shows on both floors",
          td.report(a, cart(**lost), "a", "b"), 2)

    # ...and a chest that moved *within* one floor. Index alone cannot see this,
    # and it is the case that changes reachability without changing the map.
    slid = dict(BASE, chests=dict(BASE["chests"],
                                  **{CHAOS: BASE["chests"][CHAOS][:-1] + [(254, 2, 9)]}))
    check("a chest that moved within one floor is a difference",
          td.report(a, cart(**slid), "a", "b"), 2)

    # The multiset check: index 200 sits on two Air tiles; drop one only.
    twin = dict(BASE, chests=dict(BASE["chests"], **{AIR: [(200, 4, 4)]}))
    check("losing one of two tiles sharing an index is a difference",
          td.report(a, cart(**twin), "a", "b"), 1)

    # An inbound link the other cartridge does not have -- here an overworld
    # door repointed into ToFR, which is what entrance shuffle does.
    extra = dict(BASE, inbound=BASE["inbound"] + [("door Cardia1 (#0)", AIR, 2, 2)])
    check("a new way into ToFR is a difference",
          td.report(a, cart(**extra), "a", "b"), 1)

    # Incomparable is its own answer -- not 0, and not a count.
    check("a different ToFRMode is incomparable, not agreement",
          td.report(a, cart(**dict(BASE, tofr_mode=0)), "a", "b"), None)

    check("a different GameMode is incomparable, not agreement",
          td.report(a, cart(**dict(BASE, game_mode=0)), "a", "b"), None)

    # Both sides say 3, and 3 is "Random": the flag records the setting, so one
    # of these can be Long while the other is Short. Equal is not comparable.
    rnd = cart(**dict(BASE, tofr_mode=td.TOFR_MODE_RANDOM))
    check("ToFRMode Random on both sides is incomparable, not agreement",
          td.report(rnd, cart(**dict(BASE, tofr_mode=td.TOFR_MODE_RANDOM)),
                    "a", "b"), None)

    check("no ToFRMode at all is incomparable",
          td.report(cart(**dict(BASE, tofr_mode=None)),
                    cart(**dict(BASE, tofr_mode=None)), "a", "b"), None)

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
