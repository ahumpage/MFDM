# Correct `docs/agents/issue-tracker.md`

- **Type**: `wayfinder:task` (AFK)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Ramping](../ramping_plan.md)

## Question

Nothing to decide; a chore that unblocks nothing but misleads every future session.

`docs/agents/issue-tracker.md` states that issues live in GitHub Issues for
`ahumpage/MFDM` and that all operations go through the `gh` CLI. Its "Wayfinding
operations" section describes maps as GitHub issues, tickets as sub-issues via the
`gh api` sub-issues endpoint, and blocking via GitHub's native issue dependencies.

None of that is true of this repo:

- `gh` is not installed and is not on `PATH`.
- No map has ever been created on GitHub. All three that exist — [Model
  semantics](../model_plan.md), [Dashboard](../dashboard_plan.md) and [this
  one](../ramping_plan.md) — are markdown files under `docs/planning/`, with tickets as
  numbered files in a sibling directory and blocking expressed as a `Blocked by:` line
  in each ticket's front matter.

An agent following the doc as written will fail on its first command, and may conclude
the tracker is broken rather than that the doc is wrong.

Rewrite the "Wayfinding operations" section to describe the local-markdown convention
actually in use: where maps live, the ticket file naming, the front-matter fields
(`Type` / `Status` / `Assignee` / `Blocked by` / `Part of`), how a ticket is claimed and
resolved, and how the frontier is computed by reading the `Blocked by` lines.

Leave the general issue-tracking sections alone unless they are also false — decide
whether the repo has any GitHub issue practice worth keeping, or whether the whole
document should describe local markdown.
