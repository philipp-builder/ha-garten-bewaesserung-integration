"""One soil eligibility boundary for planning, execution and notifications."""
from datetime import datetime
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util
from .const import CONF_BATTERIE, CONF_BODENSENSOREN, CONF_KREIS_ID, CONF_KREIS_TYP, CONF_VENTILE
from .soil import INHERIT, SoilPolicy, valid_sample


class SoilController:
    def _soil_init(self):
        self.soil = SoilPolicy()
        self.soil_zones = {}
        self._soil_after = {}
        self._soil_generation = {}
        self._soil_parked = {}
        self._soil_unsub = None

    def soil_policy(self, kid=None):
        if kid is None:
            return self.soil
        return self.soil_zones.setdefault(kid, SoilPolicy(mode=INHERIT))

    def _soil_effective(self, kid):
        p = self.soil_policy(kid)
        return self.soil if p.mode == INHERIT and not p.invalid else p

    def _soil_is_parked(self, kid):
        return self._soil_effective(kid).parked(
            self.pause.active and self.pause.reason == "Winterpause"
        )

    def _soil_load(self, saved):
        if not isinstance(saved, dict):
            saved = {"garden": {"invalid_payload": True}, "zones": {}}
        self.soil = SoilPolicy.restore(saved.get("garden"))
        zones = saved.get("zones", {})
        for k in self._kreise():
            kid = k[CONF_KREIS_ID]
            value = zones.get(kid) if isinstance(zones, dict) else {"invalid_payload": True}
            self.soil_zones[kid] = SoilPolicy.restore(value, zone=True)
        # No old cached value can authorize watering after an integration restart.
        self._soil_sync(force=set(self.soil_zones))

    def _soil_save(self):
        return {"garden": self.soil.to_dict(),
                "zones": {kid: p.to_dict() for kid, p in self.soil_zones.items()}}

    def _soil_sync(self, force=()):
        changed = set()
        for k in self._kreise():
            if not k.get(CONF_BODENSENSOREN):
                continue  # sensorless weather zones have no sensor season to stop
            kid = k[CONF_KREIS_ID]
            parked = self._soil_is_parked(kid)
            if kid in force or self._soil_parked.get(kid) != parked:
                changed.add(kid)
                self._soil_after[kid] = dt_util.utcnow()
                self._soil_generation[kid] = self._soil_generation.get(kid, 0) + 1
                if unsub := self._topf_debounce.pop(kid, None):
                    unsub()
                if task := self._dose_tasks.get(kid):
                    task.cancel()
            self._soil_parked[kid] = parked
            if parked:
                self.daten.kreis(kid).boden = None
        return changed

    async def _soil_close(self, changed):
        # Keep valve close/retry safety, even with parked/missing soil sensors.
        valves = {v for k in self._kreise() if k[CONF_KREIS_ID] in changed
                  for v in k.get(CONF_VENTILE, []) if self._zustand(v) == "on"}
        if valves:
            await self._soil_close_valves(sorted(valves))

    async def _soil_close_valves(self, valves):
        await self._ventile_schliessen(valves)
        unconfirmed = [v for v in valves if self._zustand(v) != "off"]
        if unconfirmed:
            await self._sende_push(
                "⚠️ Sensorpause: Ventil prüfen",
                "Schließen nicht bestätigt: " + ", ".join(unconfirmed)
                + ". Bitte Wasseranschluss und Ventile vor Ort prüfen.",
                kritisch=self._alarm_kritisch(),
            )

    def soil_reading(self, kreis):
        kid = kreis[CONF_KREIS_ID]
        sensors = kreis.get(CONF_BODENSENSOREN) or []
        if not sensors:
            return None, "ohne_sensor"
        policy = self._soil_effective(kid)
        if policy.invalid or self.soil_policy(kid).invalid:
            return None, "fehler"
        if self._soil_is_parked(kid):
            return None, "eingelagert"
        registry = er.async_get(self.hass)
        values = []
        for eid in sensors:
            s = self.hass.states.get(eid)
            record = registry.async_get(eid)
            value = valid_sample(
                s.state if s else None, getattr(s, "last_reported", None),
                s.attributes if s else {}, now=dt_util.utcnow(),
                after=self._soil_after.get(kid, dt_util.utcnow()),
                disabled=bool(record and record.disabled_by),
            )
            if value is None:
                # A missing member must not silently remove a wet-soil veto.
                return None, "wartet_auf_messwert"
            values.append(value)
        return min(values), "aktiv"

    def soil_allowed(self, kreis):
        value, status = self.soil_reading(kreis)
        if status == "fehler":
            return False
        if kreis.get(CONF_KREIS_TYP) == "topf":
            return value is not None
        return (value is not None or status == "ohne_sensor"
                or self.soil_policy(kreis[CONF_KREIS_ID]).weather_only)

    def soil_attributes(self, kreis):
        kid = kreis[CONF_KREIS_ID]
        value, status = self.soil_reading(kreis)
        return {"status": status, "monitoring_expected": status != "eingelagert",
                "source_entities": list(kreis.get(CONF_BODENSENSOREN) or []),
                "fresh_after": self._soil_after.get(kid), "max_age_hours": 24,
                "watering_allowed_by_soil": self.soil_allowed(kreis),
                "weather_only_allowed": self.soil_policy(kid).weather_only,
                "effective_mode": self._soil_effective(kid).mode,
                "mode": self.soil_policy(kid).mode, "moisture": value}

    @callback
    def _soil_event(self, event):
        if self._gestoppt:
            return
        for k in self._kreise():
            if event.data["entity_id"] in (k.get(CONF_BODENSENSOREN) or []):
                self.daten.kreis(k[CONF_KREIS_ID]).boden = self.soil_reading(k)[0]
        self.daten.broadcast()
        self._topf_boden_ereignis(event)

    async def soil_change(self, kid=None, **values):
        async with self._pause_lock:
            if not self.pause_ready:
                raise ValueError("Sensorsteuerung startet noch")
            if kid is not None and not any(k[CONF_KREIS_ID] == kid for k in self._kreise()):
                raise ValueError("Unbekannter Kreis")
            p = self.soil_policy(kid).changed(dt_util.now(), zone=kid is not None, **values)
            if kid is None:
                self.soil = p
                affected = {k[CONF_KREIS_ID] for k in self._kreise()
                            if self.soil_policy(k[CONF_KREIS_ID]).mode == INHERIT}
            else:
                self.soil_zones[kid] = p
                affected = {kid}
            # Invalidate queued work BEFORE the first await, including rapid off/on.
            changed = self._soil_sync(force=affected)
            try:
                await self._store_sichern()
            finally:
                await self._soil_close(changed)
            self._arm_soil()
            await self._recompute_alle()
            self._arme_tagestimer()  # future only; never invoke dosing/catch-up here
            self.daten.broadcast()

    @callback
    def _arm_soil(self):
        if self._soil_unsub:
            self._soil_unsub()
            self._soil_unsub = None
        ends = [datetime.fromisoformat(p.until) for p in [self.soil, *self.soil_zones.values()]
                if p.timed and not p.invalid]
        if ends and not self._gestoppt:
            self._soil_unsub = async_track_point_in_time(self.hass, self._soil_expired, min(ends))

    async def _soil_expired(self, _now):
        async with self._pause_lock:
            if self._gestoppt:
                return
            changed = self.soil.expire(dt_util.now())
            for p in self.soil_zones.values():
                changed = p.expire(dt_util.now()) or changed
            if changed:
                affected = self._soil_sync()
                await self._store_sichern()
                await self._soil_close(affected)
                await self._recompute_alle()
                self._arme_tagestimer()
                self.daten.broadcast()
            self._arm_soil()

    def _soil_battery_suppressed(self, eid):
        """Only a proven parked soil device; never a valve or active consumer."""
        registry = er.async_get(self.hass)
        battery = registry.async_get(eid)
        if not battery or not battery.device_id:
            return False
        device = battery.device_id
        def same(source):
            record = registry.async_get(source)
            return record is not None and record.device_id == device
        consumers = []
        for k in self._kreise():
            if any(same(v) for v in k.get(CONF_VENTILE, [])):
                return False
            if any(same(s) for s in k.get(CONF_BODENSENSOREN, [])):
                consumers.append(k)
            elif eid in k.get(CONF_BATTERIE, []):
                return False  # unknown role in another zone: retain safety alert
        return bool(consumers) and all(self.soil_reading(k)[1] == "eingelagert" for k in consumers)
