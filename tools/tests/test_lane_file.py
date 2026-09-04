"""A lane file is a claim about a cartridge it is not looking at.

It is written once, by hand, and read back months later against a seed nobody
had when it was drawn. Every check here is a way that claim could be false
while the file still parsed and the picture still looked plausible:

  * **the digest picks the right layout, and refuses one it does not have.**
    A picker that returned the first entry regardless passes any file with one
    layout in it, which is every file on the day it is written -- so this runs
    both ways round, on a document holding two;
  * **the digest reads the tile properties, not only the tiles.** Map tiles are
    ids into a per-tileset property table and the table is what walkability
    comes off, so two maps with the same grid under different properties must
    not share a digest -- and, since 2026-09-04, the narrowing that goes with
    that: the digest must move for a laid tile's class and for the fixed/random
    sort that prices a step, and must not move for a trap tile's formation id
    or for a tile id the map never lays. Both halves are checked by patching a
    copy of the cartridge, because a digest that noticed everything would pass
    the first three of those and refuse every reroll;
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
# The region is what pairs a loot lane with the route lane whose edges it
# subtracts, so a value that is not a region index is worth a complaint rather
# than a lane drawn twice down one corridor.
for why, reg in (("a negative region", -1), ("a region that is a string", "0"),
                 ("a region that is a boolean", True)):
    check("validate rejects %s" % why,
          len(LF.validate(doc_with({"digest": "a" * 16,
                                    "lanes": [dict(a_lane(), region=reg)]}))), 1)
check("and accepts a lane that states no region at all",
      LF.validate(doc_with({"digest": "a" * 16, "lanes": [a_lane()]})), [])

mismatched = dict(two, map_id=61)
check("validate rejects a map_id that disagrees with the map name",
      len(LF.validate(mismatched)), 1)
check("validate rejects a map name that is not a map",
      len(LF.validate(dict(two, map="nowhere"))) >= 1, True)
check("validate says all of what is wrong, not the first thing",
      len(LF.validate({"version": 99, "map": "nowhere", "map_id": 61,
                       "layouts": []})) >= 3, True)

# --------------------------------------------------------------- the retrace
# The one key on a layout entry that is a judgement rather than a measurement,
# so the only way it can be wrong is silently: nothing here rejects an unknown
# key, and a misspelt value read for its truthiness would draw a floor marked
# "no" retraced.
check("validate accepts a layout that says nothing about retrace",
      LF.validate(doc_with({"digest": "a" * 16, "lanes": [a_lane()]})), [])
for v in (True, False):
    check("validate accepts retrace %r" % v,
          LF.validate(doc_with({"digest": "a" * 16, "retrace": v,
                                "lanes": [a_lane()]})), [])
for why, v in (("a string", "yes"), ("a string that is falsey", "no"),
               ("an int", 1), ("null", None)):
    check("validate rejects retrace as %s" % why,
          len(LF.validate(doc_with({"digest": "a" * 16, "retrace": v,
                                    "lanes": [a_lane()]}))), 1)

# wants_retrace is the one place the tri-state meets the key. Both halves of
# every row matter: an override that quietly deferred to the entry would make
# "render the set the other way" impossible, which is what the comparison pass
# is built on.
for mode, entry, want in (
        ("auto", {}, False),
        ("auto", {"retrace": False}, False),
        ("auto", {"retrace": True}, True),
        ("on", {}, True),
        ("on", {"retrace": False}, True),
        ("off", {"retrace": True}, False),
        ("off", {}, False)):
    check("wants_retrace(%s, %r) is %r" % (mode, entry.get("retrace"), want),
          LF.wants_retrace(entry, mode), want)
check("wants_retrace on no entry at all is off", LF.wants_retrace(None), False)
try:
    LF.wants_retrace({}, "sometimes")
    check("a retrace mode not one of the three is refused", False, True)
except ValueError:
    check("a retrace mode not one of the three is refused", True, True)
check("and 'auto' is the default, so a caller saying nothing reads the file",
      LF.wants_retrace({"retrace": True}), True)

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
    # write() rebuilds the document from `layouts` whole, which is what lets a
    # key it has never heard of survive an editor round-trip. If that ever
    # stops being true, a saved judgement is lost on the next save.
    marked = doc_with(dict(two["layouts"][0], retrace=True), two["layouts"][1])
    LF.write("marshB3", marked)
    check("a retrace mark survives a write and read",
          LF.read("marshB3")["layouts"][0].get("retrace"), True)
    # A file written under an older VERSION -- restored from history, carried
    # on a branch -- is openable by the editor, since `read` does not validate
    # and only `load` does. Writing back the number it was loaded with would
    # save it as unopenable again, with no way for the author to migrate it.
    LF.write("marshB3", dict(two, version=1))
    check("a document loaded at an older version is written at today's",
          LF.read("marshB3")["version"], LF.VERSION)
    check("and so a round trip through the editor makes it valid again",
          LF.validate(LF.read("marshB3")), [])
    check("read of a map with no file is None", LF.read("nosuchmap"), None)
finally:
    shutil.rmtree(LF.LANES, ignore_errors=True)
    LF.LANES = keep

# ------------------------------------------------------------ the cache key
# regen_maps hashes the lane files separately from INPUT_FILES. Without a key
# that moves, editing a lane and re-running prints "nothing to do" over art
# drawn from the old stops -- the art would be wrong and the tool would say it
# was current, which is the one failure mode a cache has.
import regen_maps  # noqa: E402

keep = LF.LANES
LF.LANES = tempfile.mkdtemp(prefix="lanes-")
try:
    empty = regen_maps.lane_files_sha()
    LF.write("marshB3", two)
    one_file = regen_maps.lane_files_sha()
    check("a lane file appearing moves the cache key", empty != one_file, True)
    check("and reading it twice unchanged does not",
          regen_maps.lane_files_sha(), one_file)
    edited = doc_with({"digest": "a" * 16, "lanes": [a_lane("loot")]})
    LF.write("marshB3", edited)
    check("and editing one moves it again",
          regen_maps.lane_files_sha() != one_file, True)
    # Marking a floor for retrace needs no cache key of its own, because it is
    # a change to a lane file's contents. If it ever stopped moving this hash,
    # ticking the box would redraw nothing and the tool would say it was
    # current -- the one failure mode a cache has.
    marked = doc_with(dict(edited["layouts"][0], retrace=True))
    LF.write("marshB3", marked)
    check("and marking one for retrace moves it too",
          regen_maps.lane_files_sha() != one_file, True)
finally:
    shutil.rmtree(LF.LANES, ignore_errors=True)
    LF.LANES = keep

# The slot held a bool before the setting became per-layout, so a slot written
# then is read rather than compared. False becomes "auto" and not "off" on
# purpose: no committed lane file carried the key while such a slot could be
# written, so the two drew identical art and reading it as "off" would force a
# redraw that changes nothing.
for was, want in (({"retrace": True}, "on"), ({"retrace": False}, "auto"),
                  ({}, "auto"), ({"retrace": "off"}, "off"),
                  ({"retrace": "auto"}, "auto"), ({"retrace": "on"}, "on"),
                  ({"retrace": "sometimes"}, "auto")):
    check("a cache slot of %r reads as %r" % (was.get("retrace"), want),
          regen_maps.retrace_slot(was), want)

# The guard that decides whether to redraw and the line that says why used to
# be two copies of one chain, and they had drifted: --retrace was compared
# outside the --lanes authored gate in both, so `--lanes none --retrace off`
# after a default run redrew every file and blamed --retrace, on art that
# carries no lane at all. One function now, read here the way both read it.
import types  # noqa: E402


def flags(**kw):
    return types.SimpleNamespace(**{"npcs": "none", "lanes": "none",
                                    "retrace": "auto", **kw})


current = {"npcs": "none", "lanes": "authored", "retrace": "auto",
           "lane_files": regen_maps.lane_files_sha()}
check("art drawn with the same flags is not stale",
      regen_maps.flag_change(current, flags(lanes="authored")), None)
check("--npcs is compared whatever the lanes are",
      bool(regen_maps.flag_change(dict(current, lanes="none"),
                                  flags(npcs="gates"))), True)
check("and so is --lanes itself",
      bool(regen_maps.flag_change(current, flags(lanes="solved"))), True)
check("--retrace is compared where authored lanes are drawn",
      regen_maps.flag_change(current, flags(lanes="authored",
                                            retrace="off")),
      "--retrace changed from auto to off since the last run")
# The finding itself: nothing a run with no authored lanes puts on the image
# depends on --retrace, so switching it must not throw the art away.
check("and not where none are, because it changes nothing there",
      regen_maps.flag_change(dict(current, lanes="none"),
                             flags(lanes="none", retrace="off")), None)
check("a lane file moving is stale where authored lanes are drawn",
      regen_maps.flag_change(dict(current, lane_files="not the hash"),
                             flags(lanes="authored")),
      "a lane file changed since the last run")
check("and is not where none are",
      regen_maps.flag_change(dict(current, lanes="none",
                                  lane_files="not the hash"),
                             flags(lanes="none")), None)

# And the same question asked of the installed override, which is the reading
# that failed silently: `verify` compared INPUT_FILES and the written files and
# nothing else, so re-keying all 57 lane files on 2026-09-04 left verify.sh
# stage 4 green over art drawn from the old stops. A fabricated override
# directory rather than the machine's, so this stays a test of the checkout.
def _override(**slot):
    d = tempfile.mkdtemp(prefix="override-")
    regen_maps.write_cache(d, {
        "version": regen_maps.CACHE_VERSION, "outputs": {},
        "modes": {"std": dict({"inputs": regen_maps.inputs_fingerprint(),
                               "npcs": "none", "lanes": "authored",
                               "retrace": "auto",
                               "lane_files": regen_maps.lane_files_sha()},
                              **slot)}})
    return d


_ok = _override()
_moved = _override(lane_files="not the hash")
_none = _override(lanes="none", lane_files="not the hash")
try:
    check("verify passes an override drawn from the lane files as they stand",
          regen_maps.verify(_ok), 0)
    check("and reports one drawn from lane files that have since changed",
          regen_maps.verify(_moved), 1)
    check("and does not, where that mode drew no authored lane",
          regen_maps.verify(_none), 0)
finally:
    for d in (_ok, _moved, _none):
        shutil.rmtree(d, ignore_errors=True)

check("the file that decides which layout a digest picks is an input",
      "tools/lane_file.py" in regen_maps.INPUT_FILES, True)

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


# What the digest must and must not notice, on a patched copy of this
# cartridge. A trap tile's formation id is rolled per seed and a tileset entry
# no cell places decides nothing, so both have to be invisible here or the
# authored art is thrown away on every reroll; the class of a laid tile and the
# fixed/random sort both move where a lane can go, so both have to be seen.
def _patched(map_id, tile, byte, value):
    """This cartridge with one property byte of one tile id overwritten."""
    hurt = bytearray(rom)
    tileset = rom[rm.TILESET_LUT + map_id]
    hurt[rm.TILESET_PROP + tileset * rm.PROP_STRIDE + tile * 2 + byte] = value
    return bytes(hurt)


_inverted = rm.battle_byte_inverted(rom)
_fixed_tiles = rm.fixed_formations(rom)
_trap = _trap_map = None
for _m in sorted(rm.MAP_FILES):
    _set = rom[rm.TILESET_LUT + _m]
    _laid = {t & 0x7F for t in rm.map_tiles(rom, _m)}
    _here = sorted(t for (s, t) in _fixed_tiles if s == _set and t in _laid)
    if _here:
        _trap, _trap_map = _here[0], _m
        break
check("some laid tile on this cartridge is a fixed-formation trap",
      _trap is not None, True)

if _trap is not None:
    _base = (rm.TILESET_PROP
             + rom[rm.TILESET_LUT + _trap_map] * rm.PROP_STRIDE)
    _b1 = rom[_base + _trap * 2 + 1]
    # A different formation, still a fixed one: any non-zero value under FFR's
    # inverted test, any value with the top bit clear under a vanilla one.
    _other = ((_b1 ^ 0x01) or 0x02) if _inverted else ((_b1 ^ 0x01) & 0x7F)
    check("a trap tile's formation id does not move the digest",
          LF.digest(_patched(_trap_map, _trap, 1, _other), _trap_map),
          digests[_trap_map])
    # And the sort that formation id decides does move it: 0 reads as a random
    # encounter on an FFR cartridge, 0x80 on a vanilla one, and a random
    # encounter prices a step differently from a fixed trap.
    _rand = 0x00 if _inverted else 0x80
    check("but whether that tile is a fixed trap or an encounter does",
          LF.digest(_patched(_trap_map, _trap, 1, _rand), _trap_map)
          != digests[_trap_map], True)

_m = min(rm.MAP_FILES)
_laid = {t & 0x7F for t in rm.map_tiles(rom, _m)}
_base = rm.TILESET_PROP + rom[rm.TILESET_LUT + _m] * rm.PROP_STRIDE
_one = min(_laid)
check("a laid tile's property byte 0 moves the digest",
      LF.digest(_patched(_m, _one, 0, rom[_base + _one * 2] ^ eg.TP_NOMOVE),
                _m) != digests[_m], True)
_unlaid = sorted(set(range(ec.TILES_PER_SET)) - _laid)
check("this map lays fewer than every tile in its tileset", bool(_unlaid), True)
if _unlaid:
    _u = _unlaid[0]
    check("a tile id the map never lays does not move the digest",
          LF.digest(_patched(_m, _u, 0, rom[_base + _u * 2] ^ 0xFF), _m),
          digests[_m])

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

    # An unreadable image is a complaint too, and the digest is inside the
    # guard that makes it one. Since the digest started reading the
    # fixed/random sort it can raise where it never could before, and a
    # traceback out of load() takes down a caller walking every map -- the one
    # shape this function returns a `why` rather than throwing to avoid.
    blind = bytearray(rom)
    blind[rm.INES_HEADER + rm.fixed_bank(rom) * rm.BANK_SIZE
          + rm.SMMOVE_BATTLE_BPL] = 0xEA
    try:
        lanes, why = LF.load(bytes(blind), graph, one, chests)
        got = (lanes, "SMMove_Battle" in (why or ""))
    except ValueError as e:
        got = ("raised", str(e))
    check("an image whose battle byte cannot be read is refused, not raised",
          got, (None, True))
finally:
    shutil.rmtree(LF.LANES, ignore_errors=True)
    LF.LANES = keep

for f_ in fails:
    print("     " + f_)
print("ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
