<!--
  README.md — HACS-Integration `garten_bewaesserung`
  Score-basierte Gartenbewässerung für Home Assistant.
  Lizenz: MIT · Stand: 2026-07
-->

<img src="assets/icon.svg" align="right" width="110" alt="Logo: Wassertropfen mit Setzling">

# Garten-Bewässerung — Home-Assistant-Integration

## Urlaub und Winterpause

Am Gerät **Garten** gibt es **Bewässerung pausieren**, **Pausengrund**,
**Pausenende**, **Pause mit Enddatum**, **Nach Pausenende** und **Pausenstatus**.
Ohne Enddatum gilt die Pause bis auf Widerruf. Für eine befristete Pause zuerst
das zukünftige Enddatum einstellen, dann „Pause mit Enddatum“ aktivieren.
Winterpause wählt standardmäßig **Nur erinnern**: Wasseranschluss und Schläuche
prüfen, danach manuell freigeben. „Automatisch fortsetzen“ ist ausdrücklich wählbar.

Die Pause wird gespeichert und übersteht Neustarts. Ein bereits laufender
Durchgang wird abgebrochen und alle Ventile werden mit Wiederholversuchen
geschlossen. Auch manuelle Sofortstarts und Topf-Dosen bleiben gesperrt.
Das Pausenende erzeugt eine HA-Mitteilung und die konfigurierten Pushes.
Während einer aktiven Pause entfallen die täglichen Garten-Plan-Ankündigungen
(seit v1.9.1). Sicherheitsalarme, Test-Pushes und Pausenende-Erinnerungen bleiben
aktiv. Nur den Pausengrund auszuwählen aktiviert noch keine Pause.
Freigabe startet keinen sofortigen Nachhol-Lauf; normale zukünftige Termine
und Topf-Prüfungen gelten wieder. Ein abgelaufenes Enddatum wird auch beim
Neustart verarbeitet. Fehlerhafte gespeicherte Pausendaten bleiben sicher gesperrt.

Bestehende Urlaubsmodus-Entity-IDs bleiben erhalten; ein eingeschalteter alter
Urlaubsmodus wird als unbefristete Pause übernommen. Neuinstallationen verwenden
den Anzeigenamen „Bewässerung pausieren“. Die Aktion
`garten_bewaesserung.pause_setzen` erlaubt dieselbe Einstellung atomar;
bei mehreren Gärten ist `entry_id` erforderlich. `ende` erwartet einen
ISO-Zeitpunkt mit Zeitzone. Ohne `ende` aktiviert die Aktion eine unbefristete Pause.

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
  Dosis-Antwort-Konstante, abgesichert durch elf Gates (u. a. Peak-Sonnen-Sperre,
  Nachtruhe, Tageslimit, Mindestabstand, Regen-Veto, Sensorbatterie).
  **Nachvollziehbar:** jede Dose landet als Termin im Bewässerungskalender, die
  heutigen Uhrzeiten stehen am Dosen-Zähler — und wenn gerade *nicht* dosiert
  wird, nennt das Attribut `warum_gerade_nicht` den Grund im Klartext
  („pralle Sonne (780 ≥ 600) — wird aufgeschoben"). Siehe FAQ 21.
- **Sicherheitsnetz** — jeder Schließbefehl mit Wiederhol-Versuchen; Safety-Sweep
  nach jedem Lauf; Auto-Aus-Backstop für von Hand geöffnete Ventile; Watchdog
  schließt jedes Ventil, das länger als die Notaus-Zeit offen ist; nach einem
  HA-Neustart werden verwaiste offene Ventile sofort zwangsgeschlossen;
  Not-Aus-Button für „alles sofort zu".
- **Benachrichtigungen** — Tagesplan-Push vor dem Lauf; Alarme für Wasserleck,
  fehlende Wasserversorgung und schwache Batterien; täglicher Report, wenn ein
  Kreis trotz Automatik kritisch trocken bleibt. **Überprüfbar:** die Dienste
  werden aus den auf deinem System registrierten notify-Diensten ausgewählt
  (keine Tippfehler möglich), ein Knopf schickt eine Test-Benachrichtigung und
  meldet das Ergebnis als Notiz *in* Home Assistant, und ein nicht mehr
  existierender Dienst erzeugt eine Reparatur-Karte. Siehe FAQ 22.
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

**Vollständige Entity-Referenz:**
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
