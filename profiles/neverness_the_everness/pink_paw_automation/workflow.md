# Pink Paw Workflow

## Goal

Turn two user-supplied route recordings into a reviewable GameScriptDev profile
pack named `Pink Paw Automation`.

## Required Inputs

This workflow expects the user to provide two videos:

- one overlay recording with visible input layout
- one clean recording without the input layout

If the task is requested without both videos, stop and ask the user to provide:

1. the video with the visible input overlay
2. the clean video without the input overlay

## Workflow Summary

1. Inspect both recordings and confirm they represent the same route at a high
   level.
2. Use the overlay recording to infer keyboard, mouse direction, and likely
   click behavior.
3. Validate ambiguous inputs with the user.
4. Write route reconstruction notes and save supporting screenshots.
5. Translate the reconstructed route into a macro-oriented action plan.
6. Convert the action plan into a valid GameScriptDev profile pack.
7. Validate the pack and record its current limitations honestly.

## Step-By-Step

### 1. Compare the recordings

Use the two recordings together for different purposes:

- overlay video: infer controls and timing patterns
- clean video: verify route shape, room order, and on-screen context

Saved evidence from this profile lives in:

- `artifacts/video_analysis/input_overlay_sheet.png`
- `artifacts/video_analysis/clean_sheet.png`

### 2. Reconstruct controls from the overlay

Use sampled overlay frames to infer the playable input model.

Confirmed mapping for this route:

- `W`: primary forward movement
- `A` and `D`: steering corrections
- `F`: interaction when the prompt box appears
- `1`, `2`, `3`, `4`: character swaps
- mouse movement: camera steering and pitch shaping
- left click: treat as attack by default outside dialogue or menu contexts

Saved notes:

- `input-reconstruction.md`

Saved frame evidence:

- `artifacts/video_analysis/overlay_events/`
- `artifacts/video_analysis/validation_frames/`

### 3. Validate ambiguous inputs with the user

Use screenshots when an input meaning needs confirmation.

For this route, the user confirmed:

- `F` is the interaction key when the box appears
- `1` to `4` are character swaps
- left click should not be modeled as a general selection input

### 4. Turn the route into a macro plan

Compress the reconstruction into phases that are practical to script:

- intro and prompt interaction
- lobby departure
- stairs and elevation changes
- large-room traversal
- desk or pickup interactions
- laser-room entry and precision traversal
- post-laser traversal
- late-route cleanup and finish

Saved macro notes:

- `macro-plan.md`
- `..\..\..\artifacts\video_analysis\macro_plan.json`
- `..\..\..\artifacts\video_analysis\input_script_template.json`

Important scripting rule from this pass:

- model the route as short movement segments with interaction checkpoints, not
  as one long continuous replay

### 5. Convert the plan into a profile pack

Pack files:

- `profile.yaml`
- `notes.md`

What the current profile encodes well:

- timed `W` movement
- `A` and `D` steering taps
- timed `F` interactions
- optional swap taps
- laser-room movement as short bursts

What the current profile cannot encode yet:

- declarative mouse-look movement
- prompt-aware branching before each `F`

### 6. Validate the resulting pack

Commands used for this pack:

```powershell
python -m game_script_dev --profile profiles\neverness_the_everness\pink_paw_automation\profile.yaml --validate-only
python -m game_script_dev --profile profiles\neverness_the_everness\pink_paw_automation\profile.yaml
python -m game_script_dev check-pack --profile profiles\neverness_the_everness\pink_paw_automation\profile.yaml
```

Expected outcome:

- schema validation passes
- dry run completes
- pack check passes

### 7. Record the boundary honestly

The current `Pink Paw Automation` pack is a key-driven approximation of the
observed route, not a frame-perfect live replay.

Reason:

- the investigated route depends heavily on mouse steering
- the current profile schema does not yet declare mouse-look actions
- `F` interactions are scheduled by timing rather than prompt detection

This boundary is documented in:

- `notes.md`
- `profile.yaml`

## Recommended Next Improvement

To make this workflow produce a closer replay profile next time, extend the
runner and schema with:

- mouse-move or mouse-look actions
- prompt-aware interaction checks before scripted `F` presses
