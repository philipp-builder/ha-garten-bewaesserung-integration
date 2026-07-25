"""Bewässerungskalender: geplante + vergangene Läufe als native Termine.

Die HA-Kalender-Karte zeigt damit Plan und Historie im Wochen-/Monats-
raster — ohne eigene Frontend-Karte. Vergangene Läufe kommen aus der
Store-persistierten Lauf-Historie (Controller, B3-Abschluss); der geplante
Termin wird live aus „Nächster Lauf“ + den heutigen Kreis-Dauern gebaut.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BLOCK_MAX,
    CONF_BLOCK_PAUSE,
    CONF_KREIS_ID,
    CONF_KREIS_NAME,
    CONF_KREISE,
    CONF_VENTILE,
    DEFAULT_BLOCK_PAUSE,
    DOMAIN,
)
from .entity import GartenEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    daten = hass.data[DOMAIN][entry.entry_id]["daten"]
    async_add_entities([GartenKalender(entry, daten, "kalender")])


def _wandzeit(kreis: dict, dauer_min: int) -> float:
    """Tatsächliche Laufzeit inkl. Versickerungspausen und Ventil-Slots.

    Gießzeit ist nicht Wandzeit: Bei Intervall-Bewässerung kommen (n−1)
    Pausen dazu, und mehrere Ventile eines Kreises laufen nacheinander.
    """
    if dauer_min <= 0:
        return 0.0
    try:
        block_max = float(kreis.get(CONF_BLOCK_MAX) or 0)
        pause = float(kreis.get(CONF_BLOCK_PAUSE) or DEFAULT_BLOCK_PAUSE)
    except (TypeError, ValueError):
        return float(dauer_min)
    ventile = max(len(kreis.get(CONF_VENTILE) or []), 1)
    bloecke = 1
    if block_max > 0 and dauer_min > block_max:
        bloecke = math.ceil(dauer_min / block_max)
    return ventile * (dauer_min + (bloecke - 1) * pause)


class GartenKalender(GartenEntity, CalendarEntity):
    _attr_name = "Kalender"

    # ------------------------------------------------------------ Bausteine

    def _kreis_dauern(self) -> list[tuple[str, int, float]]:
        """(Name, Gießminuten, Wandzeit) je Kreis — aus den dauer_heute-Numbers,
        derselben Wahrheit, aus der auch der Executor seinen Snapshot zieht
        (Nutzer-Overrides sind damit im Kalender-Termin sichtbar).

        Die Wandzeit enthält zusätzlich die Versickerungspausen der
        Intervall-Bewässerung und die Slots mehrerer Ventile — sonst endete
        der Kalendertermin lange vor dem tatsächlichen Lauf.
        """
        reg = er.async_get(self.hass)
        aus: list[tuple[str, int, float]] = []
        for kreis in self._entry.options.get(CONF_KREISE, []):
            kid = kreis[CONF_KREIS_ID]
            eid = reg.async_get_entity_id(
                "number", DOMAIN, f"{self._entry.entry_id}_{kid}_dauer_heute"
            )
            dauer = 0
            if eid and (zustand := self.hass.states.get(eid)):
                try:
                    dauer = int(float(zustand.state))
                except (TypeError, ValueError):
                    pass
            aus.append(
                (kreis.get(CONF_KREIS_NAME, kid), dauer, _wandzeit(kreis, dauer))
            )
        return aus

    def _geplantes_event(self) -> CalendarEvent | None:
        """Nächster Lauf als Termin — Dauer = Summe der heutigen Kreis-
        Dauern (Sequenz-Näherung; parallel laufende Kreise machen den
        Termin höchstens etwas zu lang). Nichts geplant ⇒ kein Termin."""
        start = self._daten.hub.naechster_lauf
        if start is None:
            return None
        dauern = self._kreis_dauern()
        gesamt = sum(d for _n, d, _w in dauern)
        wand = sum(w for _n, _d, w in dauern)
        if gesamt <= 0:
            return None
        zeilen = [f"{name} {d} min" for name, d, _w in dauern if d > 0]
        if wand > gesamt:  # Intervall-Bewässerung: Pausen sichtbar machen
            zeilen.append(f"(inkl. Versickerungspausen, gesamt {wand:.0f} min)")
        return CalendarEvent(
            start=start,
            end=start + timedelta(minutes=max(wand, 5)),
            summary="Bewässerung geplant",
            description=" · ".join(zeilen),
        )

    def _laufendes_event(self) -> CalendarEvent | None:
        start = self._daten.hub.lauf_start
        if not self._daten.hub.lauf_aktiv or start is None:
            return None
        wand = sum(w for _n, _d, w in self._kreis_dauern())
        return CalendarEvent(
            start=start,
            end=start + timedelta(minutes=max(wand, 5)),
            summary="Bewässerung läuft",
        )

    def _historien_events(self) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        for eintrag in self._daten.hub.lauf_historie:
            start = dt_util.parse_datetime(eintrag.get("start") or "")
            ende = dt_util.parse_datetime(eintrag.get("ende") or "")
            if start is None or ende is None or ende <= start:
                continue
            events.append(
                CalendarEvent(
                    start=start,
                    end=ende,
                    summary=eintrag.get("titel") or "Bewässerung",
                    description=eintrag.get("beschreibung") or "",
                )
            )
        return events

    # ---------------------------------------------------- CalendarEntity-API

    @property
    def event(self) -> CalendarEvent | None:
        """Aktueller bzw. nächster Termin (bestimmt auch den on/off-State)."""
        return self._laufendes_event() or self._geplantes_event()

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        events = self._historien_events()
        if laufend := self._laufendes_event():
            events.append(laufend)
        if geplant := self._geplantes_event():
            events.append(geplant)
        return [
            e for e in events if e.end > start_date and e.start < end_date
        ]
