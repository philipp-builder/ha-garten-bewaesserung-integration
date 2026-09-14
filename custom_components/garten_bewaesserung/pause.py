"""HA-independent, persisted pause policy. All instants are timezone-aware."""
from dataclasses import dataclass, asdict, replace
from datetime import datetime

REASONS = ("Urlaub", "Winterpause", "Sonstiges")
ACTIONS = ("Automatisch fortsetzen", "Nur erinnern")


@dataclass
class Pause:
    active: bool = False
    reason: str = "Urlaub"
    until: str | None = None
    timed: bool = False
    action: str = "Automatisch fortsetzen"
    reminded: bool = False

    def to_dict(self):
        return asdict(self)

    @classmethod
    def restore(cls, data, legacy=False):
        if data is None:
            return cls(active=legacy)
        try:
            result = cls(**data)
            result.validate()
            return result
        except (TypeError, ValueError):
            # Corrupt persisted policy must never release watering.
            return cls(active=True, reason="Sonstiges", action="Nur erinnern")

    def validate(self):
        if self.reason not in REASONS or self.action not in ACTIONS:
            raise ValueError("Ungültige Pauseneinstellung")
        if any(type(v) is not bool for v in (self.active, self.timed, self.reminded)):
            raise ValueError("Ungültiger Pausenzustand")
        if self.until is not None:
            end = datetime.fromisoformat(self.until)
            if end.tzinfo is None or end.utcoffset() is None:
                raise ValueError("Pausenende benötigt eine Zeitzone")
        if self.timed and self.until is None:
            raise ValueError("Bitte zuerst ein Pausenende setzen")

    def changed(self, now, **values):
        if "reason" in values and values["reason"] != self.reason and "action" not in values:
            values["action"] = "Nur erinnern" if values["reason"] == "Winterpause" else "Automatisch fortsetzen"
        result = replace(self, **values, reminded=False)
        if values.get("active") is False:
            result.timed = False
            result.until = None
        result.validate()
        if result.active and result.timed and datetime.fromisoformat(result.until) <= now:
            raise ValueError("Pausenende muss in der Zukunft liegen")
        return result

    def expire(self, now):
        if not self.active or not self.timed or self.reminded or datetime.fromisoformat(self.until) > now:
            return None
        self.reminded = True
        if self.action == "Automatisch fortsetzen":
            self.active = False
            self.timed = False
            return "resumed"
        return "reminder"

    def label(self):
        if not self.active:
            return "Nicht pausiert"
        if self.reminded:
            return f"{self.reason}: manuelle Freigabe erforderlich"
        return f"{self.reason} bis {self.until}" if self.timed else f"{self.reason}: bis auf Widerruf"
