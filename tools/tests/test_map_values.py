"""The rewritten MAP_VALUE names tabs the override actually has, and nothing else.

Needs no cartridge. `tests/test_maptab.lua` check 1 already asserts that every
tab `MAP_VALUE` names exists -- but it reads the *pack's* table against the
*pack's* layouts, and the whole point of the rewrite is that neither of those is
what PopTracker ends up serving. So the same check has to be made again, on the
generated pair, or the eight new paths are asserted by nothing at all.

The three ways this could quietly be wrong:

  - the regex eats an entry it was not meant to, and a dungeon quietly starts
    pointing at a town (or at nothing);
  - the tab titles drift from the group `build_layouts()` builds, so every town
    resolves to a tab that is not there -- which PopTracker reports by doing
    nothing whatsoever;
  - the pack's table stops saying "Overworld" for a town, the rewrite silently
    matches nothing, and the override ships a table that was never rewritten.
"""
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import regen_maps                                              # noqa: E402

MAP_LAYOUTS = [
    "layouts/standard/tracker.json",
    "layouts/shardHunt/tracker.json",
    "layouts/NOverworld/tracker.json",
    "layouts/NOverworld/shardsTracker.json",
]

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s: got %r, want %r" % (label, got, want))
    print("%s %s" % ("ok  " if got == want else "FAIL", label))


def entries(text):
    """{map id: tab path} out of a mapValues.lua."""
    return {int(m.group(1)): m.group(2)
            for m in re.finditer(r'\[(\d+)\]\s*=\s*"([^"]*)"', text)}


def tab_titles(layout_file, shared):
    """Every tab title the layout defines, following layout references.

    The same walk tests/test_maptab.lua does, for the same reason: a
    {"type": "layout"} reference is expanded by PopTracker before any of this is
    on screen, so a walker that stopped at one would report that the standard
    layout has no dungeon tabs at all.
    """
    titles, seen = set(), set()

    def walk(node):
        if not isinstance(node, dict):
            if isinstance(node, list):
                for v in node:
                    walk(v)
            return
        if node.get("type") == "layout" and node.get("key"):
            if node["key"] not in seen:
                seen.add(node["key"])
                walk(shared.get(node["key"]))
            return
        if node.get("type") == "tabbed":
            for t in node.get("tabs") or []:
                if t.get("title"):
                    titles.add(t["title"])
                walk(t.get("content"))
        for v in node.values():
            walk(v)

    walk(regen_maps.lenient(os.path.join(PACK, layout_file)))
    return titles


pack = entries(open(os.path.join(PACK, "scripts/autotracking/mapValues.lua")).read())
made = entries(regen_maps.build_map_values())

# ---- 1. exactly the eight towns moved

moved = {mid for mid in pack if pack[mid] != made.get(mid)}
check("the eight towns are what changed", sorted(moved), list(range(8)))
check("and every other entry is untouched",
      {k: v for k, v in made.items() if k not in moved},
      {k: v for k, v in pack.items() if k not in moved})
check("the towns were on the overworld before",
      sorted({pack[m] for m in moved}), ["Overworld"])

# ---- 2. every segment of every path names a tab that exists

shared = json.loads(json.dumps(regen_maps.build_layouts()))
for layout in MAP_LAYOUTS:
    titles = tab_titles(layout, shared)
    bad = sorted({"map %d wants tab %r" % (mid, seg)
                  for mid, path in made.items() if path != "Overworld"
                  for seg in path.split("/") if seg not in titles})
    # Two of the four live in the same directory, so the file name goes in the
    # label too: an "ok" line and a missing one would look identical.
    label = layout[len("layouts/"):-len(".json")]
    check("every tab exists in " + label, bad, [])

# The tab group the rewrite points at has to be one build_layouts() built, not
# one that happened to be in the pack already.
check("the Towns group is the generated one",
      "Towns" in {t.get("title") for t in shared["shared_other_tabs"]["tabs"]},
      True)

# ---- 3. a table that no longer says "Overworld" stops the run

with tempfile.TemporaryDirectory() as tmp:
    os.makedirs(os.path.join(tmp, "scripts/autotracking"))
    src = os.path.join(PACK, "scripts/autotracking/mapValues.lua")
    dst = os.path.join(tmp, "scripts/autotracking/mapValues.lua")
    text = open(src).read()
    # One town already pointed somewhere else, as a hand edit would leave it.
    text = text.replace('[3] = "Overworld",', '[3] = "Other/Melmond",', 1)
    with open(dst, "w") as f:
        f.write(text)
    was, regen_maps.PACK = regen_maps.PACK, tmp
    try:
        regen_maps.build_map_values()
        check("a hand-edited table stops the run", "returned", "SystemExit")
    except SystemExit as e:
        check("a hand-edited table stops the run", "3" in str(e), True)
    finally:
        regen_maps.PACK = was

for f in fails:
    print("     " + f)
print("ALL PASS" if not fails else "%d FAILED" % len(fails))
sys.exit(1 if fails else 0)
