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
try:
    with open(cache) as f:
        entry = json.load(f).get("modes", {}).get(mode, {})
    npcs = entry.get("npcs", npcs)
    lanes = entry.get("lanes", lanes)
    drawn = entry.get("rom")
except (OSError, ValueError):
    drawn = None

if drawn == sha:
    print(f"current {mode} {npcs} {lanes}")
else:
    why = "no art for this mode yet" if drawn is None else "drawn from another cartridge"
    print(f"redraw {mode} {npcs} {lanes} {why}")
PY
)
    set -- $plan
    verdict=${1:-cannot}
    case $verdict in
        current)
            mode=$2 npcs=$3 lanes=$4
            # The art matches this cartridge, which does not yet mean it
            # matches the checkout: --verify is the one that compares those.
            if out=$("$PY" "$ROOT/tools/regen_maps.py" --verify 2>&1); then
                echo "$mode art was drawn from this cartridge, and is current"
            else
                echo "$out" | head -4
                echo "-> the art is this cartridge's but predates the checkout; redrawing"
                if ! "$PY" "$ROOT/tools/regen_maps.py" "$ROM" --npcs "$npcs" --lanes "$lanes"; then
                    echo "redraw failed -- the tabs will show the shipped art" >&2
                    problems=$((problems + 1))
                fi
            fi
            ;;
        redraw)
            mode=$2 npcs=$3 lanes=$4
            shift 4
            echo "redrawing $mode art from this cartridge -- $*"
            # Not piped into tail: the exit status of a pipeline is the last
            # command's, so gating on it would ask whether tail worked.
            if ! "$PY" "$ROOT/tools/regen_maps.py" "$ROM" --npcs "$npcs" --lanes "$lanes"; then
                echo "redraw failed -- the tabs will show the shipped art" >&2
                problems=$((problems + 1))
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
