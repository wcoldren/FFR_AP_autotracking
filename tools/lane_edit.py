#!/usr/bin/env python3
"""Author a map's walking route by clicking it, and let the router walk between.

ROADMAP.md, "an editor rather than a better solver": a solver cannot know which
chests are worth taking on a given seed, so the route wants a person in the
loop. What the person supplies here is an order -- a short list of stops -- and
`lane.walk` fills in the walking. The cost model is untouched; the router became
the pathing primitive instead of the whole feature.

A page in a browser, served from a socket on loopback, because `tools/doormap.py`
already established that a self-contained page with inline CSS and JS is how
this repo draws something you look at. Unlike doormap this one has to write back,
so it is a server rather than a file -- a hand pass over sixty-one maps is not
sixty-one manual file moves. `http.server` is in the standard library, which is
the only dependency rule here.

Three decisions worth stating, because each has an attractive wrong answer.

**The image is rendered here, into memory, and never read from the override
tree.** The installed override may not exist, may have been drawn from a
different cartridge -- the thing `.regen_stamp` exists to notice -- and if it
was drawn with `--lanes` it already has a lane baked into it, so you would be
authoring on top of a drawing. Rendering through `regen_maps.crops` guarantees
the pixel grid you click on *is* the grid the art will be baked on; deriving a
second crop here would be two derivations free to drift.

**There is no pathfinder in the JavaScript.** Every edit posts its stops back
and redraws from the answer. Two implementations would be two answers, and the
one you see while authoring has to be the one that bakes. It is affordable
because `Floor` memoises its search per start tile and the Floors live as long
as the process: the first drag pays for a Dijkstra, the rest are free.

**Save re-resolves and re-walks from scratch, ignoring what the browser
computed, and refuses rather than writing.** The editor must not be able to
author a file `regen_maps` will then refuse -- a refusal at bake time is a
refusal in front of a map you have stopped looking at.

    tools/lane_edit.py ROM [--map NAME] [--port N] [--no-browser]
    tools/lane_edit.py ROM --check      # resolve every lane file, draw nothing

`--check` is the question "which of my authored lanes still apply to this
seed", answered without opening a window.
"""
import http.server
import json
import os
import socketserver
import sys
import threading
import urllib.parse
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import entrance_graph as eg  # noqa: E402
import extract_chests  # noqa: E402
import lane  # noqa: E402
import lane_file  # noqa: E402
import regen_maps  # noqa: E402
import render_maps  # noqa: E402

# Loopback, and not a flag. POST /save writes a file in this checkout, so a
# socket on 0.0.0.0 would be an unauthenticated write endpoint on whatever
# network this machine is on. There is no auth here and there should not be:
# the answer to "who else can reach this" is nobody.
HOST = "127.0.0.1"

# Every route the page is allowed to ask for. The suite reads this and the
# fetches out of TEMPLATE and compares the two -- a renamed route 404s in
# silence and the only symptom is a preview that stops updating.
ROUTES = ("/", "/map.png", "/map.json", "/preview.png",
          "/path", "/save", "/quit")


class Session:
    """One cartridge, held open for the life of the process.

    The Floors are the cache that matters: Floor.search memoises per start
    tile, so the second drag of a stop costs nothing, and rebuilding them per
    request would make the page feel like the solver it replaces.
    """

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            self.rom = f.read()
        self.graph = eg.Graph(eg.Rom.of(self.rom, path))
        self.chests = extract_chests.extract(self.rom)[0]
        self.crops = regen_maps.crops(self.rom, self.graph)
        self.marks = render_maps.trap_marks(self.rom)
        self.stamp = lane_file.stamp(self.rom, path)
        self.mode = regen_maps.mode_of(self.rom, None)
        self._png = {}
        self._floor = {}
        self._data = {}
        self.lock = threading.Lock()

    def map_id(self, name):
        for mid, n in render_maps.MAP_FILES.items():
            if n == name:
                return mid
        raise KeyError(name)

    def floor(self, name, prefer=()):
        key = (name, tuple(sorted(frozenset(e) for e in prefer)) or None)
        if key not in self._floor:
            self._floor[key] = lane.Floor(self.rom, self.graph,
                                          self.map_id(name), prefer=prefer)
        return self._floor[key]

    def png(self, name):
        """The map as it will be baked, minus the Map Key band.

        The band's height depends on how many lane rows the finished file
        wants, which is the thing being authored -- so the editing image
        reserves none and /preview.png renders the real one.
        """
        if name not in self._png:
            mid = self.map_id(name)
            w, h, rgb = render_maps.render(
                self.rom, mid, unroof=True, graph=self.graph,
                crop=self.crops[name], legend_rows=0)
            self._png[name] = regen_maps.encode(w, h, rgb)
        return self._png[name]

    def preview(self, name, lanes):
        """The same render with the lanes drawn and the Map Key filled in."""
        mid = self.map_id(name)
        used = set(render_maps.map_trap_marks(
            self.rom, mid, render_maps.map_tiles(self.rom, mid),
            self.marks).values())
        rows = render_maps.legend_rows_for(
            len(used), len(render_maps.lane_key_entries(lanes)))
        w, h, rgb = render_maps.render(
            self.rom, mid, unroof=True, graph=self.graph, crop=self.crops[name],
            legend_rows=rows, marks=self.marks, lanes=lanes)
        return regen_maps.encode(w, h, rgb)

    def data(self, name):
        """Everything the page needs to draw one map's overlays and hit-test.

        All of it off lane.Floor / arrivals / exits / regions / chest_groups,
        so the editor reads the cartridge through exactly one interpreter --
        the rule doormap.py's docstring already states for the same reason.
        """
        if name in self._data:
            return self._data[name]
        mid = self.map_id(name)
        f = self.floor(name)
        crop = self.crops[name]
        groups = lane.chest_groups(self.rom, mid, self.chests)
        # A flat 4096-character mask rather than a list of tiles: the page
        # indexes it per hover, and a set membership test in JS over a few
        # thousand strings is the one thing that made panning feel slow.
        walk = "".join("1" if f.walkable((c, r)) else "0"
                       for r in range(64) for c in range(64))
        doc = lane_file.read(name)
        dig = lane_file.digest(self.rom, mid)
        out = {
            "name": name, "id": mid, "digest": dig,
            "box": list(crop.box), "shift": list(crop.shift),
            "size": list(crop.size), "tilePx": render_maps.TILE_PX,
            "walkable": walk,
            "teleports": sorted(list(t) for t in f.teleports),
            "blocked": sorted(list(t) for t in f.blocked),
            "trap": sorted(list(t) for t in f.trap),
            "encounter": sorted(list(t) for t in f.encounter),
            "chests": {str(i): [list(t) for t in ts]
                       for i, ts in sorted(groups.items())},
            "arrivals": [list(t) for t in lane.arrivals(f)],
            "exits": [list(t) for t in lane.exits(f)],
            "regions": [[list(t) for t in r] for r in lane.regions(f)],
            "links": [[list(a), list(b)] for a, b in lane.links(groups)],
            "entry": lane_file.pick(doc, dig),
            "hasFile": doc is not None,
        }
        self._data[name] = out
        return out

    def index(self):
        pal = render_maps.NES_PALETTE
        maps = []
        for mid, name in sorted(render_maps.MAP_FILES.items(),
                                key=lambda kv: kv[1]):
            doc = lane_file.read(name)
            dig = lane_file.digest(self.rom, mid)
            maps.append({
                "id": mid, "name": name,
                "chests": len(lane.chest_groups(self.rom, mid, self.chests)),
                "authored": lane_file.pick(doc, dig) is not None,
                "otherLayout": doc is not None
                               and lane_file.pick(doc, dig) is None,
            })
        return {"rom": os.path.basename(self.path), "seen": self.stamp,
                "mode": self.mode, "tilePx": render_maps.TILE_PX,
                "colours": {"route": list(pal[render_maps.LANE_ROUTE]),
                            "loot": list(pal[render_maps.LANE_LOOT]),
                            "forced": list(pal[render_maps.LANE_FORCED]),
                            "link": list(pal[render_maps.LANE_LINK]),
                            "start": list(pal[render_maps.LANE_START])},
                "maps": maps}


def lanes_from(session, name, spec):
    """spec -> (Lanes|None, complaint). Never raises for a bad lane."""
    mid = session.map_id(name)
    try:
        return lane.authored(session.rom, session.graph, mid,
                             {"lanes": spec}, session.chests), None
    except (ValueError, KeyError) as e:
        return None, str(e)


def walk_one(session, name, flavour, stops, prefer=()):
    """(path, got, gaps) for one lane's stops, as the page asks per edit."""
    mid = session.map_id(name)
    f = session.floor(name, prefer=prefer)
    groups = lane.chest_groups(session.rom, mid, session.chests)
    first = lane.anchors(f, stops[0], groups) if stops else []
    return lane.walk(f, stops, groups, start=first[0] if first else None)


def make_handler(session):
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            # The access log is noise; a save is not. The terminal this runs in
            # should be a record of what the session changed and nothing else.
            pass

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj).encode(), "application/json")

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(u.query)
            try:
                if u.path == "/":
                    page = TEMPLATE.replace(
                        "__DATA__", json.dumps(session.index()))
                    return self._send(200, page.encode(), "text/html")
                if u.path == "/map.png":
                    with session.lock:
                        return self._send(200, session.png(q["name"][0]),
                                          "image/png")
                if u.path == "/map.json":
                    with session.lock:
                        return self._json(session.data(q["name"][0]))
                if u.path == "/preview.png":
                    name = q["name"][0]
                    spec = json.loads(q["spec"][0])
                    with session.lock:
                        lanes, why = lanes_from(session, name, spec)
                        if why:
                            return self._json({"ok": False, "why": why}, 400)
                        return self._send(200, session.preview(name, lanes),
                                          "image/png")
            except (KeyError, IndexError, ValueError) as e:
                return self._json({"ok": False, "why": str(e)}, 400)
            self._json({"ok": False, "why": "no such route"}, 404)

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError as e:
                return self._json({"ok": False, "why": str(e)}, 400)
            try:
                if u.path == "/path":
                    with session.lock:
                        path, got, gaps = walk_one(
                            session, body["map"], body.get("flavour", "route"),
                            body.get("stops", []),
                            prefer=[tuple(map(tuple, e))
                                    for e in body.get("prefer", ())])
                    return self._json({"ok": not gaps, "path": path,
                                       "got": got, "gaps": gaps})
                if u.path == "/save":
                    return self._save(body)
                if u.path == "/quit":
                    self._json({"ok": True})
                    threading.Thread(
                        target=self.server.shutdown, daemon=True).start()
                    return
            except (KeyError, ValueError) as e:
                return self._json({"ok": False, "why": str(e)}, 400)
            self._json({"ok": False, "why": "no such route"}, 404)

        def _save(self, body):
            name = body["map"]
            spec = body.get("lanes", [])
            with session.lock:
                mid = session.map_id(name)
                dig = lane_file.digest(session.rom, mid)
                # Re-resolve and re-walk from scratch. Whatever the browser
                # drew is a picture; this is the claim, and it is the same call
                # regen_maps will make.
                lanes, why = lanes_from(session, name, spec)
                if why:
                    return self._json({"ok": False, "why": why}, 400)
                doc = lane_file.read(name) or {
                    "version": lane_file.VERSION, "map": name, "map_id": mid,
                    "layouts": []}
                entry = lane_file.pick(doc, dig)
                if entry is None:
                    entry = {"digest": dig, "seen": [], "lanes": []}
                    doc.setdefault("layouts", []).append(entry)
                entry["lanes"] = spec
                if body.get("note"):
                    entry["note"] = body["note"]
                if session.stamp not in entry.setdefault("seen", []):
                    entry["seen"].append(session.stamp)
                bad = lane_file.validate(doc)
                if bad:
                    return self._json({"ok": False, "why": "; ".join(bad)}, 400)
                where = lane_file.write(name, doc)
                session._data.pop(name, None)
            # Relative to the pack where that reads as a path in it, absolute
            # where it does not -- a save into a temp tree printed as
            # ../../../../var/... says less than the path itself.
            pack = os.path.dirname(HERE)
            shown = os.path.relpath(where, pack)
            print("saved %s -- %d lane(s), digest %s"
                  % (where if shown.startswith(os.pardir) else shown,
                     len(spec), dig))
            return self._json({"ok": True, "path": where})

    return Handler


class Server(socketserver.ThreadingTCPServer):
    # A /path request can take a second on a cold map, and the browser asks for
    # the image at the same time; single-threaded, the page would stall on its
    # own first paint.
    daemon_threads = True
    allow_reuse_address = True


def check(session):
    """Resolve every committed lane file against this cartridge. Draws nothing."""
    drawn = other = none = 0
    bad = []
    for mid, name in sorted(render_maps.MAP_FILES.items(), key=lambda kv: kv[1]):
        lanes, why = lane_file.load(session.rom, session.graph, mid,
                                    session.chests, name=name)
        if why == "no file":
            none += 1
        elif why is None:
            drawn += 1
            print("  %-24s %d lane(s)" % (name, len(lanes.runs)))
        elif why.startswith("no layout"):
            other += 1
            print("  %-24s %s" % (name, why))
        else:
            bad.append((name, why))
            print("  %-24s REFUSED %s" % (name, why))
    print("\n%d map(s) draw an authored lane, %d have a file for another "
          "layout, %d have none" % (drawn, other, none))
    return 1 if bad else 0


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("rom")
    ap.add_argument("--map", help="open on this map (a render_maps.MAP_FILES name)")
    ap.add_argument("--port", type=int, default=0,
                    help="0 lets the OS pick, which is the default")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="resolve every lane file against this cartridge and "
                         "exit; opens no socket and draws nothing")
    args = ap.parse_args()

    session = Session(args.rom)
    if args.check:
        return check(session)

    httpd = Server((HOST, args.port), make_handler(session))
    url = "http://%s:%d/" % (HOST, httpd.server_address[1])
    if args.map:
        url += "#" + args.map
    print("lane editor on %s -- %s, %s" % (url, session.stamp, session.mode))
    print("ctrl-c to stop")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        httpd.server_close()
    return 0



# The page. One string, inline CSS and JS, the shape doormap.py established --
# with its palette, so the two tools look like they came from the same place.
# __DATA__ is the index; everything per-map is fetched, because a cartridge's
# worth of walkability masks inlined here would be a megabyte of page.
TEMPLATE = r'''<meta charset="utf-8">
<title>Lane editor</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Chivo:wght@600;800&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
:root{
  --ground:#e9ecf2; --surface:#ffffff; --sunk:#f2f4f8;
  --ink:#141a26; --muted:#5a6479; --line:#ccd3e0; --line-soft:#e0e5ee;
  --accent:#2438c4; --accent-soft:#dfe3fa;
  --gold:#8a5f08; --gold-soft:#f6eddb;
  --jade:#0f6b53; --jade-soft:#dcefe8;
  --rust:#a3231b; --rust-soft:#fadedc;
  --shadow:0 1px 2px rgba(20,26,38,.06),0 8px 24px -16px rgba(20,26,38,.28);
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#0d121c; --surface:#151c2a; --sunk:#111726;
    --ink:#dde3ef; --muted:#8a94aa; --line:#263145; --line-soft:#1d2536;
    --accent:#8fa2ff; --accent-soft:#1e2748;
    --gold:#d9a441; --gold-soft:#2a2413;
    --jade:#4cbf94; --jade-soft:#10281f;
    --rust:#ff8a80; --rust-soft:#2c1512;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -16px rgba(0,0,0,.8);
  }
}
*{box-sizing:border-box}
body{background:var(--ground); color:var(--ink); margin:0;
  font-family:Chivo,'Helvetica Neue',Arial,sans-serif; font-size:14px}
.mono{font-family:'JetBrains Mono',ui-monospace,Menlo,monospace;
  font-variant-numeric:tabular-nums}
#app{display:grid; grid-template-columns:290px 1fr; height:100vh}
#rail{background:var(--surface); border-right:1px solid var(--line);
  overflow:auto; display:flex; flex-direction:column}
#stage{overflow:auto; padding:24px; background:var(--sunk)}
.pad{padding:14px 16px; border-bottom:1px solid var(--line-soft)}
.eyebrow{font-size:10px; font-weight:600; letter-spacing:.16em;
  text-transform:uppercase; color:var(--muted); margin:0 0 8px}
h1{font-size:16px; font-weight:800; margin:0 0 4px}
.sub{font-size:11px; color:var(--muted)}
#maps{flex:1; overflow:auto; min-height:120px}
.m{display:flex; justify-content:space-between; gap:8px; padding:5px 16px;
  cursor:pointer; border-left:3px solid transparent; font-size:12px}
.m:hover{background:var(--sunk)}
.m.on{background:var(--accent-soft); border-left-color:var(--accent);
  font-weight:600}
.m .n{color:var(--muted); font-size:11px}
.m.has .n{color:var(--jade)}
.m.stale .n{color:var(--gold)}
button{font:inherit; font-size:12px; padding:5px 10px; cursor:pointer;
  background:var(--surface); color:var(--ink);
  border:1px solid var(--line); border-radius:2px}
button:hover:not(:disabled){border-color:var(--accent); color:var(--accent)}
button:disabled{opacity:.45; cursor:not-allowed}
button.pri{background:var(--accent); border-color:var(--accent); color:#fff}
button.pri:hover:not(:disabled){filter:brightness(1.1); color:#fff}
.row{display:flex; gap:6px; flex-wrap:wrap; align-items:center}
.seg{display:flex; border:1px solid var(--line); border-radius:2px;
  overflow:hidden}
.seg button{border:0; border-radius:0; border-right:1px solid var(--line)}
.seg button:last-child{border-right:0}
.seg button.on{background:var(--accent); color:#fff}
#stops{list-style:none; margin:8px 0 0; padding:0; font-size:12px}
#stops li{display:flex; align-items:center; gap:6px; padding:4px 6px;
  border:1px solid var(--line-soft); border-radius:2px; margin-bottom:4px;
  background:var(--surface)}
#stops li.sel{border-color:var(--accent); background:var(--accent-soft)}
#stops li.gap{border-color:var(--rust); background:var(--rust-soft)}
#stops .k{flex:1}
#stops .i{width:18px; color:var(--muted); text-align:right}
#stops button{padding:1px 6px; font-size:11px}
#msg{font-size:12px; padding:8px 16px; min-height:34px; color:var(--muted)}
#msg.bad{color:var(--rust); font-weight:600}
#msg.good{color:var(--jade)}
#wrap{position:relative; display:inline-block; transform-origin:0 0}
#img{display:block; image-rendering:pixelated}
#ov{position:absolute; left:0; top:0}
label.tog{display:flex; gap:6px; align-items:center; font-size:11px;
  color:var(--muted); cursor:pointer}
</style>
<div id="app">
  <div id="rail">
    <div class="pad">
      <p class="eyebrow">Lane editor</p>
      <h1 id="rom">&nbsp;</h1>
      <div class="sub mono" id="seen">&nbsp;</div>
    </div>
    <div id="maps"></div>
    <div class="pad">
      <p class="eyebrow">Lane</p>
      <div class="row">
        <div class="seg" id="flav">
          <button data-f="route" class="on">Route</button>
          <button data-f="loot">Loot</button>
        </div>
        <select id="region"></select>
      </div>
      <ul id="stops"></ul>
      <div class="row" style="margin-top:8px">
        <button id="del">Delete</button>
        <button id="up">Up</button>
        <button id="down">Down</button>
        <button id="undo">Undo</button>
        <button id="redo">Redo</button>
      </div>
    </div>
    <div class="pad">
      <div class="row">
        <label class="tog"><input type="checkbox" id="tWalk"> walkable</label>
        <label class="tog"><input type="checkbox" id="tTrap" checked> traps</label>
        <label class="tog"><input type="checkbox" id="tDoor" checked> doors</label>
        <label class="tog"><input type="checkbox" id="tChest" checked> chests</label>
      </div>
      <div class="row" style="margin-top:8px">
        <span class="sub">zoom</span>
        <div class="seg" id="zoom">
          <button data-z="1" class="on">1&times;</button>
          <button data-z="2">2&times;</button>
          <button data-z="3">3&times;</button>
        </div>
      </div>
    </div>
    <div id="msg"></div>
    <div class="pad row">
      <button class="pri" id="save">Save</button>
      <button id="prev">Preview as baked</button>
      <button id="revert">Revert</button>
    </div>
  </div>
  <div id="stage">
    <div id="wrap"><img id="img" alt=""><canvas id="ov"></canvas></div>
  </div>
</div>
<script>
const INDEX = __DATA__;
const T = INDEX.tilePx;
const el = id => document.getElementById(id);
const rgb = c => 'rgb(' + c[0] + ',' + c[1] + ',' + c[2] + ')';

let D = null;          // the current map's data
let name = null;       // its MAP_FILES name
let lanes = [];        // [{flavour, region, stops}] -- the document being edited
let cur = 0;           // index into lanes
let sel = -1;          // selected stop
let drawn = {};        // lane index -> {path, gaps}
let undo = [], redo = [], dirty = false, zoom = 1;

/* The one piece of Crop.place duplicated outside Python. The suite compares
   this arithmetic against Crop.place on every cell of a spread of crops,
   because a map that slides on both axes is not hypothetical. */
const px = (c, r) => {
  const cc = ((c + D.shift[0]) % 64 + 64) % 64, rr = ((r + D.shift[1]) % 64 + 64) % 64;
  if (cc < D.box[0] || cc > D.box[1] || rr < D.box[2] || rr > D.box[3]) return null;
  return [(cc - D.box[0]) * T, (rr - D.box[2]) * T];
};
const tileAt = (x, y) => {
  const c = Math.floor(x / T) + D.box[0], r = Math.floor(y / T) + D.box[2];
  return [((c - D.shift[0]) % 64 + 64) % 64, ((r - D.shift[1]) % 64 + 64) % 64];
};
const walkable = t => D.walkable[t[1] * 64 + t[0]] === '1';
const same = (a, b) => a && b && a[0] === b[0] && a[1] === b[1];
const has = (list, t) => list.some(x => same(x, t));

function say(text, kind) { const m = el('msg'); m.textContent = text || ''; m.className = kind || ''; }
function snapshot() { undo.push(JSON.stringify(lanes)); if (undo.length > 200) undo.shift(); redo = []; dirty = true; }

/* Which region a tile belongs to, so an arrival stop can carry its anchor.
   Without it a two-region floor serves both halves from one door. */
function regionOf(t) {
  for (let i = 0; i < D.regions.length; i++) if (has(D.regions[i], t)) return i;
  return 0;
}
function anchorFor(ri) {
  const r = D.regions[ri] || D.regions[0] || [];
  return r.length ? r[0] : null;
}

/* A click is typed from what is under it. Inferring the kind here is what
   lets the file be portable without the author thinking about the format. */
function classify(t, forceTile) {
  if (forceTile) return { kind: 'tile', at: t };
  for (const [idx, tiles] of Object.entries(D.chests))
    if (has(tiles, t)) return { kind: 'chest', index: +idx, at: t };
  if (has(D.arrivals, t)) {
    const a = anchorFor(lanes[cur] ? lanes[cur].region : 0);
    return { kind: 'arrival', at: t, in: a || t };
  }
  if (has(D.exits, t)) return { kind: 'exit', at: t };
  return { kind: 'tile', at: t };
}
const label = s => s.kind === 'chest' ? 'chest ' + s.index
  : s.kind + ' ' + (s.at ? s.at[0] + ',' + s.at[1] : '?');

async function load(n) {
  if (dirty && !confirm('Discard unsaved changes to ' + name + '?')) return;
  name = n; location.hash = n;
  D = await (await fetch('/map.json?name=' + encodeURIComponent(n))).json();
  el('img').src = '/map.png?name=' + encodeURIComponent(n);
  const c = el('ov');
  c.width = D.size[0] * T; c.height = D.size[1] * T;
  el('img').width = c.width; el('img').height = c.height;
  lanes = D.entry ? JSON.parse(JSON.stringify(D.entry.lanes)) : [];
  if (!lanes.length) lanes = [{ flavour: 'route', region: 0, stops: [] }];
  cur = 0; sel = -1; undo = []; redo = []; dirty = false; drawn = {};
  for (const m of document.querySelectorAll('.m'))
    m.classList.toggle('on', m.dataset.n === n);
  const rs = el('region');
  rs.innerHTML = D.regions.map((r, i) =>
    '<option value="' + i + '">region ' + (i + 1) + ' of ' + D.regions.length + '</option>').join('');
  say(D.hasFile ? (D.entry ? 'authored for this layout' :
    'a file exists, for another layout') : 'no lane file yet');
  syncUI(); await refresh();
}

function syncUI() {
  const L = lanes[cur] || { flavour: 'route', region: 0, stops: [] };
  for (const b of document.querySelectorAll('#flav button'))
    b.classList.toggle('on', b.dataset.f === L.flavour);
  el('region').value = String(L.region || 0);
  const gaps = (drawn[cur] || {}).gaps || [];
  const bad = new Set(gaps.flat());
  el('stops').innerHTML = L.stops.map((s, i) =>
    '<li class="' + (i === sel ? 'sel ' : '') + (bad.has(i) ? 'gap' : '') +
    '" data-i="' + i + '"><span class="i mono">' + (i + 1) +
    '</span><span class="k">' + label(s) + '</span></li>').join('');
  el('undo').disabled = !undo.length; el('redo').disabled = !redo.length;
  el('del').disabled = sel < 0;
  el('up').disabled = sel <= 0; el('down').disabled = sel < 0 || sel >= L.stops.length - 1;
  el('save').disabled = !!gaps.length;
}

/* Every edit asks the server. There is no pathfinder here on purpose: two
   implementations would be two answers and the one drawn while authoring has
   to be the one that bakes. */
let pending = null;
function refresh() {
  clearTimeout(pending);
  return new Promise(done => { pending = setTimeout(async () => {
    drawn = {};
    for (let i = 0; i < lanes.length; i++) {
      const L = lanes[i];
      if (L.stops.length < 2) { drawn[i] = { path: [], gaps: [] }; continue; }
      let prefer = [];
      if (L.flavour === 'loot')
        for (let j = 0; j < lanes.length; j++)
          if (lanes[j].flavour === 'route' && lanes[j].region === L.region
              && drawn[j] && drawn[j].path.length > 1) {
            const p = drawn[j].path;
            for (let k = 1; k < p.length; k++) prefer.push([p[k - 1], p[k]]);
            break;
          }
      const r = await (await fetch('/path', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ map: name, flavour: L.flavour,
                               stops: L.stops, prefer }) })).json();
      drawn[i] = r;
    }
    const g = Object.values(drawn).some(d => (d.gaps || []).length);
    if (g) say('a leg has no walk -- the dashed red one. Save is refused until it does.', 'bad');
    else if (dirty) say('unsaved', '');
    paint(); syncUI(); done();
  }, 80); });
}

function paint() {
  const c = el('ov'), g = c.getContext('2d');
  g.clearRect(0, 0, c.width, c.height);
  const dot = (t, col, r) => { const p = px(t[0], t[1]); if (!p) return;
    g.fillStyle = col; g.beginPath();
    g.arc(p[0] + T / 2, p[1] + T / 2, r || 3, 0, 7); g.fill(); };
  const ring = (t, col) => { const p = px(t[0], t[1]); if (!p) return;
    g.strokeStyle = col; g.lineWidth = 2;
    g.strokeRect(p[0] + 2, p[1] + 2, T - 4, T - 4); };

  if (el('tWalk').checked) {
    g.fillStyle = 'rgba(36,56,196,.16)';
    for (let r = 0; r < 64; r++) for (let cc = 0; cc < 64; cc++)
      if (walkable([cc, r])) { const p = px(cc, r); if (p) g.fillRect(p[0], p[1], T, T); }
  }
  if (el('tTrap').checked) {
    for (const t of D.trap) ring(t, rgb(INDEX.colours.forced));
    g.fillStyle = 'rgba(120,130,150,.5)';
    for (const t of D.encounter) { const p = px(t[0], t[1]);
      if (p) g.fillRect(p[0] + T / 2 - 1, p[1] + T / 2 - 1, 2, 2); }
  }
  if (el('tDoor').checked) {
    for (const t of D.arrivals) ring(t, '#1f9d55');
    for (const t of D.exits) ring(t, '#2438c4');
    for (const t of D.blocked) ring(t, '#c2410c');
  }
  if (el('tChest').checked) {
    g.font = '600 9px JetBrains Mono, monospace'; g.textAlign = 'center';
    for (const [idx, tiles] of Object.entries(D.chests)) for (const t of tiles) {
      const p = px(t[0], t[1]); if (!p) continue;
      g.fillStyle = 'rgba(255,215,64,.85)';
      g.fillRect(p[0] + 3, p[1] + 3, T - 6, T - 6);
      g.fillStyle = '#141a26'; g.fillText(idx, p[0] + T / 2, p[1] + T / 2 + 3);
    }
    g.strokeStyle = rgb(INDEX.colours.link); g.lineWidth = 1;
    for (const [a, b] of D.links) { const pa = px(a[0], a[1]), pb = px(b[0], b[1]);
      if (!pa || !pb) continue; g.beginPath();
      g.moveTo(pa[0] + T / 2, pa[1] + T / 2); g.lineTo(pb[0] + T / 2, pa[1] + T / 2);
      g.lineTo(pb[0] + T / 2, pb[1] + T / 2); g.stroke(); }
  }

  for (let i = 0; i < lanes.length; i++) {
    const d = drawn[i]; if (!d || !d.path || d.path.length < 2) continue;
    g.strokeStyle = rgb(INDEX.colours[lanes[i].flavour]);
    g.lineWidth = i === cur ? 5 : 3;
    g.globalAlpha = i === cur ? 1 : .45;
    g.lineJoin = g.lineCap = 'round';
    g.beginPath(); let up = false;
    for (const t of d.path) { const p = px(t[0], t[1]);
      if (!p) { up = false; continue; }
      const x = p[0] + T / 2, y = p[1] + T / 2;
      if (up) g.lineTo(x, y); else g.moveTo(x, y);
      up = true; }
    g.stroke(); g.globalAlpha = 1;
  }
  /* A leg with no walk is the one line drawn that the game will not let you
     take, so it is drawn as obviously wrong rather than as a route. */
  const L = lanes[cur];
  for (const [i, j] of ((drawn[cur] || {}).gaps || [])) {
    const a = L.stops[i] && L.stops[i].at, b = L.stops[j] && L.stops[j].at;
    if (!a || !b) continue;
    const pa = px(a[0], a[1]), pb = px(b[0], b[1]); if (!pa || !pb) continue;
    g.save(); g.setLineDash([6, 4]); g.strokeStyle = rgb(INDEX.colours.forced);
    g.lineWidth = 3; g.beginPath();
    g.moveTo(pa[0] + T / 2, pa[1] + T / 2); g.lineTo(pb[0] + T / 2, pb[1] + T / 2);
    g.stroke(); g.restore();
  }
  L.stops.forEach((s, i) => {
    if (!s.at) return;
    dot(s.at, i === sel ? '#fff' : rgb(INDEX.colours.start), i === sel ? 6 : 5);
    ring(s.at, i === sel ? rgb(INDEX.colours.start) : '#141a26');
    const p = px(s.at[0], s.at[1]); if (!p) return;
    g.fillStyle = '#141a26'; g.font = '600 9px JetBrains Mono, monospace';
    g.textAlign = 'center'; g.fillText(String(i + 1), p[0] + T / 2, p[1] + T / 2 + 3);
  });
}

/* ---- interaction ---- */
let drag = -1;
el('ov').addEventListener('mousedown', e => {
  const r = e.target.getBoundingClientRect();
  const t = tileAt((e.clientX - r.left) / zoom, (e.clientY - r.top) / zoom);
  const L = lanes[cur];
  const hit = L.stops.findIndex(s => same(s.at, t));
  if (hit >= 0) { sel = hit; drag = hit; syncUI(); paint(); return; }
  snapshot();
  const stop = classify(t, e.shiftKey);
  if (sel >= 0 && e.altKey) { L.stops.splice(sel + 1, 0, stop); sel = sel + 1; }
  else { L.stops.push(stop); sel = L.stops.length - 1; }
  refresh();
});
el('ov').addEventListener('mousemove', e => {
  if (drag < 0) return;
  const r = e.target.getBoundingClientRect();
  const t = tileAt((e.clientX - r.left) / zoom, (e.clientY - r.top) / zoom);
  const s = lanes[cur].stops[drag];
  if (same(s.at, t)) return;
  lanes[cur].stops[drag] = classify(t, e.shiftKey);
  dirty = true; paint();
});
window.addEventListener('mouseup', () => { if (drag >= 0) { drag = -1; refresh(); } });
el('ov').addEventListener('contextmenu', e => {
  e.preventDefault();
  const r = e.target.getBoundingClientRect();
  const t = tileAt((e.clientX - r.left) / zoom, (e.clientY - r.top) / zoom);
  const i = lanes[cur].stops.findIndex(s => same(s.at, t));
  if (i >= 0) { snapshot(); lanes[cur].stops.splice(i, 1); sel = -1; refresh(); }
});
el('stops').addEventListener('click', e => {
  const li = e.target.closest('li'); if (!li) return;
  sel = +li.dataset.i; syncUI(); paint();
});
el('del').onclick = () => { snapshot(); lanes[cur].stops.splice(sel, 1); sel = -1; refresh(); };
el('up').onclick = () => { snapshot(); const s = lanes[cur].stops;
  [s[sel - 1], s[sel]] = [s[sel], s[sel - 1]]; sel--; refresh(); };
el('down').onclick = () => { snapshot(); const s = lanes[cur].stops;
  [s[sel + 1], s[sel]] = [s[sel], s[sel + 1]]; sel++; refresh(); };
el('undo').onclick = () => { if (!undo.length) return;
  redo.push(JSON.stringify(lanes)); lanes = JSON.parse(undo.pop()); sel = -1; refresh(); };
el('redo').onclick = () => { if (!redo.length) return;
  undo.push(JSON.stringify(lanes)); lanes = JSON.parse(redo.pop()); sel = -1; refresh(); };
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z')
    { e.preventDefault(); (e.shiftKey ? el('redo') : el('undo')).click(); }
  if ((e.key === 'Delete' || e.key === 'Backspace') && sel >= 0)
    { e.preventDefault(); el('del').click(); }
});
for (const b of document.querySelectorAll('#flav button')) b.onclick = () => {
  const f = b.dataset.f, reg = lanes[cur] ? lanes[cur].region : 0;
  let i = lanes.findIndex(L => L.flavour === f && L.region === reg);
  if (i < 0) { snapshot(); lanes.push({ flavour: f, region: reg, stops: [] }); i = lanes.length - 1; }
  cur = i; sel = -1; refresh();
};
el('region').onchange = () => {
  const reg = +el('region').value, f = lanes[cur] ? lanes[cur].flavour : 'route';
  let i = lanes.findIndex(L => L.flavour === f && L.region === reg);
  if (i < 0) { snapshot(); lanes.push({ flavour: f, region: reg, stops: [] }); i = lanes.length - 1; }
  cur = i; sel = -1; refresh();
};
for (const b of document.querySelectorAll('#zoom button')) b.onclick = () => {
  zoom = +b.dataset.z;
  for (const o of document.querySelectorAll('#zoom button')) o.classList.toggle('on', o === b);
  el('wrap').style.transform = 'scale(' + zoom + ')';
};
for (const id of ['tWalk', 'tTrap', 'tDoor', 'tChest']) el(id).onchange = paint;

el('save').onclick = async () => {
  const keep = lanes.filter(L => L.stops.length >= 2);
  if (!keep.length) { say('nothing to save: a lane needs at least two stops', 'bad'); return; }
  const r = await (await fetch('/save', { method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ map: name, lanes: keep }) })).json();
  if (r.ok) { dirty = false; say('saved ' + r.path, 'good');
    const m = document.querySelector('.m[data-n="' + name + '"]');
    if (m) { m.classList.add('has'); m.classList.remove('stale'); } }
  else say(r.why, 'bad');
};
el('prev').onclick = () => {
  const keep = lanes.filter(L => L.stops.length >= 2);
  el('img').src = '/preview.png?name=' + encodeURIComponent(name) +
    '&spec=' + encodeURIComponent(JSON.stringify(keep));
  say('showing the baked render, band and all. Pick the map again to go back.', '');
};
el('revert').onclick = () => { dirty = false; load(name); };
window.addEventListener('beforeunload', e => { if (dirty) { e.preventDefault(); e.returnValue = ''; } });

el('rom').textContent = INDEX.rom;
el('seen').textContent = INDEX.seen + '  ' + INDEX.mode;
el('maps').innerHTML = INDEX.maps.map(m =>
  '<div class="m ' + (m.authored ? 'has' : m.otherLayout ? 'stale' : '') +
  '" data-n="' + m.name + '"><span>' + m.name + '</span><span class="n">' +
  (m.authored ? 'drawn' : m.otherLayout ? 'other layout' : m.chests + ' chests') +
  '</span></div>').join('');
for (const m of document.querySelectorAll('.m')) m.onclick = () => load(m.dataset.n);
load((location.hash || '').slice(1) || INDEX.maps[0].name);
</script>
'''


if __name__ == "__main__":
    sys.exit(main())
