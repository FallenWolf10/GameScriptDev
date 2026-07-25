# Structured Action Editor Acceptance

## Result

Accepted on 2026-07-24 for the `codex/structured-action-editor` branch.

The structured Action milestone edits the same recoverable YAML Draft as the
raw editor, keeps `profile.yaml` behind authoritative validation and explicit
Save, and leaves complex Actions readable and raw-YAML-only. The existing-State
Flow graph is editable without making Builder layout part of the Profile
schema.

## Requirement Evidence

| Area | Evidence |
| --- | --- |
| Complete Action catalogue | `tests/test_action_metadata.py` proves registry/schema parity and requires complete labels, categories, keywords, field kinds, validation hints, and summary fields. |
| Versioned mutations | `test_server_exposes_action_schema_and_versioned_mutations` covers insert, update, reorder, duplicate, enable/disable, delete, undo/redo, unknown targets, invalid indexes, and stale versions. |
| `wait` tracer | `test_saved_structured_wait_edit_is_used_by_dry_run` saves the structured edit and proves the saved value appears in the dry-run Timeline. |
| YAML fidelity | Targeted round-trip mutation tests preserve untouched ordering and comments; destructive mutations require the exact backend diff fingerprint. |
| One recoverable Draft | Raw autosave is flushed before structured mutation. Invalid source is persisted and recovered by a fresh `ProfileCatalog`, which simulates application restart. |
| Save safety | Dashboard API tests prove invalid Drafts cannot replace `profile.yaml`, a revision is retained, and an external source fingerprint conflict preserves both versions. |
| Saved-only Live Run | `test_server_requires_and_accepts_per_attempt_live_confirmation` keeps a valid but unsaved `draft_only` terminal result, starts the confirmed Live path, and proves the Engine receives the Saved Profile result instead. |
| Common forms | Metadata-driven forms are enabled for `wait`, `log`, `press_key`, `hold_key`, `click_point`, `wait_for_state`, and `stop`; complex Actions remain raw-YAML-only. |
| Validation navigation | Structured locations drive field errors, severity-aware Action/State badges, the Problems Drawer, and exact Action or State Inspector focus. |
| Accessible Action movement | Keyboard Add/Move Up/Move Down/Move to State/Duplicate/Enable/Delete commands remain available alongside pointer drag. |
| Drag and drop | The Windows Operator Application accepted a palette `Wait` drop, selected the new block, and Undo restored the exact original stack. Earlier Action reorder acceptance covered insertion preview, auto-scroll, Escape cancellation, and focus return. |
| Flow graph | API tests cover versioned transition/initial/terminal edits, stale conflicts, Builder-only positions, Tidy, undo, and redo. Diagnostics cover unreachable States and missing terminal paths. |
| Graph keyboard equivalent | In the Windows Operator Application, the right-nudge control was focused and activated with Enter. The node moved twice, `Undo Layout` enabled, and two Undo operations restored the original layout. |
| Saved Target Preview | The Build Context Rail captured the repo-owned `Demo Automation Window`, rendered it above the Inspector, and labelled it `client 1280×720 · Saved Profile`. |
| Compact and normal layouts | The Operator Application was verified at its normal width and snapped to 960 pixels. Palette, State list, Action stack, Context Rail, Problems Drawer, and YAML Draft remained usable without overlap. |
| Visible focus and non-colour status | Keyboard node movement displayed the 2-pixel focus outline. Labels, icons, counts, and severity text supplement colour. |
| Reduced motion | Dashboard CSS disables transitions and smooth movement under `prefers-reduced-motion: reduce`. |

## Execution Evidence

The safe Local Demo Target had already completed the real Windows Live path in
the stabilization checkpoint:

- target match: `DemoAutomationTarget.exe`, title `Demo Automation Window`,
  client `1280×720`
- foreground focus verified before input
- live screenshot capture and Pillow template recognition at each State
- region click moved Home to Daily Tasks
- `F` and held `W` produced the completion screen
- transitions: `home_screen -> daily_menu -> completion_popup`
- terminal result: `success`
- final evidence:
  `artifacts/manual-acceptance-20260724/logs/2026-07-24/run_051920_780683_live_local_demo_target/`

The current milestone additionally proves through the server contract that an
unsaved valid Draft cannot change the Profile snapshot admitted to Live Run.

## Final Gates

The checkpoint is accepted only when all of these pass from the repository
root:

```powershell
.venv\Scripts\game-script-dev.exe doctor --workspace . --logs logs
.venv\Scripts\game-script-dev.exe check-pack --profile profiles\demo\local_target\profile.yaml
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m pytest
Get-Content -Raw src\game_script_dev\dashboard\static\app.js | node --check -
git diff --check
```

The stdin form avoids a Node 18 `realpathSync` permission failure on the
space-containing Windows user-profile path; it performs the same syntax check
on the complete JavaScript source.

## Deferred Scope

The following remain later Profile Builder work and are not silently claimed
by this milestone:

- State creation, rename, and deletion
- visual region and anchor/asset editors
- specialized nested and continuous-input Action editors
- production packaging or real-game expansion
