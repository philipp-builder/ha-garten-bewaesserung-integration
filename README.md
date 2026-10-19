<img src="https://raw.githubusercontent.com/philipp-builder/ha-garten-bewaesserung-integration/main/assets/icon.png" width="96" height="96" alt="Score Irrigation: Wassertropfen mit Setzling">

# Garten-Bewässerung — Score Irrigation

**Bewässere Rasen, Beete und Töpfe nach Bedarf — mit deinen vorhandenen Home-Assistant-Geräten.**

Score Irrigation verbindet Bodenfeuchte und Wettervorhersage mit deinen
Bewässerungsventilen. Rasen erhält eine berechnete Laufzeit zum gewählten Termin;
Töpfe bekommen kleine, sensorgesteuerte Dosen. Du siehst jederzeit, **warum ein
Kreis bewässert wird — oder warum nicht**.

Einrichtung per Oberfläche · mehrere Kreise · native HA-Steuerelemente · MIT / Open Source

*Garden irrigation for Home Assistant: soil moisture, weather-based lawn watering
and drip irrigation, with explainable decisions and independent winter pauses.*
[English overview](https://philipp-builder.github.io/ha-garten-bewaesserung-integration/)

**Loslegen:** In HACS nach **„Score Irrigation“** suchen und herunterladen.
Voraussetzungen und die ersten Schritte stehen direkt unten.

## Passt das zu deinem Garten?

- **Rasen und Beete:** Bodenfeuchte, Temperaturvorhersage und Zeit seit der letzten
  Bewässerung bestimmen den Score und die Laufzeit. Regen-Vetos können einen Lauf
  aussetzen. Rasen ist auch bewusst ohne Bodensensor konfigurierbar.
- **Töpfe und Tropfbewässerung:** Kleine Dosen halten die gemessene Bodenfeuchte
  in einem einstellbaren Sollband — mit Tageslimit, Mindestabstand und Nachtruhe.
- **Mehrere Kreise:** Ventile nacheinander oder in konfigurierten Gruppen parallel
  betreiben. Startzeit, Dauergrenzen und Pausen direkt in HA einstellen.
- **Nachvollziehbar statt Blackbox:** Status mit Begründung, Tagesplan und Kalender.
  Optional Wasserverbrauch und Kosten aus einem echten Wasserzähler.
- **Saisonwechsel ohne Fehlalarme:** Bewässerung und Bodensensoren unabhängig
  pausieren, auch je Kreis und mit Enddatum. Sicherheitsalarme bleiben aktiv.

Die Berechnung läuft in Home Assistant, ohne zusätzlichen Dienst oder Account.
Ob Wetter und Geräte eine Cloud benötigen, hängt von **deren** Integration ab.
Es ist eine regelbasierte Steuerung, kein selbstlernendes KI-Modell und kein
Versprechen einer bestimmten Wasserersparnis.

## Was du brauchst

| Voraussetzung | Unterstützt / zu beachten |
|---|---|
| Home Assistant + HACS | HA ab 2025.8.0; Installation über HACS |
| Wetter | Eine `weather.*`-Entität mit nutzbarer Vorhersage; standardmäßig tägliche Vorhersage |
| Ventile | Bereits in HA steuerbare `switch.*`-Entitäten. `valve.*` benötigt einen Template-Switch; [Anleitung in der FAQ](https://github.com/philipp-builder/ha-garten-bewaesserung-integration/blob/main/docs/FAQ.md). Kein direkter Ersatz für eine herstellerspezifische Geräteintegration. |
| Bodenfeuchte | Sensorwerte in Prozent (0–100). Für Rasen optional, für Topf-Dosen erforderlich. Konfigurierte Sensoren müssen nach Start/Freigabe neu und gültig melden. |
| Optional | Regenmessung, Globalstrahlung, kumulativer Wasserzähler, Leck-/Versorgungs-/Batteriesensoren, HA-Benachrichtigungsdienste |

Die Bedienung und Statusmeldungen sind überwiegend **Deutsch**; Setup-Dialoge
gibt es auch auf Englisch. Es werden keine eigenen Dashboard-Karten benötigt.
Ventile, Druck und Durchfluss müssen zu deiner Anlage passen; Software kann ein
mechanisch defektes Ventil oder einen ausgefallenen Funkaktor nicht sicher schließen.

## Installation und erster Kreis

1. **HACS öffnen**, nach **„Score Irrigation“** oder **„Garten-Bewässerung“**
   suchen → **Herunterladen**. Die Integration ist im HACS-Standardkatalog.
2. **Home Assistant neu starten**, nachdem der Download abgeschlossen ist.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen** →
   **Garten-Bewässerung — Score Irrigation**. Wetter-Entität auswählen.
4. In den **Optionen** der Integration **Kreis hinzufügen**: Rasen/Beet oder
   Topf/Tropf wählen, Ventile und passende Sensoren zuordnen.
5. **Startzeit, Dauergrenzen und Ausführung prüfen**, bevor du die Anlage
   unbeaufsichtigt betreibst. Bei parallelen Kreisen reicht der Wasserdruck
   möglicherweise nicht für alle Ventile.
6. Native Status-, Zeit- und Schalter-Entities über den HA-Dashboard-Editor
   hinzufügen. Einen ersten kurzen Lauf **beaufsichtigen**, Schließen der Ventile
   kontrollieren und den Benachrichtigungs-Test verwenden, falls Pushes konfiguriert sind.

Noch kein Suchtreffer? Den HACS-Katalog aktualisieren. Als Alternative lässt sich
`https://github.com/philipp-builder/ha-garten-bewaesserung-integration`
unter **Benutzerdefinierte Repositories**, Kategorie **Integration**, hinzufügen.

[Ausführliche Einrichtung & Entity-Referenz](https://github.com/philipp-builder/ha-garten-bewaesserung-integration/blob/main/docs/INSTALLATION.md)
· [FAQ & Hardware-Rezepte](https://github.com/philipp-builder/ha-garten-bewaesserung-integration/blob/main/docs/FAQ.md)

## So entscheidet die Bewässerung

Für Rasen berechnet die Integration alle 30 Minuten einen **Score von 0 bis 100**
aus Boden-Trockenheit, Temperaturvorhersage und Tagen seit der letzten Bewässerung.
Daraus entsteht eine Laufzeit innerhalb deiner Grenzen. Regen, Pausen und weitere
Sperren werden zusätzlich geprüft: Ein hoher Score allein erzwingt keinen Lauf.

Ein Status kann beispielsweise erklären: **„Score 76 → 16 min“** und die verwendeten
Boden- und Wetterwerte zeigen. Das ist ein Beispiel, keine Empfehlung für jede Anlage.

Optional ersetzt **Referenzverdunstung ET₀ nach Hargreaves** den Temperaturfaktor.
Topf-Kreise nutzen dagegen ein Feuchte-Sollband und kurze Dosen. Kalender,
Dosen-Zähler und Statusattribute zeigen, was geplant ist und warum eine Dosis wartet.

## Im Alltag

| Du möchtest … | Dafür gibt es … |
|---|---|
| Den Garten steuern | Native Zeit-, Zahlen-, Schalter- und Button-Entities; kein YAML für das normale Setup |
| Heute aussetzen | „Heute überspringen“ mit automatischer Rücksetzung am nächsten Tag |
| Urlaub oder Winterpause | Gespeicherte Bewässerungspause, optionales Enddatum und wählbare Freigabe/Erinnerung |
| Sensoren früher einlagern oder später zurückbringen | Eigenen Bodensensor-Betrieb für Garten und einzelne Kreise, unabhängig von der Bewässerungspause |
| Sehen, was passiert | Tagesplan, begründeter Kreisstatus und Bewässerungskalender |
| Meldungen erhalten | Plan-Pushes, Trockenberichte, Sicherheitsmeldungen und Test-Benachrichtigung nach Konfiguration |
| Verbrauch verfolgen | Mit kumulativem Wasserzähler: Liter, Monatskosten und Wasser-Statistiken fürs HA-Energie-Dashboard |

**Pausen sind keine bloße Benachrichtigungs-Stummschaltung:** Eine aktive
Bewässerungspause sperrt auch Sofortstarts und Topf-Dosen. Im Winter gilt
standardmäßig „Nur erinnern“ statt unbeaufsichtigtem Wiederanlauf.
Eingelagerte Bodensensoren liefern keine erfundenen Ersatzwerte. Fehlende
konfigurierte Bodenwerte sperren standardmäßig; nur für Rasen ist ausdrücklich
gewählter Wetterbetrieb möglich.

[Urlaub, Winterpause und Sensor-Einlagerung einrichten](https://github.com/philipp-builder/ha-garten-bewaesserung-integration/blob/main/docs/PAUSES.md)

## Sicherheit und Grenzen

Schließversuche mit Wiederholungen, Laufzeit-Watchdog, Neustart-Prüfung offener
Ventile und ein Not-Aus ergänzen die normalen Laufzeitgrenzen. Leck- und
Versorgungsalarme benötigen die entsprechenden Sensoren und konfigurierte
Benachrichtigungen. Pausen unterdrücken Routine-Plan-/Trockenmeldungen,
**nicht** Sicherheitsalarme.

Die Integration steuert die ihr zugeordneten Ventile. Weise ihr keine Schalter
zu, die inzwischen für andere Zwecke verwendet werden. Fremde Sensor-Entities
werden beim Einlagern weder deaktiviert noch aus anderen Health-Dashboards
entfernt. Deren Überwachung muss die Sensorpause selbst berücksichtigen.

## Hilfe, Updates und Mitmachen

- **Einrichten und nachschlagen:** [Bedienung & Entities](https://github.com/philipp-builder/ha-garten-bewaesserung-integration/blob/main/docs/INSTALLATION.md),
  [FAQ](https://github.com/philipp-builder/ha-garten-bewaesserung-integration/blob/main/docs/FAQ.md),
  [Sensor-Saison im Detail](https://github.com/philipp-builder/ha-garten-bewaesserung-integration/blob/main/docs/SENSOR_SEASON.md).
- **Änderungen vor einem Update prüfen:** [Release Notes](https://github.com/philipp-builder/ha-garten-bewaesserung-integration/releases).
  Seit v1.10.0 erfordern konfigurierte Bodensensoren nach Neustart/Freigabe neue
  gültige HA-Meldungen; der frühere fiktive 50-%-Ersatzwert entfällt.
- **Fehler melden oder Verbesserung vorschlagen:** [GitHub Issues](https://github.com/philipp-builder/ha-garten-bewaesserung-integration/issues).
  Bitte Version, erwartetes Verhalten und bereinigte Fehlermeldung angeben —
  keine Zugangsdaten oder privaten Gerätedaten.
- **Weiterentwickeln:** [Architektur](https://github.com/philipp-builder/ha-garten-bewaesserung-integration/blob/main/docs/ARCHITECTURE.md).
  CI prüft Score, Pausen, Sensor-Saison und synthetische Ventilabläufe,
  einschließlich Tests in einer echten HA-Laufzeit, sowie HACS und hassfest.

Aktionen für eigene Automationen: `jetzt_bewaessern`, `not_aus`,
`plan_neu_berechnen`, `dosis_geben` und `pause_setzen` unter
`garten_bewaesserung`. Pausen und Sicherheitsprüfungen gelten weiterhin.

[MIT-Lizenz](https://github.com/philipp-builder/ha-garten-bewaesserung-integration/blob/main/LICENSE)
· [Produktübersicht Deutsch](https://philipp-builder.github.io/ha-garten-bewaesserung-integration/de/)
· [English overview](https://philipp-builder.github.io/ha-garten-bewaesserung-integration/)
