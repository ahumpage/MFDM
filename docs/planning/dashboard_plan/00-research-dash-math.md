# How is mathematical notation rendered in Dash?

- **Type**: `wayfinder:research` (AFK)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Dashboard next iteration](../dashboard_plan.md)

## Question

[The explanatory layer](01-explanatory-layer.md) has to choose between rendered
mathematics and plain prose. That choice needs facts this repo does not contain — the
dashboard has no rendered maths anywhere today, only prose in the QA tab
(dashboard.py:1064-1073).

Establish from primary sources (Dash and Plotly documentation):

- Does `dcc.Markdown` support LaTeX, and what does enabling it cost — a `mathjax`
  flag, an extra CDN dependency, a bundle-size or offline-use penalty?
- Can Plotly figure titles, axis labels and annotations carry the same notation, or
  is it Markdown components only?
- Are there known rendering caveats (flicker on callback re-render, MathJax loading
  asynchronously after the component mounts) that would make it awkward in a
  callback-driven layout like this one?
- What is the plain alternative — Unicode subscripts and prose — and where does it
  stop being readable for expressions like the marginal-cost formula and the LP
  objective?

Findings go in `docs/research/dash-math-rendering.md`; link it from this ticket.
