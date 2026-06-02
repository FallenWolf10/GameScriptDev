# NTE Foreground `L` Diagnostic

Date: 2026-06-01

## Objective

Determine whether Neverness To Everness accepts the `L` hotkey when the runner
uses foreground-style keyboard injection instead of background window messages.

## Methods Tested

Foreground keyboard methods added to the live adapter and tested:

- `sendinput_vk`
- `sendinput_scancode`
- `sendinput_vk_scancode`
- `sendinput_unicode`
- `keybd_event_vk`
- `keybd_event_scancode`

Each method was tested twice:

- a normal tap
- a `0.2s` hold

The live game window was activated before the sweep. The diagnostic script then
captured before/after images around each `L` attempt.

## Result

No tested foreground method opened the team screen.

Visual review of the captures shows the game remained on the world-view screen
for every method. The pixel deltas recorded during the sweep came from normal
scene animation, character idle motion, lighting shifts, and weather changes,
not a transition into the team menu.

## Evidence

Artifacts:

- `logs/diagnostics/foreground_l_sweep/summary.json`
- `logs/diagnostics/foreground_l_sweep_hold_02/summary.json`

Representative images:

- `logs/diagnostics/foreground_l_sweep/sendinput_vk_before.png`
- `logs/diagnostics/foreground_l_sweep/sendinput_vk_after.png`
- `logs/diagnostics/foreground_l_sweep/sendinput_scancode_after.png`

Current direct observation after the sweep also remained on world view.

## Interpretation

Changing from background messages to foreground injection was not enough to make
`L` work in this client state.

That suggests one or more of the following:

- `L` is not the currently bound hotkey in this NTE client configuration
- the game requires a more specific gameplay-focus state than simple foreground
  ownership
- the client is reading this action through a different input path than the
  tested Windows keyboard injections
- the action is gated by UI/context rules that were not satisfied during the
  test

## Repo Changes

The live runtime now supports explicit foreground key-delivery selection so
future sweeps can be configured without patching code again:

- `target.foreground_key_method` in profile schema
- runtime wiring for the selected foreground method
- foreground keyboard senders for SendInput and legacy `keybd_event` variants
- repeatable diagnostic script: `scripts/diagnose_nte_foreground_l.py`
