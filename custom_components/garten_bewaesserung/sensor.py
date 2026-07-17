"""Sensoren: Score, Status, Zeitstempel, Dosen, Liter — Engine-gespeist."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_FLOW_SENSOR,
    CONF_KREIS_TYP,
    CONF_KREISE,
    CONF_TARIF,
    CONF_WAEHRUNG,
    DEFAULT_TARIF,
    DEFAULT_WAEHRUNG,
    DOMAIN,
)
from .entity import GartenEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    daten = hass.data[DOMAIN][entry.entry_id]["daten"]
    entities: list[SensorEntity] = [
        NaechsterLaufSensor(entry, daten, "naechster_lauf"),
        BerichtSensor(entry, daten, "letzter_lauf_bericht"),
    ]
    for kreis in entry.options.get(CONF_KREISE, []):
        entities += [
            ScoreSensor(entry, daten, "score", kreis),
            StatusSensor(entry, daten, "status", kreis),
            ZuletztSensor(entry, daten, "zuletzt_bewaessert", kreis),
        ]
        if kreis.get(CONF_KREIS_TYP) == "topf":
            entities.append(DosenSensor(entry, daten, "dosen_heute", kreis))
        if kreis.get(CONF_FLOW_SENSOR):
            entities += [
                LiterHeuteSensor(entry, daten, "liter_heute", kreis),
                LiterMonatSensor(entry, daten, "liter_monat", kreis),
                KostenMonatSensor(entry, daten, "kosten_monat", kreis),
            ]
    async_add_entities(entities)


class ScoreSensor(GartenEntity, SensorEntity):
    _attr_name = "Score"
    _attr_native_unit_of_measurement = None
    _attr_icon = "mdi:percent-circle-outline"

    @property
    def native_value(self) -> int | None:
        return self.kreis_laufzeit.score

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self.kreis_laufzeit.faktoren)


class StatusSensor(GartenEntity, SensorEntity):
    _attr_name = "Status"
    _attr_icon = "mdi:text-long"

    @property
    def native_value(self) -> str | None:
        s = self.kreis_laufzeit.status
        return s[:255] if s else None


class ZuletztSensor(GartenEntity, RestoreSensor):
    _attr_name = "Zuletzt bewässert"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self.kreis_laufzeit.zuletzt_bewaessert is None:
            if (alt := await self.async_get_last_state()) and alt.state not in (
                "unknown",
                "unavailable",
            ):
                self.kreis_laufzeit.zuletzt_bewaessert = dt_util.parse_datetime(alt.state)

    @property
    def native_value(self):
        return self.kreis_laufzeit.zuletzt_bewaessert


class DosenSensor(GartenEntity, SensorEntity):
    _attr_name = "Dosen heute"
    _attr_icon = "mdi:water-plus-outline"

    @property
    def native_value(self) -> int:
        return self.kreis_laufzeit.dosen_heute


class NaechsterLaufSensor(GartenEntity, SensorEntity):
    _attr_name = "Nächster Lauf"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        return self._daten.hub.naechster_lauf


class BerichtSensor(GartenEntity, SensorEntity):
    _attr_name = "Letzter Lauf"
    _attr_icon = "mdi:clipboard-text-clock"

    @property
    def native_value(self) -> str | None:
        b = self._daten.hub.letzter_lauf_bericht
        return b[:255] if b else None


class LiterHeuteSensor(GartenEntity, SensorEntity):
    _attr_name = "Liter heute"
    _attr_native_unit_of_measurement = "L"
    _attr_icon = "mdi:water"

    @property
    def native_value(self) -> float | None:
        return self.kreis_laufzeit.liter_heute

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"letzte_sitzung_liter": self.kreis_laufzeit.letzte_sitzung_liter}


class LiterMonatSensor(GartenEntity, SensorEntity):
    _attr_name = "Liter Monat"
    _attr_native_unit_of_measurement = "L"
    _attr_icon = "mdi:water-plus"

    @property
    def native_value(self) -> float | None:
        return self.kreis_laufzeit.liter_monat


class KostenMonatSensor(GartenEntity, SensorEntity):
    """Monatskosten = Liter Monat / 1000 × Wassertarif (Number-Entity —
    Tarif-Änderungen wirken ab der nächsten Aktualisierung)."""

    _attr_name = "Kosten Monat"
    _attr_icon = "mdi:cash"

    @property
    def native_unit_of_measurement(self) -> str:
        return self._entry.options.get(CONF_WAEHRUNG, DEFAULT_WAEHRUNG)

    @property
    def native_value(self) -> float | None:
        liter = self.kreis_laufzeit.liter_monat
        if liter is None:
            return None
        tarif = DEFAULT_TARIF
        eid = er.async_get(self.hass).async_get_entity_id(
            "number", DOMAIN, f"{self._entry.entry_id}_{CONF_TARIF}"
        )
        if eid and (zustand := self.hass.states.get(eid)):
            try:
                tarif = float(zustand.state)
            except (TypeError, ValueError):
                pass
        return round(liter / 1000 * tarif, 2)
