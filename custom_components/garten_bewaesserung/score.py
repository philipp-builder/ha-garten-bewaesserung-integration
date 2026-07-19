"""Reine Score-/Dauer-/Status-Berechnung — 1:1-Parität zum Blueprint B1.

Bewusst OHNE Home-Assistant-Imports (auch keine relativen Paket-Imports):
das Modul ist standalone testbar (`python3 tests/test_score.py`), weil das
Paket-`__init__.py` sonst HA-Module ziehen würde. Der Controller füttert
alle Werte explizit hinein.

Rundung: Jinjas `round()` rundet kaufmännisch (half-up), Pythons `round()`
bankers. Für exakte Parität nutzen alle Rundungen hier `_runde()`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

FALLBACK_BODEN = 50.0
FALLBACK_TMAX = 20.0
NIE_BEWAESSERT_TAGE = 999.0


def _runde(x: float) -> int:
    """Kaufmännisch runden wie Jinja `round(0) | int` (half-up, x >= 0)."""
    return int(math.floor(x + 0.5))


def _runde1(x: float) -> float:
    """Kaufmännisch auf 1 Nachkommastelle wie Jinja `round(1)`."""
    return math.floor(x * 10 + 0.5) / 10


def sicher_float(wert: Any, fallback: float) -> float:
    """Jinja-`float(x, fallback)`-Semantik: None/Unfug ⇒ Fallback."""
    try:
        if wert is None or (isinstance(wert, str) and wert.strip() == ""):
            return fallback
        return float(wert)
    except (TypeError, ValueError):
        return fallback


@dataclass(frozen=True)
class ScoreParameter:
    """Formel-Parameter (Options-`score`-Block; Defaults = Kit-Seed)."""

    gewicht_boden: float = 60
    gewicht_temp: float = 20
    gewicht_tage: float = 20
    skip_schwelle: float = 25
    temp_anker: float = 15.0
    temp_spanne: float = 15.0
    tage_saettigung: float = 7
    # Temperatur-Faktor-Quelle: "tmax" (Kit-Verhalten) oder "et0" —
    # Referenz-Verdunstung nach Hargreaves statt bloßer Maximaltemperatur.
    temp_quelle: str = "tmax"
    et0_anker: float = 2.0  # mm/Tag ⇒ Faktor 0
    et0_spanne: float = 5.0  # mm/Tag über Anker ⇒ Faktor 100 (also bei 7 mm/Tag)


@dataclass(frozen=True)
class ScoreEingabe:
    """Roh-Größen eines Kreises zum Berechnungszeitpunkt."""

    boden: float | None  # Minimum über die Sensoren; None = keine konfiguriert
    tmax: float
    wetter_ok: bool
    tage_seit: float  # NIE_BEWAESSERT_TAGE = nie gestempelt
    veto_schwelle: float
    min_dauer: float
    max_dauer: float
    skip: bool = False
    urlaub: bool = False
    aggressiv: bool = False
    regen_beobachtet: float | None = None  # None = kein Regen-24h-Sensor
    regen_beobachtet_schwelle: float = 3.0
    regen_forecast: float = 0.0
    regen_forecast_schwelle: float = 1.5
    et0: float | None = None  # mm/Tag (Hargreaves); None = nicht ermittelbar
    temp_quelle_kreis: str = "global"  # "global" | "tmax" | "et0" (Kreis-Override)


@dataclass(frozen=True)
class ScoreErgebnis:
    score: int
    dauer: int
    status: str
    faktoren: dict[str, Any] = field(default_factory=dict)


def extrahiere_wetter(
    forecast: list[dict[str, Any]] | None, typ: str
) -> tuple[float, float, bool]:
    """(tmax, regen_forecast, wetter_ok) aus einer Vorhersage-Liste — B1-Schritt 3.

    daily: Tmax über 3 Tage, Regen = erster Tag. hourly: Tmax über 72 h,
    Regen = Summe der ersten 24 h. Leer/None ⇒ Fallbacks (20 °C, 0 mm).
    """
    if not forecast:
        return (FALLBACK_TMAX, 0.0, False)
    if typ == "hourly":
        tmax = max(sicher_float(f.get("temperature"), FALLBACK_TMAX) for f in forecast[:72])
        regen = sum(sicher_float(f.get("precipitation"), 0.0) for f in forecast[:24])
    else:
        tmax = max(sicher_float(f.get("temperature"), FALLBACK_TMAX) for f in forecast[:3])
        regen = sicher_float(forecast[0].get("precipitation"), 0.0)
    return (tmax, regen, True)


def extrahiere_regen_datenbasis(
    forecast: list[dict[str, Any]] | None, typ: str
) -> list[dict[str, Any]] | None:
    """Die exakten Forecast-Zeilen hinter `regen_forecast` — Glass-Box.

    Gleiche Slice- und Float-Semantik wie extrahiere_wetter (hourly: erste
    24 Einträge, daily: erster Eintrag), damit die Summe der `mm`-Werte
    konstruktionsbedingt dem Veto-Wert entspricht. Fürs Debugging als
    Attribut von sensor.garten_plan_heute gedacht.
    """
    if not forecast:
        return None
    zeilen = forecast[:24] if typ == "hourly" else forecast[:1]
    return [
        {
            "t": str(f.get("datetime", "?")),
            "mm": sicher_float(f.get("precipitation"), 0.0),
        }
        for f in zeilen
    ]


def extrahiere_tagestemperaturen(
    forecast: list[dict[str, Any]] | None, typ: str
) -> list[tuple[float, float]]:
    """(Tmax, Tmin) je Tag für bis zu 3 Tage — Grundlage der ET₀-Berechnung.

    daily: temperature/templow je Eintrag (Einträge ohne templow werden
    übersprungen — manche Wetter-Integrationen liefern keins). hourly:
    24-h-Blöcke über 72 h; ein Block zählt ab 12 vorhandenen Stundenwerten.
    """
    if not forecast:
        return []
    tage: list[tuple[float, float]] = []
    if typ == "hourly":
        temps: list[float] = []
        for f in forecast[:72]:
            try:
                temps.append(float(f.get("temperature")))
            except (TypeError, ValueError):
                continue
        for i in range(0, len(temps), 24):
            block = temps[i:i + 24]
            if len(block) >= 12:
                tage.append((max(block), min(block)))
    else:
        for f in forecast[:3]:
            try:
                tage.append((float(f.get("temperature")), float(f.get("templow"))))
            except (TypeError, ValueError):
                continue
    return tage


def berechne_et0_hargreaves(
    breite_grad: float, tag_des_jahres: int, tmax: float, tmin: float
) -> float:
    """Referenz-Verdunstung ET₀ in mm/Tag nach Hargreaves-Samani.

    Extraterrestrische Strahlung Ra aus Breitengrad + Kalendertag
    (FAO-56 Gl. 21-25; validiert gegen das FAO-Beispiel J=246/φ=-20°
    ⇒ Ra = 32.2 MJ/m²/Tag), dann ET₀ = 0.0023 · Ra · (Tmean+17.8) · √ΔT.
    Braucht weder Feuchte- noch Wind-Daten — nur Tmax/Tmin der Vorhersage.
    """
    phi = math.radians(breite_grad)
    j = 2 * math.pi * tag_des_jahres / 365
    dr = 1 + 0.033 * math.cos(j)
    delta = 0.409 * math.sin(j - 1.39)
    # Polarnacht/-tag: cos-Argument einklemmen statt Domain-Fehler
    omega = math.acos(min(1.0, max(-1.0, -math.tan(phi) * math.tan(delta))))
    ra_mj = (24 * 60 / math.pi) * 0.0820 * dr * (
        omega * math.sin(phi) * math.sin(delta)
        + math.cos(phi) * math.cos(delta) * math.sin(omega)
    )
    tmean = (tmax + tmin) / 2
    return max(
        0.0, 0.0023 * 0.408 * ra_mj * (tmean + 17.8) * math.sqrt(max(0.0, tmax - tmin))
    )


def mittlere_et0(
    breite_grad: float, tag_des_jahres: int, tage: list[tuple[float, float]]
) -> float | None:
    """Mittleres ET₀ über die Vorhersage-Tage (Kalendertag läuft mit)."""
    if not tage:
        return None
    werte = [
        berechne_et0_hargreaves(breite_grad, tag_des_jahres + i, tmax, tmin)
        for i, (tmax, tmin) in enumerate(tage)
    ]
    return sum(werte) / len(werte)


def berechne_score(e: ScoreEingabe, p: ScoreParameter) -> ScoreErgebnis:
    """Score, Dauer und Status-Text — exakt die B1-Schritte 4/5."""
    boden_konfiguriert = e.boden is not None
    boden = e.boden if boden_konfiguriert else FALLBACK_BODEN

    # ET₀-Modus nur mit gültigem Wetter + berechenbarem Wert — sonst
    # fällt der Faktor auf den bewährten Tmax-Pfad zurück. Ein Kreis kann
    # die globale Quelle übersteuern (z. B. ET₀ nur für den Rasen).
    quelle = (
        e.temp_quelle_kreis
        if e.temp_quelle_kreis in ("tmax", "et0")
        else p.temp_quelle
    )
    et_aktiv = quelle == "et0" and e.et0 is not None and e.wetter_ok
    if et_aktiv:
        temp_faktor = min(max((e.et0 - p.et0_anker) / p.et0_spanne * 100, 0), 100)
    else:
        temp_faktor = min(max((e.tmax - p.temp_anker) / p.temp_spanne * 100, 0), 100)
    tage_faktor = min(e.tage_seit / p.tage_saettigung * 100, 100)
    boden_faktor = max((e.veto_schwelle - boden) * 2, 0)

    if boden_konfiguriert:
        gewicht_summe = max(p.gewicht_boden + p.gewicht_temp + p.gewicht_tage, 1)
        score_roh = _runde(
            (
                boden_faktor * p.gewicht_boden
                + temp_faktor * p.gewicht_temp
                + tage_faktor * p.gewicht_tage
            )
            / gewicht_summe
        )
    else:
        gewicht_summe = max(p.gewicht_temp + p.gewicht_tage, 1)
        score_roh = _runde(
            (temp_faktor * p.gewicht_temp + tage_faktor * p.gewicht_tage) / gewicht_summe
        )

    veto_boden = boden_konfiguriert and boden > e.veto_schwelle
    veto_regen_beobachtet = (
        e.regen_beobachtet is not None
        and e.regen_beobachtet >= e.regen_beobachtet_schwelle
    )
    veto_regen_forecast = e.wetter_ok and e.regen_forecast >= e.regen_forecast_schwelle

    if e.skip or e.urlaub:
        score = 0
    elif e.aggressiv:
        score = 100
    elif veto_regen_beobachtet or veto_regen_forecast or veto_boden:
        score = 0
    else:
        score = min(max(score_roh, 0), 100)

    # Gürtel + Hosenträger (B1): Vetos erzwingen Dauer 0 unabhängig von der
    # Skip-Schwelle (Score-0-Randfall). Aggressiv ist davon ausgenommen —
    # er übersteuert Regen-/Boden-Veto laut Kit-Doku auch bei der Dauer
    # (der ursprüngliche B1-Guard vergaß die Ausnahme; im Kit mitgefixt).
    if e.skip or e.urlaub:
        dauer = 0
    elif not e.aggressiv and (
        veto_regen_beobachtet or veto_regen_forecast or veto_boden
    ):
        dauer = 0
    elif score < p.skip_schwelle:
        dauer = 0
    else:
        dauer = _runde(e.min_dauer + (e.max_dauer - e.min_dauer) * score / 100)

    wetter_hinweis = "" if e.wetter_ok else " (Wetter n/v)"
    boden_anzeige = f"{_runde(boden)} %" if boden_konfiguriert else "—"
    temp_anzeige = (
        f"ET₀ {_runde1(e.et0 or 0.0)} mm" if et_aktiv else f"Tmax {_runde(e.tmax)} °C"
    )
    tage_anzeige = (
        "nie bewässert"
        if e.tage_seit >= NIE_BEWAESSERT_TAGE
        else f"{_runde1(e.tage_seit)} Tage her"
    )

    if e.skip:
        status = f"⏭ Übersprungen: „Heute überspringen“ ist aktiv{wetter_hinweis}"
    elif e.urlaub:
        status = f"⏸ Urlaubsmodus aktiv — keine Bewässerung{wetter_hinweis}"
    elif e.aggressiv:
        status = (
            f"⚡ Aggressiv-Modus: Score 100 → {dauer} min "
            f"(Boden {boden_anzeige}, {temp_anzeige}){wetter_hinweis}"
        )
    elif veto_regen_beobachtet:
        status = (
            f"☔ Regen-Veto: {_runde1(e.regen_beobachtet or 0.0)} mm in 24 h gemessen "
            f"(Schwelle {_runde1(e.regen_beobachtet_schwelle)} mm){wetter_hinweis}"
        )
    elif veto_regen_forecast:
        status = (
            f"☔ Regen-Veto: {_runde1(e.regen_forecast)} mm Vorhersage "
            f"(Schwelle {_runde1(e.regen_forecast_schwelle)} mm)"
        )
    elif veto_boden:
        status = (
            f"💧 Boden feucht genug: {boden_anzeige} über Veto-Schwelle "
            f"{_runde(e.veto_schwelle)} % → 0 min{wetter_hinweis}"
        )
    elif score < p.skip_schwelle:
        status = (
            f"Score {score} unter Schwelle {_runde(p.skip_schwelle)} → 0 min "
            f"(Boden {boden_anzeige}, {temp_anzeige}, {tage_anzeige})"
            f"{wetter_hinweis}"
        )
    else:
        status = (
            f"Score {score} → {dauer} min "
            f"(Boden {boden_anzeige}, {temp_anzeige}, {tage_anzeige})"
            f"{wetter_hinweis}"
        )

    return ScoreErgebnis(
        score=score,
        dauer=dauer,
        status=status,
        faktoren={
            "boden": boden if boden_konfiguriert else None,
            "boden_faktor": round(boden_faktor, 2),
            "temp_faktor": round(temp_faktor, 2),
            "tage_faktor": round(tage_faktor, 2),
            "tmax": e.tmax,
            "et0": _runde1(e.et0) if e.et0 is not None else None,
            "temp_quelle": "et0" if et_aktiv else "tmax",
            "tage_seit": e.tage_seit,
            "wetter_ok": e.wetter_ok,
            "veto_boden": veto_boden,
            "veto_regen_beobachtet": veto_regen_beobachtet,
            "veto_regen_forecast": veto_regen_forecast,
            "skip": e.skip,
            "urlaub": e.urlaub,
            "aggressiv": e.aggressiv,
        },
    )


def baue_plan_uebersicht(
    tmax: float,
    wetter_ok: bool,
    regen_beobachtet: float | None,
    regen_forecast: float,
    kreise: list[tuple[str, float | None]],
    zeit_str: str,
    et0: float | None = None,
) -> str:
    """Kompakte Tages-Übersichtszeile für sensor.garten_plan_heute.

    kreise: Liste (Name, Bodenfeuchte % oder None ohne Sensor).
    Ergebnis ist auf 255 Zeichen gekappt (HA-State-Limit) — die Rohwerte
    stehen ungekürzt in den Sensor-Attributen.
    """
    teile = [f"Tmax3d {_runde(tmax)} °C"]
    if et0 is not None:
        teile.append(f"ET₀ {_runde1(et0)} mm")
    if regen_beobachtet is not None:
        teile.append(
            f"Regen 24h {_runde1(regen_beobachtet)} mm + FC {_runde1(regen_forecast)} mm"
        )
    else:
        teile.append(f"Regen FC {_runde1(regen_forecast)} mm")
    for name, boden in kreise:
        teile.append(f"{name} {_runde(boden)} %" if boden is not None else f"{name} —")
    zeile = " · ".join(teile) + f" — berechnet {zeit_str}"
    if not wetter_ok:
        zeile += " (Wetter n/v)"
    return zeile if len(zeile) <= 255 else zeile[:254] + "…"


def baue_plan_push(
    zeit_str: str, kreise: list[tuple[str, int, int | None]]
) -> tuple[str, str]:
    """(Titel, Nachricht) des Tagesplan-Push — B2-Parität.

    kreise: Liste (Name, Dauer min, Score oder None).
    """
    titel = f"🌱 Garten-Plan heute ({zeit_str})"
    zeilen = []
    for name, dauer, score_wert in kreise:
        if score_wert is not None:
            zeilen.append(f"💧 {name}: {dauer} min (Score {score_wert})")
        else:
            zeilen.append(f"💧 {name}: {dauer} min")
    return (titel, "\n".join(zeilen))
