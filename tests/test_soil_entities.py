"""Native platform/identity checks in real HA; no devices or credentials."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
sys.path.insert(0, str(Path(__file__).parents[1]))
import homeassistant
from custom_components.garten_bewaesserung import select, datetime, switch, sensor
from custom_components.garten_bewaesserung.const import HUB_SCHLUESSEL, BODEN_KREIS_SCHLUESSEL
from custom_components.garten_bewaesserung.soil import SoilPolicy, INHERIT
from custom_components.garten_bewaesserung.soil_entity import SoilEntity


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


asyncio.run(run())
