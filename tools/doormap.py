#!/usr/bin/env python3
"""Render a seed's entrance and floor shuffle as a single self-contained page.

entrance_graph.py answers questions at a terminal; this draws the same data as
something you can keep open on a second monitor while the emulator runs. It is
a view over that tool, not a second reader -- every coordinate here comes from
Graph, so there is one place where the cartridge is interpreted.

The page needs no network and no build step: fonts come from Google Fonts and
everything else is inline.

Usage:
    tools/doormap.py ROM [-o doormap.html] [--npc elfdoctor,smith]
"""

import argparse
import json
import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from entrance_graph import (  # noqa: E402
    Graph, Rom, MAP_NAMES, MAP_COUNT, DOOR_NAMES, TP_TELE_NORM,
    VANILLA_DOOR_MAP, UNUSED_DOORS, coord, ffr_info, resolve_npc, route_to_npc,
)

HERE = os.path.dirname(os.path.abspath(__file__))

# What each fetch NPC takes off your hands, and what to call them on the page.
# Vanilla structure: NPCFetchItems randomizes the reward, not who wants what,
# and ShuffleObjectiveNPCs (off here) is what would move them.
NPC_LABEL = {
    "elfdoctor": ("Elf Doctor", "Herb"), "smith": ("Smith", "Adamant"),
    "nerrick": ("Nerrick", "TNT"), "matoya": ("Matoya", "Crystal Eye"),
    "unne": ("Unne", "Slab"), "fairy": ("Fairy", "Bottle"),
    "titan": ("Titan", "Ruby"), "bikke": ("Bikke", "Ship"),
    "astos": ("Astos", "Crown"), "sarda": ("Sarda", "Rod"),
    "bahamut": ("Bahamut", "Tail"), "elfprince": ("Elf Prince", "Herb"),
}

# The flags worth showing as chips, in reading order, with the label to print.
CHIPS = [
    ("Entrances", "Entrances"),
    ("EntrancesIncludesDeadEnds", "Dead ends included"),
    ("EntrancesMixedWithTowns", "Towns mixed in"),
    ("Floors", "Floors"),
    ("ReversedFloors", "Floors reversed"),
    ("NPCFetchItems", "Fetch rewards shuffled"),
    ("ShuffleObjectiveNPCs", "NPCs moved"),
]


def read_flags(rom_path):
    """(seed, version, [(label, on)]) from the cartridge's FFRInfo record.

    A cartridge whose flags cannot be read still gets a page -- the shuffle
    itself comes from the teleport tables, not from here -- but it gets one
    with no seed, no version and none of the chips, so the failure has to reach
    the terminal. An FFR build with no schema yet is the common case, and a
    silent empty flag row on an entrance-shuffled seed reads as "nothing is
    shuffled".
    """
    sys.path.insert(0, os.path.join(HERE, "ffr_flags"))
    try:
        import ffr_flags
        with open(rom_path, "rb") as f:
            info, flags = ffr_flags.decode_rom(f.read())
    except Exception as e:
        print(f"cannot read the flag record: {e}", file=sys.stderr)
        print("  the page will have no seed, no version and no flag chips",
              file=sys.stderr)
        return None, None, []
    chips = [(label, bool(flags.get(key))) for key, label in CHIPS if key in flags]
    if not flags.get("OwMapExchange"):
        chips.append(("Overworld unedited", False))
    return info.get("Seed"), info.get("Version"), chips


def build(g, npcs):
    # Which rows are doors you can walk into is Graph.starts()'s question, not a
    # rule to restate here: No-Overworld swaps the overworld for an ocean stub
    # with nine pads on it, so 23 of the 32 rows keep an ordinary map byte and
    # have no tile anywhere. Counting those as doors puts the player in front of
    # an entrance that is not on the cartridge.
    live = {i for i, _, _ in g.starts()}
    doors = []
    for i in range(32):
        m = g.entr_map[i]
        pos = g.doors.get(i, [])
        doors.append({
            "id": i, "name": DOOR_NAMES[i], "ow": pos[0] if pos else None,
            "tiles": len(pos), "mapId": int(m),
            "map": MAP_NAMES[m] if m < MAP_COUNT else None,
            "arrive": [coord(g.entr_x[i]), coord(g.entr_y[i])],
            "unchanged": VANILLA_DOOR_MAP.get(i) == m, "unused": i in UNUSED_DOORS,
            "live": i in live,
        })

    # Two interleaved passes, because the panel has to be able to say why a
    # floor is a dead end. The walk finds the staircases you can actually take;
    # the sweep adds the ones that are on a floor you stood on but behind a
    # locked door or a plate, which carry steps=None. Without those, a floor
    # whose far half is locked reads as having no way on at all. They alternate
    # rather than run once each: see the sweep's own comment below.
    have = set()
    seen, q, links = set(), deque(), {}
    for _, m, a in g.starts():
        if (m, a) not in seen:
            seen.add((m, a))
            q.append((m, a))
    swept = set()
    while True:
        while q:
            m, a = q.popleft()
            for (x, y), (kind, pay, steps) in g.reachable_teleports(m, a, have).items():
                if kind != TP_TELE_NORM:
                    continue
                dm = g.norm_map[pay]
                if dm >= MAP_COUNT:
                    continue
                arrive = (coord(g.norm_x[pay]), coord(g.norm_y[pay]))
                was = links.get((m, x, y))
                # One floor is commonly entered at several landing spots, and
                # the walk from each is a different length. Report the shortest,
                # so the number does not depend on the order the queue ran in.
                if was is None or was["steps"] is None or steps < was["steps"]:
                    links[(m, x, y)] = {"from": MAP_NAMES[m], "fromId": m, "x": x, "y": y,
                                        "to": MAP_NAMES[dm], "toId": dm,
                                        "arrive": list(arrive), "steps": steps}
                    swept.discard((m, x, y))
                if (dm, arrive) not in seen:
                    seen.add((dm, arrive))
                    q.append((dm, arrive))

        # The staircase directly under your feet is the one exception to "the
        # walk did not find it, so you cannot walk to it". reachable_teleports
        # drops the tile it starts on, because stepping onto a teleport is what
        # takes you off the floor and you are already standing there -- but you
        # can step off and back on. Two links are this every time: Coneria
        # Castle 2F's way down, and Ice Cave B1's hole to B3. Calling them gated
        # would be a plain lie about a staircase the player uses on the way out.
        #
        # A staircase the sweep finds under your feet is walkable, so it is a
        # way on and the floor it lands on has to be walked like any other --
        # otherwise that floor's own staircases never get listed and the
        # empty-handed headline undercounts. Hence the outer loop: sweep, feed
        # what it opened back to the walk, and repeat until nothing new opens.
        arrivals = {}
        for m, a in seen:
            arrivals.setdefault(m, set()).add(a)
        opened = False
        for m in arrivals:
            for x, y, kind, pay in g.teleports(m):
                if kind != TP_TELE_NORM:
                    continue
                # Leave the walk's own answer alone; a sweep entry can be
                # revisited, because a later pass may reach the tile it sits on
                # and turn a None into a 0.
                if (m, x, y) in links and (m, x, y) not in swept:
                    continue
                dm = g.norm_map[pay]
                if dm >= MAP_COUNT:
                    continue
                arrive = (coord(g.norm_x[pay]), coord(g.norm_y[pay]))
                steps = 0 if (x, y) in arrivals[m] else None
                swept.add((m, x, y))
                links[(m, x, y)] = {"from": MAP_NAMES[m], "fromId": m, "x": x, "y": y,
                                    "to": MAP_NAMES[dm], "toId": dm,
                                    "arrive": list(arrive), "steps": steps}
                if steps == 0 and (dm, arrive) not in seen:
                    seen.add((dm, arrive))
                    q.append((dm, arrive))
                    opened = True
        if not opened:
            break

    # A door counts towards "maps open empty-handed" only if it is a door the
    # router would actually take -- so ask the router, rather than restating its
    # rule here. Restating it got this wrong: Graph.starts() admits every door
    # when the overworld's tile properties named no entrance at all, and a
    # copied "has an overworld tile" test drops all 32 in that case, so the
    # page's headline undercounted against the floor links printed below it.
    # A gated staircase is in links too and proves nothing about where it goes,
    # so only the ones with a step count vouch for their destination.
    reachable = sorted({l["toId"] for l in links.values() if l["steps"] is not None}
                       | {m for _, m, _ in g.starts()})

    routes = []
    for name in npcs:
        # Every place he stands, not the first one found -- $13, the Fairy, is
        # in two maps on a stock cartridge. route_to_npc also handles the case
        # where the map is reachable and he is not: two staircase chains into
        # one floor commonly arrive on two sides of a locked door, and the
        # shorter chain is not always the useful one.
        spot, found, _ = route_to_npc(g, resolve_npc(g, name), have)
        label, item = NPC_LABEL.get(name, (name, None))
        if found is None:
            routes.append({"npc": name, "label": label, "item": item, "steps": None})
            continue
        door, path, m0, a0 = found
        steps = [{"map": MAP_NAMES[m0], "mapId": m0, "arrive": list(a0)}]
        for pm, pa, x, y, walked, node in path:
            dm, da = node
            steps[-1].update({"stairs": [x, y], "walk": walked})
            steps.append({"map": MAP_NAMES[dm], "mapId": dm, "arrive": list(da)})
        steps[-1]["npc"] = {"label": label, "at": [spot["tile_col"], spot["tile_row"]],
                            "walk": g.can_reach_npc(spot["map_id"], steps[-1]["arrive"],
                                                    spot, have)}
        pos = g.doors.get(door, [])
        doorname = DOOR_NAMES[door]
        routes.append({
            "npc": name, "label": label, "item": item, "door": doorname,
            "doorId": door, "ow": pos[0] if pos else None, "steps": steps,
            "direct": len(steps) == 1,
            "unchanged": VANILLA_DOOR_MAP.get(door) == g.entr_map[door],
        })

    return {"doors": doors, "routes": routes, "maps": MAP_NAMES,
            "mapCount": MAP_COUNT,
            "floors": sorted(links.values(),
                             key=lambda f: (f["fromId"], f["y"], f["x"])),
            "reachable": reachable}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("-o", "--out", default="doormap.html")
    ap.add_argument("--npc", default="elfdoctor,smith",
                    help="comma-separated NPCs to draw routes to")
    args = ap.parse_args()

    rom = Rom(args.rom)
    # The whole page is the extended teleport tables drawn out. On a cartridge
    # that has none, every door, link and route on it would be invented.
    if ffr_info(rom) is None:
        sys.exit(f"{args.rom}: no FFRInfo record -- this is not a Final Fantasy "
                 "Randomizer cartridge, and there is no shuffle on it to draw")
    g = Graph(rom)
    npcs = [n.strip() for n in args.npc.split(",") if n.strip()]
    data = build(g, npcs)
    seed, version, chips = read_flags(args.rom)
    stem = os.path.splitext(os.path.basename(args.rom))[0]
    name = stem.split("_")[-1] if "_" in stem else stem

    page = (TEMPLATE
            .replace("__SEEDNAME__", name)
            .replace("__SEED__", name)
            .replace("__DATA__", json.dumps(data, separators=(",", ":")))
            .replace("__META__", json.dumps(
                {"rom": stem, "seed": seed, "version": version, "chips": chips},
                separators=(",", ":"))))
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(page)
    gated = sum(1 for f in data["floors"] if f["steps"] is None)
    print(f"wrote {args.out} ({len(page)} bytes): {len(data['doors'])} doors, "
          f"{len(data['floors'])} floor links ({gated} of them gated), "
          f"{len(data['routes'])} routes")


TEMPLATE = r'''<meta charset="utf-8">
<title>__SEEDNAME__ Door Map</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Chivo:wght@600;800&family=Lora:ital,wght@0,400;0,500;1,400&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
:root{
  --ground:#e9ecf2; --surface:#ffffff; --sunk:#f2f4f8;
  --ink:#141a26; --muted:#5a6479; --line:#ccd3e0; --line-soft:#e0e5ee;
  --accent:#2438c4; --accent-soft:#dfe3fa;
  --gold:#8a5f08; --gold-soft:#f6eddb;
  --jade:#0f6b53; --jade-soft:#dcefe8;
  --shadow:0 1px 2px rgba(20,26,38,.06),0 8px 24px -16px rgba(20,26,38,.28);
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#0d121c; --surface:#151c2a; --sunk:#111726;
    --ink:#dde3ef; --muted:#8a94aa; --line:#263145; --line-soft:#1d2536;
    --accent:#8fa2ff; --accent-soft:#1e2748;
    --gold:#d9a441; --gold-soft:#2a2413;
    --jade:#4cbf94; --jade-soft:#10281f;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -16px rgba(0,0,0,.8);
  }
}
:root[data-theme="dark"]{
  --ground:#0d121c; --surface:#151c2a; --sunk:#111726;
  --ink:#dde3ef; --muted:#8a94aa; --line:#263145; --line-soft:#1d2536;
  --accent:#8fa2ff; --accent-soft:#1e2748;
  --gold:#d9a441; --gold-soft:#2a2413;
  --jade:#4cbf94; --jade-soft:#10281f;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -16px rgba(0,0,0,.8);
}
*{box-sizing:border-box}
body{
  background:var(--ground); color:var(--ink);
  font-family:Lora,Georgia,'Times New Roman',serif;
  font-size:16px; line-height:1.6;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1040px; margin:0 auto; padding:40px 24px 96px; display:flex; flex-direction:column; gap:48px}
h1,h2,h3,.eyebrow,th,.chip,.stat-n,button,input{font-family:Chivo,'Helvetica Neue',Arial,sans-serif}
.mono{font-family:'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,monospace; font-variant-numeric:tabular-nums}
.eyebrow{
  font-size:11px; font-weight:600; letter-spacing:.16em; text-transform:uppercase;
  color:var(--muted); margin:0 0 10px;
}
h1{font-size:clamp(30px,5vw,46px); font-weight:800; letter-spacing:-.02em; line-height:1.04; margin:0; text-wrap:balance}
h2{font-size:22px; font-weight:800; letter-spacing:-.01em; margin:0; text-wrap:balance}
h3{font-size:15px; font-weight:600; margin:0}
p{margin:0; max-width:65ch}
.lede{color:var(--muted); font-size:17px; margin-top:14px}

/* masthead */
.mast{border-bottom:2px solid var(--ink); padding-bottom:28px}
.chips{display:flex; flex-wrap:wrap; gap:8px; margin-top:22px}
.chip{
  font-size:11px; font-weight:600; letter-spacing:.06em; text-transform:uppercase;
  padding:5px 10px; border:1px solid var(--line); border-radius:2px;
  background:var(--surface); color:var(--muted);
}
.chip.on{border-color:var(--accent); color:var(--accent); background:var(--accent-soft)}
.stats{display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:1px; margin-top:26px; background:var(--line); border:1px solid var(--line)}
.stat{background:var(--surface); padding:14px 16px}
.stat-n{display:block; font-size:26px; font-weight:800; letter-spacing:-.02em; line-height:1.1}
.stat-l{font-size:12px; color:var(--muted); font-family:Chivo,sans-serif; letter-spacing:.04em}

/* section */
section{display:flex; flex-direction:column; gap:18px}
/* section's display beats the browser's own [hidden] rule, so say it here */
[hidden]{display:none!important}
.head{display:flex; align-items:baseline; justify-content:space-between; gap:16px; flex-wrap:wrap}

/* route chain */
.routes{display:grid; grid-template-columns:repeat(auto-fit,minmax(310px,1fr)); gap:20px}
.route{background:var(--surface); border:1px solid var(--line); border-top:3px solid var(--gold); box-shadow:var(--shadow); padding:20px}
.route-h{display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:4px}
.route-sub{font-size:13px; color:var(--muted); margin-bottom:18px}
.chain{list-style:none; margin:0; padding:0}
.step{position:relative; padding:0 0 20px 26px; border-left:2px solid var(--line-soft)}
.step:last-child{padding-bottom:0; border-left-color:transparent}
.step::before{
  content:""; position:absolute; left:-6px; top:5px; width:10px; height:10px;
  border-radius:50%; background:var(--surface); border:2px solid var(--gold);
}
.step.first::before{background:var(--gold)}
.step-map{font-family:Chivo,sans-serif; font-weight:600; font-size:15px}
.step-d{font-size:13px; color:var(--muted); margin-top:3px}
.step-d .mono{color:var(--ink)}
.arrive{color:var(--muted)}
.hit{color:var(--gold); font-weight:600; font-family:Chivo,sans-serif; font-size:13px; margin-top:6px}

/* tables */
.tools{display:flex; gap:10px; align-items:center; flex-wrap:wrap}
input[type=search]{
  font-size:13px; padding:8px 12px; width:min(280px,100%);
  border:1px solid var(--line); border-radius:2px; background:var(--surface); color:var(--ink);
}
input[type=search]:focus-visible{outline:2px solid var(--accent); outline-offset:1px; border-color:var(--accent)}
.count{font-size:12px; color:var(--muted); font-family:Chivo,sans-serif}
.scroll{overflow-x:auto; border:1px solid var(--line); background:var(--surface)}
table{border-collapse:collapse; width:100%; font-size:14px}
th{
  text-align:left; font-size:11px; font-weight:600; letter-spacing:.1em; text-transform:uppercase;
  color:var(--muted); padding:11px 14px; border-bottom:1px solid var(--line); white-space:nowrap;
  background:var(--sunk); position:sticky; top:0;
}
td{padding:10px 14px; border-bottom:1px solid var(--line-soft); vertical-align:top}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover td{background:var(--sunk)}
td.num{color:var(--muted); width:1%}
td.grp{color:var(--muted)}
.dest{font-family:Chivo,sans-serif; font-weight:600}
.tag{
  display:inline-block; margin-left:8px; font-family:Chivo,sans-serif;
  font-size:10px; font-weight:600; letter-spacing:.08em; text-transform:uppercase;
  padding:2px 6px; border-radius:2px; background:var(--jade-soft); color:var(--jade);
}
.tag.dim{background:var(--sunk); color:var(--muted)}
tr.mark td{background:var(--gold-soft)}
tr.mark:hover td{background:var(--gold-soft)}
.none{padding:20px 14px; color:var(--muted); font-size:14px}

/* click-through */
a.maplink{color:var(--accent); text-decoration:none; border-bottom:1px solid var(--accent-soft)}
a.maplink:hover{border-bottom-color:var(--accent)}
a:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
tr.focus td, tr.focus:hover td{background:var(--accent-soft)}
tr.focus td:first-child{box-shadow:inset 3px 0 0 var(--accent)}

/* focus panel */
.focus{background:var(--surface); border:1px solid var(--line); border-top:3px solid var(--accent); box-shadow:var(--shadow); padding:22px 24px}
.focus-h{display:flex; align-items:baseline; justify-content:space-between; gap:12px; flex-wrap:wrap}
.focus-sum{font-size:14px; color:var(--muted); margin-top:8px; max-width:70ch}
.legs{display:grid; grid-template-columns:repeat(auto-fit,minmax(270px,1fr)); gap:24px; margin-top:22px}
.leg h4{
  font-family:Chivo,sans-serif; font-size:11px; font-weight:600; letter-spacing:.14em;
  text-transform:uppercase; color:var(--muted); margin:0 0 12px;
  padding-bottom:7px; border-bottom:1px solid var(--line-soft);
}
.leg ul{list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:11px}
.leg li{font-size:14px; line-height:1.45}
.leg li.gated{opacity:.72}
.leg .sub{display:block; font-size:12.5px; color:var(--muted)}
.leg .empty{font-size:13.5px; color:var(--muted)}
.close{
  font-family:Chivo,sans-serif; font-size:12px; letter-spacing:.04em; color:var(--muted);
  text-decoration:none; border-bottom:1px solid var(--line); white-space:nowrap;
}
.close:hover{color:var(--ink); border-bottom-color:var(--ink)}

footer{border-top:1px solid var(--line); padding-top:24px; color:var(--muted); font-size:14px; display:flex; flex-direction:column; gap:12px}
code{font-family:'JetBrains Mono',monospace; font-size:.9em; background:var(--sunk); padding:1px 5px; border:1px solid var(--line-soft)}
@media (prefers-reduced-motion:reduce){*{animation:none!important; transition:none!important}}
</style>

<div class="wrap">

<header class="mast">
  <p class="eyebrow">Final Fantasy Randomizer &middot; entrance and floor shuffle</p>
  <h1>Where every door goes</h1>
  <p class="lede">The overworld entrances of seed <span class="mono">__SEED__</span>, read straight out of the cartridge. <span id="doorlede"></span> Click any floor name to open it, and keep clicking to walk the dungeon; Back retraces your steps.</p>
  <div class="chips" id="chips"></div>
  <div class="stats" id="stats"></div>
</header>

<section id="focus-sec" hidden>
  <article class="focus" id="focus"></article>
</section>

<section>
  <div class="head">
    <h2 id="routes-h">Routes</h2>
  </div>
  <div class="routes" id="routes"></div>
</section>

<section>
  <div class="head">
    <h2 id="doors-h">All 32 doors</h2>
    <div class="tools">
      <input type="search" id="q" placeholder="Filter doors and staircases" aria-label="Filter doors and staircases">
      <span class="count" id="count"></span>
    </div>
  </div>
  <p>Listed by the landmark each door still sits on. Coordinates are overworld tiles for the door, and map tiles for where you land inside.</p>
  <div class="scroll">
    <table>
      <thead><tr><th>#</th><th>Door, at its usual spot</th><th>Overworld</th><th>Now opens into</th><th>You land at</th></tr></thead>
      <tbody id="doors"></tbody>
    </table>
  </div>
</section>

<section>
  <div class="head">
    <h2>Staircases inside</h2>
  </div>
  <p>Every staircase on every floor you can reach from the doors above. The ones you cannot walk to with nothing in hand are marked <em>gated</em> &mdash; a locked door, a plate, or a stretch of floor no arrival lands on. Several maps &mdash; Dwarf Cave among them &mdash; have no overworld door at all and sit only behind one of these.</p>
  <div class="scroll">
    <table>
      <thead><tr><th>On this floor</th><th>Stairs at</th><th>Take you to</th><th>Landing at</th><th>Walk</th></tr></thead>
      <tbody id="floors"></tbody>
    </table>
  </div>
</section>

<footer>
  <p>Read from the cartridge with <code>tools/entrance_graph.py</code>: doors from <code>lut_EntrTele_Map</code>, floor links from the standard-map tile properties against FFR's extended teleport tables in bank <span class="mono">$0F</span>. Walking distances count tiles on the real map data, so locked doors and the Rod and Lute plates are respected.</p>
  <p id="caveat"></p>
</footer>

</div>

<script>
const DATA = __DATA__;
const META = __META__;

const pretty = s => s
  .replace(/([a-z])([A-Z0-9])/g, '$1 $2')
  .replace(/([A-Z])([A-Z][a-z])/g, '$1 $2')
  .replace(/\bOf\b/g, 'of');
const xy = a => a ? `${a[0]}, ${a[1]}` : '—';
const el = id => document.getElementById(id);
const hex = n => '$' + n.toString(16).toUpperCase().padStart(2, '0');

const mapName = id => pretty(DATA.maps[id]);
/* Every floor name on the page goes through here, so there is one definition
   of what a clickable floor is: a real entry in the cartridge's map table. A
   door whose row points past the end of it is not a place you can go. */
const mapLink = id => DATA.maps[id] === undefined
  ? '—' : `<a class="maplink" href="#map-${id}">${mapName(id)}</a>`;
const reachable = new Set(DATA.reachable);

/* masthead */
el('chips').innerHTML = [
  `<span class="chip mono">${META.rom}</span>`,
  META.version ? `<span class="chip">FFR ${META.version}</span>` : '',
].concat(META.chips.map(([label, on]) =>
  `<span class="chip${on ? ' on' : ''}">${label}</span>`)).join('');

/* "Leads somewhere" means the router would take it: a row with a map byte and
   no tile on the overworld is not an entrance, whatever the byte says. */
const live = DATA.doors.filter(d => d.live).length;
const spare = DATA.doors.filter(d => !d.unused).length;
const unchanged = DATA.doors.filter(d => d.unchanged && d.live).length;
el('doorlede').textContent = live === spare
  ? `All ${live} of them have a tile on the overworld; only what is behind them moved.`
  : `Only ${live} of its ${DATA.doors.length} rows have a tile on the overworld \u2014 the rest
     are not doors you can walk into on this cartridge, whatever map byte they carry.`;
el('stats').innerHTML = [
  [live, live === 1 ? 'door that leads somewhere' : 'doors that lead somewhere'],
  [unchanged, unchanged === 1 ? 'door that did not move' : 'doors that did not move'],
  [DATA.floors.filter(f => f.steps !== null).length, 'staircases you can walk to'],
  [DATA.reachable.length + ' of ' + DATA.mapCount, 'maps open empty-handed'],
].map(([n, l]) => `<div class="stat"><span class="stat-n mono">${n}</span><span class="stat-l">${l}</span></div>`).join('');

el('doors-h').textContent = `All ${DATA.doors.length} doors`;
el('routes-h').textContent = DATA.routes.length === 2
  ? 'The two you are carrying items for'
  : (DATA.routes.length === 1 ? 'The one you need' : 'Routes');

/* routes */
const subtitle = r => {
  if (!r.steps) return `Nothing in this seed reaches ${r.label}.`;
  const door = `Enter at the ${pretty(r.door)} door, overworld <span class="mono">${xy(r.ow)}</span>.`;
  if (r.unchanged) return `${door} This is one of the doors that still leads where it always did.`;
  if (r.direct) return `${door} It opens straight onto the floor you want.`;
  const last = r.steps[r.steps.length - 1];
  return `${door} No door opens into ${pretty(last.map)}; it sits ${r.steps.length - 1}
    ${r.steps.length === 2 ? 'floor' : 'floors'} deep behind this chain.`;
};

el('routes').innerHTML = DATA.routes.map(r => {
  const title = r.item ? `${r.item} &rarr; the ${r.label}` : `To the ${r.label}`;
  const steps = (r.steps || []).map((s, i) => {
    const bits = [`${i === 0 ? 'arrive' : 'land at'} <span class="mono">${xy(s.arrive)}</span>`];
    if (s.stairs) bits.push(`stairs <span class="mono">${xy(s.stairs)}</span>, ${s.walk} steps`);
    const npc = s.npc
      ? (s.npc.walk === null
          ? `<div class="hit">&rarr; ${s.npc.label} is at ${xy(s.npc.at)}, but no way into this map lands you where you can reach him</div>`
          : `<div class="hit">&rarr; ${s.npc.label} at ${xy(s.npc.at)}, ${s.npc.walk} steps further</div>`)
      : '';
    return `<li class="step${i === 0 ? ' first' : ''}">
      <div class="step-map">${mapLink(s.mapId)}</div>
      <div class="step-d">${bits.join(' &middot; ')}</div>${npc}</li>`;
  }).join('');
  return `<article class="route">
    <div class="route-h"><h3>${title}</h3></div>
    <div class="route-sub">${subtitle(r)}</div>
    <ol class="chain">${steps}</ol>
  </article>`;
}).join('');

/* caveat, only when the flags earn it */
const chip = name => (META.chips.find(c => c[0] === name) || [])[1];
const notes = [];
if (chip('Fetch rewards shuffled')) {
  notes.push(`<strong>One caveat.</strong> This seed shuffles what fetch NPCs hand back.
    Who wants which item did not change, and ${chip('NPCs moved') ? 'the NPCs did move' : 'the NPCs did not move'},
    but do not count on the vanilla reward.`);
}
el('caveat').innerHTML = notes.join(' ');
el('caveat').hidden = notes.length === 0;

/* tables */
const routeDoors = new Set(DATA.routes.filter(r => r.steps).map(r => r.doorId));
const routeLinks = new Set();
for (const r of DATA.routes) for (const s of (r.steps || [])) {
  if (s.stairs) routeLinks.add(`${s.mapId}:${s.stairs[0]}:${s.stairs[1]}`);
}

/* Rows render against the row visible above them, not against the row that
   happened to precede them in the data: filter the first row of a run of
   same-map staircases away and the next one would otherwise still show the
   continuation arrow, with no map name anywhere to say which floor it is on. */
const doorRows = DATA.doors.map(d => ({
  text: `${d.id} ${d.name} ${d.map || ''}`.toLowerCase(),
  mark: routeDoors.has(d.id),
  to: d.live ? d.mapId : undefined,
  html: () => `<td class="num mono">${d.id}</td>
    <td>${pretty(d.name)}${d.unused ? '<span class="tag dim">unused</span>'
      : (d.live ? '' : '<span class="tag dim">not on the map</span>')}</td>
    <td class="mono">${xy(d.ow)}${d.tiles > 1 ? ` <span class="arrive">+${d.tiles - 1}</span>` : ''}</td>
    <td><span class="dest">${d.unused ? '—' : mapLink(d.mapId)}</span>${d.unchanged && d.live ? '<span class="tag">unchanged</span>' : ''}</td>
    <td class="mono arrive">${d.unused ? '—' : xy(d.arrive)}</td>`
}));

const floorRows = DATA.floors.map(f => ({
  text: `${f.from} ${f.to}`.toLowerCase(),
  mark: routeLinks.has(`${f.fromId}:${f.x}:${f.y}`),
  from: f.from,
  at: f.fromId,
  to: f.toId,
  html: prev => {
    const grouped = prev && prev.from === f.from;
    return `<td class="${grouped ? 'grp' : ''}">${grouped ? '↳' : mapLink(f.fromId)}</td>
      <td class="mono">${f.x}, ${f.y}</td>
      <td><span class="dest">${mapLink(f.toId)}</span></td>
      <td class="mono arrive">${xy(f.arrive)}</td>
      <td class="mono arrive">${f.steps === null
        ? '<span class="tag dim">gated</span>' : f.steps}</td>`;
  }
}));

const draw = () => {
  const q = el('q').value.trim().toLowerCase();
  const paint = (id, rows) => {
    const keep = rows.filter(r => !q || r.text.includes(q));
    let prev = null;
    const body = keep.map(r => {
      const cells = r.html(prev);
      prev = r;
      const on = focused !== null && (r.at === focused || r.to === focused);
      return `<tr class="${r.mark ? 'mark ' : ''}${on ? 'focus' : ''}">${cells}</tr>`;
    }).join('');
    el(id).innerHTML = keep.length
      ? body
      : `<tr><td class="none" colspan="5">Nothing matches &ldquo;${q}&rdquo;.</td></tr>`;
    return keep.length;
  };
  const d = paint('doors', doorRows), f = paint('floors', floorRows);
  el('count').textContent = q ? `${d} doors, ${f} staircases` : '';
};

/* focus panel, addressed by #map-<id> so Back walks the route backwards */
let focused = null;

const list = (items, empty) => items.length
  ? `<ul>${items.map(i => `<li class="${i[0] ? 'gated' : ''}">${i[1]}</li>`).join('')}</ul>`
  : `<p class="empty">${empty}</p>`;

const summarise = (id, doorsIn, stairsIn, out) => {
  const walk = out.filter(f => f.steps !== null).length;
  const bits = [];
  if (reachable.has(id)) bits.push('You can stand here with nothing in hand.');
  else if (stairsIn.length) bits.push(`Every staircase into ${mapName(id)} is gated, so
    nothing on this page reaches it empty-handed.`);
  else bits.push('No door and no staircase on this page reaches this floor.');
  if (!out.length) bits.push('No staircase leads on from here.');
  else if (walk === out.length) bits.push(`${out.length} staircase${out.length === 1 ? '' : 's'}
    lead${out.length === 1 ? 's' : ''} on, all walkable from where you land.`);
  else if (out.length === 1) bits.push(`1 staircase sits on the floor, and it is not
    walkable from where you land.`);
  else bits.push(`${out.length} staircases sit on the floor; ${walk || 'none'} of them
    walkable from where you land.`);
  return bits.join(' ');
};

const renderFocus = () => {
  const hit = /^#map-(\d+)$/.exec(location.hash);
  focused = hit && DATA.maps[+hit[1]] !== undefined ? +hit[1] : null;
  el('focus-sec').hidden = focused === null;
  if (focused === null) { el('focus').innerHTML = ''; return; }
  const id = focused;
  const doorsIn = DATA.doors.filter(d => d.live && d.mapId === id);
  const stairsIn = DATA.floors.filter(f => f.toId === id);
  const out = DATA.floors.filter(f => f.fromId === id);

  const ways = doorsIn.map(d => [false, `Through the <strong>${pretty(d.name)}</strong> door
      ${d.unchanged ? '<span class="tag">unchanged</span>' : ''}
      <span class="sub">overworld <span class="mono">${xy(d.ow)}</span> &middot;
      you land at <span class="mono">${xy(d.arrive)}</span></span>`])
    .concat(stairsIn.map(f => [f.steps === null, `From ${mapLink(f.fromId)}
      <span class="sub">its stairs at <span class="mono">${f.x}, ${f.y}</span> &middot;
      you land at <span class="mono">${xy(f.arrive)}</span>${f.steps === null
        ? ' &middot; gated on that side' : ''}</span>`]));

  const onward = out.map(f => [f.steps === null, `To ${mapLink(f.toId)}
    <span class="sub">stairs at <span class="mono">${f.x}, ${f.y}</span> &middot;
    ${f.steps === null ? 'nothing you can walk to empty-handed'
      : f.steps === 0 ? 'the staircase you land on'
      : `<span class="mono">${f.steps}</span> steps from where you land`}
    &middot; landing at <span class="mono">${xy(f.arrive)}</span></span>`]);

  el('focus').innerHTML = `<p class="eyebrow">Focused floor</p>
    <div class="focus-h"><h2>${mapName(id)}</h2><a class="close" href="#">clear</a></div>
    <p class="focus-sum"><span class="mono">map ${id} &middot; ${hex(id)}</span> &mdash;
      ${summarise(id, doorsIn, stairsIn, out)}</p>
    <div class="legs">
      <div class="leg"><h4>Ways in</h4>${list(ways,
        'Nothing on this page opens into this floor.')}</div>
      <div class="leg"><h4>Onward</h4>${list(onward,
        'A dead end: no staircase leads out of it.')}</div>
    </div>`;
};

const show = (smooth) => {
  renderFocus();
  draw();
  if (focused === null) return;
  el('focus-sec').scrollIntoView({block: 'start', behavior:
    smooth && !matchMedia('(prefers-reduced-motion: reduce)').matches ? 'smooth' : 'auto'});
};

el('q').addEventListener('input', draw);
addEventListener('hashchange', () => show(true));
show(false);
</script>
'''


if __name__ == "__main__":
    main()
