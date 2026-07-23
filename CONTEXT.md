# Context

## Glossary

### Local Automation Runner

A user-operated tool that automates repetitive UI actions on the user's local machine.

### Local Web Dashboard

A browser-based control surface hosted on the user's local machine for managing profiles, validation, dry runs, readiness-gated live runs, run logs, and artifacts without turning the runner into a cloud service.

### Application-Managed Run

A run launched from the Operator Application and owned by that application. It remains observable through status, timeline, logs, and artifacts without requiring a foreground terminal session.
_Avoid_: Dashboard-Managed Run, Detached Run

### Run Ownership

The rule that an Application-Managed Run remains valid only while the Operator Application that launched it still owns it. If ownership is lost during a live run, the runner fails closed, records the interruption when possible, and sends no further input.
_Avoid_: Dashboard Ownership

### Active Run

The single Application-Managed Run that has been admitted and has not yet reached a completed, failed, cancelled, or interrupted terminal status.
_Avoid_: Selected Run, Open Run

### Interrupted Run

A terminal Run that lost application ownership, worker communication, or orderly shutdown before reaching its intended result. Its available evidence is preserved, but execution is never resumed from that record.
_Avoid_: Paused Run, Recoverable Run

### Background Window Message Input

Live input delivered directly to a specific target window handle by posting keyboard or mouse messages to that window instead of injecting global desktop input into the current foreground application.

### Background Capture Compatibility

A Live Readiness finding that target-client capture and required anchor recognition remain reliable while the non-minimized target is behind other windows. It is independent of Background Window Message Input; without this finding, the target must remain visible.
_Avoid_: Background Input Support, Minimized Capture, Assumed Occlusion Support

### Foreground Input Fallback

A compatibility path used only when a target cannot reliably accept Background Window Message Input. In this mode the runner requires the target window to become foreground before sending live desktop input.

### Robust Input Variation

Small coordinate and timing variation used to reduce brittle exact-pixel assumptions in UI automation. It is not anti-detection or evasion behavior.

### Physical Client Pixel

One unvirtualized pixel inside the matched target window's client area. Profile resolution, named regions, capture dimensions, and absolute pointer targets use this coordinate space independently of Windows display scaling.
_Avoid_: CSS Pixel, Desktop Logical Pixel

### Target Display Change

A change to the matched target window's monitor or effective DPI after a Live Run Snapshot is admitted. It invalidates the coordinate environment and interrupts the Run rather than being handled as a workflow Transition.
_Avoid_: Application DPI Change, State Transition

### Target Geometry Change

Minimization or a change to the matched target window's physical client width or height after Live admission. It interrupts the Run even when the Profile's Resolution Policy is `ignore`.
_Avoid_: Same-Monitor Repositioning, Window Decoration Change

### Game Profile

A game-specific description of window identity, standard resolution, screen anchors, state transitions, actions, visual assets, timeout settings, retry limits, and recovery rules. The automation runner executes game profiles without hardcoding game-specific behavior into the runner itself.

### Profile Pack

A folder for one game or game-mode workflow that groups the YAML profile, assets, notes, validation examples, known limitations, and compatibility checklist together.

### Compatibility Checklist

A profile-pack review record that must confirm target identity, supported resolution, required assets, complete state graph coverage, terminal states, failure transitions, interruption recovery, known limitations, and successful validation or dry-run evidence before live mode is available.

### Profile-Pack Authoring Support

Tools or guidance that help a profile author create, validate, review, and maintain profile packs without adding game-specific behavior to the runner.

### Live Run Review

A post-run inspection of the states, actions, anchor detections, screenshots, retries, failures, logs, and artifacts from a live-mode execution.

### Operator Package

A local installable or runnable form of the tool intended for an operator who wants to use the runner, dashboard, and demo workflows without working directly from source.

### Operator Installer

The signed per-user Windows EXE that installs, repairs, updates, and uninstalls the Operator Application while preserving the User Workspace and Operational Data.
_Avoid_: Portable ZIP, MSIX Package

### Supported Windows Platform

A currently serviced x64 release of Windows 11 included in the Operator Application's tested release matrix.
_Avoid_: Windows 10 Compatibility, Best-Effort Platform

### Operator Application

The single user-facing product that brings together profile execution and profile authoring while preserving local control and live-run safety.
_Avoid_: Desktop Dashboard, Software Application

### Application Bar

The fixed top-level Operator Application row that switches between Run, Build, and Settings while keeping Active Run identity and Stop globally visible beneath the native Windows controls.
_Avoid_: Browser Navigation, Second Sidebar

### Run Workspace

The operator-focused part of the Operator Application for selecting profiles, checking readiness, starting and stopping runs, and reviewing results.
_Avoid_: Run Dashboard, Operator Dashboard

### Run Overview

The central Run Workspace surface that presents the selected Profile or Run, Target Preview, critical status, primary controls, and current progress at a glance.
_Avoid_: Readiness Page, Main Dashboard

### Run Progress Card

The compact active-Run summary beside the Target Preview that shows execution status, current State and Action, elapsed time, retries, and the latest meaningful event without duplicating the full Timeline.
_Avoid_: Live Log Card, Progress Percentage

### Run Outcome Summary

The completed-Run form of the Run Progress Card that shows terminal status, result, duration, final State, primary failure information, latest evidence, and relevant review or repeat actions.
_Avoid_: Completion Popup, Automatic Run Review

### Run Detail Panel

The fixed right area of Run Workspace that provides Readiness, Timeline, Logs, Artifacts, and Profile Pack details without navigating away from the Run Overview.
_Avoid_: Log Column, Details Page

### Profile Builder

The author-focused part of the Operator Application for creating, arranging, validating, and reviewing profile packs through structured visual editing.
_Avoid_: Builder Dashboard, Profile Dashboard

### Profile Setup

The short guided entry into Profile Builder that chooses a starting source, records essential identity and target information, scaffolds the Profile Pack, and then opens a recoverable Profile Draft.
_Avoid_: New Profile Wizard, Project Wizard

### Flow View

The Profile Builder view that presents States and their success and failure Transitions as a compact workflow graph.
_Avoid_: Graph Page, Workflow Dashboard

### State Node

The compact Flow View representation of one State, showing its identity, role, anchor and Action counts, Transition connectors, and aggregate validation status.
_Avoid_: State Card, Expanded State Form

### Flow Layout

The portable visual arrangement of State nodes in Flow View; it has no effect on State order, Transitions, validation, or execution.
_Avoid_: State Order, Workflow Behavior

### State View

The Profile Builder view that focuses on the anchors, ordered Actions, and Transitions belonging to one selected State.
_Avoid_: State Page, Action Dashboard

### Action Block

The compact State View representation of one ordered Action, showing its essential summary, selection, and validation status.
_Avoid_: Action Card, Action Form

### Action Inspector

The persistent contextual editor that exposes the complete configuration of the selected Action while its State and target preview remain visible.
_Avoid_: Action Modal, Action Dialog

### Tool Palette

The fixed left area of Profile Builder whose available tools follow the active view: State and Transition tools in Flow View, and Action tools in State View.
_Avoid_: Action Sidebar, Permanent Toolbox

### Context Rail

The persistent split area on the right of Profile Builder that keeps the Target Preview above the contextual Inspector, with a user-adjustable divider.
_Avoid_: Right Sidebar, Floating Properties Window

### Problems Drawer

The collapsible Profile Builder area that lists all current authoring problems and navigates directly to the affected Profile, State, anchor, Transition, or Action.
_Avoid_: Error Page, Validation Popup

### Draft Validation

The authoritative schema and pack check of the current Profile Draft that determines whether it can become a Saved Profile Version.
_Avoid_: Live Readiness, Overall Status

### Live Readiness

The safety gate for a Saved Profile Version that combines validity, target compatibility, required evidence, and operational checks to determine whether Live Run is available.
_Avoid_: Draft Validation, Profile Validity

### Profile Draft

A recoverable authoring version of a Profile Pack that may be incomplete or invalid and has not replaced the last explicitly saved profile.
_Avoid_: Autosaved Profile, Temporary Profile

### Saved Profile Version

A validated profile version explicitly accepted by the author as the current runnable form of a Profile Pack.
_Avoid_: Published Profile, Final Profile

### Run Snapshot

The immutable profile content assigned to one automation run so later authoring changes cannot alter that run while it is executing.
_Avoid_: Live Draft, Working Profile

### Run Evidence Unit

The self-contained stored set for one Run: identity and result metadata, Run Snapshot, readiness record, Timeline, log, and artifacts. Retention, export, and deletion operate on the unit rather than leaving partial evidence behind.
_Avoid_: Artifact Folder, Log File

### Evidence Bundle

A standard ZIP export of a terminal Run Evidence Unit containing an offline HTML summary, versioned machine-readable manifest, Run Snapshot, readiness record, Timeline, log, original artifacts, and file checksums.
_Avoid_: Proprietary Run File, PDF Report

### Shareable Bundle

An explicitly reduced Evidence Bundle whose operator-selected omissions are recorded in its manifest so it cannot be mistaken for complete Run evidence.
_Avoid_: Redacted Evidence, Full Evidence Bundle

### Pinned Run

A completed Run whose Run Snapshot, logs, timeline, and artifacts are protected from automatic retention until the operator explicitly unpins it. Pinning is not a substitute for exporting or backing up evidence.
_Avoid_: Saved Profile, Archived Run

### Operational Data

Application-managed settings, recovery drafts, Run records, logs, artifacts, and caches stored under `%LOCALAPPDATA%\GameScriptDev`, separately from installed files and the User Workspace.
_Avoid_: User Workspace, Profile Data

### Verified Application Update

An Operator Application release whose publisher signature and package hash are validated before an explicitly approved installation that cannot modify the User Workspace or run during an Active Run.
_Avoid_: Silent Update, Built-in Source Update

### User Workspace

The user-owned location that contains editable Profile Packs and their assets independently of the Operator Application installation.
_Avoid_: Working Directory, Installation Folder

### Built-in Profile Pack

A runnable Profile Pack supplied with the Operator Application whose original contents remain protected; editing begins from a copy in the User Workspace.
_Avoid_: Bundled Template, Read-Only Template

### Profile Reference

The source-qualified identity of a Profile Pack, combining its Built-in or User source with its pack identifier so equal identifiers never shadow one another.
_Avoid_: Profile Name, Unqualified Profile ID

### Pack Lineage

Portable Profile Pack metadata that records the Built-in Profile Reference and version from which a user-owned Pack was copied, without making the copy dependent on its source.
_Avoid_: Live Link, Inheritance

### Lineage Baseline

The immutable comparison record captured when a Built-in Profile Pack is copied, containing original structured text plus an asset checksum inventory so later source updates can distinguish user changes from upstream changes.
_Avoid_: Parent Profile, Inherited Profile

### Source Update

A newer Built-in version of the Pack recorded by a user-owned Pack's lineage. It is offered for deliberate comparison and never changes the User Pack automatically.
_Avoid_: Required Upgrade, Automatic Merge

### Regression Fixture

A saved, non-sensitive artifact from a known run that can be reused to test profile validation, vision matching, state detection, or run review behavior without repeating a live run.

### Declarative Profile

A game profile expressed as data rather than custom game-specific code. It describes states, anchors, actions, retries, timeouts, and recovery behavior using a fixed vocabulary that the automation runner understands.

### State

A recognizable screen or mode in the target application, confirmed by one or more anchors.

### Anchor

A visual or textual signal used to confirm that the target application is in a specific state.

### Required Anchor

An anchor that must be present before the automation runner treats a state as confirmed.

### Optional Anchor

An anchor that increases confidence in state recognition but is not required on its own.

### Forbidden Anchor

An anchor whose presence proves that the automation runner is not in the expected state.

### Action

An input or observation step performed by the automation runner while it is in a state.

### Disabled Workflow Item

A State or Action retained in a Profile Pack for later authoring work but deliberately excluded from the active state graph and automation execution.
_Avoid_: Commented-Out Code, Inactive Code

### Transition

The expected movement from one state to another after an action or action sequence completes.

### Explicit Transition

A transition declared directly in a game profile so the runner can validate the workflow graph before execution.

### Terminal State

A state that ends the workflow after its anchors are confirmed. Terminal states usually represent successful completion or a known final failure screen.

### Run Artifact

A log file, screenshot, or other output generated by a single automation run and stored with enough timestamp and state context to diagnose what happened.

### Daily Log Folder

A date-based folder that groups the daily activity log and per-run artifacts for all automation runs on that date.

### Global Interruption

An unexpected popup, disconnection screen, launcher error, system dialog, or other overlay that can appear during any part of the workflow and temporarily interrupt the expected state transition.

### Recovery Action

An action sequence used to dismiss or recover from a global interruption before returning to the expected workflow.

### Retry Current State

A recovery policy that repeats the current state's action sequence after a temporary failure, up to the profile's retry limit.

### Restart Workflow

A recovery policy that returns to the initial state check when the runner can no longer trust its current position but the application may still be usable.

### Graceful Termination

A controlled stop that records the failure point, writes a log entry, captures a screenshot when possible, and exits without further input actions.

### Demo Profile

A non-game profile used to validate the runner, profile schema, state machine, logging, retry behavior, and failure handling before real game assets and actions are available.

### Local Demo Target

A repo-owned desktop window used to exercise live-mode safety checks, screenshots, input, state recognition, logs, and artifacts without depending on a real game or external service.

### Live Verification Scenario

A controlled run that pairs a profile with a known local target so live mode can be verified end-to-end while preserving readiness gating, target-window checks, and graceful termination.

### Dry Run Mode

An execution mode that loads and validates a game profile, records planned actions, simulates waits and retries, and avoids desktop input actions.

### Live Mode

An explicit execution mode that can focus windows, capture screenshots, move the pointer, click, and send keyboard input to the target application.

### Live Confirmation

A required Operator Application summary shown after Live Readiness passes and before the Live Run Worker starts. It identifies the Saved Profile Version, target window, input mode, and any elevation request; Cancel has initial focus and the operator must explicitly activate `Start Live Run` for each attempt.

### Runtime Adapter

A boundary between the state-machine runner and an external desktop capability such as window control, screen capture, visual detection, or input.

### Window Adapter

The runtime adapter responsible for finding, focusing, and preparing the target application window.

### Target Window Detection

The process of finding the target application's visible window by comparing the profile's target identity against live operating-system windows.

### Window Handle

A live operating-system identifier for a specific target window. Background Window Message Input is addressed to this handle rather than to whichever application currently owns foreground focus.

### Screen Adapter

The runtime adapter responsible for capturing the target window or screen.

### Vision Adapter

The runtime adapter responsible for detecting anchors and locating visual targets in screenshots.

### Input Adapter

The runtime adapter responsible for sending mouse and keyboard input.

### Strict Profile Schema

A profile contract that must pass validation before execution begins. Unknown action types, missing required fields, invalid transitions, or unresolved assets prevent both dry run and live mode execution.

### YAML Profile

A declarative profile stored as YAML so state-machine workflows, anchors, actions, and recovery rules remain readable and commentable while being edited and debugged by humans.

### Running Target Requirement

A startup rule requiring the target application to already be running before the automation runner begins. If the configured target window or process is missing, the runner stops before executing workflow actions.

### Target Identity

The profile's description of the application instance to automate, usually combining process name matching with window title matching so the runner can confirm the process exists and focus the correct interactive window.

### Resolution Policy

The profile's rule for handling the target window size. The default policy verifies the expected resolution and stops on mismatch; other policies may attempt resizing or ignore resolution checks when explicitly configured.

### Template Matching

Visual detection that compares a cropped image asset against the current screen or target window capture.

### OCR Matching

Text detection that searches the current screen or target window capture for configured words or phrases.

### Detection Strategy

The profile-level choice of visual and textual matching methods. Profiles may describe both template matching and OCR matching, while the initial runner implementation prioritizes template matching.

### Supported Action

An action type included in the runner's fixed vocabulary and accepted by strict profile validation.

### Bounded Wait

A wait action that repeatedly checks for a condition until it succeeds or reaches a configured timeout.

### Named Click Region

A configured coordinate region with a human-readable name that can be clicked without scattering hardcoded pixels through a profile.
