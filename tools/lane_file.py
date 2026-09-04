"""The file a hand-drawn lane lives in, and the digest that guards it.

A lane authored by a person is the one thing about the drawn maps that nothing
can re-derive. The art comes off the cartridge, the pins come off the tables,
and both are regenerated rather than stored -- but which chests are worth the
detour on a given seed is a judgement, so it is kept, in `tools/lanes/`, one
tracked JSON file per map. `docs/ARCHITECTURE.md` owns the rule that nothing
cartridge-derived is committed; this is the stated exception to it.

`lane.py` is the router and never opens a file. This module is the other half:
it owns the format, the digest, and the refusal. The split is why `lane.py`'s
docstring can still say it returns tiles and touches no disk.

**A lane file is a claim about a cartridge, made long before that cartridge is
in front of it**, so the format is built around outliving the seed it was drawn
on. Two mechanisms, and they guard different things:

* **Typed stops** survive what moves inside a fixed floor. A chest index moves
  between seeds; the tile grid does not. So a stop records what it is -- an
  arrival, a chest index, an exit, or a bare tile -- and `lane.anchors` resolves
  it per cartridge. See that function for what each kind falls back to.
* **The layout digest** refuses what the stops cannot survive. It covers the
  map's 4096 decompressed tiles *and* its tileset id and that tileset's 256-byte
  property block -- because the tiles are ids into that table, and the table is
  what `Floor.walkable`, `Floor.enter` and the trap classification actually
  read. Two identical tile grids under different tilesets walk differently, and
  a digest that missed that would happily draw a lane through rock.

One more thing lives on a layout entry, and it is a judgement rather than a
measurement: **`retrace`**, whether this floor's lanes should prefer their own
edges and so collapse a loop into one line. It sits beside `digest` and `lanes`
because it is a claim about how *one floor on one cartridge layout* is drawn --
per layout, because a No-Overworld seed's version of a floor may loop where the
standard one does not. `wants_retrace` is where it and the caller's override
meet; `docs/ISSUES.md`, "Is a loop worth collapsing?", is why the answer is not
one setting for the whole set.

Map objects are deliberately *outside* the digest. A gate NPC standing in a
doorway changes the walk, but the loader re-walks every leg against the
cartridge in hand, so the walking is always legal for that cartridge and a
moved NPC simply makes the lane detour. The digest guards the author's clicked
tiles, and those are geometry.

Sixteen hex characters over 4352 bytes. That is not a cryptographic claim and
is not meant as one -- it is a fingerprint against a corpus of a few dozen
layouts, where the question is "is this the floor I drew on" and not "can this
be forged".

`load` answers with three distinguishable outcomes rather than a bool, because
"there is no authored lane here" and "there is one and it is wrong" are not the
same event and only the second is a defect. `regen_maps` reports the first and
refuses on the second.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lane  # noqa: E402
import extract_chests  # noqa: E402
import render_maps  # noqa: E402

LANES = os.path.join(HERE, "lanes")
VERSION = 1
FLAVOURS = ("route", "loot")
# What a caller may say about retracing. "auto" is the only one that reads the
# file; the other two are a person overruling every entry at once, which is how
# both sides of the comparison get rendered once entries start disagreeing.
RETRACE = ("auto", "on", "off")


def digest(rom, map_id):
    """Sixteen hex characters over everything that decides where a lane can go.

    The decompressed tiles, the tileset id, and that tileset's property block.
    See the module docstring for why the last two are in and why objects are
    not.
    """
    tileset = rom[extract_chests.TILESET_LUT + map_id]
    base = extract_chests.TILESET_PROP + tileset * extract_chests.PROP_STRIDE
    h = hashlib.sha256()
    h.update(bytes(render_maps.map_tiles(rom, map_id)))
    h.update(bytes((tileset,)))
    h.update(bytes(rom[base:base + extract_chests.PROP_STRIDE]))
    return h.hexdigest()[:16]


def path_for(name):
    return os.path.join(LANES, name + ".json")


def read(name):
    """The parsed file for one map name, or None where there is none."""
    p = path_for(name)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def write(name, doc):
    """Write one map's lane file, whole, atomically.

    Through a temp file in the same directory and os.replace, so an editor
    killed mid-save leaves the previous file rather than half of a new one.
    Stable key order and a trailing newline, so a git diff says what changed
    rather than reshuffling the document around it.
    """
    if not os.path.isdir(LANES):
        os.makedirs(LANES)
    ordered = {"version": doc.get("version", VERSION),
               "map": doc["map"],
               "map_id": doc["map_id"],
               "layouts": doc.get("layouts", [])}
    p = path_for(name)
    tmp = p + ".tmp"
    with open(tmp, "w") as f:
        json.dump(ordered, f, indent=1)
        f.write("\n")
    os.replace(tmp, p)
    return p


def pick(doc, dig):
    """The layout entry matching this digest, or None.

    Pure, and the reason the format holds a *list* of layouts rather than one:
    a No-Overworld seed and a standard one disagree about most floors and agree
    about the rest, so a file that could hold only one layout would lose the
    maps a seed never touched every time another was authored.
    """
    if not doc:
        return None
    for entry in doc.get("layouts", ()):
        if entry.get("digest") == dig:
            return entry
    return None


def wants_retrace(entry, mode="auto"):
    """Whether to draw this layout retraced, under this override.

    The one place the tri-state is interpreted, so `lane.py` keeps taking a
    plain bool and stays ignorant of the key -- the format, its defaults and
    its refusals are this module's, which is the split the docstring above
    states.

    `auto` is the default and lets the entry decide, absent meaning off. `on`
    and `off` are a person overruling every entry at once; `on` is what the
    bare `--retrace` flag meant before the key existed, and what every
    measurement recorded against that flag was taken with.
    """
    if mode not in RETRACE:
        raise ValueError("retrace %r is not one of %s"
                         % (mode, ", ".join(RETRACE)))
    if mode != "auto":
        return mode == "on"
    return bool((entry or {}).get("retrace", False))


def validate(doc):
    """[complaint] -- everything wrong with this document's shape.

    All of them, not the first: a validator that stops at one complaint makes
    fixing a file a game of twenty questions, and one that returns a bare bool
    cannot say what to fix at all.
    """
    out = []
    if not isinstance(doc, dict):
        return ["not a JSON object"]
    if doc.get("version") != VERSION:
        out.append("version is %r, expected %r" % (doc.get("version"), VERSION))
    name = doc.get("map")
    if name not in render_maps.MAP_FILES.values():
        out.append("map %r is not one of render_maps.MAP_FILES" % (name,))
    else:
        want = [m for m, n in render_maps.MAP_FILES.items() if n == name][0]
        if doc.get("map_id") != want:
            out.append("map_id is %r but %s is map %d"
                       % (doc.get("map_id"), name, want))
    layouts = doc.get("layouts")
    if not isinstance(layouts, list):
        return out + ["layouts is not a list"]
    if not layouts:
        out.append("no layouts: the file claims nothing")
    for li, entry in enumerate(layouts):
        where = "layout %d" % li
        dig = entry.get("digest")
        if not isinstance(dig, str) or len(dig) != 16:
            out.append("%s: digest %r is not sixteen hex characters" % (where, dig))
        # Absent is the ordinary case and means "not retraced". Present has to
        # be a bool: nothing here rejects an unknown key, so a misspelt value
        # would otherwise be read for its truthiness and a floor marked
        # "retrace": "no" would draw retraced.
        if "retrace" in entry and not isinstance(entry["retrace"], bool):
            out.append("%s: retrace %r is not true or false"
                       % (where, entry["retrace"]))
        lanes_ = entry.get("lanes")
        if not isinstance(lanes_, list) or not lanes_:
            out.append("%s: no lanes" % where)
            continue
        for ai, spec in enumerate(lanes_):
            at = "%s lane %d" % (where, ai)
            if spec.get("flavour") not in FLAVOURS:
                out.append("%s: flavour %r is not one of %s"
                           % (at, spec.get("flavour"), ", ".join(FLAVOURS)))
            reg = spec.get("region")
            if reg is not None and (isinstance(reg, bool)
                                    or not isinstance(reg, int) or reg < 0):
                out.append("%s: region %r is not a region index; it pairs a "
                           "loot lane with the route lane it subtracts" % (at, reg))
            stops = spec.get("stops")
            if not isinstance(stops, list) or len(stops) < 2:
                out.append("%s: a lane needs at least two stops" % at)
                continue
            for si, stop in enumerate(stops):
                s = "%s stop %d" % (at, si)
                kind = stop.get("kind")
                if kind not in lane.STOP_KINDS:
                    out.append("%s: kind %r is not one of %s"
                               % (s, kind, ", ".join(lane.STOP_KINDS)))
                    continue
                if kind == "chest" and not isinstance(stop.get("index"), int):
                    out.append("%s: a chest stop needs an index" % s)
                if kind == "arrival" and not _pair(stop.get("in")):
                    out.append("%s: an arrival needs its region anchor in "
                               "'in'; without it a two-region floor serves "
                               "both halves from one door" % s)
                if kind == "tile" and not _pair(stop.get("at")):
                    out.append("%s: a tile stop needs its own 'at'" % s)
    return out


def _pair(v):
    return (isinstance(v, (list, tuple)) and len(v) == 2
            and all(isinstance(x, int) for x in v))


def stamp(rom, path):
    """The '<version>|<seed>|<flags>' record, for a layout's `seen` list.

    Not an identity and not used as one -- the digest is what decides whether a
    layout applies. This is a note to a person about which cartridges the lane
    was drawn against, which is the question a `seen` list answers.
    """
    import regen_maps
    return regen_maps.cartridge_id(rom, path)["ffr"]


def load(rom, graph, map_id, chests=None, name=None, retrace="auto"):
    """(Lanes|None, why) for one map, on this cartridge.

    `why` is None when a lane was drawn, and otherwise says which of the three
    outcomes this was. Only the third is a defect:

      "no file"            nothing was ever authored for this map
      "no layout ..."      something was, for a floor this cartridge does not
                           have -- an ordinary thing on a seed that re-laid it
      anything else        a layout that does match, whose stops do not resolve
                           or whose legs cannot be walked

    `retrace` is one of RETRACE and defaults to "auto", which is the layout
    entry's own say. See wants_retrace().
    """
    if name is None:
        name = render_maps.MAP_FILES[map_id]
    doc = read(name)
    if doc is None:
        return None, "no file"
    bad = validate(doc)
    if bad:
        return None, "%s: %s" % (name, "; ".join(bad))
    dig = digest(rom, map_id)
    entry = pick(doc, dig)
    if entry is None:
        return None, "no layout for this cartridge (digest %s)" % dig
    try:
        return lane.authored(rom, graph, map_id, entry, chests,
                             retrace=wants_retrace(entry, retrace)), None
    except ValueError as e:
        return None, str(e)
