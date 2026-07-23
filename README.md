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
- background window-message live input for compatible targets
- foreground verification only when a profile requires the foreground fallback
- liveness and identity checks before live screenshots and input
- contextual live screenshot artifact names
- optional OCR adapter support behind the vision adapter boundary
- named-region pointer clicks through window-relative background messages or foreground desktop input, depending on profile compatibility
- local web dashboard for profile discovery, validation, dry runs, readiness, logs, and artifacts
- local Windows Operator Application shell with the same dashboard capabilities
- one-screen Run workspace with an explicit per-attempt Live Confirmation
- Profile Builder foundation with in-app blank Profile creation, recoverable YAML Draft editing, validation, and conflict-safe Save
- atomic single-Active-Run admission enforced by the backend
- profile-pack metadata and live-mode compatibility checklist gating
- profile-pack scaffold/check authoring commands
- run review timeline and startup checks in the dashboard
- repo-owned Local Demo Target for safe live verification
- safe Local Demo regression fixtures
- capped global interruption recovery attempts
- terminal states
- daily log folders
- automatic 24-hour retention for logs and generated artifacts
- validation example profiles
- demo profile

The current adapter boundaries are:

- `WindowAdapter`
- `ScreenAdapter`
- `VisionAdapter`
- `InputAdapter`

## Environment Setup

This repository is intended to run from a project-local virtual environment on
Windows with Python 3.11. Using a local `.venv` avoids the "works on one
computer but not another" problem caused by globally installed packages.

Bootstrap a fresh machine with the repo-owned setup script:

```powershell
.\scripts\setup.ps1
```

That script will:

- create `.venv/`
- upgrade `pip`
- install the project plus developer tools from `.[dev]`
- optionally install OpenCV support when requested
- run the built-in `doctor` check to catch missing runtime pieces early

Optional flags:

```powershell
.\scripts\setup.ps1 -IncludeOptionalOpencv
.\scripts\setup.ps1 -IncludeOptionalOcr
```

OCR requires both the Python package and the native Tesseract application to be
installed on the machine. The Python package alone is not sufficient.

If you prefer the manual path, the equivalent commands are:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
python -m game_script_dev doctor --workspace . --logs logs
```

The repo also includes `.python-version` with `3.11` so version managers such
as `pyenv-win` can automatically select the expected interpreter.

The first concrete vision implementation uses Pillow and NumPy for small, testable template matching. It can be replaced by OpenCV later if performance or matching tolerance needs increase.

State execution failures retry the current state up to the profile `max_retries` value. After that, the runner follows `on_failure` when it names another state, or gracefully terminates when `on_failure` is `graceful_termination`.

Global interruptions run their configured recovery actions only up to the interruption's `max_retries` value while the interruption remains visible. If the interruption persists past that cap, the current state fails through the normal retry and failure policy.

Profiles define click coordinates as named regions, then actions reference those names. This keeps coordinate data centralized and lets validation catch missing or misspelled regions before a run starts.

Live mode can now enumerate visible Windows application windows and match the target by process name and/or window title. It verifies the configured resolution policy, checks liveness before live screenshots and input, captures the matched target window into the run artifact folder, and can evaluate template anchors against those captures. Profiles default to `target.input_mode: background_window_messages`, which sends keyboard and mouse messages directly to the matched window handle without requiring foreground ownership. Profiles that use `target.input_mode: foreground` take the compatibility fallback and must focus and confirm the foreground handle before live desktop input is sent. Live `wait` actions, a limited allowlist of keyboard press/hold actions, and named-region pointer clicks are available with bounded duration guards. Live `press_key` now uses a short default dwell instead of a zero-duration down/up burst because some game clients can miss taps that are shorter than one input-sampling window. OCR is optional and can be injected behind the vision adapter boundary.

In live mode, `wait_for_state` is a bounded polling loop over screen capture and anchor detection. It uses the profile default timeout unless the action supplies `timeout_seconds`, and supports `poll_interval_seconds` for tuning. Live polling uses a small positive minimum interval to avoid tight screenshot loops.

## Run The Demo

Start the local demo target in one terminal:

```powershell
$env:PYTHONPATH = "src"
python -m game_script_dev.demo_target
```

Then run the demo profile in another terminal:

```powershell
$env:PYTHONPATH = "src"
python -m game_script_dev --profile profiles/demo/profile.yaml
```

The canonical profile-pack version lives at:

```powershell
$env:PYTHONPATH = "src"
python -m game_script_dev --profile profiles/demo/local_target/profile.yaml
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
Records older than 24 hours are automatically pruned from `logs/` and the
workspace `artifacts/` folder when a run starts or the dashboard launches.

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

The dashboard discovers profiles, validates them, launches explicit dry runs,
shows readiness blockers before live mode, and surfaces run history, logs,
artifacts, current state, final result, and failure reason. A ready Live Run opens
the per-attempt confirmation summary specified in `docs/RUN_WORKSPACE_UI.md`;
the backend rechecks readiness and requires the confirmation value before it
admits the run. New contributors should use the `Local Demo Target` profile
pack before any real game profile work.

### Desktop Operator Application

Install the optional desktop dependency, then launch the same local dashboard
inside the Windows application shell:

```powershell
python -m pip install -e .[desktop]
game-script-dev-app --workspace . --logs logs
```

The shell binds its private dashboard server to an automatically assigned
loopback port, uses the Edge/WebView2 renderer, and shuts the server down with
the window. It refuses a normal close while a Run is active. The current shell
is a source and packaging proof; it does not yet include the signed per-user
installer, dedicated elevated Live Run Worker, updater, or managed evidence
retention described in `docs/OPERATOR_PACKAGE.md`.

To build the PyInstaller one-folder proof on Windows:

```powershell
python -m pip install -e .[package]
.\scripts\build_operator.ps1
```

The expected output is `dist/GameScriptDev/GameScriptDev.exe`. The proof build
has been generated and smoke-tested on a Windows x64 development machine: the
packaged server started, discovered the workspace Profiles, passed startup
diagnostics, and served its embedded interface assets. It must still be
exercised on the full supported Windows/DPI matrix before it is treated as a
distributable release.

The Local Demo Target pack uses `target.input_mode: foreground` because Tk
windows do not reliably accept direct background mouse messages. Live input is
sent only after the runner refocuses and verifies the matched demo window.

Run the operator startup checks from source:

```powershell
$env:PYTHONPATH = "src"
python -m game_script_dev doctor --workspace . --logs logs
```

Run the automated test suite after setup:

```powershell
$env:PYTHONPATH = "src"
python -m pytest
```

For manual live verification against the repo-owned target, see
[docs/LOCAL_DEMO_TARGET.md](docs/LOCAL_DEMO_TARGET.md).

## Profile Packs

Reusable game or game-mode profiles can be grouped as profile packs under
`profiles/<game>/<mode>/`. A pack keeps `profile.yaml`, assets, notes, and
validation examples together. Profile packs declare target identity, resolution,
detection strategy, states, regions, actions, interruptions, known limitations,
and a compatibility checklist.

See [docs/PROFILE_PACKS.md](docs/PROFILE_PACKS.md) for the folder structure and
checklist contract. The dashboard blocks live mode for profile packs until their
compatibility checklist is complete and a successful dashboard dry run has been
recorded. Intentionally infinite manual-stop profiles can opt into treating an
operator-stopped dashboard dry run as that evidence with
`execution.manual_stop_is_dry_run_success: true`. If the workflow itself should
loop until the operator stops it, also set `execution.allow_infinite_run: true`
so the engine does not fail the run after the normal dry-run step cap.

For a full annotated authoring example, see
[docs/PROFILE_TEMPLATE.md](docs/PROFILE_TEMPLATE.md).

The planned visual authoring UI is documented in
[docs/PROFILE_BUILDER_UI.md](docs/PROFILE_BUILDER_UI.md). It describes the
dashboard-based Profile Builder concept, user roles, editor structure, backend
shape, and phased implementation plan.

Create and check a new pack shape:

```powershell
$env:PYTHONPATH = "src"
python -m game_script_dev scaffold-pack --output profiles/example/daily --game "Example" --mode "Daily"
python -m game_script_dev check-pack --profile profiles/example/daily/profile.yaml
```

Safe fixture rules live in
[docs/REGRESSION_FIXTURES.md](docs/REGRESSION_FIXTURES.md).

## Live Mode

Live mode is always an explicit operator command. The CLI additionally requires
typing `RUN` unless `--yes` is supplied. The dashboard and Operator Application
require both passing readiness and an explicit per-attempt Live Confirmation;
the backend rejects missing or stale confirmation and admits at most one Active
Run. The canonical input path posts keyboard and mouse messages directly to the
target window handle when the profile supports `background_window_messages`.
The foreground path is a compatibility fallback for targets that require
global desktop input. In both cases, the runner checks that the original target
is still alive before live screenshots and input, and fails closed when the
window cannot be confirmed. The dedicated least-privilege Live Run Worker
described in the packaging plan remains future work.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for the implementation roadmap and current checkpoint.

## Reproducibility Guidance

For this project, Docker is useful for linting, tests, or pure validation
workflows, but it is not the best primary solution for live automation because
the runner depends on the host Windows desktop, target windows, screenshots,
and input APIs.

The most reliable baseline is:

- pin the Python version to 3.11
- always work inside `.venv`
- install from the repo manifest instead of ad hoc `pip install` commands
- keep every required package declared in `pyproject.toml`
- run `doctor` and `pytest` on each new machine

If a machine needs a package that is not declared here, treat that as a repo
issue and add it to the manifest instead of fixing only that one computer.
