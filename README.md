<!--
  README.md — HACS-Integration `garten_bewaesserung`
  Score-basierte Gartenbewässerung für Home Assistant.
  Lizenz: MIT · Stand: 2026-07
-->

<img src="assets/icon.svg" align="right" width="110" alt="Logo: Wassertropfen mit Setzling">

# Garten-Bewässerung — Home-Assistant-Integration

**Score-basierte Gartenbewässerung: Setup per Wizard, beliebig viele Kreise,
erklärbare Entscheidungen, mehrschichtiges Sicherheitsnetz gegen hängende Ventile.**

> 🌐 Landing Page: [Deutsch](https://philipp-builder.github.io/ha-garten-bewaesserung-integration/de/) · [English](https://philipp-builder.github.io/ha-garten-bewaesserung-integration/)

Die Integration berechnet für jeden Bewässerungskreis alle 30 Minuten einen
**Score (0–100)** aus Bodenfeuchte, Temperatur-Vorhersage und „Tagen seit letzter
Bewässerung", leitet daraus die heutige Bewässerungsdauer ab und führt sie zur
eingestellten Zeit automatisch aus. Regen — gemessen oder vorhergesagt — setzt aus.

- **Home Assistant:** ≥ 2025.8
- **Sprache:** Deutsch (Entities + Dialoge; Setup-Dialoge auch Englisch)
- **Abhängigkeiten:** keine (keine Cloud, `requirements: []`)
- **Lizenz:** [MIT](LICENSE)

## Funktionen

- **Score statt Zeitplan** — gewichtete Formel aus Boden-Trockenheit,
  Vorhersage-Tmax und Durst-Tagen; Vetos für gemessenen und vorhergesagten Regen.
  Jeder Kreis hat einen **Status-Sensor mit Klartext-Begründung**
  („Score 72 → 16 min (Boden 42 %, Tmax 29 °C, nie bewässert)") und allen
  Score-Faktoren als Attributen.
- **Beliebig viele Kreise, komplett per UI** — anlegen, bearbeiten, löschen im
  Options-Dialog. Je Kreis 1–n Ventile, 0–n Bodenfeuchte-Sensoren, Ausführung
  sequenziell, parallel ab Laufbeginn oder an eine Ketten-Position gekoppelt
  (Tropfkreis startet z. B. erst mit dem zweiten Sprenger), eigene Dauer-Grenzen
  und Veto-Schwelle.
- **Topf-Frequenzbewässerung** — Topf-Kreise erhalten tagsüber kleine Dosen, die
  die Bodenfeuchte in einem Soll-Band halten; Dosisgröße aus einer einstellbaren
  Dosis-Antwort-Konstante, abgesichert durch neun Gates (u. a. Peak-Sonnen-Sperre,
  Tageslimit, Mindestabstand, Regen-Veto).
- **Sicherheitsnetz** — jeder Schließbefehl mit Wiederhol-Versuchen; Safety-Sweep
  nach jedem Lauf; Auto-Aus-Backstop für von Hand geöffnete Ventile; Watchdog
  schließt jedes Ventil, das länger als die Notaus-Zeit offen ist; nach einem
  HA-Neustart werden verwaiste offene Ventile sofort zwangsgeschlossen;
  Not-Aus-Button für „alles sofort zu".
- **Benachrichtigungen** — Tagesplan-Push vor dem Lauf; Alarme für Wasserleck,
  fehlende Wasserversorgung und schwache Batterien; täglicher Report, wenn ein
  Kreis trotz Automatik kritisch trocken bleibt.
- **Wasser-Bilanz** — mit einem Flow-Sensor je Kreis: Liter pro Sitzung, Tag und
  Monat plus Monatskosten aus dem hinterlegten Wassertarif.
- **Modi** — Heute überspringen (Auto-Reset um Mitternacht), Urlaubsmodus,
  Boost-Modus (Score 100), Kreise einzeln pausierbar.
- **Plan-Übersicht** — `sensor.garten_plan_heute` fasst den Tagesplan in einer
  Zeile zusammen (Tmax 3 Tage, Regen gemessen + Vorhersage, Bodenfeuchte aller
  Kreise, Berechnungszeitpunkt); die Rohwerte liegen als Attribute bei.
- **Verdunstung statt nur Temperatur (optional)** — der Temperatur-Faktor kann
  auf **ET₀ nach Hargreaves** umgestellt werden: Referenz-Verdunstung aus
  Sonnenstand (Breitengrad + Kalendertag) und Tmax/Tmin der Vorhersage, ohne
  zusätzliche Sensoren. Fällt bei fehlenden Daten automatisch auf Tmax zurück —
  besonders für Rasenkreise ohne Bodensensor interessant — und pro Kreis
  übersteuerbar (z. B. nur der Rasen auf ET₀). Der Tuning-Dialog ist dafür in
  Sektionen mit Erklärtext unter jedem Feld gegliedert.

## Installation

1. HACS → ⋮ → **Benutzerdefinierte Repositories** →
   `https://github.com/philipp-builder/ha-garten-bewaesserung-integration`,
   Typ **Integration** → hinzufügen.
2. In HACS nach **„Garten-Bewässerung"** suchen → öffnen → **„Herunterladen"**
   klicken (das Hinzufügen des Repositories allein installiert noch nichts).
3. Sobald HACS „Neustart erforderlich" anzeigt: Home Assistant neu starten.
4. Einstellungen → Geräte & Dienste → **Integration hinzufügen** →
   „Garten-Bewässerung" → Wetter-Entität wählen (beliebige `weather.*` mit Vorhersage).

## Konfiguration

Alles Weitere über das Zahnrad am Integrations-Eintrag:

| Menüpunkt | Inhalt |
|---|---|
| Globale Einstellungen | Wetter-Entität · optional eigener Regen-24h-Sensor (mm) · optional Globalstrahlungs-Sensor (Peak-Sonnen-Sperre) |
| Benachrichtigungen | notify-Dienste · kritische Pushes · Dashboard-Deep-Link |
| Tuning | Score-Gewichte und -Parameter, Regen-Schwellen, Topf-Parameter, Wassertarif |
| Kreis hinzufügen/bearbeiten/entfernen | Name, Typ (Rasen/Beet oder Topf/Tropf), Ventile, Sensoren, Reihenfolge, Dauer-Grenzen, Sollband + k, optionale Flow-/Leck-/Versorgungs-/Batterie-Sensoren |

Startzeit, Dauer-Grenzen, Schwellen und Modi sind zusätzlich als Entities
(`time`, `number`, `switch`) direkt im Dashboard verstellbar.

**Vollständige Entity-Referenz und Migration von der Blueprint-Edition:**
[docs/INSTALLATION.md](docs/INSTALLATION.md) ·
Architektur: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) ·
Rezepte & Troubleshooting (Regen-24h-Sensor, Template-Switch für
`valve.`-Entities u. v. m.): [FAQ](docs/FAQ.md).

## Services & Events

| Service | Wirkung |
|---|---|
| `garten_bewaesserung.jetzt_bewaessern` | geplanten Lauf sofort starten (Skip/Urlaub gelten weiter) |
| `garten_bewaesserung.not_aus` | Lauf abbrechen, alle Ventile schließen |
| `garten_bewaesserung.plan_neu_berechnen` | Score/Dauer aller Kreise sofort neu berechnen |
| `garten_bewaesserung.dosis_geben` | sofortige Topf-Dose (Feld `kreis`) |

Events für eigene Automationen: `garten_bewaesserung_lauf_gestartet`,
`…_lauf_beendet`, `…_notaus`.

## Entwicklung & Tests

Die Score-Formel liegt HA-frei in `custom_components/garten_bewaesserung/score.py`;
`python3 tests/test_score.py` prüft sie ohne weitere Abhängigkeiten (läuft auch in
der CI, zusammen mit hassfest- und HACS-Validierung). `tests/e2e/` enthält einen
End-to-End-Test, der die Integration in einer ephemeren Home-Assistant-Instanz im
Docker durchspielt — vom Config-Flow über Läufe und Not-Aus bis zur
Neustart-Recovery.
