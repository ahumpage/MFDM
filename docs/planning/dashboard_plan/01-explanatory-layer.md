# The explanatory layer: what the dashboard explains, and where

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: [How is mathematical notation rendered in Dash?](00-research-dash-math.md)
- **Part of**: [Map: Dashboard next iteration](../dashboard_plan.md)

## Question

There is no formula anywhere in the UI today. What exists is scattered and partial:
prose about LP optimality in the QA tab's `Details` block (dashboard.py:1064-1073),
marginal-cost figures embedded in trace names (dashboard.py:354) and plant checklist
labels (dashboard.py:921-922), KPI sub-captions naming quantities such as "the LP
objective" (dashboard.py:873) and "market - production" (dashboard.py:877), and a
statement of the optimality conditions that lives only in a source comment nobody
reading the dashboard will ever see (dashboard.py:560-572).

Decide:

- **Which formulae earn a place.** Candidates: marginal cost (`fuel/efficiency + VOM`),
  the LP objective, the energy balance, the clearing price as the marginal plant's
  cost, producer surplus. All of them is a textbook; none is the status quo.
- **Where explanation lives.** A dedicated "how this works" tab, an expandable block
  per chart, hover tooltips, or prose captions under each figure. This trades against
  the "Not yet specified" question of whether three tabs survive.
- **Who is reading.** A viewer who already knows dispatch needs different text from
  one who does not. The repo is onboarding material, which argues for the latter, but
  a dashboard heavy with tutorial text is worse for repeated daily use.
- **Prose or notation**, informed by the research ticket.
- **Whether the explanation is static or reflects the run.** "Coal set the price in
  412 of 744 hours because..." is far more useful than a generic formula, and much
  more work.

Pin the vocabulary while you are here: *clearing price*, *shadow price*, *marginal
cost*, *producer surplus*, *curtailment* all appear in the UI with no definition.
Write them into `CONTEXT.md`.
