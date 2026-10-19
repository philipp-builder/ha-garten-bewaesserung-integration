"""Pure season/persistence/freshness policy regressions; stdlib only."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components/garten_bewaesserung"))
from soil import ACTIVE, AUTO, INHERIT, STORED, SoilPolicy, valid_sample

NOW = datetime(2026, 10, 19, 8, tzinfo=timezone.utc)


class PolicyTests(unittest.TestCase):
    def test_migration_defaults_and_inheritance(self):
        self.assertEqual(SoilPolicy.restore(None).mode, AUTO)
        self.assertEqual(SoilPolicy.restore(None, zone=True).mode, INHERIT)

    def test_modes_only_automatic_follows_active_winter(self):
        for mode in (AUTO, ACTIVE, STORED):
            for winter in (True, False):
                self.assertEqual(SoilPolicy(mode=mode).parked(winter),
                                 mode == STORED or (mode == AUTO and winter))

    def test_roundtrip_and_expiry_once(self):
        p = SoilPolicy(mode=STORED).changed(NOW, until=(NOW+timedelta(days=1)).isoformat(), timed=True)
        p = SoilPolicy.restore(p.to_dict())
        self.assertFalse(p.expire(NOW))
        self.assertTrue(p.expire(NOW+timedelta(days=2)))
        self.assertEqual(p.mode, ACTIVE)
        self.assertFalse(p.expire(NOW+timedelta(days=3)))

    def test_invalid_storage_is_visible_fail_closed(self):
        for data in ({"mode": "bad"}, {"timed": "false"}, {"until": "bad"},
                     {"until": "2027-01-01T00:00:00"}, [], "oops", {"extra": True},
                     {"mode": INHERIT}, {"weather_only": 1}, {"timed": True}):
            p = SoilPolicy.restore(data)
            self.assertTrue(p.invalid, data)
            self.assertTrue(p.parked(False))
            self.assertTrue(SoilPolicy.restore(p.to_dict()).invalid)

    def test_dates_validate_and_disabling_does_not_change_mode(self):
        for values in ({"timed": True}, {"until": "no"},
                       {"mode": STORED, "timed": True, "until": NOW.isoformat()}):
            with self.assertRaises(ValueError):
                SoilPolicy().changed(NOW, **values)
        p = SoilPolicy(mode=STORED).changed(NOW, timed=False)
        self.assertEqual(p.mode, STORED)

    def test_expiry_across_dst_is_absolute_and_does_not_activate_watering(self):
        end = datetime(2026, 10, 25, 2, 30, tzinfo=ZoneInfo("Europe/Zurich"), fold=1)
        p = SoilPolicy(mode=STORED, timed=True, until=end.isoformat())
        self.assertFalse(p.expire(datetime(2026, 10, 25, 0, 45, tzinfo=timezone.utc)))
        self.assertTrue(p.expire(datetime(2026, 10, 25, 1, 31, tzinfo=timezone.utc)))

    def sample(self, value="5", reported=NOW, attrs=None, **kwargs):
        return valid_sample(value, reported, attrs or {}, now=NOW,
                            after=NOW-timedelta(seconds=1), **kwargs)

    def test_valid_range_and_same_value_new_report(self):
        for v in (0, 5, 100, "50.2"):
            self.assertEqual(self.sample(v), float(v))
        self.assertIsNone(self.sample(reported=NOW-timedelta(seconds=1)))
        self.assertEqual(self.sample(), 5)

    def test_reject_invalid_future_stale_disabled_and_restored(self):
        for value in (None, "unknown", "unavailable", "nan", "inf", -1, 101):
            self.assertIsNone(self.sample(value))
        for stamp in (None, NOW+timedelta(seconds=1), NOW-timedelta(days=2), NOW.replace(tzinfo=None)):
            self.assertIsNone(self.sample(reported=stamp))
        self.assertIsNone(self.sample(disabled=True))
        self.assertIsNone(self.sample(attrs={"restored": True}))

    def test_explicit_weather_fallback_persists_but_defaults_safe(self):
        self.assertFalse(SoilPolicy().weather_only)
        self.assertTrue(SoilPolicy.restore(SoilPolicy(weather_only=True).to_dict()).weather_only)


if __name__ == "__main__":
    unittest.main()
