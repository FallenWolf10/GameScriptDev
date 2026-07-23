# Preserve comments and model disabled workflow items

The Profile Builder will preserve untouched YAML comments and ordering where possible, warn with a cancellable diff and revision backup before comment-affecting saves, and never silently discard author context. Commented executable YAML will be replaced by explicit disabled States and Actions that remain visible for authoring but are excluded from the active graph and execution; legacy comment blocks require deliberate user-assisted conversion, while long-form explanation belongs in `notes.md`.
