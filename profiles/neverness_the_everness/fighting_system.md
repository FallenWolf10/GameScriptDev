# NevernessTheEverness Fighting System Notes

## Purpose

This document summarizes how combat appears to work in the local Neverness To
Everness setup from a scripting and profile-authoring perspective.

It is written to help turn observed gameplay into reliable GameScriptDev
actions, not to serve as a full game guide.

## Scope

These notes are based on:

- local recording analysis from the NTE route work
- the observed `1:00` to `1:20` combat sample from the supplied videos
- the current GameScriptDev input model, including camera movement support

These observations should be treated as practical local guidance, not as a
universal statement about every NTE character, build, or combat mode.

## Core Combat Model

The observed combat loop is built from four layers working together:

1. character movement
2. camera facing
3. attack input
4. short reposition and cleanup

In practice, combat does not look like a pure button-rotation system. It is
highly dependent on camera direction and short positional correction.

## What Each Input Seems To Do

- `W`
  - closes distance
  - enters the room or pack
  - keeps pressure on enemies between bursts
- `A` / `D`
  - provides small lateral correction
  - helps keep angle without making a large camera turn
- left click
  - a single left click is the normal attack input
  - a held left click is the heavy attack input
  - outside UI contexts, left click should be treated as attack by default
- camera movement
  - is used to face the enemy pack
  - is used to sweep across multiple targets
  - is required to recenter after burst effects or enemy displacement
- skill keys such as `Q` / `E`
  - appear to fit naturally as short burst or special-action inserts between
    basic attack windows
  - should be validated per character before being relied on in a live script

## Why Camera Movement Matters

The most important combat observation is that fighting depends on facing.

Even when the attack input is correct, combat becomes unreliable if the camera
is not pointed into the enemy pack. For scripting purposes, this means:

- attack timing alone is not enough
- the script should face the pack before the burst starts
- the script should include small recenter movements during cleanup
- camera correction is part of the combat loop, not a separate polish step

## Foreground Requirement

The current camera-input actions require foreground mode in this repo.

That means combat sections that use:

- `move_mouse`

should be treated as foreground-controlled segments. A route can still use
background-compatible actions elsewhere, but camera-driven combat needs active
focus on the game window for reliable execution.

## Practical Combat Phases

The observed fight is best modeled as a short state sequence instead of one
long freeform macro.

### 1. Approach

- move forward into the encounter
- apply one small camera turn toward the spawn
- stop drifting before the main burst starts

### 2. Face Pack

- use a small or medium camera correction to center the enemy group
- avoid starting sustained attack while facing off-angle

### 3. Opening Burst

- begin normal attack input
- use short attack taps rather than heavy attack holds in most fight scenes
- insert one quick skill key if the chosen character uses it reliably

### 4. Recenter

- correct the camera after knockback, dash movement, or enemy spread
- do not over-rotate

### 5. Cleanup

- attack the remaining target or survivors
- use another small camera correction if the pack has shifted

### 6. Exit

- transition back to movement only after the room is visually clear or the next
  route cue is present

## Recommended Script Shape

With the current local action support, combat should be authored as a sequence
like this:

- short `hold_key w` to enter
- `move_mouse` to face the pack
- repeated single left-click attack inputs for the main burst
- optional quick skill key insert
- another `move_mouse` for recenter
- second short attack window
- visual confirmation or route transition

This is usually better than:

- a long fixed hold with no facing correction
- repeated attacks without camera adjustment
- trying to model the whole fight as pure keyboard movement

## Region Usage In Combat

Regions are still useful in NTE profiles, but mainly for UI and stable
screen-space clicks.

For combat:

- use camera movement to aim and shape the burst
- use regions only when there is a real fixed click target
- do not treat a combat region as if it were target tracking or pathfinding

If an enemy moves, a region does not follow it. Camera movement and live game
positioning are what keep attacks aligned.

## Local Camera Calibration

Current local calibration note:

- approximately `dx: 4114.5` corresponds to a full `360` degree camera turn

Useful rough fractions:

- `dx: 2057` is about a half turn
- `dx: 1029` is about a quarter turn
- `dx: 514` is about an eighth turn
- small combat corrections will often land in the `80` to `250` range

These are practical starting points only. Final values still depend on:

- in-game sensitivity
- DPI
- Windows pointer settings
- the exact encounter angle and how much recentering is needed

## Recommended Authoring Rules

- start every combat script by defining the expected facing direction
- keep combat bursts short and segmented
- insert explicit recenter steps between burst windows
- prefer small mouse deltas over big turns once combat has started
- treat single left clicks as the default combat attack
- reserve held left click for heavy attack use cases only
- prefer normal attacks in most fight scenes unless a specific sequence proves a
  heavy attack is needed
- validate skill-key meaning per character instead of assuming one shared loadout
- end combat states with a visual cue whenever possible

## Observed Combat Pattern From The Sample

In the reviewed `1:00` to `1:20` segment, the practical pattern looked like:

1. move into the room
2. face the enemy cluster
3. begin burst while sweeping the camera across the pack
4. recenter on survivors
5. finish the remaining target
6. resume route movement

This makes the fight a good fit for a state-driven combat block rather than a
single route movement state.

## Current Limits And Risks

- not every character may map cleanly to the same burst keys
- fixed timing without visual confirmation can drift
- camera-input combat requires foreground focus
- heavy visual effects can make post-burst confirmation harder
- moving enemies can break scripts that rely on one static opening angle

## Current Team Understanding

The current local working rule is:

- single left click = normal attack
- held left click = heavy attack
- most scripted fight scenes should favor normal attacks

At the moment, this is the model we should author against unless later footage
shows a specific exception.

## Best Next Improvement

The strongest next step for high-confidence NTE combat scripting is:

- add encounter-specific visual anchors for
  - enemy present
  - combat cleared
  - exit or next-route cue

That would let combat states become:

- enter
- face
- burst
- confirm clear
- continue

instead of depending only on timing.
