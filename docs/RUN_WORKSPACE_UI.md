# Run Workspace UI Plan

This document defines how the existing local dashboard becomes the operator
side of the Windows Operator Application without losing any current capability.
The redesign changes information architecture, not runner safety or execution
semantics.

## Implementation Status

The first Run workspace slice is implemented in the source dashboard and the
desktop shell. It includes the fixed Application Bar, explicit Dry Run,
readiness-gated per-attempt Live Confirmation, authoritative Active Run status
and Stop, independent Profiles/Run History and detail tabs, Target Preview,
Progress & Outcome, startup diagnostics, and compact-width stacking without
page-level overflow. The backend atomically enforces one Active Run and rejects
unconfirmed Live starts.

The dedicated authenticated Live Run Worker, immutable Run Snapshot, ownership
heartbeat and startup recovery, source-qualified Profile References, managed
evidence retention, and verified Background Capture Compatibility remain
future implementation phases. The current shell conservatively refuses to
close during an Active Run instead of yet offering the planned bounded
`Stop Run and Exit` flow.

## Product Goal

An operator should be able to select a Profile, understand whether it can run,
start or stop it, follow its progress, and inspect its evidence from one stable
workspace. Primary status and controls remain visible while detailed material
uses internal panels instead of making the whole application page scroll.

## One-Screen Master-Detail Layout

### Fixed Command Bar

Below the global Application Bar, the Run command bar shows the selected
Profile, current execution state, Dry Run, and Live Run. Live Run retains
readiness gating and explicit confirmation. The global Stop becomes visually
dominant while a Run is active; unavailable commands remain visible with an
adjacent explanation rather than disappearing.

Stop is immediate and never opens a confirmation dialog. One pointer or
keyboard activation sends an authenticated cancellation request and changes
the command to a disabled `Stopping` state so repeated activation is harmless.
The request is idempotent, and its accessible label identifies the Active Run.
The runner releases continuous or held input before final logging and cleanup.
If the Live Run Worker does not acknowledge cooperative cancellation within a
bounded timeout, the application terminates that worker, records an interrupted
result when possible, and sends no further input. Completed and historical Runs
never expose an active Stop command.

### Live Run Confirmation

Selecting `Live Run` while blocked opens the relevant Readiness details rather
than a confirmation. Once Live Readiness passes, the Operator Application
opens a concise summary identifying the Saved Profile Version, matched target
window and process, input mode, and whether the dedicated Live Run Worker will
request elevation. It plainly states that live mouse or keyboard input may be
sent to that target.

`Cancel` has initial focus, `Escape` cancels, and the affirmative control is
labelled `Start Live Run` rather than a generic `OK`. Confirmation is required
for every attempt and is never remembered as a preference. The backend
rechecks readiness after confirmation before creating the immutable Run
Snapshot and starting or elevating the worker. The application does not require
typing a confirmation phrase because the summary, readiness gate, deliberate
activation, and per-run worker boundary provide the intended protection with
less repetitive friction.

### Left Selection Rail

The left rail switches between searchable `Profiles` and `Run History` lists.
It does not stack both full lists vertically. Each row uses a compact summary,
status, source badge, and timestamp where relevant, and the list scrolls
independently. Profiles with equal pack identifiers remain separately
selectable by their source-qualified Profile References.

Selecting a Profile opens its Run Overview. Selecting a historical or active
Run changes the overview and detail tabs to that immutable Run Snapshot while
retaining a clear link back to its Profile.

Profile selection is observational: it refreshes validation, readiness, and
the Target Preview but never creates a Run. A Dry Run begins only through the
explicit command-bar action or its documented keyboard shortcut. The overview
may recommend Dry Run as the next safe action, but does not activate it on the
operator's behalf. This keeps Run History intentional and prevents browsing
between Profiles from performing unexpected work.

## Single Active Run

The Operator Application admits at most one Active Run across all Profiles and
both Dry and Live modes. The backend enforces this atomically; disabled buttons
are only the visible explanation and are not the safety boundary. A new Run
cannot begin until the existing Run reaches a completed, failed, cancelled, or
interrupted terminal status.

If another start request reaches the backend, it is rejected with a conflict
response containing the Active Run summary. No queued or placeholder Run is
created. The command bar explains which Run is active and offers `View Active
Run` and `Stop Active Run`. If that Run finishes while the message is visible,
the requested Run is still not replayed automatically; the operator must issue
a fresh command, and Live Run must pass readiness and confirmation again.

While a Run is active, its identity and status remain pinned in the command bar
even if the operator browses another Profile or historical Run. `Stop` always
targets the Active Run and includes its Profile name in the accessible label.
Dry Run and Live Run remain visible but unavailable with an explanation linking
back to the Active Run. Browsing history and editing a Profile Draft remain
available because the Active Run uses its immutable Run Snapshot.

Saving a Profile while another Run is active does not modify, restart, or mark
that Run stale; the Outcome continues to identify its original Run Snapshot.
The new Saved Profile Version becomes relevant only to later validation,
readiness, Dry Run, or Live Run commands.

### Run Overview

The centre is reserved for the information needed at a glance:

- selected Profile or Run identity
- Target Preview and capture status
- target, client-resolution, background-capture compatibility, execution, and
  result summaries
- highest-severity readiness blockers or current Run failure
- active State and Run progress when execution is in progress
- the next safe recommended action

The overview does not repeat complete logs, artifact lists, pack notes, or the
full readiness checklist. Those remain one click away in the fixed detail
panel. The overview changes from pre-run readiness to active monitoring and
then final outcome without changing its spatial location.

During execution, a compact Run Progress Card remains beside the Target
Preview. It shows mode and status, current State, current Action or wait,
elapsed time, retry count, the latest meaningful event, and whether Stop has
been requested. Updates preserve the card's dimensions so the workspace does
not jump as labels change. A failure summary may replace the last-event line,
with full context available in Timeline or Logs.

The card does not show a completion percentage: state-machine retries, loops,
bounded waits, and manual-stop Profiles do not have a trustworthy linear
percentage. It also does not reproduce the scrolling event list. The Timeline
tab remains the complete chronological source, while the Progress Card answers
only what is happening now.

When the Run reaches a terminal status, the Progress Card transforms in place
into a Run Outcome Summary. It distinguishes success, failure, cancellation,
and interruption using text and icons as well as colour, and shows duration,
final State, primary failure reason when present, latest screenshot or evidence
link, and Timeline and Artifact counts. Its actions include `Review Timeline`,
`Open Artifacts`, and `Run Again` when applicable.

The summary remains tied to the immutable Run Snapshot and stays visible until
the operator selects another Profile or Run. It does not automatically open a
detail tab, return to readiness, or cover the workspace with a completion
dialog. Full technical errors remain in Timeline and Logs rather than expanding
the summary indefinitely.

An Interrupted Run recovered on application startup uses this same Outcome
Summary with `Application ownership lost` as its primary reason and prominent
access to preserved evidence. It is not presented as paused or resumable.

A Live Run interrupted by a Target Display Change uses the same presentation,
identifies the prior and detected monitor/DPI values, and offers `Refresh
Readiness` rather than `Resume`. Run Again still follows current readiness and
the complete Live Confirmation flow.

Target Geometry Change outcomes similarly show whether minimization or client
dimensions caused the interruption and compare admitted with detected size.

A visibility-required Run that loses an unobstructed target view uses the same
Interrupted outcome pattern, identifies `Target became occluded`, and offers
`Refresh Readiness` rather than `Resume`. A Run with verified Background
Capture Compatibility may continue behind other windows, but still interrupts
on minimization or an untrusted capture result.

### Run Again

`Run Again` always creates a new Run identifier and immutable Run Snapshot from
the current Saved Profile Version; it never silently replays the historical
snapshot. If that Saved Profile Version differs from the completed Run, the
Outcome Summary states the version change and labels the action `Run Current
Version`.

Repeating a Dry Run is an explicit new Dry Run and still passes validation and
single-Run admission. Repeating a Live Run never starts directly: the
application recalculates current Live Readiness and requires a new Live
Confirmation before it creates the Run. Historical Live Run Snapshots remain
available for evidence and comparison but are never executable through this
shortcut.

### Run Detail Panel

The fixed right panel provides these tabs:

- **Readiness:** all blockers, warnings, target checks, compatibility checks,
  runtime or worker status, and the live-verification checklist
- **Timeline:** structured State, Action, retry, failure, and completion events
- **Logs:** the complete incrementally loaded text log
- **Artifacts:** latest screenshot first, followed by all available evidence
- **Profile Pack:** pack status, metadata, notes, and validation details

Readiness shows a separate `Background Capture` row with one of three concise
results: `Verified for occlusion`, `Visible target required`, or `Probe failed`.
It never infers this result from the Profile's input mode. Target Preview repeats
the active visibility requirement in its status line, and Live Confirmation
states whether the target may be behind other windows or must remain visible.

Tabs show counts or severity badges so hidden problems remain discoverable.
The selected tab scrolls internally; changing tabs never replaces the Run
Overview. During an active Run, Timeline is the default detail. Before a Run,
Readiness is the default. After completion, the last selected tab is preserved.

## Run Evidence Retention

The packaged Operator Application stores Run records, logs, and artifacts under
its `%LOCALAPPDATA%\GameScriptDev` Operational Data area. Completed, unpinned
Runs are retained for 30 days. A separate 5 GB evidence budget applies across
their Run Snapshots, timelines, logs, and artifacts; when the budget is
exceeded, cleanup removes the oldest completed, unpinned Runs until usage is
within budget.

Active Runs and Pinned Runs are never removed automatically. If protected data
alone exceeds 5 GB, the application keeps it, displays a storage warning, and
offers review, export, unpin, and manual-delete actions rather than silently
breaking the protection promise. Settings, recovery drafts, and editable
Profile Packs are outside the Run evidence cleanup budget.

Cleanup runs after application startup and after a Run reaches a terminal
status. Run History shows a pin control and retention state on each completed
Run; Settings shows current evidence usage, the configured defaults, and the
last cleanup summary. Export creates a portable evidence archive before any
optional deletion. The current source-tree dashboard's 24-hour file cleanup is
legacy behaviour until this packaged retention model is implemented.

User-initiated deletion operates on the complete Run Evidence Unit and sends it
to the Windows Recycle Bin. A confirmation identifies the Profile, mode,
terminal status, completion time, and storage size, with Cancel focused by
default. Active Runs cannot be deleted, and a Pinned Run must be explicitly
unpinned first. After deletion, the Run disappears from the application index;
restoring its evidence unit to the original location makes it discoverable
again after refresh or restart.

If the Recycle Bin operation is unavailable or fails, the application reports
the failure and leaves the evidence untouched. It never falls back silently to
permanent deletion. Automatic retention cleanup remains permanent and applies
only to evidence already eligible under the age, budget, activity, and pinning
rules.

### Evidence Bundle Export

Export is available after a Run reaches a terminal status and creates a
standard ZIP Evidence Bundle containing:

- a self-contained offline `index.html` outcome and review summary
- a versioned `manifest.json` with Run identity, application version, timestamps,
  terminal result, format version, file inventory, and recorded omissions
- the immutable Run Snapshot and recorded Live Readiness result
- the complete Timeline and text log
- original artifact files under a stable relative structure
- SHA-256 checksums for every bundled evidence file

The offline summary makes no network requests and the JSON remains usable
without GameScriptDev. Export first builds and verifies a temporary archive,
then atomically places it at the user-selected destination. It never silently
overwrites an existing file and does not modify, pin, or delete the source Run.
If an expected source file is already missing or unreadable, export reports the
problem and requires the operator to cancel or deliberately create a bundle
whose manifest records the omission.

The export dialog shows the destination, estimated size, included content, and
a reminder that screenshots, logs, window titles, or paths may contain private
information. The default filename combines a safe Profile label, completion
timestamp, and short Run identifier while keeping the `.zip` extension.

The application exposes two deliberately different actions:

- `Export Full Evidence` includes the complete Run Evidence Unit and identifies
  the bundle mode as `full`.
- `Create Shareable Copy` lets the operator exclude screenshots, logs, target
  metadata, and absolute local-path fields before export.

A Shareable Bundle uses its own checksums and records every excluded category
and unavailable source file in the manifest. Its offline summary displays a
persistent `Reduced evidence` notice, and imports or reviewers must never treat
it as complete proof. Structured paths that remain included are converted to
bundle-relative references where possible.

Shareable export does not attempt automatic OCR, image blurring, or free-text
log redaction because those transformations can miss private content or alter
evidence unpredictably. Before creation, the UI previews the included
categories and warns that any retained screenshots or unstructured logs must be
reviewed by the operator. Neither export mode changes the source Run Evidence
Unit.

## Existing Capability Map

| Current dashboard capability | Run Workspace location |
| --- | --- |
| Profile discovery and validation status | Profiles list and Profile Pack tab |
| Profile selector and refresh | Left selection rail |
| Target preview stream and metadata | Run Overview |
| Target, resolution, and compatibility status | Run Overview summary and Readiness tab |
| Readiness blockers and warnings | Run Overview summary and Readiness tab |
| Runtime privilege status | Readiness tab and command explanation |
| Whole-dashboard administrator relaunch | Replaced by the dedicated Live Run Worker elevation flow from ADR 0006 |
| Dry Run, Live Run, and Stop | Fixed command bar |
| Explicit Live Run confirmation | Command-bar confirmation flow |
| Current State and final result | Run Overview |
| Run History | Left selection rail |
| Selected Run readiness | Readiness tab scoped to its Run Snapshot |
| Run review timeline | Timeline tab |
| Incremental logs | Logs tab |
| Latest screenshot and artifact list | Artifacts tab, with latest evidence surfaced in the overview when useful |
| Profile-pack notes and metadata | Profile Pack tab |
| Live-verification checklist | Readiness tab |

## Layout Behaviour

The command bar never scrolls. The left rail, centre overview, and right detail
panel each manage their own overflow. Both side areas can collapse to labelled
rails, but their status counts remain visible. At reduced widths the right
detail panel becomes a keyboard-accessible drawer; it does not become a new
page. Panel dimensions are application-local user preferences, not Profile
Pack data.

All important state uses text or icons in addition to colour. Keyboard focus is
visible, list selection is distinct from hover, and changing Profile or Run
never silently changes execution state.
