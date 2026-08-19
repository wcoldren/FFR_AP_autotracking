#!/bin/sh
# Offline test suite. Needs nothing but a Lua 5.4+ interpreter -- no emulator,
# no ROM, no PopTracker. The emulator and tracker APIs are stubbed, but the
# scripts under test are the real ones.
#
#   ./tests/run.sh

set -e

ROOT=$(cd "$(dirname "$0")/.." && pwd)
LUA=${LUA:-lua}

if ! command -v "$LUA" >/dev/null 2>&1; then
    echo "no lua interpreter found (set LUA=/path/to/lua)" >&2
    exit 1
fi

status=0
for t in reconcile uat mapping bridge bridge_flow e2e; do
    echo "== $t"
    if ! "$LUA" "$ROOT/tests/test_$t.lua" "$ROOT"; then
        status=1
    fi
    echo
done

if [ $status -eq 0 ]; then
    echo "all suites passed"
else
    echo "FAILURES" >&2
fi
exit $status
