# VOLL or LoL?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: resolved
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Onboarding, documentation and AI readiness](../onboarding_plan.md)

## Question

There is an **uncommitted rename in the working tree**: the constant `VOLL` has become
`LoL` throughout `model/MFDM.py`, and a matching comment change sits in
`dashboard/dashboard.py`. The rename reaches **user-facing output** — the strings printed
when a price is set by scarcity read `(LoL)`.

`CONTEXT.md` defines only **VOLL**, at `$8,300/MWh`, and it is one of the most-cited
entries in the glossary. The moment this rename is committed, the repo uses two names for
one constant and the glossary is stale on it.

Pick one name, and say what happens to the other.

### Why this is small and urgent

Small: it is one term. Urgent: it is uncommitted, so every session working on this map
risks either committing it silently or reverting it by accident, and every document
ticket downstream has to write *some* name. Resolving it early stops the ambiguity
propagating into the new documents that [Which document owns which
fact?](01-doc-set-ownership.md) will commission.

### What has to be decided

- **Which name.** `VOLL` (value of lost load) is the standard term in power-system
  literature and is what `docs/research/scarcity_pricing.md` and the European Commission
  JRC source use. `LoL` normally abbreviates *loss of load*, which is a different
  quantity — a probability or an expectation, not a price. If the rename was motivated by
  something specific, that reason needs stating; on its face it looks like it trades a
  standard term for one that collides with another concept.
- **Whether the code identifier and the documented term must match.** They could
  legitimately differ if there is a reason, but `CONTEXT.md`'s whole purpose is
  collision-resolution, so a split would need an explicit entry.
- **Scope of the change.** Code identifier, printed strings, `CONTEXT.md`, `README.md`
  (where the symbol appears in the objective but is never defined), and
  `docs/ramping_semantics.md` — which discusses `SPILL_COST != VOLL` as the single most
  load-bearing modelling decision in the ramping work.
- **What to do with the working-tree diff right now**: commit it, revert it, or amend it.

## Decision

**`LoL` wins, spelled that way everywhere, and `VOLL` is removed from the repo's own
vocabulary.** The reason is **the owner's preference**, on a training repo where the cost
of diverging from the standard term is judged acceptable. That is the whole rationale and
it is recorded plainly rather than dressed up, because the next reader deserves to know
there is no deeper argument underneath it.

**The objection was put and overruled, and is recorded here so it is not rediscovered.**
`LoL` is the standard abbreviation for *loss of load*, as in LOLP and LOLE — reliability
measures, a probability and an expected number of hours. This constant is neither: it is a
price of $8,300/MWh. `VOLL` is the standard name for that price in the literature and is
what the cited JRC source uses. So the repo's glossary, whose stated job is resolving
collisions between a term and its industry meaning, now carries a term that *creates* one.
Anyone revisiting this should weigh that against the preference, not against nothing.

**Scope, as changed:**

| Where | What happened |
|---|---|
| `model/MFDM.py` | Nothing. Already `LoL` throughout, 18 occurrences including 4 printed strings. |
| `dashboard/dashboard.py` | Nothing. Already `LoL`. |
| `CONTEXT.md` | 6 occurrences renamed; the head entry rewritten. |
| `docs/model_semantics.md` | 13 occurrences renamed, including a section heading and the anchor `CONTEXT.md` links to. |
| `README.md` | `\text{LOL}` in the objective becomes `\text{LoL}`. |
| `docs/research/scarcity_pricing.md` | **Unchanged.** Keeps `VoLL`. |
| `docs/planning/**` | **Unchanged.** Historical record. |

**The ticket's premise was stale.** It describes an uncommitted working-tree diff and asks
whether to commit, revert or amend it. The rename was in fact committed in `b42885a`, so
this was a change-or-keep decision on committed code, not a decision about a dirty tree.

**There were three spellings live, not two.** `LoL` in code, `\text{LOL}` in the README
objective, and `VoLL` in the research note, alongside `VOLL` in the documents. The README
form is corrected to `LoL`; mixed case is kept over `LOL` partly because `LOL` in printed
output such as `unserved energy (LOL)` reads as internet shorthand.

**The research note keeps `VoLL` and gets no bridging sentence.** It records what the JRC
publication *"Value of Lost Load: Greece"* says, and renaming a quoted term would misquote
the source. The consequence — accepted knowingly — is that `VoLL` now appears in the repo
with **no entry in `CONTEXT.md` explaining it**, since the cross-reference entry was
declined. A reader who opens the research note first has nowhere to look it up. Judged
tolerable because the note is self-evidently an external citation.

**`LoL` expands to "the cost of lost load".** Not "Value of Lost Load", which would be the
term being replaced, and not bare "Lost Load", which names a *quantity of energy* in MWh
rather than a price in $/MWh — an entry reading "LoL — Lost Load, $8,300/MWh" would
misdefine itself. The glossary entry states explicitly that it is a price, not a quantity
and not a probability, which is the one place the LOLP collision is defended against.

**No archive impact.** All 22 archived `manifest.json` files contain neither string, so no
stored KPI name or value depends on this rename.
