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
#
# One guard is slower than the rest and opts in separately: the floor-walk
# memo's full-lattice comparison wants a No-Overworld cartridge and several
# minutes, and says so when it skips.
#
#   FF1_SLOW=1 FF1_ROM=<a GameMode 2 seed> ./tools/tests/run.sh

set -e

HERE=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3}

status=0
for t in doormap_walk gate_objects memo_walk talk_items sprites font room_floors crop npc_pins noverworld_rules check_logic tofr_diff toggle_icons; do
    echo "== $t"
    "$PY" "$HERE/test_$t.py" || status=1
done

if [ "$status" -eq 0 ]; then
    echo "all tool tests passed"
else
    echo "tool tests FAILED" >&2
fi
exit "$status"
