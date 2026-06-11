# NTE Sprint-Run Gap Probe Results

Date: 2026-06-11

## Objective

Create a repo-native profile pack that expresses the sprint-start timing
experiment precisely, run it live against the local NTE window, and record the
first experimental pass.

## New Profile Pack

Pack path:

- `profiles/neverness_the_everness/sprint_run_gap_probe/profile.yaml`

Supporting notes:

- `profiles/neverness_the_everness/sprint_run_gap_probe/notes.md`

The pack models each trial as:

1. hold `Shift`
2. wait for a configured `Shift`-to-`W` gap
3. hold `W` for `0.8s` while `Shift` remains down
4. wait `1.0s` before the next trial

This first pack uses a coarse sweep:

- baseline walk
- gap `0.00s`
- gap `0.03s`
- gap `0.05s`
- gap `0.08s`
- gap `0.10s`
- gap `0.12s`
- gap `0.15s`
- gap `0.18s`

## Validation Status

The new pack passed:

- profile schema validation
- profile-pack check

## Live Execution Record

### First local live attempts

Initial non-elevated attempts did not complete the experiment:

- sandboxed live run could not see desktop windows
- unsandboxed live run reached Windows but failed with `WinError 5`

Those failures are consistent with the repo's earlier NTE privilege warnings.

### Successful elevated run

The repo-supported administrator relaunch path succeeded.

Successful run folder:

- `logs/2026-06-11/run_015049_065134_live_nevernesstheeverness_sprint_run_gap_probe/`

Successful run log:

- `logs/2026-06-11/run_015049_065134_live_nevernesstheeverness_sprint_run_gap_probe/run.log`

Key facts recorded by the runner:

- target window matched successfully
- target window foreground verification succeeded
- the profile executed all planned coarse-sweep trials
- the run finished `success`

## What This Proves

- The repo can now express this sprint-gap experiment as a real profile pack
  rather than an ad hoc manual sequence.
- The live runner can execute the full coarse sweep against the local NTE
  target window when run with administrator privileges.
- Each trial is now recorded in the run log with explicit timing labels.

## What This Does Not Yet Prove

This run does not yet establish the best minimum sprint-run gap.

Current limitation:

- the profile records exact input delivery, but it does not yet include
  automated visual confirmation that a given trial produced immediate
  sprint-run rather than walk, hesitation, or late sprint onset

So the current result is:

- input experiment path: validated
- exact coarse sweep execution: validated
- final recommended minimum sprint-run gap: not yet proven from this pass alone

## Recommended Next Step

Use this pack as the repeatable input driver, then add one of these stronger
verification layers:

- a human-reviewed video capture of the full sweep
- a narrower second-pass profile around the best-looking coarse candidates
- a future visual confirmation mechanism that can distinguish walk from
  immediate sprint onset
