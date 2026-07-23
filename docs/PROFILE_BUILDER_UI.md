# Profile Builder UI Plan

This document captures the proposed direction for a visual authoring UI that
helps contributors create and maintain `profile.yaml` files without manually
typing every YAML field.

The goal is not to replace YAML as the source format. The goal is to add a
local-first builder that edits the same profile model, validates through the
same schema, and writes normal profile packs that the runner and dashboard
already understand.

## Product Goal

Profile authoring should feel like building a workflow:

- identify the target window
- define screens as states
- define visual proof for each state through anchors
- drag actions into each state
- connect states through success and failure transitions
- validate, dry-run, review, and iterate

The author should not need to remember indentation, exact action field names,
or every compatibility checklist key while drafting a profile.

## Guiding Principles

- Keep workflow behavior declarative in `profile.yaml`.
- Build on the existing local dashboard instead of creating a separate app.
- Keep Python validation as the final source of truth.
- Let the UI edit structured profile data, then serialize to YAML.
- Avoid game-specific builder logic. Game-specific knowledge belongs in profile
  packs, assets, notes, and validation evidence.
- Preserve dry-run-first behavior and live-mode readiness gating.
- Make generated YAML inspectable so advanced authors can still review the raw
profile.

## Implementation Status

The first writable authoring slice is implemented in the Build workspace. It
can scaffold a blank Profile Pack in the current User Workspace and open it
immediately. Existing and newly created Profiles have an in-application raw
YAML editor backed by recoverable Draft APIs, authoritative schema validation,
explicit Save, atomic `profile.yaml` replacement, external-change conflict
rejection, and retained revision backups. Invalid YAML remains recoverable and
never replaces the Saved Profile Version.

The visual State and Action flow remains read only. It reflects a valid Draft
when possible and still needs the full graph canvas, structured field editing,
drag and drop, asset editing, and stronger problem navigation described below.

## Primary Users

### Profile Author

Creates or updates profile packs for a game workflow. This user needs help with
state graphs, anchors, action ordering, timing, named regions, and validation.

Common tasks:

- scaffold a new profile pack
- add states and transitions
- draw click regions from a preview screenshot
- add anchors from templates or OCR text
- drag actions into a state timeline
- run validation and dry-run checks
- update compatibility evidence and known limitations

### Operator

Runs existing profile packs through the dashboard. This user mainly needs
clear readiness, dry-run/live controls, run history, artifacts, and failure
reasons.

The builder should not make operator workflows noisier. Authoring controls can
live in the separate Build workspace selected from the fixed Application Bar.

### Reviewer / Maintainer

Reviews profile changes before they are trusted for live mode. This user needs
the generated YAML, notes, validation result, state graph, run evidence, and
compatibility checklist to line up.

Common tasks:

- inspect generated YAML
- compare graph structure against notes
- verify assets and anchors are present
- review dry-run/live run evidence
- confirm known limitations are honest

## Central Workspace Model

The Builder uses two levels inside one persistent workspace instead of placing
every State and Action on one giant canvas. Flow View shows compact State nodes
and their Transitions. Opening a selected State switches the central canvas to
State View, where its anchors and ordered Scratch-like Action stack are edited.

The Tool Palette remains in a stable position on the left while its contents
follow the active view. Flow View exposes State and Transition tools; State
View exposes the Action palette. The target preview plus contextual inspector
remain on the right in both views. A visible `Flow / State: <name>` control and
breadcrumb preserve location, while mouse, keyboard, and search commands
support opening a State and returning to the same selected node. The two-level
model keeps large profiles readable without introducing separate Builder
pages.

### Tool Palette

The left Tool Palette keeps the same width and location while switching to the
smallest relevant tool set. In Flow View it provides State creation, terminal
State, and Transition tools. In State View it provides draggable Actions and
an accessible `Add Action` path. Actions cannot be dropped into Flow View, so
they are not displayed there.

The palette may be collapsed to a narrow labelled rail to expand the canvas.
Its size and collapsed state are user preferences rather than profile data.
Keyboard commands can focus, search, and activate its tools without requiring
drag and drop.

### Context Rail

The right side of both Flow View and State View is a fixed Context Rail. The
Target Preview remains above the contextual Inspector, following the stable
stage-and-workspace relationship used by block-based creative tools. A
draggable divider lets the author allocate more height to either area while
preserving usable minimum sizes; this preference is local to the application
and does not become profile data.

The preview preserves the target aspect ratio and may be temporarily expanded
without replacing the Builder workspace. The Inspector scrolls internally, so
editing long settings does not move the palette, canvas, or preview. When the
application is too narrow to keep both areas useful, the rail changes to
keyboard-accessible `Preview` and `Inspector` tabs. Hidden-tab validation and
unsaved-change badges remain visible, and returning to a wider window restores
the split layout.

## Create Profile Workflow

`Create Profile` begins with a short Profile Setup and then opens the normal
Builder workspace. It is progressive setup, not a separate long-form wizard.

1. Choose `Blank Profile`, `Copy Built-in Profile`, or `Import Existing Pack`,
   then enter or confirm the game, mode, profile name, and unique destination
   in the User Workspace.
2. Select a currently running target window to populate process, title, client
   resolution, and suggested input settings, or explicitly choose `Set up
   later`.
3. For a blank profile, name the initial State and optionally capture the first
   target preview or anchor. Copies and imports retain their existing initial
   State and workflow.

Completing setup creates the existing pack shape (`profile.yaml`, `notes.md`,
`assets/`, and validation example folders) and immediately opens Flow View with
an autosaved, recoverable Profile Draft. A short `Next recommended step`
checklist highlights unresolved readiness work without covering the canvas.
Skipping target selection is allowed, but it leaves an explicit unresolved
target placeholder and Live Run remains unavailable until readiness is
complete.

Copying a Built-in Profile Pack always creates an editable user-owned copy;
the installed original is never changed. Import validates the selected pack,
copies it into the User Workspace when necessary, reports path or identifier
collisions, and never silently overwrites an existing pack. Keyboard focus
moves predictably through setup, all fields have persistent labels, and the
final action clearly states the destination that will be created.

The user-owned copy stores portable Pack Lineage containing its Built-in
Profile Reference and copied content version. The copy remains independent and
editable: lineage supports provenance, comparison, and update notices but
never causes automatic changes or execution-time inheritance.

### Built-in Source Updates

When Pack Lineage points to a newer Built-in fingerprint, Profile Builder shows
`Source Update Available` without changing the User Pack. `Compare Update`
opens a three-way comparison among the immutable Lineage Baseline, the current
User Pack, and the newly installed Built-in Pack. Structured text uses the
stored baseline content; assets use baseline checksums plus current and new
previews to identify unchanged files and conflicts.

The author can keep the current copy, dismiss this specific source version,
select individual changes for a normal Profile Draft, or create a fresh
user-owned copy with a unique identifier. Selective application never writes
directly to `profile.yaml`: it follows comment-preservation and conflict rules,
then requires Draft Validation and explicit Save. A fresh copy does not replace
the existing copy.

A Source Update alone does not invalidate the independent User Pack's Saved
Profile Version or Live Readiness. Applying any source change creates ordinary
draft changes and, once saved, invalidates affected readiness evidence under
the existing rules. Automatic merging is not offered.

`Compare Update` opens a dedicated Builder comparison workspace rather than a
small modal. Its left side filters Profile Settings, States, Transitions,
anchors, Actions, assets, notes, and disabled items. The central comparison
labels each item as added, changed, removed, unchanged, or conflicting across
the baseline, User Pack, and new Built-in source. The contextual detail area
shows the three values, impact, asset previews or checksums, and an explicit
keep-current, take-source, or manual-edit choice when resolution is required.

Non-conflicting changes remain individually selectable and are not applied
merely by opening the comparison. Conflicts begin unresolved and cannot be
silently selected. `Apply Selected to Draft` stages all resolved selections as
one undoable draft transaction, after which normal structured editing, comment
preservation, validation, diff, and Save rules apply. Closing comparison before
application leaves the User Pack unchanged.

A read-only raw comparison remains available for the complete Pack or selected
category. It provides unified text diffs and binary asset inventories, but it
is a verification view rather than a second write path. Status uses labels and
icons as well as colour, filters are keyboard accessible, and every selection
has an equivalent non-drag interaction.

## Proposed UI Structure

### 1. Profile Settings

This area edits top-level profile and pack metadata:

- profile name
- game and game mode
- target process name
- target window title match
- input mode
- key delivery methods
- expected resolution and resolution policy
- retry/default timeout settings
- infinite-run/manual-stop flags
- detection strategy
- known limitations
- compatibility checklist

The UI should use normal controls such as text inputs, selects, toggles, and
checklists. It should show validation messages beside the related field.

### 2. State Graph Editor

The profile is fundamentally a state machine. Flow View should expose that
directly without expanding every State's Actions on the graph.

States should appear as nodes. Edges should represent:

- `on_success`
- `on_failure`
- terminal result states

Each State Node uses a consistent compact size. It shows the State name; a
labelled initial, terminal, or terminal-result marker when applicable; anchor
and Action counts; separate labelled success and failure connectors; and an
aggregate valid, warning, or error status. Status and connector meaning use
text or icons as well as colour.

Nodes do not display screenshots, anchor names, or Action summaries. Selecting
a node exposes those details in the Context Rail, while opening it enters State
View. This keeps the whole workflow scannable and prevents information-rich
States from becoming disproportionately large. A node with multiple problems
shows their count and highest severity rather than placing every message on
the graph.

Useful graph actions:

- add state
- rename state
- mark state as terminal
- connect success transition
- connect failure transition
- jump to initial state
- highlight unreachable states
- highlight missing terminal path

The graph editor should make it hard to accidentally create a profile that
cannot validate.

Flow View generates a predictable left-to-right layout when no saved layout is
available: the initial State begins on the left, primary success paths continue
horizontally, failure and recovery paths branch downward, terminal States sit
toward the right, and disabled States use a separate muted lane. Authors may
drag nodes to refine this arrangement without changing workflow behaviour.

Automatic layout runs on first open or through an explicit, undoable `Tidy
Flow` action rather than rearranging the canvas after every edit. `Fit Flow`
and `Focus Selected State` provide quick navigation, while a minimap appears
only for sufficiently large graphs. Builder-only positions are stored as
portable profile-pack metadata separate from `profile.yaml`; missing metadata
is harmless because it can be regenerated.

### 3. State Detail Panel

Opening a State switches the central workspace to State View with:

- required anchors
- optional anchors
- forbidden anchors
- ordered actions
- success transition
- failure transition
- terminal result when applicable

This panel is the main authoring surface for most profile work.

### 4. Action Palette And Timeline

Actions should be added by dragging from a palette into a state's action list.
The action list should support reordering and inline validation.

Each Action appears in State View as a compact Action Block rather than a full
form. The block shows its drag handle and order, action type, essential
parameter summary, and disabled, warning, or error status. Selecting a block
opens its complete labelled settings in the persistent Action Inspector on the
right, without hiding the State or target preview. Fields validate on blur and
surface their status both beside the field and on the corresponding block.

Dragging from the palette or choosing `Add Action` shows an explicit insertion
line. Authors can also reorder with keyboard-accessible `Move Up`, `Move Down`,
and `Move to State` commands. Duplicate, disable, and delete remain available
from the selected block; delete requires confirmation when the Action contains
nested configuration. Selecting a region- or anchor-based Action activates its
overlay in the target preview. Complex nested sequences expand only while
selected, and category colour is never the only indicator of Action type or
status.

The State View palette begins with a persistent search field and a short
`Recently Used` row, followed by four collapsible groups:

- **Flow & Timing:** `wait_for_state`, `wait`, `log`, and `stop`
- **Keyboard:** key press, hold, repeat, and combined-key Actions
- **Pointer:** point, template, hold, move, drag, and scroll Actions
- **Continuous Input:** start and stop lifecycle Actions

Search matches the friendly label, YAML action type, description, and
plain-language keywords. A result can be dragged or added with the keyboard.
Recently Used history and expanded-group preferences are application-local
user settings, not profile data. Group labels, ordering, descriptions, and
search keywords come from the Action Metadata Registry so the UI catalogue
cannot drift from supported backend Actions.

Initial action palette:

- `log`
- `wait`
- `press_key`
- `hold_key`
- `click_point`
- `wait_for_state`
- `stop`

Expanded palette:

- `press_keys`
- `hold_keys`
- `repeat_key`
- `hold_key_while_repeating_key`
- `click_template`
- `hold_click`
- `move_mouse`
- `hold_mouse_button_and_move`
- `scroll_mouse`
- `start_continuous_input`
- `stop_continuous_input`

Complex continuous inputs should get specialized editors instead of one large
generic form. For example, a continuous sequence builder can show each timed
sub-action as a nested timeline.

### 5. Region Editor

Named regions are central to reliable pointer input. The builder should use
the existing target preview and allow the author to draw rectangles.

Region editor behavior:

- load latest target preview or run artifact screenshot
- draw a rectangle
- name the region
- edit `x`, `y`, `width`, and `height`
- show existing regions as overlays
- warn when an action references a missing region

The region editor maps pointer positions from the displayed Target Preview back
to the screenshot's intrinsic Physical Client Pixel dimensions before writing
coordinates. Moving or resizing the application across DPI-scaled monitors may
change the preview's CSS size but must not change serialized regions or template
crops.

The resulting data should write to the top-level `regions` mapping.

### 6. Anchor / Asset Editor

Anchors prove that the runner is on the expected screen.

Template anchor behavior:

- select a source screenshot
- crop a region
- save it under `assets/`
- create or update a `template` anchor referencing that asset
- preview the template file path and image

Text anchor behavior:

- create a `text` anchor
- edit expected OCR text
- show that OCR support is optional and depends on runtime configuration

Anchors should be assignable as required, optional, or forbidden anchors.

### 7. YAML Draft Editor

The UI always provides the complete YAML source. This gives advanced authors a
direct way to inspect and edit the Profile while the structured Builder is
being developed.

The implemented raw editor writes only to a recoverable Draft while typing.
Draft Validation uses the Python schema and pack directory, and explicit Save
is the only action that replaces `profile.yaml`. Save retains the prior source
as a limited revision backup, performs an atomic file replacement, and refuses
to overwrite a source fingerprint that changed outside the application. Raw
editing preserves the author's comments and ordering because it never
round-trips through structured serialization.

### Comment And Disabled-Item Policy

Structured saves should preserve untouched YAML comments and ordering where
possible, but do not promise byte-for-byte formatting. A save that could move
or remove comments must show a diff, retain the previous revision, and let the
author cancel; comments are never discarded silently. Long-form explanation
belongs in `notes.md`, while short contextual descriptions can be represented
by structured authoring fields.

Executable YAML should not be disabled by commenting it out. States and actions
can instead be retained as explicit disabled workflow items, shown muted in the
Builder and excluded from the active graph and execution. Existing YAML-shaped
comment blocks require an explicit author choice to keep as comments, convert
to disabled items, move to notes, or discard; the Builder must not guess and
activate commented automation automatically.

### 8. Validation And Run Controls

The builder should reuse dashboard workflows:

- validate profile
- check profile pack
- dry-run
- show readiness blockers
- launch live only through the approved confirmation summary and readiness gates
- show latest run review and artifacts

The Builder presents Draft Validation and Live Readiness as separate, related
statuses. Draft Validation applies to the current Profile Draft and answers
whether its schema and pack structure can become a Saved Profile Version. Live
Readiness applies only to the current Saved Profile Version and includes target
compatibility, required evidence, dry-run expectations, and operational safety
checks. A profile can therefore be `Valid` while still `Live Blocked`.

When the draft differs from the saved version, the Live Readiness label makes
that scope explicit and does not imply that unsaved changes are approved. The
Problems Drawer can filter `Draft Problems` and `Readiness Blockers`, while
clicking either header status opens the corresponding filter. Saving relevant
changes invalidates stale readiness evidence and triggers recalculation; the
two statuses are never collapsed into one ambiguous progress percentage.

Validation uses three coordinated levels instead of placing complete messages
throughout the canvas:

- compact severity and count badges on affected State Nodes, Action Blocks,
  sections, and fields
- the complete message and suggested correction in the contextual Inspector
- a collapsible, resizable Problems Drawer containing the full navigable list

The Builder header shows the aggregate error and warning counts. Opening that
summary or running validation opens the Problems Drawer, where authors can
filter by severity or object type. Selecting a problem switches to the correct
Flow or State View, selects the affected object, and focuses the relevant field
when one exists. Messages are never available only through colour, hover, or a
temporary toast.

Lightweight checks can update after a short pause in editing, while explicit
Validate, Save, and run-related actions call the authoritative Python schema
and pack checks. The Problems Drawer stays closed when no problems exist and
does not permanently reduce canvas space.

## Data Flow

Recommended flow:

```text
Builder UI
  -> structured profile draft
  -> backend profile writer
  -> profile.yaml
  -> existing loader/schema/check-pack
  -> dashboard readiness and run controls
```

The frontend should not become the source of truth for profile validity. It can
offer helpful client-side constraints, but final validation should call the
existing Python schema and pack checks.

## Draft And Save Safety

Builder edits update a recoverable draft without replacing `profile.yaml`.
Drafts may be incomplete or invalid and are persisted under application data.
Session undo and redo remain planned. Explicit Save validates the complete
draft, creates revision history, and atomically replaces the saved profile;
external file changes produce a conflict instead of being overwritten silently.

Validation and dry run may use an immutable, clearly labelled draft snapshot.
Live mode may use only an explicitly saved and validated profile version. Every
run receives an immutable snapshot so later Builder edits cannot change an
active run, and saving relevant profile changes invalidates stale readiness
evidence.

## Backend Shape

Implemented dashboard API additions:

```text
GET  /api/profiles/{id}/source
GET  /api/profiles/{id}/draft
POST /api/profiles/{id}/draft
POST /api/profiles/{id}/validate-draft
POST /api/profiles/{id}/save
POST /api/profiles
POST /api/profiles/{id}/discard-draft
```

Planned structured and asset APIs:

```text
POST /api/profiles/{id}/assets
```

Possible asset-specific endpoints:

```text
GET  /api/profiles/{id}/assets
POST /api/profiles/{id}/assets/template-crop
GET  /api/profiles/{id}/assets/{path}
```

The backend constrains saved Profile writes to catalogued pack folders, blank
Profile creation to one validated identifier beneath `profiles/`, and Draft and
revision records to application-managed storage. The browser never supplies an
arbitrary filesystem destination.

## Action Metadata Registry

The profile schema already defines supported actions and validation rules in
Python. The builder should avoid duplicating those rules by hand in JavaScript.

Add a Python-side action metadata registry that can drive both validation
messages and UI form generation.

Example shape:

```python
ACTION_DEFINITIONS = {
    "press_key": {
        "label": "Press Key",
        "category": "keyboard",
        "keywords": ["tap", "type", "button"],
        "fields": [
            {"name": "key", "kind": "key", "required": True},
            {"name": "seconds", "kind": "duration", "required": False},
        ],
    },
}
```

The dashboard can expose this as JSON:

```text
GET /api/profile-schema
```

This keeps frontend controls aligned with backend capabilities as new action
types are added.

## Implementation Phases

### Phase 1: Read-Only Profile Builder View

Status: foundation implemented; graph canvas and richer invalid-source problem
navigation remain.

Goal: make profiles easier to understand before editing them.

Deliverables:

- profile source endpoint
- structured profile JSON endpoint
- visual state graph
- state detail view
- action timeline view
- YAML preview

Acceptance checks:

- existing profiles can be opened in builder mode
- graph shows initial, terminal, success, and failure paths
- invalid profiles still show enough information to diagnose the issue

### Phase 2: Writable Authoring

Status: raw YAML Draft editing, blank Profile creation, validation, conflict-safe
Save, and revision retention are implemented. Structured Action editing remains.

Goal: edit common action lists without touching YAML manually.

Deliverables:

- edit state action list
- drag/reorder actions
- add/remove/edit common actions
- save back to `profile.yaml`
- validate after save

Initial editable actions:

- `log`
- `wait`
- `press_key`
- `hold_key`
- `click_point`
- `wait_for_state`
- `stop`

Acceptance checks:

- a simple profile can be modified through the UI
- saved YAML passes existing validation
- dry-run uses the edited profile without special runner behavior

### Phase 3: Profile Pack Creation And Metadata

Goal: create new pack-shaped profiles from the dashboard.

Deliverables:

- scaffold-pack UI
- edit profile settings
- edit pack metadata
- edit known limitations
- edit compatibility checklist
- run `check-pack` from UI

Acceptance checks:

- a new pack can be created without copying an old folder
- required pack files and folders are created
- missing evidence appears in the builder and existing dashboard readiness

### Phase 4: Visual Region And Anchor Tools

Goal: remove the most error-prone coordinate and asset authoring work.

Deliverables:

- draw regions on target preview or artifact screenshot
- overlay existing regions
- crop template anchors into `assets/`
- create text anchors
- assign anchors to required/optional/forbidden buckets

Acceptance checks:

- a click region can be drawn and used by `click_point`
- a template crop can be saved and referenced by an anchor
- missing assets and unknown regions are caught before dry-run/live use

### Phase 5: Full State Graph Editing

Goal: author the whole workflow visually.

Deliverables:

- add/rename/delete states
- connect transitions
- mark terminal states
- set initial state
- show unreachable nodes and missing terminal paths

Acceptance checks:

- a small profile can be created from scratch in the builder
- graph errors match schema validation errors
- generated YAML remains compatible with existing CLI and dashboard runs

### Phase 6: Advanced Actions And Continuous Input Builder

Goal: support the full action surface ergonomically.

Deliverables:

- editors for multi-key actions
- repeat actions
- mouse movement and scroll actions
- continuous input actions
- continuous sequence timeline editor
- timing helpers for recorded-input workflows

Acceptance checks:

- existing real profile packs using continuous input can be edited without
  losing structure
- nested sequence validation stays aligned with the Python schema
- generated YAML remains readable and reviewable

## Open Questions

- Should the first graph implementation use a small dependency, or should it
  start with vanilla DOM/SVG to match the existing dashboard?

## Suggested First Implementation Slice

Start with a read-only builder tab inside the existing dashboard.

Why this slice:

- it exercises profile parsing without write risk
- it helps authors immediately understand large profiles
- it creates the UI structure needed for later editing
- it can be validated against existing profile packs

Recommended first tasks:

1. Add a backend endpoint that returns a selected profile as structured JSON.
2. Add a builder tab for the selected profile.
3. Render the state list and transitions.
4. Render the selected state's anchors and actions.
5. Add a read-only YAML preview.
6. Add validation messages beside the builder view.

After that works, move to basic action editing and save support.
