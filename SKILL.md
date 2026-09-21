---
name: safe-harbor
description: Close a Claude Code session cleanly, or stop on purpose before a usage, token, or budget limit cuts work off mid-task. Use whenever the user signals the session is ending, in any wording or language ("wrap up", "let's stop here", "that's it for today", "cierro", "lo dejamos", "hasta aquí", "por hoy", "cierra la sesión"), when a budget you were given is nearly spent, or when limit or rate errors start appearing. Checkpoints progress, writes a resume-ready HANDOFF, updates memory only if it changes future behavior, cleans temp state, and ends with a fixed close report.
---

# Claude safe-harbor

Bring in-flight work to a clean, resumable stop. Most of the time that stop is an ordinary end of session. Sometimes it is a limit about to cut you off. The procedure is the same either way, and it exists so the next session starts from a HANDOFF instead of re-deriving everything.

## When to run it

- The user signals the end of the session, in any wording: "wrap up", "let's leave it here", "cierro", "lo dejamos por hoy", "hasta aquí".
- A budget you were handed is roughly 90% spent, or limit or rate errors start showing up.
- Before launching expensive multi-agent work, to confirm there is headroom.

You cannot read the live usage percentage from inside a session; it is enforced on the server. So this skill runs on the user's signal or on a budget set up front. An optional local estimator is described in `references/usage-estimator.md`. Read that file only if the user asks about estimating usage.

## The harbor procedure

1. **Stop launching new work.** No new agents, no new long-running tasks.
2. **Inventory.** What is done, what is in flight, what is queued. For a multi-agent run, which lanes finished and which were cut off. Check for uncommitted changes, open worktrees, background tasks, and temp files in the job directory.
3. **Checkpoint everything.**
   - Finished unit: commit and push. Open a PR only if the project uses them.
   - In-flight unit: a WIP commit on its own branch, or a precise note of the file and the point where it stopped. Never leave uncommitted work as the only copy.
   - Data or corpus work: do not merge half-verified output. Mark it partial and record what is left to check.
   - If the user runs git themselves, write the exact commands and hand them over instead of running them, and say that nothing is saved until they run them.
4. **Write or update the HANDOFF** in a durable place: the repo's docs, a documents folder, never a temp dir. Template in `references/handoff-template.md`. If the project already has a HANDOFF, append a dated close section instead of starting a new file.
5. **Persist memory, only what passes the test.** Before writing, ask: would the next session do anything differently for knowing this? A decision, a pending state, a trap: save it. "This got done": skip it, the HANDOFF covers resumption. Often the durable facts were saved during the work; then this step is a no-op, and you say so in the report.
6. **Clean up**, only after the work above is captured: throwaway worktrees, background tasks, temp files.
7. **Close report.** Always end with this block, in the user's language, every line present. Write "nothing" when there is nothing; never drop a line.

```
safe-harbor close
- Git: <branch; commits pushed / commands handed to the user / nothing to save>
- HANDOFF: <path, or "unchanged">
- Memory: <file updated, or "nothing new that changes behavior">
- Cleanup: <worktrees, tasks, temp files removed, or "nothing">
- For you: <decisions or actions only the user can take, or "nothing">
```

The report is what makes a close verifiable. A close that skips a step says so on that line, never silently.

## Prevention, during big work

- Each unit of work commits and pushes the moment it is done, so a cutoff loses at most the current increment.
- Give agents a budget up front and size the fleet to the budget, not the other way round.
- Keep units small and independent, so a cutoff is cheap and later merges stay clean.

## Adapting it

- No git? Save files to a synced or permanent location and note the state.
- Solo, no sub-agents? Skip the multi-lane inventory. The HANDOFF, the memory test, and the close report still apply.
- Keep one step if you keep nothing else: the HANDOFF. It is what makes the next session cheap.
