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
# Two guards are slower than the rest and opt in separately: the floor-walk
# memo's full-lattice comparison wants a No-Overworld cartridge and several
# minutes, and says so when it skips; the marker sweep walks the seed in play
# and the graded corpus by default, and every cartridge on the machine under the
# same flag.
#
#   FF1_SLOW=1 FF1_ROM=<a GameMode 2 seed> ./tools/tests/run.sh

set -e

HERE=$(cd "$(dirname "$0")" && pwd)
PY=${PYTHON:-python3}

status=0
for t in docs flag_coverage ffr_pin doormap_walk gate_objects memo_walk talk_items sprites font room_floors crop calibration npc_pins noverworld_rules check_logic tofr_diff export_diff toggle_icons pin_visibility overworld_render overworld_pins entrance_pins badge_width door_reach regen_stamp map_values map_names location_maps lane lane_file lane_edit port_lanes lane_cartridges marker_sweep shop_slot incentive_conjunction airboat_siblings regen_branch regen_refresh two_rolls; do
    echo "== $t"
    "$PY" "$HERE/test_$t.py" || status=1
done

if [ "$status" -eq 0 ]; then
    echo "all tool tests passed"
else
    echo "tool tests FAILED" >&2
fi
exit "$status"
