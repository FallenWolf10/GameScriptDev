# Roadmap

This roadmap captures the required next work before GameScriptDev moves from the current script-runner skeleton into a safer UI-supported automation tool and then into reusable game-specific profile packs.

## Required Next Work

1. Implement target-window focusing in live mode.
   - Bring the matched target window to foreground before live input.
   - Verify the foreground handle after focusing.
   - Fail closed if the target is minimized, hidden, blocked, or cannot be confirmed.

2. Add window liveness checks before live operations.
   - Confirm the original target handle still exists before screenshots and input.
   - Confirm the window still matches the expected process name and title.
   - Stop gracefully if the target disappears or changes identity.

3. Improve live diagnostics and failure artifacts.
   - Include state and action context in screenshot names or structured log entries.
   - Capture a useful final screenshot on graceful termination when possible.
   - Keep logs, screenshots, and live artifacts out of git.

4. Add optional OCR adapter support.
   - Keep template matching first-class.
   - Treat OCR as an optional vision capability behind the existing adapter boundary.
   - Add tests using fakes or small local image fixtures.

5. Add pointer input only after focus and liveness are reliable.
   - Require named regions or detected template targets.
   - Keep raw coordinates centralized in profile data.
   - Preserve explicit live confirmation before any mouse input.

6. Expand profile validation and authoring feedback.
   - Validate retry counts and other numeric execution fields.
   - Improve error messages with state, action, and field context.
   - Add more graph validation when failure-transition loops become a practical risk.

7. Expand demo and real profile coverage.
   - Exercise global interruptions, forbidden anchors, failure transitions, keyboard actions, waits, terminal states, and validation examples.
   - Keep game-specific behavior in YAML profiles and assets, not Python runner code.

8. Build the local web dashboard.
   - Start with a local-only browser dashboard served from the Python project.
   - Provide profile discovery, profile validation, dry-run launch, run history, logs, and artifact viewing.
   - Show profile readiness status before live mode is available.
   - Require explicit live-run confirmation in the dashboard before live input.
   - Surface target-window status, resolution checks, current state, final result, and failure reason.
   - Keep the dashboard operator-focused rather than promotional: dense, clear, and built for repeated workflow use.

9. Define game expansion and profile-pack requirements.
   - Support one profile pack per game or game mode, with YAML profiles, assets, notes, and validation examples grouped together.
   - Require each profile pack to declare target identity, supported resolution, detection strategy, states, regions, actions, interruptions, and known limitations.
   - Add a compatibility checklist before a profile pack is marked ready for live mode.
   - Require the checklist to confirm target identity, supported resolution, required assets, full state graph, terminal states, failure transitions, interruption recovery, known limitations, and a successful validation or dry-run result.
   - Keep the local web dashboard from launching live mode for profile packs that have not passed the compatibility checklist.
   - Keep expansion ToS-compliant and inside the project safety boundary: no anti-cheat bypass, stealth behavior, account farming, monetized grinding, or evasion logic.
   - Prefer reusable runner capabilities over game-specific Python code.

## Current Checkpoint

The project currently has the base runner structure, validation, dry-run execution, live adapter boundaries, Windows target detection, screenshots, template matching, bounded waits, limited keyboard input, logs, tests, and demo profile in place. The UI and expansion work should proceed after the live-runtime safety foundation is stronger.

## Source Coverage

This roadmap includes the actionable requirements from the current markdown documentation:

- `README.md`: current runner status, dry-run usage, live-mode limitations, logs, demo profile, OCR gap, pointer-input gap, and target-window-control gap.
- `CONTEXT.md`: safety boundary, local automation vocabulary, local web dashboard term, profile vocabulary, live confirmation, runtime adapters, detection strategies, named regions, and graceful termination.
- `docs/adr/0001-yaml-profiles-with-explicit-state-graphs.md`: game behavior stays in strict declarative YAML profiles with explicit state graphs.
- `docs/adr/0002-python-runner-with-dry-run-first.md`: Python remains the runner platform and dry-run remains the default before live input is allowed.
- `docs/adr/0003-split-live-runtime-adapters.md`: window, screen, vision, and input capabilities stay behind separate runtime adapters.

Future implementation work should proceed from this roadmap while preserving those documented decisions unless a new ADR deliberately changes them.
