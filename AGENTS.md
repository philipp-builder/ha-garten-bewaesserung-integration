# Garten-Bewässerung — Score Irrigation

This is the independent public HACS repository, not the parent HA configuration.
Keep credentials, private device data and deployment inventories out of it.

- Preserve watering safety gates; test with synthetic services/valves only.
- Active pauses suppress routine plan announcements AND daily dry reports, not safety notifications,
  test notifications or pause-expiry reminders. A selected reason alone is not
  an active pause. Recheck pause state/generation after awaited forecast work.
- Soil lifecycle is independent: automatic follows active winter only, zone
  overrides inherit by default, expiry/restart require fresh valid reports.
  `soil_reading`/`soil_allowed` are the common gates; never replace missing soil
  with 50/0 or silently enable weather fallback. Pots always require soil.
  Keep per-zone generation fencing across awaits and valve-close safety.
  Do not disable upstream entities; external health uses exact source/consumer
  scope and monitoring_expected, never a blanket unavailable exemption.
- Run `tests/test_score.py`, `tests/test_pause.py`, `tests/test_soil.py`,
  `tests/test_soil_controller.py` and `tests/test_plan_notifications.py` without installing packages. CI additionally
  runs the complete controller import and cancellation race in pinned HA2026.9.2,
  plus native sensor-season entities, full soil-controller tests and hassfest/HACS validation.
- Update manifest version, README and replace HANDOFF.md (under40lines) for
  releases. Push reviewed changes, wait for exact-commit CI, then publish the
  matching release. Verify remote HEAD and a clean worktree.
- Preserve domain, repository and existing entity/device unique IDs when changing
  branding. The approved display name is Garten-Bewässerung — Score Irrigation.
- Publishing a HACS release is not proof it is installed in anyone's HA.
