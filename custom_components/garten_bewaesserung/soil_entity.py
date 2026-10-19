"""Stable native HA controls, garden defaults with explicit zone overrides."""
from .const import CONF_BODENSENSOREN, CONF_KREISE, DOMAIN
from .entity import GartenEntity


def soil_scopes(entry):
    return [None, *[k for k in entry.options.get(CONF_KREISE, []) if k.get(CONF_BODENSENSOREN)]]


class SoilEntity(GartenEntity):
    @property
    def controller(self):
        return self.hass.data[DOMAIN][self._entry.entry_id]["controller"]

    @property
    def soil_kid(self):
        return self._kreis["id"] if self._kreis else None

    @property
    def policy(self):
        return self.controller.soil_policy(self.soil_kid)

    @property
    def available(self):
        return self.controller.pause_ready

    async def change(self, **values):
        await self.controller.soil_change(self.soil_kid, **values)
