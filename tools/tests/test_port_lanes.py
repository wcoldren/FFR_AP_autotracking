"""Carrying a lane to another cartridge must not quietly change the drawing.

The port is a copy, and the whole risk in a copy is that it looks like one
while altering what it carries. Every check here is a way the drawn judgement
could be lost while the tally still said "ported":

  * **the lanes go across verbatim** -- same stops, same `at` hints, same
    `region`, same order, and `retrace` and `note` carried rather than
    defaulted or dropped. The typed kinds mean a stop *can* be re-resolved on
    the target, which is exactly why dropping the hints is tempting and exactly
    why it is wrong: with both ends free to move a route lane collapses to the
    cheapest pair of ends the floor offers, which is a shorter walk than the
    one drawn;
  * **the tally is pinned, not merely non-empty.** 32 carry and 10 refuse on
    the documented pairing, and the ten are named. A check that only asked
    whether *some* floor carried would pass just as happily if `lane.authored`
    started accepting everything -- which is the regression that would turn
    every one of those ten authoring passes into a silently wrong copy;
  * **an entry is added, never replaced.** The source layout has to survive the
    port, or carrying a lane to a second cartridge loses it on the first;
  * **the acceptance test is the drawing code.** A port this tool accepts and
    regen_maps then refuses is the one failure worth designing against, so
    every ported entry is checked by loading it the way the art does;
  * **a refusal names a stop.** The floors that refuse are an authoring pass,
    and which stop gave out is the whole difference between that and a copy;
  * **`--apply` is all of them or none.** The write path is exercised through
    `main`, both ways: a clean run writes every floor and a run holding one
    document that will not validate writes nothing at all. A half-carried tree
    is a state nothing on disk explains, so it is worth a test that the run
    cannot produce one.

The carry is exercised against a working copy of `tools/lanes/` with the
target's own entries stripped out, so this asks the same question whether or
not a port has already landed -- a test that passed only until the port it
tests was applied would be a test that deleted itself. The stripping is also
why the pinned counts are stable: they describe the carry from scratch, not
whatever is currently committed.

Needs two cartridges that lay some floor differently: FF1_ROM is the source,
and the target is the No-Overworld oracle, the same one test_noverworld_rules
reads. Without both this skips rather than passing quietly.
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lane_file as LF  # noqa: E402
import port_lanes as PL  # noqa: E402
import render_maps as rm  # noqa: E402

fails = []


def check(what, got, want):
    ok = got == want
    print(("ok   " if ok else "FAIL ") + what.ljust(58)
          + ("" if ok else f" {got!r}"))
    if not ok:
        fails.append(f"{what}: got {got!r}, want {want!r}")


# The pinned tally, and the ten floors that refuse. `docs/ROADMAP.md` carries
# the same figures in prose ("No-Overworld has 47 of 57"): 15 floors are laid
# tile-for-tile like their standard twins and need nothing, 32 carry, 10 are an
# authoring pass, and 4 maps were never drawn on at all. The ten are six towns
# plus tofr1F losing the arrival outright, elf_castle and nw_castle keeping an
# arrival they cannot walk from, and bahamutB2 failing on a chest index.
WANT_STATES = {"have": 15, "ported": 32, "refused": 10, "no file": 4}
WANT_REFUSED = ["bahamutB2", "coneria_town", "crescent_lake", "elf_castle",
                "elfland", "lefein", "melmond", "nw_castle", "pravoka",
                "tofr1F"]

# no new cartridge: the nov oracle already sits in the corpus every other
# No-Overworld test reads, and it lays a great many floors differently.
NOV = os.path.expanduser(
    "~/repos/AP/seeds/ff1/oracle-4.9.2/nov/oracle_nov.nes")
src_path = os.environ.get("FF1_ROM")
if not src_path or not os.path.isfile(src_path):
    print("skipped: FF1_ROM names no cartridge to port from")
    sys.exit(0)
if not os.path.isfile(NOV):
    print(f"skipped: no No-Overworld oracle at {NOV}")
    sys.exit(0)

src, dst = PL.Side(src_path), PL.Side(NOV)
check("the two cartridges are not the same one", src.stamp == dst.stamp, False)

# Whether the counts above describe *this* source cartridge. They are a fact
# about the pairing, not about the tool, so pinning them against a cartridge
# the committed lanes were never drawn on would fail for the one reason that
# is not a defect. Every committed entry records what it was drawn against, so
# the tree can answer this itself rather than naming a seed here.
drawn_on = set()
for _n in sorted(set(rm.MAP_FILES.values())):
    for _e in (LF.read(_n) or {}).get("layouts", ()):
        drawn_on.update(_e.get("seen", ()))
pinned = src.stamp in drawn_on
if not pinned:
    print("note: FF1_ROM is not a cartridge these lanes were drawn on, so the"
          "\n      pinned counts are checked as shape rather than as figures")

# A working copy with the target's entries stripped, so what follows measures
# the carry rather than whatever has already been carried.
keep = LF.LANES
work = tempfile.mkdtemp(prefix="lanes-port-")
for f in os.listdir(keep):
    if f.endswith(".json"):
        shutil.copy(os.path.join(keep, f), work)


def snapshot():
    """Every lane file in the working tree, by name. For "nothing changed"."""
    out = {}
    for f in sorted(os.listdir(work)):
        if f.endswith(".json"):
            with open(os.path.join(work, f)) as fh:
                out[f] = fh.read()
    return out


def run_main(*extra):
    """(exit code, output) for a real `port_lanes.py` run over the work tree.

    Through `main` and its argument parsing rather than around them: the
    build/validate/write path lives there, and a test that re-implements the
    append checks its own copy of the logic instead of the tool's.
    """
    argv = sys.argv
    sys.argv = ["port_lanes.py", "--from", src_path, "--to", NOV] + list(extra)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = PL.main()
    finally:
        sys.argv = argv
    return code, buf.getvalue()


try:
    LF.LANES = work
    for map_id, name in rm.MAP_FILES.items():
        doc = LF.read(name)
        if doc is None:
            continue
        s, d = src.digest(map_id), dst.digest(map_id)
        if s == d:
            # One entry serves both cartridges; stripping it would take the
            # source away too, and "the target already has it" is the honest
            # state of that floor.
            continue
        left = [e for e in doc.get("layouts", ()) if e.get("digest") != d]
        if left and len(left) != len(doc["layouts"]):
            LF.write(name, dict(doc, layouts=left))

    states, carried, refused = {}, [], []
    for map_id, name in sorted(rm.MAP_FILES.items(), key=lambda kv: kv[1]):
        state, detail, entry = PL.port(src, dst, name, map_id)
        states[state] = states.get(state, 0) + 1
        if state == "ported":
            carried.append((name, map_id, entry))
        elif state == "refused":
            refused.append(name)
            check(f"{name}'s refusal names a stop", "stop" in detail, True)

    check("every map is accounted for",
          sum(states.values()), len(rm.MAP_FILES))
    if pinned:
        check("the tally is the one the roadmap describes", states,
              WANT_STATES)
        check("and the floors that refuse are the ten named there",
              refused, WANT_REFUSED)
    else:
        # Weaker, but still both directions: a tool that accepted everything
        # and one that refused everything each fail one of these.
        check("some floor carries across", bool(carried), True)
        check("and some floor refuses rather than being copied",
              bool(refused), True)

    # --- verbatim, on every floor that carried
    moved, lost_hint, rekeyed = [], [], []
    for name, map_id, entry in carried:
        was = LF.pick(LF.read(name), src.digest(map_id))
        if entry["lanes"] != was["lanes"]:
            moved.append(name)
        if was.get("retrace") != entry.get("retrace"):
            moved.append(name + " (retrace)")
        for a, b in zip(was["lanes"], entry["lanes"]):
            if a.get("region") != b.get("region"):
                lost_hint.append(name + " (region)")
            for s_, t_ in zip(a["stops"], b["stops"]):
                if s_.get("at") != t_.get("at") or s_.get("kind") != t_.get("kind"):
                    lost_hint.append(name)
        if entry["digest"] != dst.digest(map_id):
            rekeyed.append(name)
    check("a ported lane is the drawn lane, stop for stop", moved, [])
    check("and every authored `at` hint and region survives", lost_hint, [])
    check("the ported entry is keyed to the target, not the source",
          rekeyed, [])
    check("and says which cartridge it was carried to",
          sorted({tuple(e["seen"]) == (dst.stamp,) for _, _, e in carried}),
          [True])

    # --- and carries a key the copy was never told about
    # `note` is the live case: lane_edit writes it, no committed entry has one
    # yet, and a copy built from a listed set of keys drops it without
    # anything failing. Injected on the source side and read back off the port.
    name, map_id, _ = carried[0]
    before = LF.read(name)
    was = LF.pick(before, src.digest(map_id))
    LF.write(name, dict(before, layouts=[
        dict(e, note="carried by hand") if e is was else e
        for e in before["layouts"]]))
    _, _, with_note = PL.port(src, dst, name, map_id)
    check("an entry key the copy never heard of travels too",
          with_note.get("note"), "carried by hand")
    LF.write(name, before)
    check("and the injection is out of the tree again",
          LF.pick(LF.read(name), src.digest(map_id)), was)

    # --- a run that cannot validate one document writes none of them
    # map_id is the cheapest way to make a document `validate` refuses while
    # leaving its layouts portable, so this floor reaches the write path and
    # then fails it. Every other floor is fine, which is the point: the run is
    # what has to be all-or-nothing, not the file.
    name, map_id, _ = carried[0]
    good = LF.read(name)
    LF.write(name, dict(good, map_id=good["map_id"] + 1))
    was_on_disk = snapshot()
    code, out = run_main("--apply")
    check("a document that will not validate fails the run", code, 1)
    check("and names the floor that would not validate", name in out, True)
    check("and nothing at all was written", snapshot(), was_on_disk)
    LF.write(name, good)

    # --- the clean run, through main and --apply
    code, out = run_main("--apply")
    check("the carry applies cleanly", code, 0)
    check("and reports what it wrote, not what it tried",
          f"wrote {len(carried)} file(s)" in out, True)

    added, lost, undrawn, redrawn = [], [], [], []
    for name, map_id, entry in carried:
        back = LF.read(name)
        if LF.validate(back):
            added.append(name)
        if LF.pick(back, dst.digest(map_id)) != entry:
            added.append(name + " (entry)")
        # The source layout has to still be there: a port that replaced it
        # would carry the lane to the second cartridge by losing it on the
        # first, and every check above would still pass.
        if LF.pick(back, src.digest(map_id)) is None:
            lost.append(name)
        # The acceptance test is the drawing code, on every floor rather than
        # on a sample of one.
        lanes, why = LF.load(dst.rom, dst.graph, map_id, dst.chests, name=name,
                             fixed=dst.fixed)
        if why is not None:
            undrawn.append(f"{name}: {why}")
        elif len(lanes.runs) != len(entry["lanes"]):
            redrawn.append(name)
    check("every carried floor is on disk and validates", added, [])
    check("and the source layout survived the port", lost, [])
    check("and the target cartridge draws every one of them", undrawn, [])
    check("with the lanes that were carried, not fewer", redrawn, [])

    # --- and a second run finds nothing left to do
    # The replacement for a check that could not fail: asking whether anything
    # was ported onto a layout the target already draws is tautological under a
    # fixture that stripped exactly those layouts. Asking it *after* the write
    # is not -- an append that rekeyed or duplicated an entry shows up here.
    again = {}
    for map_id, name in sorted(rm.MAP_FILES.items(), key=lambda kv: kv[1]):
        state, _, _ = PL.port(src, dst, name, map_id)
        again[state] = again.get(state, 0) + 1
    check("re-running the carry finds every floor already there",
          again.get("ported", 0), 0)
    check("and moved them into `have` rather than losing them",
          again.get("have", 0), states.get("have", 0) + len(carried))

    code, out = run_main()
    check("and a dry run over a finished tree has nothing to offer",
          (code, "ported (" in out), (0, False))
finally:
    shutil.rmtree(work, ignore_errors=True)
    LF.LANES = keep

for f in fails:
    print("     " + f)
print("ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
