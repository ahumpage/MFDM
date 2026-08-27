Start reading in model/MFDM.py, this is the main model which the repo is based around.
The purpose of the repo is to build a power dispatch model from the ground up, adding in
complications and adjusting, as part of onboarding training.
The model should be built using PuLP.
The code should be readable and easy to follow, so that it can be used as a learning tool.

Read CONTEXT.md before using a term that sounds domain-specific. Several are deliberate
collision-resolutions and the everyday meaning is the wrong one: spill is not
curtailment, and the clearing price is not the highest running cost.

Layout, run order, install and command-line options are in README.md. This file holds no
facts about the repo, only pointers and conventions; if you need to state a fact, put it
in the document that owns it.

## Which document owns which fact

Before writing a fact into a document, check here that it belongs there. Reasoning behind
this table is in docs/planning/onboarding_plan/01-doc-set-ownership.md.

    README.md               getting started, and the model as maths: sets, parameters,
                            objective, constraints. Also the directory map, the
                            command-line options, the LoL and SPILL_COST values, and
                            troubleshooting. Not: why the model is built this way.
    docs/model_semantics.md what the model means. Prices, the merit-order check's
                            status, spill vs curtailment, ramping, the CSV contract
                            for inputs and outputs, worked examples, known gaps.
                            Not: the maths, and not how to run it.
    CONTEXT.md              vocabulary, one entry per term, what a term denotes.
                            Not: justification. If an entry needs a worked example it
                            belongs in docs/model_semantics.md with a pointer.
    AGENTS.md               this file. Conventions and pointers, and no facts at all.

    docs/examples/ramping/  input folders for the worked examples. Run with
                            model/MFDM.py --inputs <folder> --results <folder>

## Agent skills

### Issue tracker

Local markdown under `docs/planning/`. There is no live issue tracker and `gh` is not
installed. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, used as-is. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
