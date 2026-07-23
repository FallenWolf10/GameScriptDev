# Local Demo Target Profile Pack

This pack is the canonical safe profile-pack example for GameScriptDev. It
targets only the repo-owned `Demo Automation Window` opened by:

```powershell
$env:PYTHONPATH = "src"
python -m game_script_dev.demo_target
```

## Screen Flow

1. The target starts on `Home`.
2. The runner clicks the named `daily_button` region.
3. The target moves to `Daily Tasks`.
4. The runner presses `F`, holds `W`, and waits for `All Tasks Completed`.

The demo target also exposes controlled screens for future validation:

- Press `K` to show `Known Failure`.
- Press `I` to show `Network disconnected`.
- Press `R` to reset to `Home`.

## Detection And Limits

The pack uses template marker anchors from `assets/` instead of OCR text anchors.
That keeps live readiness independent of optional OCR configuration while still
showing readable text in the target window.

The declared resolution is 1280x720, but the profile uses `policy: ignore`
because Windows theme, title-bar, and DPI settings can change the outer window
rectangle reported by Win32. The Tk client area remains fixed at 1280x720, which
keeps the named click region and screenshot content deterministic.

This pack is not a game profile and is not evidence that any real game permits
automation. Real target packs still require their own safety and compatibility
review.

## Manual Verification

1. Start the Local Demo Target.
2. Start the dashboard with `python -m game_script_dev.dashboard --host 127.0.0.1 --port 8765`.
3. Select `Local Demo Target`.
4. Run a dashboard dry run and confirm it finishes with `success`.
5. Refresh readiness and confirm the target is matched.
6. Select `Live Run`, review the per-attempt confirmation summary, and verify
   that it names the Demo Target and foreground input mode.
7. Select `Start Live Run` only when ready for live desktop input.
8. Confirm the live run finishes with `success`.
9. Review the run log and screenshot artifacts under `logs/YYYY-MM-DD/`.
