"""The chest-slot icons are the ones the writer draws, every item's picture
exists, and no chest cell shares a picture with a person.

Three guards, two of them cartridge-free:

  * **every `img` an item names is a file in the pack.** PopTracker draws a
    missing item image as nothing, without a word, and `tests/test_mapping.lua`
    validates grid *codes* against the item JSON and never looks at an image.
    A repointed item whose new file was never written is exactly the mistake
    this change could make, so the check is here and runs on every machine.

  * **rows 3-4 of the Locations grid wear no picture rows 1-2 or the Bosses
    row wear.** That is the defect the writer exists to fix -- the Titan's
    Trove drawn as the Titan, the Earth chest drawn as the Vampire -- stated as
    a rule over the layout rather than as a list of the cells that were wrong,
    so the next reuse fails too. The grid is read from `layouts/shared.json`
    and the pictures from the item files, not from this test's memory of them.

  * **the committed PNGs are what tools/make_slot_icons.py draws.** Same
    shape as the door and toggle icon guards: the writer has a `--check` mode
    and a mode nothing runs is worth nothing. Needs a cartridge and skips
    without one, saying so. Its own `self_check` runs first, so a source icon
    that stopped being 2x art or a floor that lost its chest fails by name
    rather than as a byte difference.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import make_slot_icons  # noqa: E402

CHEST_ROWS = (2, 3)      # rows 3-4 of shared_locations_grid, zero-based
PERSON_ROWS = (0, 1)


def items_by_code():
    """code -> img, over every item file, stages included."""
    out = {}
    for name in sorted(os.listdir(os.path.join(PACK, "items"))):
        if not name.endswith(".json"):
            continue
        with open(os.path.join(PACK, "items", name), encoding="utf-8") as fh:
            for it in json.load(fh):
                entries = it.get("stages", [it])
                for e in entries:
                    for code in str(e.get("codes", "")).split(","):
                        if code and "img" in e:
                            out.setdefault(code.strip(), e["img"])
    return out


def grid_rows(key):
    with open(os.path.join(PACK, "layouts", "shared.json"), encoding="utf-8") as fh:
        return json.load(fh)[key]["content"]["rows"]


def main():
    fails = []

    def check(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")
        print(f"{'ok  ' if got == want else 'FAIL'} {label}")

    imgs = items_by_code()
    missing = sorted({img for img in imgs.values()
                      if not os.path.exists(os.path.join(PACK, img))})
    check("every item image is a file in the pack", missing, [])

    rows = grid_rows("shared_locations_grid")
    bosses = grid_rows("shared_boss_grid")[0]
    chest_codes = [c for r in CHEST_ROWS for c in rows[r]]
    person_codes = [c for r in PERSON_ROWS for c in rows[r]] + bosses
    person_imgs = {imgs.get(c) for c in person_codes}
    shared = sorted(c for c in chest_codes if imgs.get(c) in person_imgs)
    check("no chest cell wears a person's or a boss's picture", shared, [])

    # The writer's table is the inventory of chest cells, minus the shop,
    # which is a shop and is drawn as one on purpose.
    check("the writer draws every chest cell but the shop",
          sorted(set(chest_codes) - {"shopItem"}), sorted(make_slot_icons.SLOTS))
    check("  and every cell it draws is pointed at what it drew",
          sorted(c for c in make_slot_icons.SLOTS
                 if imgs.get(c) != make_slot_icons.slot_img(c)), [])

    path = os.environ.get("FF1_ROM")
    if not path:
        print("SKIP  set FF1_ROM to a Final Fantasy cartridge to check the "
              "committed icons against the writer")
    else:
        import entrance_graph
        rom = open(path, "rb").read()
        graph = entrance_graph.Graph(entrance_graph.Rom(path))
        check("the writer's own claims hold on this cartridge",
              make_slot_icons.self_check(rom, graph), [])
        built = make_slot_icons.icons(rom, graph)
        stale = sorted(rel for rel, data in built.items()
                       if not os.path.exists(os.path.join(PACK, rel))
                       or open(os.path.join(PACK, rel), "rb").read() != data)
        check("the committed icons are what make_slot_icons.py draws", stale, [])

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
