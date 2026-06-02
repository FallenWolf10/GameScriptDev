# NevernessTheEverness Inventory Toggle

## Purpose

This pack targets the running Neverness To Everness client and performs one
local menu-toggle input: press `B` once while the world-view hotkey strip is
visible.

## Target

- Process: `HTGame.exe`
- Window title contains: `NTE`
- Input mode: `background_window_messages`

The pack assumes the client is already on the expected open-world screen. It
then sends the `B` key and waits briefly.

## Current Verification Boundary

- The profile does not yet include an inventory-screen marker, so the operator
  should review the target preview or in-game screen after the run if visual
  confirmation is required.
- During this test session, background `B` input still needed external review
  because the live runner can otherwise report `success` as soon as the input
  call returns.

## Known Limitations

- Background input requires the runner or dashboard to use the same Windows
  privilege level as the NTE client.
- This pack is only for local operator-approved UI testing and does not include
  gameplay automation.
