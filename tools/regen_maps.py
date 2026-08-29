#!/usr/bin/env python3
"""Redraw the pack's dungeon maps from your own cartridge, without touching it.

The pack ships DarkmoonEX's hand-drawn maps. They are vanilla maps: right for a
vanilla layout, silent about anything the seed changed. A No-Overworld seed
seals every town's outer wall, stamps 75 new staircases across 34 maps and
builds two rooms inside Coneria Castle, none of which the shipped art has. So
the tabs show the right rooms with the wrong exits.

render_maps.py draws the seed's own maps out of the ROM. What it cannot do on
its own is put them in front of PopTracker, because swapping the art is not a
file copy:

  * the 51 shipped images are composites at 51 different sizes, each with a
    hand-solved offset in tools/map_calibration.json;
  * the pixel coordinates of all 253 dungeon markers in locations/*.json were
    computed from those offsets, so new art with old coordinates puts every
    marker somewhere other than its chest;
  * ten of the 61 maps -- the eight towns, Coneria Castle 2F and Bahamut's Lair
    B2 -- have no image in the pack at all, so they have no maps.json entry and
    no tab.

This does all of it as one piece, and writes none of it into the repo. Output
goes to PopTracker's user-override tree, which Pack::ReadFile consults ahead of
the pack for every file it loads, images included (pack.cpp:226-243, and
getImage at :445 goes through the same call). So the checkout keeps shipping the
screenshots, ROM-derived art never lands in git, and removing the override
directory puts everything back.

    tools/regen_maps.py FFR_seed.nes

Re-running is cheap: it hashes the ROM and its own inputs, and if nothing moved
it does no work at all. When the ROM does change, only the maps whose pixels
actually differ get rewritten -- two seeds of the same mode share most of their
art, and No-Overworld rolls only the Gaia gateway and the Waterfall stairs.

Deliberately not done here: MAP_VALUE still calls maps 0-7 "Overworld", so
maptab.lua will not follow you into a town. The town tabs exist and can be
clicked; auto-switching needs a mode-aware MAP_VALUE, which is a pack change
rather than a per-cartridge one.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import extract_chests
import make_markers
import pngio
import render_maps

TILE_PX = render_maps.TILE_PX
CACHE_NAME = ".regen_cache.json"
CACHE_VERSION = 1

# Everything whose content decides what gets written. A change to any of them
# invalidates the cache the same way a new cartridge does.
INPUT_FILES = [
    "tools/regen_maps.py",
    "tools/render_maps.py",
    "tools/extract_chests.py",
    "tools/make_markers.py",
    "tools/pngio.py",
    "tools/map_calibration.json",
    "tools/npc_positions.json",
    "maps/maps.json",
    "layouts/shared.json",
    "locations/overworld.json",
    "locations/incentives.json",
    "locations/NOverworld/incentives.json",
]

# Every map this redraws. A marker on one of these needs a calibration entry
# to be moved; a marker on anything else -- the overworld, the incentive sheet --
# sits on art this does not touch.
REDRAWN = set(render_maps.MAP_FILES.values())

# The two maps the pack draws as one composite each. Rendered separately they
# are two images, so the tab that held one now holds both side by side --
# trackerview.cpp:902 docks a tab's maps when there is more than one.
COMPANION_TABS = {
    "Coneria Castle": ["con_castle", "con_castle2F"],
    "Bahamut's Lair": ["bahamut", "bahamutB2"],
}

# No-Overworld turns these into real rooms with chests and stairs. The pack has
# never had art for them, so they get a tab group of their own.
TOWN_TABS = [
    ("Coneria", "coneria_town"), ("Pravoka", "pravoka"),
    ("Elfland", "elfland"), ("Melmond", "melmond"),
    ("Crescent Lake", "crescent_lake"), ("Gaia", "gaia"),
    ("Onrac", "onrac"), ("Lefein", "lefein"),
]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pack_uid():
    with open(os.path.join(PACK, "manifest.json")) as f:
        return json.load(f)["package_uid"]


def default_out():
    return os.path.join(os.path.expanduser("~"), "PopTracker", "user-override",
                        pack_uid())


def lenient(path):
    """The pack's JSON has trailing commas in places; PopTracker tolerates them."""
    with open(path) as f:
        return json.loads(re.sub(r",(\s*[}\]])", r"\1", f.read()))


def inputs_fingerprint():
    h = hashlib.sha256()
    for rel in INPUT_FILES:
        h.update(rel.encode())
        with open(os.path.join(PACK, rel), "rb") as f:
            h.update(f.read())
    return h.hexdigest()


# ---------------------------------------------------------------- calibration

def rendered_calibration():
    """The calibration the rendered art needs: none, expressed as a file.

    Every image is 64 tiles at TILE_PX, so tile n starts at pixel TILE_PX * n
    with no offset and no per-region special case. make_markers reads this the
    same way it reads the hand-solved one.
    """
    return {
        name: {
            "rom_map_id": map_id,
            "tile_px": TILE_PX,
            "regions": [{"offset_x": 0, "offset_y": 0}],
        }
        for map_id, name in render_maps.MAP_FILES.items()
    }


def tile_of(entry, x, y):
    """Invert make_markers.build: pixel back to the ROM tile that produced it.

    A candidate region has to divide evenly and land in bounds, and it also has
    to be the region make_markers.region_for would have picked for that tile --
    the first whose bounds hold it. Two regions cropped from the same 16 px
    source grid divide identically, and without the second test the earlier one
    would answer for a tile that belongs to the later. A marker no region
    explains is one this cannot move, which is reported rather than guessed at.
    """
    tp = entry["tile_px"]
    half = tp // 2
    for i, r in enumerate(entry["regions"]):
        dx, dy = x - r["offset_x"] - half, y - r["offset_y"] - half
        if dx < 0 or dy < 0 or dx % tp or dy % tp:
            continue
        col, row = dx // tp, dy // tp
        if not in_region(r, col, row):
            continue
        if next(j for j, o in enumerate(entry["regions"])
                if in_region(o, col, row)) != i:
            continue
        return col, row
    return None


def in_region(r, col, row):
    """make_markers.region_for's bounds test, which this has to agree with."""
    rlo, rhi = r.get("rows", (0, 63))
    clo, chi = r.get("cols", (0, 63))
    return rlo <= row <= rhi and clo <= col <= chi


# ------------------------------------------------------------------- contents

def build_images(rom):
    """-> {relpath: (w, h, rgb)} for all 61 maps."""
    out = {}
    for map_id, name in render_maps.MAP_FILES.items():
        out[f"images/maps/{name}.png"] = render_maps.render(rom, map_id)
    return out


def build_maps_json():
    """The pack's maps.json with every rendered map in it.

    The overworld and incentive entries keep the pack's own art and sizes --
    this changes the dungeon maps and nothing else. Rendered maps are all
    1024x1024, so one location size fits all of them.
    """
    entries = lenient(os.path.join(PACK, "maps", "maps.json"))
    by_name = {e["name"]: e for e in entries}
    order = [e["name"] for e in entries]
    for name in render_maps.MAP_FILES.values():
        e = by_name.setdefault(name, {"name": name})
        if name not in order:
            order.append(name)
        e["img"] = f"images/maps/{name}.png"
        e.setdefault("location_size", 24)
        e.setdefault("location_border_thickness", 3)
    return [by_name[n] for n in order]


def remap_locations(old_cal, path):
    """-> (new document, moved, unmoved, unexplained, uncalibrated).

    Every marker on a map this redraws is moved from its old pixel to the one
    the rendered art puts that tile at. Markers on the overworld and incentive
    maps are left alone: their art does not change.

    A marker on a map that is redrawn but has no calibration entry can be
    neither moved nor left: the art under it changes and its pixel does not, so
    it would end up pointing at whatever the new art happens to have there. Only
    a map this does not redraw is safely unmoved, so the rest are reported.
    """
    doc = lenient(os.path.join(PACK, path))
    moved = unmoved = 0
    unexplained = []
    uncalibrated = []

    def walk(nodes):
        nonlocal moved, unmoved
        for n in nodes:
            if not isinstance(n, dict):
                continue
            for ml in n.get("map_locations") or []:
                entry = old_cal.get(ml.get("map"))
                if entry is None:
                    if ml.get("map") in REDRAWN:
                        uncalibrated.append((n.get("name"), ml.get("map"),
                                             ml["x"], ml["y"]))
                    else:
                        unmoved += 1
                    continue
                tile = tile_of(entry, ml["x"], ml["y"])
                if tile is None:
                    unexplained.append((n.get("name"), ml.get("map"),
                                        ml["x"], ml["y"]))
                    continue
                col, row = tile
                ml["x"] = col * TILE_PX + TILE_PX // 2
                ml["y"] = row * TILE_PX + TILE_PX // 2
                moved += 1
            walk(n.get("children") or [])

    walk(doc)
    return doc, moved, unmoved, unexplained, uncalibrated


def map_block(content):
    """A tab's {"type": "map"} block, or None.

    shared.json writes some tabs' content bare and some wrapped in a list --
    every top-level tab uses the list form, and the nested ones a bare dict --
    so anything reaching for a tab's maps has to take both.
    """
    if isinstance(content, dict):
        return content if content.get("type") == "map" else None
    if isinstance(content, list):
        for v in content:
            if isinstance(v, dict) and v.get("type") == "map":
                return v
    return None


def build_layouts():
    """shared.json with the ten maps the pack has no tab for."""
    doc = lenient(os.path.join(PACK, "layouts", "shared.json"))
    docked = set()

    def retitle(node):
        """Give the two composite tabs their second floor."""
        if not isinstance(node, (dict, list)):
            return
        if isinstance(node, list):
            for v in node:
                retitle(v)
            return
        for tab in node.get("tabs") or []:
            maps = COMPANION_TABS.get(tab.get("title"))
            block = map_block(tab.get("content")) if maps else None
            if block is not None:
                block["maps"] = list(maps)
                docked.add(tab["title"])
            retitle(tab.get("content"))
        for v in node.values():
            retitle(v)

    retitle(doc)
    missing = sorted(set(COMPANION_TABS) - docked)
    if missing:
        # Failing quietly here is what left con_castle2F rendered, registered in
        # maps.json and reachable from no tab at all, so this is fatal.
        sys.exit("no map tab in layouts/shared.json for: " + ", ".join(missing))
    towns = {
        "title": "Towns",
        "content": {
            "type": "tabbed",
            "tabs": [{"title": t, "content": {"type": "map", "maps": [m]}}
                     for t, m in TOWN_TABS],
        },
    }
    tabs = doc["shared_other_tabs"]["tabs"]
    doc["shared_other_tabs"]["tabs"] = [t for t in tabs
                                        if t.get("title") != "Towns"] + [towns]
    return doc


# ---------------------------------------------------------------------- cache

def load_cache(out_dir):
    try:
        with open(os.path.join(out_dir, CACHE_NAME)) as f:
            cache = json.load(f)
    except (OSError, ValueError):
        return None
    return cache if cache.get("version") == CACHE_VERSION else None


def outputs_intact(out_dir, cache):
    """Every file the last run wrote is still there with the bytes it wrote.

    Without this, deleting an image by hand would leave a cache saying the work
    was already done, and the tab would come up blank with nothing to say why.
    """
    for rel, want in cache.get("outputs", {}).items():
        try:
            with open(os.path.join(out_dir, rel), "rb") as f:
                if sha(f.read()) != want:
                    return False
        except OSError:
            return False
    return True


# ----------------------------------------------------------------------- main

def write_if_changed(out_dir, rel, data, dry_run):
    """-> True if the file was written. Unchanged files keep their mtime."""
    path = os.path.join(out_dir, rel)
    try:
        with open(path, "rb") as f:
            if f.read() == data:
                return False
    except OSError:
        pass
    if not dry_run:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
    return True


def encode(w, h, rgb, out_dir, rel, dry_run):
    """PNG bytes for a rendered map. pngio writes to a path, so this goes
    through a temporary one rather than reimplementing the encoder."""
    tmp = os.path.join(out_dir, rel + ".tmp")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    pngio.write_rgb(tmp, w, h, rgb)
    with open(tmp, "rb") as f:
        data = f.read()
    os.remove(tmp)
    return data


def main():
    ap = argparse.ArgumentParser(
        description="Redraw the pack's dungeon maps from a cartridge, into "
                    "PopTracker's user-override tree.")
    ap.add_argument("rom")
    ap.add_argument("-o", "--out", help="override directory "
                                        "(default: ~/PopTracker/user-override/<uid>)")
    ap.add_argument("--force", action="store_true",
                    help="regenerate even if nothing changed")
    ap.add_argument("--dry-run", action="store_true",
                    help="say what would change, write nothing")
    ap.add_argument("--clean", action="store_true",
                    help="remove the override directory and exit")
    args = ap.parse_args()

    out_dir = args.out or default_out()

    if args.clean:
        if os.path.isdir(out_dir):
            if not args.dry_run:
                shutil.rmtree(out_dir)
            print(f"removed {out_dir}")
        else:
            print(f"nothing to remove at {out_dir}")
        return 0

    with open(args.rom, "rb") as f:
        rom = f.read()
    if rom[:4] != b"NES\x1a":
        sys.exit("not an iNES ROM")

    rom_sha = sha(rom)
    inputs_sha = inputs_fingerprint()
    cache = load_cache(out_dir)
    if (not args.force and cache
            and cache.get("rom") == rom_sha
            and cache.get("inputs") == inputs_sha
            and outputs_intact(out_dir, cache)):
        print(f"up to date: {len(cache['outputs'])} files in {out_dir}")
        print("nothing to do (--force to regenerate anyway)")
        return 0

    if cache and cache.get("rom") != rom_sha:
        print("cartridge changed since the last run")
    elif cache and cache.get("inputs") != inputs_sha:
        print("the pack or these tools changed since the last run")

    bank = extract_chests.standard_map_bank(rom)
    print(f"reading standard maps from bank ${bank:02X}")

    files = {}

    # 1. the art
    for rel, (w, h, rgb) in build_images(rom).items():
        files[rel] = encode(w, h, rgb, out_dir, rel, args.dry_run)

    # 2. the markers, moved onto it
    old_cal = {k: v for k, v in
               lenient(os.path.join(PACK, "tools", "map_calibration.json")).items()
               if not k.startswith("_")}
    moved = unmoved = 0
    problems = []
    uncalibrated = []
    for rel in ("locations/overworld.json", "locations/incentives.json",
                "locations/NOverworld/incentives.json"):
        doc, m, u, bad, uncal = remap_locations(old_cal, rel)
        files[rel] = (json.dumps(doc, indent=4) + "\n").encode()
        moved += m
        unmoved += u
        problems += bad
        uncalibrated += uncal

    # A marker that moved has to land on the tile its chest -- or its NPC -- is
    # actually on. The ROM's own answer for both is on disk, so this compares
    # against it rather than trusting the arithmetic.
    #
    # The NPC half is vanilla-derived on purpose (see extract_npcs.py): FFR
    # randomizes what an NPC gives you, not where it stands. So it is read from
    # npc_positions.json rather than off this cartridge.
    cal = rendered_calibration()
    chests, _ = extract_chests.extract(rom)
    with open(os.path.join(HERE, "npc_positions.json")) as f:
        npcs = json.load(f)
    placed = set()
    # build() keys its output by int, so the NPCs go in renumbered -- what is
    # wanted here is the set of pixels, not which NPC is at which.
    npc_places = {str(i): v for i, v in enumerate(npcs.values())}
    for group in (make_markers.build({str(k): v for k, v in chests.items()}, cal),
                  make_markers.build(npc_places, cal)):
        placed |= {(m["map"], m["x"], m["y"])
                   for marks in group.values() for m in marks}
    stray = []
    unmovable = {(m, x, y) for _, m, x, y in problems}
    for rel in ("locations/overworld.json",):
        doc = json.loads(files[rel])

        def walk(nodes):
            for n in nodes:
                if not isinstance(n, dict):
                    continue
                for ml in n.get("map_locations") or []:
                    if ml.get("map") in old_cal \
                            and (ml["map"], ml["x"], ml["y"]) not in unmovable \
                            and (ml["map"], ml["x"], ml["y"]) not in placed:
                        stray.append((n.get("name"), ml["map"], ml["x"], ml["y"]))
                walk(n.get("children") or [])
        walk(doc)

    # 3. the maps and tabs the new art needs
    files["maps/maps.json"] = (json.dumps(build_maps_json(), indent=4) + "\n").encode()
    files["layouts/shared.json"] = (json.dumps(build_layouts(), indent=4) + "\n").encode()

    def report(what, rows):
        print(f"\nFAILED: {len(rows)} {what}:")
        for name, m, x, y in rows[:10]:
            print(f"  {name} on {m} at {x},{y}")
        if len(rows) > 10:
            print(f"  ... and {len(rows) - 10} more")

    if problems:
        report("markers sit on no calibrated tile, so there is no tile to put "
               "them back on in the rendered art", problems)
    if uncalibrated:
        report("markers are on maps this redraws, but tools/map_calibration.json "
               "has no entry to move them by", uncalibrated)
    if stray:
        report("moved markers land on neither a chest tile nor an NPC tile",
               stray)
    if problems or uncalibrated or stray:
        print("\nnothing was written.")
        return 1

    changed = [rel for rel in sorted(files)
               if write_if_changed(out_dir, rel, files[rel], args.dry_run)]

    if not args.dry_run:
        with open(os.path.join(out_dir, CACHE_NAME), "w") as f:
            json.dump({"version": CACHE_VERSION, "rom": rom_sha,
                       "inputs": inputs_sha,
                       "outputs": {rel: sha(data)
                                   for rel, data in sorted(files.items())}},
                      f, indent=1)

    verb = "would write" if args.dry_run else "wrote"
    print(f"\n{verb} {len(changed)} of {len(files)} files to {out_dir}")
    print(f"  {moved} markers moved onto the rendered art, every one on the "
          "chest or NPC tile the ROM puts it on")
    print(f"  {unmoved} left alone (the overworld and incentive maps are not "
          "redrawn, so their markers keep the pack's pixels)")
    if changed and len(changed) < len(files):
        print("  changed: " + ", ".join(changed[:8])
              + (" ..." if len(changed) > 8 else ""))
    if not args.dry_run:
        print("\nRestart PopTracker to pick it up. `--clean` puts the pack back.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
