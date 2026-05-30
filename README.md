# GameScriptDev

GameScriptDev is a profile-driven local automation runner for repetitive, user-approved game UI workflows.

The runner is designed around declarative YAML game profiles. Dry-run mode is the default so profiles can be validated and exercised before any live desktop input is attempted.

## Current Status

This repository currently contains the v1 skeleton:

- strict profile loading and validation
- explicit state graph execution
- dry-run action simulation
- split runtime adapter boundaries
- Pillow-based template matching utility
- retry-aware state failure handling
- validated named click regions
- Windows target-window detection for live mode
- live target-window screenshot capture
- live template-anchor detection from captured screenshots
- terminal states
- daily log folders
- demo profile

Live input, OCR, and target window control are intentionally adapter-shaped but not implemented yet. The current adapter boundaries are:

- `WindowAdapter`
- `ScreenAdapter`
- `VisionAdapter`
- `InputAdapter`

The first concrete vision implementation uses Pillow and NumPy for small, testable template matching. It can be replaced by OpenCV later if performance or matching tolerance needs increase.

State execution failures retry the current state up to the profile `max_retries` value. After that, the runner follows `on_failure` when it names another state, or gracefully terminates when `on_failure` is `graceful_termination`.

Profiles define click coordinates as named regions, then actions reference those names. This keeps coordinate data centralized and lets validation catch missing or misspelled regions before a run starts.

Live mode can now enumerate visible Windows application windows and match the target by process name and/or window title. It verifies the configured resolution policy, captures the matched target window into the run artifact folder, and can evaluate template anchors against those captures. Live OCR and input are still intentionally unavailable.

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

## Live Mode

Live mode is explicit and requires confirmation before it can control the desktop. In this skeleton, live adapters are not implemented yet, so live mode stops before sending input.
