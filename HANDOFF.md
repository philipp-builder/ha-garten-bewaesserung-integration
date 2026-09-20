# Handoff — 2026-09-20

- v1.9.1 fixes daily plan announcements during active winter/holiday/other pauses.
- `_push_feuern` checks stopped/restore-ready/active pause before recompute and
  again after awaiting it; pause generation blocks a stale callback even if the
  user immediately resumes. Timer rearming and future normal announcements stay.
- Shared notification sender unchanged: safety alerts, explicit test pushes and
  pause-expiry reminders remain available while paused.
-9new notification regressions +12pause +19score tests pass locally. CI runs the
  same9tests with the complete controller imported in pinned HA2026.9.2, plus the
  existing cancellation-race test, hassfest and HACS validation.
- No production valve action or HA restart is needed for publishing this patch.
  Installed HA instances still need the HACS update/reload workflow.
- Parent Stäfa YAML already gates its plan push on `not veto_vacation`; do not
  migrate that setup to this integration as part of this notification fix.
