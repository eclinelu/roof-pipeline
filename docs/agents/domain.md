# Domain Docs

How the engineering skills should consume this repo's domain documentation when
exploring the codebase.

Layout: **single-context**. One `CONTEXT.md` at the repo root, one `docs/adr/`
directory. There are no monorepo signals here; `roofkit` is a single Python
package.

## Before exploring, read these

- **`CONTEXT.md`** at the repo root, and
- **`docs/adr/`**, specifically the ADRs that touch the area you are about to work in.

If either does not exist, **proceed silently**. Do not flag their absence and do
not suggest creating them upfront. The `/domain-modeling` skill (reached via
`/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when
terms or decisions actually get resolved.

## This repo already has a decision record, and it wins

`decisions/` (append only, one file per entry, indexed by `decisions/README.md`)
and `STATE.md` are the authority for what this project has decided and where it
stands. `CLAUDE.md` states that precedence explicitly. ADRs under `docs/adr/`
are for architectural decisions in the coding sense: module seams, interface
shapes, dependency choices. They do not replace `decisions/` and they never
override it.

Rule of thumb:

| Kind of decision | Where it goes |
| --- | --- |
| Method, threshold, parameter, experiment outcome, phase change | `decisions/`, via the decision-log skill |
| Code structure: where a seam goes, what a module owns, why a library | `docs/adr/` |
| Current phase, blocker, next action | `STATE.md` |

When an ADR and a `decisions/` entry disagree, `decisions/` is correct and the
ADR is stale. Fix the ADR in the same pass and say which layer you changed.

## File structure

```
/
├── CONTEXT.md
├── decisions/          <- the project decision log, authoritative
├── STATE.md
├── docs/
│   ├── adr/
│   │   ├── 0001-io-py-is-the-only-file-format-seam.md
│   │   └── 0002-....md
│   └── agents/         <- this file and its siblings
└── roofkit/
```

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal,
a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Do not drift
to synonyms the glossary explicitly avoids.

If the concept you need is not in the glossary yet, that is a signal: either you
are inventing language the project does not use (reconsider) or there is a real
gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than
silently overriding:

> _Contradicts ADR-0007 (io.py is the only file-format seam), but worth
> reopening because..._
