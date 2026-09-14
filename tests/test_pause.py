"""Policy tests without HA/packages: migration, expiry, timezones and safety."""
import importlib.util
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location('pause', Path(__file__).parents[1] / 'custom_components/garten_bewaesserung/pause.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
Pause = module.Pause
NOW = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)


class PauseTests(unittest.TestCase):
    def test_legacy_on_is_indefinite(self):
        p = Pause.restore(None, True)
        self.assertTrue(p.active)
        self.assertFalse(p.timed)
        self.assertIsNone(p.expire(NOW + timedelta(days=300)))

    def test_legacy_off_stays_off(self):
        self.assertFalse(Pause.restore(None).active)

    def test_winter_defaults_to_reminder(self):
        p = Pause().changed(NOW, reason='Winterpause', active=True)
        self.assertEqual(p.action, 'Nur erinnern')

    def test_explicit_winter_auto_allowed(self):
        p = Pause().changed(NOW, reason='Winterpause', action='Automatisch fortsetzen')
        self.assertEqual(p.action, 'Automatisch fortsetzen')

    def timed(self, action='Automatisch fortsetzen'):
        return Pause().changed(NOW, active=True, timed=True,
            until=(NOW + timedelta(hours=1)).isoformat(), action=action)

    def test_expiry_once_and_persisted(self):
        p = self.timed()
        self.assertIsNone(p.expire(NOW))
        self.assertEqual(p.expire(NOW + timedelta(hours=1)), 'resumed')
        self.assertFalse(p.active)
        restored = Pause.restore(p.to_dict())
        self.assertIsNone(restored.expire(NOW + timedelta(days=1)))

    def test_offline_expiry(self):
        p = Pause.restore(self.timed().to_dict())
        self.assertEqual(p.expire(NOW + timedelta(days=1)), 'resumed')

    def test_reminder_does_not_release(self):
        p = self.timed('Nur erinnern')
        self.assertEqual(p.expire(NOW + timedelta(days=1)), 'reminder')
        self.assertTrue(p.active)
        self.assertIsNone(Pause.restore(p.to_dict()).expire(NOW + timedelta(days=2)))

    def test_corruption_fails_closed(self):
        for data in ({'timed': True}, {'reason': 'bad'}, {'active': 'false'}, {'until': 'invalid'}):
            self.assertTrue(Pause.restore(data).active)

    def test_reject_past_and_naive(self):
        for end in (NOW.isoformat(), NOW.replace(tzinfo=None).isoformat()):
            with self.assertRaises(ValueError):
                Pause().changed(NOW, active=True, timed=True, until=end)

    def test_timezone_instant_dst(self):
        p = Pause().changed(NOW, active=True, timed=True, until='2026-10-25T02:30:00+01:00')
        self.assertIsNone(p.expire(datetime(2026,10,25,0,30,tzinfo=timezone.utc)))
        self.assertEqual(p.expire(datetime(2026,10,25,1,30,tzinfo=timezone.utc)), 'resumed')

    def test_disable_clears_stale_deadline(self):
        p = self.timed().changed(NOW, active=False)
        self.assertIsNone(p.until)
        self.assertFalse(p.timed)

    def test_timed_requires_date(self):
        with self.assertRaises(ValueError):
            Pause().changed(NOW, timed=True)


if __name__ == '__main__':
    unittest.main()
