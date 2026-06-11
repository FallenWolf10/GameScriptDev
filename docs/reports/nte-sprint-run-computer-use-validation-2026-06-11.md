# NTE Sprint-Run Computer Use Validation

Date: 2026-06-11

## Objective

Validate whether the documented procedure in
`docs/reports/nte-sprint-run-gap-test-plan-2026-06-10.md` can be executed as
written through the supported Computer Use path in this session.

## What Was Validated

Computer Use is reachable in this session.

The NTE client was discoverable through the supported Windows automation path
as:

- app id:
  `process:D:\Games\Neverness To Everness\Client\WindowsNoEditor\HT\Binaries\Win64\HTGame.exe`
- window title: `NTE`

The game window was targetable and produced a live screenshot.

The visible in-game state at validation time showed:

- normal world view rather than a menu-only screen
- character standing still
- no obvious dialogue, inventory, or map overlay blocking movement input

That means the markdown plan's basic staging assumptions were mostly satisfied
at the point of inspection.

## What Did Not Validate Cleanly

The documented trial loop depends on precise timed input control:

1. send the sprint input
2. wait an exact candidate gap
3. send and hold forward movement for a fixed window

The current supported Computer Use API in this session exposes discrete
keyboard presses, clicks, typing, scrolling, and drags, but it does not expose
the timed key-down/key-up hold control needed to reproduce the documented loop
faithfully.

In practical terms, the current Computer Use path cannot directly execute the
plan's key timing requirements as written:

- sprint key dwell: `0.1s`
- candidate gap sweep such as `0.03s`, `0.05s`, `0.08s`, `0.10s`
- forward movement hold window: `0.8s` to `1.0s`

Because of that limitation, this session did not produce a trustworthy measured
minimum sprint-run gap.

## Documentation-Level Validation Result

The markdown plan is valid as an operator-facing test design, but it is not yet
fully executable through the current Computer Use API alone.

The earlier plan note that Computer Use bootstrap failed is no longer current
for this environment. Computer Use now connects successfully and can inspect the
live NTE window. The remaining blocker is not connection failure; it is missing
timed hold semantics for the specific sprint-gap experiment.

## Conclusion

Current status after live validation:

- Computer Use connection: working
- NTE window targeting: working
- in-world visual inspection: working
- faithful sprint-gap timing sweep from the markdown plan: not currently
  supported through this Computer Use API alone

## Recommended Next Step

To validate the actual minimum sprint-run gap documented in the plan, use one
of these paths:

- extend the live control path with explicit hold-duration input support
- run the experiment through the repo's existing live runner path if that path
  already supports bounded press/hold timing for `W` and the sprint key
- revise the markdown plan if the intended execution path is a human-operated
  manual test rather than Computer Use automation
