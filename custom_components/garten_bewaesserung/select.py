"""Pause reason and expiry behavior; controller Store is authoritative."""
from homeassistant.components.select import SelectEntity
from .const import DOMAIN
from .entity import GartenEntity
from .pause import REASONS, ACTIONS
from .soil import MODES, INHERIT
from .soil_entity import SoilEntity, soil_scopes


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]["daten"]
    async_add_entities([
        PauseSelect(entry, data, "pause_grund", "Pausengrund", "reason", REASONS),
        PauseSelect(entry, data, "pause_ablauf", "Nach Pausenende", "action", ACTIONS),
    ])
    async_add_entities([SoilMode(entry, data, "boden_sensorbetrieb", k) for k in soil_scopes(entry)])
    async_add_entities([SoilFallback(entry, data, "boden_ohne_messwert", k)
                        for k in soil_scopes(entry) if k and k.get("typ") != "topf"])


class SoilMode(SoilEntity, SelectEntity):
    _attr_name = "Bodensensor-Betrieb"
    _attr_icon = "mdi:sprout"

    @property
    def options(self):
        return [INHERIT, *MODES] if self.soil_kid else list(MODES)

    @property
    def current_option(self):
        return self.policy.mode

    async def async_select_option(self, option):
        await self.change(mode=option)


class SoilFallback(SoilEntity, SelectEntity):
    _attr_name = "Bewässerung ohne Bodenmesswert"
    _attr_options = ["Sperren", "Nur Wetter (Rasen)"]
    _attr_icon = "mdi:weather-partly-cloudy"

    @property
    def current_option(self):
        return self._attr_options[int(self.policy.weather_only)]

    async def async_select_option(self, option):
        if option not in self._attr_options:
            raise ValueError("Ungültiger Ersatzbetrieb")
        await self.change(weather_only=option == self._attr_options[1])


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
