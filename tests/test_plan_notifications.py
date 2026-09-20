"""Execute real notification methods with synthetic services, never real valves.

Stdlib mode extracts the unchanged methods via AST; --ha-runtime imports the
complete controller in the pinned HA image. Both run identical regressions.
"""
import ast
import asyncio
from datetime import datetime, time, timezone
import logging
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

ROOT = Path(__file__).parents[1]
NOW = datetime(2026, 9, 20, 18, tzinfo=timezone.utc)
if '--ha-runtime' in sys.argv:
    sys.argv.remove('--ha-runtime')
    sys.path.insert(0, str(ROOT))
    import homeassistant
    from custom_components.garten_bewaesserung.controller import GartenController
else:
    path = ROOT/'custom_components/garten_bewaesserung'
    tree = ast.parse((path/'controller.py').read_text())
    methods = [n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)
               and n.name in ('_push_feuern', '_sende_push', '_pause_expired')]
    formatter = next(n for n in ast.parse((path/'score.py').read_text()).body
                     if isinstance(n, ast.FunctionDef) and n.name == 'baue_plan_push')
    constants = {}
    exec(compile((path/'const.py').read_text(), 'const.py', 'exec'), constants)
    ns = dict(constants, datetime=datetime, Any=object,
              _LOGGER=logging.getLogger(__name__))
    exec(compile(ast.Module(body=[formatter, *methods], type_ignores=[]),
                 'real_notification_methods', 'exec'), ns)
    GartenController = type('GartenController', (), {m.name: ns[m.name] for m in methods})


class PlanNotifications(unittest.IsolatedAsyncioTestCase):
    def controller(self, active=False, reason='Winterpause'):
        c = object.__new__(GartenController)
        c._gestoppt = False
        c.pause_ready = True
        c.pause = SimpleNamespace(active=active, reason=reason, expire=lambda now: None)
        c._pause_generation = 0
        c._pause_lock = asyncio.Lock()
        c._push_unsub = None
        c._an = lambda key: False
        c._recompute_alle = AsyncMock()
        c._bewaesserungszeit = lambda: time(20, 30)
        c._kreise = lambda: [{'id': 'fake', 'name': 'Synthetic zone'}]
        c._zahl = lambda *args: 5
        c.daten = SimpleNamespace(kreis=lambda kid: SimpleNamespace(score=50), broadcast=Mock())
        c.entry = SimpleNamespace(entry_id='synthetic', options={'notify_dienste': ['notify.test']})
        c._arme_tagestimer = Mock()
        c._store_sichern = AsyncMock()
        c._sende_push = AsyncMock()
        c.hass = SimpleNamespace(services=SimpleNamespace(
            async_call=AsyncMock(), has_service=lambda *args: True))
        return c

    async def test_all_active_pause_reasons_suppress_plan(self):
        for reason in ('Winterpause', 'Urlaub', 'Sonstiges'):
            with self.subTest(reason=reason):
                c = self.controller(True, reason)
                await c._push_feuern(NOW)
                c._sende_push.assert_not_awaited()
                c._recompute_alle.assert_not_awaited()
                c._arme_tagestimer.assert_called_once()

    async def test_inactive_winter_reason_does_not_suppress(self):
        c = self.controller()
        await c._push_feuern(NOW)
        c._sende_push.assert_awaited_once()
        self.assertIn('5 min', c._sende_push.call_args.args[1])

    async def test_skip_today_remains_silent(self):
        c = self.controller()
        c._an = lambda key: key == 'heute_ueberspringen'
        await c._push_feuern(NOW)
        c._sende_push.assert_not_awaited()

    async def test_startup_and_unloaded_controller_remain_silent(self):
        for ready, stopped in ((False, False), (True, True)):
            c = self.controller()
            c.pause_ready, c._gestoppt = ready, stopped
            await c._push_feuern(NOW)
            c._sende_push.assert_not_awaited()

    async def test_pause_during_recompute_even_if_immediately_resumed(self):
        for resumed in (False, True):
            c = self.controller()
            async def pause():
                c._pause_generation += 1
                c.pause.active = not resumed
            c._recompute_alle = AsyncMock(side_effect=pause)
            await c._push_feuern(NOW)
            c._sende_push.assert_not_awaited()

    async def test_stop_during_recompute_remains_silent(self):
        c = self.controller()
        async def stop(): c._gestoppt = True
        c._recompute_alle = AsyncMock(side_effect=stop)
        await c._push_feuern(NOW)
        c._sende_push.assert_not_awaited()

    async def test_normal_next_announcement_after_resume(self):
        c = self.controller(True)
        await c._push_feuern(NOW)
        c.pause.active = False
        await c._push_feuern(NOW)
        c._sende_push.assert_awaited_once()
        self.assertEqual(c._arme_tagestimer.call_count, 2)

    async def test_general_sender_still_delivers_alerts_and_reminders(self):
        method = GartenController._sende_push
        previous = method.__globals__.get('ir')
        method.__globals__['ir'] = SimpleNamespace(async_delete_issue=Mock())
        try:
            for critical in (False, True):
                c = self.controller(True)
                result = await method(c, 'Synthetic safety/reminder', 'test', critical)
                self.assertEqual(result, {'notify.test': 'ok'})
                c.hass.services.async_call.assert_awaited_once()
        finally:
            method.__globals__['ir'] = previous

    async def test_pause_expiry_reminder_survives_active_pause(self):
        c = self.controller(True)
        c.pause.expire = lambda now: 'reminded'
        method = GartenController._pause_expired
        previous = method.__globals__.get('dt_util')
        method.__globals__['dt_util'] = SimpleNamespace(now=lambda: NOW)
        try:
            await c._pause_expired(NOW)
        finally:
            method.__globals__['dt_util'] = previous
        self.assertTrue(c.pause.active)
        c._sende_push.assert_awaited_once()
        self.assertIn('gesperrt', c._sende_push.call_args.args[1])
        self.assertEqual(c.hass.services.async_call.call_args.args[:2],
                         ('persistent_notification', 'create'))


if __name__ == '__main__':
    unittest.main()
