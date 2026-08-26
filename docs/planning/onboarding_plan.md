# Map: Onboarding, documentation and AI readiness

- **Status**: open
- **Charted from**: a GitHub-issue-shaped outline, reproduced verbatim under **Origin**

## Destination

A repo a new Windows user can clone, install, run and understand **without reading
`model/MFDM.py`**, and that an agent can navigate from `AGENTS.md` alone — with the
model, the archive and the dashboard agreeing on what a scarce run actually served.

This map is **planning only**. It is done when nothing is left to decide: every ticket
resolves a decision, and the build that follows is a handoff, not part of the map. If a
session feels the pull to just write the README, that is the signal the map has reached
its edge.

## Notes

- **Domain**: least-cost economic dispatch. Read `CONTEXT.md` before using a term that
  sounds domain-specific; several are deliberate collision-resolutions (spill vs
  curtailment, clearing price vs highest running cost).
- **The model as it stands**: `README.md` (the maths), `docs/ramping_semantics.md` (the
  reasoning). Both are current and accurate — see *Settled while charting*. Note the
  latter is to be renamed `docs/model_semantics.md` and reordered, per
  [Which document owns which fact?](onboarding_plan/01-doc-set-ownership.md).
- **Tracker**: local markdown, `docs/agents/issue-tracker.md`. No `gh`, no labels.
- **Platform**: Windows, PowerShell. Commands in tickets should be runnable there.
- **Default skills** for a ticket that names none: `grilling` + `domain-modeling`.
- Several tickets touch the same files. Frontier width is six, so expect concurrent
  sessions; claim before working.

## Settled while charting

The Origin outline was written against an older tree. An audit of HEAD (`50fbaf4
ramping added`) established the following. **No ticket may reopen these**; where a
ticket and the Origin disagree, the ticket is right.

- **Ramping and spill are implemented, not planned.** `build_and_solve` carries
  `ramp_up`/`ramp_down` variables with the rate limit as their `upBound`, a `ramp_cost`
  premium in the objective, a `spill[t]` variable priced at `SPILL_COST = 1000.0`, and a
  `forced_down` slack on the ramp-down constraint. Both result CSVs carry ramp columns.
  The Origin's instruction to describe these as future work is **inverted**.
- **`README.md`'s maths is already correct.** Verified term by term against
  `build_and_solve`, including the subtle `forced_down` allowance. The README's real
  weaknesses are first-run affordances — no install command, no directory map, no
  troubleshooting, no `--inputs`/`--results`, no values for `VOLL`/`SPILL_COST`, no
  mention of `run_archive/` — not staleness.
- **`CONTEXT.md` exists** and is strong. The Origin's claim that it does not is false.
- **`docs/agents/issue-tracker.md` has already been corrected.** It documents the
  local-markdown convention and states plainly that `gh` is not installed. `AGENTS.md`
  matches it. That item of the Origin is **done**.
- **`docs/adr/` does not exist**, and no ADR exists anywhere in the repo — yet
  `AGENTS.md` asserts it does.
- **`docs/agents/triage-labels.md` is an unedited boilerplate template** and contradicts
  `issue-tracker.md` outright: one says "there are no labels", the other tabulates five,
  and `AGENTS.md` calls them "used as-is". The Origin missed this.
- **The KPI defect is in four places, not two**: `runstore.compute_kpis`,
  `dashboard.window_kpis`, and also `dashboard.build_kpis`. Only `MFDM.print_report` is
  right about energy served — and it is inconsistent with itself, printing
  `demand - unserved` three lines above a load-weighted price divided by `demand`.
- **No archived run has non-zero unserved energy.** All 22 manifests report the same
  `energy_served_mwh`; the 12 newer runs carry an `Unserved Energy (MWh)` column summing
  to exactly 0 and the 10 older ones predate it. Correcting `compute_kpis` would change
  **no existing archived value**. The compatibility question is far cheaper than
  `extra_plan.md` assumed.
- **No dependency file of any kind exists** — not `requirements.txt`, `pyproject.toml`,
  `environment.yml`, or any lockfile. The sole declaration anywhere is one line of prose
  in `README.md`. There are no tests, no test config, no CI, and no `.ps1`/`.bat`/`Makefile`.
  *(Dependency half addressed — `requirements.txt` now exists. Tests, config and CI still
  do not.)*
- **`docs/ramping_semantics.md` is already doing the job of the missing
  `docs/model_semantics.md`.** Its price definition, output-schema table and
  merit-order-check status are model-wide, not ramping-specific. Writing model semantics
  is largely a **rehoming** problem.
- **`model/MFDM.py` is more testable than it looks.** `build_parameters`,
  `build_and_solve`, `build_results` and `build_summary` are directly callable with
  in-memory arguments. Only `load_data()` is bound to module globals, which
  `use_directories` mutates. The `check_*` functions and `report` return `None` and
  communicate solely by `print`. `MFDM.py` imports no dash and no plotly.
- **A `VOLL` -> `LoL` rename sits uncommitted in the working tree**, touching user-facing
  print strings, while `CONTEXT.md` defines only `VOLL`. *(Stale: the rename was in fact
  already committed in `b42885a`. Settled by [VOLL or LoL?](onboarding_plan/02-voll-or-lol.md)
  — `LoL` throughout, and `CONTEXT.md` now defines it.)*

## Decisions so far

- **The dependency contract.** A single flat, exactly pinned `requirements.txt` at the
  repo root; python 3.8 stated in the README Quickstart and the file; `git` declared as a
  comment; CBC deliberately undocumented; no venv recommended. See
  [What are this project's dependencies, and what declares them?](onboarding_plan/00-dependency-contract.md).
- **The documentation set.** Four documents, no more: `README.md` owns getting started
  and the maths, `docs/model_semantics.md` (renamed from `ramping_semantics.md`) owns
  meaning plus the input and output CSV contract, `CONTEXT.md` owns vocabulary,
  `AGENTS.md` owns conventions and pointers and no facts at all. See
  [Which document owns which fact?](onboarding_plan/01-doc-set-ownership.md).
- **`LoL`, not `VOLL`.** One name for the $8,300/MWh price of lost load, spelled `LoL`
  everywhere in code and live documents; the research note keeps the source's `VoLL`, and
  planning documents keep their historical wording. Owner's preference, taken over the
  standard-term argument. See [VOLL or LoL?](onboarding_plan/02-voll-or-lol.md).

## Not yet specified

In scope, but not yet sharp enough to ticket. Graduates as the frontier advances.

- **Dashboard work beyond the KPI fix.** `dashboard.py` is 1992 lines and the Origin
  touches it only through scarcity accounting. Whether anything else there serves the
  destination is unclear until [Which document owns which fact?](onboarding_plan/01-doc-set-ownership.md)
  settles what a user is expected to learn from the dashboard versus from a document.
- **Repository hygiene.** `saved_plots/` holds six PNGs that no code in the repo
  generates (there is no matplotlib import anywhere); `docs/plan.docx` is referenced by
  nothing; a root `__pycache__` holds CPython 3.8 artefacts from when the modules lived
  at the root. Whether these are deleted, documented or ignored is one question or three.
- **What is committed to git.** `results/` and `run_archive/` are deliberately tracked;
  whether that survives contact with a new user cloning the repo is untested.
- **How the run archive is documented for humans.** `run_archive/runs.py` is the primary
  human interface to the archive — `list`, `show`, `diff`, `restore`, `prune` — and is
  named in neither `README.md` nor `AGENTS.md`. Likely graduates off
  [Which document owns which fact?](onboarding_plan/01-doc-set-ownership.md).
- **What happens when `git` is absent.** `runstore.git_state()` shells out to `git` via
  `subprocess`, so the default archiving path degrades to a warning without it. The
  *declaration* half is settled by
  [What are this project's dependencies, and what declares them?](onboarding_plan/00-dependency-contract.md),
  which records `git` as a comment in `requirements.txt` pointing at `--no-archive`.
  What the code *should* do when `git` is missing — warn, fail, or archive without a
  commit hash — is still open.
- **CI.** Nothing exists. Whether a test command is worth automating depends on what
  [Which cases must the test suite prove?](onboarding_plan/10-test-cases.md) produces.- **MCP**, carried over from `extra_plan.md`: "what is an MCP and figure it out / apply
  it". Too loose to ticket, and possibly out of scope once the destination is applied.

## Out of scope

Past the destination. Returns only as a fresh effort, never by graduating.

- **New model features**: ramping, spill, unit commitment, storage, minimum generation,
  negative prices. Note that ramping and spill are out of scope because they are
  **already built**, not because they are deferred.
- **Splitting code into many small files to reduce line count.** The model stays
  readable as a learning tool. Seams between inputs, model, results, dashboard, archive
  and docs may improve; file count is not the target.
- **Platform-specific AI client configuration.** No `.cursorrules`, no
  `.github/copilot-instructions.md`, no client-specific skill directories, until the
  project chooses which clients it actually wants to support. Shared facts stay in
  `AGENTS.md`.
- **Pull requests as a triage surface.** Already ruled out in
  `docs/agents/issue-tracker.md`: single-author onboarding repo, no external
  contributors.

## Origin

The loose outline this map was charted from, verbatim. Read it knowing that *Settled
while charting* corrects it in eight places.

> # Improve onboarding, documentation, and AI readiness
>
> > **Skills used to prepare this issue**
> >
> > - `codebase-design` - reviewed modules, seams, depth, locality, and testability.
> > - `improve-codebase-architecture` - reviewed architectural friction and deepening opportunities.
> > - `aer-repo-ai-audit` - reviewed repository guidance, setup, reproducibility, and AI navigability.
> > - Read-only exploration agents - reviewed the model, dashboard, archive, documentation, and first-run journey.
>
> ## Why this matters
>
> MFDM already has a useful model workflow:
>
> ```text
> inputs -> model -> results -> dashboard
> ```
>
> It also has good inline explanations, run archives, and useful QA checks.
>
> However, a new user cannot reliably set up and run the project from a fresh clone without reading source code and planning documents. An AI agent has similar problems: some guidance is stale, key contracts are implied rather than documented, and there is no automated test command to confirm a safe change.
>
> This issue improves the experience of learning, running, changing, and checking the model. It should make the repo easier to use without hiding the model logic that makes it valuable as onboarding material.
>
> ## Goal
>
> A new Windows user should be able to:
>
> 1. Clone the repository.
> 2. Install the required Python packages.
> 3. Run the dispatch model.
> 4. Open the dashboard.
> 5. Understand what the model is doing and what its outputs mean.
> 6. Make a small input change and compare the result with an earlier run.
> 7. Run a small set of checks before trusting a code change.
>
> An AI agent should be able to find the same information through clear repository guidance, rather than inferring it from large source files or stale planning notes.
>
> ## Work to do
>
> ### 1. Add a clear setup and first-run path
>
> Add a tracked dependency definition for the packages used by the project:
>
> - `numpy`
> - `pandas`
> - `pulp`
> - `dash`
> - `plotly`
>
> Also document:
>
> - supported Python version;
> - how to create and use a virtual environment;
> - what PuLP/CBC solver support is expected;
> - what to do if the solver is unavailable.
>
> Add a simple Windows-oriented way to run the normal workflow:
>
> 1. Run the model.
> 2. Stop if the model fails.
> 3. Only then start the dashboard.
> 4. Clearly show the dashboard URL and how to stop it.
>
> The helper should coordinate existing entry points. `model/MFDM.py` must remain independent of Dash and must not start the dashboard itself.
>
> Decide whether the helper should pass through the model options:
>
> - `--label`
> - `--notes`
> - `--no-archive`
>
> ### 2. Rewrite the README for a new user
>
> Make `README.md` the main starting point for a human user.
>
> It should include:
>
> - what the project is;
> - the current model scope;
> - setup instructions;
> - first-run commands;
> - expected success messages and files;
> - how to start and use the dashboard;
> - a short directory map;
> - where inputs, results, and archived runs live;
> - basic troubleshooting.
>
> The README must accurately describe the model as it exists today.
>
> Current behaviour includes:
>
> - least-cost continuous dispatch;
> - plant capacity limits;
> - solar and wind resource profiles;
> - marginal costs based on fuel cost, efficiency, and variable operating cost;
> - unserved energy priced at VoLL when demand cannot be met;
> - implicit renewable curtailment;
> - result and merit-order checks.
>
> Ramping and spill are planned work. They must not be described as active model features until they are implemented.
>
> ### 3. Explain the model without requiring source-code archaeology
>
> Create a short model-semantics document that explains:
>
> - the objective function;
> - the energy-balance and capacity constraints;
> - how marginal cost is calculated;
> - how solar and wind availability works;
> - why scarcity is represented as unserved energy at VoLL;
> - what curtailment means;
> - the difference between clearing price and shadow price;
> - what current QA checks are trying to prove;
> - which assumptions will change once ramping is introduced.
>
> A learner should be able to understand the reasoning behind a result before reading the full implementation in `model/MFDM.py`.
>
> ### 4. Document input and output CSVs
>
> Document the input files clearly:
>
> - required columns;
> - units;
> - expected formats;
> - profile-file two-row header;
> - demand and profile-hour relationship;
> - supported profiled technologies;
> - validation that the model performs.
>
> Document the result files clearly:
>
> - `results/dispatch_results.csv`;
> - `results/plant_summary.csv`;
> - the meaning and unit of important columns;
> - the difference between production cost and market cost;
> - clearing price versus shadow price;
> - unserved energy and curtailment.
>
> These CSVs are a shared interface between the model, dashboard, and archive tools. Their meaning should not require searching through several source files.
>
> ### 5. Add a safe learning feedback loop
>
> Add a test runner and document one command for running tests.
>
> Add small, hand-solvable cases rather than relying on archived-output snapshots. At minimum, cover:
>
> - normal merit-order dispatch;
> - an hour where a plant reaches its capacity;
> - equal-cost plants;
> - resource-limited solar or wind;
> - scarcity and VoLL;
> - zero demand.
>
> Tests should check visible model behaviour through the model interface, rather than depending on internal implementation details.
>
> Tests should use separate fixtures or temporary input locations so they do not overwrite the live `inputs/` directory.
>
> ### 6. Correct and simplify repository guidance
>
> Update guidance so it matches the repository as it is actually used.
>
> - Correct the tracker documentation: `gh` is not installed on the current development machine, and current planning maps/tickets are local Markdown files under `docs/planning/`.
> - Update `AGENTS.md` to match that tracker guidance.
> - Clarify that `CONTEXT.md` and `docs/adr/` should be read if present. They do not currently exist.
> - Replace fragile planning-document line-number references with stable references to functions or named sections.
> - Add clear pointers in `AGENTS.md` to setup, model semantics, result schema, and test instructions as those documents become available.
>
> Do not add platform-specific AI configuration unless the project chooses the AI clients it actually wants to support. Keep shared repository facts in `AGENTS.md`; add thin client-specific guidance only where it is needed.
>
> ### 7. Fix scarce-run accounting before relying on comparisons
>
> The model correctly treats energy served as demand minus unserved energy. The archive and dashboard comparison calculations currently use total demand as energy served, which will become wrong when a scarce run is archived.
>
> Update the archive and dashboard so that they agree with the model on:
>
> - energy served;
> - unserved energy;
> - load-weighted price.
>
> Decide how to handle existing archived manifests:
>
> - update them;
> - version the KPI definition; or
> - keep old values with a clear compatibility note.
>
> Consider adding `unserved_mwh` to archived KPIs and comparison views so scarcity is visible rather than hidden.
>
> See `docs/planning/extra_plan.md` for the existing notes.
>
> ## Out of scope
>
> This issue does not implement:
>
> - ramping;
> - spill;
> - unit commitment;
> - storage;
> - minimum generation;
> - negative prices.
>
> It also does not call for splitting code into many small files simply to reduce line count. The model should remain readable as a learning tool. Changes should improve the useful seams between inputs, model results, dashboard, archive tools, and documentation.
>
> ## Acceptance criteria
>
> - A new Windows user can follow the README from a fresh clone to install dependencies, run the model, and open the dashboard.
> - The normal run helper does not open the dashboard after a failed model run.
> - README descriptions and equations match the current executable model.
> - The model's reasoning is documented outside the implementation.
> - Input and output CSV contracts are documented.
> - A documented automated test command runs small hand-solvable model cases.
> - Repository guidance no longer directs agents to an unavailable `gh` workflow.
> - A scarce run produces consistent energy-served and load-weighted-price values in the model, archive, and dashboard.
> - Planning documents use stable navigation references rather than stale source line numbers.
>
> ## Suggested delivery order
>
> 1. Add dependencies, supported Python version, and correct README basics.
> 2. Add the first-run helper.
> 3. Add model-semantics and CSV-contract documentation.
> 4. Add hand-solvable automated tests.
> 5. Correct repository and AI-agent guidance.
> 6. Fix scarcity accounting and decide archive-manifest compatibility.
