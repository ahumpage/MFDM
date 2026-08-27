# When may the shadow price differ from the marginal plant's cost?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Model semantics](../model_plan.md)

## Question

The QA list asks that "shadow price should match marginal cost". The model already
contradicts this: `build_hourly_results` counts hours where the dual and the merit-order
price differ by more than `1e-4` and prints them as an expected note, not an error
(MFDM.py:400-403), on the grounds that they diverge in degenerate hours where a plant
sits exactly on its cap.

So an equality assertion would fail exactly where divergence has already been
accepted. Decide which is true:

- Divergence is **expected** in degenerate hours — then the QA check needs a rule
  that distinguishes acceptable divergence from a bug. What is that rule? "Only in
  hours where some plant is exactly at its availability" is checkable; "some hours"
  is not.
- Divergence is **always a bug** — then the current note is masking a real problem
  and the merit-order price calculation needs revisiting.

Worth pinning the vocabulary too: *clearing price*, *shadow price* and *marginal cost*
are used loosely across the code and the QA list. Write them into `CONTEXT.md`.
