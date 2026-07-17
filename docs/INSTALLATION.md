<!--
  INSTALLATION.md — Integration `garten_bewaesserung`: Installation, Bedienung,
  Entity-Referenz, Migration vom Blueprint-Kit.
  Lizenz: MIT · Stand: 2026-07
-->

# Integration `garten_bewaesserung` — Installation & Bedienung

Die Integration ist die Ein-Klick-Edition des Bewässerungs-Kits: dieselbe
Score-Formel, derselbe Executor, dasselbe Sicherheitsnetz — aber als Config-Flow
statt Blueprints, mit **beliebig vielen Kreisen** und punktgenauen Timern.

- **Home Assistant:** ≥ 2025.8.0
- **Sprache:** Deutsch (bewusst — wie das Kit; die Setup-Dialoge gibt es auch auf Englisch)
- **Abhängigkeiten:** keine (`requirements: []`, keine Cloud)

## Installation (HACS)

1. HACS → ⋮ → **Benutzerdefinierte Repositories** → URL
   `https://github.com/philipp-builder/ha-garten-bewaesserung-integration`, Typ **Integration** → hinzufügen.
2. Die Integration **Garten-Bewässerung** installieren, Home Assistant neu starten.
3. Einstellungen → Geräte & Dienste → **Integration hinzufügen** → „Garten-Bewässerung".
4. Im Wizard die **Wetter-Entität** wählen (beliebige `weather.*` mit Vorhersage) — fertig.

Alles Weitere passiert im **Options-Dialog** der Integration (Zahnrad am Hub-Eintrag):

| Menüpunkt | Inhalt |
|---|---|
| Globale Einstellungen | Wetter-Entität · optional eigener **Regen-24h-Sensor** (mm, beobachtet) · optional **Globalstrahlungs-Sensor** (Peak-Sonnen-Sperre) |
| Benachrichtigungen | notify-Dienste (Komma-Liste) · kritische Pushes · Dashboard-Deep-Link |
| Tuning | alle Score-Parameter (Gewichte, Skip-Schwelle, Temperatur-Anker/-Spanne, Tage-Sättigung, daily/hourly), Regen-Schwellen, Topf-Parameter, Wassertarif |
| Kreis hinzufügen / bearbeiten / entfernen | Name, Typ (Rasen/Beet oder Topf/Tropf), **1–n Ventile**, 0–n Bodensensoren, Reihenfolge, parallel/sequenziell, Dauer-Grenzen, Sollband + k (Topf), optional Flow-/Leck-/Versorgungs-/Batterie-Sensoren |

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

Pro Kreis-Gerät **„Garten \<Name\>"** (Beispiel `rasen`):

| Entity | Zweck |
|---|---|
| `sensor.garten_rasen_score` | Score 0–100; Attribute = alle Faktoren & Vetos |
| `sensor.garten_rasen_status` | der erklärende Satz („Warum (nicht)?") |
| `number.garten_rasen_dauer_heute` | heutige Dauer — Engine schreibt, du darfst überschreiben |
| `number.garten_rasen_veto_schwelle_boden` / `_min_dauer` / `_max_dauer` | Kreis-Regler |
| `sensor.garten_rasen_zuletzt_bewassert` | Stempel bei JEDEM Ventil-Schließen |
| `switch.garten_rasen_aktiv` | Kreis pausieren |
| Topf zusätzlich: `number.…_sollband_unten/oben`, `number.…_dosis_antwort_k`, `sensor.…_dosen_heute` | Soll-Band + Dosis-Zähler |
| mit Flow-Sensor: `sensor.…_liter_heute` / `_liter_monat` / `_kosten_monat` | Volumen & Kosten |

Zähler (Dosen, Liter) und der Mindestabstand überleben Neustarts (eigener Store).

## FAQ / Rezepte

Die Sensor- und Hardware-Rezepte der Blueprint-Edition gelten unverändert —
Regen-24h-Sensor bauen, `valve.`-/`light.`-Entities als Switch wrappen,
Wetter-Sonderfälle: [FAQ im Kit-Repo](https://github.com/philipp-builder/ha-garten-bewaesserung-blueprint/blob/main/docs/FAQ.md).

## Migration vom Blueprint-Kit

1. **Blueprint-Automationen deaktivieren** (nicht löschen — Rollback bleibt möglich):
   alle Instanzen der 12 Kit-Blueprints auf „aus".
2. Integration installieren + Wizard durchlaufen; Kreise mit denselben Ventilen,
   Sensoren und Werten anlegen (Veto/Min/Max/Sollband/k aus deinen Package-Helfern
   ablesen).
3. Werte, die weiterlaufen sollen, übertragen: Bewässerungszeit (`time.…`),
   Tuning-Regler im Options-Dialog.
4. Eine Nacht parallel beobachten (Blueprints aus, Integration an) — der
   Status-Sensor je Kreis zeigt, was die Engine entscheidet.
5. Danach optional das Package (`packages/bewaesserung.yaml` aus dem [Kit-Repo](https://github.com/philipp-builder/ha-garten-bewaesserung-blueprint)) entfernen und die
   Dashboard-Karten auf die neuen Entity-IDs umstellen.

**Nicht migriert wird automatisch:** Historie der alten Helfer (andere Entity-IDs)
und der „zuletzt bewässert"-Stempel — er stempelt sich beim ersten Lauf neu
(bis dahin gilt der Kreis als „nie bewässert" = maximal durstig; das ist gewollt
konservativ in Richtung „einmal gießen").

## Rollback

Integration entfernen (Einstellungen → Geräte & Dienste), Blueprint-Automationen
wieder aktivieren. Das Package war nie weg — alles läuft wie vorher.
