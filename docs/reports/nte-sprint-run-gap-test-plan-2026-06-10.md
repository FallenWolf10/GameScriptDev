# NTE Sprint-Run Gap Test Plan

Date: 2026-06-10

## Objective

Determine the minimum stable and most efficient timing gap for sprint-run input
in the local Neverness To Everness setup.

For this test, "timing gap" means the delay between the sprint-triggering input
and the follow-up movement/run input, or the delay between repeated inputs if
the mechanic proves cadence-sensitive during live observation.

This document records the plan and reasoning before starting any live in-game
testing.

## Why This Needs A Measured Test

Prior repo diagnostics already showed that NTE can ignore inputs that are
technically sent but held for too little time or delivered with the wrong
timing. The existing key timing diagnostic established a practical rule:

- zero-length or near-zero taps can be missed by the game
- about `0.1s` dwell was enough for reliable key detection in earlier tests

Because sprint-run behavior is movement-sensitive and may depend on animation
state, stamina state, or client polling windows, this should be treated as a
live timing sweep rather than a one-off guess.

## Working Hypothesis

The best sprint-run gap will likely not be the absolute shortest value that
works once. It will be the lowest value that:

- triggers the intended sprint-run behavior repeatedly
- does not degrade into walking, stutter-starting, or partial sprint
- remains stable across several back-to-back trials

My expectation before testing is:

- values below `0.05s` may be inconsistent
- the stable floor may land around `0.08s` to `0.15s`
- the most efficient practical value may be slightly above the minimum stable
  value to preserve repeatability

These are only starting assumptions and must be validated live.

## Definitions

- Minimum stable gap:
  The smallest tested delay that succeeds consistently across the acceptance
  trial count.
- Most efficient gap:
  The smallest stable delay that also produces clean in-game sprint-run
  behavior without visible hesitation and without requiring extra retries.
- Success:
  The character enters the intended sprint-run behavior promptly after the input
  sequence.
- Failure:
  The character walks, stalls, only partially accelerates, or behaves
  inconsistently compared with the intended sprint-run result.

## Planned Test Method

The live test should be performed with Computer Use controlling the game window
while I observe the result visually after each attempt.

The plan is to use a controlled manual sweep:

1. Put the character in the same safe, open in-game location.
2. Keep camera angle and starting posture as consistent as possible.
3. Trigger the sprint-run sequence using the same exact input order each trial.
4. Change only the timing gap under test.
5. Observe whether sprint-run starts correctly.
6. Repeat each candidate gap multiple times before judging it stable.

## Detailed In-Game Setup

The earlier version of this plan intentionally stayed general. For actual live
use, the setup should be tightened into one repeatable in-game staging routine.

Target staging requirements:

- be on the normal in-world exploration screen
- do not be inside a menu, dialogue, map, inventory, or interact prompt
- do not be in combat
- do not be on stairs, uneven terrain, ledges, or a sloped road
- do not begin the test while turning the camera
- do not begin with the character already moving

Preferred staging location:

- a flat, open ground segment with a long forward path
- no nearby NPC interaction bubble overlapping the movement path
- no objects that force auto-climb, collision slowdown, or path correction
- a background with enough visual reference points to judge acceleration
  cleanly, such as road markings, repeated floor seams, curb edges, or fixed
  environmental props

Starting pose:

- character fully stopped
- camera already aligned behind the character
- character facing straight down the chosen lane
- stamina or equivalent movement resource visibly full if the game uses one

The operator should keep this staging spot for the entire sweep unless the spot
proves noisy or obstructed.

## Detailed Computer Use Test Loop

Once Computer Use is available, each individual trial should follow the same
micro-sequence instead of improvising between attempts.

Per-trial loop:

1. Activate the NTE window.
2. Confirm the game is on world view and not on a UI overlay.
3. Confirm the character is fully stationary.
4. Confirm the camera is centered behind the character.
5. Send the sprint input.
6. Wait exactly the candidate gap under test.
7. Send and hold the forward movement input for a fixed short movement window.
8. Release the movement input.
9. Observe the first `0.3s` to `0.8s` of movement response.
10. Reset the character to the same start lane and stopped posture.

Recommended fixed values for consistency:

- sprint key dwell: start with `0.1s`
- forward movement hold window per trial: `0.8s` to `1.0s`
- post-trial settle wait before the next attempt: `1.0s`

If the mechanic proves to be double-tap based instead of modifier based, the
same structure still applies, but the tested variable becomes the inter-tap
delay rather than the sprint-to-forward delay.

## Detailed In-Game Confirmation Checklist

Each trial needs a stricter confirmation rule than "it looked fast enough."

Before marking a trial as a success, confirm all of the following:

- the character did not remain in walk speed for the opening movement
- the character did not hesitate for a visible beat before accelerating
- the character did not perform a partial start then settle into slower motion
- the character moved straight enough that steering correction was not the
  reason it looked fast or slow
- the response looked like the intended sprint-run state from the very start of
  the forward burst

Mark the trial as a failure if any of the following happens:

- no movement starts after the input sequence
- only normal walking begins
- sprint starts late after an obvious delay
- sprint starts inconsistently halfway into the forward hold
- the character clips an object, changes elevation, or gets interrupted by UI
- camera drift makes the speed read unreliable

Mark the trial as invalid rather than pass or fail if:

- the camera was not centered before the attempt
- a menu or interact prompt appeared
- the character was already drifting or rotating
- stamina or another resource was not in the intended baseline state
- an external disturbance changed the scene between reset and input

## Visual Cues To Use During Confirmation

The operator should judge sprint-run onset by several visible cues together
instead of relying on only one.

Primary cues:

- immediate increase in ground-covering speed relative to a normal `W` start
- quicker passage of floor seams, lane lines, or other repeated ground markers
- sprint-specific body animation or posture change if NTE shows one
- stronger or earlier camera bob / motion cadence compared with ordinary walk

Secondary cues:

- stamina bar begins reacting in the way expected for sprint
- dust, trail, or movement FX appear only during true sprint-run
- character reaches a known ground reference noticeably earlier than a walk
  attempt would

If the game exposes a sprint-only stamina drain or animation state, that should
be treated as stronger evidence than perceived speed alone.

## Recommended Control Comparisons

To avoid misreading animation timing, the operator should keep two reference
behaviors in mind:

- one clean normal-walk `W` start with no sprint input
- one known-good generous sprint-run attempt using a high gap such as `0.18s`
  or `0.20s`

These control references help distinguish:

- true failure
- borderline delayed sprint
- clean sprint-run success

## Reset Method Between Trials

A good reset matters because this is a boundary-finding test.

Between attempts:

- stop all movement completely
- return to the same lane or alignment
- restore the camera behind the character
- wait for any stamina refill if the mechanic consumes it
- confirm there is no active prompt, target lock, combat state, or environmental
  obstruction

If reset quality starts drifting, pause the sweep and rebuild the staging
position instead of continuing with contaminated data.

## Detailed Recording Table

The session notes should use a more precise per-gap record than the earlier
high-level list.

Recommended columns:

- gap
- sprint dwell
- forward hold
- trial number
- result: pass / fail / invalid
- onset type: immediate / delayed / partial / walk-only
- environment note
- confirmation note

Example confirmation note phrases:

- `clean immediate sprint from frame one`
- `walk for a moment, sprint late`
- `normal walk only`
- `invalid: interact prompt appeared`
- `invalid: camera was off-center`

## Decision Boundary For Final Recommendation

The final recommendation should not be chosen only from raw pass rate.

Choose the lowest stable gap only when:

- refined confirmation trials all pass
- the startup looks visually clean, not barely acceptable
- the value remains stable after short repetition, not only isolated success

Choose a slightly higher operational recommendation when:

- two neighboring gaps both pass
- the lower value shows occasional hesitation
- the higher value gives visibly cleaner startup with no practical efficiency
  penalty

## Current Computer Use Verification Status

This document now includes the detailed in-game procedure and confirmation
criteria that should be used with Computer Use.

However, direct Computer Use inspection was not completed in this pass. The
supported Computer Use bootstrap path was attempted, but the Windows helper was
not available to complete live app inspection in this turn. That means the
procedure above is a concrete operator-ready script, but it is not yet stamped
with new live observations from this session.

Latest attempt note:

- Date attempted: `2026-06-11`
- Method attempted: supported Computer Use bootstrap through the plugin runtime
- First action attempted: `sky.list_apps()`
- Blocking failure:
  `node_repl kernel exited unexpectedly` with Windows helper diagnostics ending
  in `CreateProcessAsUserW failed: 5`
- Practical result:
  no app listing, no live NTE window selection, and no in-game sprint-run trial
  could be executed from this session

## Why Computer Use Is The Right Tool Here

This specific task is exploratory and visual. Computer Use is useful because it
lets the test stay grounded in the actual live client behavior instead of only
assuming the automation runner's input send means the game accepted it.

Computer Use will help with:

- activating the NTE window if foreground behavior is required
- sending the live input sequence at controlled timings
- visually checking whether the result is true sprint-run instead of only
  trusting an automation-side "success"
- adjusting the test pace in real time if the game shows context-dependent
  behavior

## Variables To Control

To keep the timing result meaningful, these factors should stay as fixed as
possible during the sweep:

- same character
- same movement direction
- same in-game location and terrain
- same camera orientation
- same stamina/resource state if sprint consumes one
- same window focus state
- same privilege level between the automation tool and the game
- same frame conditions as much as practical

If any of these drift, the affected trial should be marked suspect instead of
being treated as clean evidence.

## Candidate Gap Sweep

I plan to test a coarse-to-fine ladder instead of checking many random values.

Initial coarse sweep:

- `0.00s`
- `0.03s`
- `0.05s`
- `0.08s`
- `0.10s`
- `0.12s`
- `0.15s`
- `0.18s`
- `0.20s`

If a stable zone appears, I will refine around the boundary with smaller steps,
for example:

- `0.06s`
- `0.07s`
- `0.09s`
- `0.11s`
- `0.13s`

This keeps the test efficient while still letting us identify a practical floor.

## Trial Count And Acceptance Rule

For each coarse value:

- run `5` trials

For each refined candidate near the lower stable boundary:

- run `8` to `10` trials

Acceptance rule for "stable":

- no failed trials in the refined confirmation set

If two nearby values both pass, prefer the slightly higher one when the lower
value shows even minor hesitation or ambiguity in visual startup.

## Evidence To Record

For each tested gap, I plan to document:

- the exact gap value
- trial count
- number of successes
- number of failures
- observed behavior notes
- whether the result looked immediate, delayed, or inconsistent

If practical during the live session, I should also capture:

- short screen recordings or screenshots for representative pass/fail examples
- notes about whether foreground focus seemed necessary
- notes about whether a key dwell adjustment was also needed

## Decision Logic

After the sweep, I will classify results like this:

- Unusable:
  frequent failure or clearly inconsistent startup
- Borderline:
  mostly works but shows hesitation or occasional misfire
- Stable:
  repeated clean sprint-run activation

Final recommendation should include two values:

- lowest stable gap
- recommended operational gap

Those may be the same value, but they do not have to be.

## Planned Execution Sequence

1. Launch or confirm the NTE client is already running in the intended test
   area.
2. Confirm the game window title/process and privilege level are compatible with
   live control.
3. Use Computer Use to bring the client into a clean repeatable starting state.
4. Perform the coarse sweep.
5. Narrow the sweep around the first stable boundary.
6. Re-test the best candidate set with a higher trial count.
7. Record the minimum stable gap and the recommended efficient gap.
8. Write a follow-up results report after the live test finishes.

## Risks And Watchouts

- Sprint behavior may depend on more than one timing variable.
- The mechanic may require both a non-zero gap and a non-zero key dwell.
- Terrain, stamina, or combat state may make a working value look unstable.
- Foreground-only behavior could make background-style assumptions misleading.
- Human-visible judgment can be noisy if the sprint transition animation is
  subtle.

If these appear during testing, I should expand the documentation to separate:

- gap timing
- key dwell timing
- focus requirement

instead of forcing one oversimplified conclusion.

## Planned Deliverables

Before live testing:

- this planning document

After live testing:

- a results report in `docs/reports/`
- the recommended minimum stable sprint-run gap
- the recommended efficient operating gap
- notes on any extra constraints discovered during testing

## Current Status

Planning documented.

No live Computer Use testing has been started yet in this document stage.
