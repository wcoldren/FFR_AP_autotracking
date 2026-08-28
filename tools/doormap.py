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
    coord, resolve_npc,
)

HERE = os.path.dirname(os.path.abspath(__file__))

# Vanilla door -> map, matched by the enum names in FF1Lib/Enums.cs
# (OverworldTeleportIndex against MapIndex). Only used to flag which doors did
# not move; the shuffle itself is always read from the ROM.
VANILLA_DOOR_MAP = {
    0: 16, 1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6, 8: 7, 9: 8, 10: 9, 11: 10,
    12: 11, 13: 12, 14: 13, 15: 14, 16: 15, 17: 16, 18: 17, 19: 18, 20: 19,
    21: 20, 22: 21, 23: 22, 24: 23, 25: 60, 26: 60, 27: 16, 28: 16, 29: 16,
}
UNUSED_DOORS = (30, 31)

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
        info, flags = ffr_flags.decode_rom(open(rom_path, "rb").read())
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
        })

    have = set()
    seen, q, floors, keys = set(), deque(), [], set()
    for _, m, a in g.starts():
        if (m, a) not in seen:
            seen.add((m, a))
            q.append((m, a))
    while q:
        m, a = q.popleft()
        for (x, y), (kind, pay, steps) in g.reachable_teleports(m, a, have).items():
            if kind != TP_TELE_NORM:
                continue
            dm = g.norm_map[pay]
            if dm >= MAP_COUNT:
                continue
            arrive = (coord(g.norm_x[pay]), coord(g.norm_y[pay]))
            key = (m, x, y, dm)
            if key not in keys:
                keys.add(key)
                floors.append({"from": MAP_NAMES[m], "fromId": m, "x": x, "y": y,
                               "to": MAP_NAMES[dm], "toId": dm,
                               "arrive": list(arrive), "steps": steps})
            if (dm, arrive) not in seen:
                seen.add((dm, arrive))
                q.append((dm, arrive))

    routes = []
    for name in npcs:
        spot = resolve_npc(g, name)

        # Landing on his floor is not the same as being able to walk to him:
        # two staircase chains into one map commonly arrive on two sides of a
        # locked door, and the shorter chain is not always the useful one. Fall
        # back to the plain route so the page can still say "the map is
        # reachable, he is not" rather than drawing nothing.
        def lands_by_npc(map_id, arrive, spot=spot):
            return g.can_reach_npc(map_id, arrive, spot, have) is not None

        found = (g.route(spot["map_id"], have, lands_by_npc)
                 or g.route(spot["map_id"], have))
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

    # A door counts towards "maps open empty-handed" only if it is a door you
    # can stand on: the same test Graph.starts() routes by. FFR's unused pair
    # carries an ordinary map byte and no overworld tile, and a byte past the
    # end of MAP_NAMES is not a map at all.
    return {"doors": doors, "routes": routes,
            "floors": sorted(floors, key=lambda f: (f["fromId"], f["y"], f["x"])),
            "reachable": sorted({f["toId"] for f in floors}
                                | {d["mapId"] for d in doors
                                   if d["ow"] and d["map"] is not None})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("-o", "--out", default="doormap.html")
    ap.add_argument("--npc", default="elfdoctor,smith",
                    help="comma-separated NPCs to draw routes to")
    args = ap.parse_args()

    g = Graph(Rom(args.rom))
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
    with open(args.out, "w") as f:
        f.write(page)
    print(f"wrote {args.out} ({len(page)} bytes): {len(data['doors'])} doors, "
          f"{len(data['floors'])} floor links, {len(data['routes'])} routes")


TEMPLATE = r'''<title>__SEEDNAME__ Door Map</title>
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

footer{border-top:1px solid var(--line); padding-top:24px; color:var(--muted); font-size:14px; display:flex; flex-direction:column; gap:12px}
code{font-family:'JetBrains Mono',monospace; font-size:.9em; background:var(--sunk); padding:1px 5px; border:1px solid var(--line-soft)}
@media (prefers-reduced-motion:reduce){*{animation:none!important; transition:none!important}}
</style>

<div class="wrap">

<header class="mast">
  <p class="eyebrow">Final Fantasy Randomizer &middot; entrance and floor shuffle</p>
  <h1>Where every door goes</h1>
  <p class="lede">All 32 overworld entrances in seed <span class="mono">__SEED__</span>, read straight out of the cartridge. The doors are still in their vanilla places on the map &mdash; only what is behind them moved.</p>
  <div class="chips" id="chips"></div>
  <div class="stats" id="stats"></div>
</header>

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
  <p>Every floor link reachable on foot from the doors above, with nothing in hand. Several maps &mdash; Dwarf Cave among them &mdash; have no overworld door at all and sit only behind one of these.</p>
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

/* masthead */
el('chips').innerHTML = [
  `<span class="chip mono">${META.rom}</span>`,
  META.version ? `<span class="chip">FFR ${META.version}</span>` : '',
].concat(META.chips.map(([label, on]) =>
  `<span class="chip${on ? ' on' : ''}">${label}</span>`)).join('');

const live = DATA.doors.filter(d => !d.unused).length;
const unchanged = DATA.doors.filter(d => d.unchanged && !d.unused).length;
el('stats').innerHTML = [
  [live, 'doors that lead somewhere'],
  [unchanged, unchanged === 1 ? 'door that did not move' : 'doors that did not move'],
  [DATA.floors.length, 'staircases you can walk to'],
  [DATA.reachable.length + ' of 61', 'maps open empty-handed'],
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
      <div class="step-map">${pretty(s.map)}</div>
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
  html: () => `<td class="num mono">${d.id}</td>
    <td>${pretty(d.name)}${d.unused ? '<span class="tag dim">unused</span>' : ''}</td>
    <td class="mono">${xy(d.ow)}${d.tiles > 1 ? ` <span class="arrive">+${d.tiles - 1}</span>` : ''}</td>
    <td><span class="dest">${d.map ? pretty(d.map) : '—'}</span>${d.unchanged && !d.unused ? '<span class="tag">unchanged</span>' : ''}</td>
    <td class="mono arrive">${d.unused ? '—' : xy(d.arrive)}</td>`
}));

const floorRows = DATA.floors.map(f => ({
  text: `${f.from} ${f.to}`.toLowerCase(),
  mark: routeLinks.has(`${f.fromId}:${f.x}:${f.y}`),
  from: f.from,
  html: prev => {
    const grouped = prev && prev.from === f.from;
    return `<td class="${grouped ? 'grp' : ''}">${grouped ? '↳' : pretty(f.from)}</td>
      <td class="mono">${f.x}, ${f.y}</td>
      <td><span class="dest">${pretty(f.to)}</span></td>
      <td class="mono arrive">${xy(f.arrive)}</td>
      <td class="mono arrive">${f.steps}</td>`;
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
      return `<tr class="${r.mark ? 'mark' : ''}">${cells}</tr>`;
    }).join('');
    el(id).innerHTML = keep.length
      ? body
      : `<tr><td class="none" colspan="5">Nothing matches &ldquo;${q}&rdquo;.</td></tr>`;
    return keep.length;
  };
  const d = paint('doors', doorRows), f = paint('floors', floorRows);
  el('count').textContent = q ? `${d} doors, ${f} staircases` : '';
};
el('q').addEventListener('input', draw);
draw();
</script>
'''


if __name__ == "__main__":
    main()
