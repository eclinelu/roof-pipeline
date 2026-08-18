# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those
roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (for example "apply the AFK-ready triage label"),
use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.

All five labels EXIST in `eclinelu/roof-pipeline` as of 2026-08-18, verified with
`gh label list`. `wontfix` is GitHub's default label with its description reset to
"Will not be actioned"; the other four were created for this scheme. No
`gh label create` step is needed before applying them.
