# Button Automations Workflow

## Sources

- Overlay capture: `C:\Users\Ng Yin Hao\Videos\2026-07-11 11-49-18.mp4`
- Clean capture: `C:\Users\Ng Yin Hao\Videos\Captures\NTE   2026-07-11 11-49-12.mp4`
- User map screenshots supplied on 2026-07-11

## Reconstruction summary

- The overlay capture is 1280x720, 30 fps, and 242.77 seconds.
- The clean capture is 1280x720, approximately 28.79 fps, and 257.23 seconds.
- The reset sequence appears near 3:32 in the overlay capture and near 3:42 in
  the clean capture.
- After teleport, the overlay shows an approximately 4.6-second `W` hold and a
  7-second `A` hold beginning about 2.2 seconds after `W`.
- The map selection, campfire detail panel, teleport control, campfire prompt,
  and campfire menu were reconstructed from the clean capture.

## Stability model

The loop does not attempt target tracking or dead reckoning back to the origin.
The teleport is the positional checkpoint. Template anchors guard the UI
transitions around that checkpoint, while the walk and farming portions remain
fixed-input phases.
