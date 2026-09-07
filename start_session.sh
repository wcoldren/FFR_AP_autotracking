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
#                              not drawn from. The guard is regen_maps.py's,
#                              not this script's: every path that draws asks
#                              it, so it is the same answer whether the redraw
#                              is asked for here or by hand

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

# regen_maps.py's REFUSED. The number is the whole interface between that guard
# and this script, so it is named on both sides rather than read as a bare 3.
REGEN_REFUSED=3

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

# Run a regen and say which way it came out. This script makes no judgement
# about whether the redraw should happen: regen_maps.py refuses a checkout that
# is not the one the art was drawn from, on every path that draws, and this used
# to be a second copy of that comparison written in shell. Two guards that had
# to agree is why "should the guard exist" could not be answered in one place.
#
# What is left here is the reporting, and the one thing it must not do is call
# a refusal a failure. They ask for different things -- a branch to switch to,
# or a bug to chase -- and exit 3 is how the tool tells them apart. Either way
# step 1 is the only step affected: steps 2 and 3 still open the emulator and
# the tracker on the art already on disk.
#
# Split from `regen` so a caller with a second thing to try can look at the
# status before any of this is said. Counting a problem is part of reporting,
# so a redraw that is about to be attempted another way must not come through
# here first: two lines about one failed step, and a non-zero exit for a
# session whose art came out current.
regen_report() {   # regen_report <status>
    if [ "$1" -eq 0 ]; then
        return 0
    fi
    if [ "$1" -eq "$REGEN_REFUSED" ]; then
        echo "-> steps 2 and 3 still run, on the art already on disk -- which" >&2
        echo "   is whatever the message above says it was drawn for." >&2
    else
        echo "redraw failed -- the tabs will show the shipped art" >&2
    fi
    problems=$((problems + 1))
    return 1
}

regen() {   # regen <command...>
    "$@"
    regen_report $?
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
npcs, lanes, retrace = "all", "authored", "on"
drawn = None
try:
    with open(cache) as f:
        entry = json.load(f).get("modes", {}).get(mode, {})
    npcs = entry.get("npcs", npcs)
    lanes = entry.get("lanes", lanes)
    drawn = entry.get("rom")
    # Through retrace_slot, because a slot written before the setting went
    # per-layout holds a JSON bool and this field is about to be printed into a
    # plan line and handed back as `--retrace`, where True is not a choice
    # argparse offers. Only when the key is there: absent, the default above is
    # this script's own intent and not the slot's.
    if "retrace" in entry:
        retrace = regen_maps.retrace_slot(entry)
except (OSError, ValueError):
    pass

if drawn == sha:
    print(f"current {mode} {npcs} {lanes} {retrace}")
else:
    why = "no art for this mode yet" if drawn is None else "drawn from another cartridge"
    print(f"redraw {mode} {npcs} {lanes} {retrace} {why}")
PY
)
    # Globbing off while this is split. Every field is drawn from a fixed
    # vocabulary today and none of them could expand against the working
    # directory, which is a property of the fields rather than a promise, and
    # cheaper to keep than to re-establish.
    set -f
    set -- $plan
    set +f
    verdict=${1:-cannot}
    case $verdict in
        current)
            mode=$2 npcs=$3 lanes=$4 retrace=$5
            # The art matches this cartridge, which does not yet mean it
            # matches the checkout: --verify is the one that compares those.
            if out=$("$PY" "$ROOT/tools/regen_maps.py" --verify 2>&1); then
                echo "$mode art was drawn from this cartridge, and is current"
            else
                echo "$out" | head -4
                # Not "redrawing": --verify reports on the whole override, so
                # it can fail over the mode this cartridge is not. --refresh
                # answers for the one named and says "already current" when
                # that is the truth, where the old full render spent six
                # seconds proving the same thing.
                echo "-> this cartridge's art is installed, but the override"
                echo "   predates the checkout somewhere"
                # --refresh, not a fresh render: this is the case it exists for,
                # and it reads the cartridge and the drawing settings back out
                # of the cache rather than being handed them from here. --mode
                # because the other mode's art is a redraw nobody asked for, at
                # the moment they are least willing to wait for one.
                "$PY" "$ROOT/tools/regen_maps.py" --refresh --mode "$mode"
                rc=$?
                # A refresh reopens the cartridge at the path the cache
                # recorded, while the verdict above was reached on the
                # cartridge's bytes. Those two disagree whenever the seed has
                # moved since it was drawn, and then what the failure asks for
                # -- one run on the cartridge whose sha256 starts so-and-so --
                # is the file already named on this command line. So hand it
                # that one before calling anything a failure. Everything else
                # --refresh gives up on wants the same run, for the same
                # reason: it declines to guess, and here there is nothing left
                # to guess about.
                #
                # Not on a refusal. Exit 3 is an answer about the checkout, and
                # a full render is the same draw from the same working tree --
                # it would be asking the guard the same question a second time
                # and drawing on the answer it already refused.
                if [ "$rc" -ne 0 ] && [ "$rc" -ne "$REGEN_REFUSED" ]; then
                    echo "-> the cache could not redraw that mode on its own;"
                    echo "   redrawing from the cartridge named here instead"
                    regen "$PY" "$ROOT/tools/regen_maps.py" "$ROM" \
                        --npcs "$npcs" --lanes "$lanes" --retrace "$retrace"
                else
                    regen_report "$rc"
                fi
            fi
            ;;
        redraw)
            mode=$2 npcs=$3 lanes=$4 retrace=$5
            shift 5
            # Printed before the tool runs, because on a refused path the
            # reason is the whole story: what usually brings us here is "drawn
            # from another cartridge", and a refusal naming only branches would
            # leave that unsaid while steps 2 and 3 open the emulator and the
            # tracker on the other seed's art.
            echo "$mode art needs redrawing -- $*"
            echo "-> asking regen_maps.py to redraw from this cartridge"
            # Not piped into tail: the exit status of a pipeline is the last
            # command's, so gating on it would ask whether tail worked. This is
            # the path --refresh cannot take -- it names no cartridge by design,
            # and this case is exactly a new one.
            regen "$PY" "$ROOT/tools/regen_maps.py" "$ROM" --npcs "$npcs" --lanes "$lanes" --retrace "$retrace"
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
