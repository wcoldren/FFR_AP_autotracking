"""Every committed layout must draw on the cartridge it says it was drawn on.

The other lane suites all build their own fixtures -- synthesised layouts,
stripped working copies -- which is what makes them portable, and it is also
why none of them reads the files that actually ship. `tools/lanes/` holds
entries keyed to several cartridges, and an entry keyed to the wrong one is
inert rather than broken: `lane_file.load` reports "no layout for this
cartridge", which is the *ordinary* outcome on any floor a seed re-laid. A
mis-keyed entry and an honestly-absent one are the same event to every caller,
so a whole carry could land wrong and nothing would say a word.

This closes that by taking each entry's own claim seriously. `seen` names the
cartridges an entry was drawn or carried against; where one of those cartridges
is on this machine, the entry has to load on it -- the same `lane_file.load`
call `regen_maps` makes when it draws the art, so a pass here is the art
drawing and not a re-implementation of it.

**A cartridge that is not here is skipped, and the skip is counted.** That is
the honest answer on a fresh clone, where none of them is. What must not happen
is a silent pass: if no committed entry could be checked against anything, this
says so and skips rather than reporting that all is well.

Cartridges are looked for beside the ones this machine already names --
FF1_ROM's seed directory and FF1_CORPUS -- rather than at a path written down
here, since where the seeds live is a fact about the machine.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import lane_file as LF  # noqa: E402
import port_lanes as PL  # noqa: E402
import regen_maps  # noqa: E402
import render_maps as rm  # noqa: E402

fails = []


def check(what, got, want):
    ok = got == want
    print(("ok   " if ok else "FAIL ") + what.ljust(58)
          + ("" if ok else f" {got!r}"))
    if not ok:
        fails.append(f"{what}: got {got!r}, want {want!r}")


def search_roots():
    """Where to look for cartridges, from what this machine already names.

    FF1_ROM is one seed inside a tree of them, so its parent's parent is the
    tree; FF1_CORPUS is a directory of them already. Both are optional and
    either may be absent.
    """
    roots = []
    rom = os.environ.get("FF1_ROM")
    if rom and os.path.isfile(rom):
        roots.append(os.path.dirname(os.path.dirname(os.path.abspath(rom))))
    corpus = os.environ.get("FF1_CORPUS")
    if corpus and os.path.isdir(corpus):
        roots.append(os.path.abspath(corpus))
    out = []
    for r in roots:
        if os.path.isdir(r) and not any(
                r == o or r.startswith(o + os.sep) for o in out):
            out.append(r)
    return out


# --- what the committed files claim
wanted = {}
for name in sorted(set(rm.MAP_FILES.values())):
    doc = LF.read(name)
    if doc is None:
        continue
    for entry in doc.get("layouts", ()):
        for seen in entry.get("seen", ()):
            wanted.setdefault(seen, []).append(name)
if not wanted:
    print("skipped: no committed layout names a cartridge")
    sys.exit(0)

# --- which of those cartridges are on this machine
roots = search_roots()
if not roots:
    print("skipped: neither FF1_ROM nor FF1_CORPUS says where seeds live")
    sys.exit(0)
have = {}
for root in roots:
    for dirpath, _dirs, files in os.walk(root):
        for f in sorted(files):
            if not f.endswith(".nes"):
                continue
            p = os.path.join(dirpath, f)
            with open(p, "rb") as fh:
                rom = fh.read()
            stamp = regen_maps.cartridge_id(rom, p)["ffr"]
            if stamp in wanted and stamp not in have:
                have[stamp] = p

missing = sorted(set(wanted) - set(have))
if not have:
    print(f"skipped: none of the {len(wanted)} cartridge(s) the committed "
          "layouts name is on this machine")
    sys.exit(0)

# --- and the entries keyed to them have to draw
checked = 0
for stamp, names in sorted(wanted.items()):
    if stamp not in have:
        continue
    side = PL.Side(have[stamp])
    undrawn = []
    for name in sorted(set(names)):
        map_id = [m for m, n in rm.MAP_FILES.items() if n == name][0]
        lanes, why = LF.load(side.rom, side.graph, map_id, side.chests,
                             name=name, fixed=side.fixed)
        if why is not None:
            undrawn.append(f"{name}: {why}")
        checked += 1
    # The seed alone, not the whole record: the flag string runs to a couple of
    # hundred characters and says nothing a person reads at this width.
    check(f"the {len(set(names))} layout(s) drawn on {stamp.split('|')[1]} "
          "all draw on it", undrawn, [])

check("and something was actually checked", checked > 0, True)
print(f"     {checked} layout(s) against {len(have)} cartridge(s)"
      + (f"; {len(missing)} cartridge(s) not on this machine" if missing
         else ""))
for m in missing:
    print(f"     not here: {m.split('|')[0]}|{m.split('|')[1]}"
          f"  ({len(set(wanted[m]))} layout(s) unchecked)")

for f in fails:
    print("     " + f)
print("ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
