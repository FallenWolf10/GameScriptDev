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

## Safety Boundary

Profile packs must stay within the project boundary in `CONTEXT.md`: local,
user-approved, ToS-compliant UI automation only. Do not add anti-cheat bypass,
stealth behavior, account farming, monetized grinding, or evasion logic to a
profile pack.
