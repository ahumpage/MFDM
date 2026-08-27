# Correct `docs/agents/issue-tracker.md`

- **Type**: `wayfinder:task` (AFK)
- **Status**: resolved
- **Assignee**: Alice (with OpenCode)
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

## Decision

`docs/agents/issue-tracker.md` rewritten to describe the local-markdown convention
actually in use.

**The whole document now describes local markdown, not just the Wayfinding
section.** The ticket left this open. The general sections were as false as the
Wayfinding ones — "publish to the issue tracker" said *create a GitHub issue*, and
"fetch the relevant ticket" said `gh issue view` — so scoping the fix to one
section would have left an agent failing on its first command anyway.

The repo does have a GitHub remote (`ahumpage/MFDM`), which the doc now
acknowledges while stating that no issue has ever been filed on it and `gh` is not
installed. That is more useful than silence: it tells a future reader the remote
is not a tracker they have failed to find.

The rewrite covers: the `docs/planning/` layout, ticket file naming, the
front-matter fields, the map sections, and the operations — publish, fetch,
compute the frontier, claim, resolve, drop, close an effort — expressed as file
edits. It notes that the `Blocked by` line *is* the dependency graph and there is
nothing else to consult.

**`PRs as a request surface` stays `no`**, now with the reason: single-author
onboarding repo, no external contributors.

`AGENTS.md` updated to match, since it repeated the same false claim in one line.
