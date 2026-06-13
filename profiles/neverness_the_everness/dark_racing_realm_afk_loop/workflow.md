# Dark Racing Realm Profile Workflow

## Authoring Steps

1. Read `docs/PROFILE_TEMPLATE.md`.
2. Read `docs/PROFILE_PACKS.md`.
3. Inspect the existing NTE recording-derived profile packs.
4. Probe both supplied recordings.
5. Generate overview and dense input-overlay artifacts under
   `artifacts\nte_recording_2026-06-11_2323\`.
6. Align the recordings by visible screen state.
7. Identify meaningful keyboard and mouse events.
8. Crop stable anchors from the clean recording.
9. Author an infinite, guarded AFK race loop.
10. Validate the profile and run the profile-pack check.

## Analysis Artifacts

- `artifacts\nte_recording_2026-06-11_2323\clean_contact.png`
- `artifacts\nte_recording_2026-06-11_2323\overlay_contact.png`
- `artifacts\nte_recording_2026-06-11_2323\startup\`
- `artifacts\nte_recording_2026-06-11_2323\timeline\`
- `artifacts\nte_recording_2026-06-11_2323\clean_timeline\`
- `artifacts\nte_recording_2026-06-11_2323\clicks\`
- `artifacts\nte_recording_2026-06-11_2323\clean_frames\`

## Authoring Decisions

- Use template anchors from the clean capture.
- Use fixed click regions only for the recorded 1280x720 menu layout.
- Prefer `wait_for_state` for matchmaking, race completion, and world return.
- Send no movement input during the race.
- Omit incidental attack clicks.
- Reopen the event with `Esc` after each completed race, matching the recorded
  return path.
