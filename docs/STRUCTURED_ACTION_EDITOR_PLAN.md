# Structured Action Editor Implementation Plan

## Status

Phases 1–4 implemented on `codex/structured-action-editor`.

Implemented:

- complete top-level Action metadata catalogue and schema endpoint
- versioned insert, update, move, duplicate, enable/disable, and delete mutations
- comment-preserving targeted YAML edits for Action lists and scalar fields
- session undo and redo with stale-Draft conflict rejection
- keyboard-operable `wait` palette, Action Stack, Inspector, and Problems Drawer
- Action Block drag handles and a keyboard-operable cross-State move command
- metadata-driven forms for `wait`, `log`, `press_key`, `hold_key`,
  `click_point`, `wait_for_state`, and `stop`
- Action-attached comment ownership across insert, move, cross-State move,
  duplicate, and delete operations
- backend-enforced diff confirmation for mutations that move, duplicate, or
  remove authored YAML lines
- Action- and State-level problem badges with navigable structured locations
- pointer and native palette drag-and-drop with an explicit insertion line,
  in-list auto-scroll, Escape cancellation, and the existing keyboard commands
  as equivalent controls
- synchronized raw YAML autosave, authoritative validation, explicit Save, revision
  retention, external-change conflict protection, and saved-version dry-run proof

The editable Flow graph remains to be implemented.

## Objective

Add safe structured Action editing to the existing Profile Builder before
building the full visual State graph editor.

The main architectural problem is not drawing the editor. It is keeping visual
edits and raw YAML synchronized as one recoverable Profile Draft without losing
comments, overwriting external changes, or creating a second source of truth.

Python validation remains authoritative, `profile.yaml` remains the saved source
format, and Live Run continues to use only an explicitly saved Profile Version.

## Design Direction

The editor should retain the existing restrained Operator Application visual
language. It is a precision authoring tool, not a vibrant gaming interface.

Required interaction qualities:

- visible keyboard focus
- keyboard alternatives for every drag operation
- inline validation with persistent messages
- status communicated through text and icons as well as colour
- explicit success feedback after mutations and Save
- reduced-motion support
- no layout-shifting hover effects
- confirmation before deleting complex or nested Actions

## Phase 1: Structured Editing Contract

Expand the Python Action Metadata Registry to cover every supported Action.
Each definition should provide:

- YAML Action type
- friendly label
- category
- search keywords
- field definitions
- required and optional fields
- defaults
- choices
- validation hints
- compact summary rules

Expose the registry through an internal schema endpoint so JavaScript does not
duplicate the supported Action catalogue or its field rules.

Add versioned structured Draft mutations for:

- insert Action
- update Action
- move Action
- duplicate Action
- disable or enable Action
- delete Action

Every mutation must identify the expected Profile Draft version or fingerprint.
A stale mutation returns a conflict and leaves the newer Draft untouched.
Frontend field checks may improve responsiveness, but the backend remains the
authority.

## Phase 2: One Vertical Tracer

Implement the `wait` Action end to end before expanding the editor:

1. Add `wait` from the Action palette.
2. Edit `seconds` in the Action Inspector.
3. Reorder the Action.
4. Validate it inline and through the Python schema.
5. Undo and redo the mutation.
6. Save explicitly.
7. Reload and confirm the same Action order and values.
8. Change `profile.yaml` externally and confirm the conflict preserves both
   versions.
9. Dry-run the saved Profile and confirm the edited Action is executed.

This tracer must prove the structured mutation, YAML preservation, validation,
Save, reload, conflict, and execution paths before more Action forms are added.

## Phase 3: Keyboard-First State View

Use three stable workspace areas:

- **Tool Palette:** searchable Actions and an accessible `Add Action` command
- **Action Stack:** ordered Action Blocks for the selected State
- **Context Rail:** Target Preview above the Action Inspector

Each Action Block should show:

- order
- friendly label
- YAML type
- essential parameter summary
- disabled state
- warning or error count
- current selection
- drag handle

Every pointer interaction must have a keyboard-accessible equivalent:

- Add Action
- Move Up
- Move Down
- Move to State
- Duplicate
- Disable or Enable
- Delete

Drag and drop enhances these commands; it is not the only editing path.

## Phase 4: Initial Common Action Set

After the `wait` tracer passes, add structured forms for:

- `log`
- `press_key`
- `hold_key`
- `click_point`
- `wait_for_state`
- `stop`

Simple Action forms should be generated from metadata. Nested sequences,
continuous input, and other complex Actions should retain readable summaries
but remain raw-YAML-only until specialized editors are implemented.

## YAML Fidelity And Draft Safety

Structured and raw editing must operate on the same recoverable Profile Draft.
There must never be separate raw and visual drafts.

Required safeguards:

- flush pending raw-editor autosaves before a structured mutation
- use a backend round-trip editing layer that preserves untouched comments and
  ordering
- never rewrite the complete document through ordinary `safe_dump`
- update only the intended State and Action portion when possible
- show a cancellable diff when comments or formatting may move or disappear
- keep the raw YAML editor available as the complete source view
- preserve incomplete and invalid drafts across restart
- retain explicit Validate and Save
- retain revision backups and atomic `profile.yaml` replacement
- retain saved-source fingerprint conflict protection
- allow Live Run only from the Saved Profile Version

## Validation And Problem Navigation

Backend validation should return structured locations such as:

```text
states.daily_menu.actions[2].seconds
```

The UI should use those locations for:

- inline field errors
- warning and error badges on Action Blocks
- aggregate badges on State Nodes
- a navigable Problems Drawer
- automatic navigation to the affected State, Action, and field

Draft Validation and Live Readiness remain separate statuses. A valid unsaved
Draft must never imply that the Saved Profile Version is live-ready.

## Undo And Redo

Structured mutations should form a session undo/redo history. Undo and redo:

- operate only on the recoverable Draft
- never replace `profile.yaml`
- use Draft versions to reject stale operations
- remain available until the Draft is discarded, saved, or the application
  session ends

Draft recovery after restart remains required even if session undo history is
not retained across restart.

## Drag-And-Drop Enhancement

Add drag and drop only after keyboard insertion and reordering are reliable.

Status: implemented and verified in the Windows Operator Application.

Required behavior:

- explicit insertion-line preview
- predictable drop position
- automatic scrolling inside long Action lists
- Escape cancels an active drag
- focus returns to the moved Action
- no mutation occurs until a valid drop is completed
- reduced-motion preferences are respected

## Full Flow Graph Comes Later

Do not begin editable Flow View until structured Action mutations are stable.
The later graph slice should provide:

- SVG or DOM State nodes using the existing dependency-light frontend
- deterministic automatic layout
- explicit and undoable `Tidy Flow`
- success and failure Transition editing
- initial and terminal State controls
- unreachable-State detection
- missing-terminal-path detection
- Builder-only node positions stored separately from `profile.yaml`

This prevents the project from producing an attractive graph over an unsafe or
ambiguous write path.

## Test Plan

### Unit Tests

- Action Metadata Registry covers every schema-supported Action.
- Metadata Action names match schema Action names.
- Structured mutation paths reject unknown States and invalid indexes.
- Insert, update, move, duplicate, disable, and delete produce expected Drafts.
- Draft version conflicts preserve the newer Draft.
- Untouched YAML comments and ordering remain intact.
- Invalid intermediate Drafts remain recoverable.
- Undo and redo restore exact Draft states.

### API Tests

- Schema metadata endpoint returns stable JSON.
- Mutation endpoints remain constrained to catalogued Profile Packs.
- Mutations never replace `profile.yaml`.
- Validate and Save use authoritative Python validation.
- Save retains a revision and rejects external-change conflicts.

### UI Tests

- Add, edit, move, duplicate, disable, and delete work with keyboard controls.
- Action selection and focus remain stable after rerender.
- Inline errors and Problems Drawer navigate to the correct field.
- Raw YAML and structured State View remain synchronized.
- Autosave and mutation races cannot silently lose changes.
- Drag and drop matches keyboard reorder results.

### Manual Acceptance

- Verify the Operator Application at normal and compact widths.
- Verify visible focus and complete keyboard operation.
- Verify invalid Draft recovery after navigation and restart.
- Verify Save, revision, reload, and external-change conflict behavior.
- Dry-run a saved edited Profile and inspect its Timeline and logs.
- Confirm Live Run still uses only the Saved Profile Version.

## First-Slice Acceptance Gate

Do not expand beyond the `wait` tracer until all of these pass:

- add, edit, reorder, and delete work through mouse and keyboard
- invalid values remain recoverable
- Python remains the authoritative validator
- comments outside the edited Action remain intact
- undo and redo work
- an external source conflict preserves both versions
- Save retains a revision backup
- reload shows the same ordered Actions
- dry-run executes the saved change
- all existing raw-YAML and dashboard tests remain green

## Recommended Branch And Review Boundary

Start implementation on:

```text
codex/structured-action-editor
```

The first review should contain only:

- the complete Action metadata contract needed by the tracer
- versioned structured Draft mutations
- the keyboard-first `wait` Action editor
- YAML-fidelity safeguards
- focused unit, API, UI, and manual acceptance evidence

Review that vertical slice before expanding the Action palette or beginning the
editable Flow graph.
