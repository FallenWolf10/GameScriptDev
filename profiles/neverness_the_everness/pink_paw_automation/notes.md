# NevernessTheEverness Pink Paw Automation

## Purpose

This pack now captures only the opening Pink Paw route slice requested from the
2026-06-02 recordings:

- start from the Pink Paw NPC prompt
- route to the first gold entry
- open that gate with repeated `F`
- continue until the second gold entry
- pass that second entry and stop

## Active Anchors

The profile intentionally keeps only the anchors needed for this trimmed route:

- `assets/start_npc_prompt.png`
  - reused from `pink_paw_test_route` as the initial prompt anchor
- `assets/first_gold_entry.png`
  - cropped from the first interactable gold gate
- `assets/second_gold_entry.png`
  - cropped from the second gold entry portal

## Route Model

The state graph is now anchor-driven instead of phase-heavy:

- `npc_prompt_start`
- `first_gold_entry`
- `second_gold_entry`
- `completed`
- `failed_route`

Movement between anchors remains timed, but the pack no longer carries the
older unrelated late-route, laser-room, desk, and finish states.

## Current Boundary

- the first gold gate uses repeated `F` input after the gate anchor confirms
- the second gold entry is treated as a visual confirmation point and is
  crossed immediately after confirmation
- failures still terminate conservatively because the engine confirms failure
  states like any other state; the pack therefore keeps the start prompt only
  as an optional diagnostic anchor on `failed_route`

## Validation Evidence

- Validate with:
  - `python -m game_script_dev --profile profiles\neverness_the_everness\pink_paw_automation\profile.yaml --validate-only`
- Pack check with:
  - `python -m game_script_dev check-pack --profile profiles\neverness_the_everness\pink_paw_automation\profile.yaml`
