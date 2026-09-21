# Optional: estimating your own usage

`scripts/usage.py` estimates how close you are to each of your Claude limits, so the skill can self-trigger instead of waiting for you to notice. It is optional and not installed by default (`./install.sh --estimator` copies it). Most people close sessions on their own signal and never need it.

Claude enforces several limits at once, so the tool tracks each meter separately and trips on whichever is closest to its cap:

- the **session** window (~5 hours). It is not a fixed clock reset: it starts with the first message you send after the previous window expired, and runs 5h from there. The tool reconstructs that window from your transcript timestamps, so you never have to tell it when the window started.
- the **weekly** window across all models, anchored to a fixed reset you give it once.

It sums the token usage in your local Claude Code transcripts (`~/.claude/projects/**/*.jsonl`, sub-agent runs included), weights it by model, and scales each meter against a calibration you take from the real `/usage` reading.

## Setup

```
python scripts/usage.py set-reset week 2026-07-12T02:00+02:00   # once, the weekly reset /usage shows
python scripts/usage.py calibrate session 69                    # the percents /usage shows right now
python scripts/usage.py calibrate week 87
python scripts/usage.py estimate                                # any time after
```

`estimate` prints each meter's estimated percent and exits non-zero once any crosses the trigger (85% by default, in `~/.claude/safe-harbor.json`). That exit code is the cue to run the harbor procedure.

## Limits of the estimate

It only sees this machine's Claude Code usage, not claude.ai, the API, or other devices. The exact weighting Anthropic applies toward each limit is not public, so the numbers are a conservative early warning, not a precise gauge. Re-calibrate at the start of a work session. The token counting itself is exact: it matches Claude Code's own `stats-cache.json` to the token.
