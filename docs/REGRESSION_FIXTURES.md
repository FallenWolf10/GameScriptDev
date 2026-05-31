# Regression Fixtures

Fixtures under `fixtures/` must be small, documented, and safe to commit. The
first fixture pack is `fixtures/local_demo`, which uses repo-owned synthetic
screens from the Local Demo Target instead of real game screenshots.

Each fixture pack must include:

- `manifest.json` with provenance, expected states, expected anchors, and files
- a README describing limitations
- only repo-owned or explicitly approved content
- no sensitive user data, account state, third-party game UI, monetized reward
  evidence, or real target material before Expansion Review approval

The fixture validator rejects packs that are not marked safe to commit or that
declare third-party content.
