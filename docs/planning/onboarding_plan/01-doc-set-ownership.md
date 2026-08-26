# Which document owns which fact?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: resolved
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

**Four documents, no new ones beyond `model_semantics.md`.** The set stays small
deliberately: this is an onboarding repo, and a fifth document is a fifth place for the
same fact to rot.

| Document | Single source of truth for | Explicitly not |
|---|---|---|
| `README.md` | Getting started, and the model as maths: sets, parameters, objective, constraints. Directory map, `--inputs`/`--results`, the `VOLL` and `SPILL_COST` values, troubleshooting. | Why the model is built this way. Column-by-column CSV formats. |
| `docs/model_semantics.md` | What the model means. Price semantics, the merit-order check's status, spill vs curtailment, objective reconciliation, ramping, the CSV contract for both inputs and outputs, worked examples, known gaps. | The maths itself. How to run it. |
| `CONTEXT.md` | Vocabulary. What each term denotes, one entry each. | Justification. Anything needing a worked example. |
| `AGENTS.md` | Agent-facing conventions and pointers. Owns no facts. | Anything a human would want to look up. |

**`README.md` keeps the maths, and gains the first-run affordances.** The maths stays
because this is a training repo and the model's statement should be the first thing found,
not a click away. The audit confirmed it is accurate term for term against
`build_and_solve`, so nothing about it needs rewriting.

Section order is **quickstart, directory map, running with options, maths,
troubleshooting**. The operational material sits *above* the maths rather than below it:
a reader who cannot yet run the model has no use for the objective function, and "front
and centre" is satisfied by the maths being in README and reachable from its headings,
not by it being the first thing past the quickstart.

**`docs/ramping_semantics.md` is renamed to `docs/model_semantics.md` and reordered, not
split.** The audit found it is already ~70% model-wide: of its ten sections only §§1-4
(the problem, ramp rate, ramp cost, spill) and §§8-9 (worked example, what changed) are
ramping-specific, while §5 price meaning, §6 merit-order check, §7 output schema and §10
known gaps apply to the whole model. General sections lead; ramping follows.

It is not split, because the document is a narrative: the worked examples in §8 depend on
the spill floor from §4 and the dual pricing from §5, so a split cuts through the middle
of an argument and leaves both halves needing the other. Nor does a new document merely
point into the old one - that produces exactly the "four places to state the same fact,
three of them stale" failure this ticket opened by warning about.

The rename costs **five** inbound link updates, not the four the Origin counted:
`README.md:22`, `README.md:99`, `AGENTS.md:27`, `CONTEXT.md:31` and `CONTEXT.md:111`. The
last is worse than a link - it cites **"§4"** by section number, so the reorder breaks it
whether or not the filename changes. It becomes a named link.

**The CSV contract lives inside `model_semantics.md`, covering inputs and outputs
together.** Not a separate `csv_contract.md`, on the general principle of keeping the
document count down, and for a specific reason: the output-schema section is already
load-bearing where it sits, since its objective-reconciliation note depends on the
pricing argument above it. Moving it out would re-create the split rejected above. Input
columns join it, giving one document that owns what the model consumes, what it computes
and what it emits.

Input columns are currently documented **nowhere**, and `profiles.csv` is the case that
most needs it: it carries a two-row header, a region row (`,FRA,FRA`) above a series row
(`hours,Wind,Solar`), which no document explains and no user could guess.

**`CONTEXT.md` and `model_semantics.md` divide on denotation versus justification.**
CONTEXT says what a term *denotes*; semantics argues *why the model is built that way*.
The ticket's hard case resolves cleanly under this test: CONTEXT gets "scarcity: unserved
energy priced at VOLL" in a sentence, and the argument for pricing it that way lives in
semantics. Rule of thumb to write into CONTEXT: **if an entry needs a worked example, it
belongs in semantics with a pointer.**

The seven missing terms are added: `Market Cost`, `Producer surplus`, `Load-weighted
price`, `Time-weighted price`, `Inframarginal rent`, `Attribution`, `Objective
reconciliation`.

**`AGENTS.md` owns no facts at all.** It keeps agent-facing conventions - start in
`model/MFDM.py`, read `CONTEXT.md` before using a domain term, the skills sections - and
otherwise only pointers. The directory map and `--inputs`/`--results` move to `README.md`,
because a fact whose only home is `AGENTS.md` is invisible to the humans who need it, and
duplicating it creates two copies to drift. The layout block becomes a pointer to README.

Two consequences worth naming. The `requirements.txt` line added to `AGENTS.md` by
[the dependency contract](00-dependency-contract.md) becomes a pointer. And the sentence
at `AGENTS.md:17` claiming the run archive "is kept in the repo" - which contradicts
`.gitignore:9`, where `run_archive/` is excluded - **is deleted rather than moved**. It is
a fact, so it does not belong in `AGENTS.md`; it is also false, so it does not belong in
README either.

**`docs/examples/ramping/` stays where it is.** The general/ramping split applies to the
prose, not the fixtures. Those genuinely are ramping scenarios, the name is accurate, and
renaming churns paths the document references for no gain. Non-ramping examples, if they
arrive, sit beside it as siblings.

**The ownership table above is copied into `AGENTS.md`** as a convention: check which
document owns a fact before writing it. This does not violate the no-facts rule - which
document owns which *kind* of fact is a pointer, not a fact about the model - and
`AGENTS.md` is the file most likely to be read by whatever writes the next document. The
reasoning stays here; only the table travels.

### The `FRA` region row

`FRA` is **not leftover**, contrary to first impressions. `MFDM.py:212` reads the file
with `header=[0, 1]` and flattens the two rows into names like `"FRA Wind"`, and the
comment at `:208-211` keeps the region deliberately so that multi-region files stay
unambiguous. It is a hook for a feature that never arrived.

Removing it is a schema migration, not a doc edit: it touches `inputs/profiles.csv`, the
parser and its flatten loop, the technology-token matching at `:447-472`, the two further
`profiles.csv` files under `docs/examples/ramping/`, and the run archive - `runstore`
hashes `profiles.csv`, and `runs.py restore` would hand a new parser an old two-row
header. **Deferred to its own ticket**;
[Should profiles.csv keep its region header row?](11-profiles-region-header.md).

`FRA` appears in **no document anywhere** - the only occurrences outside the CSVs are
three comment lines in `MFDM.py`. So there is nothing to strip from the docs. The live
question was what the new input contract should say, and the answer is that it
**documents the two-row header as it actually is**, with one sentence noting the region
row is slated for removal and linking the migration ticket. A contract describing a
format the parser rejects would be worse than no contract: a learner hitting the mismatch
would have no way to tell which of the two was lying.

### Downstream work

Writing and moving the documents. Not done here - the output of this ticket is the
ownership table.
