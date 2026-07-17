"""Bewässerungs-Startzeit als time-Entity.

Persistenz wie bei den Konfig-Numbers (Review-Finding F3): entry.options
ist die einzige Wahrheit — die Entity liest CONF_ZEIT und schreibt
Änderungen zurück. Kein RestoreEntity, das würde Options-Dialog-Edits
nach dem Reload mit dem alten Zustand überschreiben.
"""
from __future__ import annotations

from datetime import time as time_t

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ZEIT, DEFAULT_ZEIT, DOMAIN
from .entity import GartenEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    daten = hass.data[DOMAIN][entry.entry_id]["daten"]
    async_add_entities([BewaesserungszeitEntity(entry, daten)])


class BewaesserungszeitEntity(GartenEntity, TimeEntity):
    _attr_name = "Bewässerungszeit"
    _attr_icon = "mdi:clock-start"

    def __init__(self, entry, daten) -> None:
        super().__init__(entry, daten, "bewaesserungszeit", None)
        try:
            self._attr_native_value = time_t.fromisoformat(
                entry.options.get(CONF_ZEIT, DEFAULT_ZEIT)
            )
        except ValueError:
            self._attr_native_value = time_t.fromisoformat(DEFAULT_ZEIT)

    async def async_set_value(self, value: time_t) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
        neu = dict(self._entry.options)
        neu[CONF_ZEIT] = value.isoformat()
        self.hass.config_entries.async_update_entry(self._entry, options=neu)
