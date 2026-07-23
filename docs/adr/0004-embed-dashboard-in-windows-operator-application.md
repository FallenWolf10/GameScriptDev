# Embed the dashboard in the Windows Operator Application

The Windows-first Operator Application will use a thin pywebview/WebView2 shell around the existing local dashboard and Python runner instead of rewriting the interface in a native toolkit or adding a Rust/Node desktop host. This preserves the current runner and web UI, suits the visual Profile Builder, and makes packaged parity the first proof: installation, preview, dry/live execution, elevation, fail-closed ownership, logs, artifacts, and constrained profile writes must work before the dashboard redesign proceeds.
