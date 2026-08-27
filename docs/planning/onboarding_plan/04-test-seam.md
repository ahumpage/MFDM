# How does a test drive this model?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Onboarding, documentation and AI readiness](../onboarding_plan.md)

## Question

There are no tests, no test config and no CI. The Origin asks for a test runner, one
documented command, and small hand-solvable cases that "check visible model behaviour
through the model interface, rather than depending on internal implementation details".

That last phrase is the whole difficulty: **`model/MFDM.py` does not have a single
interface a test can drive.** Decide what the seam is.

### What the audit found

The file is more testable than its size suggests, but the seams are uneven:

- **Directly callable with in-memory arguments**, no file I/O: `build_parameters(plants,
  fuel, demand, profile)`, `build_and_solve(params)`, `build_hourly_results(params, prob, gen,
  unserved, spill)`, `build_plant_summary(params, results)`, plus `dispatch_ceiling`,
  `dispatch_floor`, `check_horizon`, `find_column`, `build_profile_factors`,
  `name_last_in_stack`.
- **Bound to module globals**: `load_data()` takes no arguments and reads the six path
  constants. `use_directories(inputs, results)` mutates them via `global`. Its docstring
  states this is deliberate — it keeps the common case free of plumbing.
- **Observable only through stdout**: `warn_nonpositive_demand`, `warn_capacity_shortfall`,
  `warn_merit_order_departures` and `report` all return `None` and communicate exclusively by
  `print`. The merit-order check, the objective reconciliation and the energy-balance
  check — the three things most worth asserting on — are all in this group.
- **`main(argv=None)` returns `None`.** It parses args, mutates globals, writes CSVs and
  prints. There is no in-memory entry point that takes inputs and hands back results.
- **Import has side effects**: importing `MFDM` inserts `run_archive/` onto `sys.path`
  and imports `runstore`.
- Archiving is skipped when `--inputs` or `--results` is passed, so a test using custom
  folders will not pollute `run_archive/` — but a test that forgets will.

The two folders under `docs/examples/ramping/` are the closest thing to a suite already:
runnable fixtures with hand-verified expected numbers written out in prose, but no
assertions.

### What has to be decided

- **What is "the model interface" for test purposes?** Three candidates:
  1. **Compose the pipeline** — `build_parameters` -> `build_and_solve` -> `build_hourly_results`.
     No file I/O, fast, but a test then knows the four-stage shape, which is an
     implementation detail that ramping already changed once.
  2. **Run `main()` against a fixture directory** and read the written CSVs. Closest to
     what a user does, exercises `load_data` and the CLI, but slow and touches disk.
  3. **Add a new entry point** — something like `run(inputs_dir) -> (results, summary)` —
     that both `main` and tests call. Deepens the module, at the cost of a new function
     whose only caller outside `main` is the test suite.
- **What happens to the print-only checks?** Capture stdout and assert on strings
  (fragile, but zero production change); have them return a structured result that
  `report` formats (a real deepening, and a change to production code inside a
  planning-only map); or leave them untested.
- **Where do fixtures live?** `docs/examples/ramping/` already holds two, referenced from
  a document. A `tests/fixtures/` directory would duplicate that pattern. Can the worked
  examples become the fixtures, so the document and the suite cannot drift apart?
- **Isolation.** How does a test guarantee it never writes to `inputs/`, `results/` or
  `run_archive/`, given that `use_directories` mutates module globals and a second test
  in the same process inherits them?
- **Runner and command.** pytest is the default assumption; confirm it, decide where its
  config lives, and decide the one command that goes in the docs.

This is a design decision, not an investigation — the investigation is above.
[Which cases must the test suite prove?](10-test-cases.md) waits on it.

## Decision
