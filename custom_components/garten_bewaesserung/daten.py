"""Laufzeit-Container: verbindet Engine (Controller) und Entities.

Die Engine schreibt Ergebnisse (Score, Status, Zeitstempel, Zähler) hierher
und feuert das Dispatcher-Signal; die Sensor-Entities lauschen darauf.
Einstell-Entities (number/switch/time) halten ihren Zustand selbst
(RestoreEntity) — die Engine liest sie über den HA-State (bewusst dieselbe
Blickrichtung wie die Blueprint-Edition: eine Wahrheit, der State-Machine).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN


def signal(entry_id: str) -> str:
    """Dispatcher-Signal für Laufzeit-Updates dieses Hubs."""
    return f"{DOMAIN}_{entry_id}_update"


@dataclass
class KreisLaufzeit:
    """Von der Engine berechnete Werte eines Kreises."""

    score: int | None = None
    status: str | None = None
    boden: float | None = None  # Min über die Kreis-Sensoren (Engine-Sicht)
    dauer_heute: int | None = None  # von Engine geschrieben; number zeigt/überschreibt
    zuletzt_bewaessert: datetime | None = None
    dosen_heute: int = 0
    liter_heute: float | None = None
    liter_monat: float | None = None
    liter_gesamt: float | None = None  # kumulativ, nie zurückgesetzt (Energy-Dashboard)
    letzte_sitzung_liter: float | None = None
    faktoren: dict[str, Any] = field(default_factory=dict)  # Score-Anatomie fürs Attribut


@dataclass
class HubLaufzeit:
    """Hub-weite Engine-Werte."""

    naechster_lauf: datetime | None = None
    letzter_lauf_bericht: str | None = None
    lauf_aktiv: bool = False
    lauf_start: datetime | None = None  # Beginn des aktiven Laufs (Kalender)
    plan_heute: str | None = None  # kompakte Tageszeile (Wetter · Böden · Zeit)
    plan_details: dict[str, Any] = field(default_factory=dict)  # Rohwerte als Attribute
    # Abgeschlossene Läufe für den Kalender: {start, ende, titel, beschreibung}
    lauf_historie: list[dict[str, str]] = field(default_factory=list)


class GartenDaten:
    """Pro Config-Entry: Laufzeitwerte + Update-Broadcast."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._hass = hass
        self._entry_id = entry_id
        self.hub = HubLaufzeit()
        self.kreise: dict[str, KreisLaufzeit] = {}

    def kreis(self, kreis_id: str) -> KreisLaufzeit:
        return self.kreise.setdefault(kreis_id, KreisLaufzeit())

    def broadcast(self) -> None:
        """Alle lauschenden Entities neu zeichnen."""
        async_dispatcher_send(self._hass, signal(self._entry_id))
