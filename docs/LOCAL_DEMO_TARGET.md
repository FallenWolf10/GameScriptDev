# Local Demo Target

The Local Demo Target is a repo-owned desktop window for safe live-mode
verification. It is not a game, does not call the network, and does not touch
account state, rewards, or third-party services.

## Start The Window

```powershell
$env:PYTHONPATH = "src"
python -m game_script_dev.demo_target
```

The window title is `Demo Automation Window`. The visible workflow is:

1. `Home`
2. `Daily Tasks`
3. `All Tasks Completed`

The controlled failure screens are keyboard-triggered for future validation:

- `K` shows `Known Failure`.
- `I` shows `Network disconnected`.
- `R` resets to `Home`.

## Live Verification

Run these steps on Windows:

1. Start the Local Demo Target and leave it visible.
2. Select the `Local Demo Target` profile pack in the dashboard. Its stable
   dashboard id is `demo__local_target`.
3. Run a dashboard dry run for `profiles/demo/local_target/profile.yaml`.
4. Confirm the dashboard readiness view no longer reports the target as absent.
5. Start a live run only after typing the required `RUN` confirmation.
6. Confirm the run reaches `success`.
7. Inspect the daily log folder under `logs/YYYY-MM-DD/` and verify the run
   folder contains `run.log` and screenshot artifacts showing the state flow.

The demo profile uses small template markers instead of OCR text anchors so live
readiness does not depend on optional OCR configuration. Its resolution policy is
`ignore` because standard Tk window decorations vary by Windows theme and display
scaling; the target still uses a fixed 1280x720 client area for deterministic
input and screenshots.
