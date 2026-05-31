# Operator Package

The source-tree operator path is the supported package shape for this roadmap
slice. It keeps live confirmation, readiness gates, profile validation, logs,
and artifacts visible while the Windows packaging wrapper is still deferred.

## Startup Checks

Run:

```powershell
game-script-dev doctor --workspace . --logs logs
```

The same checks are available to the dashboard at `/api/startup-checks`.

Checks cover:

- Python version
- runtime dependencies
- writable log folder
- profile discovery
- profile validation
- Local Demo Target profile validity
- live adapter import boundary

## Operator Flow

1. Start the dashboard with `game-script-dev-dashboard --workspace . --logs logs`.
2. Start the Local Demo Target with `python -m game_script_dev.demo_target`.
3. Select `demo__local_target` in the dashboard.
4. Run a dry run and confirm readiness.
5. Type the explicit live confirmation only after blockers are resolved.
6. Review the run timeline, log, and artifacts after completion.

The package path does not bypass live confirmation, readiness blockers, profile
validation, or the dry-run-first workflow.
