# Claude safe-harbor

A [Claude Code](https://claude.com/claude-code) skill that brings your work safely to a stop before a usage, token, or budget limit cuts it off mid-task, so a hard cutoff never costs you more than the last small step.

[Español](README.es.md)

## The problem

You are deep in a long session, maybe with several background agents running, and you hit a hard limit: the weekly quota, a token budget, a rate limit. Everything not yet saved is gone. The agents that had already committed and pushed survive. The ones caught mid-work disappear with their context, and afterwards you cannot even tell how far each one got.

## The idea

Two halves, both needed:

- **Prevention.** Work commits and pushes the moment each piece is done, so a cutoff at any instant loses at most the current increment.
- **Reaction.** When a limit is near, stop on purpose: checkpoint everything, write a resume-ready handoff, and leave nothing half-saved.

`safe-harbor` is the second half, and it nudges you toward the first.

## What it does

When you run it, it:

1. Stops launching new work.
2. Takes inventory of what is done, in flight, and queued.
3. Checkpoints everything: commit, push, and open a PR for finished work; save partial state for anything mid-flight.
4. Writes a `HANDOFF` doc in a durable place, with the current state, open PRs, where each in-flight task stopped, and the exact command to resume.
5. Updates long-term memory if the session keeps any.
6. Cleans up temp state and background tasks, but only after the work is captured.
7. Reports what landed, what is pending, and how to pick it up.

## Install

Copy the skill into your Claude Code skills directory:

```bash
git clone https://github.com/iulian640/claude-safe-harbor
mkdir -p ~/.claude/skills/safe-harbor
cp claude-safe-harbor/SKILL.md ~/.claude/skills/safe-harbor/
cp -r claude-safe-harbor/references ~/.claude/skills/safe-harbor/
```

Or run `./install.sh` from the cloned repo.

## Use

Trigger it by asking, in whatever words fit:

- "wrap up safely, we're close to the limit"
- "save progress before we run out"
- `/safe-harbor`

You can also tell Claude a ceiling up front ("stay under 90% this week", "spend at most 500k tokens on this") and it will size the work to fit and reach harbor on its own before the cap.

## Make it fire reliably

Installing the skill gives Claude the procedure. It does not make Claude run it on its own. Two steps close that gap:

1. **Turn it into a standing instruction.** Add a line to your `CLAUDE.md` (global or per-project):

   > Always run the safe-harbor skill when wrapping up a session or approaching a usage, token, or budget limit.

   That moves the skill from "available if asked" to "runs by default".

2. **Give it a trigger it can act on.** The skill cannot read your live usage, so hand it a ceiling at the start of expensive work: "stay under 90% this week", or "spend at most 500k tokens on this". Claude sizes the work to fit and reaches harbor before the cap.

For a mechanical backstop at session end, you can also wire a `Stop` hook that commits and pushes any dangling work. That is optional; the `CLAUDE.md` line plus a budget covers the common case.

3. **Let it estimate its own usage (optional).** `scripts/usage.py` reads your local Claude Code transcripts and tracks each Claude limit separately (the ~5-hour session window and the weekly window), anchored to its real reset time. It weights the tokens by model and scales each meter against a calibration you take from the real `/usage` reading, then trips on whichever meter is closest to its cap. Set it up once per work session (`set-reset` + `calibrate` for each meter, with the numbers `/usage` shows), then `python scripts/usage.py estimate` any time for a per-meter percent and a trigger signal. It only sees this machine and is a conservative early warning, not a precise gauge, but the token counting is exact (it matches Claude Code's own accounting to the token), and it lets the skill self-trigger instead of waiting for you to notice.

## Why it is not fully automatic

A skill cannot watch your usage and pull the plug by itself. It is not a background process, and the weekly quota lives on the server with no reliable live read from inside a session. So `safe-harbor` runs on your signal or on a budget you set, not on a percentage watchdog. Paired with checkpoint-safe work, where a cutoff is nearly free anyway, it reaches the same result without depending on a watchdog that cannot exist.

## License

MIT. See [LICENSE](LICENSE).
