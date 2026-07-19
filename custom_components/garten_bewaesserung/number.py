"""Einstell-Numbers: Tagesdauer (Engine schreibt, Nutzer darf überschreiben)
und Tuning-Regler (Kreis + global).

Persistenz-Modell (Review-Finding F3): Für KONFIG-Regler sind die
entry.options die einzige Wahrheit — die Entity liest daraus und schreibt
Änderungen dorthin zurück (ohne Reload; es gibt keine update_listener).
RestoreEntity wäre hier falsch: es überschriebe frisch gespeicherte
Options-Dialog-Werte nach dem Reload mit dem alten Zustand.
Nur die Engine-geschriebene Tagesdauer nutzt RestoreNumber.
"""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_K_FAKTOR,
    CONF_KREIS_ID,
    CONF_KREIS_TYP,
    CONF_KREISE,
    CONF_MAX_DAUER,
    CONF_MIN_DAUER,
    CONF_REGEN_BEOBACHTET,
    CONF_REGEN_FORECAST,
    CONF_STANDARD_DAUER,
    CONF_STRAHLUNG_SCHWELLE,
    CONF_TARIF,
    CONF_VETO,
    CONF_ZIEL_OBEN,
    CONF_ZIEL_UNTEN,
    DEFAULT_REGEN_BEOBACHTET,
    DEFAULT_REGEN_FORECAST,
    DEFAULT_STANDARD_DAUER,
    DEFAULT_STRAHLUNG_SCHWELLE,
    DEFAULT_TARIF,
    DOMAIN,
)
from .entity import GartenEntity


@dataclass(frozen=True)
class _Def:
    schluessel: str
    name: str
    mini: float
    maxi: float
    step: float
    einheit: str | None
    icon: str
    fallback: float = 0.0


KREIS_NUMBERS = [
    _Def(CONF_VETO, "Veto-Schwelle Boden", 0, 100, 1, "%", "mdi:water-percent", 70),
    _Def(CONF_MIN_DAUER, "Min-Dauer", 0, 60, 1, "min", "mdi:timer-sand", 5),
    _Def(CONF_MAX_DAUER, "Max-Dauer", 1, 90, 1, "min", "mdi:timer", 20),
]
TOPF_NUMBERS = [
    _Def(CONF_ZIEL_UNTEN, "Sollband unten", 0, 100, 1, "%", "mdi:arrow-collapse-down", 45),
    _Def(CONF_ZIEL_OBEN, "Sollband oben", 0, 100, 1, "%", "mdi:arrow-collapse-up", 65),
    _Def(CONF_K_FAKTOR, "Dosis-Antwort k", 0.2, 10, 0.1, None, "mdi:chart-bell-curve", 2.0),
]
HUB_NUMBERS = [
    _Def(CONF_STANDARD_DAUER, "Standard-Dauer (Auto-Aus)", 1, 60, 1, "min",
         "mdi:timer-lock-outline", DEFAULT_STANDARD_DAUER),
    _Def(CONF_REGEN_BEOBACHTET, "Regen-Veto beobachtet", 0, 20, 0.5, "mm",
         "mdi:weather-pouring", DEFAULT_REGEN_BEOBACHTET),
    _Def(CONF_REGEN_FORECAST, "Regen-Veto Vorhersage", 0, 20, 0.5, "mm",
         "mdi:weather-cloudy-arrow-right", DEFAULT_REGEN_FORECAST),
    _Def(CONF_STRAHLUNG_SCHWELLE, "Peak-Sonnen-Sperre", 0, 200000, 1, None,
         "mdi:weather-sunny-alert", DEFAULT_STRAHLUNG_SCHWELLE),
    _Def(CONF_TARIF, "Wassertarif pro m³", 0, 20, 0.01, None, "mdi:cash", DEFAULT_TARIF),
]
DAUER_HEUTE = _Def("dauer_heute", "Dauer heute", 0, 90, 1, "min", "mdi:timer-outline")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    daten = hass.data[DOMAIN][entry.entry_id]["daten"]
    entities: list[NumberEntity] = [
        KonfigNumber(entry, daten, d, None) for d in HUB_NUMBERS
    ]
    for kreis in entry.options.get(CONF_KREISE, []):
        entities.append(DauerHeuteNumber(entry, daten, DAUER_HEUTE, kreis))
        defs = list(KREIS_NUMBERS)
        if kreis.get(CONF_KREIS_TYP) == "topf":
            defs += TOPF_NUMBERS
        entities += [KonfigNumber(entry, daten, d, kreis) for d in defs]
    async_add_entities(entities)


class _BasisNumber(GartenEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    def __init__(self, entry, daten, d: _Def, kreis) -> None:
        super().__init__(entry, daten, d.schluessel, kreis)
        self._d = d
        self._attr_name = d.name
        self._attr_native_min_value = d.mini
        self._attr_native_max_value = d.maxi
        self._attr_native_step = d.step
        self._attr_native_unit_of_measurement = d.einheit
        self._attr_icon = d.icon


class KonfigNumber(_BasisNumber):
    """Options-gestützter Regler: liest aus entry.options, schreibt zurück."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry, daten, d: _Def, kreis) -> None:
        super().__init__(entry, daten, d, kreis)
        if kreis is None:
            wert = entry.options.get(d.schluessel, d.fallback)
        else:
            wert = kreis.get(d.schluessel, d.fallback)
        self._attr_native_value = float(wert if wert is not None else d.fallback)

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
        # Write-Through in die Options (persistiert; löst KEINEN Reload aus,
        # da die Integration keine update_listener registriert).
        neu = dict(self._entry.options)
        if self._kreis is None:
            neu[self._d.schluessel] = value
        else:
            kreise = [dict(k) for k in neu.get(CONF_KREISE, [])]
            for k in kreise:
                if k[CONF_KREIS_ID] == self._kreis[CONF_KREIS_ID]:
                    k[self._d.schluessel] = value
            neu[CONF_KREISE] = kreise
        self.hass.config_entries.async_update_entry(self._entry, options=neu)


class DauerHeuteNumber(_BasisNumber, RestoreNumber):
    """Engine schreibt, Nutzer darf bis zum Lauf überschreiben (Restore)."""

    def __init__(self, entry, daten, d: _Def, kreis) -> None:
        super().__init__(entry, daten, d, kreis)
        self._attr_native_value = 0.0

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (alt := await self.async_get_last_number_data()) and alt.native_value is not None:
            self._attr_native_value = alt.native_value

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
