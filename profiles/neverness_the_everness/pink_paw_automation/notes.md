# NevernessTheEverness Pink Paw Automation

## Purpose

This pack turns the investigated Pink Paw route into a valid GameScriptDev
profile pack named `Pink Paw Automation`.

It is intended as a key-driven approximation of the recording-derived route,
not a frame-perfect replay.

## Source Basis

- This profile was reconstructed from two user-supplied recordings:
  - one overlay recording with visible input layout
  - one clean recording without the input layout
- Profile-local workflow and analysis:
  - `workflow.md`
  - `input-reconstruction.md`
  - `macro-plan.md`

## Confirmed Control Meaning

- `F` is the interaction key when the prompt box appears.
- `1`, `2`, `3`, `4` are character swap keys.
- Left click should be treated as attack by default when no chat or dialogue box
  is open.
- Left click should not be used as a general selection action for this route.

## What This Pack Encodes

- forward route movement with `W`
- steering corrections with `A` and `D`
- timed `F` interactions
- optional timed character swaps
- laser-room movement as short bursts rather than long holds

## Current Validation Boundary

This pack is valid as profile data, but it is intentionally honest about the
runner boundary:

- the current profile schema does not support declarative mouse-look movement
- the current profile schema does not support prompt-aware conditional `F`
  interaction
- because the investigated route depends heavily on mouse steering, this pack is
  best understood as a runnable scaffold rather than a high-confidence live
  route executor

## Recommended Next Improvement

The best technical next step would be extending the runner with one or both of:

- declarative mouse-move actions
- prompt-aware interaction or state confirmation anchors for the Pink Paw route

Once those exist, this pack can be upgraded from an approximation into a much
closer replay profile.

## Validation Evidence

- Profile validation passed with:
  - `python -m game_script_dev --profile profiles\neverness_the_everness\pink_paw_automation\profile.yaml --validate-only`
- Dry run completed successfully on `2026-06-02` with run log:
  - `logs\2026-06-02\run_132510_627856_dry-run_nevernesstheeverness_pink_paw_automation\run.log`
