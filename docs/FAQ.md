<!--
=============================================================================
FAQ.md — Häufige Fragen zur Garten-Bewässerungs-Integration (HACS)
-----------------------------------------------------------------------------
Zweck:  Antworten auf die häufigsten Installations-, Hardware- und
        Betriebsfragen, inklusive Copy-Paste-Rezepte (Template-Switch-Wrapper,
        Regen-24h-Sensor in 3 Varianten, notify-Gruppe, Webhook-Not-Aus,
        history_stats-Persistenz für den Trocken-Report).
Quelle: portiert aus einem produktiven 4-Kreis-System.
Lizenz: MIT · Stand: 2026-07 · Mindestversion Home Assistant: 2025.8
=============================================================================
-->

# FAQ — Garten-Bewässerung (HACS-Integration)

**Bevor du hier suchst:** Die Dialoge der Integration erklären jedes Feld
direkt darunter (Tuning, Kreis-Anlage, Globale Einstellungen), und
[INSTALLATION.md](INSTALLATION.md) enthält die komplette Entity-Referenz.
Diese FAQ deckt alles ab, was quer dazu liegt: Hardware-Sonderfälle,
Copy-Paste-Rezepte, Fehlersuche.

## Inhalt

1. [Welche Ventile funktionieren?](#1-welche-ventile-funktionieren)
2. [Mein Ventil ist eine `valve`- oder `light`-Entität — was nun? (Template-Switch-Rezept)](#2-mein-ventil-ist-eine-valve--oder-light-entität--was-nun-template-switch-rezept)
3. [Welche Bodenfeuchte-Sensoren brauche ich? Geht es auch ohne?](#3-welche-bodenfeuchte-sensoren-brauche-ich-geht-es-auch-ohne)
4. [Wie baue ich den Regen-24h-Sensor? (3 Rezepte je nach Quellsensor)](#4-wie-baue-ich-den-regen-24h-sensor-3-rezepte-je-nach-quellsensor)
5. [Meine Wetter-Integration liefert kein `daily` / keinen Niederschlag](#5-meine-wetter-integration-liefert-kein-daily--keinen-niederschlag)
6. [Wie finde ich den Namen meines notify-Dienstes?](#6-wie-finde-ich-den-namen-meines-notify-dienstes)
7. [Wie schicke ich Pushes an mehrere Handys? (notify-Gruppen-Rezept)](#7-wie-schicke-ich-pushes-an-mehrere-handys-notify-gruppen-rezept)
8. [„Warum bewässert er heute nicht?“](#8-warum-bewässert-er-heute-nicht)
9. [Ein Ventil ging nicht zu — was ist passiert, was tun?](#9-ein-ventil-ging-nicht-zu--was-ist-passiert-was-tun)
10. [Die Notaus-Schwelle und die Max-Dauern — welche Regel gilt? (Invariante)](#10-die-notaus-schwelle-und-die-max-dauern--welche-regel-gilt-invariante)
11. [Wie aktualisiere oder deinstalliere ich die Integration?](#11-wie-aktualisiere-oder-deinstalliere-ich-die-integration)
12. [iOS vs. Android — was ist bei den Pushes anders?](#12-ios-vs-android--was-ist-bei-den-pushes-anders)
13. [Not-Aus per Webhook / Apple-Kurzbefehl auslösen (Rezept)](#13-not-aus-per-webhook--apple-kurzbefehl-auslösen-rezept)
14. [Topf-Frequenzbewässerung: Wer setzt den Dosen-Zähler zurück?](#14-topf-frequenzbewässerung-wer-setzt-den-dosen-zähler-zurück)
15. [Trocken-Report: Ich will eine strenge 23-h-Persistenz-Prüfung (history_stats-Rezept)](#15-trocken-report-ich-will-eine-strenge-23-h-persistenz-prüfung-history_stats-rezept)
16. [Kann ich kurz vor Mitternacht bewässern?](#16-kann-ich-kurz-vor-mitternacht-bewässern)

---

## 1. Welche Ventile funktionieren?

**Alles, was in Home Assistant als `switch` erscheint und Wasser schaltet.**
Die Integration ruft ausschließlich `switch.turn_on` / `switch.turn_off` auf
und prüft den Zustand über die State-Machine. Getestet wurde im Ursprungssystem
mit Zigbee-Bewässerungsventilen (Sonoff SWV), die als `switch` mit eigenem
Durchfluss-, Leck- und Wasserversorgungs-Sensor erscheinen — aber genauso
funktionieren:

- Zigbee-/Z-Wave-Bewässerungsventile beliebiger Hersteller (solange sie als
  `switch` auftauchen),
- eine Pumpe an einer smarten Steckdose (`switch.steckdose_pumpe`),
- ein Magnetventil an einem Relais (Shelly, ESPHome, Hutschienen-Aktor).

**Wichtig für Funk-Ventile:** Jeder Schließ-Befehl läuft als Retry-Schleife
(bis zu 5 Versuche im 3-Sekunden-Abstand, bis das Ventil wirklich `off`
meldet) — das fängt den klassischen Zigbee-Aussetzer „device did not respond“
ab, bei dem ein einzelner `turn_off` still verpufft. Der eingebaute
Notaus-Watchdog überwacht automatisch **alle** Ventile aller Kreise — es gibt
nichts zu instanziieren und keine Liste zu pflegen
(siehe [Frage 9](#9-ein-ventil-ging-nicht-zu--was-ist-passiert-was-tun)).

Erscheint dein Ventil nicht als `switch`, sondern als `valve` oder `light`:
[Frage 2](#2-mein-ventil-ist-eine-valve--oder-light-entität--was-nun-template-switch-rezept).

## 2. Mein Ventil ist eine `valve`- oder `light`-Entität — was nun? (Template-Switch-Rezept)

Manche Integrationen legen Bewässerungsventile als `valve.*` an, manche
Zigbee-Ventile tauchen (falscher Gerätetyp im Quirk) als `light.*` auf. Der
Kreis-Dialog erwartet `switch` — wickle das Ventil in einen
**Template-Switch**. Der Wrapper ist einmalig 10 Zeilen YAML in der
`configuration.yaml` (danach „Entwicklerwerkzeuge → YAML → Template-Entitäten
neu laden" bzw. HA-Neustart) und verhält sich exakt wie ein natives
Ventil-Switch.

**Variante A — Ventil ist `valve.*`:**

```yaml
switch:
  - platform: template
    switches:
      bewaesserungsventil_rasen:
        friendly_name: "Bewässerungsventil Rasen"
        # 'opening' zählt mit als AN — sonst meldet der Wrapper während der
        # Öffnungsfahrt kurz 'off' und verwirrt die Retry-Close-Prüfung.
        value_template: >-
          {{ states('valve.DEIN_VENTIL') in ['open', 'opening'] }}
        turn_on:
          - action: valve.open_valve
            target:
              entity_id: valve.DEIN_VENTIL
        turn_off:
          - action: valve.close_valve
            target:
              entity_id: valve.DEIN_VENTIL
```

**Variante B — Ventil ist `light.*`:**

```yaml
switch:
  - platform: template
    switches:
      bewaesserungsventil_tropf:
        friendly_name: "Bewässerungsventil Tropf"
        value_template: "{{ is_state('light.DEIN_VENTIL', 'on') }}"
        turn_on:
          - action: light.turn_on
            target:
              entity_id: light.DEIN_VENTIL
        turn_off:
          - action: light.turn_off
            target:
              entity_id: light.DEIN_VENTIL
```

Danach wählst du im Kreis-Dialog `switch.bewaesserungsventil_rasen`
(bzw. `_tropf`) als Ventil — **nie** die darunterliegende
`valve`/`light`-Entität. Der Wrapper spiegelt den echten Gerätezustand (kein
`optimistic`), d. h. Retry-Close-Härtung und Notaus-Watchdog sehen den
tatsächlichen Zustand.

## 3. Welche Bodenfeuchte-Sensoren brauche ich? Geht es auch ohne?

**Jeder Sensor, der Bodenfeuchte in Prozent (0–100) meldet, funktioniert:**
Zigbee-Bodenfeuchtesensoren, ESPHome-Eigenbauten mit kapazitiver Sonde,
Pflanzensensoren — die Score-Engine liest schlicht den Zustand als Zahl.

- **Mehrere Sensoren pro Kreis:** erlaubt (das Feld ist eine Mehrfachauswahl).
  Es zählt das **Minimum** — der trockenste Sensor gewinnt. Sinnvoll, wenn
  ein Ventil mehrere Zonen mit je eigenem Sensor bewässert.
- **Sensor fällt aus:** Ein konfigurierter, aber `unavailable`r Sensor wird
  mit 50 % angenommen (neutraler Wert — der Score läuft weiter, statt zu
  eskalieren oder zu verhungern).
- **Gar kein Sensor:** Geht. Lass das Feld leer — die Score-Gewichte werden
  automatisch renormalisiert, der Score bildet sich dann nur aus
  Wetter-Faktor (Tmax oder ET₀) und „Tage seit letzter Bewässerung“. Das
  Boden-Veto („feucht genug → 0 min“) entfällt logischerweise mit. Tipp:
  Für sensorlose Rasenkreise lohnt die ET₀-Quelle (Tuning → „Temperatur &
  Verdunstung“ oder direkt am Kreis).
- **Kalibrierung:** Bodenfeuchte-Prozente sind je nach Substrat, Einbautiefe
  und Sensor-Modell sehr unterschiedlich. Beobachte nach dem Gießen und nach
  2–3 trockenen Tagen, welche Werte DEIN Sensor liefert, und stelle danach
  die Veto-Schwelle des Kreises ein (`number.garten_<kreis>_veto_schwelle_boden`).
  Die Seed-Werte (Rasen 70 %, Topf 65 %) stammen aus dem Ursprungssystem mit
  Zigbee-Sensoren in Töpfen.
- **Glitch-Schutz (Topf-Kreise):** Funk-Sensoren melden bei Dropouts gern
  kurz 0 %. Die Topf-Frequenzbewässerung ignoriert Werte unter der
  Glitch-Untergrenze (Tuning → Töpfe, Standard 5 %) — eine 0-%-Falschmeldung
  löst also keine Dosis aus.

## 4. Wie baue ich den Regen-24h-Sensor? (3 Rezepte je nach Quellsensor)

Die Integration akzeptiert optional einen Sensor „Regen der letzten 24 h in
mm“ (Globale Einstellungen → Regensensor; Schwelle =
`number.garten_regen_veto_beobachtet`, Seed 3 mm). Welches Rezept du brauchst,
hängt davon ab, **in welcher Form dein Regensensor liefert**. Prüfe das zuerst
in „Entwicklerwerkzeuge → Zustände“: Steigt der Wert immer weiter (kumulativ)?
Springt er pro Messintervall auf kleine Häppchen (Intervall-mm)? Oder ist es
eine Rate in mm/h?

Alle Rezepte kommen in die `configuration.yaml` (oder eine included Datei),
danach HA neu starten.

**Form 1 — Intervall-mm** (Sensor meldet mm *pro Messintervall*, z. B.
„0.4 mm in den letzten 10 Minuten“):

```yaml
sensor:
  - platform: statistics
    name: "Bewaesserung Regen 24h"
    unique_id: bewaesserung_regen_24h
    entity_id: sensor.DEIN_REGEN_SENSOR    # <— dein Intervall-mm-Sensor
    state_characteristic: total            # Summe aller Messwerte im Fenster
    sampling_size: 1000                    # muss >= Messwerte deines Sensors in 24 h sein
    max_age:
      hours: 24
```

Hinweis: HA zeichnet nur *Zustandsänderungen* auf. Meldet dein Sensor zweimal
hintereinander exakt denselben Wert (z. B. 0.4 → 0.4), zählt das nur einmal —
bei Intervall-Sensoren, die zwischen 0 und Messwert wechseln, praktisch nie
ein Problem; im Zweifel untertreibt der Sensor leicht (Veto feuert etwas
seltener — die konservative Richtung).

**Form 2 — kumulativ** (Wert steigt immer weiter, z. B. Jahres-/Gesamtsumme):

```yaml
sensor:
  - platform: statistics
    name: "Bewaesserung Regen 24h"
    unique_id: bewaesserung_regen_24h
    entity_id: sensor.DEIN_REGEN_TOTAL     # <— dein kumulativer Zähler
    state_characteristic: change           # Wertänderung im 24-h-Fenster = mm in 24 h
    sampling_size: 1000
    max_age:
      hours: 24
```

Sonderfall „Regen heute“ (setzt um Mitternacht auf 0 zurück): `change` würde
nach dem Reset negativ. Nimm dann stattdessen
`state_characteristic: sum_differences_nonnegative` — das summiert nur die
*Anstiege* im Fenster und ignoriert den Mitternachts-Sprung auf 0. Ergebnis
ist wieder eine saubere rollende 24-h-Summe. (Alternativ kannst du einen
„Regen heute“-Sensor auch DIREKT eintragen — dann gilt die Schwelle eben
„seit Mitternacht“ statt rollend; für das Skip-Veto meist gut genug.)

**Form 3 — Rate in mm/h**: erst per Integral-Helfer zu einem kumulativen
Zähler aufintegrieren, dann Form 2 anwenden:

```yaml
sensor:
  - platform: integration                  # Riemann-Summe: mm/h × h = mm
    source: sensor.DEIN_REGEN_RATE
    name: "Bewaesserung Regen kumulativ"
    unique_id: bewaesserung_regen_kumulativ
    unit_time: h
    method: left                           # WICHTIG: left — trapezoidal überzählt
                                           # bei seltenen Messwerten massiv
  - platform: statistics
    name: "Bewaesserung Regen 24h"
    unique_id: bewaesserung_regen_24h
    entity_id: sensor.bewaesserung_regen_kumulativ
    state_characteristic: change
    sampling_size: 1000
    max_age:
      hours: 24
```

Nach dem Neustart prüfen: „Entwicklerwerkzeuge → Zustände“ →
`sensor.bewaesserung_regen_24h` zeigt eine plausible Zahl (0 bei Trockenheit).
Dann den Sensor in **Globale Einstellungen → Regensensor** eintragen — ohne
Eintrag bleibt das Regen-beobachtet-Veto schlicht deaktiviert, nichts geht
kaputt.

## 5. Meine Wetter-Integration liefert kein `daily` / keinen Niederschlag

Die Integration holt die Vorhersage per `weather.get_forecasts`. Zwei
Stellschrauben:

- **Kein `daily`-Forecast** (manche Integrationen können nur stündlich):
  Stelle im **Tuning → „Temperatur & Verdunstung“ → Vorhersage-Typ** auf
  „hourly“. Tmax wird dann über die ersten 72 Stunden gebildet (entspricht
  den 3 Tagen des daily-Modus), der Niederschlag über die ersten 24 Stunden
  summiert. Merke den Unterschied fürs Regen-Vorhersage-Veto: **daily zählt
  nur den heutigen Tageswert, hourly die Summe der nächsten 24 h** (rollt
  über Mitternacht) — für einen Abendlauf ist hourly meist das ehrlichere
  Fenster. Welcher Modus aktiv war, steht als `forecast_typ` in den
  Attributen von `sensor.garten_plan_heute` — und das Attribut
  `regen_fc_datenbasis` listet die exakt summierten Forecast-Zeilen
  (Zeitstempel + mm), sodass du jede FC-Zahl direkt gegen
  „Entwicklerwerkzeuge → Aktionen“ vergleichen kannst.
- **Kein `precipitation`-Feld im Forecast:** Fehlende Werte werden als 0
  gelesen — das Regen-**Vorhersage**-Veto feuert dann einfach nie.
  Kompensiere mit dem Regen-**beobachtet**-Veto: baue den Regen-24h-Sensor
  aus [Frage 4](#4-wie-baue-ich-den-regen-24h-sensor-3-rezepte-je-nach-quellsensor)
  aus einer echten Messquelle.
- **Vorhersage-Abruf schlägt komplett fehl** (Integration offline, Timeout):
  Die Berechnung bricht NICHT ab. Der Score rechnet mit Tmax = 20 °C und
  Regen-Vorhersage = 0 weiter, und der Status-Text des Kreises bekommt den
  Hinweis „(Wetter n/v)“ — so siehst du sofort, dass der Plan gerade auf dem
  Fallback läuft. (Der ET₀-Modus fällt dabei automatisch auf den Tmax-Pfad
  zurück.)

Teste deinen Forecast direkt: „Entwicklerwerkzeuge → Aktionen“ →
`weather.get_forecasts` → deine Wetter-Entität als Ziel, `type: daily` (oder
`hourly`) → „Aktion ausführen“. In der Antwort siehst du, ob `temperature`,
`templow` (für ET₀) und `precipitation` geliefert werden.

## 6. Wie finde ich den Namen meines notify-Dienstes?

Öffne **„Entwicklerwerkzeuge → Aktionen“** (englisch: Developer Tools →
Actions) und tippe im Aktions-Auswahlfeld `notify.` ein. Die Liste zeigt alle
verfügbaren Dienste. Jedes Handy mit installierter Companion-App erscheint als
`notify.mobile_app_<gerätename>` — der Gerätename stammt aus der Companion-App
(Einstellungen → Companion App → Gerätename) und wird kleingeschrieben mit
Unterstrichen versehen (aus „Peters iPhone“ wird
`notify.mobile_app_peters_iphone`).

Direkt dort testen: Dienst auswählen, bei `message` einen Text eintragen,
„Aktion ausführen“ — kommt der Push an, ist der Name korrekt. Genau diesen
Namen (mit `notify.`-Präfix) trägst du im **Options-Dialog →
Benachrichtigungen** ein.

## 7. Wie schicke ich Pushes an mehrere Handys? (notify-Gruppen-Rezept)

**Weg 1 (ohne YAML):** Das Benachrichtigungen-Feld akzeptiert eine
**komma-getrennte Liste**:

```
notify.mobile_app_handy1, notify.mobile_app_handy2
```

Jeder Dienst bekommt denselben Push. Einträge, die nicht mit `notify.`
beginnen, werden ignoriert (Tippfehler-Schutz).

**Weg 2 (notify-Gruppe — pflegst du die Empfängerliste an EINER Stelle):**

```yaml
# configuration.yaml — danach HA neu starten
notify:
  - platform: group
    name: alle_handys          # ergibt den Dienst notify.alle_handys
    services:
      - action: mobile_app_handy1    # OHNE "notify."-Präfix!
      - action: mobile_app_handy2
```

Danach trägst du im Options-Dialog nur noch `notify.alle_handys` ein. Kommt
später ein drittes Handy dazu, ergänzt du es einmal in der Gruppe.
Stolperfalle: Unter `services:` steht der Dienstname **ohne**
`notify.`-Präfix (also `mobile_app_handy1`, nicht
`notify.mobile_app_handy1`).

## 8. „Warum bewässert er heute nicht?“

**Schau auf den Status-Sensor des Kreises** (`sensor.garten_<kreis>_status`) —
das ist die eingebaute Antwort auf genau diese Frage. Die Engine schreibt
alle 30 Minuten pro Kreis einen erklärenden Satz; `sensor.garten_plan_heute`
fasst zusätzlich den ganzen Tag in einer Zeile zusammen. Die möglichen Texte:

| Status-Text beginnt mit | Bedeutung | Was tun (falls unerwünscht) |
|---|---|---|
| `⏭ Übersprungen` | „Heute überspringen“ ist an | `switch.garten_heute_uberspringen` ausschalten (wird sonst um 00:01 automatisch zurückgesetzt) |
| `⏸ Urlaubsmodus` | Urlaubsmodus ist an | Toggle ausschalten — er bleibt an, bis DU ihn ausschaltest |
| `⏸ Kreis deaktiviert` | `switch.garten_<kreis>_aktiv` ist aus | Kreis wieder aktivieren |
| `☔ Regen-Veto: … gemessen` | Regen-24h-Sensor über der Schwelle | `number.garten_regen_veto_beobachtet` erhöhen |
| `☔ Regen-Veto: … Vorhersage` | Forecast-Regen über der Schwelle | `number.garten_regen_veto_vorhersage` erhöhen — oder daily/hourly-Fenster prüfen ([Frage 5](#5-meine-wetter-integration-liefert-kein-daily--keinen-niederschlag)) |
| `💧 Boden feucht genug` | Bodenfeuchte ÜBER der Veto-Schwelle | Veto-Schwelle des Kreises senken — oder freuen: der Boden ist wirklich nass |
| `Score X unter Schwelle Y` | Score zu niedrig (Boden ok, kühl, kürzlich bewässert) | Skip-Schwelle senken oder Veto-Schwelle erhöhen (macht den Kreis „durstiger“) |
| `… (Wetter n/v)` (Anhang) | Vorhersage-Abruf schlug fehl, Fallback Tmax 20 °C | Wetter-Integration prüfen ([Frage 5](#5-meine-wetter-integration-liefert-kein-daily--keinen-niederschlag)) |

Wenn der Status eine Dauer > 0 zeigt, aber trotzdem nichts lief, prüfe die
Ausführungs-Ebene:

1. **Skip/Urlaub zur Startzeit:** Die Engine prüft beide Toggles NOCHMAL beim
   Start — auch beim Sofort-Start-Knopf.
2. **Ventil `unavailable` zur Startzeit:** Der Slot wird einzeln übersprungen
   (Funkverbindung prüfen, [Frage 9](#9-ein-ventil-ging-nicht-zu--was-ist-passiert-was-tun)).
3. **Dauer wurde nach dem Push wieder 0:** Der Score rechnet alle 30 min neu —
   ein Regenschauer zwischen Plan-Push (Startzeit − Vorlauf) und Ausführung
   kann den Plan legitim auf 0 ziehen. (Deine MANUELL überschriebene Dauer
   bleibt dagegen bis zum Lauf erhalten — der Lauf nimmt beim Start einen
   Schnappschuss.)
4. **Bericht ansehen:** `sensor.garten_letzter_lauf` zeigt den letzten Lauf
   mit Quelle, Kreisen und ob er abgebrochen wurde; die Events
   `garten_bewaesserung_lauf_gestartet/_beendet` stehen im
   Entwicklerwerkzeuge-Event-Log.

## 9. Ein Ventil ging nicht zu — was ist passiert, was tun?

Die Integration hat für genau diesen Fall vier gestaffelte, **eingebaute**
Sicherungen — im Ursprungssystem war ein Zigbee-Ventil, das zum
Schließzeitpunkt nicht erreichbar war („device did not respond“), der
Auslöser für die gesamte Härtung:

1. **Retry-Close überall:** Jeder Schließ-Vorgang (Lauf, Auto-Aus,
   Topf-Dosis, Not-Aus, Watchdog) wiederholt `turn_off`, bis das Ventil
   wirklich `off` meldet (5 Versuche, 3 s Abstand). Ein einzelner
   Funk-Aussetzer wird so fast immer abgefangen.
2. **Sicherheits-Sweep:** Am Ende jedes Laufs werden noch einmal ALLE
   Ventile geschlossen — auch die, deren Slot vorher einen Fehler hatte.
   Meldet danach trotzdem noch ein Ventil „an“, bekommst du (falls
   notify-Dienste gesetzt) einen Warn-Push.
3. **Notaus-Watchdog:** Ist ein Ventil länger als die Notaus-Schwelle
   (Globale Einstellungen, Standard 40 min) ununterbrochen offen — egal
   wodurch geöffnet —, wird es zwangsgeschlossen + Push. Er überwacht
   automatisch **alle** Ventile aller Kreise; nach einem HA-Neustart werden
   verwaiste offene Ventile sofort zwangsgeschlossen.
4. **Auto-Aus-Backstop:** fängt von Hand geöffnete Ventile nach der
   Auto-Aus-Dauer (Globale Einstellungen, Standard 10 min).

**Wenn es trotzdem passiert ist** (Warn-Push „Ventil noch offen“):

- Zuerst physisch: Wasserhahn zu / Ventil von Hand schließen.
- Dann Ursache: In 9 von 10 Fällen ist es die Funkstrecke. Prüfe die
  Verbindungsqualität des Ventils (bei Zigbee: LQI/RSSI auf der Geräteseite)
  und die Batterie. Die wirksamste Abhilfe im Ursprungssystem: einen
  **netzbetriebenen Zigbee-Router** (Smart Plug ~15 €) zwischen Koordinator
  und Garten-Ventil stecken — das stabilisiert den Hop mehr als jede
  Software-Maßnahme.

## 10. Die Notaus-Schwelle und die Max-Dauern — welche Regel gilt? (Invariante)

**Regel: `Notaus-Schwelle > größte Max-Dauer aller Kreise` und
`Notaus-Schwelle > Auto-Aus-Dauer`.**

Der Watchdog kann nicht unterscheiden, ob ein Ventil *legitim* lange läuft
oder *hängt* — er kennt nur die Zeit. Liegt die Notaus-Schwelle unter einer
Max-Dauer, würgt er jede lange (aber gewollte) Bewässerung dieses Kreises ab
und schickt dir dazu noch einen Fehlalarm-Push.

Mit den Seed-Werten passt es: Notaus 40 min gegen Max-Dauer 20 min (Rasen)
bzw. 4 min (Topf) und Auto-Aus 10 min — komfortabler Abstand. **Wenn du eine
Max-Dauer über ~35 min stellst, erhöhe im selben Zug die Notaus-Schwelle**
(Globale Einstellungen), z. B. Max-Dauer 45 → Notaus 60. Merkhilfe: Notaus ≈
größte Max-Dauer + 15–20 min Reserve. Die Reserve muss den Versatz
sequenzieller Ketten NICHT abdecken: Der Watchdog-Timer läuft **pro Ventil**
ab dessen Einschalt-Moment, nicht ab Laufbeginn. Achtung Sonderfall
**mehrere Ventile in EINEM Kreis**: die laufen nacheinander je die volle
Kreis-Dauer — pro Ventil gilt trotzdem die eigene Uhr, die Invariante bleibt
also einfach „Notaus > Max-Dauer“.

## 11. Wie aktualisiere oder deinstalliere ich die Integration?

**Update:** HACS zeigt neue Versionen automatisch an (Repo öffnen →
„Herunterladen“/Update), danach Home Assistant neu starten. Deine
Konfiguration (Kreise, Tuning, Zähler) bleibt vollständig erhalten — sie
lebt im Config-Entry und im integrationseigenen Speicher, nicht im Code.

**Deinstallation:**

1. **Integration entfernen:** Einstellungen → Geräte & Dienste →
   Garten-Bewässerung → ⋮ → Löschen. Damit verschwinden alle Entities,
   Geräte, Timer und der Speicher der Integration.
2. **HACS-Download entfernen:** HACS → Garten-Bewässerung → ⋮ → Entfernen,
   danach HA neu starten.
3. **Reste von Hand:** Eigene Zutaten aus dieser FAQ — Template-Switches
   ([Frage 2](#2-mein-ventil-ist-eine-valve--oder-light-entität--was-nun-template-switch-rezept)),
   Regen-24h-Sensor ([Frage 4](#4-wie-baue-ich-den-regen-24h-sensor-3-rezepte-je-nach-quellsensor)),
   notify-Gruppen, Webhook-Automationen — liegen in deiner
   `configuration.yaml` und bleiben, bis du sie entfernst. Historien-Daten
   gelöschter Entities altern über die normale Recorder-Aufbewahrung heraus;
   sofort loswerden: Aktion `recorder.purge_entities`.

## 12. iOS vs. Android — was ist bei den Pushes anders?

Die Pushes der Integration benutzen einen einheitlichen Payload, der auf
beiden Plattformen funktioniert. Die Unterschiede im Detail:

- **„Kritische Pushes“ (Benachrichtigungen-Dialog):** setzt iOS
  `interruption-level: time-sensitive` — die Nachricht durchbricht
  Fokus-Modi/„Nicht stören“ (aber NICHT die Stummschaltung; es ist bewusst
  keine „Critical Notification“ mit Ton-Zwang). Damit das greift, muss in den
  iOS-Einstellungen → Mitteilungen → Home Assistant „Zeitkritische
  Mitteilungen" erlaubt sein. **Android ignoriert das Feld komplett und
  harmlos** — dort steuerst du die Wichtigkeit über den
  Benachrichtigungskanal des Geräts (Systemeinstellungen → Apps → Home
  Assistant → Benachrichtigungen).
- **Dashboard-Deep-Link (Benachrichtigungen-Dialog):** Der Payload setzt
  `url` (iOS) UND `clickAction` (Android) auf denselben Pfad — ein Tipp auf
  den Push öffnet die Companion-App direkt auf diesem Dashboard.
  **Stolperfalle:** Der Pfad muss ein GÜLTIGER Lovelace-Pfad sein (so wie er
  in der Browser-URL steht, z. B. `/garten-bewaesserung` oder
  `/dashboard-garten/wasser`). Bei einem ungültigen Pfad öffnet die App
  **stumm** das Standard-Dashboard — es gibt keine Fehlermeldung, weder in
  der App noch im HA-Log. Wenn dein Deep-Link „nicht funktioniert“, ist es
  praktisch immer ein Tippfehler im Pfad.
- Beide Apps brauchen naturgemäß eine erreichbare HA-Instanz für die
  Zustellung (iOS via Apple Push über den HA-Cloud-Relay der Companion-App,
  Android via Firebase oder lokalen Push).

## 13. Not-Aus per Webhook / Apple-Kurzbefehl auslösen (Rezept)

Von unterwegs (Apple-Kurzbefehl, Widget, Kurzautomation) löst du den Not-Aus
über eine Mini-Automation aus, die den Service der Integration ruft:

```yaml
# automations.yaml (oder per UI: Neue Automation → YAML-Modus)
- alias: "Bewaesserung Not-Aus per Webhook"
  triggers:
    - trigger: webhook
      webhook_id: "notaus-HIER-EINE-EIGENE-LANGE-ZUFALLS-ID"
      local_only: false          # nur nötig, wenn der Aufruf von außen kommt
      allowed_methods:
        - POST
  actions:
    - action: garten_bewaesserung.not_aus
```

**Wichtige Hinweise:**

- Die `webhook_id` ist das einzige Passwort dieses Endpunkts — nimm eine
  lange Zufalls-ID (z. B. 32 Hex-Zeichen), niemals `notaus` o. ä. Aufruf:
  `POST https://deine-ha-adresse/api/webhook/<deine-id>` — im
  Apple-Kurzbefehl: „Inhalte von URL abrufen“, Methode POST.
- `local_only: false` nur setzen, wenn der Aufruf wirklich von außerhalb
  deines LANs kommt — HA verwirft externe Aufrufe an lokale Webhooks sonst
  **stillschweigend** (nur eine Debug-Zeile im Log, der Kurzbefehl sieht
  trotzdem Erfolg).
- `garten_bewaesserung.not_aus` verhält sich identisch zum
  `button.garten_not_aus`: Lauf abbrechen, alle Ventile retry-schließen,
  Push. Weitere Services für eigene Automationen: `jetzt_bewaessern`,
  `plan_neu_berechnen`, `dosis_geben` (siehe README).

## 14. Topf-Frequenzbewässerung: Wer setzt den Dosen-Zähler zurück?

**Niemand außer der Integration selbst — das ist eingebaut.** Der Zähler
(`sensor.garten_<kreis>_dosen_heute`) wird bei jeder Dosis erhöht (auch wenn
das Ventil beim Öffnen nicht reagiert — Absicht: ein wild „nachfeuernder“
Kreis bei Funkproblemen wäre gefährlicher als eine verpasste Dosis), täglich
um **00:01** automatisch auf 0 gesetzt und überlebt HA-Neustarts (eigener
Speicher — auch der Mindestabstand zwischen Dosen übersteht einen Neustart).

Diagnose-Tipp: Wenn ein Topf „keine Dosen mehr bekommt“, prüfe zuerst
`sensor.garten_<kreis>_dosen_heute` gegen das Tageslimit (Tuning → Töpfe,
Standard 4) — steht er am Limit, ist das die Erklärung. Danach die übrigen
Gates: Master-Schalter `switch.garten_topf_frequenzbewasserung`, Kreis aktiv,
Bodenwert über der Glitch-Grenze aber unter dem Sollband, Peak-Sonnen-Sperre,
Mindestabstand, Regen-Veto.

## 15. Trocken-Report: Ich will eine strenge 23-h-Persistenz-Prüfung (history_stats-Rezept)

Der eingebaute Trocken-Report (08:00) prüft den **Momentanwert** gegen die
halbe Veto-Schwelle des Kreises, gedämpft wenn in den letzten 24 h bewässert
wurde. Wer strenger prüfen will — *„lag der Boden ≥ 23 der letzten
24 Stunden durchgehend unter der Schwelle?“*, unempfindlich gegen kurze
Morgen-Ausreißer — baut das mit zwei Zusatz-Sensoren pro Pflanze plus einer
kleinen Automation nach (hier für eine Tomate mit Schwelle 35 %):

```yaml
# configuration.yaml — Schicht 1: Momentan-Flag (unter Schwelle JETZT?)
template:
  - binary_sensor:
      - name: "Boden kritisch Tomate jetzt"
        unique_id: boden_kritisch_tomate_jetzt
        # float(100): ein nicht verfügbarer Sensor zählt NICHT als trocken
        state: "{{ states('sensor.DEIN_BODENSENSOR_TOMATE') | float(100) < 35 }}"

# Schicht 2: Stunden unter Schwelle in den letzten 24 h (liest aus der
# Recorder-Datenbank — überlebt Neustarts und Konfigurations-Reloads)
sensor:
  - platform: history_stats
    name: "Boden kritisch Tomate Stunden 24h"
    unique_id: boden_kritisch_tomate_stunden_24h
    entity_id: binary_sensor.boden_kritisch_tomate_jetzt
    state: "on"
    type: time
    start: "{{ now() - timedelta(hours=24) }}"
    end: "{{ now() }}"
```

```yaml
# Schicht 3: täglicher Check um 08:00 — Alarm ab 23 von 24 Stunden
- alias: "Trocken-Alarm Tomate (23h-Persistenz)"
  triggers:
    - trigger: time
      at: "08:00:00"
  conditions:
    - condition: numeric_state
      entity_id: sensor.boden_kritisch_tomate_stunden_24h
      above: 23
  actions:
    - action: notify.mobile_app_mein_handy
      data:
        title: "🌵 Boden kritisch trocken"
        message: >-
          Tomate: mindestens 23 der letzten 24 h unter 35 %
          (aktuell {{ states('sensor.DEIN_BODENSENSOR_TOMATE') }} %).
```

Drei Hinweise aus dem Ursprungssystem:

- **Warum nicht einfach `delay_on: "24:00:00"` am Template-Binärsensor?**
  Getestet und verworfen: Der `delay_on`-Timer ist Teil des Laufzeit-Zustands
  und startet bei **jedem Konfigurations-Reload bei 0** — in einem System, an
  dem man gelegentlich schraubt, feuert der Alarm dann nie. `history_stats`
  liest stattdessen aus der Recorder-Datenbank und ist reload-fest.
- **Warum 23 statt 24?** Die 1-Stunde-Toleranz schluckt kurzes Sensor-Zittern
  knapp über der Schwelle und die 1–2 Sekunden `unavailable` bei Reloads.
  Mit `above: 23.9` wird der Alarm praktisch unerreichbar.
- Der Recorder muss die letzten 24 h vorhalten (Standard sind 10 Tage —
  nur relevant, wenn du `purge_keep_days` aggressiv gesenkt oder den
  Binärsensor per `recorder:`-Exclude ausgeschlossen hast).

Pro weiterer Pflanze duplizierst du die drei Blöcke mit eigener Schwelle.

## 16. Kann ich kurz vor Mitternacht bewässern?

**Ja.** Der Lauf nimmt beim Start einen **Schnappschuss aller Dauern** und
arbeitet ihn vollständig ab — der Tagesreset um 00:01 (Dauern, Skip-Toggle,
Dosen-/Liter-Zähler) entwaffnet einen bereits laufenden Plan nicht. Zwei
Randnotizen: Die Tages-Zähler (Liter heute, Dosen heute) wechseln um 00:01
auf den neuen Tag, auch wenn gerade gewässert wird; und die
Watchdog-Invariante aus [Frage 10](#10-die-notaus-schwelle-und-die-max-dauern--welche-regel-gilt-invariante)
gilt natürlich unabhängig von der Uhrzeit.
