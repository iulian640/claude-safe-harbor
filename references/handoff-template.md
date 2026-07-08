# HANDOFF: <project> (<date>)

> Drop this in a durable place (the repo, a synced folder), never a temp dir.
> Written when a session stops near a limit, so the next one resumes without re-deriving anything.

## State in one line
<e.g. "Audit done and merged; 3 of 5 feature lanes landed; 2 data lanes cut off mid-transcription.">

## Landed (in main / done)
- #NNN <title>: merged
- ...

## Open PRs (need action)
- #NNN <branch>: <CI status>. Left to do: <review / spot-check / merge>
- ...

## In flight when it stopped
For each unit that was cut off:
- **<name>**: stopped at `<file>:<point>`. Next step: <concrete action>. Work saved on branch `<branch>` (WIP commit <sha>), or discarded and needs a clean redo.
- ...

## Queued (not started)
- <task>: <why it's next>

## How to resume
```
<exact command(s) to pick up>
```

## Decisions still open for the human
- <decision>: <options>
