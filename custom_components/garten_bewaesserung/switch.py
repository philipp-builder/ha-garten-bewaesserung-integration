"""Schalter: globale Modi + Kreis-aktiv. Zustand überlebt Neustarts."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_KREISE, DOMAIN
from .entity import GartenEntity

HUB_SWITCHES = [
    # (schluessel, name, default_an, icon)
    ("heute_ueberspringen", "Heute überspringen", False, "mdi:skip-next-circle-outline"),
    # Stable unique_id/entity_id keeps existing automations working.
    ("urlaubsmodus", "Bewässerung pausieren", False, "mdi:pause-circle"),
    ("pause_befristet", "Pause mit Enddatum", False, "mdi:calendar-end"),
    ("aggressiv_modus", "Boost-Modus", False, "mdi:fire"),
    ("topf_steuerung", "Topf-Frequenzbewässerung", True, "mdi:flower-outline"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    daten = hass.data[DOMAIN][entry.entry_id]["daten"]
    entities = [
        GartenSwitch(entry, daten, s, name, default, icon, None)
        for s, name, default, icon in HUB_SWITCHES
    ]
    entities += [
        GartenSwitch(entry, daten, "aktiv", "Aktiv", True, "mdi:sprinkler-variant", kreis)
        for kreis in entry.options.get(CONF_KREISE, [])
    ]
    async_add_entities(entities)


class GartenSwitch(GartenEntity, SwitchEntity, RestoreEntity):
    def __init__(self, entry, daten, schluessel, name, default_an, icon, kreis) -> None:
        super().__init__(entry, daten, schluessel, kreis)
        self._attr_name = name
        self._attr_icon = icon
        self._attr_is_on = default_an
        self._schluessel = schluessel

    @property
    def is_on(self):
        c = self.hass.data[DOMAIN][self._entry.entry_id]["controller"]
        if c.pause_ready and self._schluessel in ("urlaubsmodus", "pause_befristet"):
            return c.pause.active if self._schluessel == "urlaubsmodus" else c.pause.timed
        return self._attr_is_on

    @property
    def extra_state_attributes(self):
        if self._schluessel == "urlaubsmodus":
            c = self.hass.data[DOMAIN][self._entry.entry_id]["controller"]
            return {**c.pause.to_dict(), "status": c.pause.label()}
        return None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (alt := await self.async_get_last_state()) and alt.state in ("on", "off"):
            self._attr_is_on = alt.state == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        if self._schluessel in ("urlaubsmodus", "pause_befristet"):
            c = self.hass.data[DOMAIN][self._entry.entry_id]["controller"]
            await c.pause_aendern(**{"active" if self._schluessel == "urlaubsmodus" else "timed": True})
            return
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if self._schluessel in ("urlaubsmodus", "pause_befristet"):
            c = self.hass.data[DOMAIN][self._entry.entry_id]["controller"]
            await c.pause_aendern(**{"active" if self._schluessel == "urlaubsmodus" else "timed": False})
            return
        self._attr_is_on = False
        self.async_write_ha_state()
