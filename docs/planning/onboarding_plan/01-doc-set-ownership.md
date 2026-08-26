# Which document owns which fact?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Onboarding, documentation and AI readiness](../onboarding_plan.md)

## Question

The Origin asks for a rewritten `README.md`, a new model-semantics document, and a new
CSV-contract document. But the repo already has `README.md`, `CONTEXT.md`,
`docs/ramping_semantics.md` and `AGENTS.md`, and their boundaries are already blurred.
Adding two more documents without deciding ownership produces four places to state the
same fact and three of them going stale.

Decide the **documentation set**: which documents exist, and what each one is the single
source of truth for.

### What the audit found

The most important finding is that **`docs/ramping_semantics.md` is already ~70% general
model semantics**, filed under a title that hides it:

- Its section on what the reported price means is the authoritative statement of the
  clearing price for the **whole model**, and explicitly supersedes `model_plan.md`.
- Its output-schema section documents `Curtailment`, `Unserved Energy`, `Market Cost`
  and `Production Cost` — columns that pre-date ramping entirely.
- Its section on the merit-order check documents that check's status model-wide.
- Its spill-vs-curtailment table and objective-reconciliation note are core model
  vocabulary, not ramping trivia.

Meanwhile `docs/model_semantics.md` — named as the Destination of the `model_plan`
effort, which never closed — **does not exist**. So the Origin's item 3 is largely a
**rehoming** problem, not a writing-from-scratch one.

Second finding: `README.md`'s maths is **already accurate and current**, verified term by
term against `build_and_solve` including the `forced_down` allowance. Its actual gaps are
first-run affordances: no install command, no directory map, no troubleshooting beyond
one line, no mention of `--inputs`/`--results`, no values for `VOLL` or `SPILL_COST`
despite both appearing as symbols in the objective, and no mention of `run_archive/`
even though a new folder appears on every default run.

Third: `CONTEXT.md` is strong but has gaps in repo vocabulary the code and docs actually
use — `Market Cost`, `Producer surplus`, `Load-weighted price`, `Time-weighted price`,
`Inframarginal rent`, `Attribution`, `Objective reconciliation`.

### What has to be decided

- **Does `README.md` stay a maths document, or become a getting-started document?** It
  currently opens with a quickstart and then becomes sets/parameters/objective/constraints.
  Those are two different readers. If they split, where does the maths go, and what does
  `AGENTS.md`'s existing description of README ("the model stated as maths") become?
- **What happens to `docs/ramping_semantics.md`?** Renamed to `model_semantics.md` and
  extended; split into a general document plus a ramping annex; or left alone with a new
  document pointing into it. Renaming breaks four inbound links (`README.md`, `AGENTS.md`,
  `CONTEXT.md` x3) and the `docs/examples/ramping/` framing.
- **Where does the CSV contract live?** The output-schema table already exists inside
  ramping_semantics. Input columns are documented nowhere. One document for both, or an
  input contract beside the existing output one?
- **What is `CONTEXT.md` for, versus a semantics document?** Vocabulary versus reasoning
  is the obvious line, but "why scarcity is unserved energy at VOLL" could sit either
  side. Draw it explicitly, and decide whether the missing terms above get added.
- **What does `AGENTS.md` own?** It currently holds the only directory map in the repo
  and the only mention of `--inputs`/`--results` — facts a human needs. Does it stay the
  agent-facing file, or become the shared-facts file the Origin describes?

The output is an ownership table, not the documents themselves.

## Decision
