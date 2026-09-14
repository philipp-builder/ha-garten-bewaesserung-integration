"""Deterministic controller race test; run inside the pinned HA image."""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).parents[1]))
import homeassistant  # initialize its validation compatibility layer first
from custom_components.garten_bewaesserung.controller import GartenController
from custom_components.garten_bewaesserung.daten import KreisLaufzeit
from custom_components.garten_bewaesserung.pause import Pause

async def run():
    for resumed in (False, True):
        c = object.__new__(GartenController)
        c._gestoppt = False
        c.pause_ready = True
        c.pause = Pause()
        c._pause_generation = 0
        c._dose_tasks = {}
        c._letzte_dose = {}
        c._kreise = lambda: [{'id': 'tomaten', 'typ': 'topf', 'ventile': ['switch.fake']}]
        c._zustand = lambda eid: 'off'
        c._topf_boden = lambda kreis: 30
        c._zahl = lambda domain, key, kid, fallback: fallback
        c.daten = SimpleNamespace(kreis=lambda kid: KreisLaufzeit(), broadcast=lambda: None)
        c.entry = SimpleNamespace(options={})
        async def interleaved_store():
            c._pause_generation += 1
            c.pause.active = not resumed
        c._store_sichern = interleaved_store
        # A stale enqueue would require nonexistent hass/create_task and fail.
        await c.dosis_geben('tomaten')
        assert c._dose_tasks == {}
    print('PASS: pause during pending dose persistence, including immediate resume')

asyncio.run(run())
