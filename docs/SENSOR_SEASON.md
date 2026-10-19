# Sensor-Saison: Sicherheit und Betrieb

Version 1.10.0. Name: **Garten-Bewässerung — Score Irrigation**.
Domain, Repository, Geräte- und bestehende Entity-Unique-IDs bleiben unverändert.

## Zwei unabhängige Schichten

Bewässerungspause sperrt Wasserbefehle und Routine-Plan-/Trockenmeldungen.
Sensorbetrieb bestimmt, welche Bodenwerte überhaupt verwendet werden dürfen.
„Automatisch (Winterpause)“ folgt ausschließlich `pause.active` **und** dem
Grund Winterpause. Nur den Grund auszuwählen reicht nicht. Ein aktiver
Sensor-Override hebt niemals die Bewässerungspause auf.

Garden defaults and per-zone overrides are persisted in the existing version-1
Store under the additive `soil` key. Missing key migrates to automatic/inherit;
malformed policy becomes a visible fault with watering blocked. No database or
counter migration. A deliberate valid UI change repairs a malformed policy.

An optional timezone-aware deadline is valid only for explicitly stored sensors.
It is processed once, including when HA was offline at expiry. Expiry selects
Active, requires new reports and only rearms future watering slots. Irrigation's
own pause/end date is unchanged. Zone inheritance uses the garden deadline;
a zone-specific deadline requires selecting Stored on that zone first.

## Freshness and incomplete data

- A fresh observation is HA `last_reported`, strictly after controller startup or
  the zone's last policy transition, and at most 24 hours old. Not `last_changed`.
- Identical newly reported readings qualify through a filtered `state_reported`
  listener; changed readings use `state_changed`. No extra hardware/cloud polling.
- HA restore placeholders, disabled registry entries, missing/nonfinite/out-of-range
  values are rejected. All configured sources must be valid; a missing wet sensor
  must not silently disappear from a multi-sensor safety decision.
- This cannot prove a physical measurement time if an upstream integration
  republishes its own cache as a new HA report. No promise of radio-level freshness.
- Restart intentionally waits for a new report even for previously active sensors.
  Configure reliable reporting; a sensor that does not report within 24 hours
  requires investigation, not invented values. No stale value enters the score.
- Sensorless lawns retain their existing weather calculation. Configured-but-missing
  or stored soil sources block by default; weather-only fallback requires explicit
  per-lawn opt-in. Pots, including manual doses, require eligible soil readings.

## Concurrency and safety

Policy changes invalidate a per-zone generation before awaiting Store I/O. Queued
plans/doses cannot reopen after rapid pause/resume. Active affected valves are
closed with existing bounded retries; an unconfirmed close produces a safety
push. An in-flight open command is checked again after it returns and closed if
the policy changed. Other zones retain their own generations/settings. The main
run may finish its current wait before advancing; there is no immediate catch-up.
Leak/supply/watchdog/valve-close handling is never season-disabled. A battery
warning is suppressed only for a known soil device whose configured consumers
are all stored, and never when that device also owns a valve.

## UI and external monitoring

Native select/date/switch/status entities live on the existing Garden and zone
devices; add these through HA's normal dashboard editor. No custom card dependency.
The separate status stays readable while numerical moisture is unknown. Its
`status` attribute is one of `aktiv`, `eingelagert`, `wartet_auf_messwert`, `fehler`,
`ohne_sensor`. Only healthy explicit/effective storage makes `monitoring_expected`
false. `source_entities` identifies exact configured sources; shared sources need
all-consumer checks. Faults and waiting-for-new-reading remain monitorable.

This integration does not disable upstream entities, erase their history, alter
other integrations' Recorder/health settings, or change a separate private YAML
installation. It contains no adaptive learning model; actual water counters and
run history are retained. Never reconstruct watering from deliberately invalid
soil values or relabel stored values as zero.

## Validation / release

Run the stdlib score, pause, plan-notification, soil-policy and soil-controller
tests. CI repeats notification/controller tests with the full pinned HA import,
checks native entities, the prior pause race, hassfest and HACS validation.
All services/valves in tests are synthetic. Publish only after exact-commit CI.
Installing/updating and restarting the target HA is a separate operator action;
publication does not prove installation on any household's server.
