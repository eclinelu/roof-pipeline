### 2026-08-18: TOOLING RESET: the superpowers skill set, `graphify`, `task-observer` and `session-closeout` are removed at every level, and the instructions that invoked them are deleted

**Decision:** Emmett is replacing his agent skill environment wholesale with a
different author's set. Removed in this session:

- the 14 superpowers skills installed loose at user scope
  (`~/.claude/skills/`): brainstorming, dispatching-parallel-agents,
  executing-plans, finishing-a-development-branch, receiving-code-review,
  requesting-code-review, subagent-driven-development, systematic-debugging,
  test-driven-development, using-git-worktrees, using-superpowers,
  verification-before-completion, writing-plans, writing-skills;
- the same 14 again as the `superpowers@claude-plugins-official` v6.2.0 plugin,
  which was installed at PROJECT scope for this repo. Its `enabledPlugins` entry
  in `.claude/settings.json` is gone, its registry entry is gone, and its cache
  is deleted. The plugin also carried a SessionStart hook that injected
  `using-superpowers` into every session; removing the plugin removes the hook;
- `graphify`, `task-observer` and `session-closeout` at user scope.

The instructions that called for them are deleted in the same pass, because a
standing instruction pointing at a skill that no longer exists makes the agent
fail a documented workflow every session. Global `~/.claude/CLAUDE.md` is now
empty: its entire contents were the task-observer session-start directive, the
session-closeout end-of-session directive, and the `/graphify` trigger. The two
plan documents under `docs/superpowers/plans/` carried a
`REQUIRED SUB-SKILL: Use superpowers:...` directive line; that line is replaced
with a plain instruction to work the plan task-by-task.

KEPT, and not part of this reset: the three project skills `decision-log`,
`odm-run` and `visual-pass`, which are specific to this pipeline and have no
equivalent in the incoming set; and the user-scope `find-skills`,
`market-research`, `market-sizing-analysis` and `pdf`.

**Why:** Emmett's stated reason: a full reset of his skills ahead of switching to
Matt Popock's set. He named the removals himself and named the documentation
cleanup as part of the same request. No claim is made here about the merits of
either skill set; this entry records what changed and what still points at it.

**What was deliberately NOT changed:**

- `decisions/2026-07-26-decision-entries-need-no-approval.md` still discusses
  `session-closeout`. It is append-only and is a true record of what was decided
  on that date. It is now historical rather than operative; the skill it flags
  no longer exists.
- The memory file `reserve-deliberate-acts-to-emmett.md` still mentions a
  session-closeout commit as a past event. Rewriting a historical account to
  erase a tool name would distort the record.
- `graphify-out/` (untracked, gitignored) is left on disk. It is generated output
  from the removed skill, not documentation calling for it. Deleting it is
  Emmett's call, not a side effect of removing the tool.
- The `docs/superpowers/` DIRECTORY NAME is unchanged. It is a label on
  historical work products, not a directive; renaming it would rewrite paths
  referenced from inside those documents for no functional gain.
- The `claude-plugins-official` marketplace clone under `~/.claude/plugins/
  marketplaces/` is left in place. It is a downloaded catalog of 18 uninstalled
  plugins; none of them load.

**Cost if wrong:** Low and reversible. Every removed skill is re-installable from
its source, and the deleted global `CLAUDE.md`, the two deleted memory files and
the pre-edit memory index were copied to the session scratchpad before deletion.
The real exposure is the gap between now and installing the replacement set: the
project's own working rules that lived in those skills, specifically the
end-of-session wind-down and the observation log, are simply not running until
something replaces them. The `decision-log` skill survives, so the record this
entry belongs to is unaffected.
