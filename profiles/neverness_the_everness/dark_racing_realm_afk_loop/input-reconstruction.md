# Dark Racing Realm Input Reconstruction

## Recording Properties

- clean capture:
  - 1280x720
  - variable frame rate reported from a 120 fps source
  - about 319.97 seconds
- input-overlay capture:
  - 1280x720
  - 30 fps
  - about 316.50 seconds

The captures are not timestamp-identical. The same screens appear several
seconds apart, so the reconstruction uses screen-state alignment.

## Meaningful Input Sequence

Times below refer to the input-overlay recording.

1. Around `1.9s`: press `F4` to open Activities.
2. Around `5.2s`: left-click the Dark Racing Realm tab.
3. Around `6.6s`: left-click the start-race button.
4. Around `32s`: arrive at the race start.
5. From race start until roughly `272s`: send no movement input.
6. Around `296.0s`: left-click the leave button on the result screen.
7. Around `307.1s`: press `Esc` after returning to the world.
8. Around `310.7s`: left-click the Dark Racing Realm tab again.
9. Around `315.1s`: left-click the start-race button for the next cycle.

## Omitted Inputs

The overlay also shows left-clicks around `0.8s`, `21.3s`, and `36.1s`.

- The first produces an in-world attack before Activities opens.
- The second occurs during the match lineup countdown.
- The third produces another attack near the race start.

None of these clicks advances the workflow, so the profile omits them.

## Race Behavior

The keyboard overlay shows no meaningful `W`, `A`, `S`, `D`, `Shift`, or
character-swap input during the race. The character remains at the start line
with zero progress while other players complete the event.

The profile models this directly with an anchor-driven wait for the result
screen instead of a fixed four-minute sleep.

## Loop Interpretation

The recording ends after the next matchmaking request begins. That partial
second cycle is evidence that the demonstrated routine is intended to repeat,
so the profile uses:

- `execution.allow_infinite_run: true`
- `execution.manual_stop_is_dry_run_success: true`

The operator must stop the loop manually.
