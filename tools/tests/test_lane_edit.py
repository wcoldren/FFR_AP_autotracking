"""The editor draws what the bake will draw, and cannot author what it refuses.

An editor is a claim of a different kind from a lane: it says "what you are
looking at is what you will get". Every check here is a way that could be false
while the page still looked like it worked:

  * **the page asks for routes the server serves.** A renamed route 404s in
    silence -- no error is shown, the preview simply stops updating and the
    lane on screen quietly becomes the last good answer. So the fetches in the
    page are read out of the template and held against the handler's own list;
  * **the placeholder is filled.** __DATA__ appears once and nothing that looks
    like a placeholder survives substitution, because a page that ships the
    literal token renders an empty rail and no error;
  * **the socket is on loopback.** POST /save writes a file in this checkout,
    so this is a one-line assertion protecting a write endpoint;
  * **the page's tile-to-pixel arithmetic is Crop.place.** It is the only piece
    of render_maps duplicated in JavaScript, and it decides which tile a click
    lands on. Checked over every cell of a spread of crops including ones slid
    on both axes -- sky4F is slid on both on every cartridge measured, so a
    mod-64 sign error there is a real editor that quietly edits the wrong tile;
  * **the tool works when it is run, and not only when it is imported.** These
    suites import the module, which executes it to the end; running it as a
    script stops at main(), which blocks in serve_forever(). So anything
    defined below main() exists for the tests and does not exist for the tool
    -- TEMPLATE was, and every page it served was a NameError while this file
    was green. The last check spawns the real command;
  * **a save that would be refused at bake time is refused here, and writes
    nothing.** The editor must not be able to author a file regen_maps will
    then reject, because that refusal arrives in front of a map you have
    stopped looking at.

The first four need no cartridge. The live round trip sets FF1_ROM; without one
it skips rather than passing quietly.
"""
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lane_edit as LE  # noqa: E402
import render_maps as rm  # noqa: E402

fails = []


def check(label, got, want):
    if got != want:
        fails.append(f"{label}: got {got!r}, want {want!r}")
    print(f"{'ok  ' if got == want else 'FAIL'} {label}")


# ------------------------------------------------- the page and the handler
script = LE.TEMPLATE[LE.TEMPLATE.index("<script>"):]
asked = set()
for m in re.finditer(r"""['"](/[A-Za-z0-9_.]*)""", script):
    asked.add(m.group(1))
check("every route the page asks for is one the server serves",
      sorted(asked - set(LE.ROUTES)), [])
check("and the page asks for more than nothing", bool(asked), True)
check("__DATA__ appears exactly once", LE.TEMPLATE.count("__DATA__"), 1)
page = LE.TEMPLATE.replace("__DATA__", "{}")
check("and nothing placeholder-shaped survives substitution",
      re.findall(r"__[A-Z][A-Z0-9_]*__", page), [])
check("the editor listens on loopback only", LE.HOST, "127.0.0.1")

# Three ways the page could keep looking like it worked while being wrong, each
# guarded in the JavaScript and each read back out of it here.
check("undo clamps the current lane after restoring a shorter document",
      script.count("clamp(); sel = -1; refresh();"), 2)
check("a refresh overtaken by a newer one discards its own answers",
      "if (mine !== gen) return done();" in script, True)
check("and the baked preview is not forced into the editing frame",
      "removeAttribute('width')" in script, True)

# ------------------------------------------- the page's tile-pixel arithmetic
# A transcription of the page's px(), checked against Crop.place rather than
# against a second reading of it. The two lines below are also matched against
# the template, so editing the JavaScript without editing this fails here
# rather than in front of a map.
for frag in ("((c + D.shift[0]) % 64 + 64) % 64",
             "(cc - D.box[0]) * T"):
    check("the page still computes %r" % frag, frag in script, True)


def js_px(crop, c, r):
    cc = ((c + crop.shift[0]) % 64 + 64) % 64
    rr = ((r + crop.shift[1]) % 64 + 64) % 64
    if cc < crop.box[0] or cc > crop.box[1] or rr < crop.box[2] or rr > crop.box[3]:
        return None
    return ((cc - crop.box[0]) * rm.TILE_PX, (rr - crop.box[2]) * rm.TILE_PX)


spread = [rm.Crop(box=(0, 63, 0, 63)),
          rm.Crop(box=(3, 40, 7, 51)),
          rm.Crop(box=(0, 20, 0, 20), shift=(17, 0)),
          rm.Crop(box=(0, 20, 0, 20), shift=(0, 29)),
          rm.Crop(box=(2, 33, 5, 44), shift=(11, 47))]
off = []
for crop in spread:
    for r in range(64):
        for c in range(64):
            want = crop.place(c, r)
            want = None if want is None else (want[0] * rm.TILE_PX,
                                              want[1] * rm.TILE_PX)
            if js_px(crop, c, r) != want:
                off.append((crop.shift, c, r))
check("the page's tile-to-pixel agrees with Crop.place on every cell",
      off[:4], [])
check("and the spread includes a crop slid on both axes",
      any(s.shift[0] and s.shift[1] for s in spread), True)

# ------------------------------------------------------------ the round trip
path = os.environ.get("FF1_ROM")
if not path or not os.path.exists(path):
    print("SKIP  set FF1_ROM to a Final Fantasy cartridge for the round trip")
    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    sys.exit(1 if fails else 0)

import lane as L  # noqa: E402
import lane_file as LF  # noqa: E402
import regen_maps as RM  # noqa: E402


def png_hw(b):
    """(width, height) out of a PNG's IHDR."""
    return (int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big"))


session = LE.Session(path)

# The image you click on has to be cropped the way the art is. content_crop
# keeps a speck only where something stands on it, so a crop built without the
# NPC cells is a few cells tighter than the bake's on any map an NPC keeps
# alive -- which clips an edge NPC out of the image and puts a clicked stop on
# a different tile from the one that gets drawn.
baked = RM.crops(session.rom, session.graph, RM.npc_cells_of(session.rom))
blind = RM.crops(session.rom, session.graph)
check("the editor crops the way the bake crops",
      [n for n in sorted(baked) if session.crops[n] != baked[n]], [])
print("     (%d map(s) on this cartridge have an NPC that moves the box)"
      % len([n for n in blind if blind[n] != baked[n]]))

# Whether a *real* NPC moves a box is a fact about the cartridge in hand, and on
# some it moves none -- which would make the check above pass for a Session that
# dropped the argument entirely. So the claim tested here is the one that does
# not depend on the seed: the cells are what content_crop keeps the box open
# for, so a caller that omits them is one cartridge away from a different grid.
moved = None
for nm in sorted(blind):
    mid_ = session.map_id(nm)
    _, specks = rm.drop_specks(
        rm.content_cells(rm.map_tiles(session.rom, mid_)), ())
    if not specks:
        continue
    stood_on = sorted(specks[0])[0]
    probed = RM.crops(session.rom, session.graph,
                      {mid_: [("npc probe",) + stood_on]})
    if probed[nm] != blind[nm]:
        moved = (nm, stood_on)
        break
print("     (an NPC on %s at %s moves that map's box)" % (moved or ("none",) * 2))
check("and the NPC cells decide the box, so handing them over is not "
      "decoration", moved is not None, True)
mid = next((m for m in sorted(rm.MAP_FILES)
            if L.plan(session.rom, session.graph, m, session.chests)), None)
check("some map on this cartridge carries a lane to author", mid is not None, True)
name = rm.MAP_FILES[mid]
solved = L.plan(session.rom, session.graph, mid, session.chests)
floor = L.Floor(session.rom, session.graph, mid)
outs = set(L.exits(floor))
run = solved.runs[0]
stops = [{"kind": "arrival", "at": list(run.start), "in": list(run.start)}]
stops += [{"kind": "chest", "index": i} for i in run.got]
if run.path[-1] in outs:
    stops.append({"kind": "exit", "at": list(run.path[-1])})
wall = next(c for c in ((x, y) for y in range(64) for x in range(64))
            if not floor.walkable(c))

# The Floor cache carries the preference set in its key, and a loot lane's
# preference is the route lane's *current* drawing -- so it changes on every
# edit to the route lane. Uncapped, that holds one fully-searched floor per
# edit for the life of the process.
for k in range(LE.Session.FLOORS + 4):
    session.floor(name, prefer=[((0, 0), (0, k + 1))])
check("the Floor cache is capped rather than growing per edit",
      len(session._floor) <= LE.Session.FLOORS, True)
check("and one preference set spelled two ways is one entry",
      session.floor(name, prefer=[((1, 1), (1, 2)), ((2, 2), (2, 3))]) is
      session.floor(name, prefer=[((2, 3), (2, 2)), ((1, 2), (1, 1))]), True)

keep = LF.LANES
LF.LANES = tempfile.mkdtemp(prefix="lanes-")
httpd = LE.Server((LE.HOST, 0), LE.make_handler(session))
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = "http://%s:%d" % httpd.server_address


def get(p):
    try:
        with urllib.request.urlopen(base + p) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def post(p, obj):
    req = urllib.request.Request(base + p, json.dumps(obj).encode(),
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


try:
    code, body = get("/")
    check("the served page carries no unfilled placeholder",
          (code, b"__DATA__" in body), (200, False))
    code, body = get("/map.png?name=" + name)
    editing_png = body
    check("the map is served as a PNG the page can show",
          (code, body[:4]), (200, b"\x89PNG"))
    code, body = get("/map.json?name=" + name)
    data = json.loads(body)
    check("the walkability mask covers the whole grid",
          (code, len(data["walkable"])), (200, 64 * 64))
    check("and it is the Floor the router will walk",
          data["walkable"][run.start[1] * 64 + run.start[0]], "1")

    # The page's own edit loop, and the claim that makes the editor honest:
    # what it draws is what the router walks.
    code, body = post("/path", {"map": name, "flavour": run.label,
                                "stops": stops})
    check("a lane posted from the page walks the route the solver found",
          (body["ok"], len(body["path"])), (True, len(run.path)))

    code, body = post("/path", {"map": name, "flavour": "route",
                                "stops": [stops[0],
                                          {"kind": "tile", "at": list(wall)}]})
    check("a leg with no walk comes back as a gap, not a straight line",
          (body["ok"], bool(body["gaps"])), (False, True))

    check("no file yet", os.path.exists(LF.path_for(name)), False)
    code, body = post("/save", {"map": name, "lanes": [
        {"flavour": "route", "region": 0,
         "stops": [stops[0], {"kind": "tile", "at": list(wall)}]}]})
    check("saving a lane the bake would refuse is refused here",
          (code, body["ok"]), (400, False))
    check("and it writes nothing", os.path.exists(LF.path_for(name)), False)

    code, body = post("/save", {"map": name, "lanes": [
        {"flavour": run.label, "region": run.region, "stops": stops}]})
    check("a lane that walks is saved", (code, body["ok"]), (200, True))
    saved = LF.read(name)
    check("and the file it wrote validates", LF.validate(saved), [])
    check("and load reads the lane back off it",
          LF.load(session.rom, session.graph, mid, session.chests)[1], None)

    code, body = get("/preview.png?name=%s&spec=%s" % (
        name, urllib.parse.quote(json.dumps([
            {"flavour": run.label, "region": run.region, "stops": stops}]))))
    check("the baked preview renders", (code, body[:4]), (200, b"\x89PNG"))
    # It reserves the Map Key band the editing image renders none of, so it is
    # a taller frame -- which is why the page has to unpin the image's height
    # before showing it rather than squashing the band and the map into one.
    check("and it is taller than the frame the page pins for editing",
          png_hw(body)[1] > png_hw(editing_png)[1], True)
    code, body = get("/nosuchroute")
    check("an unknown route is a 404 and not a page", code, 404)

    # Run the actual command, not this module's import of it. A name defined
    # below main() is present for every check above and absent for every real
    # invocation, because main() never returns -- so an import-only suite can
    # be green over a tool that cannot serve a single page.
    import subprocess
    proc = subprocess.Popen(
        [sys.executable, os.path.join(os.path.dirname(HERE), "lane_edit.py"),
         path, "--port", "0", "--no-browser"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    served = None
    try:
        for _ in range(400):
            line = proc.stdout.readline()
            if not line:
                break
            m = re.search(r"http://127\.0\.0\.1:(\d+)/", line)
            if m:
                served = int(m.group(1))
                break
        if served:
            try:
                with urllib.request.urlopen(
                        "http://127.0.0.1:%d/" % served, timeout=30) as r:
                    got = (r.status, b"<script>" in r.read())
            except Exception as e:          # noqa: BLE001 - reported, not raised
                got = ("raised", str(e))
        else:
            got = ("no url", proc.stdout.read()[:200])
        check("the tool as a command serves its page", got, (200, True))
    finally:
        proc.terminate()
        proc.wait(timeout=30)
finally:
    httpd.shutdown()
    httpd.server_close()
    shutil.rmtree(LF.LANES, ignore_errors=True)
    LF.LANES = keep

for f in fails:
    print("     " + f)
print("ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
