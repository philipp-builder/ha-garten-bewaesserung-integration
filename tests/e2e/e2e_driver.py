#!/usr/bin/env python3
"""Integrations-E2E-Treiber: Onboarding -> Config-Flow -> 2x Options-Flow (Kreise)
-> Entity-Assertions. Läuft gegen die ephemere Test-HA auf 127.0.0.1:8124."""
import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

BASE = "http://127.0.0.1:8124"
CLIENT = BASE + "/"
TOKEN = None


def req(path, data=None, method=None, auth=True, raw=False):
    url = BASE + path
    body = None
    headers = {"Content-Type": "application/json"}
    if auth and TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    if data is not None:
        body = data if raw else json.dumps(data).encode()
        if raw:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=30) as resp:
        txt = resp.read().decode()
        return json.loads(txt) if txt else {}


def warte_auf_ha(sekunden=180):
    ende = time.time() + sekunden
    while time.time() < ende:
        try:
            urllib.request.urlopen(BASE + "/api/", timeout=5)
        except urllib.error.HTTPError:
            return  # 401 = API lebt
        except Exception:
            time.sleep(3)
            continue
        return
    sys.exit("HA nicht erreichbar")


def onboarding_token():
    global TOKEN
    d = req(
        "/api/onboarding/users",
        {"client_id": CLIENT, "name": "Test", "username": "test", "password": "test1234", "language": "de"},
        auth=False,
    )
    code = d["auth_code"]
    form = urllib.parse.urlencode(
        {"grant_type": "authorization_code", "code": code, "client_id": CLIENT}
    ).encode()
    tok = req("/auth/token", form, auth=False, raw=True)
    TOKEN = tok["access_token"]
    # restliche Onboarding-Schritte abhaken (best effort)
    for pfad, body in [
        ("/api/onboarding/core_config", {}),
        ("/api/onboarding/analytics", {}),
        ("/api/onboarding/integration", {"client_id": CLIENT, "redirect_uri": CLIENT}),
    ]:
        try:
            req(pfad, body)
        except Exception:
            pass


def flow_abschliessen(fid_path, first_body, schritte):
    """Einen Flow starten und eine Liste von Schritt-Antworten durchspielen."""
    d = req(fid_path, first_body)
    for antwort in schritte:
        fid = d["flow_id"]
        basis = fid_path.rsplit("/", 0)[0]
        d = req(f"{fid_path}/{fid}" if False else f"{'/'.join(fid_path.split('/'))}/{fid}", antwort)
    return d


def main():
    warte_auf_ha()
    onboarding_token()
    print("Onboarding OK, Token da")

    # Wetter-Entity finden — YAML-Plattformen brauchen nach Onboarding einen Moment
    wetter = None
    ende = time.time() + 90
    while time.time() < ende:
        states = req("/api/states")
        wetter = next(
            (s["entity_id"] for s in states if s["entity_id"].startswith("weather.")), None
        )
        if wetter and any(s["entity_id"] == "switch.testventil_1" for s in states):
            break
        time.sleep(3)
    if not wetter:
        print("DIAGNOSE — vorhandene Entities:")
        for s in sorted(x["entity_id"] for x in states):
            print("  ", s)
        sys.exit("keine weather-Entity in der Test-HA")
    print("Wetter:", wetter)

    # ---- Config-Flow (Hub) ----
    d = req("/api/config/config_entries/flow", {"handler": "garten_bewaesserung"})
    assert d.get("step_id") == "user", d
    d = req(f"/api/config/config_entries/flow/{d['flow_id']}", {"wetter": wetter})
    assert d.get("type") == "create_entry", d
    entry_id = d["result"]["entry_id"]
    print("Hub angelegt:", entry_id)

    def options_flow(schritte):
        f = req("/api/config/config_entries/options/flow", {"handler": entry_id})
        for antwort in schritte:
            f = req(f"/api/config/config_entries/options/flow/{f['flow_id']}", antwort)
        return f

    # ---- Kreis 1: Rasen mit 2 Ventilen ----
    f = options_flow(
        [
            {"next_step_id": "kreis_hinzufuegen"},
            {
                "name": "Rasen",
                "typ": "rasen",
                "ventile": ["switch.testventil_1", "switch.testventil_2"],
                "bodensensoren": ["sensor.testboden_1"],
                "ausfuehrung": "sequenziell",
                "gruppe_reihenfolge": 1,
            },
            {"veto_schwelle": 70, "min_dauer": 5, "max_dauer": 20, "leck_sensoren": [], "batterie_sensoren": []},
        ]
    )
    assert f.get("type") == "create_entry", f
    print("Kreis Rasen angelegt")

    # ---- Kreis 2: Topf ----
    f = options_flow(
        [
            {"next_step_id": "kreis_hinzufuegen"},
            {
                "name": "Tomaten",
                "typ": "topf",
                "ventile": ["switch.testventil_3"],
                "bodensensoren": ["sensor.testboden_2"],
                "ausfuehrung": "parallel_start",
                "gruppe_reihenfolge": 2,
            },
            {
                "veto_schwelle": 70,
                "min_dauer": 1,
                "max_dauer": 3,
                "ziel_unten": 50,
                "ziel_oben": 70,
                "k_faktor": 3.7,
                "leck_sensoren": [],
                "batterie_sensoren": [],
            },
        ]
    )
    assert f.get("type") == "create_entry", f
    print("Kreis Tomaten angelegt")

    time.sleep(8)  # OptionsFlowWithReload: Core-Reload nach Options-Update abwarten

    # ---- Entity-Assertions (object_ids = HA-slugify aus "<Device> <Name>") ----
    states = req("/api/states")
    ids = {s["entity_id"] for s in states}
    erwartet = [
        "time.garten_bewasserungszeit",
        "switch.garten_heute_uberspringen",
        "switch.garten_urlaubsmodus",
        "switch.garten_boost_modus",
        "switch.garten_topf_frequenzbewasserung",
        "button.garten_not_aus",
        "button.garten_sofort_start",
        "button.garten_plan_neu_berechnen",
        "number.garten_standard_dauer_auto_aus",
        "number.garten_regen_veto_beobachtet",
        "number.garten_regen_veto_vorhersage",
        "number.garten_peak_sonnen_sperre",
        "number.garten_wassertarif_pro_m3",
        "sensor.garten_nachster_lauf",
        "sensor.garten_letzter_lauf",
        "sensor.garten_rasen_score",
        "sensor.garten_rasen_status",
        "sensor.garten_rasen_zuletzt_bewassert",
        "sensor.garten_rasen_bodenfeuchte",
        "sensor.garten_tomaten_bodenfeuchte",
        "number.garten_rasen_dauer_heute",
        "number.garten_rasen_veto_schwelle_boden",
        "number.garten_rasen_min_dauer",
        "number.garten_rasen_max_dauer",
        "switch.garten_rasen_aktiv",
        "sensor.garten_tomaten_score",
        "sensor.garten_tomaten_dosen_heute",
        "number.garten_tomaten_sollband_unten",
        "number.garten_tomaten_sollband_oben",
        "number.garten_tomaten_dosis_antwort_k",
        "switch.garten_tomaten_aktiv",
    ]
    fehlend = [e for e in erwartet if e not in ids]
    garten = sorted(i for i in ids if "garten" in i)
    print(f"\nGarten-Entities gesamt: {len(garten)}")
    for g in garten:
        print("  ", g)
    if fehlend:
        print("\nFEHLEND:", fehlend)
        sys.exit(1)
    # Zeit-Default prüfen (21:00 aus Seed)
    zeit = next(s for s in states if s["entity_id"] == "time.garten_bewasserungszeit")
    assert zeit["state"].startswith("21:00"), zeit["state"]

    # Topf-Master AUS: die Executor-/Score-Phasen sollen keine Topf-Dosen
    # zünden (Boden 38 liegt dauerhaft unter dem Sollband) — der dedizierte
    # Topf-Test unten schaltet ihn wieder ein.
    req("/api/services/switch/turn_off", {"entity_id": "switch.garten_topf_frequenzbewasserung"})

    # ---- Engine: Plan neu berechnen und Score-Parität prüfen ----
    req("/api/services/button/press", {"entity_id": "button.garten_plan_neu_berechnen"})
    time.sleep(4)
    states = req("/api/states")
    st = {s["entity_id"]: s for s in states}

    def wert(eid):
        return st[eid]["state"]

    print("\nEngine-Ergebnisse:")
    for eid in (
        "sensor.garten_rasen_score",
        "sensor.garten_rasen_status",
        "number.garten_rasen_dauer_heute",
        "sensor.garten_tomaten_score",
        "number.garten_tomaten_dauer_heute",
        "sensor.garten_nachster_lauf",
    ):
        print(f"   {eid} = {wert(eid)}")
    print("   faktoren rasen:", st["sensor.garten_rasen_score"].get("attributes"))

    # Erwartung mit Testbett-Wetter (Tmax 29, Regen 0) und Kit-Defaults:
    # Rasen:   Boden 42/Veto 70 -> 56 | Temp 93,33 | Tage nie -> 100  => 72 -> 16 min
    # Tomaten: Boden 38/Veto 70 -> 64 | dito                          => 77 -> 3 min
    assert wert("sensor.garten_rasen_score") == "72", st["sensor.garten_rasen_score"]
    assert wert("sensor.garten_rasen_bodenfeuchte") == "42.0", wert("sensor.garten_rasen_bodenfeuchte")
    assert wert("number.garten_rasen_dauer_heute") == "16.0", wert("number.garten_rasen_dauer_heute")
    assert wert("sensor.garten_tomaten_score") == "77", st["sensor.garten_tomaten_score"]
    assert wert("number.garten_tomaten_dauer_heute") == "3.0", wert("number.garten_tomaten_dauer_heute")
    assert wert("sensor.garten_rasen_status").startswith("Score 72 → 16 min"), wert("sensor.garten_rasen_status")
    assert wert("sensor.garten_nachster_lauf") not in ("unknown", "unavailable"), "nachster_lauf leer"
    assert "21:00" in wert("sensor.garten_nachster_lauf") or "T21:00" in wert("sensor.garten_nachster_lauf")

    # Plan-heute-Übersicht (v1.0.1): kompakte Zeile + Rohwert-Attribute
    plan = st["sensor.garten_plan_heute"]
    print("   sensor.garten_plan_heute =", plan["state"])
    assert plan["state"].startswith(
        "Tmax3d 29 °C · Regen FC 0.0 mm · Rasen 42 % · Tomaten 38 % — berechnet "
    ), plan["state"]
    pa = plan["attributes"]
    assert pa["tmax_3d"] == 29.0 and pa["wetter_ok"] is True, pa
    assert pa["regen_24h_mm"] is None and pa["regen_forecast_mm"] == 0.0, pa
    assert [k["name"] for k in pa["kreise"]] == ["Rasen", "Tomaten"], pa
    assert pa["wetter_entity"] == wetter, pa
    basis = pa["regen_fc_datenbasis"]
    assert isinstance(basis, list) and len(basis) == 1 and basis[0]["mm"] == 0.0, basis
    assert pa["kreise"][0]["score"] == 72 and pa["kreise"][0]["dauer"] == 16, pa

    # Kreis deaktivieren -> Score 0, Status "deaktiviert"
    req("/api/services/switch/turn_off", {"entity_id": "switch.garten_rasen_aktiv"})
    req("/api/services/button/press", {"entity_id": "button.garten_plan_neu_berechnen"})
    time.sleep(3)
    states = req("/api/states")
    st = {s["entity_id"]: s for s in states}
    assert wert("sensor.garten_rasen_score") == "0", wert("sensor.garten_rasen_score")
    assert "deaktiviert" in wert("sensor.garten_rasen_status")
    assert wert("sensor.garten_tomaten_score") == "77"  # Nachbar-Kreis unberührt

    # ================= Executor (B3/B11): Sofort-Start, Parallel, Not-Aus =====
    def zustand(eid):
        return next(s["state"] for s in req("/api/states") if s["entity_id"] == eid)

    req("/api/services/switch/turn_on", {"entity_id": "switch.garten_rasen_aktiv"})
    req("/api/services/button/press", {"entity_id": "button.garten_plan_neu_berechnen"})
    time.sleep(3)
    req("/api/services/button/press", {"entity_id": "button.garten_sofort_start"})
    time.sleep(6)
    assert zustand("switch.testventil_1") == "on", "Rasen-Ventil 1 nicht offen"
    assert zustand("switch.testventil_2") == "off", "Ventil 2 dürfte noch warten"
    assert zustand("switch.testventil_3") == "on", "Tomaten (parallel) nicht offen"
    print("Executor: V1 + V3 (parallel) offen, V2 wartet — jetzt Not-Aus…")

    req("/api/services/button/press", {"entity_id": "button.garten_not_aus"})
    time.sleep(4)
    for v in ("switch.testventil_1", "switch.testventil_2", "switch.testventil_3"):
        assert zustand(v) == "off", f"{v} nach Not-Aus nicht zu"
    bericht = zustand("sensor.garten_letzter_lauf")
    assert "abgebrochen" in bericht, bericht
    print("Not-Aus: alle Ventile zu, Bericht:", bericht)

    # Skip-Veto gilt auch für den Manuell-Start (B3)
    req("/api/services/switch/turn_on", {"entity_id": "switch.garten_heute_uberspringen"})
    req("/api/services/button/press", {"entity_id": "button.garten_sofort_start"})
    time.sleep(3)
    for v in ("switch.testventil_1", "switch.testventil_3"):
        assert zustand(v) == "off", "Skip-Veto ignoriert!"
    req("/api/services/switch/turn_off", {"entity_id": "switch.garten_heute_uberspringen"})
    print("Skip-Veto: Manuell-Start korrekt verweigert")

    # ============ Neustart-Recovery (B5-B): offenes Ventil nach Boot zu =======
    import subprocess

    req("/api/services/switch/turn_on", {"entity_id": "switch.testventil_2"})
    time.sleep(1)
    assert zustand("switch.testventil_2") == "on"
    print("Ventil 2 offen gelassen — HA-Neustart…")
    subprocess.run(["docker", "restart", "int-test"], check=True, capture_output=True)
    warte_auf_ha(240)

    # Neu einloggen (Onboarding ist durch — normaler Login-Flow)
    f = req("/auth/login_flow", {"client_id": CLIENT, "handler": ["homeassistant", None], "redirect_uri": CLIENT}, auth=False)
    f = req(f"/auth/login_flow/{f['flow_id']}", {"client_id": CLIENT, "username": "test", "password": "test1234"}, auth=False)
    form = urllib.parse.urlencode({"grant_type": "authorization_code", "code": f["result"], "client_id": CLIENT}).encode()
    globals()["TOKEN"] = req("/auth/token", form, auth=False, raw=True)["access_token"]

    ende = time.time() + 160
    while time.time() < ende:
        try:
            if zustand("switch.testventil_2") == "off":
                break
        except Exception:
            pass
        time.sleep(5)
    assert zustand("switch.testventil_2") == "off", "Recovery hat Ventil 2 nicht geschlossen"
    print("Neustart-Recovery: verwaistes Ventil 2 wurde zwangsgeschlossen")

    # ====== B9-Stempel: „zuletzt bewässert“ wurde beim Schließen gesetzt ======
    for eid in ("sensor.garten_rasen_zuletzt_bewassert", "sensor.garten_tomaten_zuletzt_bewassert"):
        assert zustand(eid) not in ("unknown", "unavailable"), f"{eid} nicht gestempelt"
    print("Sitzungs-Stempel (B9): beide Kreise tragen einen Zeitstempel")

    # ========== Topf-Dose (B6) + Volumen (B9): Flow-Sensor nachrüsten =========
    entry_id2 = req("/api/config/config_entries/entry?domain=garten_bewaesserung")[0]["entry_id"]

    def options_flow2(schritte):
        f = req("/api/config/config_entries/options/flow", {"handler": entry_id2})
        for antwort in schritte:
            f = req(f"/api/config/config_entries/options/flow/{f['flow_id']}", antwort)
        return f

    f = options_flow2(
        [
            {"next_step_id": "kreis_bearbeiten"},
            {"kreis": "tomaten"},
            {
                "name": "Tomaten",
                "typ": "topf",
                "ventile": ["switch.testventil_3"],
                "bodensensoren": ["sensor.testboden_2"],
                "ausfuehrung": "parallel_start",
                "gruppe_reihenfolge": 2,
            },
            {
                "veto_schwelle": 55,  # F3-Regression: Edit muss die Entity erreichen
                "min_dauer": 1,
                "max_dauer": 3,
                "ziel_unten": 50,
                "ziel_oben": 70,
                "k_faktor": 3.7,
                "flow_sensor": "sensor.testflow",
                "leck_sensoren": [],
                "batterie_sensoren": [],
            },
        ]
    )
    assert f.get("type") == "create_entry", f
    time.sleep(8)  # Reload
    assert zustand("number.garten_tomaten_veto_schwelle_boden") == "55.0", (
        "F3: Options-Edit kam nicht in der Number an: "
        + zustand("number.garten_tomaten_veto_schwelle_boden")
    )
    print("F3: Kreis-Edit (Veto 70→55) erreicht die Number nach dem Reload")
    req("/api/services/input_number/set_value", {"entity_id": "input_number.flow", "value": 1.0})
    req("/api/services/switch/turn_on", {"entity_id": "switch.garten_topf_frequenzbewasserung"})
    time.sleep(1)

    # Zuletzt-Stempel ist frisch → 24-h-Dämpfer… betrifft nur den Report.
    # Topf-Gates: Master an (Default), Boden 38 < Sollband-Unterkante 50,
    # Glitch 5 < 38, keine Strahlung/Regen-Sensoren, Dosen 0<4, Ventil zu.
    ids2 = {s["entity_id"] for s in req("/api/states")}
    for eid in (
        "sensor.garten_tomaten_liter_heute",
        "sensor.garten_tomaten_liter_monat",
        "sensor.garten_tomaten_kosten_monat",
    ):
        assert eid in ids2, f"{eid} fehlt nach Flow-Konfiguration"
    req("/api/services/button/press", {"entity_id": "button.garten_plan_neu_berechnen"})
    time.sleep(5)
    assert zustand("switch.testventil_3") == "on", "Topf-Dose hat Ventil nicht geöffnet"
    assert zustand("sensor.garten_tomaten_dosen_heute") == "1", zustand("sensor.garten_tomaten_dosen_heute")
    print("Topf-Dose (B6): Ventil offen, Dosen-Zähler = 1")

    # Wasser „fließt“: 0,02 m³ = 20 L, dann Not-Aus schließt die Dose
    req("/api/services/input_number/set_value", {"entity_id": "input_number.flow", "value": 1.02})
    time.sleep(1)
    req("/api/services/button/press", {"entity_id": "button.garten_not_aus"})
    time.sleep(2)
    assert zustand("switch.testventil_3") == "off", "Dose nach Not-Aus nicht zu"

    # Mindestabstand-Gate: erneuter Nach-Check darf KEINE zweite Dose zünden
    req("/api/services/button/press", {"entity_id": "button.garten_plan_neu_berechnen"})
    time.sleep(4)
    assert zustand("switch.testventil_3") == "off", "Intervall-Gate versagt (2. Dose)"
    assert zustand("sensor.garten_tomaten_dosen_heute") == "1"
    print("Mindestabstand-Gate (⑤): zweite Dose korrekt verweigert")

    # Volumen-Settle (30 s) abwarten → 20,0 L / 0,06 EUR
    time.sleep(35)
    assert zustand("sensor.garten_tomaten_liter_heute") == "20.0", zustand("sensor.garten_tomaten_liter_heute")
    assert zustand("sensor.garten_tomaten_liter_monat") == "20.0"
    assert zustand("sensor.garten_tomaten_kosten_monat") == "0.06", zustand("sensor.garten_tomaten_kosten_monat")
    print("Volumen (B9): 20,0 L Sitzung → Liter heute/Monat + Kosten korrekt")

    # Cent-genauer Wassertarif (v1.3.4): 2.13 muss die Number akzeptieren
    req("/api/services/number/set_value",
        {"entity_id": "number.garten_wassertarif_pro_m3", "value": 2.13})
    time.sleep(1)
    assert zustand("number.garten_wassertarif_pro_m3") == "2.13", (
        zustand("number.garten_wassertarif_pro_m3")
    )
    req("/api/services/number/set_value",
        {"entity_id": "number.garten_wassertarif_pro_m3", "value": 3.0})
    time.sleep(1)
    print("Wassertarif: Cent-Schritt 2.13 akzeptiert")

    # ======== Services (F7): dosis_geben umgeht Gates, not_aus räumt ab ========
    req("/api/services/garten_bewaesserung/dosis_geben", {"kreis": "tomaten"})
    time.sleep(3)
    assert zustand("switch.testventil_3") == "on", "dosis_geben hat nicht geöffnet"
    assert zustand("sensor.garten_tomaten_dosen_heute") == "2"
    req("/api/services/garten_bewaesserung/not_aus", {})
    time.sleep(3)
    assert zustand("switch.testventil_3") == "off", "not_aus-Service versagt"
    print("Services (F7): dosis_geben + not_aus funktionieren")

    # === Auto-Aus-Backstop (F2) + Re-Arm nach Options-Reload (F1) ===
    req("/api/services/number/set_value",
        {"entity_id": "number.garten_standard_dauer_auto_aus", "value": 1})
    time.sleep(1)
    req("/api/services/switch/turn_on", {"entity_id": "switch.testventil_1"})
    time.sleep(2)
    assert zustand("switch.testventil_1") == "on"
    # Options-Reload mitten im Auto-Aus-Fenster (Benachrichtigungen-Step ändern)
    f = req("/api/config/config_entries/options/flow", {"handler": entry_id2})
    f = req(f"/api/config/config_entries/options/flow/{f['flow_id']}",
            {"next_step_id": "benachrichtigungen"})
    antwort = {k["name"]: k["default"] for k in f.get("data_schema", []) if "default" in k}
    antwort["dashboard_pfad"] = "/test-reload"
    f = req(f"/api/config/config_entries/options/flow/{f['flow_id']}", antwort)
    assert f.get("type") == "create_entry", f
    print("Ventil 1 offen, Reload ausgelöst — warte auf Auto-Aus (~1 min)…")
    ende2 = time.time() + 110
    while time.time() < ende2 and zustand("switch.testventil_1") == "on":
        time.sleep(5)
    assert zustand("switch.testventil_1") == "off", (
        "F1/F2: Auto-Aus hat das Ventil nach dem Reload nicht geschlossen"
    )
    print("Auto-Aus (B4/F2) + Re-Arm nach Reload (F1): Ventil wurde geschlossen")

    # ========== Typwechsel im Edit (v1.0.1): Rasen -> Topf -> Rasen ==========
    # Master aus, damit der Boden-42-Rasen als Topf keine echte Dose zündet.
    req("/api/services/switch/turn_off", {"entity_id": "switch.garten_topf_frequenzbewasserung"})
    rasen_basis = {
        "name": "Rasen",
        "ventile": ["switch.testventil_1", "switch.testventil_2"],
        "bodensensoren": ["sensor.testboden_1"],
        "ausfuehrung": "sequenziell",
        "gruppe_reihenfolge": 1,
    }
    f = options_flow2(
        [
            {"next_step_id": "kreis_bearbeiten"},
            {"kreis": "rasen"},
            {**rasen_basis, "typ": "topf"},
            {
                "veto_schwelle": 70, "min_dauer": 5, "max_dauer": 20,
                "ziel_unten": 45, "ziel_oben": 65, "k_faktor": 2.0,
                "leck_sensoren": [], "batterie_sensoren": [],
            },
        ]
    )
    assert f.get("type") == "create_entry", f
    time.sleep(8)
    ids3 = {s["entity_id"] for s in req("/api/states")}
    for eid in (
        "number.garten_rasen_sollband_unten",
        "number.garten_rasen_sollband_oben",
        "number.garten_rasen_dosis_antwort_k",
        "sensor.garten_rasen_dosen_heute",
    ):
        assert eid in ids3, f"{eid} fehlt nach Typwechsel Rasen->Topf"
    print("Typwechsel Rasen->Topf: Sollband/k/Dosen-Entities erschienen")

    f = options_flow2(
        [
            {"next_step_id": "kreis_bearbeiten"},
            {"kreis": "rasen"},
            {**rasen_basis, "typ": "rasen"},
            {"veto_schwelle": 70, "min_dauer": 5, "max_dauer": 20,
             "leck_sensoren": [], "batterie_sensoren": []},
        ]
    )
    assert f.get("type") == "create_entry", f
    time.sleep(8)
    ids4 = {s["entity_id"] for s in req("/api/states")}
    for eid in ("number.garten_rasen_sollband_unten", "sensor.garten_rasen_dosen_heute"):
        assert eid not in ids4, f"{eid} lebt noch nach Typwechsel Topf->Rasen"
    assert "sensor.garten_tomaten_liter_heute" in ids4, "Nachbar-Kreis beschädigt"
    assert "sensor.garten_rasen_score" in ids4, "Rasen-Basis-Entities weg"
    # Registry-Datei: das Aufräumen ist die eigentliche Neuerung — Leichen-Check
    # (Registry-Save ist verzögert, daher Retry-Fenster).
    ende3 = time.time() + 40
    leichen = None
    while time.time() < ende3:
        reg_json = subprocess.run(
            ["docker", "exec", "int-test", "cat", "/config/.storage/core.entity_registry"],
            check=True, capture_output=True, text=True,
        ).stdout
        leichen = [
            frag
            for frag in ("rasen_ziel_unten", "rasen_ziel_oben", "rasen_k_faktor", "rasen_dosen_heute")
            if frag in reg_json
        ]
        if not leichen:
            break
        time.sleep(5)
    assert not leichen, f"Registry-Leichen nach Typwechsel: {leichen}"
    print("Typwechsel Topf->Rasen: typ-spezifische Entities + Registry-Einträge entfernt")

    # ============ ET₀-Modus (v1.1.0): Tuning-Sektionen + Umschaltung ==========
    f = options_flow2(
        [
            {"next_step_id": "tuning"},
            {
                "gewichte": {},
                "temperatur": {"score_temp_quelle": "et0"},
                "regen_sonne": {},
                "toepfe": {},
                "kosten": {},
            },
        ]
    )
    assert f.get("type") == "create_entry", f
    time.sleep(8)
    req("/api/services/button/press", {"entity_id": "button.garten_plan_neu_berechnen"})
    time.sleep(4)
    st3 = {s["entity_id"]: s for s in req("/api/states")}
    fak = st3["sensor.garten_rasen_score"]["attributes"]
    assert fak.get("temp_quelle") == "et0", fak
    assert (fak.get("et0") or 0) > 0, fak
    assert "ET₀" in st3["sensor.garten_rasen_status"]["state"], st3["sensor.garten_rasen_status"]["state"]
    plan3 = st3["sensor.garten_plan_heute"]
    assert "ET₀" in plan3["state"], plan3["state"]
    assert plan3["attributes"]["temp_quelle"] == "et0" and plan3["attributes"]["et0_mm"] > 0
    assert plan3["attributes"]["forecast_typ"] == "daily", plan3["attributes"]
    print("ET₀-Modus (Tuning-Sektionen):", plan3["state"])

    # ===== Temperatur-Quelle pro Kreis (v1.2.0): Tomaten-Override auf Tmax ====
    f = options_flow2(
        [
            {"next_step_id": "kreis_bearbeiten"},
            {"kreis": "tomaten"},
            {
                "name": "Tomaten",
                "typ": "topf",
                "ventile": ["switch.testventil_3"],
                "bodensensoren": ["sensor.testboden_2"],
                "ausfuehrung": "parallel_start",
                "gruppe_reihenfolge": 2,
            },
            {
                "veto_schwelle": 55, "min_dauer": 1, "max_dauer": 3,
                "temp_quelle": "tmax",
                "ziel_unten": 50, "ziel_oben": 70, "k_faktor": 3.7,
                "flow_sensor": "sensor.testflow",
                "leck_sensoren": [], "batterie_sensoren": [],
            },
        ]
    )
    assert f.get("type") == "create_entry", f
    time.sleep(8)
    req("/api/services/button/press", {"entity_id": "button.garten_plan_neu_berechnen"})
    time.sleep(4)
    st4 = {s["entity_id"]: s for s in req("/api/states")}
    assert st4["sensor.garten_rasen_score"]["attributes"]["temp_quelle"] == "et0"
    assert st4["sensor.garten_tomaten_score"]["attributes"]["temp_quelle"] == "tmax", (
        st4["sensor.garten_tomaten_score"]["attributes"]
    )
    assert "Tmax" in st4["sensor.garten_tomaten_status"]["state"]
    print("Per-Kreis-Quelle: Rasen=ET₀ (global), Tomaten=Tmax (Override)")

    # ===== Parallel-Kopplung (v1.3.0): Tomaten startet mit Kettenposition 2 ====
    req("/api/services/switch/turn_off", {"entity_id": "switch.garten_topf_frequenzbewasserung"})
    f = options_flow2(
        [
            {"next_step_id": "kreis_hinzufuegen"},
            {
                "name": "Rasen Zwei",
                "typ": "rasen",
                "ventile": ["switch.testventil_4"],
                "bodensensoren": [],
                "ausfuehrung": "sequenziell",
                "gruppe_reihenfolge": 2,
            },
            {"veto_schwelle": 70, "min_dauer": 1, "max_dauer": 5,
             "temp_quelle": "global", "flow_sensor": "sensor.testflow_liter",
             "leck_sensoren": [], "batterie_sensoren": []},
        ]
    )
    assert f.get("type") == "create_entry", f
    time.sleep(8)
    f = options_flow2(
        [
            {"next_step_id": "kreis_bearbeiten"},
            {"kreis": "tomaten"},
            {
                "name": "Tomaten",
                "typ": "topf",
                "ventile": ["switch.testventil_3"],
                "bodensensoren": ["sensor.testboden_2"],
                "ausfuehrung": "parallel_gruppe",
                "gruppe_reihenfolge": 2,
            },
            {
                "veto_schwelle": 55, "min_dauer": 1, "max_dauer": 3,
                "temp_quelle": "tmax",
                "ziel_unten": 50, "ziel_oben": 70, "k_faktor": 3.7,
                "flow_sensor": "sensor.testflow",
                "leck_sensoren": [], "batterie_sensoren": [],
            },
        ]
    )
    assert f.get("type") == "create_entry", f
    time.sleep(8)
    # Rasen auf 0 min -> Kette springt sofort zu Rasen Zwei; Tomaten koppelt dort an
    req("/api/services/button/press", {"entity_id": "button.garten_plan_neu_berechnen"})
    time.sleep(4)
    for eid, wert2 in (
        ("number.garten_rasen_dauer_heute", 0),
        ("number.garten_rasen_zwei_dauer_heute", 3),
        ("number.garten_tomaten_dauer_heute", 2),
    ):
        req("/api/services/number/set_value", {"entity_id": eid, "value": wert2})
    time.sleep(1)
    req("/api/services/button/press", {"entity_id": "button.garten_sofort_start"})
    time.sleep(6)
    assert zustand("switch.testventil_1") == "off" and zustand("switch.testventil_2") == "off", (
        "Rasen (0 min) haette uebersprungen werden muessen"
    )
    assert zustand("switch.testventil_4") == "on", "Rasen Zwei nicht gestartet"
    assert zustand("switch.testventil_3") == "on", "Tomaten nicht an Position 2 angekoppelt"
    # Während beide offen sind: +0.005 m3 = +5 L "fliessen" — prüft beide
    # Einheiten-Pfade (Rasen Zwei zählt in L, Tomaten in m³)
    req("/api/services/input_number/set_value", {"entity_id": "input_number.flow", "value": 1.025})
    time.sleep(1)
    req("/api/services/button/press", {"entity_id": "button.garten_not_aus"})
    time.sleep(3)
    for v in ("switch.testventil_3", "switch.testventil_4"):
        assert zustand(v) == "off", f"{v} nach Not-Aus offen"
    time.sleep(35)  # Volumen-Settle
    assert zustand("sensor.garten_rasen_zwei_liter_heute") == "5.0", (
        "L-Einheit: " + zustand("sensor.garten_rasen_zwei_liter_heute")
    )
    assert zustand("sensor.garten_tomaten_liter_heute") == "25.0", (
        "m³-Einheit: " + zustand("sensor.garten_tomaten_liter_heute")
    )
    print("Volumen-Einheiten: Rasen Zwei 5.0 L (L-Zähler), Tomaten 25.0 L (m³-Zähler)")
    ids5 = {s["entity_id"] for s in req("/api/states")}
    assert "sensor.garten_rasen_zwei_bodenfeuchte" not in ids5, (
        "Bodenfeuchte-Feld darf ohne Sensoren nicht existieren"
    )
    print("Parallel-Kopplung: Tomaten startete mit Kettenposition 2 (Rasen Zwei)")
    print("Bodenfeuchte-Infofeld: Rasen 42.0, Rasen Zwei (ohne Sensor) korrekt ohne Feld")

    print("\nALLE ASSERTIONS PASS — Flows, Entities, Score-Engine (B1), Executor (B3), Not-Aus (B11), Skip-Veto, Neustart-Recovery (B5-B), Stempel (B9), Topf-Dose (B6) + Gates, Volumen/Kosten und Typwechsel (v1.0.1) OK")


if __name__ == "__main__":
    main()
