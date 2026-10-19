"""Actual controller methods against synthetic states/services, never real valves.

Stdlib AST mode and CI full HA imports execute the same assertions.
"""
import ast
import asyncio
import __future__
from datetime import datetime, timedelta, timezone, time as time_t
from functools import partial
import logging
import math
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "custom_components/garten_bewaesserung"
sys.path.insert(0, str(SOURCE))
import soil
import pause
import score
import const
sys.path.remove(str(SOURCE))  # never shadow stdlib calendar with our HA platform

HA_RUNTIME = "--ha-runtime" in sys.argv
if HA_RUNTIME:
    sys.argv.remove("--ha-runtime")
    sys.path.insert(0, str(ROOT))
    import homeassistant
    from custom_components.garten_bewaesserung.controller import GartenController
else:
    ns = {**vars(const), **vars(score), **vars(soil), "Pause": pause.Pause,
          "asyncio": asyncio, "partial": partial, "datetime": datetime,
          "timedelta": timedelta, "time_t": time_t, "math": math,
          "callback": lambda f: f, "_LOGGER": logging.getLogger(__name__),
          "NICHT_ERREICHBAR": ("unavailable", "unknown", None),
          "UNGUELTIG": ("unknown", "unavailable", "", None)}
    for file in ("soil_controller.py", "controller.py"):
        classes = [n for n in ast.parse((SOURCE/file).read_text()).body if isinstance(n, ast.ClassDef)]
        exec(compile(ast.Module(body=classes, type_ignores=[]), file, "exec",
                     flags=__future__.annotations.compiler_flag), ns)
    GartenController = ns["GartenController"]

NOW = datetime(2026, 10, 19, 8, tzinfo=timezone.utc)


class SoilControllerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.records = {}
        clock = NS(utcnow=lambda: NOW, now=lambda: NOW, parse_datetime=datetime.fromisoformat)
        registry = NS(async_get=lambda eid: self.records.get(eid))
        globals_seen = set()
        for cls in GartenController.__mro__:
            for method in cls.__dict__.values():
                if not hasattr(method, "__globals__") or id(method.__globals__) in globals_seen:
                    continue
                globals_seen.add(id(method.__globals__))
                p = patch.dict(method.__globals__, {
                    "dt_util": clock, "er": NS(async_get=lambda hass: registry),
                    "async_track_point_in_time": Mock(return_value=Mock()),
                    "async_call_later": Mock(return_value=Mock()),
                })
                p.start()
                self.addCleanup(p.stop)
        self.zones = [{"id": "lawn", "name": "Lawn", "typ": "rasen",
                       "bodensensoren": ["sensor.soil"], "ventile": ["switch.lawn"]},
                      {"id": "pot", "name": "Pot", "typ": "topf",
                       "bodensensoren": ["sensor.pot"], "ventile": ["switch.pot"]}]
        self.states = {}
        self.runtimes = {}
        c = self.c = object.__new__(GartenController)
        c._gestoppt, c.pause_ready = False, True
        c.pause = pause.Pause()
        c._pause_lock = asyncio.Lock()
        c._pause_generation = 0
        c._topf_debounce, c._dose_tasks, c._letzte_dose = {}, {}, {}
        c._batterie_debounce, c._batterie_zuletzt = {}, None
        c._zyklus_aktiv = set()
        c._wetter_retry_unsub = None
        c._kreise = lambda: self.zones
        c._zustand = lambda eid: self.states[eid].state if eid in self.states else None
        c._zahl = lambda domain, key, kid, default: default
        c._an = lambda key, kid=None: key in ("aktiv", "topf_steuerung")
        c._eid = lambda *args: None
        c._store = NS(async_save=AsyncMock(), async_load=AsyncMock(return_value={}))
        c._store_sichern = AsyncMock()
        c._arme_tagestimer = Mock()
        c._recompute_alle = AsyncMock()
        c._sende_push = AsyncMock()
        c._ventile_schliessen = AsyncMock()
        c._setze_dauer = AsyncMock()
        c.hass = NS(states=NS(get=lambda eid: self.states.get(eid)),
                    config=NS(latitude=47), services=NS(async_call=AsyncMock(return_value={})))
        c.entry = NS(entry_id="test", options={"kreise": self.zones},
                     async_create_background_task=Mock())
        def runtime(kid):
            if kid not in self.runtimes:
                self.runtimes[kid] = NS(boden=None, score=None, status=None, faktoren={},
                    zuletzt_bewaessert=None, dosen_heute=0, dosis_grund=None, dosis_details={})
            return self.runtimes[kid]
        c.daten = NS(kreis=runtime, hub=NS(lauf_aktiv=False, lauf_historie=[]), broadcast=Mock())
        c._soil_init()
        c._soil_load({})
        for k in self.zones:
            c._soil_after[k["id"]] = NOW-timedelta(seconds=1)
            self.state(k["bodensensoren"][0], "5")
            self.state(k["ventile"][0], "off")

    def state(self, eid, value, **attrs):
        self.states[eid] = NS(state=value, last_reported=NOW, last_changed=NOW-timedelta(days=30),
                              attributes=attrs, name=eid)

    async def test_morning_report_active_pauses_all_reasons(self):
        for reason in ("Winterpause", "Urlaub", "Sonstiges"):
            self.c.pause.active, self.c.pause.reason = True, reason
            await self.c._trocken_report(NOW)
        self.c._sende_push.assert_not_awaited()

    async def test_reason_alone_and_fresh_low_value_reports(self):
        self.c.pause.reason = "Winterpause"
        await self.c._trocken_report(NOW)
        self.c._sende_push.assert_awaited_once()
        self.assertIn("Lawn 5%", self.c._sende_push.call_args.args[1])

    async def test_independent_seasons_inheritance_and_override(self):
        await self.c.soil_change(mode=soil.STORED)
        self.assertEqual(self.c.soil_reading(self.zones[0])[1], "eingelagert")
        self.assertFalse(self.c.pause.active)
        await self.c.soil_change("lawn", mode=soil.ACTIVE)
        self.assertEqual(self.c.soil_reading(self.zones[0])[1], "wartet_auf_messwert")
        self.assertEqual(self.c.soil_reading(self.zones[1])[1], "eingelagert")
        self.c._soil_after["lawn"] = NOW-timedelta(microseconds=1)
        self.assertEqual(self.c.soil_reading(self.zones[0]), (5, "aktiv"))

    async def test_holiday_does_not_park_automatic_sensors(self):
        self.c.pause.active, self.c.pause.reason = True, "Urlaub"
        self.assertEqual(self.c.soil_reading(self.zones[0]), (5, "aktiv"))
        self.c.pause.reason = "Winterpause"
        self.c._soil_sync()
        self.assertEqual(self.c.soil_reading(self.zones[0]), (None, "eingelagert"))
        self.c.pause.active = False
        self.c._soil_sync()
        self.assertEqual(self.c.soil_reading(self.zones[0])[1], "wartet_auf_messwert")

    async def test_parked_reports_and_manual_dose_are_blocked(self):
        await self.c.soil_change(mode=soil.STORED)
        await self.c._trocken_report(NOW)
        await self.c.dosis_geben("pot")
        self.c._sende_push.assert_not_awaited()
        self.c.entry.async_create_background_task.assert_not_called()
        self.assertEqual(self.c.daten.kreis("pot").dosen_heute, 0)

    async def test_configured_missing_is_not_sensorless_and_fallback_is_explicit(self):
        self.states.pop("sensor.soil")
        self.assertFalse(self.c.soil_allowed(self.zones[0]))
        self.c.soil_policy("lawn").weather_only = True
        self.assertTrue(self.c.soil_allowed(self.zones[0]))
        self.c.soil_policy("pot").weather_only = True
        self.states.pop("sensor.pot")
        self.assertFalse(self.c.soil_allowed(self.zones[1]))
        self.zones[0]["bodensensoren"] = []
        self.c.soil_policy("lawn").weather_only = False
        self.assertTrue(self.c.soil_allowed(self.zones[0]))

    async def test_multiple_sensors_require_all_valid_and_enabled(self):
        self.zones[0]["bodensensoren"].append("sensor.wet")
        self.state("sensor.wet", "80")
        self.assertEqual(self.c.soil_reading(self.zones[0]), (5, "aktiv"))
        self.records["sensor.wet"] = NS(disabled_by="user")
        self.assertIsNone(self.c.soil_reading(self.zones[0])[0])
        self.records.clear()
        self.state("sensor.wet", "nan")
        self.assertIsNone(self.c.soil_reading(self.zones[0])[0])

    async def test_startup_never_trusts_cached_low_value(self):
        self.c._soil_load(self.c._soil_save())
        self.assertEqual(self.c.soil_reading(self.zones[0])[1], "wartet_auf_messwert")
        await self.c._trocken_report(NOW)
        self.c._sende_push.assert_not_awaited()

    async def test_expired_during_restart_does_not_catch_up(self):
        self.c.soil.mode, self.c.soil.timed = soil.STORED, True
        self.c.soil.until = (NOW-timedelta(days=1)).isoformat()
        self.c._soil_sync()
        await self.c._soil_expired(NOW)
        self.assertEqual(self.c.soil.mode, soil.ACTIVE)
        self.assertFalse(self.c.soil_allowed(self.zones[0]))
        self.c.entry.async_create_background_task.assert_not_called()
        self.c._arme_tagestimer.assert_called_once()

    async def test_invalid_storage_never_masks_fault_or_enables_fallback(self):
        self.c._soil_load({"garden": {"mode": "broken"}})
        self.c.soil_policy("lawn").weather_only = True
        self.assertFalse(self.c.soil_allowed(self.zones[0]))
        self.assertTrue(self.c.soil_attributes(self.zones[0])["monitoring_expected"])
        self.assertEqual(self.c.soil_reading(self.zones[0])[1], "fehler")

    async def test_pause_closes_only_affected_valves_and_keeps_off_command_allowed(self):
        self.state("switch.lawn", "on")
        self.state("switch.pot", "on")
        await self.c.soil_change("lawn", mode=soil.STORED)
        self.c._ventile_schliessen.assert_awaited_once_with(["switch.lawn"])
        await self.c._ventil_befehl("switch.lawn", "turn_on")
        self.c.hass.services.async_call.assert_not_awaited()
        await self.c._ventil_befehl("switch.lawn", "turn_off")
        self.assertEqual(self.c.hass.services.async_call.call_args.args[1], "turn_off")

    async def test_battery_suppression_is_proven_device_scoped(self):
        self.records["sensor.battery"] = NS(device_id="soil-device")
        self.records["sensor.soil"] = NS(device_id="soil-device", disabled_by=None)
        self.assertFalse(self.c._soil_battery_suppressed("sensor.battery"))
        await self.c.soil_change("lawn", mode=soil.STORED)
        self.assertTrue(self.c._soil_battery_suppressed("sensor.battery"))
        self.zones[1]["bodensensoren"] = ["sensor.soil"]
        self.assertFalse(self.c._soil_battery_suppressed("sensor.battery"))
        await self.c.soil_change("pot", mode=soil.STORED)
        self.assertTrue(self.c._soil_battery_suppressed("sensor.battery"))
        self.records["switch.lawn"] = NS(device_id="soil-device")
        self.assertFalse(self.c._soil_battery_suppressed("sensor.battery"))
        self.assertFalse(self.c._soil_battery_suppressed("sensor.unknown"))

    async def test_battery_timer_rechecks_season_before_sending(self):
        self.records["sensor.battery"] = NS(device_id="soil-device")
        self.records["sensor.soil"] = NS(device_id="soil-device", disabled_by=None)
        self.state("sensor.battery", "5")
        await self.c.soil_change("lawn", mode=soil.STORED)
        await self.c._batterie_pruefen("sensor.battery")
        self.c._sende_push.assert_not_awaited()
        self.records.clear()  # unknown device role: don't swallow safety alerts
        await self.c._batterie_pruefen("sensor.battery")
        self.c._sende_push.assert_awaited_once()

    async def test_generation_blocks_dose_during_store_even_if_resumed(self):
        async def interleave():
            self.c._soil_sync(force={"pot"})
        self.c._store_sichern.side_effect = interleave
        await self.c.dosis_geben("pot")
        self.c.entry.async_create_background_task.assert_not_called()

    async def test_stale_queued_dose_never_opens(self):
        k = {**self.zones[1], "_soil_generation": self.c._soil_generation["pot"]}
        self.c._soil_sync(force={"pot"})
        self.c._soil_after["pot"] = NOW-timedelta(seconds=1)
        await self.c._dose_ausfuehren(k, 1)
        self.c.hass.services.async_call.assert_not_awaited()

    async def test_recompute_after_await_uses_current_soil_policy(self):
        async def weather(*args, **kwargs):
            self.c.soil.mode = soil.STORED
            return {}
        self.c.hass.services.async_call.side_effect = weather
        await GartenController._recompute_alle(self.c)
        for kid in ("lawn", "pot"):
            self.assertIsNone(self.c.daten.kreis(kid).boden)
            self.assertIsNone(self.c.daten.kreis(kid).score)
        self.assertEqual([call.args for call in self.c._setze_dauer.call_args_list],
                         [("lawn", 0), ("pot", 0)])

    async def test_open_in_flight_is_closed_again_after_season_change(self):
        async def pause_during_open(*args, **kwargs):
            self.c.soil.mode = soil.STORED
            self.c._soil_sync()
        self.c.hass.services.async_call.side_effect = pause_during_open
        await self.c._ventil_befehl("switch.lawn", "turn_on")
        self.c._ventile_schliessen.assert_awaited_once_with(["switch.lawn"])

    async def test_unchanged_report_refreshes_soil_without_immediate_dose(self):
        self.c._soil_after["lawn"] = NOW-timedelta(microseconds=1)
        self.c._soil_event(NS(data={"entity_id": "sensor.soil"}))
        self.assertEqual(self.c.daten.kreis("lawn").boden, 5)
        self.c.entry.async_create_background_task.assert_not_called()

    async def test_stale_queued_lawn_plan_cannot_reopen_after_resume(self):
        k = {**self.zones[0], "_soil_generation": self.c._soil_generation["lawn"]}
        self.c._soil_sync(force={"lawn"})
        self.c._soil_after["lawn"] = NOW-timedelta(seconds=1)
        self.c.daten.hub.lauf_aktiv = True
        with patch("asyncio.sleep", new=AsyncMock()):
            await self.c._kreis_ausfuehren(k, 1)
        self.c.hass.services.async_call.assert_not_awaited()
        self.assertTrue(k["_soil_skipped"])

    async def test_pause_change_cancels_pending_pot_debounce(self):
        unsubscribe = self.c._topf_debounce["pot"] = Mock()
        await self.c.soil_change("pot", mode=soil.STORED)
        unsubscribe.assert_called_once()
        self.assertNotIn("pot", self.c._topf_debounce)

    async def test_garden_sensor_pause_does_not_stop_sensorless_weather_zone(self):
        self.zones[0]["bodensensoren"] = []
        self.state("switch.lawn", "on")
        before = self.c._soil_generation["lawn"]
        await self.c.soil_change(mode=soil.STORED)
        self.assertEqual(self.c._soil_generation["lawn"], before)
        self.c._ventile_schliessen.assert_not_awaited()
        self.assertTrue(self.c.soil_allowed(self.zones[0]))


if __name__ == "__main__":
    unittest.main()
