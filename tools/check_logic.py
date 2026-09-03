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

With --derived it checks the rules tools/noverworld_rules.py derives from a
No-Overworld cartridge instead of the pack's own, so the derivation can be
verified before it is wired into anything:

    python3 tools/check_logic.py seed.nes --derived rules.json \
        --ap-rules seed.yaml --ff1-world .../vendor/Archipelago/worlds/ff1

That mode prints every population as a number and reconciles them, because a run
that compared twelve locations must not read like one that compared two hundred.
The derivation varies only the twelve items that gate a tile; FFR also requires
five trade items -- the Slab, Herb, Adamant, Bottle and Crystal -- so those are
granted for free rather than skipped, and FFR then reads as permissively as it
can, so a divergence that survives cannot be blamed on the vocabulary gap.
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

# The No-Overworld variants' own trees -- the files scripts/init.lua loads for
# those four variants, so they are what a GameMode 2 seed has to be graded
# against. The pair is chosen by the cartridge's own mode rather than by the
# --derived switch: a hand-written No-Overworld rule set is checkable exactly
# when the checker reads the tree the player is actually running.
NOVERWORLD_FILES = ["locations/NOverworld/overworld.json",
                    "locations/NOverworld/incentives.json"]

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
    "Shard": "shards", "Orbs": "orbs",
}

# What FFR's *Archipelago exporter* prints for two requirements on a
# No-Overworld seed (FF1Lib/archipelago/Archipelago.cs:311-314). It is not the
# item-screen rename: MetroidVaniaMap.cs renames MARK to the Earth Orb, while
# the exporter independently spells the Canoe requirement "Mark". Both are real
# and they disagree, so this alias follows the exporter and nothing else.
# Measured on a GameMode-2 export: 159 uses of Mark, 212 of Sigil, and no use of
# Canoe or Floater anywhere. The spoiler .txt does not rename (ExtSpoiler.cs),
# so this applies to the Archipelago source only.
NOVERWORLD_ALIASES = {"Mark": "Canoe", "Sigil": "Floater"}

# What tools/noverworld_rules.py actually varies -- entrance_graph.ITEM_NAMES,
# the items that gate a tile. Held here rather than imported so this tool does
# not need the cartridge reader just to name the set.
#
# Oxyale and the Ruby joined it when SubEngineer and Titan did. They were the
# two biggest off-vocabulary grants by a distance -- 129 and 32 of `nov`'s 222
# comparisons -- and the grant is what made "222 of 222 agree" describe 58
# locations. Both are tile blockers like any other now, so the comparison
# actually varies them.
SWEPT_ITEMS = {"key", "crown", "cube", "orbs", "rod", "lute",
               "tnt", "floater", "canoe", "chime", "oxyale", "ruby"}

# Vehicles and items FFR can hand you at the start. Its own logic stops
# mentioning them once they are free, and the pack picks them up from cart RAM
# rather than from a flag, so the harness has to pin them by hand or every rule
# that names one reads as too strict.
FREE_FLAGS = {
    "FreeBridge": ["bridge"], "FreeShip": ["ship"], "FreeCanal": ["canal"],
    "FreeCanoe": ["canoe"], "FreeAirship": ["floater", "airship"],
    "FreeLute": ["lute"], "FreeRod": ["rod"], "FreeTail": ["tail"],
}

# The $name calls the rules make, and what they come out as for a given seed.
# They exist because access_rules cannot say "and not this flag"; the harness
# has to answer them the same way scripts/logic.lua does.
LUA_RULES = {
    "$noSardasForest": lambda flags: flags.get("MapSardasForest") is not True,
    "$noShipDrydock": lambda flags: flags.get("ShipDrydock") is not True,
    # ShuffleObjectiveNPCs moves Bahamut, Dr Unne and the Elf Doctor between
    # their three homes, and the permutation is rolled at generation rather
    # than written into the flag string. The pack answers that by requiring
    # all three homes, which is Bahamut's Cave, and this is the guard that
    # switches it off on a seed that did not roll the flag.
    "$noObjectiveShuffle": lambda flags: flags.get("ShuffleObjectiveNPCs") is not True,
    # The mode guards. One set of rules serves both modes by carrying both
    # modes' alternatives and letting these two decide which are live, so for
    # any one seed exactly one of them is pinned and the other mode's
    # alternatives fall out. GameMode 2 is No-Overworld (Enums.cs:396-404).
    "$noOverworld": lambda flags: flags.get("GameMode") == 2,
    "$standardWorld": lambda flags: flags.get("GameMode") != 2,
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
        " folds the visit in, because SCLogic.cs:555-557 resolves an NPC gated"
        " on the Unne flag to Unne's own reachability, so its rule already"
        " requires standing where the translation happens",
    ("Inner Sea/Coneria Castle/Coneria Castle Sara/Sara", "strict"):
        "the pack wants Garland beaten before the princess is back; FFR folds"
        " that in, because Garland is beatable from the start",
    ("Inner Sea/Elf Castle/Elf Castle Elf Prince/Elf Prince", "strict"):
        "ShuffleObjectiveNPCs is on, and the pack does not know where the Elf"
        " Doctor went. FFR does -- it wrote the seed -- so its rule names the"
        " one home the roll picked and does not move at all between a shuffled"
        " export and an unshuffled one. The permutation reaches neither the"
        " flag string nor the spoiler, so the pack asks for all three homes"
        " instead, which is Bahamut's Cave. Deliberately strict, the same call"
        " the Cardia gateway roll got, and it only fires on a seed that rolled"
        " the flag",
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

def load_pack_rules(pack=PACK, files=None):
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

    for rel in (files or LOCATION_FILES):
        with open(os.path.join(pack, rel)) as handle:
            walk(json.load(handle), [], [])
    return sections


def find_section(sections, path):
    """PopTracker location refs are written as suffixes of the full path.

    A ref can match twice, because the same pin is written into both the board
    tree and the incentive poster -- "I: Shop Item/I: Shop Item" matches
    "Onrac Continent/..." and "I: Onrac Continent/..." alike. That is not
    ambiguous at runtime -- but not by the suffix rule this function uses.
    Tracker::getLocationAndSection splits a ref at its *last* slash, so the
    location it looks up here is the single segment "I: Shop Item"; with no
    slash left in it, Tracker::getLocation compares node *names* and never
    reaches its id-suffix branch at all. scripts/init.lua:41-42 loads
    overworld.json before incentives.json, so the board tree wins on load
    order. Suffix and name-equality pick the same node today, and would stop
    agreeing the moment a board node's id merely ends with a name it is not
    itself named for -- at which point this function and the tracker disagree
    about which section a ref reaches. Resolve it board-first rather than
    giving up, which is what left this pin ungraded on every cartridge. Two
    hits inside the board tree are still a genuine ambiguity.
    """
    if path in sections:
        return path
    want = "/" + path
    hits = [k for k in sections if k.endswith(want)]
    if len(hits) == 1:
        return hits[0]
    board = [k for k in hits if not k.startswith("I: ")]
    if len(board) == 1:
        return board[0]
    return None


def find_hosted(sections, code, incentive):
    """The section that hosts a code. The same code is hosted twice -- once in
    the dungeon tree and once as an incentive pin -- and the two carry different
    rules, so which file it came from matters."""
    hits = [k for k in sections
            if sections[k]["hosted"] == code and k.startswith("I: ") == incentive]
    return hits[0] if len(hits) == 1 else None


def load_derived_rules(path, sections):
    """noverworld_rules.py's output as {section path: chain}, plus what it could
    not place.

    The derived file keys on a *node* name; `sections` keys on the full
    `Area/Node/Section` path, and a chest's section is generically called
    "Chest". So the join is on the second-to-last component, not on a path
    suffix -- `find_section` matches suffixes and resolves 0 of 241 chest names.

    A node may host more than one section (`Coneria Castle` does). The derived
    rule is a statement about the tiles beside one map cell, which is equally
    true of every section that node hosts, so it attaches to all of them.
    Attaching to the first would leave the rest on a stale overworld rule
    silently. The fan-out is reported because no derived name triggers it today,
    which means the branch is untested by data.

    Returns (chains, report). Nothing is ever dropped quietly: a name that
    resolves to nothing, or to more than one node, lands in `report` and the
    caller fails the run over it.
    """
    with open(path) as handle:
        blob = json.load(handle)
    rules, unreachable = blob["rules"], blob.get("unreachable", [])

    by_name = {}
    for full in sections:
        parts = full.split("/")
        if len(parts) >= 2:
            by_name.setdefault(parts[-2], []).append(full)

    chains, report = {}, {"fanned": [], "ambiguous": [], "unmatched": [],
                          "unreachable": list(unreachable), "names": len(rules)}
    for name, sets in sorted(rules.items()):
        where = by_name.get(name)
        if not where:
            report["unmatched"].append(name)
            continue
        nodes = {"/".join(f.split("/")[:-1]) for f in where}
        if len(nodes) > 1:
            report["ambiguous"].append((name, sorted(nodes)))
            continue
        if len(where) > 1:
            report["fanned"].append((name, len(where)))
        for full in where:
            chains[full] = as_chain(sets)
    return chains, report


def as_chain(sets):
    """A derived or-of-ands as a chain `satisfied()` can evaluate.

    "Free" is the trap. The obvious spelling of an empty requirement is
    `",".join([])` -> `[[""]]`, and that evaluates to **False**: `"".split(",")`
    is `[""]`, and `""` is never in `provided`. Every one of the 167 free
    locations would report as stricter than FFR, and the run would look like the
    derivation had failed catastrophically rather than like the adapter had. An
    empty requirement is an empty chain -- `satisfied` skips it and returns True.
    """
    if any(not s for s in sets):
        return []
    return [[",".join(s) for s in sets]]


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


# Terms that colour a pin rather than gate it. `^$incentiveSlot|<flag>` returns
# Normal or Inspect and never None (scripts/logic.lua), so it cannot make a
# section unreachable -- but it is not in `provided` either, so left alone it
# would read as "never satisfied" and report every incentive slot in the pack as
# stricter than FFR.
NON_GATING = ("^$incentiveSlot|",)


def gating(term):
    return not term.startswith(NON_GATING)


# scripts/logic.lua calls that stand for an item rather than for a per-seed
# flag, which is what keeps them out of LUA_RULES.
#
# hasCanoe and hasFloater exist because the two feeds disagree about what to
# call these on a No-Overworld seed: FFR's exporter renames Canoe to "Mark" and
# Floater to "Sigil" (Archipelago.cs:287-289,339-340) and Archipelago sends
# those, while the Mesen bridge reads the game's own bytes and sets canoe and
# floater. A rule naming either code alone is right for one feed and wrong for
# the other, so it names the call and the call accepts both.
#
# For this comparison they are simply the item. FFR's side is already folded
# back by NOVERWORLD_ALIASES, so both sides end up saying `canoe`/`floater`.
LUA_ITEM_RULES = {
    "$hasCanoe": "canoe",
    "$hasFloater": "floater",
    # Breaking the Black Orb is what FFR's export calls "orbs". This has never
    # bitten only because Archipelago.cs:93 drops every ToFR location from the
    # pool, so the alternatives it appears in are never compared -- but with it
    # missing the term read as neither a rule nor an item, and any comparison
    # that did reach ToFR would have graded the pack as ungated there.
    "$canBreakOrb": "orbs",
}


def alt_terms(alt):
    """The codes one alternative requires, with the item-standing $calls
    resolved and the non-gating terms dropped."""
    for term in alt.split(","):
        term = term.strip()
        if gating(term):
            yield LUA_ITEM_RULES.get(term, term)


def satisfied(chain, provided):
    for rules in chain:
        if not rules:
            continue
        if not any(all(term in provided for term in alt_terms(alt))
                   for alt in rules):
            return False
    return True


def chain_codes(chain):
    """Every code a chain mentions, `$func` calls included."""
    out = set()
    for rules in chain:
        for alt in rules:
            out.update(alt_terms(alt))
    return out


def offvocab_items(chain, truth):
    """The items to hand both sides for free before comparing them.

    An off-vocabulary item is one neither expression's disagreement can be
    blamed on: SWEPT_ITEMS is entrance_graph.ITEM_NAMES, the items that gate a
    *tile*, and everything outside it is something the walk cannot reason about
    either way. FFR's model carries requirements that are game rules rather than
    tile blockers -- Oxyale to breathe, the Ruby for Titan, the Slab for the
    translation. Since the trade reader landed the derived side has its own:
    Adamant, Crystal, Slab and Ruby are what NPCs want handed over, and all four
    are in FFR_ITEMS.values(), so compare() varies them.

    Which is why this reads both sides. Off FFR's clauses alone -- what it did
    -- a derived rule naming Adamant fails every combination without it on a
    seed whose FFR rule never asks for it, and the location reports `strict`: a
    divergence belonging to the harness rather than to the derivation.
    """
    offv = {FFR_ITEMS.get(t, t) for clause in truth for t in clause
            if FFR_ITEMS.get(t, t) not in SWEPT_ITEMS}
    return offv | {code for code in chain_codes(chain)
                   if code in FFR_ITEMS.values() and code not in SWEPT_ITEMS}


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
    # ToFRMode is an enum, not a tri-state: 2 is Short, and only Short moves a
    # rule. Mid keeps the lock door and the lute plate, so it reads as Long.
    # Random (3) is rolled at generation and the string does not say where it
    # landed, so it grades strict.
    if flags.get("ToFRMode") == 2:
        codes.add("shortToFR")
    if flags.get("IncentivizeCardia") is True:
        codes.add("cardiaIsIncentive")
    if flags.get("MapDragonsHoard") is True:
        codes.update(("cardiaIsIncentive", "BahamutHoard"))

    for flag, granted in FREE_FLAGS.items():
        if flags.get(flag) is True:
            codes.update(granted)

    for name, decide in LUA_RULES.items():
        if decide(flags):
            codes.add(name)
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

    # FFR's own export, straight off the randomizer, is pretty-printed JSON with
    # the payload under the game name (Archipelago.cs:187-211, serialized
    # Formatting.Indented). The line-oriented scan below finds `"rules": {` on
    # its own line, takes the empty remainder, and returns {} -- which
    # check_seed then skips in silence, so the ground truth is invisible and the
    # run reports on whatever else it found. Try structured parsing first.
    try:
        blob = json.loads(text)
    except ValueError:
        pass
    else:
        for scope in (blob, *(v for v in blob.values() if isinstance(v, dict))):
            rules = scope.get("rules") if isinstance(scope, dict) else None
            if isinstance(rules, dict) and rules:
                return rules

    # Archipelago's own yaml and spoiler print it as a Python dict on one line.
    m = re.search(r'^\s*"?rules"?:\s*(.*)$', text, re.M)
    if not m:
        return {}
    body = m.group(1).strip()
    if body in ("", "{}"):
        return {}
    return parse_bracket_dict(body.lstrip("{").rstrip("}"))


def alias_noverworld(rules):
    """Rewrite FFR's No-Overworld requirement spellings back to item names.

    Returns (rules, count). Left alone these corrupt the comparison in both
    directions at once: `item_requirements` filters on `in FFR_ITEMS` and drops
    "Sigil" from its clause, making FFR read weaker than it is, while
    `compare`'s ffr_ok keeps "Mark" as a literal that is never in `held`, making
    FFR read permanently closed.
    """
    out, n = {}, 0
    for name, clauses in rules.items():
        new = []
        for clause in clauses:
            terms = []
            for term in clause:
                if term in NOVERWORLD_ALIASES:
                    n += 1
                    terms.append(NOVERWORLD_ALIASES[term])
                else:
                    terms.append(term)
            new.append(terms)
        out[name] = new
    return out, n


def ap_location_paths(pack=PACK, ff1=None):
    """AP location name -> pack section path, via the world's id table and the
    pack's own LOCATION_MAPPING. Nothing hand-written in between.

    A path given explicitly and not found is refused rather than skipped. The
    default not being found is a skip, because a machine with no Archipelago
    checkout is a normal condition and the caller prints so; but a --ff1-world
    that names nothing is a typo, and returning {} for it made every location
    report unmapped and the whole run come back a cheerful zero. That is the
    failure this tool is least able to afford, since a zero here reads as
    agreement.

    The default was also simply wrong, and is the reason docs/ORACLE.md calls
    --ff1-world load-bearing: the pack sits at vendor/ff1/<pack>, so `..` is
    vendor/ff1 and the world is one level further up at vendor/Archipelago.

    Two shapes are *not* a path and fall back to the default rather than
    aborting: None, and the empty string a shell fragment produces when the
    variable behind it is unset. `--ff1-world ""` used to count as given, which
    made `names` the relative `data/locations.json` and resolved it against the
    caller's cwd -- a miss on most, and the wrong table on a cwd that happens to
    have one. And a path is expanded here rather than at the call site, because
    a `~` reaching this function is the correct directory spelled the one way
    os.path.exists cannot see, and the refusal above turns that from a skip into
    an abort.
    """
    given = bool(ff1)
    if given:
        ff1 = os.path.expanduser(ff1)
    else:
        ff1 = os.path.join(pack, "..", "..", "Archipelago", "worlds", "ff1")
    names = os.path.join(ff1, "data", "locations.json")
    if not os.path.exists(names):
        if given:
            raise SystemExit("check_logic: no locations.json under %s\n"
                             "  --ff1-world must name a worlds/ff1 directory"
                             % ff1)
        return {}
    with open(names) as handle:
        name_to_id = json.load(handle)
    src = open(os.path.join(pack, "scripts/autotracking/location_mapping.lua")).read()
    id_to_path = {}
    for m in re.finditer(r'\[(\d+)\]\s*=\s*\{"@([^"]+)"', src):
        id_to_path[int(m.group(1))] = m.group(2)
    return {name: id_to_path[i] for name, i in name_to_id.items() if i in id_to_path}


# ------------------------------------------------------------------ compare

def compare(chain, truth, pinned, reqs=None, raise_chain=(), assume=()):
    """Truth-table both expressions over the items they mention.

    Returns (verdict, witness) where verdict is "match", "permissive",
    "strict" or "both", and witness is an item set they disagree on.

    `assume` is granted to *both* sides and dropped from the variables. It
    exists for the items a derived rule set cannot express -- Oxyale, the Ruby,
    the Slab -- so that FFR reads as permissively as it possibly can and a
    surviving divergence cannot be blamed on the vocabulary gap. Pinning them
    only into `pinned` does not do this: `pinned` reaches the pack side alone,
    while `ffr_ok` reads `held`, so the item goes on being varied and FFR goes on
    requiring it.
    """
    assume = set(assume)
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
    items = sorted(items - assume)

    reverse = {v: k for k, v in FFR_ITEMS.items()}
    vocabulary = set(items)
    permissive, strict = None, None
    for bits in itertools.product((False, True), repeat=len(items)):
        held = {c for c, on in zip(items, bits) if on} | assume
        if not achievable(held, vocabulary, reqs):
            continue
        provided = with_airship(pinned | held, raise_chain)
        pack_ok = satisfied(chain, provided)
        ffr_ok = any(all(FFR_ITEMS.get(n, n) in held for n in clause)
                     for clause in truth)
        if pack_ok and not ffr_ok and permissive is None:
            permissive = sorted(reverse.get(c, c) for c in held - assume)
        if ffr_ok and not pack_ok and strict is None:
            strict = sorted(reverse.get(c, c) for c in held - assume)

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

def check_seed(rom_path, pack_rules, ap_paths, players_dir=None, verbose=False,
               derived=None, derived_report=None, ap_rules_path=None):
    with open(rom_path, "rb") as handle:
        rom = handle.read()
    try:
        info, flags = ffr_flags.decode_rom(rom)
    except ffr_flags.DecodeError as err:
        print("  cannot read this ROM: %s" % err)
        return 0, 0
    pinned = flag_codes(flags)
    noverworld = flags.get("GameMode") == 2

    # --derived is a No-Overworld artefact end to end: noverworld_rules.py
    # produces it, and main() joins its node names against the NOverworld tree
    # once, for every ROM in the run. A standard cartridge selects the standard
    # tree three lines below, so grading it here would compare section paths
    # from one tree against rules keyed to the other. That silently returns "no
    # derived rule" rather than an error, and it is invisible today only
    # because the two overworld files are byte-identical -- the first real edit
    # to locations/NOverworld/overworld.json would start hiding locations. The
    # default ROM list is a glob over the whole corpus, so this is the ordinary
    # case, not a corner: skip it loudly.
    if derived is not None and not noverworld:
        print("  skipped: --derived rules are keyed to the No-Overworld tree"
              " and this cartridge is GameMode %s" % flags.get("GameMode"))
        return 0, 0

    # Read the rules the cartridge's own variant loads. scripts/init.lua picks
    # locations/NOverworld/ for the four No-Overworld variants, so checking a
    # GameMode 2 seed against the standard tree would grade the pack on files
    # that seed never loads -- and the incentive sheets genuinely differ.
    sections = pack_rules[noverworld]

    # In derived mode the airship code cannot arise: a derived chain's terms come
    # from entrance_graph.ITEM_NAMES, the items that gate a tile, plus the trade
    # items entrance_graph.ITEM_RAM names -- and neither set has `airship`. The
    # mode has no overworld, no desert and no flight to raise one over anyway.
    # Synthesising it from the pack's stale overworld rule would be the one place a
    # No-Overworld answer still depended on overworld geography. AIRSHIP_SECTION
    # does resolve in the NOverworld tree today only because that tree is a copy
    # of the standard one; leaving the call in would turn the first honest edit
    # of it into a crash.
    raise_chain = () if derived else airship_chain(sections)

    spoiler = os.path.join(os.path.dirname(rom_path),
                           "Spoiler_%s_%s.txt" % (info["Seed"],
                                                  os.path.basename(rom_path).split("_")[-1][:-4]))
    # FF1R writes the spoiler as <rom stem>.txt (FF1R/Commands/Generate.cs), not
    # under the web download's name, so a locally generated seed has its spoiler
    # sitting right there under a name this would not have looked for.
    if not os.path.exists(spoiler):
        beside = os.path.splitext(rom_path)[0] + ".txt"
        if os.path.exists(beside):
            spoiler = beside

    checks = []
    reqs = {}
    unnamed_rows = 0

    if os.path.exists(spoiler):
        rows = parse_ffr_spoiler(spoiler)
        reqs = item_requirements(rows)
        for row in rows:
            code = FFR_SOURCES.get(row["source"])
            if code is None:
                # FFR_SOURCES covers the key-item sources. With the Archipelago
                # pool flags on, the spoiler's first table also lists every
                # pooled chest, whose Source strings it does not name -- and the
                # Archipelago export covers those anyway. Count them apart from
                # a real gap.
                unnamed_rows += 1
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
    if ap_rules_path:
        ap_files = [os.path.expanduser(ap_rules_path)]
    else:
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
            # Saying so matters: an unreadable export used to be skipped in
            # silence, which reads exactly like a seed that had no export.
            print("  no rules could be read from %s" % os.path.basename(ap_file))
            continue
        if noverworld:
            ap_rules, renamed = alias_noverworld(ap_rules)
            print("  %s: %d locations, aliased %d Mark/Sigil terms to Canoe/Floater"
                  % (os.path.basename(ap_file), len(ap_rules), renamed))
            if not renamed:
                print("        no Mark or Sigil in a GameMode 2 export -- FFR's"
                      " exporter changed, check Archipelago.cs:311-314")
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
    if derived:
        # The gate exists to suppress one artefact: quantifying over vehicle
        # combinations no player can be in, which arises because the pack
        # synthesises an `airship` code the seed's own logic never mentions. A
        # derived chain and an FFR clause are two or-of-ands over the same item
        # names with nothing synthesised on either side, so achievability
        # pruning can only hide real disagreements. Dropping it is strictly
        # conservative -- but measured on both cartridges, none of the four
        # vehicles is ever in `pinned`, so leaving the gate in place would make
        # every derived run print its findings and then report zero.
        reqs, trustworthy, missing = {}, True, []
        print("  achievability pruning off: both sides are or-of-ands over the"
              " same item codes, so every subset is a fair test")
    if missing:
        print("  where %s were placed is not recorded for this seed, so what"
              " follows over-reports and is not counted" % ", ".join(missing))

    # Grouped, because one wrong rule on a dungeon shows up once per chest
    # under it and a hundred identical lines hide how few problems there are.
    # The spoiler .txt and the Archipelago export describe the same seed, so a
    # key-item location arrives from both. Identical claims are one check, not
    # two -- left alone they double every divergence's "at" list and inflate the
    # comparison count. A location where the two sources *disagree* survives as
    # two checks, which is the case worth seeing.
    seen_claims = set()
    deduped, doubled = [], 0
    for label, path, truth, why in checks:
        key = (path, repr(truth))
        if why is None and key in seen_claims:
            doubled += 1
            continue
        seen_claims.add(key)
        deduped.append((label, path, truth, why))
    checks = deduped

    groups, order, witnesses, waived = {}, [], {}, {}
    unmapped, agree = 0, 0
    no_derived, offvocab = [], []
    for label, path, truth, why in checks:
        if why:
            unmapped += 1
            if verbose:
                print("  --   %-40s %s" % (label, why))
            continue
        offv = set()
        if derived is not None:
            chain = derived.get(path)
            if chain is None:
                # FFR has a rule here and the derivation placed nothing. Not a
                # divergence -- a hole in noverworld_rules.placements().
                no_derived.append((label, path))
                continue
            # Skipping the locations with an off-vocabulary requirement was
            # the first thing tried and it is too blunt: FFR's rule is an OR, so
            # `[[Chime,Oxyale,Sigil],[Mark]]` has a clause entirely inside the
            # swept vocabulary and is perfectly comparable. Instead, hand the
            # player every off-vocabulary item for free. That makes FFR's side
            # as permissive as it can possibly be, so a location that still
            # comes out permissive is over-reach the vocabulary gap cannot
            # explain -- and one that comes out strict would be a walk that
            # closes what FFR opens even then. Which items those are, and why
            # they come off both sides, is offvocab_items().
            offv = offvocab_items(chain, truth)
            if offv:
                offvocab.append((label, path, sorted(offv)))
            here_pinned = pinned | offv
        else:
            chain = sections[path]["chain"]
            here_pinned = pinned
        verdict, witness = compare(chain, truth, here_pinned, reqs, raise_chain, offv)
        if verdict == "match":
            agree += 1
            if verbose:
                print("  ok   %-40s %s" % (label, show_rules(truth)))
            continue
        # The waivers are statements about hand-written pack rules and have no
        # standing over a derived one.
        reason = None if derived is not None else WAIVED.get((path, verdict))
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

    divergent = sum(len(g) for g in groups.values())
    if derived is not None:
        # Every population named as a number. A run that compared 12 locations
        # must not be able to read like one that compared 240.
        print("  derived rules        %4d   (%d unreachable, kept their old rules)"
              % (derived_report["names"], len(derived_report["unreachable"])))
        print("    resolved           %4d   (%d fanned, %d ambiguous, %d unmatched)"
              % (len(derived), len(derived_report["fanned"]),
                 len(derived_report["ambiguous"]), len(derived_report["unmatched"])))
        print("  FFR rules joined     %4d   (%d could not be mapped,"
              " %d duplicate claims collapsed)"
              % (len(checks) - unmapped, unmapped, doubled))
        if unnamed_rows:
            print("    spoiler rows with no FFR_SOURCES entry %4d  (the"
                  " Archipelago export covers these)" % unnamed_rows)
        print("  compared             %4d   %d agree, %d divergent in %d shapes"
              % (agree + divergent, agree, divergent, len(groups)))
        print("    of those, %d had an off-vocabulary item granted free so the"
              " vocabulary gap could not explain a divergence" % len(offvocab))
        print("  not compared:")
        print("    no derived rule    %4d   FFR has a rule, placements() found"
              " no tile" % len(no_derived))
        if offvocab:
            # The set that was actually granted, not a re-derivation of it from
            # FFR's clauses: a location can land here because the *derived* rule
            # names a trade item FFR's rule never mentions, and re-reading only
            # the FFR side would leave that location counted in the line above
            # and absent from this tally.
            seen = {}
            for label, _, granted in offvocab:
                for code in granted:
                    seen.setdefault(code, []).append(label)
            print("    off-vocabulary items: %s"
                  % ", ".join("%s x%d" % (t, len(v))
                              for t, v in sorted(seen.items(), key=lambda kv: -len(kv[1]))))
        for label, path in no_derived:
            print("      no derived rule: %s" % path)
        for name in derived_report["unmatched"]:
            print("      unmatched derived name: %s" % name)
        for name, where in derived_report["ambiguous"]:
            print("      ambiguous derived name: %s -> %s" % (name, ", ".join(where)))
        for name, n in derived_report["fanned"]:
            print("      fanned to %d sections: %s" % (n, name))
        broken = len(derived_report["ambiguous"]) + len(derived_report["unmatched"])
        return divergent + broken, unmapped

    print("  %d checked, %d agree, %d distinct divergences over %d locations,"
          " %d could not be mapped%s"
          % (agree + divergent + sum(len(w) for w in waived.values()),
             agree + sum(len(w) for w in waived.values()), len(groups),
             divergent, unmapped,
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
    ap.add_argument("--derived", default=None,
                    help="check this rules JSON (tools/noverworld_rules.py -o) "
                         "instead of the pack's own access_rules")
    ap.add_argument("--ap-rules", default=None,
                    help="the Archipelago export to read FFR's rules from, "
                         "instead of globbing beside the ROM")
    args = ap.parse_args()

    roms = [os.path.expanduser(r) for r in args.rom]
    if not roms:
        root = os.path.expanduser(args.output_dir)
        roms = sorted(glob.glob(os.path.join(root, "**", "*.nes"), recursive=True))
    if not roms:
        raise SystemExit("no ROMs found")

    pack_rules = {False: load_pack_rules(),
                  True: load_pack_rules(files=NOVERWORLD_FILES)}
    # One join for the whole run, against the NOverworld tree, because that is
    # the only tree --derived rules can be keyed to; check_seed skips any
    # cartridge that would not load it.
    sections = pack_rules[True] if args.derived else pack_rules[False]
    ap_paths = ap_location_paths(ff1=args.ff1_world)
    if not ap_paths:
        print("(no worlds/ff1 found -- Archipelago rules will be skipped)\n")

    derived = report = None
    if args.derived:
        derived, report = load_derived_rules(args.derived, sections)

    total, unmapped = 0, 0
    for rom in roms:
        print(os.path.basename(rom))
        d, u = check_seed(rom, pack_rules, ap_paths, args.players_dir, args.verbose,
                          derived, report, args.ap_rules)
        total += d
        unmapped += u
        print("")

    print("%d divergences across %d seeds (%d checks unmapped)"
          % (total, len(roms), unmapped))
    return 1 if total else 0


if __name__ == "__main__":
    # Being piped into head is not an error worth a traceback.
    try:
        import signal
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (ImportError, AttributeError, ValueError):
        pass
    sys.exit(main())
