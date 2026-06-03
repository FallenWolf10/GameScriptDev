# Pink Paw Test Route Workflow

## Workflow Used

1. Read the general profile template and profile pack documentation.
2. Inspect the existing `pink_paw_automation` profile as the closest local
   example.
3. Probe both supplied videos.
4. Generate contact sheets and sampled frames under:
   `artifacts\pink_paw_test_route\`
5. Use the overlay recording to identify interaction inputs.
6. Use the clean recording to crop stable visual anchors.
7. Author a compact, guarded profile pack for the recorded test flow.

## Generated Analysis Artifacts

- `artifacts\pink_paw_test_route\overlay_contact.jpg`
- `artifacts\pink_paw_test_route\clean_contact.jpg`
- `artifacts\pink_paw_test_route\overlay_frame_*.png`
- `artifacts\pink_paw_test_route\clean_720_frame_*.png`

## Pack Files

- `profile.yaml`
- `notes.md`
- `input-reconstruction.md`
- `workflow.md`
- `assets\*.png`

## Review Notes

This route is deliberately narrower than `pink_paw_automation`. It models the
short recorded enter/exit test flow and includes anchors for major screens.
