# Split live runtime adapters

Live desktop control will be split into window, screen, vision, and input adapters instead of one combined desktop adapter. This keeps the state-machine runner independent from platform libraries, makes dry-run behavior easy to test, and lets future implementations swap screenshot, template matching, OCR, or input libraries without rewriting workflow execution.
