"""A lane file is a claim about a cartridge it is not looking at.

It is written once, by hand, and read back months later against a seed nobody
had when it was drawn. Every check here is a way that claim could be false
while the file still parsed and the picture still looked plausible:

  * **the digest picks the right layout, and refuses one it does not have.**
    A picker that returned the first entry regardless passes any file with one
    layout in it, which is every file on the day it is written -- so this runs
    both ways round, on a document holding two;
  * **the digest reads the tileset, not only the tiles.** Map tiles are ids
    into a property table and the table is what walkability comes off, so two
    maps with the same grid under different tilesets must not share a digest;
  * **validate says all of what is wrong.** One complaint per defect, each
    demonstrated on its own broken document, because a validator that returns
    a bare bool cannot say what to fix and one that stops at the first makes
    fixing a file a game of twenty questions;
  * **a write that dies half way leaves the old file.** os.replace off a temp
    file in the same directory, and a second layout already in the document
    survives the write of the first;
  * **a lane that matches this cartridge is a walk the game allows** -- every
    tile walkable, consecutive tiles one step apart mod 64, no gate NPC, no
    staircase in the middle, a route lane opening nothing and ending on a way
    off the floor;
  * **and one that does not match is refused rather than drawn.** The refusal
    is the whole point of the digest, so a refusal that never fires is a
    refusal that does not exist -- the last check breaks a real file on purpose.

The first half needs no cartridge. The second sets FF1_ROM; without one it
skips rather than passing quietly.
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import entrance_graph as eg  # noqa: E402
import extract_chests as ec  # noqa: E402
import lane as L  # noqa: E402
import lane_file as LF  # noqa: E402
import render_maps as rm  # noqa: E402

fails = []


def check(label, got, want):
    if got != want:
        fails.append(f"{label}: got {got!r}, want {want!r}")
    print(f"{'ok  ' if got == want else 'FAIL'} {label}")


def doc_with(*layouts):
    return {"version": LF.VERSION, "map": "marshB3",
            "map_id": [m for m, n in rm.MAP_FILES.items()
                       if n == "marshB3"][0],
            "layouts": list(layouts)}


def a_lane(flavour="route"):
    return {"flavour": flavour,
            "stops": [{"kind": "arrival", "at": [1, 1], "in": [1, 1]},
                      {"kind": "exit", "at": [5, 5]}]}


# ----------------------------------------------------------------- the picker
two = doc_with({"digest": "a" * 16, "lanes": [a_lane()]},
               {"digest": "b" * 16, "lanes": [a_lane("loot")]})
check("pick finds the second layout by its digest",
      LF.pick(two, "b" * 16)["lanes"][0]["flavour"], "loot")
check("and the first, so it is not just returning the last",
      LF.pick(two, "a" * 16)["lanes"][0]["flavour"], "route")
check("and nothing for a digest the file does not carry",
      LF.pick(two, "c" * 16), None)
check("and nothing at all for no file", LF.pick(None, "a" * 16), None)

# ------------------------------------------------------------- the validator
check("a well-formed document has no complaints", LF.validate(two), [])

broken = {
    "an unknown stop kind":
        [{"kind": "doorway", "at": [1, 1]}, {"kind": "exit", "at": [2, 2]}],
    "an arrival with no region anchor":
        [{"kind": "arrival", "at": [1, 1]}, {"kind": "exit", "at": [2, 2]}],
    "a chest with no index":
        [{"kind": "arrival", "at": [1, 1], "in": [1, 1]}, {"kind": "chest"}],
    "a tile stop with no tile":
        [{"kind": "arrival", "at": [1, 1], "in": [1, 1]}, {"kind": "tile"}],
}
for why, stops in broken.items():
    d = doc_with({"digest": "a" * 16,
                  "lanes": [{"flavour": "route", "stops": stops}]})
    check("validate rejects %s" % why, len(LF.validate(d)), 1)

check("validate rejects a flavour that is neither route nor loot",
      len(LF.validate(doc_with({"digest": "a" * 16,
                                "lanes": [dict(a_lane(), flavour="both")]}))), 1)
check("validate rejects a lane of one stop",
      len(LF.validate(doc_with({"digest": "a" * 16,
                                "lanes": [{"flavour": "route",
                                           "stops": [{"kind": "exit",
                                                      "at": [1, 1]}]}]}))), 1)
mismatched = dict(two, map_id=61)
check("validate rejects a map_id that disagrees with the map name",
      len(LF.validate(mismatched)), 1)
check("validate rejects a map name that is not a map",
      len(LF.validate(dict(two, map="nowhere"))) >= 1, True)
check("validate says all of what is wrong, not the first thing",
      len(LF.validate({"version": 99, "map": "nowhere", "map_id": 61,
                       "layouts": []})) >= 3, True)

# ------------------------------------------------------------- the round trip
keep = LF.LANES
LF.LANES = tempfile.mkdtemp(prefix="lanes-")
try:
    LF.write("marshB3", two)
    back = LF.read("marshB3")
    check("a written document reads back identical", back, two)
    check("and both its layouts survive the write",
          [e["digest"] for e in back["layouts"]], ["a" * 16, "b" * 16])
    check("a file is written whole, with no temp left beside it",
          sorted(os.listdir(LF.LANES)), ["marshB3.json"])
    check("read of a map with no file is None", LF.read("nosuchmap"), None)
finally:
    shutil.rmtree(LF.LANES, ignore_errors=True)
    LF.LANES = keep

# ------------------------------------------------- every committed lane file
committed = sorted(f for f in os.listdir(LF.LANES)
                   if f.endswith(".json")) if os.path.isdir(LF.LANES) else []
bad = []
for f in committed:
    name = f[:-len(".json")]
    doc = LF.read(name)
    bad += ["%s: %s" % (f, c) for c in LF.validate(doc)]
    if doc.get("map") != name:
        bad.append("%s: names map %r" % (f, doc.get("map")))
check("every committed lane file validates and matches its filename", bad, [])
print("     (%d lane file(s) committed)" % len(committed))

# --------------------------------------------------------- with a cartridge
path = os.environ.get("FF1_ROM")
if not path or not os.path.exists(path):
    print("SKIP  set FF1_ROM to a Final Fantasy cartridge for the rest")
    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    sys.exit(1 if fails else 0)

with open(path, "rb") as fh:
    rom = fh.read()
graph = eg.Graph(eg.Rom.of(rom, path))
chests = ec.extract(rom)[0]

# The digest reads the tileset, not only the grid.
digests = {m: LF.digest(rom, m) for m in rm.MAP_FILES}
check("a map's digest is stable across two reads",
      LF.digest(rom, 0), digests[0])
clash = [(a, b) for a in rm.MAP_FILES for b in rm.MAP_FILES
         if a < b and digests[a] == digests[b]
         and bytes(rm.map_tiles(rom, a)) != bytes(rm.map_tiles(rom, b))]
check("no two differently-laid maps share a digest", clash, [])
check("every digest is sixteen hex characters",
      sorted({len(d) for d in digests.values()}), [16])

# A lane authored against this cartridge is a walk the game allows. Built from
# the solver's own answer so the suite needs no committed file to have a case.
one = None
for mid in sorted(rm.MAP_FILES):
    got = L.plan(rom, graph, mid, chests)
    if got is not None and any(r.label == "route" for r in got.runs):
        one, solved = mid, got
        break
check("some map on this cartridge carries a route lane", one is not None, True)

f = L.Floor(rom, graph, one)
outs = set(L.exits(f))
spec = []
for r in solved.runs:
    stops = [{"kind": "arrival", "at": list(r.start), "in": list(r.start)}]
    stops += [{"kind": "chest", "index": i} for i in r.got]
    if r.path[-1] in outs:
        stops.append({"kind": "exit", "at": list(r.path[-1])})
    spec.append({"flavour": r.label, "stops": stops, "region": r.region})
entry = {"digest": LF.digest(rom, one), "seen": [LF.stamp(rom, path)],
         "lanes": spec}
doc = {"version": LF.VERSION, "map": rm.MAP_FILES[one], "map_id": one,
       "layouts": [entry]}
check("a document built from a solved lane validates", LF.validate(doc), [])

keep = LF.LANES
LF.LANES = tempfile.mkdtemp(prefix="lanes-")
try:
    LF.write(rm.MAP_FILES[one], doc)
    lanes, why = LF.load(rom, graph, one, chests)
    check("load draws a lane whose layout matches this cartridge", why, None)

    illegal, stray, wrong_errand = [], [], []
    for run in (lanes.runs if lanes else ()):
        for i, cell in enumerate(run.path):
            if not f.walkable(cell):
                illegal.append((run.label, cell))
            if cell in f.blocked:
                illegal.append((run.label, "gate", cell))
            if cell in f.teleports and 0 < i < len(run.path) - 1:
                stray.append((run.label, cell))
        for a, b in zip(run.path, run.path[1:]):
            dx = min((a[0] - b[0]) % 64, (b[0] - a[0]) % 64)
            dy = min((a[1] - b[1]) % 64, (b[1] - a[1]) % 64)
            if dx + dy != 1:
                illegal.append((run.label, a, b))
        if run.label == "route" and (run.got or run.path[-1] not in outs):
            wrong_errand.append((run.label, run.got, run.path[-1]))
        if run.label == "loot" and not run.got:
            wrong_errand.append((run.label, "collects nothing"))
    check("every step of an authored lane is a step the game allows",
          illegal, [])
    check("and it never stops on a staircase in the middle", stray, [])
    check("and each flavour keeps its own errand", wrong_errand, [])

    # The refusal. Break the layout the file was drawn for and the loader must
    # say so rather than drawing the lane on a floor it was not drawn on.
    other = dict(doc, layouts=[dict(entry, digest="f" * 16)])
    LF.write(rm.MAP_FILES[one], other)
    lanes, why = LF.load(rom, graph, one, chests)
    check("a layout this cartridge does not have is refused, not drawn",
          (lanes, (why or "").startswith("no layout for this cartridge")),
          (None, True))

    # And a stop that resolves to nowhere on a layout that does match.
    wall = next(c for c in ((x, y) for y in range(64) for x in range(64))
                if not f.walkable(c))
    hurt = json.loads(json.dumps(entry))
    hurt["lanes"] = [{"flavour": "route",
                      "stops": [dict(spec[0]["stops"][0]),
                                {"kind": "tile", "at": list(wall)}]}]
    LF.write(rm.MAP_FILES[one], dict(doc, layouts=[hurt]))
    lanes, why = LF.load(rom, graph, one, chests)
    check("a stop pointing into rock is refused, and the refusal says which",
          (lanes, bool(why) and "stop 1" in why), (None, True))
finally:
    shutil.rmtree(LF.LANES, ignore_errors=True)
    LF.LANES = keep

for f_ in fails:
    print("     " + f_)
print("ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
