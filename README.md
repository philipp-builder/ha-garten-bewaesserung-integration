<!--
  README.md — HACS-Integration `garten_bewaesserung`
  Die Ein-Klick-Edition des Garten-Bewässerungs-Kits.
  Lizenz: MIT · Stand: 2026-07
-->

# Garten-Bewässerung — Home-Assistant-Integration (HACS)

**Score-basierte Gartenbewässerung als Custom Integration: Setup-Wizard statt YAML,
beliebig viele Kreise, erklärbare Entscheidungen, fünfschichtiges Sicherheitsnetz.**

> 🌐 **[Landing Page (English) →](https://philipp-builder.github.io/ha-garten-bewaesserung/)** · 🧩 **Blueprint-Edition** (gleiche Logik als 12 Blueprints + Package, „gläserne Werkstatt"): [ha-garten-bewaesserung](https://github.com/philipp-builder/ha-garten-bewaesserung)

Die Integration berechnet für jeden Bewässerungskreis alle 30 Minuten einen
**Score (0–100)** aus Bodenfeuchte, Temperatur-Vorhersage und „Tagen seit letzter
Bewässerung", leitet daraus die heutige Dauer ab und führt sie abends aus —
sequenziell oder parallel, mit Dauer-Snapshot, Retry-Schließen, Safety-Sweep,
Auto-Aus-Backstop, Ventil-Watchdog und Neustart-Recovery. Töpfe werden tagsüber
mit kleinen Dosen im Soll-Feuchteband gehalten. Jede Entscheidung steht als
Klartext-Satz im Status-Sensor.

- **Home Assistant:** ≥ 2025.8
- **Sprache:** Deutsch (Entities + Dialoge; Setup-Dialoge auch Englisch)
- **Abhängigkeiten:** keine (`requirements: []`, keine Cloud)
- **Lizenz:** [MIT](LICENSE)

## Installation

1. HACS → ⋮ → **Benutzerdefinierte Repositories** →
   `https://github.com/philipp-builder/ha-garten-bewaesserung-integration`, Typ **Integration**.
2. „Garten-Bewässerung" installieren, Home Assistant neu starten.
3. Einstellungen → Geräte & Dienste → **Integration hinzufügen** → „Garten-Bewässerung"
   → Wetter-Entität wählen — fertig. Kreise, Sensoren und Tuning: Zahnrad → Options-Dialog.

**Ausführliche Anleitung, Entity-Referenz und Migration von der Blueprint-Edition:**
[docs/INSTALLATION.md](docs/INSTALLATION.md) · Architektur/Design-Entscheidungen:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Qualität

Portiert aus einem produktiven 4-Kreis-System (mehrere Saisons Dauereinsatz), dann:

- **13 Formel-Paritätstests** gegen die Original-Zahlen (`tests/test_score.py`, laufen in der CI ohne Abhängigkeiten)
- **E2E-Harness** (`tests/e2e/`): ephemere HA im Docker — Onboarding → Config-Flow →
  Kreis-CRUD → Score-Parität → Executor → Not-Aus → Container-Restart-Recovery →
  Topf-Dosen → Volumen/Kosten → Services, alles mit exakten Erwartungswerten
- **Adversariale Review-Runde:** 8 Findings (Schwerpunkt Reload-Lebenszyklus), alle gefixt und regressionsgetestet

## Automations-API

Services: `garten_bewaesserung.jetzt_bewaessern` · `.not_aus` · `.plan_neu_berechnen` ·
`.dosis_geben` (Feld `kreis`). Events: `garten_bewaesserung_lauf_gestartet` /
`_lauf_beendet` / `_notaus`.
