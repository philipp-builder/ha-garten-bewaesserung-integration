"""Konstanten und Defaults der Garten-Bewässerung.

Alle Default-Werte sind die erprobten Seed-Werte der Blueprint-Edition
(produktives 4-Kreis-Referenzsystem) — siehe docs/ARCHITECTURE.md.
"""
from __future__ import annotations

DOMAIN = "garten_bewaesserung"

# --- Options-Keys (Hub) ---
CONF_WETTER = "wetter"
CONF_REGEN_SENSOR = "regen_sensor"
CONF_STRAHLUNG_SENSOR = "strahlung_sensor"
CONF_NOTIFY = "notify_dienste"
CONF_PUSH_KRITISCH = "push_kritisch_alarme"
CONF_DASHBOARD_PFAD = "dashboard_pfad"
CONF_ZEIT = "bewaesserungszeit"
CONF_VORLAUF = "vorlauf_min"
CONF_STANDARD_DAUER = "standard_dauer"
CONF_REGEN_BEOBACHTET = "regen_beobachtet_mm"
CONF_REGEN_FORECAST = "regen_forecast_mm"
CONF_STRAHLUNG_SCHWELLE = "strahlung_schwelle"
CONF_NOTAUS_MIN = "notaus_minuten"
CONF_TARIF = "wasser_tarif"
CONF_WAEHRUNG = "waehrung"
CONF_KREISE = "kreise"

# --- Kreis-Keys ---
CONF_KREIS_ID = "id"
CONF_KREIS_NAME = "name"
CONF_KREIS_TYP = "typ"  # "rasen" | "topf"
CONF_VENTILE = "ventile"
CONF_BODENSENSOREN = "bodensensoren"
CONF_GRUPPE = "gruppe_reihenfolge"
CONF_PARALLEL = "parallel"
CONF_VETO = "veto_schwelle"
CONF_MIN_DAUER = "min_dauer"
CONF_MAX_DAUER = "max_dauer"
CONF_ZIEL_UNTEN = "ziel_unten"
CONF_ZIEL_OBEN = "ziel_oben"
CONF_K_FAKTOR = "k_faktor"
CONF_FLOW_SENSOR = "flow_sensor"
CONF_LECK = "leck_sensoren"
CONF_VERSORGUNG = "versorgung_sensor"
CONF_BATTERIE = "batterie_sensoren"

# --- Defaults (= Kit-Seed-Werte) ---
DEFAULT_ZEIT = "21:00:00"
DEFAULT_VORLAUF = 30
DEFAULT_STANDARD_DAUER = 10
DEFAULT_REGEN_BEOBACHTET = 3.0
DEFAULT_REGEN_FORECAST = 1.5
DEFAULT_STRAHLUNG_SCHWELLE = 600
DEFAULT_NOTAUS_MIN = 40
DEFAULT_RETRY_ANZAHL = 5
DEFAULT_RETRY_ABSTAND_S = 3
DEFAULT_PAUSE_S = 5  # Pause zwischen zwei Ventilen einer Sequenz (B3)

# Feste Engine-Parameter (B6/B8/B9/B10/B12-Defaults; bewusst keine Options)
TOPF_UNTERSCHREITUNG_MIN = 10  # Entprellung unter Sollband-Unterkante (B6)
VERSORGUNG_DEBOUNCE_S = 60  # Versorgung weg für ≥ 1 min (B8)
BATTERIE_SCHWELLE = 20  # % (B10)
BATTERIE_DEBOUNCE_MIN = 30  # unter Schwelle seit … (B10)
BATTERIE_COOLDOWN_H = 24  # max. 1 Batterie-Push pro Tag (B10)
REPORT_STUNDE = 8  # Trocken-Report um 08:00 (B12)
REPORT_DAEMPFER_H = 24  # „kürzlich bewässert“-Dämpfer (B12)
VOLUMEN_SETTLE_S = 30  # Integral-Sensor nachlaufen lassen (B9)
DEFAULT_TARIF = 3.0
DEFAULT_WAEHRUNG = "EUR"

SCORE_DEFAULTS = {
    "gewicht_boden": 60,
    "gewicht_temp": 20,
    "gewicht_tage": 20,
    "skip_schwelle": 25,
    "temp_anker": 15.0,
    "temp_spanne": 15.0,
    "tage_saettigung": 7,
    "forecast_typ": "daily",
}
TOPF_DEFAULTS = {
    "max_dosen": 4,
    "dosis_max_min": 4,
    "min_intervall_min": 90,
    "glitch_grenze": 5,
}
KREIS_TYP_DEFAULTS = {
    # veto, min, max, ziel_unten, ziel_oben (Kit-Seed-Tabelle)
    "rasen": {"veto_schwelle": 70, "min_dauer": 5, "max_dauer": 20},
    "topf": {"veto_schwelle": 65, "min_dauer": 1, "max_dauer": 4,
             "ziel_unten": 45, "ziel_oben": 65, "k_faktor": 2.0},
}

# Fallbacks (B1-Parität — bewusst KEINE Options: greifen nur bei kaputten Quellen)
FALLBACK_BODEN = 50.0
FALLBACK_TMAX = 20.0

# Alle Hub-Entity-Schlüssel (unique_id = "<entry>_<schluessel>") — Grundlage
# für das Registry-Aufräumen beim Setup (verwaiste Kreis-Entities erkennen).
HUB_SCHLUESSEL = {
    "bewaesserungszeit", "heute_ueberspringen", "urlaubsmodus",
    "aggressiv_modus", "topf_steuerung", "not_aus", "sofort_start",
    "plan_neu", "naechster_lauf", "letzter_lauf_bericht",
    CONF_STANDARD_DAUER, CONF_REGEN_BEOBACHTET, CONF_REGEN_FORECAST,
    CONF_STRAHLUNG_SCHWELLE, CONF_TARIF,
}

# Bedingte Kreis-Entity-Schlüssel (unique_id = "<entry>_<kid>_<schluessel>"):
# existieren nur bei erfüllter Bedingung. Das Registry-Aufräumen entfernt sie,
# wenn die Bedingung wegfällt (Typwechsel Topf→Rasen bzw. Flow-Sensor entfernt).
TOPF_KREIS_SCHLUESSEL = {CONF_ZIEL_UNTEN, CONF_ZIEL_OBEN, CONF_K_FAKTOR, "dosen_heute"}
FLOW_KREIS_SCHLUESSEL = {"liter_heute", "liter_monat", "kosten_monat"}

STORE_VERSION = 1
EVENT_LAUF_GESTARTET = f"{DOMAIN}_lauf_gestartet"
EVENT_LAUF_BEENDET = f"{DOMAIN}_lauf_beendet"
EVENT_NOTAUS = f"{DOMAIN}_notaus"

PLATTFORMEN = ["sensor", "number", "switch", "button", "time"]
