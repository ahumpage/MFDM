# Does this repo have a triage vocabulary at all?

- **Type**: `wayfinder:grilling` (HITL)
- **Status**: open
- **Assignee**: unclaimed
- **Blocked by**: —
- **Part of**: [Map: Onboarding, documentation and AI readiness](../onboarding_plan.md)

## Question

Two agent-facing documents in this repo contradict each other outright, and `AGENTS.md`
sides with the wrong one.

- `docs/agents/issue-tracker.md` states plainly: *"There are no labels, no comments and
  no number space shared with pull requests."*
- `docs/agents/triage-labels.md` tabulates five labels — `needs-triage`, `needs-info`,
  `ready-for-agent`, `ready-for-human`, `wontfix` — and `AGENTS.md` describes them as
  *"The five canonical triage roles, used as-is."*

No ticket under `docs/planning/` uses any of those five strings. The real ticket
front-matter uses `Type: wayfinder:{research,prototype,grilling,task}` with `(AFK)`/`(HITL)`
and `Status: {open,claimed,resolved,dropped}`.

`triage-labels.md` closes with *"Edit the right-hand column to match whatever vocabulary
you actually use"* — it is an **unedited boilerplate template**. `issue-tracker.md` was
deliberately customised by an earlier ticket; this one was not.

An agent told to apply a label here would invent vocabulary the repo does not use, which
also violates the instruction in `docs/agents/domain.md` to use terms as defined and not
drift to synonyms.

### The related defect

`AGENTS.md` also asserts: *"Single-context: `CONTEXT.md` + `docs/adr/` at the repo
root."* **`docs/adr/` does not exist, and no ADR exists anywhere in the repo.**

Note the two files differ in blame here. `docs/agents/domain.md` says to read ADRs *if
present* and explicitly instructs an agent to proceed silently when they are absent — so
`domain.md` is self-consistent. It is `AGENTS.md` that states a falsehood about the repo.

`domain.md` also illustrates a `src/<context>/docs/adr/` layout; this repo has no `src/`,
so that section is generic template content too.

### What has to be decided

- **Does this repo need a triage vocabulary?** It is single-author with no external
  contributors and a four-state ticket lifecycle that is already working. The honest
  answer may be no — in which case `triage-labels.md` gets deleted and `AGENTS.md`'s
  reference with it.
- **If yes, what are the states**, and how do they relate to the `Status` field that
  already exists? Two overlapping lifecycles would be worse than none.
- **Do ADRs exist in this repo's future?** `model_plan.md` and `ramping_plan.md` both
  say "ADRs only where a decision is hard to reverse" — so the absence may be deliberate.
  But `docs/ramping_semantics.md` records at least three decisions of exactly that kind
  (`SPILL_COST != VOLL`; the dual becomes canonical; the merit-order check demoted from
  error to warning) and they live in a spec rather than an ADR. Either start the
  directory, or correct `AGENTS.md` to stop claiming it exists.
- **Is `docs/agents/domain.md` worth keeping as-is**, given its `src/` illustration does
  not describe this repo, and the skills it names live under `.agents/`, which
  `.gitignore` excludes — so a fresh clone will not have them.

## Decision
