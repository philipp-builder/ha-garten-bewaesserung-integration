<!--
  INSTALLATION.md — Integration `garten_bewaesserung`: Installation, Bedienung,
  Entity-Referenz.
  Lizenz: MIT · Stand: 2026-07
-->

# Integration `garten_bewaesserung` — Installation & Bedienung

Score-basierte Bewässerung als Config-Flow: erprobte Formel, robuster
Executor, mehrschichtiges Sicherheitsnetz — mit **beliebig vielen Kreisen**
und punktgenauen Timern.

- **Home Assistant:** ≥ 2025.8.0
- **Sprache:** Deutsch (bewusst — wie das Kit; die Setup-Dialoge gibt es auch auf Englisch)
- **Abhängigkeiten:** keine (`requirements: []`, keine Cloud)

## Installation (HACS)

1. HACS → ⋮ → **Benutzerdefinierte Repositories** → URL
   `https://github.com/philipp-builder/ha-garten-bewaesserung-integration`, Typ **Integration** → hinzufügen.
2. In HACS nach **„Garten-Bewässerung"** suchen → öffnen → **„Herunterladen"** klicken.
   Das Hinzufügen des Repositories allein installiert noch nichts — und wer vor dem
   Download neu startet, findet das Custom-Repository danach nicht mehr in HACS
   (HACS entfernt beim Start alle nicht heruntergeladenen Custom-Repositories).
3. Sobald HACS „Neustart erforderlich" meldet: Home Assistant neu starten.
4. Einstellungen → Geräte & Dienste → **Integration hinzufügen** → „Garten-Bewässerung".
5. Im Wizard die **Wetter-Entität** wählen (beliebige `weather.*` mit Vorhersage) — fertig.

Alles Weitere passiert im **Options-Dialog** der Integration (Zahnrad am Hub-Eintrag):

| Menüpunkt | Inhalt |
|---|---|
| Globale Einstellungen | Wetter-Entität · optional eigener **Regen-24h-Sensor** (mm, beobachtet) · optional **Globalstrahlungs-Sensor** (Peak-Sonnen-Sperre) |
| Benachrichtigungen | notify-Dienste (Komma-Liste) · kritische Pushes · Dashboard-Deep-Link |
| Tuning | in einklappbaren Sektionen mit Erklärtext unter jedem Feld: Score-Gewichte & Schwellen · Temperatur & Verdunstung (Quelle **Tmax oder ET₀ nach Hargreaves** — Sonnenstand aus Breitengrad + Tmax/Tmin der Vorhersage, keine Extra-Sensoren; besonders für Rasen interessant) · Regen & Sonne · Topf-Parameter · Wasserkosten. Der aktuelle ET₀-Wert steht vorab in den Attributen von `sensor.garten_plan_heute` |
| Kreis hinzufügen / bearbeiten / entfernen | Name, Typ (Rasen/Beet oder Topf/Tropf — auch nachträglich änderbar; typ-spezifische Entities wie Sollband/Dosen erscheinen bzw. verschwinden dabei automatisch), **1–n Ventile**, 0–n Bodensensoren, Reihenfolge, Ausführung (sequenziell · parallel ab Laufbeginn · **parallel ab Reihenfolge-Position** — koppelt z. B. einen Tropfkreis an den zweiten Sprenger der Kette), Dauer-Grenzen, **Temperatur-Quelle je Kreis** (wie global / Tmax / ET₀), Sollband + k (Topf), optional Wasserzähler- (kumulativ, m³/L — FAQ 17!) /Leck-/Versorgungs-/Batterie-Sensoren |

Nach jedem Speichern lädt die Integration automatisch neu — neue Kreis-Entities
erscheinen sofort.

## Was die Engine tut (Kurzfassung)

- **:00/:30** — Score & Tagesdauer je Kreis neu berechnen (Formel = Kit-B1, inkl.
  aller Vetos und Fallbacks). Der **Status-Sensor** erklärt jede Entscheidung im Klartext.
- **Bewässerungszeit − 30 min** — Tagesplan-Push (unterdrückt bei „Heute überspringen").
- **Bewässerungszeit** — Lauf: Kreise in Gruppen-Reihenfolge, `parallel`-Kreise
  gleichzeitig; pro Ventil öffnen → Dauer → Retry-Schließen; Safety-Sweep am Ende;
  Dauer-Snapshot beim Start.
- **Töpfe tagsüber** — Soll-Band-Dosen mit den 9 Kit-Gates (Master-Schalter, Glitch-Schutz,
  Peak-Sonne, Tageslimit, Mindestabstand, Skip, Urlaub, Regen, Ventil zu).
- **Sicherheitsnetz** — Watchdog schließt jedes Ventil, das länger als die Notaus-Zeit
  offen ist (egal wer es geöffnet hat); nach einem HA-Neustart werden verwaiste offene
  Ventile sofort zwangsgeschlossen; Not-Aus-Button bricht alles ab.
- **08:00** — Trocken-Report: Kreise, deren Boden trotz Automatik kritisch trocken ist
  (unter der **halben Veto-Schwelle**, gedämpft wenn in den letzten 24 h bewässert wurde).
- **Alarme** — Leck (sofort), Wasserversorgung weg (≥ 1 min, nur wenn das Ventil per HA
  geöffnet wurde), Batterie < 20 % (max. 1 Push/Tag).

## Entity-Referenz

Hub-Gerät **„Garten"**:

| Entity | Zweck |
|---|---|
| `time.garten_bewasserungszeit` | tägliche Startzeit (Timer werden live umgeplant) |
| `switch.garten_heute_uberspringen` | heute nicht bewässern (00:01 Auto-Reset) |
| `switch.garten_urlaubsmodus` / `switch.garten_boost_modus` | dauerhaft aus / Score 100 |
| `switch.garten_topf_frequenzbewasserung` | Master-Schalter der Topf-Dosen |
| `button.garten_sofort_start` / `button.garten_not_aus` / `button.garten_plan_neu_berechnen` | Manuell-Start · alles zu · sofort neu rechnen |
| `number.garten_standard_dauer_auto_aus`, `number.garten_regen_veto_*`, `number.garten_peak_sonnen_sperre`, `number.garten_wassertarif_pro_m3` | globale Regler |
| `sensor.garten_nachster_lauf` / `sensor.garten_letzter_lauf` | nächster geplanter Lauf · Bericht des letzten Laufs |
| `calendar.garten_kalender` | Bewässerungskalender: geplanter Lauf + Historie der letzten 200 Läufe als Termine — einfach eine Kalender-Karte darauf zeigen lassen |
| `sensor.garten_plan_heute` | kompakte Tageszeile: `Tmax3d 26 °C · Regen 24h 0.4 mm + FC 1.5 mm · Rasen 42 % · Tomaten 38 % — berechnet 15:00` — Rohwerte (Wetter, Regen, pro Kreis Boden/Score/Dauer, Zeitstempel, verwendete `wetter_entity`) als Attribute — inkl. Glass-Box `regen_fc_datenbasis`: die exakt summierten Forecast-Zeilen hinter dem FC-Regenwert (hourly: 24 Stundenwerte, daily: der Tageseintrag) für Sekunden-Diagnose von Regen-Fragen |

Pro Kreis-Gerät **„Garten \<Name\>"** (Beispiel `rasen`):

| Entity | Zweck |
|---|---|
| `sensor.garten_rasen_score` | Score 0–100; Attribute = alle Faktoren & Vetos |
| `sensor.garten_rasen_status` | der erklärende Satz („Warum (nicht)?") |
| `number.garten_rasen_dauer_heute` | heutige Dauer — Engine schreibt, du darfst überschreiben |
| `number.garten_rasen_veto_schwelle_boden` / `_min_dauer` / `_max_dauer` | Kreis-Regler |
| `sensor.garten_rasen_zuletzt_bewassert` | Stempel bei JEDEM Ventil-Schließen |
| `sensor.garten_rasen_bodenfeuchte` | Engine-Sicht der Bodenfeuchte (Minimum über die Kreis-Sensoren) — nur bei konfigurierten Bodensensoren |
| `switch.garten_rasen_aktiv` | Kreis pausieren |
| Topf zusätzlich: `number.…_sollband_unten/oben`, `number.…_dosis_antwort_k`, `sensor.…_dosen_heute` | Soll-Band + Dosis-Zähler |
| mit Flow-Sensor: `sensor.…_liter_heute` / `_liter_monat` / `_kosten_monat` | Volumen & Kosten |
| mit Flow-Sensor: `sensor.…_liter_gesamt` | Lebenszeit-Zähler (`device_class: water`, `total_increasing`) — fürs Energie-Dashboard, siehe unten |

Zähler (Dosen, Liter) und der Mindestabstand überleben Neustarts (eigener Store).

**Energie-Dashboard (Wasser-Balken gratis):** Einstellungen → Dashboards →
Energie → **Wasserquelle hinzufügen** → pro Kreis `sensor.garten_<kreis>_liter_gesamt`
auswählen. HA zeichnet dann native Tages-/Wochen-/Monats-Balken deines
Gartenwassers — ohne eine einzige eigene Karte. (Braucht einen konfigurierten
Wasserzähler-Sensor am Kreis; die Balken beginnen ab dem Zeitpunkt der Einrichtung.)

**Falsch konfigurierter Wasserzähler?** Liefert der gewählte Sensor eine
Durchfluss-**Rate** (L/min, m³/h) statt eines kumulativen Zählerstands, erscheint
seit v1.4.0 automatisch eine Karte unter **Einstellungen → Reparaturen** mit dem
Rezept (Integral-Helfer, FAQ Frage 17). Sie verschwindet von selbst nach der
ersten gültigen Sitzung mit einem echten Zähler.

## FAQ / Rezepte

Sensor- und Hardware-Rezepte — Regen-24h-Sensor bauen, `valve.`-/`light.`-
Entities als Switch wrappen, Wetter-Sonderfälle: [FAQ](FAQ.md).

