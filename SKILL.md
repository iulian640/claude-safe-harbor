---
name: safe-harbor
description: Bring in-flight work safely to a stop before a usage, token, or budget limit cuts it off mid-task. Use when the user says to wrap up or "we're close to the limit", when a budget you were given is nearly spent, when limit/rate errors start appearing, or before launching expensive multi-agent work. Checkpoints all progress (commit/push/PR), writes a resume-ready handoff doc, updates memory, cleans up temp state, and stops launching new work.
---

# Claude safe-harbor

Bring in-flight work safely into harbor before a usage, token, or budget limit cuts it off mid-task, so a hard cutoff never costs more than the last small step.

## The problem

When an AI coding session hits a hard limit (weekly quota, token budget, rate limit) partway through a task, anything not yet saved is lost. It is worst with background or parallel agents: the ones that already committed and pushed survive the cutoff; the ones caught mid-work vanish with their context, and you cannot tell afterwards how far each got.

## The principle: checkpoint early, stop on purpose

Two halves, both needed:

1. **Prevention (always on).** Every unit of work commits and pushes the moment it is done, so a cutoff at any instant loses at most the current increment.
2. **Reaction (this skill).** When a limit is near, run the harbor procedure: a deliberate, clean stop that leaves everything saved and resumable.

## When to run it

- The user says to wrap up, "save progress", "we're close to the limit", or names a ceiling (for example, "stay under 90% this week").
- A budget you were handed is roughly 90–95% spent.
- Limit or rate errors start showing up on some calls.
- Before you launch expensive multi-agent work, to confirm there is headroom and to set a budget for it.

**A caveat worth stating plainly:** from inside a session you usually cannot read the live weekly-usage percentage; it is enforced on the server. So this skill runs on the user's signal or on a budget set up front, not on an automatic percentage watchdog. See *Why not fully automatic* below.

## The harbor procedure

1. **Stop launching new work.** No new agents, no new long-running tasks.
2. **Inventory.** List what is done, what is in flight, and what is queued. For a multi-agent run, note which lanes finished and which were mid-flight.
3. **Checkpoint everything.**
   - Finished unit → commit, push, open its PR.
   - In-flight unit → save partial state: a WIP commit on its own branch, or a precise note of the file and the point where it stopped. Never leave uncommitted work as the only copy.
   - Data or corpus work → do not merge half-verified output; mark it partial and record what is left to check.
4. **Write a HANDOFF doc** in a durable place (not a temp directory). Include: the current state, open PRs and their status, for each in-flight task where it stopped and the next concrete step, and the exact command to resume.
5. **Persist memory.** If the session keeps long-term memory, record the checkpoint so the next session starts oriented instead of re-deriving everything.
6. **Clean up**, but only after the work above is captured. Remove throwaway worktrees, stop background tasks, prune temp files.
7. **Report.** A short summary: what landed, what is pending, and how to pick it up next time.

## Prevention playbook (before and during big work)

- Make agents checkpoint-safe: each one commits, pushes, and opens its PR the moment it finishes, independently of the others.
- Set a budget up front: tell the agent to spend at most X and let it size the work to fit and stop cleanly at the cap.
- Size the fleet to the budget, not the budget to the fleet.
- Keep units small and independent, so a cutoff is cheap and later merges stay clean.

## Estimating your usage (optional helper)

`scripts/usage.py` estimates how close you are to each of your Claude limits, so the skill can self-trigger instead of waiting for you to notice. Claude enforces several limits at once, so the tool tracks each meter separately, anchored to its real reset time, and trips on whichever is closest to its cap:

- the current **session** window (~5 hours), the one that bites during bursts of work,
- the **weekly** window across all models.

It sums the token usage in your local Claude Code transcripts (`~/.claude/projects/**/*.jsonl`, sub-agent runs included), weights it by model, and scales each meter against a calibration you take from the real `/usage` reading.

- `python scripts/usage.py set-reset session <iso>` and `... set-reset week <iso>` once, with the reset times `/usage` shows (e.g. `2026-07-09T00:50+02:00`). This anchors each window instead of guessing.
- `python scripts/usage.py calibrate session <pct>` and `... calibrate week <pct>`, with the percents `/usage` shows right now. This fixes each meter's scale.
- `python scripts/usage.py estimate` any time after. It prints each meter's estimated percent and exits non-zero once any crosses the trigger, which is the cue to run the wrap-up procedure above.

It only sees this machine's Claude Code usage, and the exact weighting toward each limit is not public, so the numbers are a conservative early warning, not a precise gauge. The session meter's window floats, so re-anchor and re-calibrate it at the start of a work session. (The token counting itself is exact: it matches Claude Code's own `stats-cache.json` to the token.)

## Why not fully automatic

A skill cannot watch your usage and pull the plug by itself. It is not a background daemon, and the weekly quota lives on the server with no reliable live read from inside a session. The substitute that works is the pairing above: checkpoint-safe work, so a cutoff is nearly free, plus a budget you set and this deliberate stop, so you choose the ceiling. That reaches the same outcome without depending on a watchdog that cannot exist.

## Adapting it

- **No git?** Swap commit/push/PR for your durable store: save files to a synced or permanent location and note the state.
- **Solo, no sub-agents?** Skip the multi-lane inventory; the handoff doc, the memory write, and the clean stop still apply.
- **Keep one step if you keep nothing else:** the HANDOFF doc. It is what makes the next session cheap instead of a re-derivation from scratch.
