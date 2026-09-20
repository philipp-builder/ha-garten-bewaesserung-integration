# Garten-Bewässerung integration

This is the independent public HACS repository, not the parent HA configuration.
Keep credentials, private device data and deployment inventories out of it.

- Preserve watering safety gates; test with synthetic services/valves only.
- Active pauses suppress routine plan announcements, not safety notifications,
  test notifications or pause-expiry reminders. A selected reason alone is not
  an active pause. Recheck pause state/generation after awaited forecast work.
- Run `tests/test_score.py`, `tests/test_pause.py` and
  `tests/test_plan_notifications.py` without installing packages. CI additionally
  runs the complete controller import and cancellation race in pinned HA2026.9.2,
  plus hassfest/HACS validation.
- Update manifest version, README and replace HANDOFF.md (under40lines) for
  releases. Push reviewed changes, wait for exact-commit CI, then publish the
  matching patch release. Verify remote HEAD and a clean worktree.
- Publishing a HACS release is not proof it is installed in anyone's HA.
