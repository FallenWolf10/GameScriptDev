# Pink Paw Test Route Input Reconstruction

## Source Inputs

This reconstruction uses two recordings:

- overlay recording:
  `C:\Users\Ng Yin Hao\Videos\2026-06-02 13-51-44.mp4`
- clean recording:
  `C:\Users\Ng Yin Hao\Videos\Captures\NTE   2026-06-02 13-51-41.mp4`

## Recording Properties

- overlay video: 1280x720, 30 fps, about 50.93 seconds
- clean video: 1920x1080 source, normalized to 1280x720 for anchor crops,
  about 55.46 seconds

## Observed Route

This test route is mostly UI interaction rather than movement replay.

Approximate sequence:

1. Start beside the Pink Paw NPC with the interaction prompt visible.
2. Press `F` to open NPC dialogue.
3. Select the first/join dialogue option.
4. Click the event panel enter button.
5. Wait through the bank loading/interstitial screen.
6. Arrive in the instance lobby and wait briefly.
7. Open the exit confirmation with `Esc`.
8. Confirm exit.
9. Return to the Pink Paw NPC prompt.

## Input Model

High-confidence inputs from the overlay:

- `F`: interaction with the NPC prompt
- mouse click: selecting fixed UI options and confirmation buttons
- `Esc`: opens the recorded exit confirmation

Low-confidence or intentionally omitted:

- movement keys are not required for this short test route
- mouse-look direction is visible in the overlay but not functionally needed for
  this pack
- character swap keys are not used by this test route

## Anchor Selection

Anchors were chosen from stable UI or screen identity areas instead of
transient character poses:

- NPC prompt bar
- Pink Paw event panel header
- bank loading title
- in-instance countdown/ready marker
- exit confirmation title
- returned NPC prompt bar

The goal is to let the profile fail early if it is started from the wrong
screen or if the event flow changes.
