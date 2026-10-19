"""Native platform/identity checks in real HA; no devices or credentials."""
import asyncio
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch
sys.path.insert(0, str(Path(__file__).parents[1]))
import homeassistant
from custom_components.garten_bewaesserung import select, datetime, switch, sensor
from custom_components.garten_bewaesserung.const import HUB_SCHLUESSEL, BODEN_KREIS_SCHLUESSEL
from custom_components.garten_bewaesserung.soil import SoilPolicy, INHERIT
from custom_components.garten_bewaesserung.soil_entity import SoilEntity
from custom_components.garten_bewaesserung.controller import GartenController
from custom_components.garten_bewaesserung.daten import GartenDaten
from homeassistant.core import HomeAssistant


async def run():
    zones = [{"id": "lawn", "name": "Lawn", "typ": "rasen", "bodensensoren": ["sensor.soil"]},
             {"id": "pot", "name": "Pot", "typ": "topf", "bodensensoren": ["sensor.pot"]},
             {"id": "weather", "name": "Weather", "typ": "rasen"}]
    entry = NS(entry_id="test", options={"kreise": zones})
    policies = {None: SoilPolicy(), "lawn": SoilPolicy(mode=INHERIT), "pot": SoilPolicy(mode=INHERIT)}
    c = NS(soil_policy=lambda kid: policies[kid], pause_ready=True, soil_change=AsyncMock(),
           soil_reading=lambda k: (None, "eingelagert"),
           soil_attributes=lambda k: {"monitoring_expected": False}, _kreise=lambda: zones)
    hass = NS(data={"garten_bewaesserung": {"test": {"daten": NS(), "controller": c}}})
    entities = []
    for platform in (select, datetime, switch, sensor):
        await platform.async_setup_entry(hass, entry, entities.extend)
    new = [e for e in entities if isinstance(e, SoilEntity)]
    assert len(new) == 13  # four garden controls, four per soil zone, lawn-only fallback
    assert len({e.unique_id for e in entities}) == len(entities)
    for e in new:
        e.hass = hass
        assert e.available
        key = e.unique_id.removeprefix("test_")
        if e.soil_kid:
            assert key.removeprefix(e.soil_kid+"_") in BODEN_KREIS_SCHLUESSEL
        else:
            assert key in HUB_SCHLUESSEL
        if isinstance(e, select.SoilMode):
            assert e.current_option in e.options
            await e.async_select_option("Eingelagert")
        if isinstance(e, select.SoilFallback):
            assert e.soil_kid == "lawn"
            assert e.current_option == "Sperren"
        if isinstance(e, sensor.SoilStatus):
            assert e.native_value is not None
        if isinstance(e, datetime.SoilEnd):
            assert e.native_value is None
        if isinstance(e, switch.SoilTimed):
            assert not e.is_on
    c.pause_ready = False
    assert all(not e.available for e in new)
    print("PASS: 13 native season entities, identity/registry scope, safe startup, no weather-only pot control")
    await report_bus()


async def report_bus():
    """Real controller startup + real unchanged-report bus, no running HA server."""
    with TemporaryDirectory() as directory:
        hass = HomeAssistant(directory)
        zone = {"id": "lawn", "name": "Lawn", "typ": "rasen", "bodensensoren": ["sensor.test_soil"]}
        entry = NS(entry_id="season-test", options={"kreise": [zone]},
                   async_create_background_task=lambda h, coro, name: h.async_create_task(coro))
        c = GartenController(hass, entry, GartenDaten(hass, entry.entry_id))
        c._store_laden = AsyncMock(side_effect=lambda: c._soil_load({}))
        c._startup_recovery = AsyncMock()
        c._recompute_alle = AsyncMock()
        c._arme_tagestimer = Mock()
        c._eid = lambda *args: None
        registry = NS(async_get=lambda eid: None)
        with patch("custom_components.garten_bewaesserung.soil_controller.er.async_get", return_value=registry), \
             patch("custom_components.garten_bewaesserung.controller.ir.async_get", return_value=NS(issues={})):
            hass.states.async_set("sensor.test_soil", "5")
            await c.start()
            assert c.soil_reading(zone)[1] == "wartet_auf_messwert"
            old_changed = hass.states.get("sensor.test_soil").last_changed
            hass.states.async_set("sensor.test_soil", "5")
            await hass.async_block_till_done()
            assert hass.states.get("sensor.test_soil").last_changed == old_changed
            assert c.soil_reading(zone) == (5, "aktiv")
            assert c.daten.kreis("lawn").boden == 5
            c.stop()
            hass.states.async_set("sensor.test_soil", "9")
            await hass.async_block_till_done()
            assert c.daten.kreis("lawn").boden == 5  # listener really removed
        print("PASS: real HA start/stop + unchanged report freshness; no hardware polling")


asyncio.run(run())
