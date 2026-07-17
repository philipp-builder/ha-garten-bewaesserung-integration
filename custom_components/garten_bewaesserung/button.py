"""Buttons: Not-Aus, Sofort-Start, Plan neu berechnen — rufen den Controller."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import GartenEntity

_LOGGER = logging.getLogger(__name__)

BUTTONS = [
    # (schluessel, name, icon, controller_methode)
    ("not_aus", "Not-Aus", "mdi:water-off", "not_aus"),
    ("sofort_start", "Sofort-Start", "mdi:play-circle-outline", "sofort_start"),
    ("plan_neu", "Plan neu berechnen", "mdi:refresh", "plan_neu"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    daten = hass.data[DOMAIN][entry.entry_id]["daten"]
    async_add_entities(
        GartenButton(entry, daten, s, name, icon, methode)
        for s, name, icon, methode in BUTTONS
    )


class GartenButton(GartenEntity, ButtonEntity):
    def __init__(self, entry, daten, schluessel, name, icon, methode) -> None:
        super().__init__(entry, daten, schluessel, None)
        self._attr_name = name
        self._attr_icon = icon
        self._methode = methode

    async def async_press(self) -> None:
        controller = self.hass.data[DOMAIN][self._entry.entry_id].get("controller")
        if controller is None:
            _LOGGER.warning(
                "Garten-Bewässerung: Engine noch nicht aktiv — '%s' hat keine Wirkung "
                "(kommt mit dem Engine-Update).",
                self._methode,
            )
            return
        await getattr(controller, self._methode)()
