# Architektur: HACS-Integration `garten_bewaesserung` (v1.0)

Verbindliche Spec für die Portierung der Blueprint-Edition nach Python.
**Referenz-Verhalten = die 12 Blueprints der
[Blueprint-Edition](https://github.com/philipp-builder/ha-garten-bewaesserung-blueprint)**
(adversarial verifiziert, 2026-07). Jede bewusste Abweichung steht in diesem
Dokument — alles andere ist Parität. Leitentscheidungen, die sich in der
Umsetzung als falsch herausstellten, sind unter „Umsetzungs-Entscheidungen“
korrigiert — die Korrektur gilt.

## Leitentscheidungen (opinionated, entschieden 2026-07-17)

1. **Ein Config-Entry („Hub"), Kreise in `entry.options`.** Kein Entry-pro-Kreis,
   keine Subentry-API. Options-Flow verwaltet die Kreisliste (add/edit/remove)
   über ein Menü. (HA-Minimum wurde in der Umsetzung 2025.8 — siehe unten.)
2. **Controller statt DataUpdateCoordinator.** Wir pollen keine externe API —
   wir orchestrieren. Ein zentrales `GartenController`-Objekt pro Entry besitzt
   Scheduler, Executor-Task, Watchdog und Zustand. Coordinator-Pattern wäre
   Formzwang ohne Nutzen.
3. **Punktgenaue Timer statt Fenster-Mathematik.** Der Blueprint-Ansatz
   (time_pattern + Toleranzfenster) war ein YAML-Workaround. In Python:
   `async_track_point_in_time` für Plan-Push (Zeit − Vorlauf) und Lauf-Start,
   re-armiert bei Änderung der `time`-Entity und um Mitternacht. Damit
   entfallen die Fenster-Randfälle (:15/:45, Mitternachts-Wrap) strukturell.
4. **Score-Berechnung bleibt zum :00/:30-Raster** (Parität + Dashboards zeigen
   dieselben Rhythmen wie die Blueprint-Edition), zusätzlich sofort bei
   Options-Änderung und HA-Start.
5. **stdlib-only.** `manifest.json` → `requirements: []`. Wetter via
   `weather.get_forecasts`-Service-Call, alles andere HA-Bordmittel.
6. **Ein Device pro Kreis + ein Hub-Device.** Saubere Geräteseiten; die
   object_ids (`garten_<slug>_score`) entstehen über kurze Device-Namen
   („Garten“/„Garten <Name>“) — siehe Umsetzungs-Entscheidungen.
7. **Namen/UI:** Setup-Dialoge zweisprachig (`strings.json` + `translations/`),
   Entity-Namen deutsch via `_attr_name` (has_entity_name = True; KEINE
   translation_keys — Begründung unten).
8. **Events + Services als Erweiterungspunkte**, damit Nutzer weiterhin eigene
   YAML-Automationen andocken können (Philosophie der Blueprint-Edition bleibt
   zugänglich): Events `garten_bewaesserung_lauf_gestartet/_beendet/_notaus`,
   Services `jetzt_bewaessern`, `not_aus`, `dosis_geben`, `plan_neu_berechnen`.

## Datenmodell

```
entry.data:    { }                        # nichts Unveränderliches — alles in options
entry.options: {
  "wetter": "weather.xyz",                # Pflicht
  "regen_sensor": "" ,                    # optional, 24h-mm-Kontrakt wie Kit
  "strahlung_sensor": "",                 # optional
  "notify_dienste": ["notify.mobile_app_a", ...],
  "push_kritisch_alarme": true,
  "dashboard_pfad": "",
  "bewaesserungszeit": "21:00:00",        # einzige Wahrheit; time-Entity = Write-Through-Sicht
  "vorlauf_min": 30,
  "standard_dauer": 10,
  "regen_beobachtet_mm": 3.0, "regen_forecast_mm": 1.5,
  "strahlung_schwelle": 600,
  "topf": {"max_dosen": 4, "dosis_max_min": 4, "min_intervall_min": 90, "glitch_grenze": 5},
  "score": {"gewicht_boden": 60, "gewicht_temp": 20, "gewicht_tage": 20,
             "skip_schwelle": 25, "temp_anker": 15, "temp_spanne": 15,
             "tage_saettigung": 7, "forecast_typ": "daily",
             "temp_quelle": "tmax", "et0_anker": 2.0, "et0_spanne": 5.0},
  "notaus_minuten": 40,
  "retry": {"anzahl": 5, "abstand_s": 3},
  "wasser_tarif": 3.0, "waehrung": "EUR",
  "kreise": [ {
      "id": "rasen",                      # slug, stabil (Entity-IDs!)
      "name": "Rasen",
      "typ": "rasen" | "topf",
      "ventile": ["switch.a", "switch.b"],# 1..n; >1 = sequenzielle Gruppe IM Kreis
      "bodensensoren": ["sensor.x"],      # 0..n; min()-Aggregation
      "gruppe_reihenfolge": 1,            # Kreise mit gleicher Startzeit: Ordnung
      "parallel": true,                   # false = wartet auf vorherige Kreise
      "veto_schwelle": 70, "min_dauer": 5, "max_dauer": 20,
      "ziel_unten": 50, "ziel_oben": 70, "k_faktor": 2.0,   # topf-only
      "flow_sensor": "", "leck_sensoren": [], "versorgung_sensor": "",
      "batterie_sensoren": []
  } ]
}
```

**Abweichung ggü. Kit:** Ein Kreis kann MEHRERE Ventile haben (West+Ost =
ein Rasen-Kreis mit 2 Ventilen — das Kit brauchte dafür geteilte Helper +
Executor-Slots). `parallel: false` bildet „nach der vorherigen Gruppe" ab.

## Entity-Modell

Hub-Device „Garten" *(kurz — HA leitet die object_id aus „<Device> <Entity>" ab;
`suggested_object_id` ist im Core nicht setzbar. IDs unten = tatsächliche
HA-Slugs, ü→u/ä→a)*:
- `time.garten_bewasserungszeit` (RestoreEntity)
- `switch.garten_heute_uberspringen` / `_urlaubsmodus` / `_boost_modus` / `_topf_frequenzbewasserung`
- `button.garten_not_aus`, `button.garten_sofort_start`, `button.garten_plan_neu_berechnen`
- `number.garten_standard_dauer_auto_aus`, `_regen_veto_beobachtet`, `_regen_veto_vorhersage`, `_peak_sonnen_sperre`, `_wassertarif_pro_m3`
- `sensor.garten_nachster_lauf` (timestamp), `sensor.garten_letzter_lauf` (Bericht)

Pro Kreis-Device „Garten <Name>":
- `sensor.garten_<id>_score` (attrs: boden/temp/tage-Faktoren, Vetos, Rohwerte)
- `sensor.garten_<id>_status` (der erklärende Satz — Herzstück der Diagnose)
- `number.garten_<id>_dauer_heute` (Engine schreibt, Nutzer darf überschreiben)
- `number.garten_<id>_veto_schwelle_boden` / `_min_dauer` / `_max_dauer`
- topf: `number.garten_<id>_sollband_unten` / `_sollband_oben` / `_dosis_antwort_k`, `sensor.garten_<id>_dosen_heute`
- `sensor.garten_<id>_zuletzt_bewassert` (timestamp; Stempel bei JEDEM Ventil on→off — B9-Semantik)
- `switch.garten_<id>_aktiv` (Kreis pausieren, neu ggü. Kit)
- flow konfiguriert: `sensor.garten_<id>_liter_heute` / `_liter_monat` / `_kosten_monat`

**Umsetzungs-Entscheidungen (nach E2E, verbindlich):**
1. `OptionsFlowWithReload` statt update_listener — der Listener-Pfad verlor im
   E2E das Race gegen den Plattform-Erstimport (⇒ HA-Minimum 2025.8).
2. KEINE translation_keys für Entity-NAMEN: der Core leitet object_ids aus einer
   festen Übersetzung ab — das würde die dokumentierten deutschen IDs brechen.
   Namen bleiben deutsch via `_attr_name` (Flows sind DE+EN übersetzt).
3. Dispatcher-Handler der Entities MUSS `@callback` sein (sonst Executor-Thread).
4. `_letzte_dose` (Topf-Gate ⑤) wird im Store persistiert — das Kit bekommt
   Neustart-Festigkeit von `last_triggered` geschenkt, Python nicht.
5. Trocken-Report-Schwelle = halbe Veto-Schwelle des Kreises (das Kit hat
   Pro-Pflanze-Inputs; die Integration leitet ab statt zu fragen).

Tuning-Werte: `entry.options` ist die EINZIGE Wahrheit — Konfig-Numbers und
die Zeit-Entity lesen daraus und schreiben Änderungen zurück (Write-Through,
kein RestoreEntity; das hätte Options-Dialog-Edits nach dem Reload mit dem
Alt-Zustand überschrieben — Review-Finding F3). Nur die Engine-geschriebene
Tagesdauer je Kreis ist eine RestoreNumber.
**Regel:** Engine liest zur Laufzeit die Entities; statische Konfiguration
(Kreise, Sensoren, Notify) kommt aus den options.

## Controller (Engine)

```
GartenController
├─ scheduler:  :00/:30 Score-Recompute · Push-Timer (Zeit−Vorlauf) ·
│              Lauf-Timer (Zeit) · 00:01 Tagesreset · Report-Timer
├─ executor:   run() als asyncio.Task
│              Reihenfolge: Kreise sortiert (gruppe_reihenfolge); parallel-
│              Kreise als eigene Tasks. Pro Ventil: on → sleep(dauer) →
│              retry_close(). Dauer-SNAPSHOT bei Lauf-Start (B3-Parität).
│              cancel() bei Not-Aus/Skip → Safety-Sweep in finally-Block.
├─ watchdog:   pro Ventil-on einen Timer (notaus_minuten) — kein for:-Trigger-
│              Re-Arm-Problem; dazu B4-Auto-Aus (Standard-Dauer) für Öffnungen
│              außerhalb eines Laufs; Startup-Sweep nach Verfügbarkeits-
│              Wartefenster (bis 120 s, B5) schließt verwaiste Ventile.
├─ sitzung:    state-Listener auf alle Ventile: on→off stempelt
│              zuletzt_bewaessert + Volumen-Delta (30 s Settle) — B9.
├─ topf:       pro Topf-Kreis Soll-Band-Loop (alle 30 min + Unterschreitungs-
│              Listener), 9 Gates exakt wie B6, Dosis geklemmt.
├─ alarme:     Leck (to on), Versorgung (off ≥1 min + Ventil an + HA-Kontext),
│              Batterie (< Schwelle 30 min, 1 Push/Tag), Trocken-Report (Zeit,
│              Dämpfer via zuletzt_bewaessert) — B7/B8/B10/B12.
└─ store:      Store('garten_bewaesserung/<entry>.json'):
               {lauf_aktiv, dosen, liter_heute, liter_monat, letzte_dose,
               datum, monat} → Restart-Recovery beim Start: lauf_aktiv==true
               (oder echter HA-Boot) ⇒ offene Ventile retry-schließen + Push.
```

**Score-Formel: 1:1 aus B1** inkl. aller Fallbacks (Sensor unavailable ⇒ 50 %,
Wetterfehler ⇒ Tmax 20 °C + Statushinweis, keine Sensoren ⇒ Renormalisierung,
Aggressiv ⇒ 100 nach Skip/Urlaub, Vetos erzwingen Dauer 0 unabhängig von der
Skip-Schwelle). Die Zahlenbeispiele aus der Kit-Verifikation sind die Unit-Tests.

**ET₀-Erweiterung (v1.1.0, über B1 hinaus):** Der Temperatur-Faktor kann per
Tuning-Option `temp_quelle: et0` statt aus Tmax aus der Referenz-Verdunstung
nach **Hargreaves-Samani** gespeist werden — Ra aus Breitengrad + Kalendertag
(FAO-56 Gl. 21–25, gegen das FAO-Ra-Beispiel validiert), Tmax/Tmin je
Vorhersagetag (daily: `templow`; hourly: 24-h-Blöcke), gemittelt über bis zu
3 Tage. Anker/Spanne (Default 2/5 mm ⇒ Faktor 100 bei 7 mm/Tag) analog zum
Tmax-Paar. Ohne `templow`/Wetter fällt der Faktor still auf den Tmax-Pfad
zurück (`faktoren.temp_quelle` zeigt den aktiven Pfad); der berechnete
ET₀-Wert ist immer in `sensor.garten_plan_heute` (`et0_mm`) sichtbar.

## Dateien

```
custom_components/garten_bewaesserung/
├─ __init__.py          # setup/unload, Store, Recovery, Service-Registrierung
├─ manifest.json        # version, config_flow, iot_class: calculated, req: []
├─ const.py             # Domain, Defaults (= Kit-Seed-Werte), Options-Keys
├─ config_flow.py       # Setup-Wizard + OptionsFlow (Menü, Kreis-CRUD)
├─ controller.py        # GartenController (Scheduler/Executor/Watchdog/Alarme)
├─ score.py             # reine Funktionen: Score/Dauer/Status (testbar ohne HA)
├─ entity.py            # Basisklassen, Device-Zuordnung
├─ sensor.py / number.py / switch.py / button.py / time.py
├─ services.yaml
├─ strings.json + translations/de.json + translations/en.json
tests/
├─ test_score.py        # Formel-Parität (Kit-Zahlenbeispiele), läuft ohne HA
├─ e2e/                 # ephemere HA im Docker: Flows, Engine, Executor,
│                       # Not-Aus, Restart-Recovery, Töpfe, Volumen, Services
```

## Nicht-Ziele v1.0
Kein Auto-Dashboard (Beispiel-YAML in docs), keine Subentries, kein
HACS-Default-Store (Custom-Repo), kein learned-k (bleibt Addon-Doc; k ist
number-Entity pro Topf), keine Zonen-/Anwesenheits-Gates (wie Kit).
