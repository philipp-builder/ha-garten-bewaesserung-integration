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


def berechne_score(e: ScoreEingabe, p: ScoreParameter) -> ScoreErgebnis:
    """Score, Dauer und Status-Text — exakt die B1-Schritte 4/5."""
    boden_konfiguriert = e.boden is not None
    boden = e.boden if boden_konfiguriert else FALLBACK_BODEN

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
            f"(Boden {boden_anzeige}, Tmax {_runde(e.tmax)} °C){wetter_hinweis}"
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
            f"(Boden {boden_anzeige}, Tmax {_runde(e.tmax)} °C, {tage_anzeige})"
            f"{wetter_hinweis}"
        )
    else:
        status = (
            f"Score {score} → {dauer} min "
            f"(Boden {boden_anzeige}, Tmax {_runde(e.tmax)} °C, {tage_anzeige})"
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
) -> str:
    """Kompakte Tages-Übersichtszeile für sensor.garten_plan_heute.

    kreise: Liste (Name, Bodenfeuchte % oder None ohne Sensor).
    Ergebnis ist auf 255 Zeichen gekappt (HA-State-Limit) — die Rohwerte
    stehen ungekürzt in den Sensor-Attributen.
    """
    teile = [f"Tmax3d {_runde(tmax)} °C"]
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
