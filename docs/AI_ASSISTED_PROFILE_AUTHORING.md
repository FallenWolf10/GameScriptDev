# AI-Assisted Profile Authoring From Paired Videos

Use this workflow when an AI assistant helps turn gameplay recordings into a
GameScriptDev Profile Pack. The output is a reviewable proposal, not proof that
live automation is safe or reliable.

Start with:

- [Profile Template](PROFILE_TEMPLATE.md) for the schema and Action contracts
- [Profile Packs](PROFILE_PACKS.md) for pack structure, compatibility evidence,
  known limitations, and readiness requirements
- the target pack's existing `workflow.md`, `notes.md`, and
  `input-reconstruction.md`, when present

## Required Inputs

Obtain both recordings before authoring:

1. a video with the keyboard and mouse input overlay visible
2. a clean video without the input overlay

Also record the intended routine, target pack, expected starting state, desired
outcome, supported resolution/UI settings, and operator stop conditions. Align
the videos by visible state transitions; do not assume their timestamps, frame
rates, resolutions, or routes match exactly.

## Workflow

### 1. Propose the Minimum Workflow

Use the overlay video to infer only the inputs needed to move between meaningful
states. Use the clean video to identify stable visual anchors and confirm the
route's visible outcomes.

Draft the smallest useful state graph and Action sequence:

- name observable start, progress, success, and failure states
- prefer anchor-confirmed transitions over long blind timing chains
- omit incidental clicks, attacks, camera movement, or repeated input that does
  not advance the routine
- preserve uncertainty in notes instead of inventing precision

The goal is to reproduce state transitions and the video's intended outcome,
not to copy every recorded input frame by frame.

### 2. Validate Without Live Input

Review the proposed YAML and pack files against the Profile Template and Profile
Packs documentation. Confirm:

- schema and Profile Pack checks pass
- target identity and supported resolution are explicit
- required assets exist and are sourced from appropriate clean frames
- success, failure, timeout, interruption, and terminal behavior are explicit
- known limitations and uncertain inferences are documented

Static validation proves structure only. It does not prove capture, anchor
recognition, input delivery, timing, or target behavior.

### 3. Collect Controlled Dry-Run Evidence

Run only through the normal dashboard dry-run workflow, with no live input.
Capture:

- screenshots for expected states and anchor matches
- the state/action timeline, including retries and timeouts
- the run log and final result
- any mismatch between the proposed graph and the clean video

Compare the evidence against video goals and expected state transitions. Revise
one state, anchor, Action, timing value, or failure path at a time, then repeat
static validation and the dry run. Do not enable live mode while evidence is
ambiguous or readiness remains blocked.

### 4. Gate a Short Supervised Live Trial

A live trial requires the user's explicit approval after they review the dry-run
evidence, known limitations, exact trial scope, and stop criteria. The user must
remain present and able to trigger the emergency stop.

Keep the first trial short and bounded to the smallest useful transition or
Action sequence. Before starting, verify:

- the intended target window and starting state
- the approved Profile version and immutable run snapshot
- the emergency-stop control and release of held input
- a conservative time limit and maximum retry count
- no unrelated account, reward, purchase, destructive, or irreversible action
  is reachable

Stop immediately on unexpected focus or target identity, loss of visibility,
anchor disagreement, wrong state, repeated timeout, unintended input, UI or
resolution change, user intervention, or emergency stop. Never continue by
guessing, broaden the trial automatically, or treat partial success as approval
for a longer run.

### 5. Review and Iterate

After every supervised trial, preserve screenshots, timeline, logs, final state,
stop reason, and released-input status. Compare observed states and transitions
with the clean-video goal and the approved proposal.

Make one evidence-backed change at a time. Return to static validation and dry
run after each change; require fresh user approval before another live trial.

## Final Evidence Record

Add a dated record to the target pack's notes or its focused authoring report:

- source videos and how they were aligned
- approved routine scope and Profile revision
- proposed and observed state transitions
- validation and Profile Pack check results
- dry-run and supervised-live run identifiers
- representative screenshots, timeline, and log locations
- changes made during iteration
- final outcome, explicit stop reason, and emergency-stop result
- unresolved uncertainties, known limitations, supported environment, and
  whether live readiness was actually established

Do not store sensitive account data, monetized-reward evidence, or unsuitable
third-party content in the repository. An AI-authored Profile remains
human-reviewed and evidence-gated; recorded input, passing tests, or a successful
dry run alone must never be presented as proof of general real-game reliability.
