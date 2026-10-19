# Handoff — 2026-10-19
## v1.10.1: newcomer-first HACS description
- README now leads with purpose, supported hardware/limits, installation and the first circuit; operation/safety/support follow. No unproven water-saving, learning or cloud-independence claims.
- Detailed existing winter controls preserved in docs/PAUSES.md; release/migration notes are below the introduction. INSTALLATION.md agrees with standard-catalog installation and current notification selection.
- Description uses absolute public PNG/repository links. Existing component brand/icon.png (256) and icon@2x.png (512) are correct and byte-identical to assets; not newly added or a missing-package fix.
- Public HACS repositories.json now contains philipp-builder/ha-garten-bewaesserung-integration. Earlier October19 catalog-delay findings are superseded.
- HACS issue5402 maintainer says store-icon fix ships with Marketplace in HA2026.11. Legacy HACS may still show its placeholder; no household HACS patch or early HA upgrade. This is separate from the README image.
- HACS reads version-specific README (installed version if installed, latest otherwise); v1.10.1 is a documentation-only patch, manifest version change only inside runtime component. Never rewrite v1.10.0.
- Four listing checks plus70existing local tests pass. CI also validates full HA runtime, hassfest and HACS. Publish only after exact-commit green, then verify release/tag/remote parity.
- Private authenticated HACS page could not be opened with the web tool; do not claim a live browser/readback check. Public source/catalog and asset packaging were checked.
## v1.10.0 behavior retained
- Approved name Garten-Bewässerung — Score Irrigation; domain/repo/entity/device IDs unchanged. v1.10.0 released from9bcad60, CI39222491958 passed.
- All active irrigation pauses suppress routine plan/dry reports, not safety/test/expiry notices. Reason selection alone is not an active pause.
- Independent persisted global/per-zone soil season/end dates. Automatic follows ACTIVE winter only; fresh valid HA reports after startup/resume, unchanged-value reports count. HA report time is not proven physical measurement time.
- No imaginary50% soil; explicit lawn-only weather opt-in, pots never blind. Per-zone generations fence stale work/in-flight opens; close retries/alarms remain. Exact health metadata, no upstream registry disabling or adaptive learning.
- Details: docs/SENSOR_SEASON.md and docs/PAUSES.md. Public integration does not change the separate Stäfa YAML setup.
- No production deployment/restart, valve commands, notifications or credential access in this listing task. Source release != installed household update.
