#!/bin/sh
# The whole gate, in one command. Nothing is "done" on a successful edit alone.
#
#   ./verify.sh
#
# Four stages, each reporting PASS, FAIL or SKIP. It exits non-zero if any
# stage fails, and zero if some only skipped -- a skip is "this machine cannot
# answer that", not "that passed". The summary says which, so a green run with
# three skips does not read like a green run.
#
#   1. the Lua suites          -- needs a Lua 5.4 interpreter, nothing else
#   2. the Python tool suites  -- stronger with FF1_ROM pointing at a cartridge
#   3. check_logic             -- the access rules against FFR's own, on a
#                                 No-Overworld and a standard cartridge
#   4. the installed override  -- whether the drawn art predates the checkout
#
# A stage skips when this machine cannot answer it: no Lua interpreter, no
# oracle corpus, no cartridges in it, no override installed. So someone who
# installed this as a PopTracker pack sees skips and a green run rather than a
# wall of failures. An override that is installed and stale is an answer rather
# than an absence, and fails. Override any of these to point it elsewhere:
#
#   LUA=lua5.4  PYTHON=python3
#   FF1_ROM=<a cartridge>            strengthens stage 2
#   FF1_CORPUS=<oracle-4.9.2 dir>    stage 3
#   FF1_WORLD=<archipelago>/worlds/ff1
#
# Why check_logic runs on both cartridge kinds: the rules are one set serving
# two modes since the noverworld-logic merge, so a change that satisfies one can
# break the other, and only running both says which.

set -u

ROOT=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3}
CORPUS=${FF1_CORPUS:-$HOME/repos/AP/seeds/ff1/oracle-4.9.2}
WORLD=${FF1_WORLD:-$HOME/repos/AP/vendor/Archipelago/worlds/ff1}

fails=0
skips=0
summary=""

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT INT TERM

record() {   # record <state> <label>
    summary="${summary}
  $1  $2"
    [ "$1" = FAIL ] && fails=$((fails + 1))
    [ "$1" = SKIP ] && skips=$((skips + 1))
    return 0
}

stage() { printf '\n=== %s\n' "$1"; }

# ------------------------------------------------------------------- 1. Lua
stage "1/4  Lua suites"
if ! command -v "${LUA:-lua}" >/dev/null 2>&1; then
    echo "no lua interpreter found (set LUA=/path/to/lua)"
    record SKIP "Lua suites (no interpreter)"
elif "$ROOT/tests/run.sh" >/dev/null 2>&1; then
    record PASS "Lua suites"
else
    "$ROOT/tests/run.sh" 2>&1 | tail -20
    record FAIL "Lua suites"
fi

# ---------------------------------------------------------------- 2. Python
stage "2/4  Python tool suites"
if [ -n "${FF1_ROM:-}" ] && [ ! -f "${FF1_ROM:-}" ]; then
    echo "FF1_ROM is set but names no file: $FF1_ROM"
    record FAIL "Python tool suites"
elif "$ROOT/tools/tests/run.sh" >/dev/null 2>&1; then
    if [ -n "${FF1_ROM:-}" ]; then
        record PASS "Python tool suites (with a cartridge)"
    else
        record PASS "Python tool suites (no FF1_ROM: the cartridge tests skipped)"
    fi
else
    "$ROOT/tools/tests/run.sh" 2>&1 | tail -30
    record FAIL "Python tool suites"
fi

# ------------------------------------------------------------ 3. check_logic
stage "3/4  check_logic, both cartridge kinds"
if [ ! -d "$CORPUS" ]; then
    echo "no oracle corpus at $CORPUS -- set FF1_CORPUS"
    record SKIP "check_logic (no corpus)"
elif [ ! -d "$WORLD" ]; then
    echo "no Archipelago ff1 world at $WORLD -- set FF1_WORLD"
    echo "  without --ff1-world only about 20 checks map and the run reports a"
    echo "  cheerful zero, so this skips rather than running it wrong"
    record SKIP "check_logic (no ff1 world)"
else
    logic_fail=0
    logic_ran=0
    # check_logic exits 1 to *report* a divergence and 0 when it found none, so
    # its exit status cannot gate this stage: `nov` is expected to have exactly
    # one, and a non-zero exit is the normal case there. Piping it into `tail`
    # would have gated on `tail` instead, which is worse. The count is the
    # signal, and it is compared against what the
    # corpus is known to produce. `nov` has one genuine divergence, explained in
    # docs/ROADMAP.md, "Five object gates, twelve items, and one divergence that
    # had been hiding"; `std` has none. A move in either direction is news: a
    # new divergence is a regression, and one going away means something changed
    # that nobody recorded.
    for pair in "nov/oracle_nov 1" "std/oracle_std 0"; do
        set -- $pair
        rel=$1
        want=$2
        rom="$CORPUS/$rel.nes"
        rules="$CORPUS/$rel.yaml"
        name=$(basename "$rel")
        mode=$(dirname "$rel")
        if [ ! -f "$rom" ] || [ ! -f "$rules" ]; then
            echo "  $name: no cartridge or export in the corpus, skipped"
            continue
        fi
        out="$TMP/$name.out"
        derived="$CORPUS/$mode/derived_$mode.json"
        set -- "$rom" --ap-rules "$rules" --ff1-world "$WORLD"
        [ -f "$derived" ] && set -- "$@" --derived "$derived"
        # A run that produced no count at all is the real failure, and that
        # covers a crash and a changed summary line alike.
        "$PY" "$ROOT/tools/check_logic.py" "$@" >"$out" 2>&1
        logic_ran=$((logic_ran + 1))
        got=$(sed -n 's/^\([0-9][0-9]*\) divergences across .*/\1/p' "$out" | tail -1)
        if [ -z "$got" ]; then
            echo "  $name: no divergence count in the output -- check_logic"
            echo "    crashed, or its summary line changed shape. Either way"
            echo "    this stage read nothing and must not report a pass."
            tail -12 "$out"
            logic_fail=1
        elif [ "$got" -ne "$want" ]; then
            echo "  $name: $got divergences, expected $want"
            grep -n "^  --" "$out" | head -20
            logic_fail=1
        else
            echo "  $name: $got divergences, as expected"
        fi
    done
    # Skipping both cartridges used to leave logic_fail at 0 and record a PASS
    # for a stage that read nothing. That is the normal state of a fresh clone:
    # ~/repos/AP/.gitignore has `/seeds/**/*.nes`, so the corpus directory
    # arrives with its exports and none of its cartridges.
    if [ "$logic_fail" -ne 0 ]; then
        record FAIL "check_logic"
    elif [ "$logic_ran" -eq 0 ]; then
        echo "  neither cartridge is in the corpus (.nes files are gitignored)"
        echo "  -- nothing was checked, so this is not a pass"
        record SKIP "check_logic (no cartridges in the corpus)"
    elif [ "$logic_ran" -eq 2 ]; then
        record PASS "check_logic on both cartridge kinds"
    else
        record SKIP "check_logic ($logic_ran of 2 cartridges present)"
    fi
fi

# --------------------------------------------------------------- 4. override
stage "4/4  installed override"
if out=$("$PY" "$ROOT/tools/regen_maps.py" --verify 2>&1); then
    echo "$out" | head -2
    # --verify exits 0 both when the override matches and when there is none
    # to match -- "the pack's own art is what the tracker will serve" is not a
    # comparison this stage made, and must not be summarised as one.
    if echo "$out" | grep -q "^no override installed"; then
        record SKIP "override (none installed)"
    else
        record PASS "override is current with this checkout"
    fi
else
    echo "$out" | head -6
    echo "  (not a code failure: the drawn art predates the checkout. Re-run"
    echo "   regen_maps.py once per mode, reading --npcs and --lanes back out"
    echo "   of .regen_cache.json first -- both default to none.)"
    record FAIL "override is stale"
fi

# ---------------------------------------------------------------- summary
printf '\n=== summary%s\n\n' "$summary"
if [ "$fails" -ne 0 ]; then
    printf '%d stage(s) FAILED\n' "$fails"
    exit 1
fi
if [ "$skips" -ne 0 ]; then
    printf 'all run stages passed, %d skipped -- a skip is not a pass\n' "$skips"
else
    printf 'all four stages passed\n'
fi
exit 0
