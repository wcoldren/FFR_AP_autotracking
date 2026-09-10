"""Where the cartridges on this machine are, for the suites that read several.

Most suites here synthesise what they need and run anywhere. A few cannot:
holding a committed claim against the cartridge it names, or measuring a roll
that only exists on a real seed, means finding real seeds. Those are looked for
beside the cartridges this machine already names -- FF1_ROM's seed tree and
FF1_CORPUS -- rather than at a path written down in a suite, since where the
seeds live is a fact about the machine and not about the pack.

This was copied into two suites before it was a module, which is the ordinary
way the two copies come to disagree. Neither copy had drifted yet; moving it
was cheaper than finding out when they had.

Both entry points answer emptily rather than raising when the machine names
nothing. A caller has to say so and skip -- silence here is the honest answer
on a fresh clone, and reporting it as a pass is the failure to avoid.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)


def _inside(inner, outer):
    """Is `inner` `outer` itself, or somewhere beneath it?"""
    return inner == outer or inner.startswith(outer + os.sep)


def search_roots():
    """The directories to walk, deduplicated and with no root inside another.

    FF1_ROM is one seed inside a tree of them, so its parent's parent is the
    tree; FF1_CORPUS is a directory of them already. Both are optional and
    either may be absent.

    Containment is collapsed in both directions, which is not symmetry for its
    own sake. An earlier cut only dropped a new root that sat inside a kept
    one, so FF1_CORPUS naming the tree that holds FF1_ROM's seed kept both and
    `cartridges` -- which de-duplicates nothing itself -- returned every
    cartridge twice. One caller keys on the stamp and absorbed that; the sweep
    does not, and would have swept the machine twice over and said so in its
    count. The covered direction was the one this machine's own config happens
    to take, which is how it went unnoticed.
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
        if not os.path.isdir(r) or any(_inside(r, o) for o in out):
            continue
        out = [o for o in out if not _inside(o, r)]
        out.append(r)
    return out


def cartridges(roots=None):
    """Every `.nes` under the roots, sorted, as absolute paths.

    Sorted so a suite that reports "the first cartridge that answered" reports
    the same one twice running. Nothing here opens a file: a caller that wants
    the stamp reads it, and a caller that only wants a count does not pay for
    one.
    """
    out = []
    for root in (search_roots() if roots is None else roots):
        for dirpath, _dirs, files in os.walk(root):
            for f in files:
                if f.endswith(".nes"):
                    out.append(os.path.join(dirpath, f))
    return sorted(out)


def rom_or_none(path):
    """`entrance_graph.Rom` for `path`, or None where it is not a full image.

    `Rom._load` reports a non-iNES or too-short file with `sys.exit`, which is
    the right answer for a CLI handed one cartridge and the wrong one for a
    suite walking whatever `.nes` files a machine happens to hold. `SystemExit`
    derives from BaseException, so the obvious `except Exception` around the
    constructor does not catch it: one stray file under a search root aborts
    the whole run with the exit status of a failed gate. The roots are wide
    enough for that to matter -- FF1_ROM pointing at the vanilla image in a
    shared `roms/` directory makes its parent's parent the home directory.

    Caught here rather than at each call site so every caller that walks
    `cartridges()` skips rather than aborts, and so the next such caller gets
    it for free.
    """
    if TOOLS not in sys.path:
        sys.path.insert(0, TOOLS)
    import entrance_graph  # noqa: E402  (lazy: only this entry point needs it)
    try:
        return entrance_graph.Rom(path)
    except (Exception, SystemExit):
        return None
