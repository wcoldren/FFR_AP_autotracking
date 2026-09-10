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


def search_roots():
    """The directories to walk, deduplicated and with no root inside another.

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
