#!/usr/bin/env python3
"""Split grouped chest sections into one location per chest, where the map art
has been calibrated for every chest in the group.

A group of chests behind one section only ever shows "some of these are still
out there" -- collecting three of six changes nothing on the map, because a
section stays available until it is entirely cleared. One location per chest is
the only shape that shows partial progress, which is the normal case in play.

Runs over whatever tools/marker_positions.json currently covers, so it can be
re-run as more maps are calibrated. Sections whose chests are not all
calibrated are left exactly as they are.

The parent node keeps its overworld pin and mirrors each new child as a ref
section -- without that it would have a marker and no sections of its own, and
PopTracker draws nothing for such a location.

Usage: tools/split_locations.py [--apply]
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
LOC = os.path.join(PACK, "locations", "overworld.json")
MAP = os.path.join(PACK, "scripts", "autotracking", "location_mapping.lua")


def lenient(path):
    return json.loads(re.sub(r",(\s*[}\]])", r"\1", open(path).read()))


def load_mapping(limit=512):
    """{AP id: (location path, hosted item)} out of location_mapping.lua.

    `limit` caps the ids read. The default keeps chests only, which is what
    splitting a grouped section is about, and is now what every caller wants:
    regen_maps.marker_tiles and noverworld_rules.placements both pass 512 and
    pick the NPCs up through `hosted_item` in the location tree instead.

    That join is the wider one. This table only names locations the multiworld
    has an id for, and eight of the fourteen NPCs the cartridge places carry no
    shuffled item and so have no id at all -- Bahamut among them. A caller
    reading NPCs out of here would miss them silently.
    """
    ids = {}
    for line in open(MAP):
        # the pack is not uniformly spaced: at least one row reads
        # {"@..." ,"earth"}, with the space before the comma
        m = re.match(r'\s*\[(\d+)\] = \{"([^"]+)"\s*(?:,\s*"([^"]+)")?\s*\}', line)
        if m and (limit is None or int(m.group(1)) < limit):
            ids[int(m.group(1))] = (m.group(2), m.group(3))
    return ids


def leaf_of(path):
    """The location name an "@Some Location/Section" path points at."""
    return path.lstrip("@").rsplit("/", 1)[0]


def node_label(parent, section):
    """Readable, unique node name: the parent plus the section, without saying
    the parent twice when the section name already leads with it."""
    if section.lower().startswith(parent.lower()):
        return section
    return f"{parent} {section}"


def plan():
    markers = json.load(open(os.path.join(HERE, "marker_positions.json")))
    positions = json.load(open(os.path.join(HERE, "chest_positions.json")))
    mapping = load_mapping()

    by_path = {}
    for ap, (path, hosted) in mapping.items():
        by_path.setdefault(path, []).append(ap)

    out = {}
    for path, aps in by_path.items():
        if len(aps) < 1:
            continue
        chests = [ap - 256 for ap in aps]
        if not all(str(c) in markers for c in chests):
            continue                      # not fully calibrated yet
        # A chest drawn on more than one tile is still one chest: FF1 keys a
        # chest by an id stored in the tile, so the same id placed twice means
        # one flag, one item, reachable from either spot. Ordeals' 2F chest is
        # four-pack #1 on 3F, which the map art says out loud. Both tiles get a
        # box; they share a location, so they light and clear together.
        # reading order: top to bottom, then left to right
        def key(ap):
            p = positions[str(ap - 256)][0]
            return (p["tile_row"], p["tile_col"])
        out[path] = sorted(aps, key=key)
    return out, mapping, markers


def find_node(text, name):
    """Character span of the node object whose "name" is exactly `name`."""
    needle = f'"name": "{name}",'
    i = text.index(needle)
    start = text.rfind("{", 0, i)
    depth = 0
    for j in range(start, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                return start, j + 1
    raise ValueError(name)


def dump(obj, indent):
    """json.dumps at a given indent, every line after the first shifted in."""
    body = json.dumps(obj, indent=4)
    return ("\n" + " " * indent).join(body.split("\n"))


def rebuild(node, secs, markers, positions, indent):
    """Node text with `secs` (name -> ap ids) split out into per-chest children."""
    I = " " * indent
    keep = [s for s in node.get("sections", []) if s["name"] not in secs]
    children = list(node.get("children", []))

    new_children = []
    for name, aps in secs.items():
        label = node_label(node["name"], name)
        for n, ap in enumerate(aps, 1):
            chest = ap - 256
            mks = markers[str(chest)]
            hosted = secs_hosted.get((name, ap))
            child_name = label if len(aps) == 1 else f"{label} {n}"
            sec = {"name": "Incentive" if hosted else "Chest", "item_count": 1}
            if hosted:
                sec["hosted_item"] = hosted
            new_children.append({
                "name": child_name,
                "sections": [sec],
                "map_locations": [{"map": m["map"], "x": m["x"], "y": m["y"],
                                   "size": 16, "border_thickness": 2} for m in mks],
                "_ref_name": child_name if len(aps) == 1 else f"{name} {n}",
                "_sec_name": sec["name"],
            })

    refs = [{"name": c.pop("_ref_name"), "ref": f'{c["name"]}/{c.pop("_sec_name")}'}
            for c in new_children]

    out = dict(node)
    out["sections"] = keep + refs
    out["children"] = children + new_children
    # keep a stable, readable key order
    order = ["name", "color", "access_rules", "visibility_rules", "sections",
             "map_locations", "children"]
    ordered = {k: out[k] for k in order if k in out}
    for k in out:
        if k not in ordered:
            ordered[k] = out[k]
    return I + dump(ordered, indent)


secs_hosted = {}


def main():
    apply = "--apply" in sys.argv
    todo, mapping, markers = plan()
    positions = json.load(open(os.path.join(HERE, "chest_positions.json")))
    for ap, (path, hosted) in mapping.items():
        if hosted:
            secs_hosted[(path[1:].rsplit("/", 1)[1], ap)] = hosted

    tree = lenient(LOC)
    # locations that already carry per-chest markers are done
    done = set()

    def scan(nodes):
        for n in nodes:
            secs = n.get("sections", [])
            if (len(secs) == 1 and secs[0].get("item_count") == 1
                    and n.get("map_locations")):
                done.add(n["name"])
            scan(n.get("children", []))
    scan(tree)

    split = {}
    for path, aps in todo.items():
        loc, sec = path[1:].rsplit("/", 1)
        if loc in done:
            continue
        split.setdefault(loc, {})[sec] = aps

    text = open(LOC).read()
    n_nodes = n_chests = 0
    renames = {}
    for loc, secs in sorted(split.items()):
        n_nodes += 1
        n_chests += sum(len(a) for a in secs.values())
        print(f"  {loc}")
        for s, a in sorted(secs.items()):
            label = node_label(loc, s)
            print(f"      {s:30s} {len(a):2d} -> "
                  + (label if len(a) == 1 else f"{label} 1..{len(a)}"))
            for n, ap in enumerate(a, 1):
                child = label if len(a) == 1 else f"{label} {n}"
                renames[ap] = (child, "Incentive" if secs_hosted.get((s, ap)) else "Chest",
                               secs_hosted.get((s, ap)))
        if apply:
            start, end = find_node(text, loc)
            indent = len(text[:start].split("\n")[-1])
            node = lenient(LOC)
            def pick(nodes):
                for x in nodes:
                    if x["name"] == loc:
                        return x
                    r = pick(x.get("children", []))
                    if r:
                        return r
            node = pick(node)
            text = text[:start] + rebuild(node, secs, markers, positions, indent).lstrip() + text[end:]

    print(f"\n{n_nodes} locations, {n_chests} chests")
    if not apply:
        print("(dry run; pass --apply)")
        return
    open(LOC, "w").write(text)

    src = open(MAP).read().split("\n")
    out = []
    for line in src:
        m = re.match(r"(\s*)\[(\d+)\] = \{", line)
        ap = int(m.group(2)) if m else None
        if ap in renames:
            child, sec, hosted = renames[ap]
            tail = f', "{hosted}"' if hosted else ""
            out.append(f'{m.group(1)}[{ap}] = {{"@{child}/{sec}"{tail}}},')
        else:
            out.append(line)
    open(MAP, "w").write("\n".join(out))
    print("applied")


if __name__ == "__main__":
    main()
