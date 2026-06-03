# AGENTS.md

## Repo Working Rules

- Before starting substantial work, inspect the repo for task-specific workflow
  docs and use them as operating instructions when they exist.
- Prefer existing repo workflows over inventing a new process from scratch.
- When a workflow doc and code disagree, inspect the current code and profile
  artifacts, then update the workflow doc if needed instead of silently
  ignoring it.

## Recording-To-Profile Tasks

When the task involves any of the following:

- recording analysis
- overlay-video input reconstruction
- turning gameplay recordings into a GameScriptDev profile pack
- updating an existing profile from gameplay footage

start from the general authoring references:

1. `C:\Users\Ng Yin Hao\Documents\GameScriptDev\docs\PROFILE_TEMPLATE.md`
2. `C:\Users\Ng Yin Hao\Documents\GameScriptDev\docs\PROFILE_PACKS.md`

Then inspect the specific target profile pack if one already exists.

If the user requests this kind of task without providing both required videos,
stop and ask for:

1. the video with the visible input overlay
2. the clean video without the input overlay

## Template And Example Usage

For recording-to-profile work:

- use `C:\Users\Ng Yin Hao\Documents\GameScriptDev\docs\PROFILE_TEMPLATE.md`
  as the primary schema and structure reference
- use relevant existing profile packs as examples of how the repo applies the
  template in practice
- consider
  `C:\Users\Ng Yin Hao\Documents\GameScriptDev\profiles\neverness_the_everness\pink_paw_automation\`
  as a complete example when that helps understanding, but do not treat it as
  the default target unless the user is specifically working on that profile

## Expected Future Behavior

For recording-to-profile tasks, first identify the target pack, gather the two
required videos from the user, read the general template docs, then inspect the
target profile's local workflow and notes before proposing changes or editing
the pack.
