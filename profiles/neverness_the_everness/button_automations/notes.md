# NevernessTheEverness Button Automations

## Purpose

This pack loops the recorded campfire-to-farming routine. Its key reliability
decision is to teleport back to the protection-point campfire after each fixed
farming window instead of trying to walk back from an unknown combat position.

## Why the moving target is not used as a position anchor

Combat dashes, knockback, and moving enemies make the final character position
non-deterministic. A reverse movement macro would accumulate error on every
cycle. Teleporting to the campfire produces the same route origin and facing
far more reliably, so drift is discarded rather than estimated.

## Recorded cycle

1. Confirm the campfire interaction prompt.
2. Open the campfire menu with `F` and select **Refresh Monsters**.
3. Reproduce the overlapping movement seen after reset:
   - hold `W` for about 4.6 seconds
   - begin holding `A` 2.2 seconds after `W` starts
   - hold `A` for about 7 seconds
4. Repeat normal-attack clicks for 200 seconds.
5. Open the map with `M`.
6. Select the campfire icon and click the teleport button.
7. Wait for the campfire prompt, then repeat.

## Operator tuning

- Change only `fixed_farming`'s `stop_after_seconds` and matching wait when the
  desired farming duration changes.
- `refresh_monsters_button` is the 104x99 crop at `(20, 112)` in the supplied
  1278x720 screenshot of the Chinese campfire menu.
- Tune `campfire_map_icon` if the map camera or UI layout changes.
- Tune the two route hold durations only from repeated live trials beginning at
  the campfire; do not tune them from an arbitrary combat endpoint.
- The current pack deliberately uses normal attacks only. Add character-specific
  `Q`, `E`, or swap inputs only after confirming the intended fixed rotation.

## Readiness

This pack explicitly sets `execution.skip_dry_run_requirement: true`, so the
dashboard can enable live mode without a recorded dry run. This bypass applies
only to profiles that opt into it; target, resolution, asset, and compatibility
checks still apply.
