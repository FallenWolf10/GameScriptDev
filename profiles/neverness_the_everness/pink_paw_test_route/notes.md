# NevernessTheEverness Pink Paw Test Route

## Purpose

This pack captures a short Pink Paw test route under
`profiles/neverness_the_everness/pink_paw_test_route`.

The route is based on two user-provided recordings from 2026-06-02:

- overlay recording with visible input display:
  `C:\Users\Ng Yin Hao\Videos\2026-06-02 13-51-44.mp4`
- clean recording without the input overlay:
  `C:\Users\Ng Yin Hao\Videos\Captures\NTE   2026-06-02 13-51-41.mp4`

## Route Summary

The observed test route is compact and UI-heavy:

- begin beside the Pink Paw NPC with the interaction prompt visible
- interact with the NPC
- choose the join option
- enter the Pink Paw event panel
- wait through the bank loading/interstitial screen
- arrive inside the red-carpet instance lobby
- open the exit confirmation
- confirm exit
- return to the NPC prompt

## Anchors

Template anchors were cropped from the clean recording after normalizing frames
to 1280x720:

- `assets/start_npc_prompt.png`: start prompt beside the Pink Paw NPC
- `assets/event_panel_title.png`: Pink Paw event panel title/header
- `assets/bank_loading_title.png`: bank loading/interstitial title
- `assets/instance_ready_marker.png`: in-instance ready/countdown marker
- `assets/exit_confirm_dialog.png`: exit confirmation title
- `assets/return_npc_prompt.png`: returned NPC prompt after exit

## Current Boundary

This pack is suitable as a guarded test-route scaffold. It is not intended as a
general Pink Paw farming route or a frame-perfect replay.

Important limitations:

- click regions were reviewed at 1280x720
- the route assumes the initial NPC prompt is already visible
- UI scale, language, or event-panel layout changes may require new anchors
- the exit confirmation is part of this recorded test route

## Validation Evidence

Validation completed on 2026-06-02:

- `python -m game_script_dev --profile profiles\neverness_the_everness\pink_paw_test_route\profile.yaml --validate-only`
- `python -m game_script_dev --profile profiles\neverness_the_everness\pink_paw_test_route\profile.yaml`
- `python -m game_script_dev check-pack --profile profiles\neverness_the_everness\pink_paw_test_route\profile.yaml`

Dry-run log:

- `logs\2026-06-02\run_142934_694452_dry-run_nevernesstheeverness_pink_paw_test_route\run.log`
