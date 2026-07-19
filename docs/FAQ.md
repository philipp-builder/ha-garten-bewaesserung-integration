<!--
=============================================================================
FAQ.md — Häufige Fragen zum Garten-Bewässerungs-Kit (Blueprints + Package)
-----------------------------------------------------------------------------
Zweck:  Antworten auf die häufigsten Installations-, Hardware- und
        Betriebsfragen, inklusive Copy-Paste-Rezepte (Template-Switch-Wrapper,
        Regen-24h-Sensor in 3 Varianten, notify-Gruppe, Webhook-Not-Aus,
        history_stats-Persistenz für den Trocken-Report).
Quelle: portiert aus einem produktiven 4-Kreis-System.
Lizenz: MIT · Stand: 2026-07 · Mindestversion Home Assistant: 2024.10.0
=============================================================================
-->

# FAQ — Garten-Bewässerungs-Kit

**Bevor du hier suchst:** Die Blueprint-Beschreibungen im Home-Assistant-UI sind
die Detail-Doku jedes Bausteins (jede Eingabe hat einen erklärenden Text), das
README erklärt die Installation Schritt für Schritt. Diese FAQ deckt alles ab,
was quer dazu liegt: Hardware-Sonderfälle, Rezepte, Fehlersuche.

## Inhalt

1. [Welche Ventile funktionieren mit dem Kit?](#1-welche-ventile-funktionieren-mit-dem-kit)
2. [Mein Ventil ist eine `valve`- oder `light`-Entität — was nun? (Template-Switch-Rezept)](#2-mein-ventil-ist-eine-valve--oder-light-entität--was-nun-template-switch-rezept)
3. [Welche Bodenfeuchte-Sensoren brauche ich? Geht es auch ohne?](#3-welche-bodenfeuchte-sensoren-brauche-ich-geht-es-auch-ohne)
4. [Wie baue ich den Regen-24h-Sensor? (3 Rezepte je nach Quellsensor)](#4-wie-baue-ich-den-regen-24h-sensor-3-rezepte-je-nach-quellsensor)
5. [Meine Wetter-Integration liefert kein `daily` / keinen Niederschlag](#5-meine-wetter-integration-liefert-kein-daily--keinen-niederschlag)
6. [Wie finde ich den Namen meines notify-Dienstes?](#6-wie-finde-ich-den-namen-meines-notify-dienstes)
7. [Wie schicke ich Pushes an mehrere Handys? (notify-Gruppen-Rezept)](#7-wie-schicke-ich-pushes-an-mehrere-handys-notify-gruppen-rezept)
8. [„Warum bewässert er heute nicht?“](#8-warum-bewässert-er-heute-nicht)
9. [Ein Ventil ging nicht zu — was ist passiert, was tun?](#9-ein-ventil-ging-nicht-zu--was-ist-passiert-was-tun)
10. [Die Notaus-Schwelle und die Max-Dauern — welche Regel gilt? (Invariante)](#10-die-notaus-schwelle-und-die-max-dauern--welche-regel-gilt-invariante)
11. [Ich habe mehr als 4 Kreise — geht das?](#11-ich-habe-mehr-als-4-kreise--geht-das)
12. [Wie viele Blueprint-Instanzen brauche ich? (Checkliste)](#12-wie-viele-blueprint-instanzen-brauche-ich-checkliste)
13. [Wie baue ich das Dashboard ein? (Raw-Editor)](#13-wie-baue-ich-das-dashboard-ein-raw-editor)
14. [Wie aktualisiere oder deinstalliere ich das Kit?](#14-wie-aktualisiere-oder-deinstalliere-ich-das-kit)
15. [iOS vs. Android — was ist bei den Pushes anders?](#15-ios-vs-android--was-ist-bei-den-pushes-anders)
16. [Not-Aus per Webhook / Apple-Kurzbefehl auslösen (Rezept)](#16-not-aus-per-webhook--apple-kurzbefehl-auslösen-rezept)
17. [Topf-Frequenzbewässerung: Wer setzt den Dosen-Zähler zurück? (Zähler-Kontrakt)](#17-topf-frequenzbewässerung-wer-setzt-den-dosen-zähler-zurück-zähler-kontrakt)
18. [Trocken-Report: Ich will die exakte 23-h-Persistenz-Prüfung des Originals (history_stats-Rezept)](#18-trocken-report-ich-will-die-exakte-23-h-persistenz-prüfung-des-originals-history_stats-rezept)

---

## 1. Welche Ventile funktionieren mit dem Kit?

**Alles, was in Home Assistant als `switch` erscheint und Wasser schaltet.**
Die Blueprints rufen ausschließlich `switch.turn_on` / `switch.turn_off` auf und
prüfen den Zustand mit `is_state(…, 'on'/'off')`. Getestet wurde das Kit im
Ursprungssystem mit Zigbee-Bewässerungsventilen (Sonoff SWV), die als `switch`
mit eigenem Durchfluss-, Leck- und Wasserversorgungs-Sensor erscheinen — aber
genauso funktionieren:

- Zigbee-/Z-Wave-Bewässerungsventile beliebiger Hersteller (solange sie als
  `switch` auftauchen),
- eine Pumpe an einer smarten Steckdose (`switch.steckdose_pumpe`),
- ein Magnetventil an einem Relais (Shelly, ESPHome, Hutschienen-Aktor).

**Wichtig für Funk-Ventile:** Jeder Schließ-Befehl im Kit läuft als
Retry-Schleife (Standard: bis zu 5 Versuche im 3-Sekunden-Abstand, bis das
Ventil wirklich `off` meldet) — das fängt den klassischen Zigbee-Aussetzer
„device did not respond“ ab, bei dem ein einzelner `turn_off` still verpufft.
Zusätzlich unbedingt den Watchdog-Blueprint „Ventil-Notaus“ mit **allen**
Ventilen instanziieren (siehe [Frage 9](#9-ein-ventil-ging-nicht-zu--was-ist-passiert-was-tun)).

Erscheint dein Ventil nicht als `switch`, sondern als `valve` oder `light`:
[Frage 2](#2-mein-ventil-ist-eine-valve--oder-light-entität--was-nun-template-switch-rezept).

## 2. Mein Ventil ist eine `valve`- oder `light`-Entität — was nun? (Template-Switch-Rezept)

Manche Integrationen legen Bewässerungsventile als `valve.*` an, manche
Zigbee-Ventile tauchen (falscher Gerätetyp im Quirk) als `light.*` auf. Die
Kit-Blueprints erwarten `switch` — wickle das Ventil in einen
**Template-Switch**. Der Wrapper ist einmalig 10 Zeilen YAML in der
`configuration.yaml` (danach „Entwicklerwerkzeuge → YAML → Template-Entitäten
neu laden" bzw. HA-Neustart) und verhält sich in allen Blueprints exakt wie
ein natives Ventil-Switch.

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

Danach trägst du in den Blueprints überall `switch.bewaesserungsventil_rasen`
(bzw. `_tropf`) ein — **nie** die darunterliegende `valve`/`light`-Entität.
Der Wrapper spiegelt den echten Gerätezustand (kein `optimistic`), d. h. die
Retry-Close-Härtung und der Notaus-Watchdog sehen den tatsächlichen Zustand.

## 3. Welche Bodenfeuchte-Sensoren brauche ich? Geht es auch ohne?

**Jeder Sensor, der Bodenfeuchte in Prozent (0–100) meldet, funktioniert:**
Zigbee-Bodenfeuchtesensoren, ESPHome-Eigenbauten mit kapazitiver Sonde,
Pflanzensensoren — der Score-Blueprint liest schlicht `states(sensor)` als
Zahl.

- **Mehrere Sensoren pro Kreis:** erlaubt (Eingabe `bodensensoren` ist eine
  Mehrfachauswahl). Es zählt das **Minimum** — der trockenste Sensor gewinnt.
  Sinnvoll, wenn ein Ventil mehrere Zonen mit je eigenem Sensor bewässert.
- **Sensor fällt aus:** Ein konfigurierter, aber `unavailable`r Sensor wird
  mit 50 % angenommen (neutraler Wert — der Score läuft weiter, statt zu
  eskalieren oder zu verhungern).
- **Gar kein Sensor:** Geht. Lass die Eingabe leer — die Score-Gewichte
  werden automatisch renormalisiert, der Score bildet sich dann nur aus
  Temperatur-Vorhersage und „Tage seit letzter Bewässerung“. Das Boden-Veto
  („feucht genug → 0 min“) entfällt logischerweise mit.
- **Kalibrierung:** Bodenfeuchte-Prozente sind je nach Substrat, Einbautiefe
  und Sensor-Modell sehr unterschiedlich. Beobachte nach dem Gießen und nach
  2–3 trockenen Tagen, welche Werte DEIN Sensor liefert, und stelle danach
  die Veto-Schwelle des Kreises (Dashboard-Slider) ein. Die Seed-Werte
  (Rasen 70 %, Beeren 65 %, Tomate 70 %) stammen aus dem Ursprungssystem mit
  Zigbee-Sensoren in Töpfen.
- **Glitch-Schutz (nur Topf-Blueprint):** Funk-Sensoren melden bei Dropouts
  gern kurz 0 %. Die Topf-Frequenzbewässerung ignoriert Werte unter der
  `glitch_grenze` (Standard 5 %) — eine 0-%-Falschmeldung löst also keine
  Dosis aus.

## 4. Wie baue ich den Regen-24h-Sensor? (3 Rezepte je nach Quellsensor)

Der Score-Blueprint und die Topf-Frequenzbewässerung akzeptieren optional
einen Sensor „Regen der letzten 24 h in mm“ (Eingabe `regen_24h_sensor`,
Vergleich gegen den Schwellen-Helfer `input_number.bewaesserung_regen_beobachtet_mm`,
Seed 3 mm). Welches Rezept du brauchst, hängt davon ab, **in welcher Form dein
Regensensor liefert**. Prüfe das zuerst in „Entwicklerwerkzeuge → Zustände“:
Steigt der Wert immer weiter (kumulativ)? Springt er pro Messintervall auf
kleine Häppchen (Intervall-mm)? Oder ist es eine Rate in mm/h?

Alle Rezepte kommen in die `configuration.yaml` (oder eine included Datei),
danach HA neu starten. Der Name ist bewusst ASCII („Bewaesserung“), damit die
Entity-ID exakt `sensor.bewaesserung_regen_24h` lautet.

**Form 1 — Intervall-mm** (Sensor meldet mm *pro Messintervall*, z. B.
„0.4 mm in den letzten 10 Minuten“ — das ist auch das auskommentierte Rezept
im Package):

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
„Regen heute“-Sensor auch DIREKT als `regen_24h_sensor` eintragen — dann gilt
die Schwelle eben „seit Mitternacht“ statt rollend; für das Skip-Veto meist
gut genug.)

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
Dann den Sensor in den Blueprint-Instanzen (Score + Topf) als
`regen_24h_sensor` eintragen — ohne Eintrag bleibt das Regen-beobachtet-Veto
schlicht deaktiviert, nichts geht kaputt.

## 5. Meine Wetter-Integration liefert kein `daily` / keinen Niederschlag

Der Score-Blueprint holt die Vorhersage per `weather.get_forecasts`. Zwei
Stellschrauben:

- **Kein `daily`-Forecast** (manche Integrationen können nur stündlich):
  Stelle im Score-Blueprint die Eingabe **`Vorhersage-Typ` auf „hourly“**.
  Tmax wird dann über die ersten 72 Stunden gebildet (entspricht den 3 Tagen
  des daily-Modus), der Niederschlag über die ersten 24 Stunden summiert
  (entspricht der 24-h-Semantik der Regen-Schwelle).
- **Kein `precipitation`-Feld im Forecast:** Der Blueprint liest fehlende
  Werte als 0 (`| default(0)`) — das Regen-**Vorhersage**-Veto feuert dann
  einfach nie. Kompensiere mit dem Regen-**beobachtet**-Veto: baue den
  Regen-24h-Sensor aus [Frage 4](#4-wie-baue-ich-den-regen-24h-sensor-3-rezepte-je-nach-quellsensor)
  aus einer echten Messquelle.
- **Vorhersage-Abruf schlägt komplett fehl** (Integration offline, Timeout):
  Die Berechnung bricht NICHT ab. Der Score rechnet mit Tmax = 20 °C und
  Regen-Vorhersage = 0 weiter, und der Status-Text des Kreises bekommt den
  Hinweis „(Wetter n/v)“ — so siehst du auf dem Dashboard sofort, dass der
  Plan gerade auf dem Fallback läuft.

Teste deinen Forecast direkt: „Entwicklerwerkzeuge → Aktionen“ →
`weather.get_forecasts` → deine Wetter-Entität als Ziel, `type: daily` (oder
`hourly`) → „Aktion ausführen“. In der Antwort siehst du, ob `temperature`
und `precipitation` geliefert werden.

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
Namen (mit `notify.`-Präfix) trägst du in die Blueprint-Eingabe
`notify_dienste` ein.

## 7. Wie schicke ich Pushes an mehrere Handys? (notify-Gruppen-Rezept)

**Weg 1 (ohne YAML):** Alle Blueprints des Kits akzeptieren in
`notify_dienste` eine **komma-getrennte Liste**:

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

Danach trägst du in allen Blueprint-Instanzen nur noch `notify.alle_handys`
ein. Kommt später ein drittes Handy dazu, ergänzt du es einmal in der Gruppe —
statt in ~6 Blueprint-Instanzen. Stolperfalle: Unter `services:` steht der
Dienstname **ohne** `notify.`-Präfix (also `mobile_app_handy1`, nicht
`notify.mobile_app_handy1`). Auf älteren HA-Versionen heißt der Schlüssel
`service:` statt `action:` — ab der Kit-Mindestversion 2024.10 funktioniert
`action:`.

## 8. „Warum bewässert er heute nicht?“

**Schau auf den Status-Text des Kreises** — das ist die eingebaute Antwort auf
genau diese Frage. Der Score-Blueprint schreibt alle 30 Minuten pro Kreis
einen erklärenden Satz in `input_text.bewaesserung_kreisN_status`; das
Kit-Dashboard zeigt ihn unter der Plan-Tabelle. Die möglichen Texte und was
sie bedeuten:

| Status-Text beginnt mit | Bedeutung | Was tun (falls unerwünscht) |
|---|---|---|
| `⏭ Übersprungen` | „Heute überspringen“ ist an | Toggle auf dem Dashboard ausschalten (wird sonst um 00:01 automatisch zurückgesetzt) |
| `⏸ Urlaubsmodus` | Urlaubsmodus ist an | Toggle ausschalten — er bleibt an, bis DU ihn ausschaltest |
| `☔ Regen-Veto: … gemessen` | Regen-24h-Sensor über der Schwelle | Schwelle (`Regen beobachtet`) auf dem Dashboard erhöhen |
| `☔ Regen-Veto: … Vorhersage` | Forecast-Regen über der Schwelle | Schwelle (`Regen Vorhersage`) erhöhen |
| `💧 Boden feucht genug` | Bodenfeuchte ÜBER der Veto-Schwelle | Veto-Schwelle des Kreises senken — oder freuen: der Boden ist wirklich nass |
| `Score X unter Schwelle Y` | Score zu niedrig (Boden ok, kühl, kürzlich bewässert) | Skip-Schwelle senken oder Veto-Schwelle erhöhen (macht den Kreis „durstiger“) |
| `… (Wetter n/v)` (Anhang) | Vorhersage-Abruf schlug fehl, Fallback Tmax 20 °C | Wetter-Integration prüfen ([Frage 5](#5-meine-wetter-integration-liefert-kein-daily--keinen-niederschlag)) |

Wenn der Status-Text eine Dauer > 0 zeigt, aber trotzdem nichts lief, prüfe
zusätzlich die Ausführungs-Ebene:

1. **Skip/Urlaub zur Startzeit:** Der Executor prüft beide Toggles NOCHMAL
   beim Start — auch beim Manuell-Knopf.
2. **Ventil `unavailable` zur Startzeit:** Der Slot wird einzeln
   übersprungen (Funkverbindung prüfen, [Frage 9](#9-ein-ventil-ging-nicht-zu--was-ist-passiert-was-tun)).
3. **Dauer wurde nach dem Push wieder 0:** Der Score rechnet alle 30 min neu —
   ein Regenschauer zwischen Plan-Push (Standard ~20:35, Trigger-Raster :05/:35) und Ausführung (21:00)
   kann den Plan legitim auf 0 ziehen.
4. **Automations-Trace ansehen:** Einstellungen → Automationen → deine
   Executor-Instanz → „Verlauf“ (Traces) zeigt jeden Durchlauf mit dem
   exakten Abzweig, der genommen wurde.

## 9. Ein Ventil ging nicht zu — was ist passiert, was tun?

Das Kit hat für genau diesen Fall vier gestaffelte Sicherungen — im
Ursprungssystem war ein Zigbee-Ventil, das zum Schließzeitpunkt nicht
erreichbar war („device did not respond“), der Auslöser für die gesamte
Härtung:

1. **Retry-Close überall:** Jeder Schließ-Vorgang (Executor, Auto-Aus,
   Topf-Dosis, Not-Aus, Watchdog) wiederholt `turn_off`, bis das Ventil
   wirklich `off` meldet (Standard: 5 Versuche, 3 s Abstand). Ein einzelner
   Funk-Aussetzer wird so fast immer abgefangen.
2. **Sicherheits-Sweep:** Der Executor schließt am Ende jedes Laufs noch
   einmal ALLE konfigurierten Ventile — auch die, deren Slot vorher einen
   Fehler hatte. Meldet danach trotzdem noch ein Ventil „an“, bekommst du
   (falls `notify_dienste` gesetzt) den Push „⚠️ Bewässerung: Ventil noch
   offen".
3. **Watchdog „Ventil-Notaus“:** Ist ein Ventil länger als die
   Notaus-Schwelle (Standard 40 min) ununterbrochen offen — egal wodurch —
   wird es zwangsgeschlossen + Push. Der Watchdog hat zusätzlich einen
   Neustart-Trigger: nach jedem HA-Start werden offene Ventile SOFORT
   geschlossen (ein Neustart tötet alle laufenden Warte-Schritte, das Ventil
   wäre sonst herrenlos).
4. **„Ventil Auto-Aus“-Backstop:** fängt manuell geöffnete Ventile nach der
   Standard-Dauer.

**Wenn es trotzdem passiert ist** (Push „meldet trotz 5 Schließversuchen noch
nicht aus"):

- Zuerst physisch: Wasserhahn zu / Ventil von Hand schließen.
- Dann Ursache: In 9 von 10 Fällen ist es die Funkstrecke. Prüfe die
  Verbindungsqualität des Ventils (bei Zigbee: LQI/RSSI auf der Geräteseite)
  und die Batterie. Die wirksamste Abhilfe im Ursprungssystem: einen
  **netzbetriebenen Zigbee-Router** (Smart Plug ~15 €) zwischen Koordinator
  und Garten-Ventil stecken — das stabilisiert den Hop mehr als jede
  Software-Maßnahme.
- Kontrolliere, dass der Watchdog wirklich ALLE Ventile in seiner
  `ventile`-Liste hat — ein Ventil, das dort fehlt, wird nicht überwacht.

## 10. Die Notaus-Schwelle und die Max-Dauern — welche Regel gilt? (Invariante)

**Regel: `Notaus-Schwelle > größte Max-Dauer aller Kreise` und
`Notaus-Schwelle > Standard-Dauer (Auto-Aus)`.**

Der Watchdog kann nicht unterscheiden, ob ein Ventil *legitim* lange läuft
oder *hängt* — er kennt nur die Zeit. Liegt die Notaus-Schwelle unter einer
Max-Dauer, würgt er jede lange (aber gewollte) Bewässerung dieses Kreises ab
und schickt dir dazu noch einen Fehlalarm-Push.

Mit den Seed-Werten passt es: Notaus 40 min gegen Max-Dauern 20/20/18/3 min
und Standard-Dauer 10 min — komfortabler Abstand. **Wenn du eine Max-Dauer
über ~35 min stellst, erhöhe im selben Zug die Notaus-Schwelle** (Eingabe
`notaus_minuten` der Watchdog-Instanz), z. B. Max-Dauer 45 → Notaus 60.
Merkhilfe: Notaus ≈ größte Max-Dauer + 15–20 min Reserve. Die Reserve deckt
den Slot-Versatz sequenzieller Gruppen NICHT ab — muss sie auch nicht: der
`for:`-Timer des Watchdogs läuft **pro Ventil** ab dessen Einschalt-Moment,
nicht ab Gruppenstart.

## 11. Ich habe mehr als 4 Kreise — geht das?

Ja, aber ehrlich: **nicht per Klick.** Das Package liefert Helfer für genau
4 Kreise. Für Kreis 5 (und weitere) musst du selbst Hand anlegen — das Kit
ist darauf ausgelegt, dass das sauber möglich ist:

1. **Helfer-Satz anlegen:** Kopiere im Package (`packages/bewaesserung.yaml`)
   die kompletten `kreis4_*`-Blöcke und benenne sie auf `kreis5_*` um — in
   allen vier Abschnitten: `input_number` (score, dauer_heute, veto_schwelle,
   min_dauer, max_dauer, dosen_heute, ziel_unten, ziel_oben),
   `input_datetime` (kreis5_letzte_bewaesserung), `input_text`
   (kreis5_status). ASCII beachten („ae“, kein „ä“ in den Schlüsseln).
2. **Reset erweitern:** In der Package-Automation `bewaesserung_system_reset`
   die Entity-Listen des Tages-Resets um
   `input_number.bewaesserung_kreis5_dauer_heute` und
   `…_kreis5_dosen_heute` ergänzen — **sonst blockiert das Topf-Tages-Limit
   ab Tag 2 und die Tagesdauer von gestern leckt in den neuen Tag.**
3. **HA neu starten** (Packages werden nur beim Start geladen), dann die
   Kreis-5-Werte von Hand setzen (das Seed-Script kennt Kreis 5 nicht).
4. **Blueprint-Instanzen:** eine weitere „Kreis: Score & Tagesdauer“-Instanz,
   die auf die Kreis-5-Helfer zeigt; je Ventil eine „Auto-Aus“- und eine
   „Sitzungs-Tracker“-Instanz; das Ventil zusätzlich in die `ventile`-Listen
   von Watchdog UND Not-Aus aufnehmen.
5. **Grenzen der 4er-Slots:** Der Executor („Ausführung — sequenzielle
   Gruppe") hat 4 Slots pro Instanz — Ventil 5 kommt in eine **zweite
   Executor-Instanz** (gleiche Startzeit = läuft parallel zur ersten Gruppe;
   andere Startzeit = läuft danach). Der Tagesplan-Push hat ebenfalls
   4 Slots — entweder eine zweite Push-Instanz (ergibt zwei Nachrichten)
   oder Kreis 5 im Push weglassen.
6. **Dashboard:** Die Tier-1-Karten iterieren über Kreis 1–4 — für Kreis 5
   die Markdown-Schleifen von `range(1, 5)` auf `range(1, 6)` erweitern bzw.
   Karten duplizieren.

Beim nächsten Kit-Update deine Package-Änderungen nicht blind überschreiben —
eigene Blöcke vorher sichern ([Frage 14](#14-wie-aktualisiere-oder-deinstalliere-ich-das-kit)).

## 12. Wie viele Blueprint-Instanzen brauche ich? (Checkliste)

Ehrliche Antwort: Für den Vollausbau des Ursprungssystems (4 Kreise,
4 Ventile, 2 Töpfe, alle Alarme) sind es **rund 15–20 Instanzen**. Das klingt
nach viel, ist aber je Instanz ein 1-Minuten-Formular, weil die Standardwerte
zum Package passen. Anlegen: Einstellungen → Automationen & Szenen →
Blueprints → Blueprint anklicken → „Automation erstellen“.

| Blueprint (Datei) | Instanzen | Pflicht-Eingaben (Rest hat Package-Defaults) |
|---|---|---|
| Kreis: Score & Tagesdauer (`kreis_score.yaml`) | 1 **pro Kreis** | `wetter` |
| Tagesplan-Push (`tagesplan_push.yaml`) | 1 | keine (ohne `notify_dienste` wirkungslos) |
| Ausführung — sequenzielle Gruppe (`ausfuehrung_gruppe.yaml`) | 1 pro sequenzielle Gruppe | `ventil_1` |
| Ventil Auto-Aus (`ventil_auto_aus.yaml`) | 1 **pro Ventil** | `ventil` |
| Ventil-Notaus / Watchdog (`ventil_notaus.yaml`) | 1 (alle Ventile eintragen!) | `ventile` |
| Topf-Frequenzbewässerung (`topf_soll_band.yaml`) | 1 pro Topf-Kreis | `bodensensor`, `ventil`, `k` |
| Alarm: Wasserleck (`alarm_leck.yaml`) | 0–1 (nur mit Leck-Sensoren) | `leck_sensoren` |
| Alarm: Wasserversorgung (`alarm_wasserversorgung.yaml`) | 1 pro Sensor/Ventil-Paar | `versorgung_sensor`, `ventil` |
| Ventil: Sitzungs-Tracker (`ventil_sitzung.yaml`) | 1 **pro Ventil** | `ventil` |
| Batterie-Warnung (`batterie_warnung.yaml`) | 1 | `batterie_sensoren` |
| Not-Aus: Alle Ventile zu (`not_aus.yaml`) | 1 (alle Ventile eintragen!) | `ventile` |
| Trocken-Report (`boden_kritisch_report.yaml`) | 0–1 | `sensor_1` |

Drei Stolperfallen aus der Praxis:

- **Watchdog und Not-Aus brauchen ALLE Ventile** in ihrer Liste — ein
  vergessenes Ventil ist unbewacht bzw. bleibt beim Not-Aus offen.
- **Zwei Ventile am selben Kreis** (z. B. Rasen West + Ost teilen sich
  Kreis 1): beide Sitzungs-Tracker-Instanzen zeigen mit `letzte_helper` auf
  DENSELBEN Helfer (`…kreis1_letzte_bewaesserung`), im Executor bekommen
  beide Slots denselben Tagesdauer-Helfer. Nur EINE Score-Instanz für den
  Kreis.
- **Kreis 2–4 konfigurieren heißt: die sieben Kreis-Helfer umstellen.** Die
  Defaults jeder Score-Instanz zeigen auf Kreis 1 — für Kreis 2 stellst du
  score/dauer/veto/min/max/letzte/status auf die `kreis2_*`-Helfer um.

## 13. Wie baue ich das Dashboard ein? (Raw-Editor)

Die Datei `dashboard/garten.yaml` ist eine komplette `views:`-Liste für den
Lovelace-Raw-Editor:

1. **Eigenes Dashboard (empfohlen):** Einstellungen → Dashboards →
   „Dashboard hinzufügen“ → „Neues Dashboard von Grund auf“ → öffnen →
   Stift-Symbol (Bearbeiten) → ⋮ oben rechts → **„Raw-Konfigurationseditor“**
   → gesamten Inhalt durch den Inhalt von `dashboard/garten.yaml` ersetzen →
   speichern.
2. **In ein bestehendes Dashboard:** im Raw-Editor NUR den Eintrag unterhalb
   von `views:` (den Block ab `- title: Garten`) in deine bestehende
   `views:`-Liste kopieren.

Danach gilt:

- **Tier 1 funktioniert sofort**, wenn das Package installiert und HA neu
  gestartet ist — es referenziert ausschließlich Package-Entities und native
  Karten (keine HACS-Abhängigkeiten). Zeigt eine Zeile „—“, fehlt nur das
  optionale Volumen-Tracking (Absicht, kein Fehler).
- **Tier 2 (Abschnitt „HARDWARE“) ist auskommentiert.** Erst die
  `REPLACE_ME_VENTIL_1..4`- und `REPLACE_ME_BODENSENSOR_1..4`-Marker durch
  deine echten Entity-IDs ersetzen, DANN die `#` entfernen. Ein
  einkommentierter Block mit übrig gebliebenem `REPLACE_ME_…` erzeugt rote
  Fehlerkarten.
- Der Raw-Editor validiert beim Speichern — bei einer YAML-Fehlermeldung ist
  fast immer die Einrück-Tiefe beim Kopieren verrutscht (der `- title:`-Block
  muss exakt eine Ebene unter `views:` stehen).

## 14. Wie aktualisiere oder deinstalliere ich das Kit?

**Update:**

- **Blueprints:** Einstellungen → Automationen & Szenen → Tab „Blueprints“ →
  ⋮ am jeweiligen Blueprint → **„Blueprint neu importieren“** (gleiche
  Quell-URL). Bestehende Instanzen behalten ihre Eingaben; neue Eingaben
  einer neuen Version bekommen deren Standardwerte. Danach die Instanzen
  einmal öffnen und speichern schadet nie.
- **Package:** neue `packages/bewaesserung.yaml` über die alte kopieren → HA
  neu starten. Deine **eingestellten Helfer-WERTE bleiben erhalten** (HA
  restauriert Helfer-Zustände beim Start), solange die Helfer-Schlüssel
  gleich heißen. Das Seed-Script danach **nicht** erneut ausführen — es ist
  ein bewusster „Werks-Reset“ und überschreibt dein Tuning.
- **Dashboard:** neue Datei erneut per Raw-Editor einspielen; deine
  Tier-2-Marker-Ersetzungen musst du dabei erneut vornehmen (vorher
  rauskopieren).

**Deinstallation (Reihenfolge wichtig):**

1. **Blueprint-Instanzen löschen:** Einstellungen → Automationen — alle
   Kit-Automationen entfernen. (Tipp: auf der Blueprint-Seite zeigt jeder
   Blueprint seine Instanzen.)
2. **Blueprints löschen:** Tab „Blueprints“ → ⋮ → Löschen. Geht erst, wenn
   keine Instanz mehr existiert — HA weigert sich sonst.
3. **Dashboard-Ansicht entfernen** (Raw-Editor oder Dashboard löschen).
4. **Package entfernen:** die Zeile `bewaesserung: !include packages/bewaesserung.yaml`
   aus der `configuration.yaml` nehmen, Datei löschen, HA neu starten — alle
   Kit-Helfer, die Reset-Automation und das Seed-Script verschwinden damit.
5. **Reste:** Per UI angelegte Volumen-Helfer (Integral + Verbrauchszähler
   aus dem README-Rezept) von Hand löschen (Einstellungen → Geräte & Dienste
   → Helfer). Historien-Daten der gelöschten Entities altern über die
   normale Recorder-Aufbewahrung heraus; wer sie sofort loswerden will:
   Aktion `recorder.purge_entities`.

## 15. iOS vs. Android — was ist bei den Pushes anders?

Die Kit-Pushes benutzen einen einheitlichen Payload, der auf beiden
Plattformen funktioniert. Die Unterschiede im Detail:

- **`push_kritisch` (zeitkritisch):** setzt iOS
  `interruption-level: time-sensitive` — die Nachricht durchbricht
  Fokus-Modi/„Nicht stören“ (aber NICHT die Stummschaltung; es ist bewusst
  keine „Critical Notification“ mit Ton-Zwang). Damit das greift, muss in den
  iOS-Einstellungen → Mitteilungen → Home Assistant „Zeitkritische
  Mitteilungen" erlaubt sein. **Android ignoriert das Feld komplett und
  harmlos** — dort steuerst du die Wichtigkeit über den
  Benachrichtigungskanal des Geräts (Systemeinstellungen → Apps → Home
  Assistant → Benachrichtigungen).
- **`dashboard_pfad` (Deep-Link):** Der Payload setzt `url` (iOS) UND
  `clickAction` (Android) auf denselben Pfad — ein Tipp auf den Push öffnet
  die Companion-App direkt auf diesem Dashboard, auf beiden Plattformen.
  **Stolperfalle:** Der Pfad muss ein GÜLTIGER Lovelace-Pfad sein (so wie er
  in der Browser-URL steht, z. B. `/garten-bewaesserung` oder
  `/dashboard-garten/wasser`). Bei einem ungültigen Pfad öffnet die App
  **stumm** das Standard-Dashboard — es gibt keine Fehlermeldung, weder in
  der App noch im HA-Log. Wenn dein Deep-Link „nicht funktioniert“, ist es
  praktisch immer ein Tippfehler im Pfad.
- Beide Apps brauchen naturgemäß eine erreichbare HA-Instanz für die
  Zustellung (iOS via Apple Push über den HA-Cloud-Relay der Companion-App,
  Android via Firebase oder lokalen Push).

## 16. Not-Aus per Webhook / Apple-Kurzbefehl auslösen (Rezept)

Der Not-Aus-Blueprint hat **bewusst nur den Button-Trigger** (ein optionaler
Webhook-Trigger ist in Blueprints technisch nicht sauber abbildbar — ein
leerer `webhook_id` wäre eine ungültige Trigger-Konfiguration). Von unterwegs
(Apple-Kurzbefehl, Widget, Kurzautomation) löst du ihn über eine
Mini-Automation aus, die deine Not-Aus-Instanz direkt triggert:

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
    - action: automation.trigger
      target:
        entity_id: automation.DEINE_NOT_AUS_INSTANZ
```

**So findest du die Entity-ID deiner Not-Aus-Instanz** (der Platzhalter oben):
Die ID leitet sich aus dem NAMEN ab, den du der Instanz beim Anlegen gegeben
hast — Umlaute werden dabei verstümmelt („Bewässerung Not-Aus“ wird zu
`automation.bewasserung_not_aus`, mit nur einem „a“!). Verlass dich nicht auf
Raten: Einstellungen → Automationen & Szenen → Instanz öffnen → ⋮ →
„Informationen“ zeigt die Entity-ID — oder „Entwicklerwerkzeuge → Zustände“
nach `automation.` filtern und den Alias suchen. (Nachträgliches Umbenennen
der Automation ändert die Entity-ID übrigens NICHT.)

**Wichtige Hinweise:**

- Die `webhook_id` ist das einzige Passwort dieses Endpunkts — nimm eine
  lange Zufalls-ID (z. B. 32 Hex-Zeichen), niemals `notaus` o. ä. Aufruf:
  `POST https://deine-ha-adresse/api/webhook/<deine-id>` — im
  Apple-Kurzbefehl: „Inhalte von URL abrufen“, Methode POST.
- `local_only: false` nur setzen, wenn der Aufruf wirklich von außerhalb
  deines LANs kommt — HA verwirft externe Aufrufe an lokale Webhooks sonst
  **stillschweigend** (nur eine Debug-Zeile im Log, der Kurzbefehl sieht
  trotzdem Erfolg).
- `automation.trigger` startet die Aktionen der Not-Aus-Instanz direkt — das
  Verhalten ist identisch zum Buttondruck (Lauf-Flag aus, alle Ventile
  retry-schließen, Push).
- Gleichwertige Alternative ohne Instanz-ID-Suche: statt `automation.trigger`
  einfach den Paket-Button drücken —
  `action: input_button.press`, `target.entity_id: input_button.bewaesserung_not_aus`.
  Das triggert dieselbe Not-Aus-Instanz über ihren regulären Button-Trigger.

## 17. Topf-Frequenzbewässerung: Wer setzt den Dosen-Zähler zurück? (Zähler-Kontrakt)

**Der Blueprint erhöht den Zähler nur — zurücksetzen tut ihn das Package.**
Das ist ein bewusster Kontrakt:

- Die Topf-Frequenzbewässerung zählt jede Dosis in den Helfer
  (`input_number.bewaesserung_kreisN_dosen_heute`) und verweigert weitere
  Dosen, sobald das Tages-Limit (Seed: 4) erreicht ist. Der Zähler erhöht
  sich übrigens auch, wenn das Ventil beim Öffnen nicht reagiert — Absicht:
  ein wild „nachfeuernder“ Kreis bei Funkproblemen wäre gefährlicher als
  eine verpasste Dosis.
- Die Package-Automation `bewaesserung_system_reset` setzt **alle vier**
  `kreisN_dosen_heute`-Zähler täglich um **00:01** auf 0 (gemeinsam mit den
  Tagesdauern und dem Skip-Toggle).
- **Verwendest du einen EIGENEN Zähler-Helfer** (nicht die Package-Helfer,
  z. B. für einen selbstgebauten Kreis 5), musst du auch einen eigenen
  täglichen Reset bauen — sonst steht der Zähler am zweiten Tag noch auf 4
  und **das Tages-Limit blockiert ab Tag 2 dauerhaft jede weitere Dose.**
  Genau dieser stille Ausfallmodus ist der Grund für diesen FAQ-Eintrag.

Mini-Reset für eigene Zähler (an die Reset-Zeit des Packages angelehnt):

```yaml
- alias: "Bewaesserung Kreis 5 Dosen-Reset"
  triggers:
    - trigger: time
      at: "00:01:00"
  actions:
    - action: input_number.set_value
      target:
        entity_id: input_number.bewaesserung_kreis5_dosen_heute
      data:
        value: 0
```

Diagnose-Tipp: Wenn ein Topf „seit gestern keine Dosen mehr bekommt“, prüfe
als Erstes den Zählerstand auf dem Dashboard — steht er auf dem Limit, fehlt
der Reset.

## 18. Trocken-Report: Ich will die exakte 23-h-Persistenz-Prüfung des Originals (history_stats-Rezept)

Der Trocken-Report-Blueprint prüft den **Momentanwert** zum Report-Zeitpunkt
plus den „kürzlich bewässert“-Dämpfer (siehe seine Beschreibung — die
Abweichung vom Original ist dort offengelegt). Das Original prüfte strenger:
*„lag der Boden ≥ 23 der letzten 24 Stunden durchgehend unter der Schwelle?“*
— unempfindlich gegen kurze Morgen-Ausreißer. Das braucht zwei
Zusatz-Sensoren pro Pflanze plus eine kleine Automation (hier für eine
Tomate mit Schwelle 35 %):

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
Die Trocken-Report-Blueprint-Instanz kannst du dann weglassen — oder
parallel weiterlaufen lassen (der Blueprint bündelt mehrere Pflanzen in
einen Push, das Rezept hier pusht pro Pflanze).

## 19. Kann ich kurz vor Mitternacht bewässern?

Besser nicht mit Startzeiten ab ~23:40. Der Grund: Das Package setzt um **00:01**
alle Tages-Helfer zurück (geplante Dauern auf 0, „Lauf aktiv“ aus) — ein Plan-Lauf,
der über Mitternacht hinausläuft, wird dadurch entwaffnet: noch nicht gestartete
Kreise lesen Dauer 0 und werden übersprungen, und für bereits offene Ventile
übernimmt der Auto-Aus-Backstop bzw. der Notaus-Watchdog das Schließen (es bleibt
also nichts offen — aber der Plan wird nicht zu Ende bewässert). Mit den
Standardwerten (Startzeit 21:00, Max-Dauern ≤ 20 min) ist das nie ein Thema.
