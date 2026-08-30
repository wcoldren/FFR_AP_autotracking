#!/bin/sh
# The cartridge-reading tools' own tests. Needs Python 3 and nothing else.
#
#   ./tools/tests/run.sh
#
# Tests that read a cartridge skip unless FF1_ROM points at one -- any Final
# Fantasy image will do, since the seed-specific layouts they need are
# synthesised rather than shipped.
#
#   FF1_ROM="$HOME/roms/Final Fantasy (USA).nes" ./tools/tests/run.sh

set -e

HERE=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3}

status=0
for t in doormap_walk gate_objects sprites font room_floors crop; do
    echo "== $t"
    "$PY" "$HERE/test_$t.py" || status=1
done

if [ "$status" -eq 0 ]; then
    echo "all tool tests passed"
else
    echo "tool tests FAILED" >&2
fi
exit "$status"
