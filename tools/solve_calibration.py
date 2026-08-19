#!/usr/bin/env python3
"""Propose a tile->pixel calibration for every map image, and say how sure it is.

Two signals, because neither alone is trustworthy:

  1. Where the chest sprites are drawn. Every dungeon has its own palette, so
     the sprite colour is discovered per image rather than assumed: the right
     colour is the one whose compact blobs line up with the ROM's chest tiles
     under a single translation. This proposes candidate offsets.

  2. Whether the image cells at the chest tiles actually look alike. At a
     correct offset every chest tile holds the same sprite, so their colour
     histograms agree; at a wrong one they hold unrelated rock. This is what
     picks between candidates, and it is the part that matters -- blob
     alignment alone confidently produced a wrong answer for iceB3, where five
     stray blobs happened to sit on five chest tiles under one translation.

Output is a proposal, not an answer. Nothing here replaces looking at the
overlay: see tools/overlay_preview.py and the contact sheets.

Usage: tools/solve_calibration.py <img2rom.json> <out.json>
"""

import collections
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pngio  # noqa: E402

TILE = 16
MAX_REGIONS = 3


def rnd(x):
    return int(math.floor(x + 0.5))


def colour_positions(w, rgb, col):
    pat, out = bytes(col), []
    i = rgb.find(pat)
    while i != -1:
        if i % 3 == 0:
            p = i // 3
            out.append((p % w, p // w))
        i = rgb.find(pat, i + 1)
    return out


def blobs(px):
    s, seen, out = set(px), set(), []
    for p in px:
        if p in seen:
            continue
        st, comp = [p], []
        seen.add(p)
        while st:
            cx, cy = st.pop()
            comp.append((cx, cy))
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    q = (cx + dx, cy + dy)
                    if q in s and q not in seen:
                        seen.add(q)
                        st.append(q)
        xs = [c[0] for c in comp]
        ys = [c[1] for c in comp]
        n, bw, bh = len(comp), max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
        if 18 <= n <= 90 and 9 <= bw <= 18 and 6 <= bh <= 15:
            out.append(((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0))
    return out


def cell_hist(w, h, rgb, col, row, ox, oy):
    x0, y0 = ox + col * TILE, oy + row * TILE
    if x0 < 0 or y0 < 0 or x0 + TILE > w or y0 + TILE > h:
        return None
    c = collections.Counter()
    for y in range(y0, y0 + TILE):
        b = (y * w + x0) * 3
        for k in range(0, TILE * 3, 3):
            c[bytes(rgb[b + k:b + k + 3])] += 1
    return c


def hist_sim(a, b):
    return sum((a & b).values()) / float(TILE * TILE)


MIN_SPRITE_PX = 12   # of the candidate colour, inside a 16x16 tile


def explained(w, h, rgb, chests, ox, oy, colour, thresh=0.72):
    """Which chests sit on a tile that both holds the sprite and matches the rest.

    Requiring the sprite colour to actually be present is what stops this
    settling on a patch of uniform rock: blank cells are near-identical to each
    other, so similarity alone scores them beautifully and means nothing.
    """
    hists = {}
    for k, (c, r) in chests.items():
        hh = cell_hist(w, h, rgb, c, r, ox, oy)
        if hh is not None and hh.get(bytes(colour), 0) >= MIN_SPRITE_PX:
            hists[k] = hh
    if len(hists) == 1:
        return list(hists), 1.0
    if not hists:
        return [], 0.0
    best, bestsim = [], 0.0
    for ref in hists:
        grp = [k for k, hh in hists.items() if hist_sim(hists[ref], hh) >= thresh]
        if len(grp) > len(best):
            sims = [hist_sim(hists[ref], hists[k]) for k in grp if k != ref]
            best, bestsim = grp, (sum(sims) / len(sims) if sims else 1.0)
    return best, bestsim


def candidates(w, rgb, hist, chests):
    """Offsets worth scoring, from blob alignment across every plausible colour."""
    seen = set()
    for col, n in hist.items():
        if not (20 <= n <= 9000):
            continue
        bl = blobs(colour_positions(w, rgb, col))
        if not bl:
            continue
        votes = collections.Counter()
        for cx, cy in bl:
            for c, r in chests.values():
                votes[(rnd(cx - (c * TILE + 8)), rnd(cy - (r * TILE + 8)))] += 1
        for off, _ in votes.most_common(6):
            if (off, col) not in seen:
                seen.add((off, col))
                yield off, col


def solve(img, mid, POS):
    chests = {}
    for k, places in POS.items():
        for p in places:
            if p["map_id"] == mid:
                chests[f'{k}:{p["tile_col"]},{p["tile_row"]}'] = (p["tile_col"], p["tile_row"])
    w, h, rgb = pngio.read_rgb(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "images", "maps", f"{img}.png"))
    hist = collections.Counter()
    for i in range(0, len(rgb), 3):
        hist[bytes(rgb[i:i + 3])] += 1

    left, regions = dict(chests), []
    while left and len(regions) < MAX_REGIONS:
        best = None
        single = len(chests) == 1
        for (ox, oy), col in candidates(w, rgb, hist, left):
            grp, sim = explained(w, h, rgb, left, ox, oy, col)
            if len(grp) < (1 if single else 2):
                continue
            key = (len(grp), sim)
            if best is None or key > best[0]:
                best = (key, (ox, oy), grp, sim)
        if best is None:
            break
        (_, off, grp, sim) = best
        regions.append({"offset_x": off[0], "offset_y": off[1],
                        "matched": sorted(grp), "similarity": round(sim, 3)})
        for k in grp:
            left.pop(k, None)
    return chests, regions, sorted(left)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    POS = json.load(open(os.path.join(here, "chest_positions.json")))
    img2rom = json.load(open(sys.argv[1]))
    out = {}
    for img, mid in sorted(img2rom.items()):
        chests, regions, missed = solve(img, mid, POS)
        got = sum(len(r["matched"]) for r in regions)
        out[img] = {"rom_map_id": mid, "chests": len(chests), "matched": got,
                    "regions": regions, "unmatched": missed}
        sims = " ".join(f'({r["offset_x"]},{r["offset_y"]})x{len(r["matched"])}'
                        f'@{r["similarity"]*100:.0f}%' for r in regions)
        mark = "ok " if got == len(chests) else ("~  " if got >= len(chests) * 0.6 else "!! ")
        print(f"  {mark}{img:12s} {got:2d}/{len(chests):2d}  {sims}")
    json.dump(out, open(sys.argv[2], "w"), indent=1)
    full = sum(1 for v in out.values() if v["matched"] == v["chests"])
    print(f"\n{full}/{len(out)} maps fully explained; "
          f"{sum(v['matched'] for v in out.values())}/{sum(v['chests'] for v in out.values())} chests")


if __name__ == "__main__":
    main()
