# NTE Key Timing Diagnostic

Date: 2026-06-01

## Objective

Explain why some Neverness To Everness key actions appeared to fail even after
background and foreground delivery methods were tested.

## Root Cause

The issue was not only the delivery path. The more important problem was key
timing.

At the time of the failed runs, `press_key` sent `key_down` and `key_up`
immediately back to back with effectively no dwell time between them. That was
enough for Windows to accept the synthetic input, but not enough for the game
client to reliably observe the key as being held down.

NTE appears to sample or poll input in a way that can miss a zero-duration tap.
When the key remained down for about `0.1s`, the client consistently detected
the input.

## Why `hold_key` Worked

`hold_key` already performed:

1. `key_down`
2. sleep for the configured duration
3. `key_up`

That meant the key stayed logically pressed across multiple game frames. A
`0.1s` hold spans several frames in a normal 60 FPS or higher client, so the
game had time to notice the input state.

By contrast, the old `press_key` behavior was:

1. `key_down`
2. `key_up`

with no wait in between. If both events landed within the same input sampling
window, the client could observe "not pressed" on every poll even though the
automation runner technically sent both events successfully.

## Observable Symptom

- `press_key` could report `success` while the game did nothing
- `hold_key` with `0.1s` worked for the same logical input
- This could look like a focus or injection-method problem even when timing was
  the actual blocker

## Repo Fix

The live adapter now treats `press_key` as a short tap instead of a zero-length
burst.

- Default live `press_key` dwell: `0.1s`
- `press_key` actions can optionally override the dwell with `seconds`
- `hold_key` remains the explicit longer-hold action

Example:

```yaml
- type: press_key
  key: l
  seconds: 0.2
```

## Takeaway

When a game accepts a held key but ignores an immediate tap, diagnose timing
before assuming the input API or window focus path is wrong. For game clients,
"input delivered" is not the same as "input sampled by the game."
