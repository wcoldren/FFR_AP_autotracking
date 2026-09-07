#!/usr/bin/env python3
"""The branch a regen bakes into the override, recorded and then guarded.

The override shadows the pack, so a regen does not merely redraw art -- it
rewrites the four location trees and `layouts/shared.json` from whatever the
working tree holds, and that is what the next session plays on. A regen from a
branch without the toggle work once wrote four location trees carrying no pin
rules. The cache's `inputs` hash notices that the pack changed and cannot
notice that the change was a step backwards, because a hash is the same size
either way.

Four parts, and they fail differently, so they are checked separately:

  1. `regen_maps.checkout_id()` records the branch. Its hard cases are the ones
     that have to stay apart: a detached head has no branch but does have a
     commit, and a checkout with no git has neither -- and reading either as a
     match is how a guard passes the run it was written to stop.
  2. `regen_maps.branch_block()` compares. Part 2 used to test a second copy of
     this comparison, written in shell in `start_session.sh`; the cases came
     here when that copy went, because they were always cases about the rule
     rather than about the language it was spelled in.
  3. `main` asks it before it draws. A predicate that is right and runs after
     the write is not a guard, so its position is checked separately from its
     answer, on the path that actually rewrites the location trees.
  4. There is still only one copy. Two guards that agree pass every check the
     first three make, and disagreeing is the failure that actually happened.

Needs git and nothing else -- no cartridge, no override, no PopTracker. Every
repository it asks about is one it just made in a temp dir, and the one
cartridge-shaped file is a synthetic image no render could survive.
"""

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)

import regen_maps as r              # noqa: E402

fails = []


def ok(cond, label, got=""):
    print(f"{'ok  ' if cond else 'FAIL'} {label:66} {got}")
    if not cond:
        fails.append(label)


def git(cwd, *args):
    return subprocess.run(("git", "-C", cwd) + args,
                          capture_output=True, text=True)


def have_git():
    try:
        return subprocess.run(("git", "--version"),
                              capture_output=True).returncode == 0
    except OSError:
        return False


if not have_git():
    print("SKIP: no git on this machine, and both halves ask git a question")
    raise SystemExit(0)


# --- 1. what checkout_id records -----------------------------------------
#
# checkout_id reads regen_maps.PACK, which is fixed at import. Repointing it is
# the whole of the fixture: everything else it does is a git call.

def checkout_id_in(path):
    was = r.PACK
    r.PACK = path
    try:
        return r.checkout_id()
    finally:
        r.PACK = was


with tempfile.TemporaryDirectory() as tmp:
    # git looks for a repository by walking upward, so a TMPDIR that itself
    # sits inside a checkout -- a common CI layout -- would let the "no
    # repository" fixtures below answer with the enclosing repo instead of
    # with nothing. The ceiling stops that walk at the fixture root. Realpath
    # because git compares physical paths and on macOS the temp dir arrives
    # through a symlink.
    os.environ["GIT_CEILING_DIRECTORIES"] = os.path.realpath(tmp)
    repo = os.path.join(tmp, "repo")
    os.mkdir(repo)
    git(repo, "init", "-q", "-b", "trunk")
    git(repo, "config", "user.email", "t@example.invalid")
    git(repo, "config", "user.name", "t")
    # One of INPUT_FILES, so the dirty check has something real to look at.
    tracked = os.path.join(repo, "layouts")
    os.mkdir(tracked)
    with open(os.path.join(tracked, "shared.json"), "w") as f:
        f.write("{}\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "first")

    ident = checkout_id_in(repo)
    ok(ident.get("branch") == "trunk",
       "a checkout on a branch records that branch", ident.get("branch"))
    ok(ident.get("dirty") is False,
       "a clean input set records dirty False", ident.get("dirty"))
    ok(isinstance(ident.get("head"), str) and len(ident.get("head", "")) >= 7,
       "the commit is recorded beside it", ident.get("head"))

    # Dirty is scoped to INPUT_FILES, which is the set inputs_fingerprint
    # hashes. An edit anywhere else moves no drawn byte, and reporting it would
    # teach this record's reader to ignore it.
    with open(os.path.join(repo, "NOTES.md"), "w") as f:
        f.write("a note\n")
    ok(checkout_id_in(repo).get("dirty") is False,
       "an edit outside INPUT_FILES does not read as dirty")

    with open(os.path.join(tracked, "shared.json"), "w") as f:
        f.write('{"changed": true}\n')
    ok(checkout_id_in(repo).get("dirty") is True,
       "an edit to an INPUT_FILES path does read as dirty")

    # One probe failing must not spend another probe's answer. `dirty` is
    # provenance and nothing compares it; `branch` is the only field the guard
    # reads. Gating the whole record on `git status` would switch the guard off
    # for this mode and then report it as art too old to have a branch -- a
    # guard turning itself off while blaming something else.
    class _StatusFails:
        SubprocessError = subprocess.SubprocessError

        @staticmethod
        def run(cmd, **kw):
            if "status" in cmd:
                raise OSError("git status cannot run here")
            return subprocess.run(cmd, **kw)

    was_sp = r.subprocess
    r.subprocess = _StatusFails
    try:
        degraded = checkout_id_in(repo)
    finally:
        r.subprocess = was_sp
    ok(degraded.get("branch") == "trunk",
       "a failing git status still records the branch the guard reads",
       degraded)
    ok("dirty" not in degraded,
       "-- and drops only the field whose own probe failed")

    git(repo, "checkout", "-q", "--", "layouts/shared.json")
    head = git(repo, "rev-parse", "HEAD").stdout.strip()
    git(repo, "checkout", "-q", head)
    detached = checkout_id_in(repo)
    ok("branch" not in detached,
       "a detached head records no branch at all", detached)
    ok(detached.get("head"),
       "-- but still records the commit, so the two states stay apart",
       detached.get("head"))

    plain = os.path.join(tmp, "notarepo")
    os.mkdir(plain)
    ok(checkout_id_in(plain) == {},
       "a directory that is no repository records nothing",
       checkout_id_in(plain))


# --- 2. what the guard does with it ---------------------------------------
#
# `regen_maps.branch_block` is the comparison itself, and is now the only copy
# of it: start_session.sh used to carry a second one in shell. Each case below
# was a case that guard was written to answer, and they moved here with it.
#
# checkout_id reads `PACK`, so pointing that at a fixture repository is how a
# case gets a branch to be on. FF1_REGEN_ANYWAY is scrubbed for the same reason
# the shell version scrubbed it: the developer most likely to have it exported
# is the one who just hit the guard, and inheriting it turns every mismatch
# check in here green.

anyway = os.environ.pop("FF1_REGEN_ANYWAY", None)


def block_in(root, drawn_on):
    """-> branch_block's answer with the pack rooted at `root`."""
    was_pack = r.PACK
    r.PACK = root
    try:
        return r.branch_block({"branch": drawn_on} if drawn_on else {})
    finally:
        r.PACK = was_pack


try:
    with tempfile.TemporaryDirectory() as tmp:
        # git looks for a repository by walking upward, so a TMPDIR that itself
        # sits inside a checkout -- a common CI layout -- would let the "no
        # repository" fixtures below answer with the enclosing repo instead of
        # with nothing. The ceiling stops that walk at the fixture root.
        # Realpath because git compares physical paths and on macOS the temp dir
        # arrives through a symlink.
        os.environ["GIT_CEILING_DIRECTORIES"] = os.path.realpath(tmp)
        repo = os.path.join(tmp, "repo")
        os.mkdir(repo)
        git(repo, "init", "-q", "-b", "trunk")
        git(repo, "config", "user.email", "t@example.invalid")
        git(repo, "config", "user.name", "t")
        with open(os.path.join(repo, "f"), "w") as f:
            f.write("x\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", "first")

        # The demonstration this guard was added for: the art on disk was drawn
        # from one branch, the checkout is standing on another, and the regen
        # does not happen.
        said = block_in(repo, "titan-cell")
        ok(said is not None, "a branch mismatch is blocked", str(said))
        ok(said is not None and "titan-cell" in said and "trunk" in said,
           "-- and names both branches, so the message says which way round")

        # The before half of that demonstration: nothing but the branch differs.
        ok(block_in(repo, "trunk") is None,
           "the same art on the matching branch is not blocked")

        os.environ["FF1_REGEN_ANYWAY"] = "1"
        ok(block_in(repo, "titan-cell") is None,
           "FF1_REGEN_ANYWAY gets through a mismatch")
        del os.environ["FF1_REGEN_ANYWAY"]

        # The three "cannot tell" states proceed. A guard that fired on an
        # absence is one people learn to pass with the override, which costs
        # more than it saves.
        ok(block_in(repo, None) is None,
           "art with no branch recorded is not blocked")

        head = git(repo, "rev-parse", "HEAD").stdout.strip()
        git(repo, "checkout", "-q", head)
        ok(block_in(repo, "trunk") is None, "nor is a detached head")

        plain = os.path.join(tmp, "notarepo")
        os.mkdir(plain)
        ok(block_in(plain, "trunk") is None,
           "nor a checkout with no repository at all")
finally:
    if anyway is not None:
        os.environ["FF1_REGEN_ANYWAY"] = anyway


# --- 3. and that the drawing path asks it ---------------------------------
#
# The two checks above hold the predicate; this one holds its position. A guard
# that is correct and sits after the write is not a guard, and the path that
# rewrites the location trees is `main`'s, not `refresh`'s -- start_session.sh's
# redraw case goes straight down it with a cartridge the override has not seen.
#
# The cartridge is a synthetic image: big enough that cartridge_id can read the
# tables it looks for, and empty enough that no render could survive it. That is
# deliberate. Reaching a real render here would mean the guard let it past.

here = r.checkout_id().get("branch")
if not here:
    print("SKIP: this checkout has no branch, so the guard cannot be shown to "
          "fire")
else:
    with tempfile.TemporaryDirectory() as tmp:
        rom = os.path.join(tmp, "fake.nes")
        with open(rom, "wb") as f:
            f.write(b"NES\x1a" + bytes([32, 0, 0, 0]) + bytes(8)
                    + b"\x00" * (32 * 16384))
        out = os.path.join(tmp, "override")
        os.mkdir(out)
        with open(os.path.join(out, r.CACHE_NAME), "w") as f:
            json.dump({"version": r.CACHE_VERSION,
                       "inputs": r.inputs_fingerprint(),
                       "modes": {"std": {"rom": "0" * 64, "rom_path": rom,
                                         "npcs": "all", "lanes": "none",
                                         "retrace": "auto", "marker": [14, 2],
                                         "inputs": "stale",
                                         "branch": here + "-not"}},
                       "outputs": {}}, f)

        def draw(env=None):
            base = {k: v for k, v in os.environ.items()
                    if k != "FF1_REGEN_ANYWAY"}
            done = subprocess.run(
                (sys.executable, os.path.join(TOOLS, "regen_maps.py"), rom,
                 "--mode", "std", "--out", out),
                capture_output=True, text=True, env={**base, **(env or {})})
            return done.returncode, done.stdout + done.stderr

        rc, out_text = draw()
        ok(rc == r.REFUSED and "not redrawing" in out_text,
           "a redraw from the wrong branch stops before it draws", str(rc))
        ok("cartridge changed since the last run" in out_text,
           "-- and still says why the redraw was wanted, which is the reason "
           "that brought us here")

        # The other half: the same call gets past the guard and on to the
        # render, which this cartridge then refuses. That it got that far is
        # the thing being shown -- without it the check above passes on a
        # command that was never going to draw anyway.
        rc, out_text = draw({"FF1_REGEN_ANYWAY": "1"})
        ok(rc != r.REFUSED and "not redrawing" not in out_text,
           "and FF1_REGEN_ANYWAY=1 gets it to the render", str(rc))


# --- 4. and that there is still only one copy ------------------------------
#
# The drift this collapse undid was not a wrong guard, it was a second one:
# start_session.sh grew its own branch comparison in shell three days before
# --refresh copied it into Python, and two guards that had to agree is why
# "should the guard exist at all" could not be answered anywhere. Nothing above
# would notice it happening again -- both copies would pass their own checks --
# so the count is what gets asserted.

session = open(os.path.join(PACK, "start_session.sh")).read()
ok("symbolic-ref" not in session and "regen_ok" not in session,
   "start_session.sh makes no branch comparison of its own")
ok('--refresh --mode "$mode"' in session,
   "-- it delegates the mode it is about to play to --refresh")

print()
if fails:
    print(f"{len(fails)} FAILED")
    for f in fails:
        print("  " + f)
    raise SystemExit(1)
print("all regen-branch guards passed")
