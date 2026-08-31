"""The four pin-toggle icons are the ones the writer draws, and the pack knows
which of them are wired up.

Two guards, because the icons have two ways to rot and neither one shows up in
the Lua suite:

  * **the committed PNGs are what tools/make_toggle_icons.py draws.** The
    writer has a `--check` mode and nothing ran it, so editing `GLYPH` or a
    shape function left the images stale with every suite still green. That is
    the shape of check the repo already refuses elsewhere -- one that cannot
    fail is worth nothing -- so it runs here. It is also the existence check:
    a deleted image reads as differing from what the writer draws.

  * **an icon is either referenced or knowingly ahead of its toggle.** Three of
    the four were drawn before the pins they switch, so they sit in the pack
    with no item, no layout cell and no Lua naming them. That is fine while it
    is deliberate and recorded; it is not fine as a thing nobody notices. The
    audit fails either way round: wiring one up without taking it off STAGED
    fails, and drawing a fifth that nothing references fails.

`tests/test_mapping.lua`'s 4b check validates itemgrid *codes* against the item
JSON. It never looks at an image, which is why neither of these was caught.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import make_toggle_icons                                       # noqa: E402

# Icons drawn ahead of the toggles that will use them, and so referenced by
# nothing. Empty: all four Pins toggles are built. Kept rather than deleted
# because it is what fails when a fifth icon is drawn and left unwired, and
# what fails again when one is wired up without being taken off this list.
STAGED = set()

# Where a reference to an image can live. Searched as text rather than parsed:
# an "img" in an item, a "map_image" in maps.json and an image built by string
# concatenation in Lua all count, and a parser that understood only the first
# would report the other two as dead. Two things are excluded: the writer, which
# names every icon by construction, and this directory -- a name mentioned only
# by the test that audits it is not a reference, and letting one count would let
# the audit satisfy itself.
SEARCH_DIRS = ("items", "layouts", "locations", "maps", "scripts", "tools")
SEARCH_EXT = (".json", ".lua", ".py")
SKIP = (os.path.join(TOOLS, "make_toggle_icons.py"), HERE)


def pack_text():
    """Every file that could name an image, as one blob."""
    out = []
    for d in SEARCH_DIRS:
        for root, _, files in os.walk(os.path.join(PACK, d)):
            for f in files:
                path = os.path.join(root, f)
                if f.endswith(SEARCH_EXT) and not path.startswith(SKIP):
                    with open(path, encoding="utf-8") as fh:
                        out.append(fh.read())
    return "\n".join(out)


def main():
    fails = []

    def check(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")
        print(f"{'ok  ' if got == want else 'FAIL'} {label}")

    # The committed images are the drawn ones.
    check("the committed icons are what make_toggle_icons.py draws",
          make_toggle_icons.main(["--check"]), 0)

    # Every icon is referenced, or listed above as waiting for its toggle. The
    # writer's own table is the inventory, so a fifth icon joins this check by
    # being added there rather than by being remembered here.
    text = pack_text()
    dead = {name for name in make_toggle_icons.ICONS
            if not re.search(re.escape(name + ".png"), text)}
    check("the icons waiting for their toggles are the ones recorded as such",
          dead, STAGED)

    for f in fails:
        print("     " + f)
    print("ALL PASS" if not fails else f"{len(fails)} FAILED")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
