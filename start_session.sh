#!/bin/sh
# One command to sit down and play: art, emulator, tracker.
#
#   ./start_session.sh path/to/FFR_seed.nes
#
# Three steps, each of which can be turned off, and each of which says what it
# actually did rather than that it ran:
#
#   1. the map art  -- redrawn from this cartridge when the art on disk was
#                      drawn from a different one, reusing the --npcs and
#                      --lanes that mode was last drawn with
#   2. Mesen        -- the ROM and bridge/ffr_uat_bridge.lua, through
#                      bridge/launch_mesen_ffr.sh
#   3. PopTracker   -- opened, not driven. Clicking UAT and loading the save
#                      are still yours, and the reminder at the end says so
#
# It ends by printing the cartridge's own logic flags. That is the list the
# flag grid should agree with, and a grid that never got the flag record is
# wrong in a scattered enough way -- some cells default on, some default off --
# to read as a handful of unrelated pin bugs instead of one missing record.
#
# macOS only: both launches go through `open -a`. Overrides, all optional:
#
#   MESEN_APP=Mesen            the emulator bundle, if the guess is wrong
#   POPTRACKER_APP=poptracker  the tracker bundle
#   PYTHON=python3
#   FF1_NO_MAPS=1              skip step 1
#   FF1_NO_EMU=1               skip step 2
#   FF1_NO_TRACKER=1           skip step 3
#   FF1_REGEN_ANYWAY=1         redraw even from a branch the art on disk was
#                              not drawn from -- see the guard below

set -u

ROOT=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3}

if [ $# -lt 1 ]; then
    echo "usage: $0 <seed.nes>" >&2
    exit 1
fi

ROM=$1
if [ ! -f "$ROM" ]; then
    echo "no such ROM: $ROM" >&2
    exit 1
fi
case $ROM in
    /*) ;;
    *) ROM=$(cd "$(dirname "$ROM")" && pwd)/$(basename "$ROM") ;;
esac

problems=0
step() { printf '\n=== %s\n' "$1"; }

# An app bundle is named by whoever installed it, and the two emulators this
# has been run against are called different things. Guess, then let the guess
# be overridden, rather than hardcoding one and failing on the other machine.
find_app() {   # find_app <name> [<name>...]
    for name in "$@"; do
        if [ -d "/Applications/$name.app" ] || [ -d "$HOME/Applications/$name.app" ]; then
            echo "$name"
            return 0
        fi
    done
    return 1
}

# Which branch a regen would bake into the override, and whether that is the
# one the art on disk was drawn from.
#
# This matters because the override shadows the pack: PopTracker serves it
# ahead of the checkout, so a redraw does not merely rebuild art -- it rewrites
# the four location trees and `layouts/shared.json` from whatever this working
# tree currently holds, and that is what the session then plays on. Nothing
# about the art on disk says which branch wrote it. A regen from a branch
# without the toggle work once wrote four location trees carrying no pin rules,
# and would have silently dropped the Pins group at the next restart.
#
# regen_maps.py records the branch in its cache, so the comparison is against
# the branch that drew this mode's art last rather than against a list of
# blessed names kept here. Three answers, and only one of them stops anything:
# a match, a mismatch, and "cannot tell" -- no git, a detached head, or art
# drawn before the branch was recorded. "Cannot tell" says so and proceeds; a
# guard that fires on an absence is one people learn to pass with the override,
# which costs more than it saves.
regen_ok() {   # regen_ok <mode> <branch the art was last drawn from, or ->
    _mode=$1 _was=$2
    if [ -n "${FF1_REGEN_ANYWAY:-}" ]; then
        return 0
    fi
    _now=$(git -C "$ROOT" symbolic-ref --quiet --short HEAD 2>/dev/null) || _now=
    if [ -z "$_now" ]; then
        echo "  (cannot tell which branch this checkout is on; redrawing)"
        return 0
    fi
    if [ "$_was" = "-" ]; then
        echo "  (no branch recorded for the $_mode art on disk; redrawing from $_now)"
        return 0
    fi
    if [ "$_now" = "$_was" ]; then
        return 0
    fi
    echo "$_mode art was last drawn from '$_was'; this checkout is on '$_now'" >&2
    echo "-> not redrawing. The override shadows the pack, so this would bake" >&2
    echo "   the location trees and layout on '$_now' into what you play on." >&2
    echo "   Steps 2 and 3 still run, on the art already on disk -- which is" >&2
    echo "   whatever the line above this one says it was drawn for." >&2
    echo "   FF1_REGEN_ANYWAY=1 to redraw anyway." >&2
    problems=$((problems + 1))
    return 1
}

# ----------------------------------------------------------------- 1. the art
step "1/3  map art"
if [ -n "${FF1_NO_MAPS:-}" ]; then
    echo "skipped (FF1_NO_MAPS)"
else
    # Whether the art on disk was drawn from this cartridge, and with what.
    # Both questions are answered from regen_maps.py's own cache and its own
    # mode_of, so there is no second opinion here about which mode a cartridge
    # is or where the override lives.
    plan=$("$PY" - "$ROOT" "$ROM" <<'PY'
import hashlib, json, os, sys

root, rom_path = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.join(root, "tools"))
import regen_maps

with open(rom_path, "rb") as f:
    rom = f.read()
sha = hashlib.sha256(rom).hexdigest()

try:
    mode = regen_maps.mode_of(rom, rom_path)
except SystemExit as e:
    print("cannot " + str(e).replace("\n", " "))
    raise SystemExit(0)

out = regen_maps.default_out()
cache = os.path.join(out, regen_maps.CACHE_NAME)
npcs, lanes = "all", "none"
drawn = None
# "-" rather than an empty field: this line is read back by a positional
# `set --`, where an empty one would shift every field after it. Art drawn
# before the branch was recorded has no branch, which is not a branch named "".
branch = "-"
try:
    with open(cache) as f:
        entry = json.load(f).get("modes", {}).get(mode, {})
    npcs = entry.get("npcs", npcs)
    lanes = entry.get("lanes", lanes)
    drawn = entry.get("rom")
    branch = entry.get("branch") or "-"
except (OSError, ValueError):
    pass

if drawn == sha:
    print(f"current {mode} {npcs} {lanes} {branch}")
else:
    why = "no art for this mode yet" if drawn is None else "drawn from another cartridge"
    print(f"redraw {mode} {npcs} {lanes} {branch} {why}")
PY
)
    # Globbing off: a branch name is one of these fields now, and git allows
    # characters the shell would otherwise expand against the working directory.
    set -f
    set -- $plan
    set +f
    verdict=${1:-cannot}
    case $verdict in
        current)
            mode=$2 npcs=$3 lanes=$4 drawn_branch=$5
            # The art matches this cartridge, which does not yet mean it
            # matches the checkout: --verify is the one that compares those.
            if out=$("$PY" "$ROOT/tools/regen_maps.py" --verify 2>&1); then
                echo "$mode art was drawn from this cartridge, and is current"
            else
                echo "$out" | head -4
                if regen_ok "$mode" "$drawn_branch"; then
                    echo "-> the art is this cartridge's but predates the checkout; redrawing"
                    if ! "$PY" "$ROOT/tools/regen_maps.py" "$ROM" --npcs "$npcs" --lanes "$lanes"; then
                        echo "redraw failed -- the tabs will show the shipped art" >&2
                        problems=$((problems + 1))
                    fi
                fi
            fi
            ;;
        redraw)
            mode=$2 npcs=$3 lanes=$4 drawn_branch=$5
            shift 5
            # Printed before the guard rather than inside it. On the blocked
            # path this line is the whole story, and the reason that usually
            # brings us here is "drawn from another cartridge" -- so a guard
            # message naming only branches would leave the seed mismatch
            # unsaid while steps 2 and 3 open the emulator and the tracker on
            # the other seed's art.
            echo "$mode art needs redrawing -- $*"
            if regen_ok "$mode" "$drawn_branch"; then
                echo "-> redrawing from this cartridge"
                # Not piped into tail: the exit status of a pipeline is the
                # last command's, so gating on it would ask whether tail worked.
                if ! "$PY" "$ROOT/tools/regen_maps.py" "$ROM" --npcs "$npcs" --lanes "$lanes"; then
                    echo "redraw failed -- the tabs will show the shipped art" >&2
                    problems=$((problems + 1))
                fi
            fi
            ;;
        *)
            echo "$plan"
            echo "-> not redrawing. Pass --mode to regen_maps.py by hand if the" >&2
            echo "   tabs matter for this cartridge." >&2
            problems=$((problems + 1))
            ;;
    esac
fi

# -------------------------------------------------------------- 2. the emulator
step "2/3  Mesen"
if [ -n "${FF1_NO_EMU:-}" ]; then
    echo "skipped (FF1_NO_EMU)"
elif APP=${MESEN_APP:-$(find_app Mesen MesenCE)}; [ -n "$APP" ]; then
    echo "opening $APP with the bridge attached"
    if ! "$ROOT/bridge/launch_mesen_ffr.sh" "$ROM" "$APP"; then
        echo "could not open $APP" >&2
        problems=$((problems + 1))
    fi
else
    echo "no Mesen bundle found in /Applications or ~/Applications" >&2
    echo "  set MESEN_APP to its name if it lives elsewhere" >&2
    problems=$((problems + 1))
fi

# --------------------------------------------------------------- 3. the tracker
step "3/3  PopTracker"
if [ -n "${FF1_NO_TRACKER:-}" ]; then
    echo "skipped (FF1_NO_TRACKER)"
elif APP=${POPTRACKER_APP:-$(find_app poptracker PopTracker)}; [ -n "$APP" ]; then
    echo "opening $APP"
    if ! open -a "$APP"; then
        echo "could not open $APP" >&2
        problems=$((problems + 1))
    fi
else
    echo "no PopTracker bundle found in /Applications or ~/Applications" >&2
    echo "  set POPTRACKER_APP to its name if it lives elsewhere" >&2
    problems=$((problems + 1))
fi

# ------------------------------------------------------------------- the flags
step "this cartridge's logic flags"
echo "The flag grid should agree with this list. If it does not, the board"
echo "never got the flag record and is showing the pack's defaults, which are"
echo "on for some of these and off for others."
echo
"$PY" "$ROOT/tools/ffr_flags/decode.py" "$ROM" --logic || problems=$((problems + 1))

step "still yours to do"
echo "  1. click UAT in PopTracker's top bar -- green and Online within ~5s"
echo "  2. load your save; nothing is marked from the title screen"

if [ "$problems" -ne 0 ]; then
    printf '\n%d step(s) had a problem -- see above\n' "$problems"
    exit 1
fi
exit 0
