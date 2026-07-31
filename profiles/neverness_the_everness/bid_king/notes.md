# Bid King Safety Model

> **NOT LIVE VALIDATED.** This pack is an isolated behavioral model with synthetic
> assets and geometry. It is not a runnable compatibility claim.

## Authoritative behavioral reference

- Exact commit: https://github.com/1bananachicken/MaaNTE/commit/376c6d0e8461f6633c6cf69ce6c9468b2ae6e9ff
- Referenced file: `assets/resource/base/pipeline/BidKing/BidKing.json`
- Boundary: only public state-transition behavior is retained. No MaaNTE source
  implementation, JSON grammar, PNG, ROI, threshold, coordinate, timing, binary,
  translation, or framework call is copied into this pack.

## Source-to-profile traceability

| Source behavior | Profile representation | Evidence boundary |
| --- | --- | --- |
| `BidKingEntrance` | `entry` | Direct entry state; no target fact asserted. |
| `BidKingRound`, default `max_hit: 1` | `round_01` | Exactly one statically unrolled round. User counts 1..9999 are unsupported. |
| `BidKingStart` template then click | `start` anchor plus `placeholder_start_click` | Synthetic PPM and 1x1 region only. |
| `BidKingConfirm` template then click | `confirmation` | Synthetic PPM and 1x1 region only. |
| `BidKingBalance` recognition | `ready` | Synthetic ready marker; no copied ROI or cadence. |
| `BidKingWaitBidOrSkip`, Skip before Bid | `bid_or_skip_01/02` -> `skip_check_01/02` -> `bid_check_01/02` | Explicit priority through success/failure edges. |
| Skip recognition then click | `skip_check_01/02` then `skip_01/02` | Check/action split prevents a failed skip click from falling through to Bid. |
| Bid -> SelectOne -> ConfirmBid | `bid_01/02` -> `select_one_01/02` -> `bid_confirm_01/02` | Two synthetic cycles maximum. |
| ConfirmBid returns to WaitBidOrSkip | `bid_confirm_01` -> `bid_or_skip_02` | One bounded return is retained. |
| Skip -> Exit | `skip_01/02` -> `exit` | Synthetic click regions only. |
| Exit -> Round or TaskExit | `exit` -> `round_complete` | Source default count 1 means no second round is authored. |
| `BidKingTaskExit` / `StopTask` | `round_complete` terminal result `completed` | Mapped to an explicit reachable terminal state. |

## Intentional safety changes

- Every source `timeout: -1` is discarded. The profile uses a one-second default
  timeout, one state attempt, one-tenth-second placeholder polls, and finite waits.
- The source's arbitrary round count is not implemented because the current schema
  has no declarative counter. The source default of one round is preserved by one
  explicit round state.
- The Bid -> SelectOne -> ConfirmBid -> branch loop is capped at two bid cycles.
  Reaching the cap terminates as `failed_bid_limit_reached`.
- Skip and Bid recognition are separate check states. Skip is attempted first.
  A recognition miss can branch to Bid; an action failure cannot.
- Bid check/action states forbid the Skip placeholder, so a live implementation
  would fail closed if both were present. This has not been tested against a target.
- There is no continuous input, infinite run, task restart, real target, or live
  operating instruction.

## Unsupported and unverified facts

- Real target identity, process name, window title, resolution, display scaling,
  coordinates, regions, template dimensions, thresholds, ROIs, and timings.
- Whether background window messages are accepted by the target.
- Whether screenshots remain visible and stable during input.
- Whether Skip and Bid can be simultaneously visible, flicker, or change between
  recognition and click.
- Any behavior outside the single bounded Bid King round represented here.

The `64x64` window, diagonal `1x1` regions, and all 2x2 PPM files are deliberately
synthetic authoring placeholders. Replace them only with independently captured,
reviewed evidence before considering any compatibility checklist item complete.

## Daily operating record

- Starting state: detached clean HEAD `570e86ba7a92932720192f3982178136d64cb422`.
- Protected changes: none; all existing repository files remain outside scope.
- External handoff scope: one new Bid King pack, pack-local fixtures, and one focused test module.
- Returned artifact: unified diff with SHA-256
  `25d464e466ed4a7a914d3cbc2280e06ad3908f9cf17e579a7bf60479394c2bf2`;
  reviewed and applied as 16 new Bid King-only files.
- Independent acceptance: Ruff passed; 10 focused and 282 full tests passed;
  pack check, validate-only, safe dry-run, engine scenarios, readiness gating,
  and isolated dashboard draft/saved recovery passed.
- Delivery authorization: the user authorized committing and pushing only the
  accepted Bid King files to `origin/main` after the clean acceptance gate.
- Delivery boundary: no pull request, merge operation, deployment, migration,
  live target, real-game interaction, real input, or real user data access.
  The resulting commit and remote-main verification are reported by the
  coordinating task because a commit cannot record its own final hash.
