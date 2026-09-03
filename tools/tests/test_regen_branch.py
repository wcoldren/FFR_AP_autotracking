#!/usr/bin/env python3
"""The branch a regen bakes into the override, recorded and then guarded.

The override shadows the pack, so a regen does not merely redraw art -- it
rewrites the four location trees and `layouts/shared.json` from whatever the
working tree holds, and that is what the next session plays on. A regen from a
branch without the toggle work once wrote four location trees carrying no pin
rules. The cache's `inputs` hash notices that the pack changed and cannot
notice that the change was a step backwards, because a hash is the same size
either way.

Two halves, and they fail differently, so they are checked separately:

  1. `regen_maps.checkout_id()` records the branch. Its hard cases are the ones
     that have to stay apart: a detached head has no branch but does have a
     commit, and a checkout with no git has neither -- and reading either as a
     match is how a guard passes the run it was written to stop.
  2. `start_session.sh`'s `regen_ok` compares. The guard is sliced out of the
     shipped file rather than restated here, so a rewrite of the message text
     is fine and a rewrite of the predicate is not.

Needs git and nothing else -- no cartridge, no override, no PopTracker. Every
repository it asks about is one it just made in a temp dir.
"""

import os
import re
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
# Sliced out of start_session.sh rather than restated, so this tests the shipped
# predicate. If the slice stops finding the function that is a failure too: it
# means the guard was renamed or reshaped and nothing here is covering it.

src = open(os.path.join(PACK, "start_session.sh")).read()
m = re.search(r"^regen_ok\(\) \{.*?^\}$", src, re.S | re.M)
ok(m is not None, "regen_ok is still a top-level function in start_session.sh")
guard = m.group(0) if m else ""


def run_guard(root, was, env=None):
    """-> (exit status, stdout+stderr, the `problems` counter afterwards)."""
    script = (
        "set -u\n"
        f'ROOT="{root}"\n'
        "problems=0\n"
        f"{guard}\n"
        f'if regen_ok std "{was}"; then echo WOULD-REDRAW; else echo SKIPPED; fi\n'
        'echo "problems=$problems"\n'
    )
    done = subprocess.run(("sh", "-c", script), capture_output=True, text=True,
                          env={**os.environ, **(env or {})})
    out = done.stdout + done.stderr
    n = re.search(r"problems=(\d+)", out)
    return done.returncode, out, int(n.group(1)) if n else -1


if guard:
    with tempfile.TemporaryDirectory() as tmp:
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
        _, out, n = run_guard(repo, "titan-cell")
        ok("SKIPPED" in out and n == 1,
           "a branch mismatch skips the redraw and counts a problem",
           out.strip().splitlines()[0] if out.strip() else "")
        ok("titan-cell" in out and "trunk" in out,
           "-- and names both branches, so the message says which way round")

        # The same call on the matching branch is the before half of that
        # demonstration: nothing about the cartridge or the cache changed.
        _, out, n = run_guard(repo, "trunk")
        ok("WOULD-REDRAW" in out and n == 0,
           "the same call on the matching branch redraws and counts nothing")

        _, out, n = run_guard(repo, "titan-cell", {"FF1_REGEN_ANYWAY": "1"})
        ok("WOULD-REDRAW" in out and n == 0,
           "FF1_REGEN_ANYWAY redraws through a mismatch")

        # The two "cannot tell" states proceed, and say so. A guard that fired
        # on an absence is one people learn to pass with the override.
        _, out, n = run_guard(repo, "-")
        ok("WOULD-REDRAW" in out and n == 0 and "no branch recorded" in out,
           "art with no branch recorded redraws, and says that is why")

        head = git(repo, "rev-parse", "HEAD").stdout.strip()
        git(repo, "checkout", "-q", head)
        _, out, n = run_guard(repo, "trunk")
        ok("WOULD-REDRAW" in out and n == 0 and "cannot tell" in out,
           "a detached head redraws, and says it could not tell")

        plain = os.path.join(tmp, "notarepo")
        os.mkdir(plain)
        _, out, n = run_guard(plain, "trunk")
        ok("WOULD-REDRAW" in out and n == 0 and "cannot tell" in out,
           "so does a checkout with no repository at all")


print()
if fails:
    print(f"{len(fails)} FAILED")
    for f in fails:
        print("  " + f)
    raise SystemExit(1)
print("all regen-branch guards passed")
