# Handoff — 2026-10-19
## v1.10.0: independent soil-sensor season
- Approved display name: Garten-Bewässerung — Score Irrigation. Domain/repository/existing entity and device IDs unchanged. No claim of exclusive trademark ownership.
- Root cause of winter morning alerts: v1.9.1 guarded plan pushes only; _trocken_report did not check active pause. Now all active irrigation pauses suppress routine dry reports too; safety/test/expiry notifications remain.
- Native global/per-zone select, date, timed switch and status. Default automatic follows ACTIVE irrigation Winterpause; zone default inherits garden. Active and Stored independent overrides, optional timezone-aware end date.
- Additive soil Store key; corruption visibly blocks, migration defaults automatic/inherit. End date selects Active, no immediate catch-up; startup/resume requires fresh valid HA reports (same-value reports count). All sources 0..100/finite/enabled/non-restored and <=24h. HA report age is not proven physical sample time.
- Central soil_reading/soil_allowed gates score, reports, auto/manual pots and final valve open. Missing configured lawn source no longer invents 50%; explicit per-lawn weather-only fallback available, never for pots. Intentionally sensorless lawns unchanged.
- Per-zone generations fence queued work and rapid pause/resume. Affected open valves closed with retries; in-flight open rechecked; failed close still alarms. Other zones retain settings/generations. Actual water counts/history retained; no adaptive learning engine here.
- Soil-device battery alerts suppressed only with proven identity and all configured consumers stored; valves/unknown device roles retain alerts. No registry disabling/Recorder changes to upstream entities.
- monitoring_expected/source_entities/status/fresh_after attributes support external health integration; no blanket suppression, and invalid policy remains a fault. This does not change a separate private YAML installation.
## Tests / publication
- Local stdlib: 19 score +12 pause +9 plan-notification +9 soil-policy +21 soil-controller tests. Same controller assertions run with full HA imports in CI, alongside existing pause race, 13 native season entity checks and real HA startup/unchanged-report/shutdown checks.
- Workflow also runs hassfest and HACS validation. Publish v1.10.0 only after exact-commit CI succeeds; never infer a passing AST unit suite proves HA setup.
- README and docs/SENSOR_SEASON.md document controls, behavior change, monitoring/freshness limits and safe release procedure.
- HACS default PR9343 merged October18; the subsequent generated public catalog was still delayed at the October19 investigation. Recheck catalog rather than assume a reinstall/HA restart fixes upstream generation.
- Public release != installed update. No production HA restart, watering, camera, mail or server deployment is part of this source release.
