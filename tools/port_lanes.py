#!/usr/bin/env python3
"""Carry a hand-drawn lane from the cartridge it was drawn on to another one.

A lane file holds one entry per floor *layout*, keyed by the layout digest, and
`lane_file.pick` draws the entry whose key matches the cartridge in hand. Two
cartridges that lay a floor identically share a digest and so share an entry
for free. Two that lay it differently do not, and the lane has to be carried
across by hand -- which is what this does, for every floor at once.

**Carrying is not authoring, and the distinction is the point of this tool.**
Where the target cartridge lays a floor differently but still walks the drawn
stops, the author's judgement about which chests are worth the detour survives
intact and only the key has to be minted. Where it does not walk, no amount of
copying will help and the floor is an authoring pass in `tools/lane_edit.py`.
This tool sorts the two, writes the first kind, and names the second.

**The lanes are copied verbatim.** Every stop keeps its `kind`, its `at` hint
and its `region`, and the entry keeps its `retrace`. It is tempting to drop the
`at` hints and let `lane.anchors` re-resolve each stop from what it *means* on
the target -- the typed kinds exist precisely so a stop can survive a cartridge
that moved it. Doing that is wrong here and measurably so: with both ends free
to move, a route lane collapses to the cheapest arrival/exit pair the floor
offers, which on 23 of the No-Overworld floors is a shorter walk than the one
that was drawn and on some of them is a single step. The typed kind is the
fallback for when the hint no longer holds; it is not an improvement on a hint
that does.

**A port that walks is a draft, not a finished lane.** It is the drawn route
replayed on a floor whose walls have moved, so it is legal and it may well be
silly -- a corridor that was the short way round on one cartridge can be the
long way on another. Review it in `tools/lane_edit.py` before believing it. The
exception is a floor laid tile-for-tile the same, where the ported lane draws a
byte-identical path and there is nothing to review; those share a digest
already and this tool reports them as needing nothing.

**`--apply` is all of them or none.** Every ported document is built and
validated first, and the writes only happen if all of them pass -- a carry is
one act across a set of floors, and a half-carried tree is a state nothing on
disk explains. Each individual write is atomic already (`lane_file.write`), so
the failure this guards is the run, not the file. A refusal to validate exits
1 and writes nothing; the tally is printed either way, and is the same tally
the dry run prints.

Refusal is `lane.authored`'s, unchanged and deliberately so: the same call
`lane_file.load` makes when the art is drawn. A port this tool accepted and
`regen_maps` then refused would be the one failure worth designing against, so
the acceptance test is the drawing code and not a re-implementation of it.

    tools/port_lanes.py --from <cartridge drawn on> --to <cartridge wanted>
    tools/port_lanes.py --from ... --to ... --apply

Writes nothing without `--apply`.
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import entrance_graph as eg  # noqa: E402
import extract_chests  # noqa: E402
import lane  # noqa: E402
import lane_file  # noqa: E402
import regen_maps  # noqa: E402
import render_maps  # noqa: E402


class Side:
    """One cartridge, and the few derived things a port needs from it."""

    def __init__(self, path):
        self.path = path
        with open(path, "rb") as fh:
            self.rom = fh.read()
        self.graph = eg.Graph(eg.Rom.of(self.rom, path))
        self.chests = extract_chests.extract(self.rom)[0]
        # Once for the cartridge; digest() would otherwise rescan every
        # tileset for all 57 floors.
        self.fixed = render_maps.fixed_formations(self.rom)
        self.stamp = lane_file.stamp(self.rom, path)

    def digest(self, map_id):
        return lane_file.digest(self.rom, map_id, self.fixed)


def port(src, dst, name, map_id):
    """(state, detail, entry) for one map. Writes nothing.

    Five states, and only `ported` produces an entry to write:

      "no file"     nothing was ever authored for this map
      "no source"   authored, but not for the cartridge being ported from
      "have"        the target already draws this floor -- either the two
                    cartridges share the layout, or a port already landed
      "ported"      the drawn stops walk on the target; `entry` is the new one
      "refused"     they do not, and `detail` says which stop gave out
    """
    doc = lane_file.read(name)
    if doc is None:
        return "no file", None, None
    src_dig, dst_dig = src.digest(map_id), dst.digest(map_id)
    if lane_file.pick(doc, dst_dig) is not None:
        return "have", dst_dig, None
    was = lane_file.pick(doc, src_dig)
    if was is None:
        return "no source", src_dig, None

    # Everything the source entry says travels, and only the key is minted.
    # Copying a listed set of keys instead was narrower than "verbatim" claims
    # and silently so: it dropped `note`, which `lane_edit` writes and which is
    # the author's own word about the drawing, and it would drop the next key
    # the format grows without anything failing. `retrace` rides along here for
    # the reason it would have been listed for -- whether a loop is worth
    # collapsing is a judgement about the drawing, and the drawing is what is
    # being carried; a floor that loops on one cartridge and not the other is
    # exactly the case the key is per-layout for, so review can still change it.
    entry = dict(was)
    entry["digest"] = dst_dig
    entry["seen"] = [dst.stamp]
    try:
        lane.authored(dst.rom, dst.graph, map_id, entry, dst.chests,
                      retrace=lane_file.wants_retrace(entry))
    except ValueError as e:
        return "refused", str(e), None
    return "ported", dst_dig, entry


def main():
    ap = argparse.ArgumentParser(
        description="Carry every hand-drawn lane from one cartridge's layouts "
                    "to another's, where the drawn stops still walk.")
    ap.add_argument("--from", dest="src", required=True, metavar="ROM",
                    help="the cartridge the lanes were drawn on")
    ap.add_argument("--to", dest="dst", required=True, metavar="ROM",
                    help="the cartridge to carry them to")
    ap.add_argument("--apply", action="store_true",
                    help="write the ported entries into tools/lanes/. Without "
                         "this, nothing is written and the tally is a "
                         "measurement")
    args = ap.parse_args()

    src, dst = Side(args.src), Side(args.dst)
    # Both stamps have to be readable before anything is walked. `seen` is the
    # only record on disk of which cartridge a lane was carried to, so an
    # unreadable one writes 32 entries that say nothing about where they came
    # from -- and the same-cartridge refusal below cannot be made out of two
    # "unknown"s, which is what `cartridge_id` yields for any image whose
    # FFRInfo block does not parse. Two such images used to compare equal here
    # and report as the same cartridge.
    for flag, side in (("--from", src), ("--to", dst)):
        if side.stamp == regen_maps.STAMP_UNKNOWN:
            print(f"{flag} {os.path.basename(side.path)} carries no readable "
                  "FFRInfo record, so there is nothing to name in `seen` and "
                  "no way to tell it apart from the other side")
            return 2
    if src.stamp == dst.stamp:
        print("both --from and --to are the same cartridge; nothing to port")
        return 2

    tally = {}
    refused, ported = [], []
    for map_id, name in sorted(render_maps.MAP_FILES.items(),
                               key=lambda kv: kv[1]):
        state, detail, entry = port(src, dst, name, map_id)
        tally[state] = tally.get(state, 0) + 1
        if state == "refused":
            refused.append((name, detail))
        elif state == "ported":
            ported.append((name, entry))

    # Every document is built and validated before a byte of any of them is
    # written, and they are written only if all of them pass. Validating inside
    # the loop above meant a floor that failed at 20 of 32 left nineteen files
    # carried, thirteen not, and nothing in the tree saying which run they came
    # from; a carry is one act across a set of floors and should land or not
    # land. It also counted the failure as written -- `ported` was appended to
    # before the check -- so a run that wrote 31 of 32 reported 32 and exited 0.
    docs, invalid = [], []
    for name, entry in ported:
        doc = lane_file.read(name)
        doc["layouts"] = list(doc.get("layouts", ())) + [entry]
        # Against the document as `write` will store it rather than as it was
        # read; see lane_file.normalize for the one field that differs and why
        # checking the wrong one reports a fault the write does not have.
        doc = lane_file.normalize(doc)
        why = lane_file.validate(doc)
        if why:
            invalid.append((name, why))
        docs.append((name, doc))

    print(f"from {os.path.basename(src.path)}  ({src.stamp.split('|')[1]})")
    print(f"to   {os.path.basename(dst.path)}  ({dst.stamp.split('|')[1]})")
    for state in ("have", "ported", "refused", "no source", "no file"):
        if tally.get(state):
            print(f"  {tally[state]:3d}  {state}")

    if ported:
        print(f"\nported ({len(ported)}), and each is a draft to review in "
              "tools/lane_edit.py:")
        for name, _ in ported:
            print(f"  {name}")
    if refused:
        print(f"\nrefused ({len(refused)}), and each is an authoring pass "
              "rather than a copy:")
        for name, why in refused:
            print(f"  {name}: {why}")

    if invalid:
        print(f"\nnothing was written: {len(invalid)} ported document(s) do "
              "not validate, and the carry is all of them or none:")
        for name, why in invalid:
            print(f"  {name}: {'; '.join(why)}")
        return 1

    if ported and not args.apply:
        print("\nnothing was written. Re-run with --apply to keep the ports.")
    elif ported:
        for name, doc in docs:
            lane_file.write(name, doc)
        print(f"\nwrote {len(docs)} file(s). Re-run regen_maps.py for the "
              "mode this cartridge draws.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
