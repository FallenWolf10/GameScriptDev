# Separate recoverable drafts from saved profiles

The Profile Builder will persist recoverable drafts while replacing `profile.yaml` only through an explicit, validated, atomic save that retains limited revision history and refuses silent external-change conflicts. Invalid drafts remain recoverable, dry runs may use clearly labelled immutable draft snapshots, live runs may use only a Saved Profile Version, and every run receives an immutable Run Snapshot so later edits cannot change active execution.
