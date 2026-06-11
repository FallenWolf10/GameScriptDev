# Pink Paw Workflow

## Goal

Update `pink_paw_automation` from the 2026-06-02 recordings so the pack uses:

- the `pink_paw_test_route` start prompt anchor as the initial route proof
- gold-entry anchors instead of unrelated late-route states
- repeated `F` interaction at the first gold gate
- a route that stops once the second gold entry has been passed

## Current Authoring Result

The active profile is intentionally narrower than the earlier long-form draft.
It now keeps only the anchor-driven portion requested by the user:

1. confirm the Pink Paw NPC prompt
2. move to the first gold entry
3. confirm the first gold-entry anchor
4. press `F` repeatedly to open that gate
5. move to the second gold entry
6. confirm the second gold-entry anchor
7. pass the second entry and stop

## Asset Basis

Anchors used by the updated pack:

- `assets/start_npc_prompt.png`
  - reused from `pink_paw_test_route`
- `assets/first_gold_entry.png`
  - cropped from the first gold gate sequence in the clean capture
- `assets/second_gold_entry.png`
  - cropped from the later gold-entry portal in the clean capture

## Practical Rule

When extending this pack again, keep the graph anchored around stable route
checkpoints. Do not reintroduce the old unrelated late-route states unless a
new request explicitly asks for coverage beyond the second gold entry.
