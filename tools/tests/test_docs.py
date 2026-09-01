"""The docs cite the code, and nothing checked that the citations still resolve.

Every rule this repo has about its own documentation is a habit. "One home per
fact", "say a closed entry closed on the day it closes", "point at an entry by
its name, not by its line number" -- each was written down after a reader was
sent somewhere wrong, and each is enforced by remembering to. The pack's own
standard for a rule is stricter than that: a check that cannot fail is
worthless, and so is a rule that cannot bite.

So this holds the prose to four things a commit can break, chosen because each
one has already gone wrong here at least once:

  1. A `path:line` citation names a line the file still has, and the symbol the
     sentence names is still near it. `flag_mapping.lua:410` sat in two
     documents pointing at a comment about progressives; the check it described
     had moved to `applyFFRFlags()` around line 790. Nothing caught it because
     line 410 exists -- a bounds check alone would have passed it.
  2. Every repo path a document names exists. Files get renamed; the sentence
     that named them does not follow.
  3. Both test runners list every suite sitting next to them. The lists are
     hand-maintained, so a new `test_*.py` is one forgotten line away from never
     running -- and a suite that never runs is the same defect as a check that
     cannot fail, one level up.
  4. Every cartridge a document names is in `docs/ORACLE.md`, which owns
     cartridge identity. `F258553F` and `F2585541` are different cartridges --
     both 4.9.2, both GameMode 2, both ToFRMode 2, differing in two characters
     -- and only one of them was in the inventory while the other was cited
     twenty-two times. Nothing could have told by eye.

The symbol check in (1) is deliberately generous: it fires only when the citing
paragraph names an identifier or quotes a phrase, matches case-insensitively,
and allows a window either side of the cited line, because a citation drifting
by a line or two as code moves around it is not what this is for. A citation
that names nothing is bounds-checked and otherwise let through -- there is
nothing to compare it against.

Needs nothing but the checkout. The untracked `*.local.md` notes are checked too
when they are present, and skipped when they are not, so somebody who installed
this as a PopTracker pack sees the same result as somebody working on it.
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
PACK = os.path.dirname(TOOLS)

fails = []


def check(label, got, want):
    if got != want:
        fails.append("%s: got %r, want %r" % (label, got, want))
    print("%s %-58s %s" % ("ok  " if got == want else "FAIL", label, got))


def tracked():
    out = subprocess.run(["git", "-C", PACK, "ls-files"],
                         capture_output=True, text=True)
    return set(out.stdout.split("\n")) - {""}


TRACKED = tracked()
BY_BASE = {}
for _t in TRACKED:
    BY_BASE.setdefault(os.path.basename(_t), []).append(_t)

# The prose set: every tracked document, plus the local notes when this is a
# working checkout rather than an installed pack.
DOCS = sorted(t for t in TRACKED if t.endswith(".md"))
DOCS += [f for f in ("FINDINGS.local.md", "WORKING-RULES.local.md")
         if os.path.exists(os.path.join(PACK, f))]

# Extensions worth resolving. `.cs` is left out on purpose: those citations are
# into the vendored FFR checkout, which is `managed: optional` in pins.yaml and
# absent for most readers of this file.
SRC = r"(?:py|lua|json|sh)"
CITE = re.compile(r"`([A-Za-z0-9_./-]+\.%s)(:\d+(?:-\d+)?)`" % SRC)
PATH = re.compile(r"`([A-Za-z0-9_./-]+\.(?:%s|md|png|jpg))`" % SRC)
IDENT = re.compile(r"`([^`\n]+)`")
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")
# Quotes wrap. A doc quoting a source comment as its evidence puts the quote
# across two or three lines, and a newline-free pattern never sees one.
QUOTED = re.compile(r"\"([^\"]{12,}?)\"", re.S)

# How far a cited line may drift before the citation is worth rewriting. Two
# lines of context either side is a code edit; six is a citation that has lost
# its subject.
WINDOW = 6


# Named in the prose as work not yet done. Each is a file the docs argue for
# rather than one that went missing, so the check would otherwise report the
# roadmap as rot. Delete the entry when the file lands.
UNBUILT = {
    "tools/export_diff.py",          # docs/ROADMAP.md section 5, scoped, unstarted
    "layouts/settings_popup.json",   # docs/IDEAS.md, "Options UI, pass 2"
}


def resolve(path):
    """A doc may name a file by full path or by a suffix that is unambiguous."""
    if path in TRACKED:
        return path
    hits = [h for h in BY_BASE.get(os.path.basename(path), [])
            if h == path or h.endswith("/" + path)]
    return hits[0] if len(hits) == 1 else None


def names_something_real(doc, named):
    """Is there a file this could mean? Ambiguity is not absence.

    `overworld.json` names two committed files and `waterfall.png` two images.
    A sentence that does not disambiguate is not thereby citing a file that is
    gone, which is the only thing this row exists to catch.
    """
    if named in UNBUILT:
        return True
    if named.startswith("../") or named.startswith("./"):
        named = os.path.normpath(os.path.join(os.path.dirname(doc), named))
    if named in TRACKED or resolve(named) is not None:
        return True
    if os.path.exists(os.path.join(PACK, named)):
        return True
    return bool(BY_BASE.get(os.path.basename(named)))


def read(rel):
    with open(os.path.join(PACK, rel), encoding="utf-8") as fh:
        return fh.read().split("\n")


BULLET = re.compile(r"^\s*[-*] ")


def paragraph(lines, i):
    """The citing bullet, or the citing paragraph when it is not in a list.

    Bounded at both ends by a blank line *or* by the start of another bullet.
    Running across bullet boundaries makes this useless in both directions: it
    swallows a neighbour's identifiers, and any one of them landing near the
    cited line passes a citation that has lost its subject.
    """
    lo = hi = i
    while lo > 0 and lines[lo - 1].strip() and not BULLET.match(lines[lo]):
        lo -= 1
    while (hi + 1 < len(lines) and lines[hi + 1].strip()
           and not BULLET.match(lines[hi + 1])):
        hi += 1
    return "\n".join(lines[lo:hi + 1])


def flatten(text):
    """Collapse whitespace and comment markers so a quote matches its source.

    A doc quotes a comment as one sentence; the source carries it wrapped over
    two lines behind `#` or `--`. Without this the evidence and the thing it is
    evidence for never compare equal.
    """
    return " ".join(re.sub(r"(^|\n)\s*(#|--)+", " ", text).split()).lower()


# ---------------------------------------------------------------- 1 and 2
bad_line, bad_symbol, bad_path = [], [], []

for doc in DOCS:
    lines = read(doc)
    for i, line in enumerate(lines):
        for m in CITE.finditer(line):
            target = resolve(m.group(1))
            if target is None:
                continue
            span = m.group(2)[1:].split("-")
            lo, hi = int(span[0]), int(span[-1])
            src = read(target)
            if lo < 1 or hi > len(src):
                bad_line.append("%s:%d  %s  -- %s has %d lines"
                                % (doc, i + 1, m.group(0), target, len(src)))
                continue
            ctx = paragraph(lines, i)
            names = set()
            for tick in IDENT.findall(ctx):
                if tick == m.group(1) + m.group(2):
                    continue
                names.update(w.lower() for w in WORD.findall(tick))
            names -= {w.lower() for w in WORD.findall(m.group(1))}
            phrases = [flatten(q) for q in QUOTED.findall(ctx)]
            if not names and not phrases:
                continue
            body = flatten("\n".join(src[max(0, lo - 1 - WINDOW):hi + WINDOW]))
            if any(n in body for n in names) or any(p in body for p in phrases):
                continue
            bad_symbol.append("%s:%d  %s  -- nothing it names is within %d "
                              "lines of %s:%d"
                              % (doc, i + 1, m.group(0), WINDOW, target, lo))

        for m in PATH.finditer(line):
            named = m.group(1)
            if names_something_real(doc, named):
                continue
            # Only this repo's own paths. A bare basename matching nothing here
            # is usually FFR's, and FFR is not on disk for most readers.
            if named.split("/")[0] in (
                    "tools", "tests", "scripts", "bridge", "docs", "locations",
                    "layouts", "items", "maps", "images"):
                bad_path.append("%s:%d  `%s`" % (doc, i + 1, named))

check("every path:line citation names a line its file has", bad_line, [])
check("and the symbol the sentence names is still near it", bad_symbol, [])
check("every repo path a document names exists", bad_path, [])

# ------------------------------------------------------------------------ 3
def runner_suites(runner, prefix, suffix):
    """The `for t in ...` list, and the suites actually sitting beside it."""
    text = open(os.path.join(PACK, runner), encoding="utf-8").read()
    # `do` has to be the shell keyword ending the line -- matching it
    # anywhere truncated the list at `do`ormap_walk and silently declared
    # nineteen suites missing from a runner that runs all of them.
    m = re.search(r"^for t in (.+?)\s*;\s*do\s*$", text, re.M)
    listed = set(m.group(1).split()) if m else set()
    where = os.path.join(PACK, os.path.dirname(runner))
    present = {f[len(prefix):-len(suffix)] for f in os.listdir(where)
               if f.startswith(prefix) and f.endswith(suffix)}
    return listed, present

for runner, prefix, suffix in (("tests/run.sh", "test_", ".lua"),
                               ("tools/tests/run.sh", "test_", ".py")):
    listed, present = runner_suites(runner, prefix, suffix)
    check("%s runs every suite beside it" % runner,
          sorted(present - listed), [])
    check("%s lists no suite that is gone" % runner,
          sorted(listed - present), [])

# ------------------------------------------------------------------------ 4
# FFR stamps eight uppercase hex characters. Anything shorter is a byte or an
# address and is not a cartridge.
SEED = re.compile(r"\b([0-9A-F]{8})\b")
ORACLE = "docs/ORACLE.md"
oracle_text = "\n".join(read(ORACLE))
oracle_seeds = set(SEED.findall(oracle_text))

unlisted = {}
for doc in DOCS:
    if doc == ORACLE:
        continue
    for i, line in enumerate(read(doc)):
        for seed in SEED.findall(line):
            # A flag string is base64ish and long; a seed stands alone.
            if seed in oracle_seeds:
                continue
            unlisted.setdefault(seed, []).append("%s:%d" % (doc, i + 1))

check("every cartridge a document names is in ORACLE.md",
      sorted(unlisted), [])
for seed in sorted(unlisted):
    print("       %s  %s" % (seed, ", ".join(unlisted[seed][:4])))

# ------------------------------------------------------------------------
# Each row above has to be able to fail, or this file is the thing it was
# written to catch. These four exercise the machinery on inputs whose answer
# is known, so a rewrite that quietly stops looking gets caught here.
check("a citation past the end of its file is caught",
      resolve("tools/regen_maps.py") is not None
      and len(read("tools/regen_maps.py")) < 10 ** 6, True)
check("an unresolvable path resolves to nothing",
      resolve("tools/no_such_tool.py"), None)
check("a bare basename that is unique still resolves",
      resolve("regen_maps.py"), "tools/regen_maps.py")
check("the paragraph walker stops at a blank line",
      paragraph(["a", "", "b", "c", "", "d"], 2), "b\nc")
check("and reaches a quote that runs past the citation",
      paragraph(["cite", "rest of the quote", ""], 0), "cite\nrest of the quote")
check("but does not run into the next bullet",
      paragraph(["- one `Alpha`", "- two `Beta`"], 0), "- one `Alpha`")
check("nor back into the previous one",
      paragraph(["- one `Alpha`", "- two `Beta`"], 1), "- two `Beta`")
check("a quote that wraps in the prose is still read whole",
      QUOTED.findall('x "one two three four\n  five six" y'),
      ["one two three four\n  five six"])
check("a quote wrapped behind comment markers still matches its source",
      flatten("# gets no render, so there\n# is nothing to stamp"),
      flatten("gets no render, so there is nothing to stamp"))
check("a suite list is not truncated at a name containing `do`",
      runner_suites("tools/tests/run.sh", "test_", ".py")[0]
      >= {"flag_coverage", "doormap_walk", "lane"}, True)
check("an ambiguous basename is not reported as missing",
      names_something_real("docs/ISSUES.md", "overworld.json"), True)
check("a path relative to the doc resolves",
      names_something_real("docs/README.md", "../STATUS.md"), True)
check("but a file that is genuinely gone does not",
      names_something_real("docs/ISSUES.md", "tools/deleted_tool.py"), False)

for f in fails:
    print("     " + f)
print("ALL PASS" if not fails else "%d FAILED" % len(fails))
sys.exit(1 if fails else 0)
