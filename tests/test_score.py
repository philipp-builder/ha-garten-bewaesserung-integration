"""Formel-Parität score.py ↔ Blueprint B1/B2 — die Kit-Zahlenbeispiele.

Läuft ohne Home Assistant und ohne pytest:  `python3 tests/test_score.py`
(pytest sammelt die test_*-Funktionen trotzdem ganz normal ein).
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

_PFAD = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components"
    / "garten_bewaesserung"
    / "score.py"
)
_spec = importlib.util.spec_from_file_location("score", _PFAD)
score = importlib.util.module_from_spec(_spec)
sys.modules["score"] = score  # nötig für dataclass-Auflösung (py3.12+)
_spec.loader.exec_module(score)

P = score.ScoreParameter()  # Kit-Defaults 60/20/20, Skip 25, 15/15, 7 d


def _e(**kw):
    basis = dict(
        boden=40.0,
        tmax=30.0,
        wetter_ok=True,
        tage_seit=999.0,
        veto_schwelle=70.0,
        min_dauer=5.0,
        max_dauer=20.0,
    )
    basis.update(kw)
    return score.ScoreEingabe(**basis)


def test_boden_faktor_ankerung():
    """Kit-Doku: Boden AN der Schwelle ⇒ 0; 10 pp darunter ⇒ 20; 30 ⇒ 60."""
    for boden, erwartet in ((70.0, 0.0), (60.0, 20.0), (40.0, 60.0)):
        erg = score.berechne_score(_e(boden=boden), P)
        assert erg.faktoren["boden_faktor"] == erwartet, (boden, erg.faktoren)


def test_referenzfall_score_76():
    """Boden 40/Veto 70 ⇒ 60 · Tmax 30 ⇒ 100 · nie bewässert ⇒ 100 → Score 76."""
    erg = score.berechne_score(_e(), P)
    assert erg.score == 76, erg
    # Dauer = 5 + 15 × 0,76 = 16,4 → 16 (half-up)
    assert erg.dauer == 16, erg
    assert erg.status.startswith("Score 76 → 16 min"), erg.status
    assert "nie bewässert" in erg.status


def test_veto_boden_ueber_schwelle():
    erg = score.berechne_score(_e(boden=75.0), P)
    assert erg.score == 0 and erg.dauer == 0
    assert erg.status.startswith("💧 Boden feucht genug: 75 % über Veto-Schwelle 70 %")


def test_skip_und_urlaub():
    assert score.berechne_score(_e(skip=True), P).status.startswith("⏭")
    assert score.berechne_score(_e(urlaub=True), P).score == 0
    erg = score.berechne_score(_e(urlaub=True), P)
    assert erg.dauer == 0 and erg.status.startswith("⏸")


def test_aggressiv_uebersteuert_regen_aber_nicht_skip():
    erg = score.berechne_score(_e(aggressiv=True, regen_forecast=9.0), P)
    assert erg.score == 100 and erg.dauer == 20  # Max-Dauer
    assert erg.status.startswith("⚡")
    # … aber Skip/Urlaub gewinnen gegen Aggressiv (B1-Veto-Reihenfolge)
    erg = score.berechne_score(_e(aggressiv=True, skip=True), P)
    assert erg.score == 0 and erg.dauer == 0


def test_regen_vetos_inklusive_schwellen_randfall():
    """≥-Vergleich: exakt AN der Schwelle wird schon übersprungen."""
    erg = score.berechne_score(_e(regen_beobachtet=3.0), P)
    assert erg.score == 0 and erg.status.startswith("☔") and "gemessen" in erg.status
    erg = score.berechne_score(_e(regen_forecast=1.5), P)
    assert erg.score == 0 and "Vorhersage" in erg.status
    # Ohne Regen-Sensor (None) ist das Beobachtet-Veto deaktiviert
    erg = score.berechne_score(_e(regen_beobachtet=None), P)
    assert erg.score == 76


def test_wetter_ausfall_fallback_und_hinweis():
    """Wetter n/v ⇒ Tmax 20 (Faktor 33,33), Forecast-Veto aus, Statushinweis."""
    erg = score.berechne_score(
        _e(wetter_ok=False, tmax=20.0, regen_forecast=99.0), P
    )
    # (60×60 + 33,33×20 + 100×20) / 100 = 62,67 → 63
    assert erg.score == 63, erg
    assert erg.status.endswith("(Wetter n/v)"), erg.status


def test_keine_bodensensoren_renormalisierung():
    """boden=None ⇒ Gewichte auf Temp+Tage renormalisiert, kein Boden-Veto."""
    erg = score.berechne_score(_e(boden=None), P)
    # (100×20 + 100×20) / 40 = 100
    assert erg.score == 100 and erg.dauer == 20
    assert "Boden —" in erg.status


def test_skip_schwelle_ergibt_dauer_null():
    """Boden 58/Veto 70 ⇒ 24 · Tmax 15 ⇒ 0 · Tage 0 ⇒ 0 → Score 14 < 25."""
    erg = score.berechne_score(_e(boden=58.0, tmax=15.0, tage_seit=0.0), P)
    assert erg.score == 14, erg
    assert erg.dauer == 0
    assert erg.status.startswith("Score 14 unter Schwelle 25")


def test_rundung_half_up_wie_jinja():
    """62,5 muss auf 63 runden (Jinja half-up), nicht 62 (Python bankers)."""
    # boden=None, temp_faktor 25 (Tmax 18,75), tage_faktor 100 → (25+100)/2 = 62,5
    erg = score.berechne_score(_e(boden=None, tmax=18.75), P)
    assert erg.score == 63, erg


def test_extrahiere_wetter_daily_und_hourly():
    daily = [
        {"temperature": 27, "precipitation": 0.0},
        {"temperature": 29, "precipitation": 0.0},
        {"temperature": 24, "precipitation": 1.2},
        {"temperature": 35, "precipitation": 9.9},  # Tag 4 — darf nicht zählen
    ]
    tmax, regen, ok = score.extrahiere_wetter(daily, "daily")
    assert (tmax, regen, ok) == (29, 0.0, True)

    hourly = [{"temperature": 10 + i * 0.1, "precipitation": 0.1} for i in range(80)]
    tmax, regen, ok = score.extrahiere_wetter(hourly, "hourly")
    assert abs(tmax - 17.1) < 1e-9  # Maximum der ersten 72 h
    assert abs(regen - 2.4) < 1e-9  # Summe der ersten 24 h
    assert ok

    tmax, regen, ok = score.extrahiere_wetter(None, "daily")
    assert (tmax, regen, ok) == (20.0, 0.0, False)
    tmax, regen, ok = score.extrahiere_wetter([], "daily")
    assert ok is False
    # kaputte Werte ⇒ Jinja-float-Fallbacks
    tmax, regen, ok = score.extrahiere_wetter(
        [{"temperature": None, "precipitation": "x"}], "daily"
    )
    assert (tmax, regen, ok) == (20.0, 0.0, True)


def test_dauer_formel_endpunkte():
    erg = score.berechne_score(_e(aggressiv=True), P)
    assert erg.dauer == 20  # Score 100 ⇒ Max
    # Score exakt an der Skip-Schwelle (25) wird bewässert (nur < skippt):
    # boden None, temp 0, tage_faktor 50 (3,5 d) → Score (0×20+50×20)/40 = 25
    erg = score.berechne_score(_e(boden=None, tmax=15.0, tage_seit=3.5), P)
    assert erg.score == 25 and erg.dauer == 9  # 5 + 15×0,25 = 8,75 → 9


def test_plan_push_nachricht():
    titel, text = score.baue_plan_push(
        "21:00", [("Rasen", 16, 76), ("Tomaten", 3, 77), ("Beeren", 4, None)]
    )
    assert titel == "🌱 Garten-Plan heute (21:00)"
    assert text.split("\n") == [
        "💧 Rasen: 16 min (Score 76)",
        "💧 Tomaten: 3 min (Score 77)",
        "💧 Beeren: 4 min",
    ]


def test_plan_uebersicht_zeile():
    z = score.baue_plan_uebersicht(
        26.0, True, 0.4, 1.5, [("Rasen", 42.0), ("Tomaten", 54.4), ("Beet", None)], "15:00"
    )
    assert z == (
        "Tmax3d 26 °C · Regen 24h 0.4 mm + FC 1.5 mm · "
        "Rasen 42 % · Tomaten 54 % · Beet — — berechnet 15:00"
    ), z
    # ohne Regen-24h-Sensor nur Forecast; Wetter-Ausfall wird markiert
    z2 = score.baue_plan_uebersicht(20.0, False, None, 0.0, [("Rasen", 42.0)], "05:30")
    assert z2 == "Tmax3d 20 °C · Regen FC 0.0 mm · Rasen 42 % — berechnet 05:30 (Wetter n/v)", z2
    # 255-Zeichen-Kappung (HA-State-Limit)
    viele = [(f"Kreis-mit-langem-Namen-{i}", 50.0) for i in range(20)]
    z3 = score.baue_plan_uebersicht(26.0, True, None, 0.0, viele, "12:00")
    assert len(z3) == 255 and z3.endswith("…"), len(z3)


def test_hargreaves_et0():
    # Extern vorgerechnete Pins (Ra-Zwischenschritt gegen FAO-56-Beispiel
    # J=246/φ=-20° = 32.2 MJ/m²/Tag validiert): Zürich-Sommer + Winter.
    assert abs(score.berechne_et0_hargreaves(47.4, 199, 29.0, 16.0) - 5.4645) < 0.001
    assert abs(score.berechne_et0_hargreaves(47.4, 15, 5.0, -2.0) - 0.5013) < 0.001
    # ΔT ≤ 0 (Inversionslage/Datenfehler) → 0 statt sqrt-Domain-Fehler
    assert score.berechne_et0_hargreaves(47.4, 100, 10.0, 12.0) == 0.0


def test_tagestemperaturen_daily_und_hourly():
    daily = [
        {"temperature": 27, "templow": 15},
        {"temperature": 29, "templow": 16},
        {"temperature": 24},  # ohne templow → übersprungen
    ]
    assert score.extrahiere_tagestemperaturen(daily, "daily") == [(27.0, 15.0), (29.0, 16.0)]
    hourly = [{"temperature": 10 + (i % 24) / 2} for i in range(48)]
    assert score.extrahiere_tagestemperaturen(hourly, "hourly") == [(21.5, 10.0), (21.5, 10.0)]
    assert score.extrahiere_tagestemperaturen(None, "daily") == []
    assert score.mittlere_et0(47.4, 199, []) is None


def test_score_mit_et0_quelle():
    p_et = score.ScoreParameter(temp_quelle="et0")  # Anker 2, Spanne 5
    erg = score.berechne_score(_e(et0=4.5), p_et)
    assert erg.faktoren["temp_faktor"] == 50.0  # (4.5−2)/5 → 50 statt Tmax-100
    assert erg.faktoren["temp_quelle"] == "et0" and erg.faktoren["et0"] == 4.5
    assert "ET₀ 4.5 mm" in erg.status
    assert erg.score == 66  # (60·60 + 50·20 + 100·20)/100
    # Kein ET₀-Wert (z. B. templow fehlt) → stiller Rückfall auf Tmax
    erg2 = score.berechne_score(_e(), p_et)
    assert erg2.faktoren["temp_quelle"] == "tmax" and erg2.score == 76


def test_temp_quelle_pro_kreis_override():
    p_tmax = score.ScoreParameter()  # global tmax
    p_et = score.ScoreParameter(temp_quelle="et0")
    # Kreis-Override et0 schlägt globales tmax
    erg = score.berechne_score(_e(et0=4.5, temp_quelle_kreis="et0"), p_tmax)
    assert erg.faktoren["temp_quelle"] == "et0" and erg.score == 66
    # Kreis-Override tmax schlägt globales et0
    erg2 = score.berechne_score(_e(et0=4.5, temp_quelle_kreis="tmax"), p_et)
    assert erg2.faktoren["temp_quelle"] == "tmax" and erg2.score == 76
    # "global" (Default) folgt der globalen Einstellung
    erg3 = score.berechne_score(_e(et0=4.5, temp_quelle_kreis="global"), p_et)
    assert erg3.faktoren["temp_quelle"] == "et0" and erg3.score == 66


if __name__ == "__main__":
    fehler = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  PASS {name}")
            except AssertionError as exc:
                fehler += 1
                print(f"  FAIL {name}: {exc}")
    print(f"\n{'ALLE TESTS PASS' if fehler == 0 else str(fehler) + ' FEHLER'}")
    sys.exit(1 if fehler else 0)
