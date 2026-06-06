# Profile Template Reference

This document is a copy-paste-friendly starting point for `profile.yaml`
authoring. It shows every field the current schema understands, including the
optional ones, and explains what each field means.

Use this as a reference template. Delete the parts your pack does not need.

## Complete Annotated Template

```yaml
version: 1
# Profile schema version. The current loader expects 1.

name: Example Game Daily Task
# Human-readable name shown in logs, validation output, and the dashboard.

target:
  process_name: ExampleGame.exe
  # Optional. Exact process image name to match.

  window_title_contains: Example Game
  # Optional. Case-insensitive substring match for the window title.
  # At least one of process_name or window_title_contains must be present.

  input_mode: background_window_messages
  # Optional. Supported values:
  # - background_window_messages
  # - foreground

  foreground_key_method: sendinput_vk
  # Optional. Used only when input_mode: foreground.
  # Supported values:
  # - sendinput_vk
  # - sendinput_scancode
  # - sendinput_vk_scancode
  # - sendinput_unicode
  # - keybd_event_vk
  # - keybd_event_scancode

  background_key_method: post_message_simple
  # Optional. Used only when input_mode: background_window_messages.
  # Supported values:
  # - post_message_simple
  # - post_message_scancode_all
  # - post_message_scancode_root
  # - send_message_timeout_scancode_all
  # - send_message_timeout_scancode_root

  use_qwerty_physical_keys: false
  # Optional. When true, the runner treats supported letter keys as QWERTY
  # physical positions before final normalization.

window:
  resolution:
    width: 1280
    # Required. Expected target width in pixels.

    height: 720
    # Required. Expected target height in pixels.

    policy: verify_only
    # Optional. Supported values currently used by the runner:
    # - verify_only
    # - ignore
    # - attempt_resize
    # The live runner does not implement resizing yet, so attempt_resize will
    # still be blocked in readiness checks.

execution:
  default_timeout_seconds: 30
  # Optional. Default timeout for wait_for_state when the action does not set
  # timeout_seconds explicitly.

  max_retries: 3
  # Optional. Per-state retry count before on_failure or graceful termination.

  manual_stop_is_dry_run_success: false
  # Optional. Set true only for intentionally infinite or operator-driven
  # dry-run workflows where the dashboard should treat an operator-stopped
  # dry run as valid live-readiness evidence.

profile_pack:
  game: Example Game
  # Optional but expected for profile packs. Product/game name.

  game_mode: Daily Task
  # Optional but expected for profile packs. Workflow or mode name.

  detection_strategy: template_and_ocr
  # Optional but expected for profile packs. Supported values:
  # - template_matching
  # - ocr_matching
  # - template_and_ocr

  known_limitations:
    - Verified only at 1280x720 windowed mode.
    - Requires the target window to remain visible.
  # Optional but expected for profile packs. Human-readable review notes about
  # what the profile cannot safely handle yet.

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
  # Optional but expected for profile packs. Every key above must be present
  # and boolean when profile_pack is declared.

regions:
  start_button:
    x: 540
    y: 420
    width: 200
    height: 64
  # Optional. Named click region. Actions like click_point and hold_click
  # reference the region name instead of duplicating coordinates.

  close_popup:
    x: 1120
    y: 80
    width: 60
    height: 60

initial_state: home_screen
# Required. Name of the first state the engine enters.

states:
  home_screen:
    required_anchors:
      - name: home_title
        type: template
        asset: assets/home_title.ppm
      - name: home_text
        type: text
        text: Welcome Back
    # Optional list. Every required anchor must be present for the state to
    # confirm successfully.

    optional_anchors:
      - name: bonus_banner
        type: template
        asset: assets/bonus_banner.ppm
    # Optional list. Presence is logged, but absence does not fail the state.

    forbidden_anchors:
      - name: maintenance_popup
        type: text
        text: Maintenance
    # Optional list. If a forbidden anchor is found in live mode, the state
    # fails immediately.

    actions:
      - type: log
        message: Starting from the home screen.
      # Writes a checkpoint to logs.

      - type: wait
        seconds: 0.5
      # Sleeps for a bounded duration.

      - type: click_point
        region: start_button
        # Optional. Override the profile target input mode for this click only.
        # input_mode: foreground
      # Clicks the center of a named region.

      - type: hold_click
        region: start_button
        seconds: 1.0
        # Optional. Override the profile target input mode for this click only.
        # input_mode: foreground
      # Holds the left mouse button on a named region for a duration.

      - type: click_template
        target: assets/collect_button.ppm
      # Locates a template on the current screenshot and clicks its center.

      - type: press_key
        key: enter

      - type: press_key
        key: f1
        seconds: 0.2
      # Taps a supported key. Optional seconds overrides the default dwell.

      - type: hold_key
        key: w
        seconds: 2.0
      # Holds one supported key for a duration.

      - type: press_keys
        keys: [ctrl, c]
      # Taps several supported keys together.

      - type: hold_keys
        keys: [shift, w]
        seconds: 1.5
      # Holds several supported keys together for a duration.

      - type: repeat_key
        key: space
        repeat_for_seconds: 3
        repeat_every_seconds: 0.5
        tap_duration_seconds: 0.1
      # Repeats one key on an interval for a bounded duration.

      - type: hold_key_while_repeating_key
        hold_key: w
        hold_seconds: 10
        tap_key: space
        tap_every_seconds: 1
        tap_duration_seconds: 0.1
      # Holds one key while tapping another key on a repeating interval.

      - type: move_mouse
        dx: 120
        dy: -40
        seconds: 0.3
        input_mode: foreground
      # Moves the mouse by a relative delta. Mouse-look style actions require
      # foreground input mode.

      - type: hold_mouse_button_and_move
        button: right
        dx: 200
        dy: 0
        seconds: 0.4
        input_mode: foreground
      # Holds a mouse button while applying a relative mouse movement.

      - type: start_continuous_input
        name: forward_motion
        action: hold_key
        key: w
      # Starts a named continuous keyboard action and immediately continues to
      # later actions.

      - type: start_continuous_input
        name: scan_shortcuts
        action: press_key
        key: tab
        repeat_every_seconds: 0.2
        seconds: 0.1
        stop_after_seconds: 3
      # Repeated tap variants need repeat_every_seconds. stop_after_seconds is
      # optional; without it the action runs until a matching stop action or
      # until the run exits. For repeated press-style continuous input, 0.2
      # seconds is the recommended baseline cadence.

      - type: wait
        seconds: 2.5
      # Common recorded-input sequence:
      # start_continuous_input -> wait -> next start_continuous_input.
      # A good baseline is wait_seconds = previous stop_after_seconds - 0.5.

      - type: start_continuous_input
        name: keep_clicking
        action: click_point
        region: start_button
        repeat_every_seconds: 0.2
        stop_after_seconds: 1.0
      # Repeated click variant. It keeps clicking the named region center until
      # stopped or until stop_after_seconds expires.

      - type: wait
        seconds: 0.5
      # Example of the same timing rule:
      # previous stop_after_seconds 1.0 -> wait 0.5.

      - type: start_continuous_input
        name: confirm_enter
        action: press_key
        key: enter
        repeat_every_seconds: 0.2
        seconds: 0.1
        stop_after_seconds: 1.0
      # Another repeated press example using the same recommended cadence.

      - type: start_continuous_input
        name: drag_hold
        action: hold_click
        region: start_button
        stop_after_seconds: 2
      # Continuous hold-click variant. It keeps the mouse button held down
      # until stopped or until stop_after_seconds expires.

      - type: stop_continuous_input
        name: forward_motion
      # Stops a previously-started continuous keyboard action.

      - type: start_continuous_input
        name: combat_cycle
        action: sequence
        sequence:
          - action: press_key
            key: "1"
            repeat_every_seconds: 0.1
            seconds: 0.1
            run_for_seconds: 1.0
          - action: press_key
            key: "2"
            repeat_every_seconds: 0.1
            seconds: 0.1
            run_for_seconds: 1.0
          - action: press_key
            key: "3"
            repeat_every_seconds: 0.1
            seconds: 0.1
            run_for_seconds: 1.0
          - action: press_key
            key: "4"
            repeat_every_seconds: 0.1
            seconds: 0.1
            run_for_seconds: 1.0
      # Continuous sequence variant. Each step runs by itself for its own
      # run_for_seconds window, then the next step starts. The whole sequence
      # loops until stopped or until outer stop_after_seconds expires.

      - type: wait_for_state
        state: mission_screen
        timeout_seconds: 20
        poll_interval_seconds: 0.5
      # Polls captures until the target state confirms or the timeout expires.
      # timeout_seconds and poll_interval_seconds are optional.

    on_success: mission_screen
    # Optional for non-terminal states, but normally required in practice.
    # If omitted on a non-terminal state, the run finishes as
    # failed_missing_transition after actions complete.

    on_failure: known_failure
    # Optional. Defaults to graceful_termination.
    # Can be:
    # - graceful_termination
    # - another declared state name

  mission_screen:
    required_anchors:
      - name: mission_title
        type: template
        asset: assets/mission_title.ppm
    actions:
      - type: stop
        result: operator_stopped
    # stop ends the run immediately with the supplied result string.

  completed:
    required_anchors:
      - name: completion_title
        type: template
        asset: assets/completion_title.ppm
    terminal: true
    result: success
    # Terminal states end the run when reached.

  known_failure:
    required_anchors:
      - name: disconnect_text
        type: text
        text: Disconnected
    terminal: true
    result: failed_disconnect

interruptions:
  - name: network_disconnect
    required_anchors:
      - name: disconnect_popup
        type: template
        asset: assets/disconnect_popup.ppm
    recovery_actions:
      - type: click_point
        region: close_popup
      - type: wait
        seconds: 1
    max_retries: 2
    # Optional list. Interruptions are checked globally while the run is active.
    # If an interruption remains visible after its recovery retries are spent,
    # the current state fails through the normal retry and failure policy.
```

## Field-By-Field Notes

### Top-Level Fields

- `version`: schema version. Use `1`.
- `name`: descriptive name for the workflow.
- `target`: how the runner finds the intended window and which input mode it
  should use.
- `window.resolution`: expected dimensions and how strictly to enforce them.
- `execution`: retry and wait defaults.
- `profile_pack`: review metadata for pack-shaped profiles.
- `regions`: shared named rectangles for mouse input.
- `initial_state`: where execution begins.
- `states`: the state graph itself.
- `interruptions`: global popup or modal recovery rules.

### Anchor Types

Two anchor types are currently supported:

- `template`: requires `asset`, which must point to an existing file relative
  to the profile directory.
- `text`: requires `text`, which is matched through the OCR boundary.

Anchors can appear in:

- `required_anchors`
- `optional_anchors`
- `forbidden_anchors`
- `interruptions[].required_anchors`

### Supported Action Types

- `log`
  - Fields: `message`
- `wait`
  - Fields: `seconds`
- `click_point`
  - Fields: `region`
- `hold_click`
  - Fields: `region`, `seconds`
- `click_template`
  - Fields: `target`
- `press_key`
  - Fields: `key`, optional `seconds`
- `hold_key`
  - Fields: `key`, optional `seconds` (defaults to `1`)
- `press_keys`
  - Fields: `keys`, optional `seconds`
- `hold_keys`
  - Fields: `keys`, optional `seconds` (defaults to `1`)
- `repeat_key`
  - Fields: `key`, `repeat_for_seconds`, `repeat_every_seconds`, optional
    `tap_duration_seconds`
- `hold_key_while_repeating_key`
  - Fields: `hold_key`, `hold_seconds`, `tap_key`, `tap_every_seconds`,
    optional `tap_duration_seconds`
- `move_mouse`
  - Fields: `dx`, `dy`, optional `seconds`, optional `input_mode`
  - Must use `foreground` input mode
- `hold_mouse_button_and_move`
  - Fields: `button`, `dx`, `dy`, optional `seconds`, optional `input_mode`
  - Must use `foreground` input mode
- `start_continuous_input`
  - Fields: `name`, `action`, optional `stop_after_seconds`
  - Supported `action` values:
    `click_point`, `hold_click`, `press_key`, `press_keys`, `hold_key`,
    `hold_keys`, `repeat_key`, `hold_key_while_repeating_key`, `sequence`
  - `click_point` requires `region` and `repeat_every_seconds`
  - `hold_click` requires `region`
  - `press_key` and `press_keys` also require `repeat_every_seconds`
  - `repeat_key` requires `key` and `repeat_every_seconds`
  - `hold_key_while_repeating_key` requires `hold_key`, `tap_key`,
    `tap_every_seconds`, optional `tap_duration_seconds`
  - `sequence` requires `sequence`, a non-empty list of timed sub-actions
  - Each `sequence` step must include `action` and `run_for_seconds`
  - Sequence steps can use the same continuous sub-actions except nested
    `sequence`
  - Recorded-workflow reference:
    prefer `repeat_every_seconds: 0.2` for repeated press/click continuous
    input unless the target proves it needs a slower interval
  - Chained timing reference:
    after each `start_continuous_input`, add an explicit `wait`; a useful
    baseline is `wait = previous stop_after_seconds - 0.5`
- `stop_continuous_input`
  - Fields: `name`
- `wait_for_state`
  - Fields: `state`, optional `timeout_seconds`, optional
    `poll_interval_seconds`
- `stop`
  - Fields: optional `result`

### Supported Key Names

The current schema accepts these keys:

- letters: `a` through `z`
- digits: `0` through `9`
- control/navigation keys:
  `alt`, `backspace`, `control`, `ctrl`, `down`, `enter`, `esc`, `escape`,
  `f1`, `left`, `left_shift`, `right`, `right_shift`, `shift`, `space`,
  `tab`, `up`

### State Graph Rules

- Every referenced state must exist.
- The graph must have a reachable terminal state.
- Unreachable declared states fail validation.
- `on_failure` defaults to `graceful_termination` when omitted.
- Terminal states use `terminal: true` and usually define `result`.

### Practical Authoring Tips

- Prefer named `regions` over repeating raw click coordinates in multiple
  actions.
- Use `required_anchors` for the minimum proof that the state is really on
  screen.
- Add `forbidden_anchors` for known bad states that look similar to valid ones.
- For chained continuous inputs from recording reconstruction, start with
  `repeat_every_seconds: 0.2`, then place a `wait` after each start. A strong
  default is `wait = previous stop_after_seconds - 0.5`.
- When tuning live timing, optimize for the lowest stable value instead of the
  shortest possible tap. A target can accept the Windows input call and still
  miss a too-short press during its own sampling window, especially under lag
  or load. Start with `press_key` around `0.1s` and the repeated
  press/click cadence above, then adjust only after repeated live runs.
- Prefer to win efficiency by replacing blind waits with `wait_for_state`
  rather than by shrinking tap dwell too aggressively. Adapter-level success
  means the input was sent, not necessarily that the target consumed it.
- Keep `known_limitations` honest. They are part of the readiness contract, not
  just a comment bucket.
- Start with dry-run and validation before attempting live mode.
