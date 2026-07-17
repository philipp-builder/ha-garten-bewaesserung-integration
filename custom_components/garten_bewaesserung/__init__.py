"""Garten-Bewässerung — score-basierte Bewässerungssteuerung.

Portierung der adversarial verifizierten Blueprint-Edition nach Python.
Referenz-Verhalten + Architektur: docs/ARCHITECTURE.md.
"""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

from .const import CONF_KREIS_ID, CONF_KREISE, DOMAIN, HUB_SCHLUESSEL, PLATTFORMEN
from .controller import GartenController
from .daten import GartenDaten

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Hub-Entry aufsetzen: Registry säubern, Plattformen, Engine starten."""
    hass.data.setdefault(DOMAIN, {})
    _registry_aufraeumen(hass, entry)
    daten = GartenDaten(hass, entry.entry_id)
    controller = GartenController(hass, entry, daten)
    hass.data[DOMAIN][entry.entry_id] = {"daten": daten, "controller": controller}
    await hass.config_entries.async_forward_entry_setups(entry, PLATTFORMEN)
    # Engine erst NACH den Plattformen starten — sie liest die Entities.
    await controller.start()
    _services_registrieren(hass)
    # Kein update_listener: der Options-Flow nutzt OptionsFlowWithReload,
    # der Core reloaded nach jedem Options-Speichern selbst.
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    eintrag = hass.data[DOMAIN].get(entry.entry_id)
    if eintrag and eintrag["controller"]:
        eintrag["controller"].stop()
    ok = await hass.config_entries.async_unload_platforms(entry, PLATTFORMEN)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return ok


def _registry_aufraeumen(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Entities/Devices gelöschter Kreise entfernen (Review-Finding F6).

    Ohne Aufräumen blieben sie als „nicht verfügbar" stehen — und ein später
    gleichnamig angelegter Kreis würde die alten Registry-Einträge samt
    restauriertem Alt-Zustand wiederverwenden.
    """
    kids = {k[CONF_KREIS_ID] for k in entry.options.get(CONF_KREISE, [])}
    praefix = f"{entry.entry_id}_"
    reg = er.async_get(hass)
    for eintrag in list(er.async_entries_for_config_entry(reg, entry.entry_id)):
        if not eintrag.unique_id.startswith(praefix):
            continue
        rest = eintrag.unique_id[len(praefix):]
        if rest in HUB_SCHLUESSEL:
            continue
        if any(rest.startswith(f"{kid}_") for kid in kids):
            continue
        _LOGGER.info("Entferne verwaiste Entity %s (%s)", eintrag.entity_id, rest)
        reg.async_remove(eintrag.entity_id)
    devreg = dr.async_get(hass)
    for geraet in list(dr.async_entries_for_config_entry(devreg, entry.entry_id)):
        for dom, ident in geraet.identifiers:
            if (
                dom == DOMAIN
                and ident.startswith(praefix)
                and ident[len(praefix):] not in kids
            ):
                _LOGGER.info("Entferne verwaistes Gerät %s", geraet.name)
                devreg.async_remove_device(geraet.id)
                break


def _services_registrieren(hass: HomeAssistant) -> None:
    """Automations-API: vier Services, arbeiten auf allen Hub-Einträgen."""
    if hass.services.has_service(DOMAIN, "not_aus"):
        return

    async def _alle(methode: str, **kwargs) -> None:
        for eintrag in list(hass.data.get(DOMAIN, {}).values()):
            if controller := eintrag.get("controller"):
                await getattr(controller, methode)(**kwargs)

    async def _jetzt_bewaessern(_call: ServiceCall) -> None:
        await _alle("starte_lauf", quelle="Service")

    async def _not_aus(_call: ServiceCall) -> None:
        await _alle("not_aus")

    async def _plan_neu(_call: ServiceCall) -> None:
        await _alle("plan_neu")

    async def _dosis_geben(call: ServiceCall) -> None:
        await _alle("dosis_geben", kid=call.data["kreis"])

    hass.services.async_register(DOMAIN, "jetzt_bewaessern", _jetzt_bewaessern)
    hass.services.async_register(DOMAIN, "not_aus", _not_aus)
    hass.services.async_register(DOMAIN, "plan_neu_berechnen", _plan_neu)
    hass.services.async_register(
        DOMAIN,
        "dosis_geben",
        _dosis_geben,
        schema=vol.Schema({vol.Required("kreis"): cv.string}),
    )
