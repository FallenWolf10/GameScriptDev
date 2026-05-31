# GameScriptDev

GameScriptDev is a profile-driven local automation runner for repetitive, user-approved game UI workflows.

The runner is designed around declarative YAML game profiles. Dry-run mode is the default so profiles can be validated and exercised before any live desktop input is attempted.

## Current Status

This repository currently contains the v1 skeleton:

- strict profile loading and validation
- explicit state graph execution
- reachable terminal state graph validation
- dry-run action simulation
- split runtime adapter boundaries
- Pillow-based template matching utility
- retry-aware state failure handling
- validated named click regions
- Windows target-window detection for live mode
- live target-window screenshot capture
- live template-anchor detection from captured screenshots
- bounded live waits for expected states
- bounded live wait actions
- limited live keyboard press and hold actions
- target-window focusing and foreground verification before live input
- liveness and identity checks before live screenshots and input
- contextual live screenshot artifact names
- optional OCR adapter support behind the vision adapter boundary
- named-region pointer clicks after live focus and liveness verification
- local web dashboard for profile discovery, validation, dry runs, readiness, logs, and artifacts
- profile-pack metadata and live-mode compatibility checklist gating
- capped global interruption recovery attempts
- terminal states
- daily log folders
- validation example profiles
- demo profile

The current adapter boundaries are:

- `WindowAdapter`
- `ScreenAdapter`
- `VisionAdapter`
- `InputAdapter`

The first concrete vision implementation uses Pillow and NumPy for small, testable template matching. It can be replaced by OpenCV later if performance or matching tolerance needs increase.

State execution failures retry the current state up to the profile `max_retries` value. After that, the runner follows `on_failure` when it names another state, or gracefully terminates when `on_failure` is `graceful_termination`.

Global interruptions run their configured recovery actions only up to the interruption's `max_retries` value while the interruption remains visible. If the interruption persists past that cap, the current state fails through the normal retry and failure policy.

Profiles define click coordinates as named regions, then actions reference those names. This keeps coordinate data centralized and lets validation catch missing or misspelled regions before a run starts.

Live mode can now enumerate visible Windows application windows and match the target by process name and/or window title. It verifies the configured resolution policy, focuses the matched window, confirms the foreground handle, checks liveness before live screenshots and input, captures the matched target window into the run artifact folder, and can evaluate template anchors against those captures. Live `wait` actions, a limited allowlist of keyboard press/hold actions, and named-region pointer clicks are available with bounded duration guards. OCR is optional and can be injected behind the vision adapter boundary.

In live mode, `wait_for_state` is a bounded polling loop over screen capture and anchor detection. It uses the profile default timeout unless the action supplies `timeout_seconds`, and supports `poll_interval_seconds` for tuning. Live polling uses a small positive minimum interval to avoid tight screenshot loops.

## Run The Demo

```powershell
$env:PYTHONPATH = "src"
python -m game_script_dev --profile profiles/demo/profile.yaml
```

Validate a profile without running it:

```powershell
$env:PYTHONPATH = "src"
python -m game_script_dev --profile profiles/demo/profile.yaml --validate-only
```

Logs are written under:

```text
logs/YYYY-MM-DD/
```

Each run gets its own folder under the daily log folder with `run.log` and an `artifacts/` directory.

## Local Dashboard

Serve the local-only dashboard:

```powershell
$env:PYTHONPATH = "src"
python -m game_script_dev.dashboard --host 127.0.0.1 --port 8765
```

Then open:

```text
http://127.0.0.1:8765
```

The dashboard discovers profiles, validates them, launches dry runs, shows readiness blockers before live mode, requires `RUN` confirmation for live runs, and surfaces run history, logs, artifacts, current state, final result, and failure reason.

## Profile Packs

Reusable game or game-mode profiles can be grouped as profile packs under
`profiles/<game>/<mode>/`. A pack keeps `profile.yaml`, assets, notes, and
validation examples together. Profile packs declare target identity, resolution,
detection strategy, states, regions, actions, interruptions, known limitations,
and a compatibility checklist.

See [docs/PROFILE_PACKS.md](docs/PROFILE_PACKS.md) for the folder structure and
checklist contract. The dashboard blocks live mode for profile packs until their
compatibility checklist is complete and a successful dashboard dry run has been
recorded.

## Live Mode

Live mode is explicit and requires confirmation before it can control the desktop. The runner focuses and verifies the target window before live input, checks that the original target is still alive before live screenshots and input, and fails closed when the window cannot be confirmed.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for the implementation roadmap and current checkpoint.
