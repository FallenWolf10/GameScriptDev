# Roadmap

This roadmap captures the next work for GameScriptDev after the runner, dashboard, and profile-pack foundation. The project remains a profile-driven local automation runner for repetitive local UI workflows.

## Current Checkpoint

Sections 1 through 9 are implemented and committed. The runner now has:

- strict YAML profile loading and validation
- explicit state graph execution
- dry-run-first workflow execution
- split live runtime adapters for window, screen, vision, and input
- Windows target detection, focusing, foreground verification, and liveness checks
- live screenshots, template matching, bounded waits, keyboard input, and named-region pointer input
- optional OCR adapter boundary
- contextual logs and artifacts
- validation example profiles
- local web dashboard for discovery, validation, explicit dry runs,
  readiness-gated live launch with per-attempt confirmation, run history, logs,
  artifacts, compatibility status, current state, final result, and failure reason
- profile-pack metadata and compatibility checklist gating
- source-tree Windows Operator Application shell and PyInstaller one-folder proof
- atomic single-Active-Run backend admission
- one-screen Run workspace and read-only Profile Builder foundation

The current implementation focus is completing the packaged application safety
boundaries and moving the writable raw-YAML Builder foundation into structured
Action editing and later drag-and-drop authoring. Manual Windows live
verification against the repo-owned `Demo Automation Window` passed on
2026-07-24; every real target pack still requires its own independent proof.

Sections 10 and 11 now have implementation slices in the worktree: the Local Demo Target can be launched with `python -m game_script_dev.demo_target`, the flat demo profile remains available, and the canonical `profiles/demo/local_target/profile.yaml` pack is discoverable as `demo__local_target`. Section 12 also has an ergonomics slice: the dashboard shows a live verification checklist, selected-run readiness, and a final/latest screenshot link, while live captures now include per-context sequence numbers and final success screenshots. Sections 14 through 19 now have source-tree support: profile-pack scaffolding/checks, dashboard pack metadata, run review, startup checks, and safe Local Demo regression fixtures. The Section 10 Windows proof matched and foregrounded the repo-owned target, captured the Home, Daily Tasks, and final-success screens, recognized the expected templates, delivered the region click plus `F` and held `W` input, reached `completion_popup`, and retained final evidence.

## Grill-With-Docs Outcome

The next step should not jump straight to a real game profile. A real game would mix three questions at once: whether live adapters work, whether profile-pack authoring works, and whether a specific game's UI can be automated reliably.

The sharper next step is a repo-owned **Local Demo Target** paired with a **Live Verification Scenario**:

- It respects ADR 0001 by keeping workflow behavior declarative in YAML profiles.
- It respects ADR 0002 by keeping dry-run as the default and live mode explicit.
- It respects ADR 0003 by verifying live behavior through existing runtime adapters instead of adding runner shortcuts.
- It turns the current Demo Profile from a dry-run-only example into a safe live verification target.

No new ADR is needed for this step. The decision is a reversible planning slice, not a hard-to-reverse architectural commitment.

## Section 10: Build a Local Demo Target

Goal: provide a small local desktop target window that can be opened by the operator and safely controlled by the existing live runner.

Required behavior:

- Open a visible desktop window titled `Demo Automation Window`.
- Present deterministic states that correspond to the demo profile workflow.
- Start at a home screen with a visible `Home` signal.
- Expose a clickable daily-task region matching the profile's named region intent.
- Move to a daily menu state with a visible `Daily Tasks` signal after the expected click.
- React to the demo keyboard flow and reach a completion state with `All Tasks Completed`.
- Provide at least one controlled interruption or known failure screen for future validation.
- Avoid external network calls, real game processes, account state, or monetized rewards.

Implementation constraints:

- Prefer Python standard-library UI tooling for the first version so the demo target does not add a dependency just to prove live mode.
- Keep the demo target separate from the runner engine and runtime adapters.
- Do not special-case the demo target inside live adapters.
- Keep profile behavior in YAML; the demo target should simulate screens, not define runner workflow.
- Make the demo target manually startable before live mode runs, preserving the Running Target Requirement.

Acceptance checks:

- `python -m game_script_dev.demo_target` opens the local demo target window.
- The existing demo profile can find the target window in live readiness.
- A live run can focus the demo target, capture screenshots, perform the named-region click, send the keyboard actions, and finish with `success`.
- Logs and artifacts show the live state progression and useful screenshots.
- The dashboard shows the demo profile as blocked when the target is absent and live-ready only when dry-run and target checks pass. Profile-pack compatibility remains `not_applicable` for the flat demo profile until Section 11 promotes it into a pack.
- Unit tests cover the target-launch command shape where possible without requiring GUI automation in CI.
- Manual verification steps are documented for Windows.

## Section 11: Promote the Demo Profile Into a Profile Pack

Goal: make the demo workflow the canonical example profile pack.

Required behavior:

- Move or mirror the demo into a pack-shaped folder such as `profiles/demo/local_target/profile.yaml`.
- Add `notes.md` explaining the local target, expected screen flow, limitations, and live verification steps.
- Add validation examples for complete and incomplete compatibility checklists.
- Set checklist values based on the local demo target's verified behavior.
- Keep the original quick-start path working or document the replacement clearly.

Acceptance checks:

- The dashboard discovers the demo profile pack with a stable id.
- The profile-pack checklist blocks live mode until every required item is true and a successful dashboard dry run is recorded.
- README points new contributors to the demo target before any real game profile work.

## Section 12: Improve Live Verification Ergonomics

Goal: make live verification easier to repeat and diagnose after the local demo target exists.

Likely work:

- Add a concise live verification checklist to the dashboard or docs.
- Surface the latest readiness blockers beside the selected run.
- Link directly from run history to the most useful screenshot artifact.
- Capture a final screenshot for successful live runs as well as graceful failures if that proves useful.
- Tighten artifact names when multiple waits or retries happen in the same state.

Acceptance checks:

- A contributor can run the demo target, dashboard, dry run, readiness check, and live run using documented steps.
- The resulting logs and artifacts are enough to diagnose target mismatch, resolution mismatch, anchor mismatch, and input refusal.

## Section 13: Exercise a Real Profile Pack

Goal: after live behavior is proven against the Local Demo Target, create one real profile pack with documented workflow notes and compatibility evidence.

Required behavior:

- Review the target workflow before writing the profile pack.
- Keep all game-specific behavior in YAML, assets, notes, and validation examples.
- Document known limitations and compatibility evidence.

Acceptance checks:

- The pack passes strict validation.
- The dashboard blocks live mode until checklist and dry-run requirements pass.
- Any live test is operator-confirmed and records useful artifacts.

Status: deferred. No specific real target has been operator-confirmed yet.
## Section 14: Build Profile-Pack Authoring Support

Goal: make new profile packs easier to create correctly after one real pack has exposed the practical authoring pain points.

Required behavior:

- Add a scaffold path for a new profile pack with `profile.yaml`, `assets/`, `notes.md`, and validation example folders.
- Validate profile-pack folder shape separately from profile YAML schema when useful.
- Check for missing assets, empty notes, incomplete known limitations, and incomplete compatibility evidence.
- Report checklist blockers in author-facing language that points to the specific pack field or file.
- Keep authoring support generic; do not add game-specific Python workflows.

Acceptance checks:

- A contributor can create a pack-shaped folder without copying an old pack by hand.
- Authoring checks fail clearly when required pack files, notes, assets, or compatibility fields are missing.
- Existing profiles and validation examples continue to pass strict validation.

Status: implemented in source-tree form with `game-script-dev scaffold-pack`,
`game-script-dev check-pack`, and `game_script_dev.authoring`.

## Section 15: Expand Dashboard Profile-Pack Management

Goal: make the Local Web Dashboard useful for profile-pack authors, not only operators starting runs.

Required behavior:

- Show profile-pack metadata, known limitations, and compatibility checklist status for the selected profile.
- Surface missing or incomplete pack evidence beside readiness blockers.
- Show the latest successful dry-run evidence used for live readiness.
- Display pack notes when present.
- Provide a compact status view for valid, invalid, incomplete, live-blocked, and live-ready packs.

Acceptance checks:

- The dashboard distinguishes profile validation errors from profile-pack compatibility blockers.
- The selected profile view shows why a pack is not live-ready without requiring the user to inspect YAML.
- The dashboard remains local-only and operator-focused.

Status: implemented. `/api/profiles` now includes pack metadata, notes, and
pack status for dashboard display.

## Section 16: Add Live Run Review Mode

Goal: make every live run reviewable after it finishes so operators and profile authors can understand what happened.

Required behavior:

- Present state transitions, actions, retries, failures, final result, and key timestamps as one run timeline.
- Link relevant screenshots and artifacts to the state or action that produced them.
- Show which anchors were expected and, when available, which anchors were detected.
- Make graceful termination and input refusal reasons prominent.
- Avoid replaying or re-executing live input during review.

Acceptance checks:

- A failed live run can be diagnosed from the review timeline and artifacts.
- A successful live run records enough evidence to confirm the expected workflow path.
- Run review works for the Local Demo Target before being relied on for real profile packs.

Status: implemented. Runs now retain a timeline and expose
`/api/runs/{id}/review` without re-executing input.

## Section 17: Tighten Real-Target Pack Notes

Goal: make adding more real target profile packs deliberate, repeatable, and backed by clear notes and compatibility evidence.

Required behavior:

- Record target-specific scope and workflow notes in pack notes.
- Require compatibility evidence before live mode is considered ready.
- Keep profile-pack checks focused on concrete pack files and schema data.

Acceptance checks:

- A new real profile pack is not considered ready without notes and compatibility evidence.
- Review language is reusable across targets while allowing target-specific limitations.
- The requirements remain visible in docs and authoring workflows.

Status: implemented through pack notes, checklist metadata, and authoring checks.

## Section 18: Package the Operator Experience

Goal: make the runner, dashboard, and demo workflows usable without requiring day-to-day source-tree commands.

Required behavior:

- Provide an Operator Package for Windows after the Local Demo Target and dashboard flow are stable.
- Ship the primary release as a publisher-signed, per-user EXE installer around the proven PyInstaller one-folder payload.
- Support currently serviced Windows 11 x64 releases through an explicit packaged test matrix for v1.
- Make the application and Live Run Worker Per-Monitor V2 aware and prove physical-client-pixel capture/input at 100%, 125%, 150%, and 200% scaling.
- Gate operation behind other windows on Background Capture Compatibility
  established by Live Readiness; otherwise require the non-minimized target to
  remain visible and interrupt on visibility loss.
- Include startup checks for runtime dependencies, writable log folders, profile discovery, and basic live adapter availability.
- Add the approved Live Confirmation summary and preserve readiness gating in packaged form.
- Replace legacy 24-hour cleanup with 30-day/5 GB managed Run-evidence retention and Pinned Run protection.
- Provide publisher-signed, hash-verified application updates that install only with explicit approval and never during an Active Run.
- Document how to launch the dashboard, run dry runs, start the Local Demo Target, and locate logs/artifacts.
- Keep source-based development workflows available for contributors.

Acceptance checks:

- An operator can launch the packaged tool, open the dashboard, run the demo dry run, and find logs.
- Install, repair, update, and uninstall preserve the User Workspace and Operational Data without requiring the main application to run elevated.
- The package requires the approved Live Confirmation summary and does not bypass readiness blockers or profile validation.
- Readiness and Live Confirmation distinguish background input from background
  capture; occluded operation is unavailable unless capture and required-anchor
  recognition have been verified.
- Operators can inspect storage usage, pin important Runs, and verify that automatic cleanup removes only eligible completed Runs.
- Update failure preserves a runnable prior installation, User Workspace, and Operational Data.
- Packaging docs explain what is included and what remains source-only.

Status: first application-shell slice implemented in the worktree. It includes
`game-script-dev-app`, an ephemeral loopback server, Edge/WebView2 hosting, the
PyInstaller one-folder spec and manifest, build validation script, explicit
Live Confirmation, atomic single-Active-Run admission, and the redesigned Run,
Build, and Settings workspaces. Automated and browser-based layout checks pass.
A real Windows x64 one-folder build and packaged-server smoke test also pass.
The signed installer and supported-matrix proof,
dedicated Live Run Worker/elevation boundary, immutable snapshots and ownership
recovery, background-capture probing, managed retention, and verified updater
remain outstanding.

## Section 19: Create Regression Fixtures From Safe Runs

Goal: convert safe, non-sensitive run artifacts into reusable fixtures so future changes can be tested without repeating live runs every time.

Required behavior:

- Identify which screenshots, logs, and run metadata are safe to store as fixtures.
- Add fixture documentation that explains provenance, expected state, expected anchors, and limitations.
- Use fixtures to test vision matching, state detection, validation, dashboard run review, and artifact rendering where practical.
- Avoid storing sensitive user data, real account state, monetized-reward evidence, or third-party content that should not live in the repository.
- Prefer Local Demo Target fixtures before real target fixtures.

Acceptance checks:

- Fixture-based tests catch regressions in state detection or run review without launching a live target.
- Fixtures are small, documented, and safe to commit.
- Real target fixtures are only added after they are reviewed and considered appropriate.

Status: implemented with safe Local Demo fixtures in `fixtures/local_demo` and
fixture validation helpers in `game_script_dev.fixtures`.

## Section 20: Build A Visual Profile Builder

Goal: make profile-pack authoring easier by adding a visual builder to the
existing local dashboard.

Required behavior:

- Open existing profile packs in a builder view.
- Show the profile as a state graph, not only raw YAML.
- Let authors inspect states, anchors, actions, transitions, pack metadata, and
  generated YAML.
- Add drag/reorder action editing for common actions before expanding to the
  full action surface.
- Use the existing Python schema and pack checks as the source of truth for
  validation.
- Save normal `profile.yaml` files that remain compatible with the CLI,
  dashboard, dry-run, readiness, and live-mode controls.
- Provide visual tools for named regions and template anchors after the basic
  builder is stable.

Acceptance checks:

- Existing profiles can be opened and understood through the builder without
  changing files.
- A simple action-list edit can be saved, validated, and dry-run through the
  existing dashboard workflow.
- Generated YAML remains readable and reviewable.
- Profile builder writes are constrained to the selected profile pack folder.

Status: Phase 1 foundation and the first Phase 2 writable slice are implemented.
The Build workspace loads a selected Profile through fingerprinted source and
structured-profile endpoints, then shows its state list, transitions, required
anchors, ordered Actions, source path, pack status, and notes. Authors can create
a blank Profile, edit recoverable raw-YAML Drafts, validate them, and Save with
external-change conflict protection and retained revision backups. The visual
State and Action flow remains read only. The full graph canvas, structured Action
editing, drag-and-drop authoring, and creation/asset tools remain planned in
`docs/PROFILE_BUILDER_UI.md`.

## Completed Sections

1. Target-window focusing in live mode.
2. Window liveness checks before live operations.
3. Live diagnostics and failure artifacts.
4. Optional OCR adapter support.
5. Pointer input behind focus and liveness checks.
6. Expanded profile validation and authoring feedback.
7. Expanded demo and validation profile coverage.
8. Local web dashboard.
9. Game expansion and profile-pack requirements.
10. Local Demo Target implementation slice and manual Windows live proof.
11. Local Demo Target profile-pack promotion.
12. Live verification ergonomics slice.
13. Real target pack exercise deferred pending operator/rules confirmation.
14. Profile-pack authoring support.
15. Dashboard profile-pack management.
16. Live run review mode.
17. Tighten real-target pack notes.
18. Operator Application and one-folder packaging proof; production release
    gates remain.
19. Safe Local Demo regression fixtures.
20. Visual Profile Builder foundation and writable raw-YAML Draft slice;
    structured editing phases remain.

## Source Coverage

This roadmap is grounded in:

- `CONTEXT.md`: Local Demo Target, Live Verification Scenario, Profile-Pack Authoring Support, Live Run Review, Operator Package, Regression Fixture, profile vocabulary, live confirmation, runtime adapters, detection strategies, named regions, and graceful termination.
- `README.md`: current runner status, dry-run usage, live-mode safety checks, logs, demo profile, OCR adapter boundary, pointer input, target-window control, and dashboard command.
- `docs/PROFILE_PACKS.md`: profile-pack folder shape and compatibility checklist contract.
- `docs/PROFILE_BUILDER_UI.md`: visual authoring UI concept, user roles,
  dashboard integration plan, and implementation phases.
- `docs/adr/0001-yaml-profiles-with-explicit-state-graphs.md`: game behavior stays in strict declarative YAML profiles with explicit state graphs.
- `docs/adr/0002-python-runner-with-dry-run-first.md`: Python remains the runner platform and dry-run remains the default before live input is allowed.
- `docs/adr/0003-split-live-runtime-adapters.md`: window, screen, vision, and input capabilities stay behind separate runtime adapters.
