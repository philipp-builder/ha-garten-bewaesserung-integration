"""Pause reason and expiry behavior; controller Store is authoritative."""
from homeassistant.components.select import SelectEntity
from .const import DOMAIN
from .entity import GartenEntity
from .pause import REASONS, ACTIONS


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]["daten"]
    async_add_entities([
        PauseSelect(entry, data, "pause_grund", "Pausengrund", "reason", REASONS),
        PauseSelect(entry, data, "pause_ablauf", "Nach Pausenende", "action", ACTIONS),
    ])


class PauseSelect(GartenEntity, SelectEntity):
    def __init__(self, entry, data, key, name, field, options):
        super().__init__(entry, data, key)
        self._attr_name = name
        self._attr_options = list(options)
        self.field = field

    @property
    def current_option(self):
        return getattr(self.hass.data[DOMAIN][self._entry.entry_id]["controller"].pause, self.field)

    async def async_select_option(self, option):
        await self.hass.data[DOMAIN][self._entry.entry_id]["controller"].pause_aendern(**{self.field: option})
