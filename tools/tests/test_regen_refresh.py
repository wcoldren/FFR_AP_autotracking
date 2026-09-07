#!/usr/bin/env python3
"""Which modes count as stale, and what `--refresh` refuses to redraw.

`--verify` names a stale override and `--refresh` acts on the same answer, so
the answer is computed once, in `stale_modes`. The first part here holds that
function to the three comparisons it stands for -- and to the one it must not
make, because a mode drawn `--lanes none` has no stake in a lane file and
redrawing it on every authoring edit is the reason the lane digest is compared
per mode rather than folded into `INPUT_FILES`.

The second part is about refusals. A refresh reads its arguments out of the
cache instead of from a person, which is the whole point of it and also the
risk: the recorded cartridge can have moved, been replaced by another seed at
the same path, or never have been recorded at all, and the checkout can be on a
branch the art was not drawn on. Each of those is reported and skipped with a
non-zero exit rather than guessed at, because a stale override that reports
itself refreshed is worse than one that reports itself stale. A guard that
cannot be seen to fire is not a guard, so each is exercised on a cache built to
trip exactly it.

The third is the `--mode` filter, whose risk runs the other way. Every check
above is about refusing to redraw; this one is about reporting success over a
mode it deliberately never looked at, which is the one exit-0 path that leaves
the override stale on purpose.

Needs no cartridge, no PopTracker and no override: every directory it asks
about is one it just made in a temp dir. The fake cartridges are deliberately
not iNES images, so a guard that stopped working cannot reach a real render.
"""

import contextlib
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)

import regen_maps as r              # noqa: E402

fails = []


def ok(cond, label, got=""):
    print(f"{'ok  ' if cond else 'FAIL'} {label:66} {got}")
    if not cond:
        fails.append(label)


def cache_for(modes, outputs=None):
    return {"version": r.CACHE_VERSION, "inputs": r.inputs_fingerprint(),
            "modes": modes, "outputs": outputs or {}}


def write_override(tmp, cache):
    with open(os.path.join(tmp, r.CACHE_NAME), "w") as f:
        json.dump(cache, f)
    return tmp


def entry(**over):
    """A mode entry that is current in every respect, before `over` spoils it."""
    was = {"rom": "0" * 64, "rom_path": "/nowhere/none.nes", "npcs": "all",
           "lanes": "none", "retrace": "auto", "marker": [14, 2],
           "inputs": r.inputs_fingerprint(), "lane_files": r.lane_files_sha(),
           "head": "0000000", "branch": r.checkout_id().get("branch")}
    was.update(over)
    return was


def refresh(out_dir, only=None):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = r.refresh(out_dir, False, only)
    return rc, buf.getvalue()


# --- 1. which modes stale_modes names -------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    write_override(tmp, cache_for({"std": entry(), "nov": entry()}))
    worn, outputs_ok = r.stale_modes(tmp, cache_for(
        {"std": entry(), "nov": entry()}))
    ok(worn == {} and outputs_ok, "a cache that matches the checkout is stale "
                                  "in no respect", str(worn))

    worn, _ = r.stale_modes(tmp, cache_for({"std": entry(inputs="stale"),
                                            "nov": entry()}))
    ok(worn == {"std": [r.STALE_INPUTS]},
       "a mode whose INPUT_FILES hash moved is named, and only it", str(worn))

    # The comparison that must not fire. A mode drawn without lanes has no
    # stake in tools/lanes/, and naming it here would redraw its art on every
    # authoring edit -- which is why the digest is per mode in the first place.
    worn, _ = r.stale_modes(tmp, cache_for(
        {"std": entry(lanes="authored", lane_files="stale"),
         "nov": entry(lanes="none", lane_files="stale")}))
    ok(worn == {"std": [r.STALE_LANES]},
       "a lane edit names the mode that drew authored lanes", str(worn))

with tempfile.TemporaryDirectory() as tmp:
    # An output file that no longer holds the bytes the run wrote. It cannot be
    # attributed to a mode, so every mode is named.
    with open(os.path.join(tmp, "drawn.png"), "wb") as f:
        f.write(b"not what was written")
    write_override(tmp, cache_for({"std": entry(), "nov": entry()},
                                  {"drawn.png": "0" * 64}))
    cache = json.load(open(os.path.join(tmp, r.CACHE_NAME)))
    worn, outputs_ok = r.stale_modes(tmp, cache)
    ok(not outputs_ok and sorted(worn) == ["nov", "std"]
       and worn["std"] == [r.STALE_OUTPUTS],
       "a changed output file names every mode, and says so separately",
       str(worn))

    # The edge the second half of the return exists for: nothing to name, and
    # still not current. Read through the mode map alone this reads as clean.
    worn, outputs_ok = r.stale_modes(tmp, cache_for({}, {"drawn.png": "0" * 64}))
    ok(worn == {} and not outputs_ok,
       "damaged files with no mode to blame still report as damaged")


# --- 2. what refresh refuses ----------------------------------------------

with tempfile.TemporaryDirectory() as tmp:
    rc, out = refresh(os.path.join(tmp, "nothing-here"))
    ok(rc == 0 and "nothing to refresh" in out,
       "no override installed is not a failure")

with tempfile.TemporaryDirectory() as tmp:
    write_override(tmp, cache_for({"std": entry()}))
    rc, out = refresh(tmp)
    ok(rc == 0 and "already current" in out,
       "an override that matches the checkout is left alone")

with tempfile.TemporaryDirectory() as tmp:
    was = entry(inputs="stale")
    del was["rom_path"]
    write_override(tmp, cache_for({"std": was}))
    rc, out = refresh(tmp)
    ok(rc == 1 and "before this tool recorded" in out,
       "a mode drawn before the path was recorded is skipped, not guessed at")

with tempfile.TemporaryDirectory() as tmp:
    write_override(tmp, cache_for(
        {"std": entry(inputs="stale", rom_path=os.path.join(tmp, "gone.nes"))}))
    rc, out = refresh(tmp)
    ok(rc == 1 and "That is where this art was drawn from" in out,
       "a cartridge that has moved is skipped")

with tempfile.TemporaryDirectory() as tmp:
    rom = os.path.join(tmp, "other-seed.nes")
    with open(rom, "wb") as f:
        f.write(b"a different seed at the same path")
    write_override(tmp, cache_for({"std": entry(inputs="stale",
                                                rom_path=rom)}))
    rc, out = refresh(tmp)
    ok(rc == 1 and "no longer the cartridge" in out,
       "the hash outranks the path when a seed directory is reused")

# --- 3. what --mode narrows -----------------------------------------------
#
# The filter exists so start_session.sh can redraw the mode of the cartridge
# being sat down with and not the other one. What it must never do is turn a
# half-refreshed override into a clean exit: the mode it skipped is still
# stale, and the only place that can say so is the run that decided to skip it.

with tempfile.TemporaryDirectory() as tmp:
    write_override(tmp, cache_for({"std": entry(), "nov": entry()}))
    rc, out = refresh(tmp, "nov")
    ok(rc == 0 and "No-Overworld art is already current" in out,
       "--mode reports on the mode it was given, not on the tree")

with tempfile.TemporaryDirectory() as tmp:
    write_override(tmp, cache_for({"std": entry(inputs="stale")}))
    rc, out = refresh(tmp, "nov")
    ok(rc == 1 and "no No-Overworld art has been drawn" in out,
       "a mode this override never drew is an unanswerable request, not a pass")

with tempfile.TemporaryDirectory() as tmp:
    # Both stale, one asked for. The one left behind has to be named: this is
    # the only exit-0 path that knowingly leaves the override stale, and a
    # silent one would be found later by --verify with nothing to explain it.
    was = entry(inputs="stale")
    del was["rom_path"]
    write_override(tmp, cache_for({"std": was, "nov": entry(inputs="stale")}))
    rc, out = refresh(tmp, "std")
    ok("also stale, and left alone" in out and "No-Overworld" in out,
       "the mode left out of a filtered refresh is named")
    ok(rc == 1 and "before this tool recorded" in out
       and "seed.nes" not in out,
       "and only the named mode is acted on", str(rc))


here = r.checkout_id().get("branch")
if not here:
    print("SKIP: this checkout has no branch, so the branch guard cannot fire")
else:
    with tempfile.TemporaryDirectory() as tmp:
        rom = os.path.join(tmp, "seed.nes")
        body = b"the cartridge this art really was drawn from"
        with open(rom, "wb") as f:
            f.write(body)
        was = entry(inputs="stale", rom_path=rom, rom=r.sha(body),
                    branch=here + "-not")
        write_override(tmp, cache_for({"std": was}))
        anyway = os.environ.pop("FF1_REGEN_ANYWAY", None)
        try:
            rc, out = refresh(tmp)
            ok(rc == r.REFUSED and "not redrawing" in out and here in out,
               "art drawn on another branch is not redrawn onto this one",
               str(rc))
            # The escape hatch has to work, or the guard is a wall. It gets as
            # far as the render, which the fake cartridge then refuses -- that
            # it got there at all is the thing being checked.
            os.environ["FF1_REGEN_ANYWAY"] = "1"
            rc, out = refresh(tmp)
            ok(rc == 1 and "not redrawing" not in out,
               "and FF1_REGEN_ANYWAY=1 gets past the guard", str(rc))
        finally:
            os.environ.pop("FF1_REGEN_ANYWAY", None)
            if anyway is not None:
                os.environ["FF1_REGEN_ANYWAY"] = anyway


# The exit status has to stay 1 when the guard was not the whole story. A run
# that also failed to find a cartridge is not "you are on the wrong branch", and
# a caller that switched branches on the strength of a 3 would come back to the
# same failure with nothing explained.
if here:
    with tempfile.TemporaryDirectory() as tmp:
        rom = os.path.join(tmp, "seed.nes")
        body = b"the cartridge this art really was drawn from"
        with open(rom, "wb") as f:
            f.write(body)
        gone = entry(inputs="stale", rom_path=os.path.join(tmp, "gone.nes"))
        blocked = entry(inputs="stale", rom_path=rom, rom=r.sha(body),
                        branch=here + "-not")
        write_override(tmp, cache_for({"std": blocked, "nov": gone}))
        anyway = os.environ.pop("FF1_REGEN_ANYWAY", None)
        try:
            rc, out = refresh(tmp)
            ok(rc == 1 and "not redrawing" in out
               and "That is where this art was drawn from" in out,
               "a refusal alongside a real failure exits 1, not 3", str(rc))
        finally:
            if anyway is not None:
                os.environ["FF1_REGEN_ANYWAY"] = anyway


print()
if fails:
    print(f"{len(fails)} FAILED")
    for f in fails:
        print("  " + f)
    raise SystemExit(1)
print("all regen-refresh guards passed")
