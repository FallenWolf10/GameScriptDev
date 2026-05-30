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
- terminal states
- daily log folders
- demo profile

Live input, OCR, and target window control are intentionally adapter-shaped but not implemented yet. The current adapter boundaries are:

- `WindowAdapter`
- `ScreenAdapter`
- `VisionAdapter`
- `InputAdapter`

The first concrete vision implementation uses Pillow and NumPy for small, testable template matching. It can be replaced by OpenCV later if performance or matching tolerance needs increase.

## Run The Demo

```powershell
$env:PYTHONPATH = "src"
python -m game_script_dev --profile profiles/demo/profile.yaml
```

Logs are written under:

```text
logs/YYYY-MM-DD/
```

## Live Mode

Live mode is explicit and requires confirmation before it can control the desktop. In this skeleton, live adapters are not implemented yet, so live mode stops before sending input.
