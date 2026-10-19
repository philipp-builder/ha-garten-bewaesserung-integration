"""Timezone-aware optional pause deadline."""
from datetime import datetime
from homeassistant.components.datetime import DateTimeEntity
from .const import DOMAIN
from .entity import GartenEntity
from .soil_entity import SoilEntity, soil_scopes


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PauseEnd(entry, hass.data[DOMAIN][entry.entry_id]["daten"], "pause_ende")])
    async_add_entities([SoilEnd(entry, hass.data[DOMAIN][entry.entry_id]["daten"],
                               "boden_sensorpause_ende", k) for k in soil_scopes(entry)])


class SoilEnd(SoilEntity, DateTimeEntity):
    _attr_name = "Bodensensor-Pausenende"

    @property
    def native_value(self):
        return datetime.fromisoformat(self.policy.until) if self.policy.until else None

    async def async_set_value(self, value):
        await self.change(until=value.isoformat())


class PauseEnd(GartenEntity, DateTimeEntity):
    _attr_name = "Pausenende"

    @property
    def native_value(self):
        value = self.hass.data[DOMAIN][self._entry.entry_id]["controller"].pause.until
        return datetime.fromisoformat(value) if value else None

    async def async_set_value(self, value):
        await self.hass.data[DOMAIN][self._entry.entry_id]["controller"].pause_aendern(until=value.isoformat())
