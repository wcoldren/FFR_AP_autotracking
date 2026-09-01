# The docs

Everything behind the pack: how it is built, what it models, what is measured,
what is broken, and what is next. If you only want to *use* the tracker, the
[root README](../README.md) is the whole story and none of this is needed.

Start with **`ARCHITECTURE.md`**.

| | |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | How the pieces fit together — the two feeds, the pack, the Lua, the tools, the tests. Start here. |
| [`BRIDGE.md`](BRIDGE.md) | The emulator bridge in detail: the run clock, what a reset costs it, how the flags grid fills itself in, how the board stays honest. |
| [`NOVERWORLD.md`](NOVERWORLD.md) | How the pack models No-Overworld, read off the cartridge. Not a description of the setting — the FFR wiki has that. |
| [`ORACLE.md`](ORACLE.md) | The oracle cartridges, and how the access logic is graded against FFR's own. |
| [`ROADMAP.md`](ROADMAP.md) | What is next, in order, with the branch queue. |
| [`ISSUES.md`](ISSUES.md) | Known defects and open questions. |
| [`IDEAS.md`](IDEAS.md) | Unscoped, with the facts already attached. |
| [`../STATUS-2.md`](../STATUS-2.md) | The working log — what was built, why, and what each decision cost. The narrative the other pages lift their conclusions out of. |
| [`../STATUS.md`](../STATUS.md) | The first build-out's log, 2026-08-18 to 2026-09-01. Closed; kept because the reasoning that was tried and rejected is in it. |

## How these fit together

The log grows at the end; everything here is the settled half lifted out of it,
so a page under `docs/` should be readable without the log and the log keeps the
story of how it was found. There are two log files because one that grows
without a ceiling stops being readable: `STATUS.md` covers the first build-out
and is closed, `STATUS-2.md` is the live one. Pointers into a named section of
either stay valid — nothing moved between them except the capability inventory
at the head, which had to stay somewhere it could be kept true.

`ISSUES.md` is the defect list — if something is known wrong, it is there and not
scattered through the others. `IDEAS.md` holds what is not scoped yet, with
whatever has already been measured attached, so scoping does not start cold.
`ROADMAP.md` is the only page that claims to say what happens next.

Figures quoted anywhere here were measured on the cartridges in `ORACLE.md`
rather than reasoned about. Where a page gives a number, it names the seed.

**One home per fact.** `ORACLE.md` owns every grading figure — cartridge,
comparison, counts, and the before/after of each flag that moved one.
`FLAG_COVERAGE.md` owns the per-flag row. `ISSUES.md` owns defects, `IDEAS.md`
unscoped work, `ROADMAP.md` order, the log the narrative. A page that is not
the owner names a figure only where that figure is the subject of its sentence;
otherwise it points. A number kept in five places is a number that gets
corrected in one of them — this set carried 57 restatements of 26 distinct
grading figures before the rule was written down, with the page whose whole job
is the measurements holding the fewest of them.
