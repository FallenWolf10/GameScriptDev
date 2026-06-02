# Neverness to Everness Background Key Diagnostic

Date: 2026-06-01

## Goal

Verify whether Neverness to Everness accepts background keyboard input when the
game window is not foreground, and determine why some keys appear to work while
others do not.

## Environment

- Workspace: `C:\Users\Ng Yin Hao\Documents\GameScriptDev`
- Target process: `HTGame.exe`
- Target window title match: `NTE`
- Dashboard used for the decisive runs: admin instance on `127.0.0.1:8767`
- Target input mode: `background_window_messages`

## Control Profiles

- `profiles/neverness_the_everness/inventory_toggle/profile.yaml`
  - Sends `B`
  - Expected visual change: world view -> inventory
- `profiles/neverness_the_everness/team_screen_l/profile.yaml`
  - Sends `L`
  - Expected visual change: world view -> team screen

## Methods Tried

### 1. Background `PostMessage` with simple virtual-key payload

- Result for `B`: success with visible UI change
- Result for `L`: no visible change

### 2. Background `PostMessage` with scan-code-aware payload to root and child windows

- Method id: `post_message_scancode_all`
- Result for `L`: no visible change
- Run id: `539826b218c9`
- Evidence:
  - `logs/diagnostics/team_l_scancode_all_before.png`
  - `logs/diagnostics/team_l_scancode_all_after.png`

### 3. Background `PostMessage` with scan-code-aware payload to root window only

- Method id: `post_message_scancode_root`
- Result for `L`: no visible change
- Run id: `c0c1ef147086`
- Evidence:
  - `logs/diagnostics/team_l_scancode_root_before.png`
  - `logs/diagnostics/team_l_scancode_root_after.png`

### 4. Background `SendMessageTimeoutW` with scan-code-aware payload to root window only

- Method id: `send_message_timeout_scancode_root`
- Result for `L`: no visible change
- Run id: `a99f2093f718`
- Evidence:
  - `logs/diagnostics/team_l_send_root_before.png`
  - `logs/diagnostics/team_l_send_root_after.png`

### 5. Background `SendMessageTimeoutW` with scan-code-aware payload to root and child windows

- Method id: `send_message_timeout_scancode_all`
- Result for `L`: no visible change
- Run id: `30c4fa538fcc`
- Evidence:
  - `logs/diagnostics/team_l_send_all_before.png`
  - `logs/diagnostics/team_l_send_all_after.png`

## Direct Visual Validation

### `B` succeeded

The final control run proved that the current background message path can work
for at least one NTE hotkey.

- Profile: `inventory_toggle`
- Run id: `2f70ede65fd6`
- Before image: `logs/diagnostics/b_final_before.png`
- After image: `logs/diagnostics/b_final_after.png`
- Pixel diff:
  - `bbox: (0, 0, 1920, 1080)`
  - `changed_pixels: 2072962`

Visual result: the game changed from world view to the inventory screen after
the background `B` key was sent.

### `L` failed across all tested message-based methods

Every tested background method reached `press_key l` and the run finished
`success`, but the game view did not change.

- All saved `L` before/after pairs diffed to:
  - `bbox: null`
  - `changed_pixels: 0`

Visual result: the game remained on the world view instead of opening the team
screen.

## Why The Dashboard Still Says "Success"

The current runner reports action completion when the Windows input call returns
without adapter-level failure. It does not require a proven UI state change for
these packs.

That means:

- `success` currently means "the input message was sent by the adapter"
- It does not always mean "the game accepted and acted on that message"

This is why `L` can show as completed even though the screen remains unchanged.

## Most Likely Explanation

The evidence shows that background input is not failing globally. It is failing
selectively by key and probably by game-side input path.

What the results support:

- NTE accepts background-window keyboard messages for `B`
- NTE does not accept the tested message-based delivery paths for `L`
- The failure persists even after trying:
  - simple virtual-key messages
  - scan-code-aware message payloads
  - root-only and root-plus-child delivery
  - synchronous `SendMessageTimeoutW` delivery

The most likely reason is that NTE handles `L` differently from `B`. Common
ways games do this include:

- different hotkeys being bound to different internal handlers
- some hotkeys being read through raw input or polled key state instead of
  standard window messages
- context-gated UI actions that ignore synthetic message delivery for certain
  screens or keys

In short: `B` appears to be wired to a message-friendly UI toggle path, while
`L` appears to require a different class of input signal than plain background
window messages can provide.

## Code Changes Made During Diagnosis

The live adapter was extended so background keyboard testing could sweep
multiple Windows delivery strategies instead of just one:

- `post_message_simple`
- `post_message_scancode_all`
- `post_message_scancode_root`
- `send_message_timeout_scancode_all`
- `send_message_timeout_scancode_root`

Relevant files:

- `src/game_script_dev/adapters/live.py`
- `src/game_script_dev/schema.py`
- `src/game_script_dev/runtime.py`
- `tests/test_live_input_adapter.py`

## Conclusion

Background keyboard control is partially working for Neverness to Everness.

- Confirmed working: `B`
- Confirmed not working with the tested background message methods: `L`

So the issue is not "background input is broken." The issue is "this game only
honors some keys through background window messages, and `L` is not one of the
keys that currently responds to the tested message-based methods."
