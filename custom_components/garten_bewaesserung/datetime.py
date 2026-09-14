"""Timezone-aware optional pause deadline."""
from datetime import datetime
from homeassistant.components.datetime import DateTimeEntity
from .const import DOMAIN
from .entity import GartenEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PauseEnd(entry, hass.data[DOMAIN][entry.entry_id]["daten"], "pause_ende")])


class PauseEnd(GartenEntity, DateTimeEntity):
    _attr_name = "Pausenende"

    @property
    def native_value(self):
        value = self.hass.data[DOMAIN][self._entry.entry_id]["controller"].pause.until
        return datetime.fromisoformat(value) if value else None

    async def async_set_value(self, value):
        await self.hass.data[DOMAIN][self._entry.entry_id]["controller"].pause_aendern(until=value.isoformat())
