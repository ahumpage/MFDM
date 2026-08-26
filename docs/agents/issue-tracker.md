# Issue tracker: local markdown

Issues, specs and maps for this repo live as **markdown files under `docs/planning/`**.
There is no live issue tracker.

The repo does have a GitHub remote (`ahumpage/MFDM`), but no issue has ever been
filed on it, and the `gh` CLI is not installed and is not on `PATH`. An earlier
version of this document described a GitHub workflow; an agent following it would
have failed on its first command and might reasonably have concluded the tracker
was broken rather than the doc wrong.

If you genuinely need GitHub issues, install `gh` first and update this file.
Until then, everything below is the convention actually in use.

## Layout

```
docs/planning/
  <effort>.md              the map: one file per effort
  <effort>/               the tickets for that effort
    00-<slug>.md
    01-<slug>.md
    ...
```

Tickets are numbered in map order, zero-padded to two digits, with a short
kebab-case slug. The number is the ticket's identity; refer to a ticket as
`<effort>/01` or by its relative link.

Efforts that exist today: `model_plan`, `dashboard_plan`, `ramping_plan`,
`extra_plan`.

## Ticket format

Each ticket file opens with a level-one heading that states the question, then a
front-matter block as a bullet list, then the body.

```markdown
# What does the reported clearing price represent under ramping?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: [How ramping efficiency becomes a cost](02-ramp-cost-form.md)
- **Part of**: [Map: Ramping](../ramping_plan.md)

## Question

...

## Decision

...
```

- **Type** — `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling` or
  `wayfinder:task`. Tag `(AFK)` if an agent can run it unattended, `(HITL)` if it
  needs a human in the loop.
- **Status** — `open`, `claimed`, `resolved` or `dropped`.
- **Assignee** — `unclaimed`, or a name.
- **Blocked by** — markdown links to other ticket files, or an em dash for none.
  This line *is* the dependency graph; there is nothing else to consult.
- **Part of** — a link back to the map.

## Map format

A map is a single markdown file with these sections, in order:

- **Destination** — what "done" looks like for the whole effort.
- **Notes** — domain, conventions, constraints that apply to every ticket.
- **Settled while charting** — premises no ticket may reopen.
- **Decisions so far** — one line per resolved ticket, appended as they close.
- **Not yet specified** — in scope, not yet sharp enough to ticket.
- **Out of scope** — past the destination; returns only as a fresh effort.
- **Origin** — the loose outline the map was charted from, verbatim.

## Operations

- **Publish to the issue tracker** — write a new markdown file under
  `docs/planning/`. A spec becomes a map; a single question becomes a ticket in an
  existing effort's folder.
- **Fetch the relevant ticket** — read the file. Follow its `Part of` link for the
  map's context and its `Blocked by` links for anything it depends on.
- **Compute the frontier** — read every ticket in the effort folder, drop any whose
  `Status` is not `open`, drop any with a blocker that is not `resolved`, drop any
  with an assignee. First in numeric order wins.
- **Claim** — set `Status` to `claimed` and `Assignee` to your name. This is the
  session's first write, so a parallel session can see the ticket is taken.
- **Resolve** — append a `## Decision` section to the ticket recording the answer
  and the reasoning, set `Status` to `resolved`, then append a one-line summary
  with a link to the map's **Decisions so far**.
- **Drop** — set `Status` to `dropped` and say why in the body. Do not delete the
  file; a dropped ticket is a decision and future readers need it.
- **Close an effort** — when every ticket is resolved or dropped, produce whatever
  the map's Destination names, and link to it from the map.

Because the tracker is files in git, every operation is an ordinary edit and the
history is the audit trail. There are no labels, no comments and no number space
shared with pull requests.

## Pull requests as a triage surface

**PRs as a request surface: no.** This is a single-author onboarding repo with no
external contributors.
