# Operator Package

The first Windows Operator Application shell and PyInstaller one-folder proof
now exist in the source tree. The shell hosts the existing loopback dashboard
in Edge/WebView2, preserves current dashboard capabilities, and owns the local
HTTP server lifecycle. This is an implementation proof, not yet the signed
per-user production distribution described below.

## Primary Distribution Format

The production distribution is a publisher-signed, per-user Windows EXE
Operator Installer. It installs an already-proven PyInstaller one-folder
payload into a per-user application location, creates normal Start menu and
optional desktop shortcuts, registers repair and uninstall support, and does
not require the Operator Application itself to run elevated.

Installer startup checks for the Evergreen WebView2 Runtime before launching
the application. If it is missing, the installer offers Microsoft's per-user
Evergreen bootstrapper and explains any required download; an offline release
may instead carry the supported standalone installer. Dependency failure leaves
the application unlaunched with a repair action rather than falling back to an
unsupported browser or external dashboard window.

The PyInstaller one-folder output remains a packaging proof and diagnostic
artifact, not the primary end-user format. A portable ZIP and MSIX are deferred
until a demonstrated deployment need justifies their separate dependency,
identity, update, and support paths. The same signed installer contract is used
for verified application updates and rollback.

Relevant platform guidance:

- PyInstaller recommends proving a one-folder bundle before attempting other
  bundle forms: <https://pyinstaller.org/en/stable/operating-mode.html>
- Microsoft recommends checking for and deploying Evergreen WebView2 during
  application install or update:
  <https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution>
- MSIX uses a read-only package location and packaged desktop filesystem rules:
  <https://learn.microsoft.com/en-us/windows/msix/desktop/desktop-to-uwp-behind-the-scenes>

## Current Implementation Boundary

Implemented in the current source-tree slice:

- `game-script-dev-app` starts the existing dashboard on an automatically
  assigned `127.0.0.1` port and hosts it in an Edge/WebView2 desktop window
- the packaged manifest declares `asInvoker`, Per-Monitor V2 awareness, and
  long-path awareness
- `packaging/GameScriptDev.spec` includes the dashboard static assets in a
  PyInstaller one-folder payload
- `scripts/build_operator.ps1` verifies packaging dependencies and the expected
  executable and dashboard assets
- the application blocks normal window close while an Active Run exists
- the Run workspace has an explicit per-attempt Live Confirmation, and the
  backend atomically enforces one Active Run
- Dry Run, Live Run, Stop, readiness, history, timeline, logs, artifacts,
  profile-pack details, startup diagnostics, and the read-only Builder remain
  available inside the application

Not yet implemented or release-proven:

- the publisher-signed per-user installer, repair/uninstall registration, and
  WebView2 bootstrap path
- the dedicated authenticated Live Run Worker and worker-only elevation
- immutable Run Snapshots, ownership heartbeats, and startup recovery
- Background Capture Compatibility probing and visibility-loss interruption
- managed 30-day/5 GB evidence retention, Pinned Runs, evidence export, and
  source-qualified Profile References
- verified application updates and the supported Windows/DPI release matrix
- writable Builder drafts, drag-and-drop editing, safe save, and asset tools

The PyInstaller proof now has automated contract coverage plus a real Windows
x64 build and packaged-startup smoke test. The packaged server discovered all
workspace Profiles, passed startup diagnostics, and served the embedded HTML,
JavaScript, and CSS. This does not replace a visible interactive acceptance
test, code signing, installer validation, or the supported Windows/DPI release
matrix.

## Supported Windows Platform

Version 1 supports x64 editions of Windows 11 that are still within Microsoft's
servicing lifecycle and are listed in the release's tested support matrix. The
first release does not claim support for Windows 10, Windows Server, ARM64,
Wine, or compatibility layers. Separate architecture or legacy builds require
their own packaging and live capture/input validation before that boundary can
expand.

The Operator Installer checks architecture and the packaged minimum supported
Windows build before installation and provides a clear explanation and official
Windows lifecycle link when unsupported. A later lifecycle change does not
remotely disable an already installed offline application; instead, future
GameScriptDev releases update their declared and tested matrix. Diagnostics
always record the exact OS edition, version, build, architecture, WebView2
version, and application version for support evidence.

The release pipeline tests installation, first launch, target capture,
background and foreground input paths, Live Run Worker elevation, Stop and
ownership failure, update, repair, and uninstall on the supported Windows 11
x64 matrix. Passing unit tests on another platform is not presented as packaged
support.

### DPI And Display Scaling

The Operator Application and every Live Run Worker declare Windows Per-Monitor
V2 DPI awareness in their packaged manifests. Startup diagnostics verify the
effective awareness context before Live Readiness can pass. The shell responds
to monitor DPI changes, while capture and input adapters operate in
unvirtualized physical coordinates.

Profile resolution, named regions, screenshots, templates, and absolute target
points are defined in Physical Client Pixels. Target Preview overlays transform
between an image's intrinsic physical-pixel dimensions and its displayed CSS
size; displayed coordinates are never serialized back to a Profile without
that conversion. Before live input, the worker rechecks target identity,
monitor DPI, client geometry, and capture dimensions.

The packaged matrix covers 100%, 125%, 150%, and 200% scaling; starting on each
scale; moving the application and target between monitors with different
scales; and docking or display changes. A proof that works only at 100% scaling
does not satisfy the v1 platform gate. Microsoft recommends Per-Monitor V2 for
desktop applications:
<https://learn.microsoft.com/en-us/windows/win32/hidpi/high-dpi-desktop-application-development-on-windows>.

The admitted Live Run Snapshot records the target monitor identity and
effective DPI. A Target Display Change during Live mode immediately releases
continuous or held input, stops further Actions, captures final evidence when
safe, and marks the Run `Interrupted — target display changed`. It is not sent
through Profile failure Transitions and is never resumed automatically. A later
Live Run requires a new preview, geometry and DPI verification, Live Readiness,
and Live Confirmation.

Moving the Operator Application itself between monitors does not interrupt the
Run because execution coordinates belong to the target window. Dry Run and
authoring previews may update after a Target Display Change without being
classified as live-input interruptions.

The admitted snapshot also fixes the target's physical client width and height.
Minimization or a later client-size change is a Target Geometry Change and
follows the same input-release, evidence, and interrupted-Run path, including
when the Profile Resolution Policy is `ignore`. The application does not
restore, resize, or continue controlling the changed target automatically.

Repositioning a non-minimized target within the same monitor and DPI is allowed
when its client dimensions remain unchanged. Background messages continue to
use target-client coordinates, while foreground capture and pointer Actions
recalculate and verify the current client-to-screen origin immediately before
use. A failed conversion or off-screen target point stops input rather than
using a stale origin.

### Target Visibility And Background Capture

Background Window Message Input and background capture are separate
capabilities. Selecting a background input mode does not prove that the target
application will render usable frames while another window covers it.

The safe default is `Visible target required`. Live Readiness may instead
record Background Capture Compatibility only after a target-client capture
probe produces the expected dimensions and the Saved Profile Version's
required anchors can be recognized from the result while the target is
occluded. A successful API call, a non-empty image, or successful background
input alone is not sufficient evidence.

When the finding is absent, stale, or unsuccessful, Live mode remains available
only while the non-minimized target stays visible. If it becomes occluded, the
worker releases held input, preserves evidence, and interrupts the Run rather
than continuing from an untrusted frame. When compatibility is verified, the
target may remain behind other windows, but minimization is still a Target
Geometry Change and never becomes supported by this capability.

The Target Preview, Readiness details, and Live Confirmation present capture
compatibility separately from input mode. An occluded-capture failure during a
Live Run never silently unlocks or switches to a capture path that was not
verified by the admitted readiness result.

The current source-tree runtime is not yet compliant with this packaged
contract: it can restore a minimized background target and can fall back from
`PrintWindow` capture to screen-area capture. Packaging work must replace those
behaviours with the fail-closed rules above before the Windows release gate can
pass.

## Startup Checks

Run:

```powershell
game-script-dev doctor --workspace . --logs logs
```

The same checks are available to the dashboard at `/api/startup-checks`.

Checks cover:

- Python version
- runtime dependencies
- writable log folder
- profile discovery
- profile validation
- Local Demo Target profile validity
- live adapter import boundary

### First Launch Setup

The first launch uses one compact setup surface with three choices: create or
use the recommended `Documents\GameScriptDev` User Workspace, select an
existing workspace or source checkout, or create a workspace in another
location. No directory is created, moved, or modified until the operator
confirms the displayed absolute path.

Selecting an existing location first performs a read-only scan and reports its
Profile Pack count, invalid Packs, source-qualified duplicates, path conflicts,
and write access. An equal pack identifier in Built-in and User sources is
reported for clarity but is not a blocking conflict. The setup also displays the separate
`%LOCALAPPDATA%\GameScriptDev` Operational Data location; this location is not
presented as a Profile workspace. The application does not require an account,
network connection, telemetry choice, or unrelated product tour.

The only optional network choice is an unchecked `Check weekly for updates`
control with a plain-language explanation and privacy details. Declining it
does not reduce application functionality, and `Check for Updates` remains
available manually in Settings.

After selection, startup diagnostics run before normal workspace controls are
enabled. Success opens Run Workspace with no Run started. A blocking failure
keeps the application in a safe repair state with Retry, Choose Workspace, and
diagnostic-detail actions; it does not silently substitute another path or
enable execution. Keyboard order, persistent field labels, and visible focus
make the setup operable without drag-and-drop or pointer input.

## Application Shell Navigation

The single Operator Application uses a fixed Application Bar immediately below
the native Windows title controls; it does not replace standard minimise,
maximise, close, or system-menu behaviour. The bar provides three labelled
workspace choices:

- **Run** opens the one-screen Run Workspace.
- **Build** opens Profile Builder.
- **Settings** opens application, workspace, storage, and diagnostic settings.

Switching workspaces updates the existing shell without launching another
window or reloading the backend. The selected Profile carries between Run and
Build when it is available in both contexts. Opening a Built-in Profile Pack in
Build keeps it read-only and offers the approved user-owned copy workflow.
Recoverable draft state is represented by a visible badge and does not require
a save-or-discard interruption merely to change workspace.

Active Run identity, mode, status, and immediate Stop remain visible in the
Application Bar from every workspace. Workspace labels and icons are both used,
selection is exposed accessibly, and keyboard navigation follows the visual
order. The Application Bar stays compact; Profile-specific commands belong to
the active workspace rather than accumulating in the global row.

Workspace switching remains available during an Active Run. Build permits
draft editing and explicit saves because the Active Run continues from its
immutable Run Snapshot; changed Profile content cannot affect that execution.
Settings remains inspectable, but controls that can change input or worker
behaviour, workspace and Operational Data locations, retention cleanup,
application updates, or other Run ownership dependencies become read-only
until the Run reaches a terminal status. Each locked control explains which
Active Run owns the lock and links back to it.

Appearance, accessibility, diagnostics viewing, and evidence review remain
available when they do not mutate the Active Run's dependencies. The lock is
also enforced by the backend, so navigating directly to a settings operation
cannot bypass the visible disabled state.

## Profile Sources And Identity

Every selectable Profile uses a source-qualified Profile Reference such as
`builtin:<pack-id>` or `user:<pack-id>`. A User Pack never silently overrides or
hides a Built-in Pack with the same identifier. Lists, search results,
readiness, Builder drafts, API requests, and persisted selections carry the
qualified reference; display rows show labelled `Built-in` or `User` badges in
addition to any visual styling.

Run Snapshots record the Profile Reference, content version or fingerprint, and
complete executable snapshot so later source changes do not make provenance
ambiguous. Copying a Built-in Pack produces an independent User Pack and stores
portable Pack Lineage identifying its Built-in source and copied version. That
lineage supports comparison and update notices but never causes inherited or
automatic runtime changes.

The copy also captures an immutable Lineage Baseline: the original structured
text content and a relative asset inventory with SHA-256 checksums. This is
enough to distinguish unchanged, user-edited, upstream-edited, and
both-edited items after an application update without duplicating every binary
asset. When the installed Built-in fingerprint changes, the user copy receives
a non-destructive `Source Update Available` notice.

## Window And Run Lifecycle

The current shell implements the conservative first step: it refuses a normal
close while an Active Run exists and tells the operator to stop the Run first.
The richer close-and-stop lifecycle below remains the production target.

Closing the main window during an Active Run opens a focused summary of the
Run's Profile, mode, current State, and elapsed time. It offers `Continue
Running` and `Stop Run and Exit`, with continuing focused by default. There is
no normal option to exit while leaving an Application-Managed Run detached.

`Stop Run and Exit` sends the immediate authenticated Stop request, shows
shutdown progress, waits for bounded cleanup, and closes after the Run becomes
terminal. If the Live Run Worker does not acknowledge within its timeout, the
application terminates it and records interruption when possible before exit.
Minimise and maximise retain their ordinary Windows meanings; the application
does not silently convert Close into a system-tray action.

A crash, forced process termination, or operating-system shutdown may prevent
the dialog from appearing. The Run ownership heartbeat remains the safety
boundary in those cases: the Live Run Worker releases input and fails closed
when application ownership disappears.

### Startup Recovery

On startup, the application checks persisted Run ownership before enabling new
execution. A non-terminal Run owned by a previous application session is never
resumed. The application verifies that its identified worker is no longer able
to send input; if safe termination cannot be established, Live Run remains
blocked with a diagnostic rather than assuming the worker is gone.

The stale record becomes an Interrupted Run with reason `application ownership
lost`, a terminal timestamp, and all available Run Snapshot, Timeline, log, and
artifact evidence preserved. Run Workspace opens its Run Outcome Summary and a
startup notice offers `Review Evidence` and `Dismiss`. Dismiss removes only the
notice, not the Run record or evidence. The same recovery treatment applies to
Dry and Live modes, and no recovery action starts input or continues from the
last State.

### Healthy Startup Restoration

When ownership recovery and startup diagnostics are healthy, the application
restores the last Run, Build, or Settings workspace and its last selected
Profile. This preference includes stable view context such as the selected
detail tab and panel dimensions, but excludes transient dialogs, confirmation
state, pending commands, and execution. Restoring a Profile performs only the
approved observational validation, readiness, and preview refresh; it never
starts a Run.

An Interrupted Run notice overrides normal restoration and opens the affected
Run. If the remembered Profile no longer exists, the application falls back to
Run Workspace, clears the stale selection, and explains the change. If the User
Workspace itself is unavailable, the application remains open with execution
blocked and offers workspace repair or selection instead of silently creating
a replacement in a different location.

## Operator Flow

1. Start the source Operator Application with
   `game-script-dev-app --workspace . --logs logs` (or start the browser-only
   dashboard with `game-script-dev-dashboard --workspace . --logs logs`).
2. Start the Local Demo Target with `python -m game_script_dev.demo_target`.
3. Select `demo__local_target` in the dashboard.
4. Run a dry run and confirm readiness.
5. Select `Live Run` only after blockers are resolved and the Local Demo Target
   is confirmed. Review the per-attempt summary, then select `Start Live Run`.
6. Review the run timeline, log, and artifacts after completion.

The dashboard and desktop shell now implement the per-attempt Live Confirmation
specified in `docs/RUN_WORKSPACE_UI.md`. The backend requires the confirmation
value, rechecks readiness, and rejects a competing Active Run. The CLI still
requires typing `RUN` unless `--yes` is supplied. Live verification should use
the safe Local Demo Target and must not bypass readiness blockers, profile
validation, or the dry-run-first workflow.

The implemented application presentation and the remaining production
lifecycle work are specified in `docs/RUN_WORKSPACE_UI.md`.

## Retention Transition

The current source-tree dashboard uses the legacy automatic 24-hour cleanup
documented in `README.md`. The packaged Operator Application will replace it
with ADR 0011: 30-day retention, a 5 GB Run-evidence budget, and automatic
protection for Pinned Runs. Documentation must continue to distinguish these
behaviours until the packaged policy is implemented.

## Application Updates

An available release is presented with version, publisher, release notes,
download size, and Built-in Pack changes before any installation approval. The
download is staged outside the installation, then both its expected package
hash and trusted publisher signature are verified. A failed or unverifiable
download is discarded with a diagnostic and is never offered as runnable.

Installation requires an explicit `Install Update` action and cannot begin
during an Active Run. The updater closes the application through its normal
ownership checks, replaces only installed application and Built-in content, and
preserves the User Workspace and Operational Data. Installation is transactional
or retains the prior installed version for rollback; a failed update must not
leave a partially runnable application.

Restart performs startup diagnostics and reports the installed version. New
Built-in Pack fingerprints create the approved Source Update notices for
user-owned copies rather than modifying them. Updates are never installed
silently, scheduled to apply later without confirmation, or treated as
permission to move or delete user-authored content.

Automatic update checks are disabled until the operator explicitly enables
them. When enabled, the application checks no more than once every seven days
and sends only the installed version and platform information needed to select
a compatible release; it never sends Profile content, Run evidence, workspace
paths, or usage telemetry. A check failure does not block startup or execution.
Manual checking is always available, and either kind of check can only notify:
download and installation still require the separate explicit approval above.
