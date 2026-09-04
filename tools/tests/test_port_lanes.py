"""Carrying a lane to another cartridge must not quietly change the drawing.

The port is a copy, and the whole risk in a copy is that it looks like one
while altering what it carries. Every check here is a way the drawn judgement
could be lost while the tally still said "ported":

  * **the lanes go across verbatim** -- same stops, same `at` hints, same
    `region`, same order, and `retrace` carried rather than defaulted. The
    typed kinds mean a stop *can* be re-resolved on the target, which is
    exactly why dropping the hints is tempting and exactly why it is wrong:
    with both ends free to move a route lane collapses to the cheapest pair of
    ends the floor offers, which is a shorter walk than the one drawn;
  * **an entry is added, never replaced.** The source layout has to survive the
    port, or carrying a lane to a second cartridge loses it on the first;
  * **the acceptance test is the drawing code.** A port this tool accepts and
    regen_maps then refuses is the one failure worth designing against, so a
    ported entry is checked by loading it the way the art does;
  * **a refusal names a stop.** The floors that refuse are an authoring pass,
    and which stop gave out is the whole difference between that and a copy.

The carry is exercised against a working copy of `tools/lanes/` with the
target's own entries stripped out, so this asks the same question whether or
not a port has already landed -- a test that passed only until the port it
tests was applied would be a test that deleted itself.

Needs two cartridges that lay some floor differently: FF1_ROM is the source,
and the target is the No-Overworld oracle, the same one test_noverworld_rules
reads. Without both this skips rather than passing quietly.
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))

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

# A working copy with the target's entries stripped, so what follows measures
# the carry rather than whatever has already been carried.
keep = LF.LANES
work = tempfile.mkdtemp(prefix="lanes-port-")
for f in os.listdir(keep):
    if f.endswith(".json"):
        shutil.copy(os.path.join(keep, f), work)
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

    states, carried = {}, []
    for map_id, name in sorted(rm.MAP_FILES.items(), key=lambda kv: kv[1]):
        state, detail, entry = PL.port(src, dst, name, map_id)
        states[state] = states.get(state, 0) + 1
        if state == "ported":
            carried.append((name, map_id, entry))
        elif state == "refused":
            check(f"{name}'s refusal names a stop", "stop" in detail, True)

    check("some floor carries across", bool(carried), True)
    check("and every map is accounted for",
          sum(states.values()), len(rm.MAP_FILES))
    check("nothing is ported onto a layout the target already draws",
          [n for n, m, _ in carried
           if LF.pick(LF.read(n), dst.digest(m)) is not None], [])

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

    # --- an entry is added, and the loader draws what was added
    name, map_id, entry = carried[0]
    doc = LF.read(name)
    was = LF.pick(doc, src.digest(map_id))
    LF.write(name, dict(doc, layouts=list(doc["layouts"]) + [entry]))
    back = LF.read(name)
    check("the ported document validates", LF.validate(back), [])
    check("and the source layout is still in it",
          LF.pick(back, src.digest(map_id)), was)
    check("and the target layout is in it now too",
          LF.pick(back, dst.digest(map_id)), entry)

    lanes, why = LF.load(dst.rom, dst.graph, map_id, dst.chests, name=name)
    check("and the loader draws it on the target cartridge", why, None)
    check("with the lanes that were carried, not fewer",
          len(lanes.runs) if lanes else -1, len(entry["lanes"]))
finally:
    shutil.rmtree(work, ignore_errors=True)
    LF.LANES = keep

for f in fails:
    print("     " + f)
print("ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
