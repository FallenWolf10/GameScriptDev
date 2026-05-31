# Expansion Review

Expansion Review is required before adding or live-testing a real target profile
pack. It keeps profile work bounded to local, user-approved,
ToS-compliant automation and records why a target is safe to automate.

## Required Record

Each real target pack must include `expansion_review.md` beside `profile.yaml`.
The Local Demo Target is exempt because it is repo-owned and contains no third
party service, account, monetized reward, or anti-cheat surface.

Use `profiles/_templates/expansion_review.md` when starting a real pack.
Authoring checks require the final review to explicitly record:

- `Target rules reviewed: yes`
- `Permitted local automation documented: yes`
- `Operator confirmation recorded: yes`
- target-specific `Do Not Automate` boundaries

## Deferred Real Target Work

Roadmap Section 13 is intentionally deferred until an operator chooses a
specific real target and confirms that its rules permit the planned local UI
workflow. No real target profile, real target screenshots, or real target
fixtures should be added before that confirmation is captured in the pack's
Expansion Review.

Stop immediately if the target requires anti-cheat bypass, stealth behavior,
account farming, monetized grinding, evasion logic, or any other behavior
outside the safety boundary in `CONTEXT.md`.
