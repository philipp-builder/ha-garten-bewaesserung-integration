# Pausen und Sensor-Einlagerung

Bedienung für Garten-Bewässerung — Score Irrigation.
[Zur Übersicht](../README.md) · [Technische Sensor-Saison](SENSOR_SEASON.md)

## Bodensensoren im Winter (ab v1.10.0)

**Sensorpause und Bewässerungspause sind getrennt.** Am Gerät **Garten** und an
jedem Kreis mit Bodensensoren stehen native HA-Steuerelemente bereit:

| Einstellung | Wirkung |
|---|---|
| Bodensensor-Betrieb: Automatisch (Winterpause) | Garten-Standard: folgt einer **aktiven** Bewässerungs-Winterpause. Urlaub allein lagert keine Sensoren ein. |
| Aktiv | Sensoren unabhängig von der Bewässerungspause nutzen; Bewässerung bleibt während ihrer eigenen Pause gesperrt. |
| Eingelagert | Bodenwerte nicht für Planung, Dosen oder Trockenmeldungen verwenden. |
| Garten übernehmen | Standard je Kreis; alternativ für diesen Kreis separat auswählen. |
| Bodensensor-Pausenende + Pause mit Enddatum | Bei „Eingelagert“ zuerst Enddatum setzen, dann Befristung aktivieren. Am Ende wird der Sensorbetrieb aktiv, aber erst nach einer neuen gültigen Meldung nutzbar. |
| Bewässerung ohne Bodenmesswert | Rasen mit konfiguriertem Sensor: standardmäßig **Sperren**. Optional ausdrücklich **Nur Wetter (Rasen)**; für Töpfe nicht verfügbar. |

Der **Bodensensor-Status** zeigt Einlagerung, Warten auf eine neue gültige Messung
oder einen Konfigurationsfehler. Nach Neustart oder Änderung der Sensorsteuerung
werden alte Werte nicht sofort wieder freigegeben. Alle konfigurierten Sensoren
müssen gültige Werte von 0–100 % melden; deaktivierte, wiederhergestellte,
unbekannte, unplausible oder über 24 Stunden alte Meldungen gelten nicht.
Auch eine neue Meldung mit unverändertem Wert zählt. Das ist eine neue
**HA-Meldung**, kein unabhängig bewiesener Funkkontakt/Messzeitpunkt des Geräts.

**Verhaltensänderung:** Der bisherige fiktive 50-%-Ersatzwert bei ausgefallenen
Rasen-Bodensensoren entfällt. Bewusst ohne Bodensensor konfigurierte Rasen-Kreise
bleiben wettergesteuert. Töpfe dosieren nie aufgrund eingelagerter/fehlender Werte.
Die Steuerungsänderung schließt betroffene offene Ventile, verwirft betroffene
wartende Dosen/alte Pläne und startet keinen Nachhol-Lauf. Nicht betroffene Kreise
behalten ihre Einstellungen. Tatsächlich gemessene Wassermengen bleiben erhalten.

Während **jeder aktiven Bewässerungspause** entfallen nun auch die täglichen
08-Uhr-Trockenmeldungen. Sensor-Batteriewarnungen entfallen nur, wenn die
HA-Gerätezuordnung eindeutig ausschließlich eingelagerte Bodensensoren betrifft;
Ventilbatterien, Leck-, Versorgungs- und Schließfehler bleiben überwacht.

Die Integration deaktiviert **keine fremden ZHA-/Zigbee-Entities** und schreibt
keine erfundenen Messwerte. Andere Dashboards/Health-Checker müssen eine absichtliche
Einlagerung selbst berücksichtigen: pro Kreis stehen `monitoring_expected`,
`source_entities`, `status` und `fresh_after` als Attribute bereit. Bei gemeinsam
genutzten Quellen nur ausblenden, wenn **alle** Verbraucher eingelagert sind;
fehlende/fehlerhafte Statusdaten niemals als gesunde Pause behandeln.
Details und Grenzen: [Sensor-Saison](SENSOR_SEASON.md).

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
