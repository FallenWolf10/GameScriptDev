# NevernessTheEverness Dark Racing Realm AFK Loop

## Purpose

This pack reconstructs the repeatable Dark Racing Realm flow shown in the
paired recordings from 2026-06-11:

- open Activities from the world
- select Dark Racing Realm
- start matchmaking
- remain idle for the full race
- wait briefly on the result screen
- leave the race
- reopen Activities and start the next cycle

The profile is intentionally infinite and must be stopped by the operator.

## Source Recordings

- clean recording:
  `C:\Users\Ng Yin Hao\Videos\Captures\NTE   2026-06-11 23-23-23.mp4`
- input-overlay recording:
  `C:\Users\Ng Yin Hao\Videos\2026-06-11 23-23-24.mp4`

Both recordings are 1280x720. The clean recording is about 319.97 seconds and
the overlay recording is about 316.50 seconds. They were aligned by visible
screen transitions rather than by raw timestamp.

## State Model

- `world_ready`
- `activity_menu`
- `race_event_panel`
- `race_ready`
- `race_results`
- `world_returned`
- `failed_loop`

The successful path loops from `world_returned` back to `activity_menu`.

## Anchors

All template assets were cropped from the clean recording:

- `assets/world_location_marker.png`
- `assets/activity_sign_in_title.png`
- `assets/dark_racing_realm_title.png`
- `assets/race_zero_progress_hud.png`
- `assets/race_results_title.png`

## Important Behavior

- The recording contains no movement-key input during the race.
- The player remains at zero progress until results are shown.
- The profile therefore waits for the result anchor without sending gameplay
  input.
- Two incidental attack clicks and countdown clicks were omitted because they
  do not advance the event.

## Validation

Validation completed on 2026-06-11:

```powershell
python -m game_script_dev --profile profiles\neverness_the_everness\dark_racing_realm_afk_loop\profile.yaml --validate-only
python -m game_script_dev check-pack --profile profiles\neverness_the_everness\dark_racing_realm_afk_loop\profile.yaml
python -m pytest
```

Results:

- profile validation passed
- profile-pack check passed
- full test suite passed: 199 tests
- all five template anchors remained above the runner's `0.98` threshold
  across the sampled clean-recording frames

No live run was performed. Live mode still requires the dashboard to record a
successful operator-stopped dry run.
