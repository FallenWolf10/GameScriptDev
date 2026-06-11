# Automation-Ready Macro Plan

## Scope

This is a second-pass macro-oriented reconstruction of the Pink Paw route. It
is designed as a practical replay script, not a frame-perfect TAS.

## Confirmed input rules

- `W`: forward movement
- `A` / `D`: steering correction
- `F`: interact when prompt box appears
- `1` / `2` / `3` / `4`: character swap
- mouse move left or right: turning
- mouse move up or down: pitch correction
- left click: treat as attack by default when no dialogue or chat UI is open
- do not use left click as a general selection input unless UI state explicitly
  requires it

## Interpretation notes

- The route is built mostly from `W` movement plus mouse steering.
- `D` appears more often than `A` in the sampled route.
- Rightward mouse movement is the most common mouse direction.
- Downward mouse movement appears often during stairs, drops, and laser
  alignment.
- Some mouse-button highlights appear during movement, but only `F` and swap
  keys are safe to script as deterministic route actions from the evidence
  collected.

## Macro conventions

- `hold:key:ms` means hold the key for approximately that duration.
- `tap:key[:count]` means short press, default one tap.
- `move_mouse:dir:amount` is relative camera movement.
- `wait:ms` means pause without input.
- `check_prompt:F` means watch for the interaction prompt, then press `F`.
- `swap:n` means press the numbered character key.

## Route script

### Phase 0: intro and first interaction

Time: `0.0s` to `10.0s`

1. `wait:1500`
2. `move_mouse:left:small`
3. `wait:500`
4. `check_prompt:F`
5. `wait:500`
6. `tap:F`

Validation screenshots:

- Prompt visible:
  - `C:\Users\Ng Yin Hao\Documents\GameScriptDev\artifacts\video_analysis\validation_frames\frame_000.png`
- `F` pressed:
  - `C:\Users\Ng Yin Hao\Documents\GameScriptDev\artifacts\video_analysis\validation_frames\frame_010.png`

### Phase 1: lobby departure and corridor entry

Time: `10.0s` to `45.0s`

1. `hold:W:3000`
2. `move_mouse:right:medium`
3. `hold:W:2500`
4. `tap:D:2`
5. `move_mouse:right:small`
6. `hold:W:3000`
7. `wait:200`
8. `hold:W:2000`

### Phase 2: stairs and elevation transitions

Time: `45.0s` to `90.0s`

1. `hold:W:2500`
2. `move_mouse:down:small`
3. `hold:W:1800`
4. `move_mouse:down:medium`
5. `hold:W:1200`
6. `move_mouse:up:small`
7. `tap:D:1`
8. `hold:W:2500`

### Phase 3: first large room and hazard routing

Time: `90.0s` to `150.0s`

1. `hold:W:2000`
2. `move_mouse:right:medium`
3. `tap:D:1`
4. `hold:W:1400`
5. `tap:A:1`
6. `hold:W:1800`
7. `move_mouse:left:small`
8. `move_mouse:right:medium`
9. `hold:W:2000`
10. `wait:300`
11. `tap:2`
12. `hold:W:1200`

Note:

- `swap:2` is approximate and should only be included if matching the original
  character state matters.

### Phase 4: desk, loot, and prompt interactions

Time: `150.0s` to `195.0s`

1. `hold:W:1800`
2. `move_mouse:right:small`
3. `hold:W:1000`
4. `check_prompt:F`
5. `tap:F`
6. `wait:400`
7. `move_mouse:right:small`
8. `hold:W:1200`
9. `check_prompt:F`
10. `tap:F`

### Phase 5: laser room entry

Time: `195.0s` to `225.0s`

1. `hold:W:900`
2. `move_mouse:right:small`
3. `wait:150`
4. `tap:D:1`
5. `hold:W:700`
6. `wait:200`
7. `move_mouse:down:small`
8. `tap:W:1`
9. `tap:A:1`
10. `tap:W:1`

Guidance:

- Do not long-hold `W` here.
- Use short bursts and correction pauses.

### Phase 6: laser room traversal

Time: `225.0s` to `280.0s`

Repeat this cycle as needed through the beam pattern:

1. `move_mouse:right:small`
2. `tap:W:1`
3. `wait:120`
4. `tap:D:1`
5. `wait:120`
6. `tap:W:1`
7. `move_mouse:down:small`
8. `wait:150`

Optional attack-safe rule:

- only use `left_click` if an enemy or forced combat state is present
- do not use `left_click` for prompt interaction in this route

### Phase 7: post-laser pickups and side-room traversal

Time: `280.0s` to `340.0s`

1. `hold:W:2000`
2. `move_mouse:right:medium`
3. `tap:D:1`
4. `hold:W:1500`
5. `check_prompt:F`
6. `tap:F`
7. `wait:250`
8. `hold:W:1200`
9. `move_mouse:down:small`
10. `hold:W:1200`
11. `tap:D:1`
12. `hold:W:1400`

### Phase 8: late route cleanup and possible swaps

Time: `340.0s` to `390.0s`

1. `hold:W:2200`
2. `move_mouse:right:small`
3. `tap:D:1`
4. `hold:W:1800`
5. `tap:3`
6. `wait:200`
7. `hold:W:1500`
8. `move_mouse:right:small`
9. `check_prompt:F`
10. `tap:F`

Note:

- `tap:3` should be treated as optional unless reproducing the same visible
  character swap matters.

### Phase 9: finish and summary

Time: `390.0s` to `411.2s`

1. `hold:W:1000`
2. `wait:500`
3. `tap:F`
4. `wait:3000`

## Practical automation advice

If this is implemented as a macro:

1. Drive movement with short segments instead of one long monolithic
   recording.
2. Insert prompt-aware checkpoints before every `F`.
3. Make laser-room movement stateful, with micro-pauses between forward bursts.
4. Keep character swaps optional flags so they can be disabled during testing.
5. Separate route movement from combat logic.

## Recommended scriptable states

- `movement`
- `look_adjust`
- `interaction`
- `laser_precision`
- `optional_swap`
- `dialogue_wait`

## Best-fit first implementation

If this is turned into a real automation, the safest first format would be:

- JSON action runner
- AutoHotkey v2
- a custom Python driver using timed input primitives

For this route, JSON plus a thin runner is the easiest format to iterate on.
