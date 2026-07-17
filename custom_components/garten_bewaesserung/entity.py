"""Gemeinsame Entity-Basis: Device-Zuordnung (Hub + ein Device pro Kreis)."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import CONF_KREIS_ID, CONF_KREIS_NAME, DOMAIN
from .daten import GartenDaten, signal


# Device-Namen sind bewusst kurz: bei has_entity_name leitet HA die
# object_id aus "<Device> <Entity>" ab — "Garten" + "Score" ergibt so
# vorhersagbare IDs wie sensor.garten_rasen_score.
def hub_device(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Garten",
        manufacturer="philipp-builder",
        model="Garten-Bewässerung (Score-Engine)",
    )


def kreis_device(entry: ConfigEntry, kreis: dict[str, Any]) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{kreis[CONF_KREIS_ID]}")},
        name=f"Garten {kreis[CONF_KREIS_NAME]}",
        manufacturer="philipp-builder",
        model={"rasen": "Rasen/Beet-Kreis", "topf": "Topf/Tropf-Kreis"}.get(
            kreis.get("typ", "rasen"), "Kreis"
        ),
        via_device=(DOMAIN, entry.entry_id),
    )


class GartenEntity(Entity):
    """Basis: unique_id-Schema, Objekt-ID-Vorschlag, optionales Live-Update."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: ConfigEntry,
        daten: GartenDaten,
        schluessel: str,
        kreis: dict[str, Any] | None = None,
    ) -> None:
        self._entry = entry
        self._daten = daten
        self._kreis = kreis
        # Namen vorerst direkt (deutsch); Umstellung auf translation_keys
        # kommt gesammelt mit dem Übersetzungs-Task (#70).
        if kreis is None:
            self._attr_unique_id = f"{entry.entry_id}_{schluessel}"
            self._attr_device_info = hub_device(entry)
        else:
            kid = kreis[CONF_KREIS_ID]
            self._attr_unique_id = f"{entry.entry_id}_{kid}_{schluessel}"
            self._attr_device_info = kreis_device(entry, kreis)

    @property
    def kreis_laufzeit(self):
        assert self._kreis is not None
        return self._daten.kreis(self._kreis[CONF_KREIS_ID])

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, signal(self._entry.entry_id), self._laufzeit_update
            )
        )

    @callback
    def _laufzeit_update(self) -> None:
        # @callback ist Pflicht: ohne Markierung ruft der Dispatcher die
        # Methode im Executor-Thread auf und async_write_ha_state schlägt fehl.
        self.async_write_ha_state()
