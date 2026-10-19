"""Independent soil-sensor season policy; no HA or device side effects."""
from dataclasses import asdict, dataclass, replace
from datetime import datetime
import math

AUTO = "Automatisch (Winterpause)"
ACTIVE = "Aktiv"
STORED = "Eingelagert"
INHERIT = "Garten übernehmen"
MODES = (AUTO, ACTIVE, STORED)
MAX_AGE_SECONDS = 24 * 3600


@dataclass
class SoilPolicy:
    mode: str = AUTO
    timed: bool = False
    until: str | None = None
    weather_only: bool = False
    invalid: bool = False

    @classmethod
    def restore(cls, value, *, zone=False):
        if value is None:
            return cls(mode=INHERIT if zone else AUTO)
        try:
            p = cls(**value)
            p.validate(zone=zone)
            return p
        except (TypeError, ValueError, OverflowError):
            # Broken persisted configuration is a visible fault, NOT a healthy pause.
            return cls(mode=STORED, invalid=True)

    def validate(self, *, zone=False):
        if self.mode not in (*MODES, *((INHERIT,) if zone else ())):
            raise ValueError("Ungültiger Boden-Sensormodus")
        if any(type(v) is not bool for v in (self.timed, self.weather_only, self.invalid)):
            raise ValueError("Ungültige Sensorpause")
        if self.until is not None:
            end = datetime.fromisoformat(self.until)
            if end.tzinfo is None or end.utcoffset() is None:
                raise ValueError("Sensorpausenende benötigt eine Zeitzone")
        if self.timed and (self.mode != STORED or not self.until):
            raise ValueError("Enddatum gilt nur für eingelagerte Sensoren")

    def changed(self, now, *, zone=False, **values):
        if "mode" in values and values["mode"] != STORED:
            values.update(timed=False, until=None)
        p = replace(self, **values, invalid=False)
        p.validate(zone=zone)
        if p.timed and datetime.fromisoformat(p.until) <= now:
            raise ValueError("Sensorpausenende muss in der Zukunft liegen")
        return p

    def expire(self, now):
        if not self.invalid and self.timed and datetime.fromisoformat(self.until) <= now:
            self.mode, self.timed, self.until = ACTIVE, False, None
            return True
        return False

    def parked(self, winter):
        return self.invalid or self.mode == STORED or (self.mode == AUTO and winter)

    def to_dict(self):
        return asdict(self)


def valid_sample(state, reported, attributes, *, now, after, disabled=False):
    """Fresh HA observation, not proof of radio contact or physical sample time.

    Unchanged newly reported values qualify; last_changed must never be used.
    All initial/restored values require a later report after startup/resume.
    """
    try:
        value = float(state)
        age = (now - reported).total_seconds()
        if (disabled or attributes.get("restored") or not math.isfinite(value)
                or not 0 <= value <= 100 or not 0 <= age <= MAX_AGE_SECONDS
                or reported <= after):
            return None
        return value
    except (TypeError, ValueError, OverflowError, AttributeError):
        return None
