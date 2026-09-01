"""Where the FFR C# checkout is, and what the workspace pins it to.

Two tests need this and nothing in the pack resolved it before. The pack is a
PopTracker pack first: somebody who installed it has no FFR checkout and no
workspace, so every accessor here returns None rather than raising, and the
callers skip. A missing checkout is not a failure; a checkout that disagrees
with the schema is.

The workspace has its own resolver (`tools/vendor_paths.py`, which reads
`pins.yaml`), and this file deliberately does not import it. Reaching two
directories up into a repo that may not be there, to import a module that may
not be there, to find a checkout that lives at a predictable path anyway, buys
nothing. The layout is `vendor/ff1/FFR_AP_autotracking` beside
`vendor/ff1/FF1Randomizer-<nnn>`, which is what `pins.yaml`'s own `dest:` keys
say; when that stops being true the env override is the answer.
"""
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.abspath(os.path.join(HERE, ".."))

# The FFR versions the pack ships a flag schema for. The suffix is what the
# worktree directory is named for and what the env override is keyed by.
VERSIONS = {
    "4-9-2": "492",
    "4-9-7": "497",
}

# The pins.yaml block that claims each worktree, so a pin can be looked up from
# a schema version. `pins.yaml` calls a block a vendored clone precisely when it
# carries a `dest:`, and both of these do.
PIN_BLOCKS = {
    "4-9-2": "ff1_randomizer_492",
    "4-9-7": "ff1_randomizer_497",
}


def checkout(version):
    """The FF1Randomizer checkout for an FFR version, or None if it is not here.

    `FF1_SRC_497` / `FF1_SRC_492` override; otherwise the sibling worktree.
    """
    suffix = VERSIONS.get(version)
    if suffix is None:
        return None
    env = os.environ.get("FF1_SRC_" + suffix)
    path = env or os.path.join(os.path.dirname(PACK), "FF1Randomizer-" + suffix)
    path = os.path.abspath(os.path.expanduser(path))
    return path if os.path.isdir(os.path.join(path, "FF1Lib")) else None


def skip_reason(version):
    """Why a caller would skip, phrased for a human, or None if it need not."""
    if checkout(version) is not None:
        return None
    return ("no FFR %s checkout -- set FF1_SRC_%s to one, or run "
            "`python bootstrap.py audit` in the workspace"
            % (version, VERSIONS.get(version, "???")))


# ------------------------------------------------------------------ pins.yaml

def pins_file():
    """The workspace's pins.yaml, or None outside the workspace."""
    path = os.environ.get("AP_PINS")
    if not path:
        # vendor/ff1/FFR_AP_autotracking -> the repo root is three up.
        path = os.path.join(PACK, "..", "..", "..", "pins.yaml")
    path = os.path.abspath(os.path.expanduser(path))
    return path if os.path.isfile(path) else None


# pins.yaml is YAML and PyYAML is not a dependency -- the tool tests run on
# "Python 3 and nothing else". These two keys are plain scalars two spaces in
# under a top-level block, so they are read with a scan rather than a parser.
# A scan that guesses would be worse than no check at all, so it is deliberately
# narrow: it tracks the enclosing top-level block by column and reads only
# `dest:` and `pinned_commit:`, and returns None for anything it does not
# recognise instead of falling back to a looser match.
_BLOCK = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(?:#.*)?$")
_SCALAR = re.compile(r'^\s+(dest|pinned_commit):\s*"?([^"#\s]+)"?')


def pin_block(name, path=None):
    """`{dest, pinned_commit}` for one pins.yaml block, or None."""
    path = path or pins_file()
    if path is None:
        return None
    out, here = None, None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            m = _BLOCK.match(line)
            if m:
                here = m.group(1)
                if here == name:
                    out = {}
                elif out is not None:
                    break                      # the block ended; stop reading
                continue
            if out is None or here != name:
                continue
            m = _SCALAR.match(line)
            if m:
                out[m.group(1)] = m.group(2)
    return out or None


def pinned_commit(version):
    """The commit pins.yaml pins an FFR version's worktree to, or None."""
    block = PIN_BLOCKS.get(version)
    if block is None:
        return None
    found = pin_block(block)
    return (found or {}).get("pinned_commit")


# ------------------------------------------------------------------ git

def is_ancestor(path, commit):
    """Is `commit` an ancestor of `path`'s HEAD?

    Ancestry rather than equality, because both oracle worktrees sit two local
    commits above their pin -- the FF1R export commit and the FFRVersion stamp,
    neither of which is upstream. Comparing HEADs fails on a tree that is right.
    """
    proc = subprocess.run(["git", "-C", path, "merge-base",
                           "--is-ancestor", commit, "HEAD"],
                          capture_output=True, text=True)
    return proc.returncode == 0


def stamped_sha(path):
    """The SHA hardcoded into FFRVersion.cs on a checkout, or None.

    FFR substitutes `Sha` during its own deploy and leaves the literal "SHA" in
    source, so a local build has to stamp it by hand or the flag decoder refuses
    the cartridge. On the oracle worktrees that stamp is the pinned commit, which
    is what ties a ROM to a schema.
    """
    src = os.path.join(path, "FF1Lib", "FFRVersion.cs")
    if not os.path.isfile(src):
        return None
    with open(src, encoding="utf-8", errors="replace") as handle:
        m = re.search(r'\bSha\s*=\s*"([^"]+)"', handle.read())
    if not m or m.group(1) == "SHA":
        return None
    return m.group(1)
