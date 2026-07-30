# Neverness to Everness Fishing Core

## Scope

This pack independently recreates only a finite fishing core:

1. confirm the fishing option;
2. confirm the preparation screen;
3. confirm the fishing mini-game;
4. perform three bounded observation/correction cycles;
5. end as `caught`, `escaped`, `lost_state`, `failed_control_timeout`, or `failed_confirmation`.

The profile never loops back to the start and `execution.allow_infinite_run` is false.

## Bounded Control Design

GameScriptDev's existing interruption and state-transition primitives are sufficient, so this pack adds no engine or adapter extension. During each explicit control cycle, two mutually exclusive interruption detectors represent the cursor being outside the target dead zone:

- `cursor_left_of_dead_zone` sends a short `right` key pulse;
- `cursor_right_of_dead_zone` sends a short `left` key pulse.

When neither relation detector matches, the cursor is treated as inside the dead zone and no correction is sent. Each pulse is 0.08 seconds. The graph has three control cycles, two retries per state, and finite terminal/failure transitions.

The relation templates are deliberately safe geometric placeholders. They demonstrate the profile shape but are not evidence that template matching is suitable for the real game. Before any future live work, independently captured evidence would need to prove that the target-zone and cursor relation can be detected reliably and that the two relation anchors cannot match simultaneously.

## Geometry Assumptions

- Coordinates and captures are assumed to use a 1280x720 unvirtualized target-client area.
- The target zone and cursor are assumed to be horizontally comparable.
- The left relation means the cursor center is left of the accepted dead zone.
- The right relation means the cursor center is right of the accepted dead zone.
- Absence of both relation anchors means no correction; it does not prove a catch.
- Terminal outcomes are confirmed separately by explicit outcome anchors.

These assumptions have not been tested against a live game client.

## Independent Recreation Boundary

MaaNTE is treated only as a high-level behavioural reference. No MaaNTE source code, templates, translations, JSON grammar, binaries, assets, framework calls, or other implementation material is copied or adapted. All YAML, notes, tests, and placeholder images in this pack are native GameScriptDev work created for this repository.

## Non-goals

This pack intentionally excludes navigation, bait purchase, auto-selling, audio logic, background-input experimentation, restart logic, infinite loops, deployment, live automation, and live-game validation.

## Evidence and Readiness

- Safe placeholder PPM files are included only so profile-pack validation and local dry-run paths are reproducible.
- The default dry run exercises the `caught` path because dry-run vision reports declared anchors as present.
- Focused tests use repository-local fake adapters to exercise caught, escaped, lost-state, retry/failure, operator stop, and cleanup paths.
- `target_identity`, `supported_resolution`, and `required_assets` remain false in the compatibility checklist, intentionally blocking any claim of live readiness.
- No real user data, secrets, credentials, real-game assets, or live target were accessed.
