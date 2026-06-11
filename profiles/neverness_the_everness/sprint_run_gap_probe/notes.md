# NevernessTheEverness Sprint Run Gap Probe

## Purpose

This pack runs a coarse sprint-start timing sweep against the local NTE client
using the repo's live runner instead of ad hoc desktop automation.

It is intended to answer one narrow question:

- what is the smallest practical delay between sprint initiation and forward
  movement that still produces clean sprint-run behavior

## Target

- Window title contains: `NTE`
- Input mode: `foreground`

This pack currently relies on title matching instead of process-name matching
because local NTE runs can hide process metadata from a non-elevated runner
even while the window itself is still discoverable.

Foreground mode is chosen intentionally for this experiment because movement
timing is more sensitive than simple UI hotkeys, and prior repo diagnostics
already showed that some NTE inputs can behave differently across delivery
paths.

## Input Model Used In This Pack

This pack models each sprint trial as:

1. press and hold `Shift`
2. wait for the candidate gap
3. hold `W` for `0.8s` while `Shift` remains down
4. release automatically when the configured durations end
5. wait `1.0s` before the next trial

This means the tested variable is:

- `Shift` down -> `W` down delay

not a fully separate "tap Shift, release Shift, then later press W" model.

That choice is deliberate because the repo runner can represent this overlap
exactly and log it cleanly.

## Trial Ladder

The current pack runs these trials in order:

- baseline walk: `W` only for `0.8s`
- gap `0.00s`
- gap `0.03s`
- gap `0.05s`
- gap `0.08s`
- gap `0.10s`
- gap `0.12s`
- gap `0.15s`
- gap `0.18s`

For each non-baseline sprint trial, the total `Shift` hold is:

- `gap + 0.80s`

so `Shift` remains active through the forward burst.

## How To Review A Run

The run log records each trial label before input is sent.

Use the log together with live visual review to judge:

- baseline walk distance versus each sprint candidate
- whether acceleration looked immediate
- whether the startup hesitated, walked first, or sprinted late
- whether foreground focus appeared necessary

## Known Limitations

- The pack does not yet include visual anchors or automated sprint detection.
- The character is not reset to the exact same physical start point between
  trials.
- A successful run result means the timing sequence executed without adapter
  failure, not that the best sprint gap was proven automatically.
- This pack is for local operator-approved timing experiments only.
