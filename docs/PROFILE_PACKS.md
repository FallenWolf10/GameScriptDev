# Profile Packs

Profile packs group one game or game-mode workflow into a reviewable folder. A
pack keeps game-specific YAML, visual assets, author notes, and validation
examples together while the Python runner stays reusable.

Recommended folder layout:

```text
profiles/
  example_game/
    daily_task/
      profile.yaml
      assets/
        home_title.png
      notes.md
      validation_examples/
        valid/
        invalid/
```

The dashboard derives the profile id from the folder path. For example,
`profiles/example_game/daily_task/profile.yaml` becomes
`example_game__daily_task`.

Every profile pack must pass `game-script-dev check-pack`.

## Required Metadata

Profile packs declare their pack metadata in `profile.yaml`:

```yaml
profile_pack:
  game: Example Game
  game_mode: Daily Task
  detection_strategy: template_matching
  known_limitations:
    - Verified only at 1280x720 windowed mode.
  compatibility:
    target_identity: true
    supported_resolution: true
    required_assets: true
    full_state_graph: true
    terminal_states: true
    failure_transitions: true
    interruption_recovery: true
    known_limitations: true
    successful_validation_or_dry_run: false
```

Supported detection strategies are:

- `template_matching`
- `ocr_matching`
- `template_and_ocr`

The standard profile fields still declare target identity, supported
resolution, states, regions, actions, interruptions, and execution settings.
The profile-pack block records the compatibility review status for live mode.

Keyboard combo actions are also supported when a workflow needs simultaneous
input. Use `hold_keys` to hold several keys together for a duration, or
`press_keys` to tap them together:

```yaml
actions:
  - type: hold_keys
    keys: [shift, w]
    seconds: 1.5
  - type: press_keys
    keys: [ctrl, c]
```

For repeated taps of the same key over a fixed window, use `repeat_key`:

```yaml
actions:
  - type: repeat_key
    key: space
    repeat_for_seconds: 3
    repeat_every_seconds: 0.5
    tap_duration_seconds: 0.1
```

For overlapping timed input, use `hold_key_while_repeating_key`. This holds one
key down, waits for the requested interval, taps another key, then repeats that
tap until the total hold time is over.

```yaml
actions:
  - type: hold_key_while_repeating_key
    hold_key: w
    hold_seconds: 10
    tap_key: space
    tap_every_seconds: 1
    tap_duration_seconds: 0.1
```

Targets may also declare:

```yaml
target:
  window_title_contains: Example Window
  input_mode: background_window_messages
```

Supported input modes are:

- `background_window_messages`: the canonical live-input mode. Post keyboard and
  mouse messages directly to the target window handle instead of injecting
  global desktop input. This avoids foreground ownership but still requires the
  window to remain visible for screenshot-based state detection.
- `foreground`: a compatibility fallback for targets that cannot reliably accept
  direct window messages. This mode uses OS foreground focus plus global input
  injection and refuses live input when the target is not foreground.

When `target.input_mode` is omitted, profiles default to
`background_window_messages`. Scaffolded profile packs write the default
explicitly so authors can see and review the live-input choice.

Optional key-delivery selectors are also available on `target`:

- `foreground_key_method`: choose how foreground keyboard input is injected when
  `input_mode: foreground`. Supported values are `sendinput_vk`,
  `sendinput_scancode`, `sendinput_vk_scancode`, `sendinput_unicode`,
  `keybd_event_vk`, and `keybd_event_scancode`.
- `background_key_method`: choose how background keyboard messages are posted
  when `input_mode: background_window_messages`.

## Compatibility Checklist

Every checklist key must be present and boolean. A profile can pass schema
validation while `successful_validation_or_dry_run` or another checklist item is
still `false`; the dashboard will block live mode until the checklist is
complete and the dashboard has recorded a successful dry run.

Checklist meaning:

- `target_identity`: process and/or title matching identifies only the intended target.
- `supported_resolution`: the profile has been reviewed at the declared resolution.
- `required_assets`: template assets and OCR expectations are present and documented.
- `full_state_graph`: all expected workflow states are represented.
- `terminal_states`: success and known final failure states are explicit.
- `failure_transitions`: failure paths terminate or move to known recovery states.
- `interruption_recovery`: global interruptions and recovery actions are declared when applicable.
- `known_limitations`: unsupported cases are written down for the operator.
- `successful_validation_or_dry_run`: the pack has passed validation or a dry run after the checklist was reviewed.

## Authoring Commands

Create a pack scaffold:

```powershell
game-script-dev scaffold-pack --output profiles/example_game/daily_task --game "Example Game" --mode "Daily Task"
```

Check a pack:

```powershell
game-script-dev check-pack --profile profiles/example_game/daily_task/profile.yaml
```

The check validates folder shape, profile schema, notes, compatibility evidence,
and known limitations.

For a full annotated `profile.yaml` example that includes every supported field,
see [docs/PROFILE_TEMPLATE.md](docs/PROFILE_TEMPLATE.md).
