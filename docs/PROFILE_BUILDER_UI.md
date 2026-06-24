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
live in a separate mode or tab.

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

The profile is fundamentally a state machine. The builder should expose that
directly.

States should appear as nodes. Edges should represent:

- `on_success`
- `on_failure`
- terminal result states

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

### 3. State Detail Panel

Selecting a state opens its details:

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

### 7. YAML Preview

The UI should always provide a generated YAML preview. This gives advanced
authors a direct way to inspect the final profile and helps reviewers trust the
builder.

The first implementation can make the preview read-only. Later, a carefully
scoped raw edit mode could be added, but structured editing should remain the
default path.

### 8. Validation And Run Controls

The builder should reuse dashboard workflows:

- validate profile
- check profile pack
- dry-run
- show readiness blockers
- launch live only through existing explicit confirmation and readiness gates
- show latest run review and artifacts

Validation errors should appear in two ways:

- a complete error list
- field/action/state-level messages where the UI can map the error back to a
  specific editor object

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

## Backend Shape

Likely dashboard API additions:

```text
GET  /api/profiles/{id}/source
GET  /api/profiles/{id}/draft
POST /api/profiles/{id}/draft
POST /api/profiles/{id}/save
POST /api/scaffold-pack
POST /api/profiles/{id}/assets
POST /api/profiles/{id}/validate-draft
```

Possible asset-specific endpoints:

```text
GET  /api/profiles/{id}/assets
POST /api/profiles/{id}/assets/template-crop
GET  /api/profiles/{id}/assets/{path}
```

The backend should constrain all writes to the selected profile pack folder and
avoid allowing arbitrary filesystem paths from the browser.

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

### Phase 2: Basic Action Editing

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

- Should drafts be saved in memory only, or should the builder write a
  temporary draft file before final save?
- Should the first graph implementation use a small dependency, or should it
  start with vanilla DOM/SVG to match the existing dashboard?
- Should raw YAML edit mode exist in the first version, or only read-only
  preview?
- How should comments in hand-written YAML be handled when the builder rewrites
  a profile?
- Should builder changes create automatic backups before overwriting
  `profile.yaml`?

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
