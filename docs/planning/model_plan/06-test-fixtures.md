# The hand-solvable test fixtures

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: [The QA pass](05-qa-report.md)
- **Part of**: [Map: Model semantics](../model_plan.md)

## Question

Charting settled the shape: 2-plant / 3-hour LPs with arithmetic you can do on paper,
not golden-file regression. This ticket writes down the actual scenarios and their
expected numbers, so implementing them is transcription rather than design.

- **Which scenarios?** At minimum: baseline merit order, one plant at its cap, a tie
  on marginal cost, a profiled plant limited by its resource, scarcity, zero demand.
  Confirm the set and cut any that test the solver rather than the model.
- **Expected values.** For each: dispatch per plant per hour, both price columns,
  total production cost. Worked by hand in the spec — this is the part that catches
  a wrong model, and the part an implementation session cannot invent for itself.
- **How fixtures reach the model.** `load_data` reads fixed paths under `inputs/`
  (MFDM.py:75-78). A test needs to point the model at different CSVs, which means
  either parameterising those paths or building `par` directly and skipping
  `load_data`. The second tests less but changes nothing.
- **Where tests live and what runs them.** No `tests/` directory exists; pytest is not
  currently a dependency.
