"""GartenController — die Engine hinter den Entities.

Abgedeckt: Scheduler (B1/B2), Executor (B3), Ventil-Watchdog + Neustart-
Recovery (B4/B5), Sitzungs-Stempel (B9), Not-Aus (B11).

Grundregeln (ARCHITECTURE.md):
- Engine liest IMMER die Entities (number/switch/time), nie entry.options
  direkt — Ausnahme: statische Konfiguration (Kreise, Sensoren, Notify).
- Entity-Auflösung über die Registry per unique_id — übersteht Umbenennungen.
- Punktgenaue one-shot-Timer statt Fenster-Mathematik; Watchdog als Timer
  pro Ventil-Öffnung statt `for:`-Trigger (kein Re-Arm-Problem).
- Dauer-SNAPSHOT beim Lauf-Start: spätere Score-Neuberechnungen ändern einen
  laufenden Lauf nicht mehr (B3-Parität).
"""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, time as time_t, timedelta
from functools import partial
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    BATTERIE_COOLDOWN_H,
    BATTERIE_DEBOUNCE_MIN,
    BATTERIE_SCHWELLE,
    CONF_BATTERIE,
    CONF_BODENSENSOREN,
    CONF_DASHBOARD_PFAD,
    CONF_FLOW_SENSOR,
    CONF_GRUPPE,
    CONF_KREIS_ID,
    CONF_KREIS_NAME,
    CONF_KREIS_TYP,
    CONF_KREISE,
    CONF_LECK,
    CONF_NOTAUS_MIN,
    CONF_NOTIFY,
    CONF_PARALLEL,
    CONF_PUSH_KRITISCH,
    CONF_REGEN_SENSOR,
    CONF_STANDARD_DAUER,
    CONF_STRAHLUNG_SENSOR,
    CONF_VENTILE,
    CONF_VERSORGUNG,
    CONF_VORLAUF,
    CONF_WETTER,
    DEFAULT_NOTAUS_MIN,
    DEFAULT_PAUSE_S,
    DEFAULT_REGEN_BEOBACHTET,
    DEFAULT_REGEN_FORECAST,
    DEFAULT_RETRY_ABSTAND_S,
    DEFAULT_RETRY_ANZAHL,
    DEFAULT_STANDARD_DAUER,
    DEFAULT_STRAHLUNG_SCHWELLE,
    DEFAULT_VORLAUF,
    DOMAIN,
    EVENT_LAUF_BEENDET,
    EVENT_LAUF_GESTARTET,
    EVENT_NOTAUS,
    REPORT_DAEMPFER_H,
    REPORT_STUNDE,
    SCORE_DEFAULTS,
    STORE_VERSION,
    TOPF_DEFAULTS,
    TOPF_UNTERSCHREITUNG_MIN,
    VERSORGUNG_DEBOUNCE_S,
    VOLUMEN_SETTLE_S,
)
from .daten import GartenDaten
from .score import (
    NIE_BEWAESSERT_TAGE,
    ScoreEingabe,
    ScoreParameter,
    baue_plan_push,
    baue_plan_uebersicht,
    berechne_score,
    extrahiere_wetter,
    sicher_float,
)

_LOGGER = logging.getLogger(__name__)

UNGUELTIG = ("unknown", "unavailable", "", None)
NICHT_ERREICHBAR = ("unavailable", "unknown", "none", None)


class GartenController:
    """Pro Config-Entry: Scheduler + Executor + Watchdog + Sitzung + Not-Aus."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, daten: GartenDaten) -> None:
        self.hass = hass
        self.entry = entry
        self.daten = daten
        self._store: Store = Store(hass, STORE_VERSION, f"{DOMAIN}/{entry.entry_id}")
        self._unsubs: list = []
        self._push_unsub = None
        self._lauf_unsub = None
        self._lauf_task: asyncio.Task | None = None
        self._parallel_tasks: list[asyncio.Task] = []
        self._watchdogs: dict[str, Any] = {}  # ventil-eid -> Timer-unsub (Notaus, B5-A)
        self._auto_aus: dict[str, Any] = {}  # ventil-eid -> Timer-unsub (Backstop, B4)
        self._gestoppt = False
        self._dose_tasks: dict[str, asyncio.Task] = {}  # kid -> Dosier-Task
        self._letzte_dose: dict[str, datetime] = {}  # kid -> Zeitpunkt (Gate ⑤)
        self._topf_debounce: dict[str, Any] = {}  # kid -> Timer-unsub (10-min-Entprellung)
        self._versorgung_debounce: dict[str, Any] = {}  # sensor -> Timer-unsub
        self._batterie_debounce: dict[str, Any] = {}  # sensor -> Timer-unsub
        self._batterie_zuletzt: datetime | None = None  # globaler 24-h-Cooldown (B10)
        self._volumen_baseline: dict[str, float] = {}  # kid -> m³ bei Sitzungsbeginn
        self._volumen_settle: dict[str, Any] = {}  # kid -> Settle-Timer-unsub

    # ------------------------------------------------------------ Lebenszyklus

    async def start(self) -> None:
        await self._store_laden()
        self._unsubs.append(
            async_track_time_change(self.hass, self._recompute_geplant, minute=[0, 30], second=0)
        )
        self._unsubs.append(
            async_track_time_change(
                self.hass, self._trocken_report, hour=REPORT_STUNDE, minute=0, second=0
            )
        )
        self._unsubs.append(
            async_track_time_change(self.hass, self._tagesreset, hour=0, minute=1, second=0)
        )
        if zeit_eid := self._eid("time", "bewaesserungszeit"):
            self._unsubs.append(
                async_track_state_change_event(self.hass, [zeit_eid], self._zeit_geaendert)
            )
        if ventile := self._alle_ventile():
            # Ein Listener für Watchdog (B5-A), Sitzungs-Stempel (B9),
            # Volumen-Sitzungen und Backstop — deckt JEDE Öffnungsquelle ab
            # (Plan, Knopf, App, physischer Taster am Ventil).
            self._unsubs.append(
                async_track_state_change_event(self.hass, ventile, self._ventil_ereignis)
            )
        if leck := sorted({s for k in self._kreise() for s in k.get(CONF_LECK) or []}):
            self._unsubs.append(
                async_track_state_change_event(self.hass, leck, self._leck_ereignis)
            )
        if versorgung := sorted(
            {k[CONF_VERSORGUNG] for k in self._kreise() if k.get(CONF_VERSORGUNG)}
        ):
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, versorgung, self._versorgung_ereignis
                )
            )
        if batterie := sorted(
            {s for k in self._kreise() for s in k.get(CONF_BATTERIE) or []}
        ):
            self._unsubs.append(
                async_track_state_change_event(self.hass, batterie, self._batterie_ereignis)
            )
        if topf_sensoren := sorted(
            {
                s
                for k in self._kreise()
                if k.get(CONF_KREIS_TYP) == "topf"
                for s in k.get(CONF_BODENSENSOREN) or []
            }
        ):
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, topf_sensoren, self._topf_boden_ereignis
                )
            )
        # F1: Ein Options-Reload verwirft die Timer bereits offener Ventile —
        # hier werden Watchdog + Auto-Aus-Backstop für alles, was gerade
        # "on" meldet, sofort neu armiert (die Uhr startet dabei neu; besser
        # eine späte Zwangsschließung als gar keine).
        for ventil in self._alle_ventile():
            if self._zustand(ventil) == "on":
                self._watchdog_armieren(ventil)
                if not self.daten.hub.lauf_aktiv:
                    self._auto_aus_armieren(ventil)
        # Neustart-/Absturz-Recovery läuft im Hintergrund (wartet bis zu
        # 120 s auf Funk-Ventile) — darf das Setup nicht blockieren.
        self.entry.async_create_background_task(
            self.hass, self._startup_recovery(), f"{DOMAIN}_recovery"
        )
        await self._recompute_alle()
        self._arme_tagestimer()

    @callback
    def stop(self) -> None:
        self._gestoppt = True  # F5: keine Ghost-Timer aus in-flight-Tasks
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        for unsub in (self._push_unsub, self._lauf_unsub):
            if unsub:
                unsub()
        self._push_unsub = self._lauf_unsub = None
        for unsub in self._watchdogs.values():
            unsub()
        self._watchdogs.clear()
        for unsub in self._auto_aus.values():
            unsub()
        self._auto_aus.clear()
        for sammlung in (
            self._topf_debounce,
            self._versorgung_debounce,
            self._batterie_debounce,
            self._volumen_settle,
        ):
            for unsub in sammlung.values():
                unsub()
            sammlung.clear()
        if self._lauf_task and not self._lauf_task.done():
            self._lauf_task.cancel()
        for task in self._parallel_tasks:
            if not task.done():
                task.cancel()
        for task in self._dose_tasks.values():
            if not task.done():
                task.cancel()

    # ------------------------------------------------------- Entity-Zugriffe

    def _eid(self, domain: str, schluessel: str, kid: str | None = None) -> str | None:
        unique = (
            f"{self.entry.entry_id}_{schluessel}"
            if kid is None
            else f"{self.entry.entry_id}_{kid}_{schluessel}"
        )
        return er.async_get(self.hass).async_get_entity_id(domain, DOMAIN, unique)

    def _zustand(self, entity_id: str | None) -> str | None:
        if not entity_id:
            return None
        zustand = self.hass.states.get(entity_id)
        return zustand.state if zustand else None

    def _zahl(self, domain: str, schluessel: str, kid: str | None, fallback: float) -> float:
        return sicher_float(self._zustand(self._eid(domain, schluessel, kid)), fallback)

    def _an(self, schluessel: str, kid: str | None = None) -> bool:
        return self._zustand(self._eid("switch", schluessel, kid)) == "on"

    def _kreise(self) -> list[dict[str, Any]]:
        return self.entry.options.get(CONF_KREISE, [])

    def _alle_ventile(self) -> list[str]:
        return [v for kreis in self._kreise() for v in kreis.get(CONF_VENTILE, [])]

    def _kreis_zu_ventil(self, ventil: str) -> dict[str, Any] | None:
        for kreis in self._kreise():
            if ventil in kreis.get(CONF_VENTILE, []):
                return kreis
        return None

    def _score_parameter(self) -> tuple[ScoreParameter, str]:
        roh = {**SCORE_DEFAULTS, **self.entry.options.get("score", {})}
        typ = roh.pop("forecast_typ", "daily")
        return (ScoreParameter(**roh), typ)

    # ------------------------------------------------------------- Recompute

    async def _recompute_geplant(self, _jetzt: datetime) -> None:
        await self._recompute_alle()
        self._topf_runde()

    async def _recompute_alle(self) -> None:
        """B1 für jeden Kreis: Wetter einmal holen, Score/Dauer/Status schreiben."""
        params, forecast_typ = self._score_parameter()
        wetter = self.entry.options.get(CONF_WETTER)
        forecast = None
        try:
            antwort = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": wetter, "type": forecast_typ},
                blocking=True,
                return_response=True,
            )
            if antwort:
                forecast = antwort.get(wetter, {}).get("forecast")
        except Exception as exc:  # Wetter-Robustheit: Fehler ⇒ Fallbacks (B1)
            _LOGGER.debug("Wettervorhersage nicht abrufbar: %s", exc)
        tmax, regen_forecast, wetter_ok = extrahiere_wetter(forecast, forecast_typ)

        regen_sensor = self.entry.options.get(CONF_REGEN_SENSOR) or None
        regen_beobachtet = (
            sicher_float(self._zustand(regen_sensor), 0.0) if regen_sensor else None
        )
        skip = self._an("heute_ueberspringen")
        urlaub = self._an("urlaubsmodus")
        aggressiv = self._an("aggressiv_modus")
        regen_beob_schwelle = self._zahl(
            "number", "regen_beobachtet_mm", None, DEFAULT_REGEN_BEOBACHTET
        )
        regen_fc_schwelle = self._zahl(
            "number", "regen_forecast_mm", None, DEFAULT_REGEN_FORECAST
        )

        jetzt_ts = dt_util.utcnow().timestamp()
        uebersicht: list[tuple[str, float | None]] = []
        details_kreise: list[dict[str, Any]] = []
        for kreis in self._kreise():
            kid = kreis[CONF_KREIS_ID]
            laufzeit = self.daten.kreis(kid)

            sensoren = kreis.get(CONF_BODENSENSOREN) or []
            boden = (
                min(sicher_float(self._zustand(s), 50.0) for s in sensoren)
                if sensoren
                else None
            )
            uebersicht.append((kreis[CONF_KREIS_NAME], boden))

            if not self._an("aktiv", kid):
                laufzeit.score = 0
                laufzeit.status = "⏸ Kreis deaktiviert — keine Bewässerung"
                laufzeit.faktoren = {"deaktiviert": True}
                await self._setze_dauer(kid, 0)
                details_kreise.append(
                    {"name": kreis[CONF_KREIS_NAME], "boden": boden,
                     "score": 0, "dauer": 0, "deaktiviert": True}
                )
                continue

            if laufzeit.zuletzt_bewaessert is not None:
                tage_roh = (jetzt_ts - laufzeit.zuletzt_bewaessert.timestamp()) / 86400
                tage_seit = max(int(tage_roh * 10 + 0.5) / 10, 0.0)  # B1: round(1)
            else:
                tage_seit = NIE_BEWAESSERT_TAGE

            ergebnis = berechne_score(
                ScoreEingabe(
                    boden=boden,
                    tmax=tmax,
                    wetter_ok=wetter_ok,
                    tage_seit=tage_seit,
                    veto_schwelle=self._zahl("number", "veto_schwelle", kid, 70.0),
                    min_dauer=self._zahl("number", "min_dauer", kid, 5.0),
                    max_dauer=self._zahl("number", "max_dauer", kid, 20.0),
                    skip=skip,
                    urlaub=urlaub,
                    aggressiv=aggressiv,
                    regen_beobachtet=regen_beobachtet,
                    regen_beobachtet_schwelle=regen_beob_schwelle,
                    regen_forecast=regen_forecast,
                    regen_forecast_schwelle=regen_fc_schwelle,
                ),
                params,
            )
            laufzeit.score = ergebnis.score
            laufzeit.status = ergebnis.status
            laufzeit.faktoren = ergebnis.faktoren
            await self._setze_dauer(kid, ergebnis.dauer)
            details_kreise.append(
                {"name": kreis[CONF_KREIS_NAME], "boden": boden,
                 "score": ergebnis.score, "dauer": ergebnis.dauer}
            )

        zeit_str = dt_util.now().strftime("%H:%M")
        self.daten.hub.plan_heute = baue_plan_uebersicht(
            tmax, wetter_ok, regen_beobachtet, regen_forecast, uebersicht, zeit_str
        )
        self.daten.hub.plan_details = {
            "tmax_3d": tmax,
            "wetter_ok": wetter_ok,
            "regen_24h_mm": regen_beobachtet,
            "regen_forecast_mm": regen_forecast,
            "berechnet_um": dt_util.now().isoformat(),
            "kreise": details_kreise,
        }
        self.daten.broadcast()

    async def _setze_dauer(self, kid: str, dauer: int) -> None:
        """Tagesdauer in die number-Entity schreiben (die eine Wahrheit,
        die Nutzer bis zum Lauf überschreiben dürfen)."""
        if eid := self._eid("number", "dauer_heute", kid):
            await self.hass.services.async_call(
                "number", "set_value", {"entity_id": eid, "value": dauer}, blocking=True
            )

    # ------------------------------------------------------------ Tagestimer

    @callback
    def _zeit_geaendert(self, _ereignis) -> None:
        self._arme_tagestimer()

    def _bewaesserungszeit(self) -> time_t | None:
        roh = self._zustand(self._eid("time", "bewaesserungszeit"))
        if roh in UNGUELTIG:
            return None
        try:
            return time_t.fromisoformat(roh)
        except ValueError:
            return None

    @callback
    def _arme_tagestimer(self) -> None:
        """Push- und Lauf-Timer punktgenau (neu) armieren."""
        if self._gestoppt:  # F5: in-flight _push_/_lauf_feuern nach stop()
            return
        for unsub in (self._push_unsub, self._lauf_unsub):
            if unsub:
                unsub()
        self._push_unsub = self._lauf_unsub = None

        zeit = self._bewaesserungszeit()
        if zeit is None:
            # Kein Raten: ohne gültige Zeit weder Push noch Lauf (B2-Parität).
            self.daten.hub.naechster_lauf = None
            self.daten.broadcast()
            return

        jetzt = dt_util.now()
        lauf = jetzt.replace(
            hour=zeit.hour, minute=zeit.minute, second=zeit.second, microsecond=0
        )
        if lauf <= jetzt:
            lauf += timedelta(days=1)
        vorlauf = sicher_float(
            self.entry.options.get(CONF_VORLAUF, DEFAULT_VORLAUF), DEFAULT_VORLAUF
        )
        push = lauf - timedelta(minutes=vorlauf)
        while push <= jetzt:
            push += timedelta(days=1)

        self._push_unsub = async_track_point_in_time(self.hass, self._push_feuern, push)
        self._lauf_unsub = async_track_point_in_time(self.hass, self._lauf_feuern, lauf)
        self.daten.hub.naechster_lauf = lauf
        self.daten.broadcast()

    async def _push_feuern(self, _jetzt: datetime) -> None:
        self._push_unsub = None
        try:
            # Frisch rechnen statt B2s :05/:35-Versatz — kein Race möglich.
            await self._recompute_alle()
            if self._an("heute_ueberspringen"):
                _LOGGER.debug("Tagesplan-Push unterdrückt: heute überspringen aktiv")
                return
            zeit = self._bewaesserungszeit()
            zeit_str = zeit.strftime("%H:%M") if zeit else "?"
            zeilen = [
                (
                    kreis.get(CONF_KREIS_NAME, kreis[CONF_KREIS_ID]),
                    int(self._zahl("number", "dauer_heute", kreis[CONF_KREIS_ID], 0)),
                    self.daten.kreis(kreis[CONF_KREIS_ID]).score,
                )
                for kreis in self._kreise()
            ]
            titel, text = baue_plan_push(zeit_str, zeilen)
            if text:
                await self._sende_push(titel, text, kritisch=False)
        finally:
            self._arme_tagestimer()

    async def _lauf_feuern(self, _jetzt: datetime) -> None:
        self._lauf_unsub = None
        try:
            await self.starte_lauf(quelle="Plan")
        finally:
            self._arme_tagestimer()

    async def _tagesreset(self, _jetzt: datetime) -> None:
        """00:01: Überspringen zurücksetzen, Dosen-Zähler nullen (Kit-Parität)."""
        if (eid := self._eid("switch", "heute_ueberspringen")) and self._zustand(
            eid
        ) == "on":
            await self.hass.services.async_call(
                "switch", "turn_off", {"entity_id": eid}, blocking=True
            )
        for kreis in self._kreise():
            laufzeit = self.daten.kreis(kreis[CONF_KREIS_ID])
            laufzeit.dosen_heute = 0
            if laufzeit.liter_heute is not None:
                laufzeit.liter_heute = 0.0
            if dt_util.now().day == 1 and laufzeit.liter_monat is not None:
                laufzeit.liter_monat = 0.0
        self.daten.broadcast()
        await self._store_sichern()

    # -------------------------------------------------------------- Executor

    async def starte_lauf(self, quelle: str) -> None:
        """B3: Lauf starten — Vetos gelten für Plan UND Manuell-Start."""
        if self._gestoppt:
            return
        if self._an("heute_ueberspringen") or self._an("urlaubsmodus"):
            _LOGGER.info("Bewässerungslauf (%s) übersprungen: Skip/Urlaub aktiv", quelle)
            return
        if self._lauf_task and not self._lauf_task.done():
            # mode: single (B3) — Doppel-Start sichtbar machen, aber ignorieren.
            _LOGGER.warning("Bewässerungslauf läuft bereits — Start (%s) ignoriert", quelle)
            return
        # Dauer-SNAPSHOT jetzt (B3): Kreise sortiert; deaktivierte Kreise
        # stehen ohnehin auf Dauer 0 und werden im Lauf übersprungen.
        plan = [
            (kreis, int(self._zahl("number", "dauer_heute", kreis[CONF_KREIS_ID], 0)))
            for kreis in sorted(
                self._kreise(), key=lambda k: (k.get(CONF_GRUPPE, 99), k[CONF_KREIS_ID])
            )
        ]
        self._lauf_task = self.entry.async_create_background_task(
            self.hass, self._lauf_ausfuehren(plan, quelle), f"{DOMAIN}_lauf"
        )

    async def _lauf_ausfuehren(
        self, plan: list[tuple[dict[str, Any], int]], quelle: str
    ) -> None:
        self.daten.hub.lauf_aktiv = True
        self.daten.broadcast()
        await self._store_sichern()
        self.hass.bus.async_fire(
            EVENT_LAUF_GESTARTET,
            {
                "quelle": quelle,
                "plan": {k[CONF_KREIS_ID]: d for k, d in plan},
            },
        )
        abgebrochen = False
        try:
            sequenz = [(k, d) for k, d in plan if not k.get(CONF_PARALLEL)]
            parallel = [(k, d) for k, d in plan if k.get(CONF_PARALLEL)]
            self._parallel_tasks = [
                self.entry.async_create_background_task(
                    self.hass,
                    self._kreis_ausfuehren(kreis, dauer_min),
                    f"{DOMAIN}_kreis_{kreis[CONF_KREIS_ID]}",
                )
                for kreis, dauer_min in parallel
                if dauer_min > 0
            ]
            for kreis, dauer_min in sequenz:
                if not self.daten.hub.lauf_aktiv:  # Not-Aus-Abbruch (B3)
                    break
                await self._kreis_ausfuehren(kreis, dauer_min)
            if self._parallel_tasks:
                await asyncio.gather(*self._parallel_tasks, return_exceptions=True)
        except asyncio.CancelledError:
            abgebrochen = True
        finally:
            # F4: shield — beim Entfernen des Entries cancelt HA die
            # Background-Tasks ein zweites Mal mitten im Abschluss; der
            # geschützte innere Task schließt die Ventile trotzdem fertig.
            try:
                await asyncio.shield(
                    self.hass.async_create_task(
                        self._lauf_abschliessen(plan, quelle, abgebrochen)
                    )
                )
            except asyncio.CancelledError:
                pass  # innerer Abschluss-Task läuft geschützt weiter
            except Exception:
                _LOGGER.exception("Fehler beim Lauf-Abschluss")

    async def _kreis_ausfuehren(self, kreis: dict[str, Any], dauer_min: int) -> None:
        """Ein Kreis: jedes Ventil nacheinander volle Dauer (Kit: geteilte
        Slots laufen gleich lang, nacheinander). AUF → warten → Retry-Close."""
        if dauer_min <= 0:
            return
        for ventil in kreis.get(CONF_VENTILE, []):
            if not self.daten.hub.lauf_aktiv:  # Not-Aus zwischen Ventilen
                return
            if self._zustand(ventil) in NICHT_ERREICHBAR:
                _LOGGER.warning("Ventil %s nicht erreichbar — Slot übersprungen", ventil)
                continue
            await self._ventil_befehl(ventil, "turn_on")
            await asyncio.sleep(dauer_min * 60)
            await self._retry_close(ventil)
            await asyncio.sleep(DEFAULT_PAUSE_S)

    async def _lauf_abschliessen(
        self, plan: list[tuple[dict[str, Any], int]], quelle: str, abgebrochen: bool
    ) -> None:
        """B3-Schritte 4-6: Parallel-Tasks stoppen, Safety-Sweep, Flag AUS,
        Hängen-Check + Warn-Push, Bericht."""
        for task in self._parallel_tasks:
            if not task.done():
                task.cancel()
        self._parallel_tasks = []
        ventile = [v for kreis, _ in plan for v in kreis.get(CONF_VENTILE, [])]
        for ventil in ventile:  # Sicherheits-Sweep — egal, was vorher geschah
            await self._ventil_befehl(ventil, "turn_off")
        self.daten.hub.lauf_aktiv = False

        gegossen = [
            f"{k.get(CONF_KREIS_NAME, k[CONF_KREIS_ID])} {d} min" for k, d in plan if d > 0
        ]
        bericht = (
            f"{dt_util.now().strftime('%d.%m. %H:%M')} ({quelle}): "
            + (" · ".join(gegossen) if gegossen else "nichts zu bewässern")
        )
        if abgebrochen:
            bericht += " — abgebrochen (Not-Aus)"
        self.daten.hub.letzter_lauf_bericht = bericht
        self.daten.broadcast()
        await self._store_sichern()
        self.hass.bus.async_fire(
            EVENT_LAUF_BEENDET, {"quelle": quelle, "abgebrochen": abgebrochen, "bericht": bericht}
        )

        await asyncio.sleep(DEFAULT_RETRY_ABSTAND_S)  # Sweep im State ankommen lassen
        haengend = [v for v in ventile if self._zustand(v) == "on"]
        if haengend:
            await self._sende_push(
                "⚠️ Bewässerung: Ventil noch offen",
                "Ventil(e) ließen sich trotz Schließ-Wiederholungen und "
                f"Sicherheits-Sweep nicht schließen: {', '.join(haengend)}. "
                "Bitte manuell prüfen (Wasserhahn / Funkverbindung)!",
                kritisch=self._alarm_kritisch(),
            )

    async def _ventil_befehl(self, ventil: str, dienst: str) -> None:
        """switch.turn_on/off mit continue_on_error-Semantik (B3-Härtung)."""
        try:
            await self.hass.services.async_call(
                "switch", dienst, {"entity_id": ventil}, blocking=True
            )
        except Exception as exc:
            _LOGGER.warning("Ventil-Befehl %s auf %s fehlgeschlagen: %s", dienst, ventil, exc)

    async def _retry_close(self, ventil: str) -> bool:
        """Kanonischer Retry-Close (B3/B4/B5/B11): schließen, bis 'off' gemeldet."""
        for _versuch in range(DEFAULT_RETRY_ANZAHL):
            await self._ventil_befehl(ventil, "turn_off")
            await asyncio.sleep(DEFAULT_RETRY_ABSTAND_S)
            if self._zustand(ventil) == "off":
                return True
        return False

    # ------------------------------------------- Watchdog + Sitzung (B5-A/B9)

    @callback
    def _ventil_ereignis(self, ereignis) -> None:
        ventil = ereignis.data["entity_id"]
        neu = ereignis.data.get("new_state")
        alt = ereignis.data.get("old_state")
        neu_s = neu.state if neu else None
        alt_s = alt.state if alt else None

        if neu_s == "on" and alt_s != "on":
            # Volumen-Sitzung (B9): Baseline beim ERSTEN Ventil des Kreises
            # merken; ein Wieder-Öffnen vor dem Settle setzt die Sitzung fort.
            if (kreis := self._kreis_zu_ventil(ventil)) and kreis.get(CONF_FLOW_SENSOR):
                kid = kreis[CONF_KREIS_ID]
                if unsub := self._volumen_settle.pop(kid, None):
                    unsub()
                if kid not in self._volumen_baseline:
                    roh = self._zustand(kreis[CONF_FLOW_SENSOR])
                    if roh not in UNGUELTIG:
                        self._volumen_baseline[kid] = sicher_float(roh, 0.0)
            # Watchdog armieren: ein Timer PRO Öffnung (B5-A ohne for:-Falle).
            self._watchdog_armieren(ventil)
            # B4-Backstop (F2): Öffnungen AUSSERHALB eines Laufs bekommen
            # zusätzlich den kurzen Auto-Aus (Standard-Dauer, Default 10 min)
            # — der Executor besitzt seine Ventile, solange lauf_aktiv EIN ist.
            if not self.daten.hub.lauf_aktiv:
                self._auto_aus_armieren(ventil)
        elif alt_s == "on" and neu_s != "on":
            if unsub := self._watchdogs.pop(ventil, None):
                unsub()
            if unsub := self._auto_aus.pop(ventil, None):
                unsub()
            if neu_s == "off" and (kreis := self._kreis_zu_ventil(ventil)):
                kid = kreis[CONF_KREIS_ID]
                # B9: „zuletzt bewässert“ stempeln — egal ob Plan, Knopf,
                # Dose oder Handbetrieb.
                self.daten.kreis(kid).zuletzt_bewaessert = dt_util.utcnow()
                self.daten.broadcast()
                # Volumen-Sitzung abschließen, sobald ALLE Ventile des
                # Kreises zu sind (30 s Settle für den Integral-Sensor).
                if (
                    kreis.get(CONF_FLOW_SENSOR)
                    and kid in self._volumen_baseline
                    and all(
                        self._zustand(v) != "on"
                        for v in kreis.get(CONF_VENTILE, [])
                    )
                ):
                    if unsub := self._volumen_settle.pop(kid, None):
                        unsub()
                    self._volumen_settle[kid] = async_call_later(
                        self.hass,
                        VOLUMEN_SETTLE_S,
                        partial(self._volumen_abschluss, kid),
                    )

    @callback
    def _watchdog_armieren(self, ventil: str) -> None:
        if alte := self._watchdogs.pop(ventil, None):
            alte()
        notaus_min = sicher_float(
            self.entry.options.get(CONF_NOTAUS_MIN, DEFAULT_NOTAUS_MIN),
            DEFAULT_NOTAUS_MIN,
        )
        # partial auf die async-Methode: async_call_later erstellt daraus
        # einen Task im Event-Loop (keine sync-Lambda ⇒ kein Executor-Thread).
        self._watchdogs[ventil] = async_call_later(
            self.hass, notaus_min * 60, partial(self._notaus_watchdog, ventil)
        )

    @callback
    def _auto_aus_armieren(self, ventil: str) -> None:
        """B4: kurzer Backstop für Hand-Öffnungen (Dauer aus der
        Standard-Dauer-Number, zum Armier-Zeitpunkt gelesen — B4-Parität)."""
        if alte := self._auto_aus.pop(ventil, None):
            alte()
        minuten = self._zahl("number", CONF_STANDARD_DAUER, None, DEFAULT_STANDARD_DAUER)
        self._auto_aus[ventil] = async_call_later(
            self.hass, max(minuten, 1) * 60, partial(self._auto_aus_feuern, ventil)
        )

    async def _auto_aus_feuern(self, ventil: str, _jetzt: datetime | None = None) -> None:
        """B4-Aktion: noch offen UND kein Lauf aktiv (Post-Delay-Recheck —
        hat der Executor das Ventil inzwischen übernommen, abbrechen)."""
        self._auto_aus.pop(ventil, None)
        if self._zustand(ventil) != "on" or self.daten.hub.lauf_aktiv:
            return
        _LOGGER.info("Auto-Aus: %s nach Standard-Dauer geschlossen", ventil)
        await self._retry_close(ventil)

    async def _notaus_watchdog(self, ventil: str, _jetzt: datetime | None = None) -> None:
        """B5-A: Ventil hing länger als die Notaus-Schwelle offen."""
        self._watchdogs.pop(ventil, None)
        if self._zustand(ventil) != "on":
            return
        notaus_min = int(
            sicher_float(
                self.entry.options.get(CONF_NOTAUS_MIN, DEFAULT_NOTAUS_MIN),
                DEFAULT_NOTAUS_MIN,
            )
        )
        geschlossen = await self._retry_close(ventil)
        zustand = self.hass.states.get(ventil)
        name = (zustand.name if zustand else None) or ventil
        nachricht = (
            f"{name} war länger als {notaus_min} min ununterbrochen offen — "
            "Notaus ausgelöst und Ventil geschlossen (Funk-Ventil war evtl. "
            "zum regulären Schließzeitpunkt nicht erreichbar)."
        )
        if not geschlossen:
            nachricht += (
                " ACHTUNG: Ventil meldet trotz aller Schließversuche noch "
                "nicht „aus“ — bitte manuell prüfen!"
            )
        await self._sende_push(
            "⚠️ Garten-Ventil hing offen", nachricht, kritisch=self._alarm_kritisch()
        )

    # -------------------------------------------------- Neustart-Recovery (B5-B)

    async def _startup_recovery(self) -> None:
        """Nach HA-Neustart (oder gestorbenem Lauf) sind offene Ventile
        herrenlos: warten bis Funk-Ventile echte Zustände melden, dann
        zwangsschließen + Push (B5-B; Store deckt den Absturz-mitten-im-Lauf ab).
        """
        war_aktiv = self._war_lauf_aktiv
        self._war_lauf_aktiv = False
        if war_aktiv:
            await self._store_sichern()  # Flag sofort löschen (einmalige Recovery)
        # Echter HA-Boot ⇒ immer prüfen; Config-Reload ⇒ nur nach gestorbenem
        # Lauf (sonst würde ein Reload manuell geöffnete Ventile schließen).
        if not war_aktiv and self.hass.is_running:
            return
        ventile = self._alle_ventile()
        if not ventile:
            return
        frist = self.hass.loop.time() + 120  # B5: max 2 min auf Funk warten
        while self.hass.loop.time() < frist:
            if any(self._zustand(v) in ("on", "off") for v in ventile):
                break
            await asyncio.sleep(5)
        offene = [v for v in ventile if self._zustand(v) == "on"]
        if not offene:
            return
        for ventil in offene:
            await self._retry_close(ventil)
        namen = ", ".join(
            (z.name if (z := self.hass.states.get(v)) else v) for v in offene
        )
        await self._sende_push(
            "⚠️ Ventil nach HA-Neustart geschlossen",
            "Sicherheitsmaßnahme: Nach dem Neustart von Home Assistant kann "
            "keine laufende Bewässerung diese Ventile mehr schließen — sie "
            f"wurden deshalb sofort zwangsgeschlossen: {namen}.",
            kritisch=self._alarm_kritisch(),
        )

    async def _store_sichern(self) -> None:
        kids = [k[CONF_KREIS_ID] for k in self._kreise()]
        await self._store.async_save(
            {
                "lauf_aktiv": self.daten.hub.lauf_aktiv,
                "dosen": {kid: self.daten.kreis(kid).dosen_heute for kid in kids},
                "liter_heute": {kid: self.daten.kreis(kid).liter_heute for kid in kids},
                "liter_monat": {kid: self.daten.kreis(kid).liter_monat for kid in kids},
                # Mindestabstand-Gate (B6 ⑤) muss Neustarts überleben — im Kit
                # tut das last_triggered automatisch, hier der Store.
                "letzte_dose": {
                    kid: dt.isoformat() for kid, dt in self._letzte_dose.items()
                },
                "datum": dt_util.now().date().isoformat(),
                "monat": dt_util.now().strftime("%Y-%m"),
            }
        )

    async def _store_laden(self) -> None:
        """Zähler über Neustarts retten: Dosen/Liter des heutigen Tages bzw.
        Monats wiederherstellen (Restore-Sensoren decken nur Zeitstempel ab)."""
        g = await self._store.async_load() or {}
        self._war_lauf_aktiv = bool(g.get("lauf_aktiv"))
        jetzt = dt_util.now()
        if g.get("datum") == jetzt.date().isoformat():
            for kid, n in (g.get("dosen") or {}).items():
                self.daten.kreis(kid).dosen_heute = int(n or 0)
            for kid, wert in (g.get("liter_heute") or {}).items():
                if wert is not None:
                    self.daten.kreis(kid).liter_heute = float(wert)
        if g.get("monat") == jetzt.strftime("%Y-%m"):
            for kid, wert in (g.get("liter_monat") or {}).items():
                if wert is not None:
                    self.daten.kreis(kid).liter_monat = float(wert)
        for kid, iso in (g.get("letzte_dose") or {}).items():
            if iso and (dt := dt_util.parse_datetime(iso)):
                self._letzte_dose[kid] = dt

    # ---------------------------------------- Topf-Frequenzbewässerung (B6)

    @callback
    def _topf_boden_ereignis(self, ereignis) -> None:
        """Unterschreitungs-Entprellung: Feuchte fällt unter das Sollband
        ⇒ 10-min-Timer; steigt sie vorher zurück, wird er verworfen."""
        sensor = ereignis.data["entity_id"]
        for kreis in self._kreise():
            if (
                kreis.get(CONF_KREIS_TYP) != "topf"
                or sensor not in (kreis.get(CONF_BODENSENSOREN) or [])
            ):
                continue
            kid = kreis[CONF_KREIS_ID]
            soil = self._topf_boden(kreis)
            low = self._zahl("number", "ziel_unten", kid, 50.0)
            if soil is not None and soil < low:
                if kid not in self._topf_debounce:
                    self._topf_debounce[kid] = async_call_later(
                        self.hass,
                        TOPF_UNTERSCHREITUNG_MIN * 60,
                        partial(self._topf_debounce_feuern, kid),
                    )
            elif unsub := self._topf_debounce.pop(kid, None):
                unsub()

    async def _topf_debounce_feuern(self, kid: str, _jetzt: datetime | None = None) -> None:
        self._topf_debounce.pop(kid, None)
        await self._topf_pruefen(kid)

    @callback
    def _topf_runde(self) -> None:
        """B6-Nach-Check (alle 30 min + bei Plan-neu): verschobene Dosen
        nachholen, z. B. nach Peak-Sonne oder abgelaufenem Mindestabstand."""
        for kreis in self._kreise():
            if kreis.get(CONF_KREIS_TYP) == "topf":
                self.hass.async_create_task(self._topf_pruefen(kreis[CONF_KREIS_ID]))

    def _topf_boden(self, kreis: dict[str, Any]) -> float | None:
        """Minimum über die Sensoren; nicht-numerisch ⇒ -1 (B6-float(-1)-
        Semantik: blockiert über die Glitch-Grenze — nie blind dosieren)."""
        sensoren = kreis.get(CONF_BODENSENSOREN) or []
        if not sensoren:
            return None
        return min(sicher_float(self._zustand(s), -1.0) for s in sensoren)

    async def _topf_pruefen(self, kid: str) -> None:
        """Die 9 B6-Gates; bei Erfolg: Zähler ZUERST, dann Dosis-Task."""
        kreis = next(
            (k for k in self._kreise() if k[CONF_KREIS_ID] == kid), None
        )
        if self._gestoppt or kreis is None or kreis.get(CONF_KREIS_TYP) != "topf":
            return
        if self._dose_tasks.get(kid) and not self._dose_tasks[kid].done():
            return  # Dose läuft bereits
        t = {**TOPF_DEFAULTS, **self.entry.options.get("topf", {})}
        laufzeit = self.daten.kreis(kid)
        soil = self._topf_boden(kreis)
        low = self._zahl("number", "ziel_unten", kid, 50.0)
        high = self._zahl("number", "ziel_oben", kid, 70.0)
        strahlung_sensor = self.entry.options.get(CONF_STRAHLUNG_SENSOR) or None
        regen_sensor = self.entry.options.get(CONF_REGEN_SENSOR) or None
        lt = self._letzte_dose.get(kid)
        gates_ok = (
            self._an("topf_steuerung")  # ① Master (Anzeigename: Topf-Frequenzbewässerung)
            and self._an("aktiv", kid)  # Kreis nicht pausiert (Integration)
            and soil is not None
            and float(t["glitch_grenze"]) < soil < low  # ② gültiges Fenster
            and (  # ③ Peak-Sonnen-Sperre
                strahlung_sensor is None
                or sicher_float(self._zustand(strahlung_sensor), 0.0)
                < self._zahl(
                    "number", "strahlung_schwelle", None, DEFAULT_STRAHLUNG_SCHWELLE
                )
            )
            and laufzeit.dosen_heute < int(t["max_dosen"])  # ④ Tageslimit
            and (  # ⑤ Mindestabstand
                lt is None
                or (dt_util.utcnow() - lt).total_seconds()
                > float(t["min_intervall_min"]) * 60
            )
            and not self._an("heute_ueberspringen")  # ⑥
            and not self._an("urlaubsmodus")  # ⑦
            and (  # ⑧ Regen-Veto
                regen_sensor is None
                or sicher_float(self._zustand(regen_sensor), 0.0)
                < self._zahl(
                    "number", "regen_beobachtet_mm", None, DEFAULT_REGEN_BEOBACHTET
                )
            )
            and all(  # ⑨ Ventil(e) zu
                self._zustand(v) == "off" for v in kreis.get(CONF_VENTILE, [])
            )
        )
        if not gates_ok:
            return
        # Dosis-Formel (B6): needed / (k × headroom), geklemmt [1, dosis_max]
        k_wert = self._zahl("number", "k_faktor", kid, 2.0)
        headroom = (100 - soil) / 100
        needed = max(high - soil, 0.0)
        raw = needed / (k_wert * headroom) if (k_wert * headroom) > 0 else 0.0
        dose_min = math.floor(max(min(raw, float(t["dosis_max_min"])), 1.0) * 10 + 0.5) / 10
        # Zähler ZUERST (B6): auch ein fehlgeschlagener Öffnungsversuch zählt.
        laufzeit.dosen_heute += 1
        self._letzte_dose[kid] = dt_util.utcnow()
        self.daten.broadcast()
        await self._store_sichern()
        self._dose_tasks[kid] = self.entry.async_create_background_task(
            self.hass, self._dose_ausfuehren(kreis, dose_min), f"{DOMAIN}_dose_{kid}"
        )

    async def _dose_ausfuehren(self, kreis: dict[str, Any], dose_min: float) -> None:
        ventile = kreis.get(CONF_VENTILE, [])
        _LOGGER.info(
            "Topf-Dose %s: %.1f min auf %s", kreis[CONF_KREIS_ID], dose_min, ventile
        )
        try:
            for ventil in ventile:
                await self._ventil_befehl(ventil, "turn_on")
            await asyncio.sleep(dose_min * 60)
        except asyncio.CancelledError:
            pass
        finally:
            try:
                await asyncio.shield(
                    self.hass.async_create_task(self._ventile_schliessen(ventile))
                )
            except asyncio.CancelledError:
                pass  # innerer Schließ-Task läuft geschützt weiter
            except Exception:
                _LOGGER.exception("Fehler beim Schließen der Topf-Dose")

    async def _ventile_schliessen(self, ventile: list[str]) -> None:
        for ventil in ventile:
            await self._retry_close(ventil)

    # ------------------------------------------------- Alarme (B7/B8/B10)

    @callback
    def _leck_ereignis(self, ereignis) -> None:
        neu = ereignis.data.get("new_state")
        alt = ereignis.data.get("old_state")
        if not neu or neu.state != "on" or (alt and alt.state == "on"):
            return
        name = neu.name or ereignis.data["entity_id"]
        self.hass.async_create_task(
            self._sende_push(
                "⚠️ Wasserleck im Garten",
                f"{name} meldet ein Leck.",
                kritisch=self._alarm_kritisch(),
            )
        )

    @callback
    def _versorgung_ereignis(self, ereignis) -> None:
        sensor = ereignis.data["entity_id"]
        neu = ereignis.data.get("new_state")
        alt = ereignis.data.get("old_state")
        if neu and neu.state == "off":
            # F8: nur echte to:-off-Flanken (B8) — Attribut-Updates und
            # unavailable-Flattern re-armen sonst alle 60 s einen neuen Push.
            if alt is None or alt.state == "off":
                return
            if sensor not in self._versorgung_debounce:
                self._versorgung_debounce[sensor] = async_call_later(
                    self.hass, VERSORGUNG_DEBOUNCE_S, partial(self._versorgung_pruefen, sensor)
                )
        elif unsub := self._versorgung_debounce.pop(sensor, None):
            unsub()

    async def _versorgung_pruefen(self, sensor: str, _jetzt: datetime | None = None) -> None:
        """B8: Versorgung ≥ 1 min weg UND zugehöriges Ventil per HA geöffnet
        (user_id/parent_id im Kontext — der Geräteknopf erzeugt keinen)."""
        self._versorgung_debounce.pop(sensor, None)
        if self._zustand(sensor) != "off":
            return
        kreis = next(
            (k for k in self._kreise() if k.get(CONF_VERSORGUNG) == sensor), None
        )
        if kreis is None:
            return
        for ventil in kreis.get(CONF_VENTILE, []):
            zustand = self.hass.states.get(ventil)
            if (
                zustand is not None
                and zustand.state == "on"
                and (
                    zustand.context.user_id is not None
                    or zustand.context.parent_id is not None
                )
            ):
                await self._sende_push(
                    "Garten: Kein Wasser",
                    f"Ventil „{zustand.name}“ ist offen, aber die Wasserversorgung "
                    f"fehlt seit über {VERSORGUNG_DEBOUNCE_S // 60} min.",
                    kritisch=self._alarm_kritisch(),
                )
                return

    @callback
    def _batterie_ereignis(self, ereignis) -> None:
        sensor = ereignis.data["entity_id"]
        neu = ereignis.data.get("new_state")
        wert = sicher_float(neu.state if neu else None, 100.0)
        if wert < BATTERIE_SCHWELLE:
            if sensor not in self._batterie_debounce:
                self._batterie_debounce[sensor] = async_call_later(
                    self.hass,
                    BATTERIE_DEBOUNCE_MIN * 60,
                    partial(self._batterie_pruefen, sensor),
                )
        elif unsub := self._batterie_debounce.pop(sensor, None):
            unsub()

    async def _batterie_pruefen(self, sensor: str, _jetzt: datetime | None = None) -> None:
        """B10: < Schwelle seit 30 min; global max. 1 Push pro 24 h."""
        self._batterie_debounce.pop(sensor, None)
        zustand = self.hass.states.get(sensor)
        wert = sicher_float(zustand.state if zustand else None, 100.0)
        if wert >= BATTERIE_SCHWELLE:
            return
        jetzt = dt_util.utcnow()
        if (
            self._batterie_zuletzt is not None
            and (jetzt - self._batterie_zuletzt).total_seconds()
            < BATTERIE_COOLDOWN_H * 3600
        ):
            return
        self._batterie_zuletzt = jetzt
        name = (zustand.name if zustand else None) or sensor
        await self._sende_push(
            "🔋 Batterie niedrig",
            f"{name}: {int(wert)} %. Bitte Batterie tauschen/laden.",
            kritisch=self._alarm_kritisch(),
        )

    # ---------------------------------------------- Trocken-Report (B12)

    async def _trocken_report(self, _jetzt: datetime) -> None:
        """08:00: Kreise melden, deren Boden trotz Automatik kritisch trocken
        ist (unter der halben Veto-Schwelle) — gedämpft, wenn in den letzten
        24 h bewässert wurde. Ein gebündelter Push für alle Betroffenen."""
        betroffen: list[str] = []
        for kreis in self._kreise():
            kid = kreis[CONF_KREIS_ID]
            if not self._an("aktiv", kid):
                continue
            werte = [
                sicher_float(self._zustand(s), -1.0)
                for s in kreis.get(CONF_BODENSENSOREN) or []
            ]
            werte = [w for w in werte if w >= 0]
            if not werte:
                continue
            soil = min(werte)
            kritisch = self._zahl("number", "veto_schwelle", kid, 70.0) / 2
            if soil >= kritisch:
                continue
            zuletzt = self.daten.kreis(kid).zuletzt_bewaessert
            if (
                zuletzt is not None
                and (dt_util.utcnow() - zuletzt).total_seconds()
                < REPORT_DAEMPFER_H * 3600
            ):
                continue  # Dämpfer: kürzlich bewässert — Alarm wäre Lärm
            betroffen.append(
                f"{kreis.get(CONF_KREIS_NAME, kid)} {int(soil + 0.5)}%"
            )
        if betroffen:
            await self._sende_push(
                "🌵 Boden kritisch trocken",
                " · ".join(betroffen),
                kritisch=self._alarm_kritisch(),
            )

    # ----------------------------------------------------- Volumen (B9)

    async def _volumen_abschluss(self, kid: str, _jetzt: datetime | None = None) -> None:
        """30 s nach dem letzten Ventil-Schließen: Sitzungs-Liter aus dem
        kumulativen Flow-Sensor (Settle-Falle: Integral braucht den nächsten
        Null-Durchfluss-Messwert)."""
        self._volumen_settle.pop(kid, None)
        kreis = next((k for k in self._kreise() if k[CONF_KREIS_ID] == kid), None)
        baseline = self._volumen_baseline.pop(kid, None)
        if kreis is None or baseline is None:
            return
        flow = kreis.get(CONF_FLOW_SENSOR)
        aktuell = sicher_float(self._zustand(flow), baseline)
        liter = max(aktuell - baseline, 0.0) * 1000
        if liter <= 0:
            return
        laufzeit = self.daten.kreis(kid)
        laufzeit.letzte_sitzung_liter = round(liter, 1)
        laufzeit.liter_heute = round((laufzeit.liter_heute or 0.0) + liter, 1)
        laufzeit.liter_monat = round((laufzeit.liter_monat or 0.0) + liter, 1)
        self.daten.broadcast()
        await self._store_sichern()

    # -------------------------------------------------------------- Aktionen

    async def plan_neu(self) -> None:
        await self._recompute_alle()
        self._topf_runde()

    async def sofort_start(self) -> None:
        await self.starte_lauf(quelle="Manuell")

    async def not_aus(self) -> None:
        """B11: Lauf abbrechen, Sofort-Sweep an alle, dann je Ventil
        retry-nachfassen, Erfolg/Warnung pushen."""
        self.daten.hub.lauf_aktiv = False  # Executor überspringt Rest-Slots
        for sammlung in (
            self._topf_debounce,
            self._versorgung_debounce,
            self._batterie_debounce,
            self._volumen_settle,
        ):
            for unsub in sammlung.values():
                unsub()
            sammlung.clear()
        if self._lauf_task and not self._lauf_task.done():
            self._lauf_task.cancel()
        for task in self._parallel_tasks:
            if not task.done():
                task.cancel()
        for task in self._dose_tasks.values():
            if not task.done():
                task.cancel()
        ventile = self._alle_ventile()
        for ventil in ventile:  # 2a) Sofort-Sweep: erster Befehl an ALLE sofort
            await self._ventil_befehl(ventil, "turn_off")
        for ventil in ventile:  # 2b) retry-gehärtet nachfassen
            await self._retry_close(ventil)
        # Alles, was nicht 'off' ist (auch unerreichbar), zählt als offen (B11).
        noch_offen = [v for v in ventile if self._zustand(v) != "off"]
        if noch_offen:
            nachricht = (
                f"ACHTUNG: {len(noch_offen)} Ventil(e) melden trotz aller "
                "Schließ-Versuche nicht „aus“ (offen oder unerreichbar): "
                f"{', '.join(noch_offen)}. Bitte manuell prüfen "
                "(Wasserhahn/Funkverbindung)!"
            )
        else:
            nachricht = f"Alle {len(ventile)} Ventile melden „aus“."
        await self._sende_push("🛑 Not-Aus Bewässerung", nachricht, kritisch=self._alarm_kritisch())
        self.daten.broadcast()
        await self._store_sichern()

    async def dosis_geben(self, kid: str) -> None:
        """Service: sofortige Topf-Dose — umgeht die Plan-Gates (Score,
        Intervall, Limit), respektiert aber die Sicherheits-Basics:
        Kreis existiert + Typ Topf + Ventile zu + keine Dose läuft."""
        kreis = next((k for k in self._kreise() if k[CONF_KREIS_ID] == kid), None)
        if (
            self._gestoppt
            or kreis is None
            or kreis.get(CONF_KREIS_TYP) != "topf"
            or (self._dose_tasks.get(kid) and not self._dose_tasks[kid].done())
            or any(self._zustand(v) == "on" for v in kreis.get(CONF_VENTILE, []))
        ):
            _LOGGER.warning("dosis_geben(%s): nicht möglich (Kreis/Typ/Ventil/Dose)", kid)
            return
        t = {**TOPF_DEFAULTS, **self.entry.options.get("topf", {})}
        soil = self._topf_boden(kreis)
        high = self._zahl("number", "ziel_oben", kid, 70.0)
        k_wert = self._zahl("number", "k_faktor", kid, 2.0)
        if soil is not None and 0 <= soil < 100 and k_wert > 0:
            headroom = (100 - soil) / 100
            raw = max(high - soil, 0.0) / (k_wert * headroom) if headroom > 0 else 0.0
            dose_min = math.floor(max(min(raw, float(t["dosis_max_min"])), 1.0) * 10 + 0.5) / 10
        else:
            dose_min = float(t["dosis_max_min"])
        laufzeit = self.daten.kreis(kid)
        laufzeit.dosen_heute += 1
        self._letzte_dose[kid] = dt_util.utcnow()
        self.daten.broadcast()
        await self._store_sichern()
        self._dose_tasks[kid] = self.entry.async_create_background_task(
            self.hass, self._dose_ausfuehren(kreis, dose_min), f"{DOMAIN}_dose_{kid}"
        )

    # ----------------------------------------------------------------- Push

    def _alarm_kritisch(self) -> bool:
        return bool(self.entry.options.get(CONF_PUSH_KRITISCH, True))

    async def _sende_push(self, titel: str, nachricht: str, kritisch: bool) -> None:
        dienste = self.entry.options.get(CONF_NOTIFY) or []
        if not dienste:
            return
        payload: dict[str, Any] = {}
        if kritisch:
            payload["push"] = {"interruption-level": "time-sensitive"}
        if pfad := (self.entry.options.get(CONF_DASHBOARD_PFAD) or "").strip():
            payload["url"] = pfad
            payload["clickAction"] = pfad
        for dienst in dienste:
            if not dienst.startswith("notify."):
                continue
            try:
                await self.hass.services.async_call(
                    "notify",
                    dienst.split(".", 1)[1],
                    {"title": titel, "message": nachricht, "data": payload},
                    blocking=False,
                )
            except Exception as exc:
                _LOGGER.error("Push über %s fehlgeschlagen: %s", dienst, exc)
