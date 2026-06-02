# NevernessTheEverness Startup Clicks

## Purpose

This profile targets the running Neverness To Everness game client and performs
one local startup sequence: four left mouse clicks at the configured
`startup_click` region, then `2`, then `E`.

## Target

- Process: `HTGame.exe`
- Window title contains: `NTE`
- Input mode: `background_window_messages`

Computer Use detected the live window as
`D:\Games\Neverness To Everness\Client\WindowsNoEditor\HT\Binaries\Win64\HTGame.exe`
with the title `NTE`. This profile uses background window-message input by
default, so the target window does not need to own foreground focus unless
operator testing proves this client needs the foreground fallback.

Windows blocks background window messages from a lower-privilege process to a
higher-privilege target. If NTE is running elevated, launch the dashboard or CLI
runner elevated as well before starting a live run.

## Known Limitations

- The click target is centered for a 1280x720 window. Move the
  `regions.startup_click` rectangle if the intended click location is different.
- Background input requires the runner or dashboard to use the same Windows
  privilege level as the NTE client.
- The profile assumes the user has already opened the game and approved local
  automation for this exact input sequence.
- This pack does not include screenshot anchors because it is an immediate
  startup input macro rather than a screen-detected workflow.
