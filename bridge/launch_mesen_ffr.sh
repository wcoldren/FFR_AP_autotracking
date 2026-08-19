#!/bin/sh
# Launch MesenCE with an FFR seed and the autotracking bridge attached.
#
#   ./launch_mesen_ffr.sh /path/to/seed.nes
#
# Mesen matches a bare argument that exists on disk and ends in .lua as a
# script, and anything else that exists as a ROM. Scripts are opened once the
# ROM has loaded, and run on their own because "Auto-start script when a game
# is loaded" defaults to on.
#
# One-time setup, in Mesen: Script -> Settings -> Script Window ->
# Restrictions. Tick "Allow access to I/O and OS functions" first, then
# "Allow network access".

set -e

if [ $# -lt 1 ]; then
    echo "usage: $0 <seed.nes> [app-name]" >&2
    exit 1
fi

ROM=$1
APP=${2:-MesenCE}
BRIDGE=$(cd "$(dirname "$0")" && pwd)/ffr_uat_bridge.lua

if [ ! -f "$ROM" ]; then
    echo "no such ROM: $ROM" >&2
    exit 1
fi

# Mesen resolves relative paths against its own working directory, so pass
# both as absolute.
case $ROM in
    /*) ;;
    *) ROM=$(cd "$(dirname "$ROM")" && pwd)/$(basename "$ROM") ;;
esac

exec open -a "$APP" --args "$ROM" "$BRIDGE"
