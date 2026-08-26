# Should `profiles.csv` keep its region header row?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Onboarding, documentation and AI readiness](../onboarding_plan.md)

## Question

`inputs/profiles.csv` has a two-row header. Row 1 is a region row, `,FRA,FRA`; row 2 is
the series row, `hours,Wind,Solar`. `FRA` is explained nowhere, appears in no document,
and is the single least guessable thing about the input format — it was the strongest
argument for writing an input contract at all in
[Which document owns which fact?](01-doc-set-ownership.md).

Decide whether the region row **stays, goes, or earns its keep**.

### What the audit found

**It is not dead code.** `MFDM.py:212` reads the file with `pd.read_csv(..., header=[0, 1])`
and flattens the two rows into column names of the form `"FRA Wind"`. The comment at
`MFDM.py:208-211` states the region is kept deliberately, "so multi-region files stay
unambiguous". It is a hook for multi-region support that never arrived — speculative
generality, not residue.

Removing it is a schema migration touching five things:

| What | Where |
|---|---|
| The input file | `inputs/profiles.csv` |
| The parser and its flatten loop | `MFDM.py:208-218` |
| Technology-token matching against column names | `MFDM.py:447-472` |
| Two worked-example fixtures | `docs/examples/ramping/scenario_1_holding_back/profiles.csv`, `.../scenario_2_spill/profiles.csv` |
| The run archive | `runstore.INPUT_FILES` hashes `profiles.csv`; `runs.py restore` can put an archived copy back |

The archive is the awkward one. Every archived run holds a two-row `profiles.csv`.
After a migration, `restore` would hand the new parser a header it no longer understands
— so past runs stop being re-runnable, which is the one thing the archive exists to
guarantee.

### What has to be decided

- **Does the region row go at all?** Deleting it is the simple read: nothing consumes the
  region, one region exists, and `PROFILE_TECHNOLOGIES` matches on tokens regardless.
  Keeping it is defensible if multi-region is genuinely on the roadmap — but the hook has
  sat unused long enough to be worth re-testing rather than assuming.
- **If it goes, what happens to archived runs?** Options include leaving them
  unrestorable and saying so, having the parser accept both shapes, or migrating the
  archived copies in place. Note this overlaps
  [Manifest compatibility](07-manifest-compatibility.md), which found that correcting
  `compute_kpis` would change no archived value — the same question asked of a different
  field.
- **If it stays, what documents it?** The input contract in `docs/model_semantics.md`
  currently describes the two-row header with a forward reference to this ticket. If the
  row survives, that note becomes a real explanation of what a region is and why it is
  there — which requires someone to have a view on multi-region.
- **Is `FRA` the right token either way?** It is unexplained even to a reader who accepts
  that regions exist.

## Decision
