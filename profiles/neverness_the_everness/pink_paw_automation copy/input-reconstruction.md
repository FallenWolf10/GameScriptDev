# Recording Input Reconstruction

## Source Inputs

This reconstruction was produced from the two user-supplied route recordings
for this profile:

- one overlay recording with visible input layout
- one clean recording without the input layout

## What I checked

- Compared both recordings at overview level using generated contact sheets.
- Sampled the overlay recording at multiple timestamps to read the keyboard and
  mouse overlay.
- Cross-checked the broad route against the clean recording.

Artifacts created during analysis:

- `C:\Users\Ng Yin Hao\Documents\GameScriptDev\artifacts\video_analysis\input_overlay_sheet.png`
- `C:\Users\Ng Yin Hao\Documents\GameScriptDev\artifacts\video_analysis\clean_sheet.png`
- `C:\Users\Ng Yin Hao\Documents\GameScriptDev\artifacts\video_analysis\overlay_events\`

## Technical observations

- Overlay recording:
  - `1280x720`
  - `30 fps`
  - `411.2s`
- Clean recording:
  - `1920x1080`
  - reported around `60 tbr`
  - `407.5754s`

This means the two videos show the same route style, but they are not
frame-perfect twins. The clean recording is slightly shorter and captured at a
different resolution and frame cadence.

## High-confidence control mapping

These are the inputs I can infer with the strongest confidence from the
overlay:

- `W`: primary forward movement
- `A` / `D`: lateral correction while steering through rooms and corridors
- `F`: confirmed by user as the interaction key when the prompt box appears
- `1` / `2` / `3` / `4`: confirmed by user as character swap keys
- Mouse movement:
  - left/right: camera turning
  - up/down: pitch adjustment while going up stairs, down stairs, or checking
    angles

## Interaction prompt validation frames

These frames show the `F` interaction prompt clearly:

- Prompt visible:
  - `C:\Users\Ng Yin Hao\Documents\GameScriptDev\artifacts\video_analysis\validation_frames\frame_000.png`
  - `C:\Users\Ng Yin Hao\Documents\GameScriptDev\artifacts\video_analysis\validation_frames\frame_002.png`
  - `C:\Users\Ng Yin Hao\Documents\GameScriptDev\artifacts\video_analysis\validation_frames\frame_004.png`
- `F` pressed to enter or advance interaction:
  - `C:\Users\Ng Yin Hao\Documents\GameScriptDev\artifacts\video_analysis\validation_frames\frame_010.png`

## Mouse investigation

The mouse overlay appears to encode both direction and button state.

- Direction-only movement:
  - arrow right: horizontal camera turn to the right
  - arrow left: horizontal camera turn to the left
  - arrow down: camera pitch down
  - arrow up: camera pitch up
- Button states:
  - yellow top-left mouse button: likely left click
  - yellow top-right mouse button: likely right click or right-button hold

User clarification:

- Left click should be treated as attack by default when no chat or dialogue
  box is open.
- Left click may sometimes function as confirm or selection in UI contexts, but
  it should be ignored for route scripting unless a dialogue or menu state
  explicitly requires it.

Example mouse frames:

- plain rightward mouse look:
  - `C:\Users\Ng Yin Hao\Documents\GameScriptDev\artifacts\video_analysis\validation_frames\frame_068.png`
  - `C:\Users\Ng Yin Hao\Documents\GameScriptDev\artifacts\video_analysis\validation_frames\frame_252.png`
- right-button-highlight plus downward look:
  - `C:\Users\Ng Yin Hao\Documents\GameScriptDev\artifacts\video_analysis\validation_frames\frame_070.png`
- left-button-highlight plus rightward look:
  - `C:\Users\Ng Yin Hao\Documents\GameScriptDev\artifacts\video_analysis\validation_frames\frame_130.png`
- upward look:
  - `C:\Users\Ng Yin Hao\Documents\GameScriptDev\artifacts\video_analysis\validation_frames\frame_188.png`
- downward look:
  - `C:\Users\Ng Yin Hao\Documents\GameScriptDev\artifacts\video_analysis\validation_frames\frame_190.png`

Working interpretation:

- Mouse movement is a major part of the route, not a small correction layer.
- Rightward movement is the most common directional mouse input in the sampled
  route.
- Downward movement appears often during stairs, drops, and laser alignment.
- Right-click-highlighted moments likely represent view control while turning
  or re-aiming.
- Left-click-highlighted moments should be interpreted as attack by default
  outside chat or dialogue contexts.
- For this reconstruction, left click should not be used as a general-purpose
  selection input.

## Likely route and action sequence

Times below are approximate and meant as a reconstruction guide, not a
frame-accurate TAS script.

### 0:00 to 0:35

- Loading, intro, or mission setup.
- Expected input:
  - no movement required
  - possible `F` or confirm input to advance NPC or mission prompt

### 0:35 to 1:10

- Character starts moving through the hotel or lobby area.
- Overlay strongly shows `W`, with `D` appearing during turns.
- Expected input:
  - hold `W`
  - tap or feather `D` for rightward steering
  - move mouse right to face the target corridor

### 1:10 to 1:45

- Transition through corridor, staircase, or doorway spaces.
- Overlay samples show forward motion plus vertical camera adjustment.
- Expected input:
  - hold `W`
  - move mouse down when descending
  - move mouse up when re-centering view

### 1:45 to 2:30

- Blue-lit room and first larger navigation section.
- Red floor indicators appear in some samples, suggesting hazard avoidance.
- Expected input:
  - `W` as the base input
  - short `A` / `D` taps to adjust path around danger zones
  - mouse left or right for corridor alignment
  - optional character switch with `1` / `2` / `3` / `4` if matching the exact
    on-screen character state matters

### 2:30 to 3:10

- Counter, desk, or loot interaction area.
- Character approaches furniture and pickup zones.
- Expected input:
  - `W` to approach
  - mouse right or left to line up with objects
  - `F` for interact or pickup when prompt appears

### 3:10 to 4:10

- Laser trap section and tighter navigation.
- This is the part where steering precision matters most.
- Expected input:
  - short `W` bursts instead of continuous hold
  - `A` / `D` taps to sidestep beams
  - careful mouse turning to keep the character aligned with openings
  - avoid over-rotating; the route looks more like small corrections than big
    swings

### 4:10 to 5:20

- More traversal through side rooms, staircases, and pickup points.
- Overlay shows continued forward movement with repeated rightward steering.
- Expected input:
  - `W`
  - frequent small `D` taps
  - occasional mouse down or up for stairs and room checks
  - `F` when reaching interactables

### 5:20 to 6:10

- Late-stage route segment near the larger open interior area and goal objects.
- Samples suggest movement cleanup rather than combat-heavy execution.
- Expected input:
  - `W` to close distance
  - mouse right for final corridor turns
  - possible character switch with `1` / `2` / `3` / `4`

### 6:10 to end

- End transition, summary, or mission completion screen.
- Expected input:
  - minimal movement
  - possible confirm or continue input

## Practical simulation plan

If the goal is to perform a similar recording again, model the input sequence
like this:

1. Start with a route script built around `W` as the dominant input.
2. Treat `A` and `D` as short steering corrections, not long strafes.
3. Use mouse movement for nearly all facing changes.
4. Add explicit mouse-direction segments, especially rightward and downward
   camera adjustments.
5. Reserve `F` for:
   - starting the route
   - NPC or prompt interaction
   - pickup or checkpoint interaction
6. Add optional `1` / `2` / `3` / `4` steps only if reproducing the same
   character swaps is important.
7. In the laser sections, replace long holds with short move-adjust-move
   cycles.

## Suggested add or remove actions

If the goal is a cleaner repeatable simulation:

- Keep:
  - `W`-driven route progression
  - mouse steering
  - interaction checkpoints
  - short sidesteps in hazard sections

- Remove or minimize:
  - unnecessary camera wobble
  - long diagonal drift when `W` plus `A` or `D` is not needed
  - extra character swaps unless they are functionally required
  - over-correction near laser obstacles

- Add:
  - explicit checkpoint interactions in the script
  - tighter pause windows before laser crossings
  - per-room camera targets so the route is more reproducible

## Confidence and limits

- High confidence:
  - dominant movement pattern
  - general route structure
  - interaction-based progression
  - laser section requiring careful sidestep steering
  - `F` as interaction
  - `1` / `2` / `3` / `4` as character swaps
  - mouse direction cues as route-shaping inputs

- Medium confidence:
  - exact moment of each interact press
  - whether every yellow mouse-button state is a tap or a short hold
  - exact duration of each left-click-highlighted attack input

- Low confidence without user confirmation:
  - frame-accurate timings for a macro
  - exact mapping of every prompt in Chinese UI text
