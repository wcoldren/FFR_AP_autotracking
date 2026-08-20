#!/usr/bin/env python3
"""Check the pack's access rules against FFR's own logic for a seed.

    python3 tools/check_logic.py                       # every ROM it can find
    python3 tools/check_logic.py path/to/seed.nes
    python3 tools/check_logic.py --output-dir "~/Library/Application Support/Archipelago/output"

The pack's access_rules are a hand-written approximation of FFR's reachability.
FFR computes the real thing per seed, with that seed's flags applied, and writes
it down in two places:

  * the FFR spoiler .txt that comes with every seed, whose first table gives the
    requirement expression for each key item's location;
  * the `rules:` dict in an Archipelago yaml or spoiler, which is the same thing
    for every location that made it into the multiworld pool.

Either way it arrives as an or-of-ands over item names. This lines those up
against the pack's rules for the same place, with the seed's flags pinned from
the cartridge, and compares them as truth tables over the items they mention.
It reports both directions: a rule that opens a location FFR would not (a false
green, the dangerous kind) and one that holds a location closed FFR would open.

What it cannot map, it says so about. A quiet "no divergences" over half the
locations would be worse than useless.
"""

import argparse
import ast
import glob
import itertools
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACK = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "ffr_flags"))
import ffr_flags  # noqa: E402

LOCATION_FILES = ["locations/overworld.json", "locations/incentives.json"]

# FFR's item vocabulary against the pack's codes.
#
# Floater is the one that is not a rename. FFR's Floater is the item in your
# bag; flying also takes reaching the Ryukahn Desert to raise the airship, and
# FFR writes that out as extra terms in the requirement -- which is why its
# Cardia rules say "Canoe AND Floater" for islands only an airship can land on.
# The pack's airship code means the thing is already in the air, because that is
# what cart RAM reports. So Floater maps to the pack's floater, and airship is
# derived below from the pack's own rule for reaching the desert.
FFR_ITEMS = {
    "Ship": "ship", "Canal": "canal", "Canoe": "canoe", "Floater": "floater",
    "Bridge": "bridge", "Ruby": "ruby", "Key": "key", "Crown": "crown",
    "Crystal": "crystal", "Herb": "herb", "Tnt": "tnt", "Adamant": "adamant",
    "Slab": "slab", "Bottle": "bottle", "Chime": "chime", "Cube": "cube",
    "Oxyale": "oxyale", "Rod": "rod", "Lute": "lute", "Tail": "tail",
    "Shard": "shards",
}

# Vehicles and items FFR can hand you at the start. Its own logic stops
# mentioning them once they are free, and the pack picks them up from cart RAM
# rather than from a flag, so the harness has to pin them by hand or every rule
# that names one reads as too strict.
FREE_FLAGS = {
    "FreeBridge": ["bridge"], "FreeShip": ["ship"], "FreeCanal": ["canal"],
    "FreeCanoe": ["canoe"], "FreeAirship": ["floater", "airship"],
    "FreeLute": ["lute"], "FreeRod": ["rod"], "FreeTail": ["tail"],
}

# Places the pack is deliberately stricter than FFR, with the reason. FFR folds
# a step into an item when that step can always be taken; the pack shows the
# step, because a tracker is read while the step is still outstanding.
#
# Keyed by section path and direction. Waived findings are still printed -- a
# check that quietly disappears is a check nobody looks at again.
WAIVED = {
    ("Gaia Area/Lefein/Incentive", "strict"):
        "the pack wants the Slab translated by Dr Unne, not just carried; FFR"
        " counts holding it, because Unne is reachable whenever Lefein is",
    ("Inner Sea/Coneria Castle/Sara", "strict"):
        "the pack wants Garland beaten before the princess is back; FFR folds"
        " that in, because Garland is beatable from the start",
}

# FFR spoiler "Source" column against the pack's hosted-item codes. This is the
# hand-written part: FFR names the NPC or the chest, the pack names the thing
# the section hosts. Sources with no entry here are reported as unmapped rather
# than skipped.
FFR_SOURCES = {
    "King": "king", "Princess2": "sara", "Bikke": "bikke", "Nerrick": "nerrick",
    "Smith": "smith", "Astos": "astos", "Sarda": "sarda", "CanoeSage": "sages",
    "Matoya": "matoya", "ElfPrince": "elfprince", "Fairy": "fairy",
    "Lefein": "lefein", "CubeBot": "robot",
    "MarshCaveMajor": "marsh", "ConeriaMajor": "coneriaLocked",
    "IceCaveMajor": "iceCave", "OrdealsMajor": "ordeals",
    "EarthCaveMajor": "earth", "SeaShrineMajor": "sea", "SkyPalaceMajor": "sky",
    "TitanChest": "titansTrove",
}


# ----------------------------------------------------------------- pack rules

def load_pack_rules(pack=PACK):
    """{section path: [rule list, ...]} -- the chain of access_rules that has to
    hold, outermost first. A location's rules gate everything under it, so a
    section is reachable when every list in its chain is satisfied."""
    sections = {}

    def walk(nodes, path, chain):
        for node in nodes:
            name = node.get("name")
            if name is None:
                continue
            here = path + [name]
            rules = node.get("access_rules") or []
            sub = chain + [rules] if rules else chain
            for section in node.get("sections", []):
                if "ref" in section:
                    continue        # a pointer to a section defined elsewhere
                sname = section.get("name")
                if sname is None:
                    continue
                srules = section.get("access_rules") or []
                key = "/".join(here + [sname])
                sections[key] = {
                    "chain": sub + [srules] if srules else sub,
                    "hosted": section.get("hosted_item"),
                }
            walk(node.get("children", []), here, sub)

    for rel in LOCATION_FILES:
        with open(os.path.join(pack, rel)) as handle:
            walk(json.load(handle), [], [])
    return sections


def find_section(sections, path):
    """PopTracker location refs are written as suffixes of the full path."""
    if path in sections:
        return path
    want = "/" + path
    hits = [k for k in sections if k.endswith(want)]
    if len(hits) == 1:
        return hits[0]
    return None


def find_hosted(sections, code, incentive):
    """The section that hosts a code. The same code is hosted twice -- once in
    the dungeon tree and once as an incentive pin -- and the two carry different
    rules, so which file it came from matters."""
    hits = [k for k in sections
            if sections[k]["hosted"] == code and k.startswith("I: ") == incentive]
    return hits[0] if len(hits) == 1 else None


AIRSHIP_SECTION = "Ryukahn Desert/Floater Turn In"


def airship_chain(sections):
    """What it takes to reach the desert and raise the airship, as the pack has
    it. Everything above the Floater Turn In section, but not the section's own
    rule -- that one is "you are holding the floater", which is the other half
    of the condition and is applied separately."""
    path = find_section(sections, AIRSHIP_SECTION)
    if path is None:
        raise SystemExit("cannot find %r -- the airship rule moved" % AIRSHIP_SECTION)
    return sections[path]["chain"][:-1]


def with_airship(provided, raise_chain):
    """The pack codes a player would have, given the items they are holding."""
    if "floater" in provided and satisfied(raise_chain, provided):
        return provided | {"airship"}
    return provided


def satisfied(chain, provided):
    for rules in chain:
        if not rules:
            continue
        if not any(all(term in provided for term in alt.split(","))
                   for alt in rules):
            return False
    return True


def chain_codes(chain):
    """Every code a chain mentions, `$func` calls included."""
    out = set()
    for rules in chain:
        for alt in rules:
            for term in alt.split(","):
                out.add(term.strip())
    return out


# --------------------------------------------------------------- seed's flags

def flag_codes(flags, pack=PACK):
    """The flag codes the pack would be showing for a decoded seed.

    The mapping is read out of scripts/autotracking/flag_mapping.lua rather than
    written out again here, so the harness and the pack cannot drift apart on
    which FFR flag is which."""
    src = open(os.path.join(pack, "scripts/autotracking/flag_mapping.lua")).read()
    pairs = re.findall(r'\{\s*ffr\s*=\s*"([^"]+)"\s*,\s*code\s*=\s*"([^"]+)"', src)
    if not pairs:
        raise SystemExit("could not read the flag mapping out of flag_mapping.lua")

    codes = set()
    for ffr, code in pairs:
        if flags.get(ffr) is True:
            codes.add(code)

    # The progressives, whose stages are spelled out in the same file but as
    # Lua rather than as a table this can read.
    if flags.get("MapOpenProgression") is True:
        codes.add("progressionFlag")
        codes.add("openProgression")
        if flags.get("MapOpenProgressionExtended") is True:
            codes.add("extendedOpen")
    if flags.get("AirBoat") is True:
        codes.add("airBoat")
    if flags.get("IncentivizeCardia") is True:
        codes.add("cardiaIsIncentive")
    if flags.get("MapDragonsHoard") is True:
        codes.update(("cardiaIsIncentive", "BahamutHoard"))

    for flag, granted in FREE_FLAGS.items():
        if flags.get(flag) is True:
            codes.update(granted)
    return codes


# ------------------------------------------------------------- ground truth

REQ_SPLIT = re.compile(r"\s+OR\s+")


def parse_requirement(text):
    """"(A AND B) OR (C)" -> [["A","B"],["C"]]. "()" is no requirement."""
    text = text.strip()
    if text in ("", "()"):
        return [[]]
    out = []
    for clause in REQ_SPLIT.split(text):
        clause = clause.strip().strip("()").strip()
        if not clause:
            out.append([])
            continue
        out.append([t.strip() for t in clause.split(" AND ") if t.strip()])
    return out


def parse_ffr_spoiler(path):
    """The key-item table at the top of an FFR spoiler."""
    rows = []
    with open(path, errors="replace") as handle:
        for line in handle:
            if line.startswith("Name ") or line.startswith("---"):
                if rows:
                    break
                continue
            m = re.match(r"^(\S+)\s+(\S+) -> (\S+) -> (\S+)\s+(.*?)\s*$", line)
            if m:
                rows.append({
                    "item": m.group(1), "entrance": m.group(2),
                    "floor": m.group(3), "source": m.group(4),
                    "rules": parse_requirement(m.group(5)),
                })
    return rows


def item_requirements(rows):
    """{pack code: or-of-ands} for the key items, out of the same table.

    This is what makes the comparison mean anything. Quantifying over every
    combination of vehicles would flag rules that only look too permissive:
    the pack lets the airship alone reach Crescent Lake, and FFR's expression
    does not mention the airship at all -- but in a seed where raising the
    airship needs the canoe, "airship without canoe" is a state no player can
    be in, so the two rules never actually disagree.
    """
    reqs = {}
    for row in rows:
        code = FFR_ITEMS.get(row["item"])
        if code is None:
            continue
        clauses = [[FFR_ITEMS[i] for i in clause if i in FFR_ITEMS]
                   for clause in row["rules"]]
        reqs.setdefault(code, []).extend(clauses)
    return reqs


def achievable(held, vocabulary, reqs):
    """Could a player be holding exactly `held` out of `vocabulary`?

    Everything outside the vocabulary is taken as soon as it is reachable --
    there is no reason to leave it -- so this is "collect everything, except
    the vocabulary items you have not got to yet".
    """
    if not reqs:
        return True
    have = set()
    while True:
        grew = False
        for code, clauses in reqs.items():
            if code in have:
                continue
            if code in vocabulary and code not in held:
                continue
            if any(all(i in have for i in clause) for clause in clauses):
                have.add(code)
                grew = True
        if not grew:
            return held <= have


def ap_item_requirements(path, rules):
    """Where the progression items landed in an Archipelago seed.

    An AP seed's FFR spoiler cannot say: FFR fills every pooled location with a
    placeholder and lets Archipelago decide, so its Item column is the same name
    over and over. The AP spoiler's Locations section has the real placements,
    and `rules:` has what it takes to reach each one."""
    text = open(path, errors="replace").read()
    m = re.search(r"^Locations:\s*$", text, re.M)
    if not m:
        return {}
    reqs = {}
    for line in text[m.end():].split("\n"):
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")) and line.rstrip().endswith(":"):
            break                       # next section
        if ": " not in line:
            continue
        where, item = line.rsplit(": ", 1)
        code = FFR_ITEMS.get(item.strip())
        if code is None or where.strip() not in rules:
            continue
        clauses = [[FFR_ITEMS[i] for i in clause if i in FFR_ITEMS]
                   for clause in rules[where.strip()]]
        reqs.setdefault(code, []).extend(clauses)
    return reqs


def parse_bracket_dict(body):
    """`Name: [["A"],["B"]], Other Name: [[]]` -> {name: or-of-ands}.

    Archipelago prints these as a Python dict with the braces and the key quotes
    stripped, which literal_eval will not take, and the keys have commas and
    colons in them (`Marsh Cave Bottom (B2) - Tetris-Z Incentive`). Scanning for
    the brackets is more robust than trying to split it."""
    import ast
    out = {}
    i, n = 0, len(body)
    while i < n:
        j = body.find(": [", i)
        if j < 0:
            break
        key = body[i:j].strip().lstrip(",").strip().strip("'\"")
        k, depth = j + 2, 0
        while k < n:
            if body[k] == "[":
                depth += 1
            elif body[k] == "]":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        try:
            out[key] = ast.literal_eval(body[j + 2:k + 1])
        except (ValueError, SyntaxError):
            pass
        i = k + 1
    return out


def parse_ap_rules(path):
    """The `rules:` mapping out of an Archipelago yaml or spoiler.

    This is FFR's own logic for every location that went into the pool, computed
    with this seed's flags and handed to Archipelago verbatim -- worlds/ff1 has
    no rules of its own, it just evaluates what it was given."""
    text = open(path, errors="replace").read()
    m = re.search(r'^\s*"?rules"?:\s*(.*)$', text, re.M)
    if not m:
        return {}
    body = m.group(1).strip()
    if body in ("", "{}"):
        return {}
    return parse_bracket_dict(body.lstrip("{").rstrip("}"))


def ap_location_paths(pack=PACK, ff1=None):
    """AP location name -> pack section path, via the world's id table and the
    pack's own LOCATION_MAPPING. Nothing hand-written in between."""
    if ff1 is None:
        ff1 = os.path.join(pack, "..", "Archipelago", "worlds", "ff1")
    names = os.path.join(ff1, "data", "locations.json")
    if not os.path.exists(names):
        return {}
    with open(names) as handle:
        name_to_id = json.load(handle)
    src = open(os.path.join(pack, "scripts/autotracking/location_mapping.lua")).read()
    id_to_path = {}
    for m in re.finditer(r'\[(\d+)\]\s*=\s*\{"@([^"]+)"', src):
        id_to_path[int(m.group(1))] = m.group(2)
    return {name: id_to_path[i] for name, i in name_to_id.items() if i in id_to_path}


# ------------------------------------------------------------------ compare

def compare(chain, truth, pinned, reqs=None, raise_chain=()):
    """Truth-table both expressions over the items they mention.

    Returns (verdict, witness) where verdict is "match", "permissive",
    "strict" or "both", and witness is an item set they disagree on.
    """
    items = set()
    for clause in truth:
        for name in clause:
            if name in FFR_ITEMS:
                items.add(FFR_ITEMS[name])
    for code in chain_codes(chain):
        if code in FFR_ITEMS.values():
            items.add(code)
        elif code == "airship":
            items.add("floater")   # it is floater plus reaching the desert
    items = sorted(items)

    reverse = {v: k for k, v in FFR_ITEMS.items()}
    vocabulary = set(items)
    permissive, strict = None, None
    for bits in itertools.product((False, True), repeat=len(items)):
        held = {c for c, on in zip(items, bits) if on}
        if not achievable(held, vocabulary, reqs):
            continue
        provided = with_airship(pinned | held, raise_chain)
        pack_ok = satisfied(chain, provided)
        ffr_ok = any(all(FFR_ITEMS.get(n, n) in held for n in clause)
                     for clause in truth)
        if pack_ok and not ffr_ok and permissive is None:
            permissive = sorted(reverse.get(c, c) for c in held)
        if ffr_ok and not pack_ok and strict is None:
            strict = sorted(reverse.get(c, c) for c in held)

    # `is not None` rather than truthiness: the witness for a rule that opens
    # with nothing at all is the empty set, and that is the worst case, not a
    # missing one.
    if permissive is not None and strict is not None:
        return "both", (permissive, strict)
    if permissive is not None:
        return "permissive", permissive
    if strict is not None:
        return "strict", strict
    return "match", None


def show_rules(truth):
    return " OR ".join("(" + " AND ".join(c) + ")" if c else "()" for c in truth)


def show_chain(chain):
    return " AND ".join("[" + " | ".join(r) + "]" for r in chain) or "[always]"


# --------------------------------------------------------------------- main

def check_seed(rom_path, sections, ap_paths, players_dir=None, verbose=False):
    with open(rom_path, "rb") as handle:
        rom = handle.read()
    try:
        info, flags = ffr_flags.decode_rom(rom)
    except ffr_flags.DecodeError as err:
        print("  cannot read this ROM: %s" % err)
        return 0, 0
    pinned = flag_codes(flags)
    raise_chain = airship_chain(sections)

    spoiler = os.path.join(os.path.dirname(rom_path),
                           "Spoiler_%s_%s.txt" % (info["Seed"],
                                                  os.path.basename(rom_path).split("_")[-1][:-4]))
    checks = []
    reqs = {}

    if os.path.exists(spoiler):
        rows = parse_ffr_spoiler(spoiler)
        reqs = item_requirements(rows)
        for row in rows:
            code = FFR_SOURCES.get(row["source"])
            if code is None:
                checks.append((row["source"], None, row["rules"], "no pack section known"))
                continue
            path = find_hosted(sections, code, incentive=False)
            if path is None:
                checks.append((row["source"], None, row["rules"],
                               "no section hosts %r" % code))
                continue
            checks.append((row["source"], path, row["rules"], None))
    else:
        print("  no FFR spoiler next to the ROM (%s)" % os.path.basename(spoiler))

    here = os.path.dirname(rom_path)
    ap_files = (sorted(glob.glob(os.path.join(here, "*.yaml")))
                + sorted(glob.glob(os.path.join(here, "*_Spoiler.txt"))))
    # The yaml FFR hands you for an Archipelago run keeps the seed in its name
    # and normally lives in Players/, not next to the ROM.
    if players_dir:
        ap_files += sorted(glob.glob(os.path.join(os.path.expanduser(players_dir),
                                                  "**", "*%s*.yaml" % info["Seed"]),
                                     recursive=True))
    for ap_file in ap_files:
        ap_rules = parse_ap_rules(ap_file)
        if not ap_rules:
            continue
        found = ap_item_requirements(ap_file, ap_rules)
        if found:
            reqs = found
        for name, rules in ap_rules.items():
            path = ap_paths.get(name)
            if path is None:
                checks.append((name, None, rules, "not in LOCATION_MAPPING"))
                continue
            full = find_section(sections, path)
            if full is None:
                checks.append((name, None, rules, "path %r is not in the pack" % path))
                continue
            checks.append((name, full, rules, None))

    # Without knowing where the vehicles were placed, every combination of them
    # has to be treated as reachable, and rules that only look too permissive --
    # the airship without the canoe, in a seed where you cannot raise the
    # airship without one -- come out as divergences. Say so, and do not let
    # those decide whether this run passes.
    missing = [v for v in ("ship", "canal", "canoe", "floater")
               if v not in reqs and v not in pinned]
    trustworthy = not missing
    if missing:
        print("  where %s were placed is not recorded for this seed, so what"
              " follows over-reports and is not counted" % ", ".join(missing))

    # Grouped, because one wrong rule on a dungeon shows up once per chest
    # under it and a hundred identical lines hide how few problems there are.
    groups, order, witnesses, waived = {}, [], {}, {}
    unmapped, agree = 0, 0
    for label, path, truth, why in checks:
        if why:
            unmapped += 1
            if verbose:
                print("  --   %-40s %s" % (label, why))
            continue
        chain = sections[path]["chain"]
        verdict, witness = compare(chain, truth, pinned, reqs, raise_chain)
        if verdict == "match":
            agree += 1
            if verbose:
                print("  ok   %-40s %s" % (label, show_rules(truth)))
            continue
        reason = WAIVED.get((path, verdict))
        if reason:
            waived.setdefault(reason, []).append(label)
            continue
        key = (show_rules(truth), show_chain(chain), verdict)
        if key not in groups:
            groups[key] = []
            witnesses[key] = witness
            order.append(key)
        groups[key].append((label, path))

    for key in order:
        truth_s, chain_s, verdict = key
        where = groups[key]
        label, path = where[0]
        more = "" if len(where) == 1 else "  (and %d more like it)" % (len(where) - 1)
        print("  ****  %s%s" % (label, more))
        print("        FFR:  %s" % truth_s)
        print("        pack: %s" % chain_s)
        witness = witnesses[key]
        if verdict in ("permissive", "both"):
            got = witness[0] if verdict == "both" else witness
            print("        pack opens it with %s; FFR does not" % (", ".join(got) or "nothing"))
        if verdict in ("strict", "both"):
            got = witness[1] if verdict == "both" else witness
            print("        FFR opens it with %s; pack does not" % (", ".join(got) or "nothing"))
        for _, where_path in where:
            print("        at    %s" % where_path)

    for reason, where in waived.items():
        print("  --    %s%s" % (where[0], "" if len(where) == 1
                                else " (and %d more)" % (len(where) - 1)))
        print("        waived: %s" % reason)

    print("  %d checked, %d agree, %d distinct divergences over %d locations,"
          " %d could not be mapped%s"
          % (agree + sum(len(g) for g in groups.values())
             + sum(len(w) for w in waived.values()),
             agree + sum(len(w) for w in waived.values()), len(groups),
             sum(len(g) for g in groups.values()), unmapped,
             "" if trustworthy else " -- NOT COUNTED"))
    return (len(groups) if trustworthy else 0), unmapped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom", nargs="*", help="FFR ROMs; default is every one found")
    ap.add_argument("--output-dir",
                    default="~/Library/Application Support/Archipelago/output",
                    help="where to look for ROMs and spoilers")
    ap.add_argument("--players-dir",
                    default="~/Library/Application Support/Archipelago/Players",
                    help="where the FFR-supplied yamls live, for AP seeds")
    ap.add_argument("--ff1-world", default=None,
                    help="path to worlds/ff1, for the AP location id table")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="also list the checks that agree and the ones skipped")
    args = ap.parse_args()

    roms = [os.path.expanduser(r) for r in args.rom]
    if not roms:
        root = os.path.expanduser(args.output_dir)
        roms = sorted(glob.glob(os.path.join(root, "**", "*.nes"), recursive=True))
    if not roms:
        raise SystemExit("no ROMs found")

    sections = load_pack_rules()
    ap_paths = ap_location_paths(ff1=args.ff1_world)
    if not ap_paths:
        print("(no worlds/ff1 found -- Archipelago rules will be skipped)\n")

    total, unmapped = 0, 0
    for rom in roms:
        print(os.path.basename(rom))
        d, u = check_seed(rom, sections, ap_paths, args.players_dir, args.verbose)
        total += d
        unmapped += u
        print("")

    print("%d divergences across %d seeds (%d checks unmapped)"
          % (total, len(roms), unmapped))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
