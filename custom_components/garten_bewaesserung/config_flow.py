"""Config- und Options-Flow der Garten-Bewässerung.

Setup = bewusst minimal (nur Wetter-Entity). Alles Weitere — Kreise,
Benachrichtigungen, Tuning — läuft über den Options-Flow („Konfigurieren"),
damit die Erst-Einrichtung in unter einer Minute steht.

Kreise leben als Liste in entry.options[CONF_KREISE]; die Kreis-ID (Slug)
wird bei Anlage aus dem Namen erzeugt und danach NIE geändert (Entity-ID-
Stabilität). Umbenennen ändert nur den Anzeigenamen.
"""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import section
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERIE,
    CONF_BODENSENSOREN,
    CONF_DASHBOARD_PFAD,
    CONF_FLOW_SENSOR,
    CONF_GRUPPE,
    CONF_K_FAKTOR,
    CONF_KREIS_ID,
    CONF_KREIS_NAME,
    CONF_KREIS_TYP,
    CONF_KREISE,
    CONF_LECK,
    CONF_MAX_DAUER,
    CONF_MIN_DAUER,
    CONF_NOTAUS_MIN,
    CONF_NOTIFY,
    CONF_PARALLEL,
    CONF_START_MIT_GRUPPE,
    CONF_PUSH_KRITISCH,
    CONF_REGEN_BEOBACHTET,
    CONF_REGEN_FORECAST,
    CONF_REGEN_SENSOR,
    CONF_STANDARD_DAUER,
    CONF_STRAHLUNG_SCHWELLE,
    CONF_STRAHLUNG_SENSOR,
    CONF_TARIF,
    CONF_VENTILE,
    CONF_VERSORGUNG,
    CONF_VETO,
    CONF_VORLAUF,
    CONF_WAEHRUNG,
    CONF_WETTER,
    CONF_ZEIT,
    CONF_ZIEL_OBEN,
    CONF_ZIEL_UNTEN,
    DEFAULT_NOTAUS_MIN,
    DEFAULT_REGEN_BEOBACHTET,
    DEFAULT_REGEN_FORECAST,
    DEFAULT_STANDARD_DAUER,
    DEFAULT_STRAHLUNG_SCHWELLE,
    DEFAULT_TARIF,
    DEFAULT_VORLAUF,
    DEFAULT_WAEHRUNG,
    DEFAULT_ZEIT,
    DOMAIN,
    KREIS_TYP_DEFAULTS,
    SCORE_DEFAULTS,
    TOPF_DEFAULTS,
)


def _slugify(name: str) -> str:
    """Deutschen Namen in einen stabilen ASCII-Slug wandeln."""
    s = name.strip().lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s or "kreis"


def _eindeutige_id(name: str, vorhandene: list[dict[str, Any]]) -> str:
    basis = _slugify(name)
    ids = {k[CONF_KREIS_ID] for k in vorhandene}
    kandidat, n = basis, 2
    while kandidat in ids:
        kandidat = f"{basis}_{n}"
        n += 1
    return kandidat


def _notify_liste(rohtext: str) -> list[str]:
    """Komma-Liste → validierte notify-Dienste (Kit-Konvention)."""
    return [
        t.strip()
        for t in rohtext.split(",")
        if t.strip().startswith("notify.")
    ]


class GartenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Erst-Einrichtung des Hubs (bewusst nur ein Schritt)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            options: dict[str, Any] = {
                CONF_WETTER: user_input[CONF_WETTER],
                CONF_REGEN_SENSOR: "",
                CONF_STRAHLUNG_SENSOR: "",
                CONF_NOTIFY: [],
                CONF_PUSH_KRITISCH: True,
                CONF_DASHBOARD_PFAD: "",
                CONF_ZEIT: DEFAULT_ZEIT,
                CONF_VORLAUF: DEFAULT_VORLAUF,
                CONF_STANDARD_DAUER: DEFAULT_STANDARD_DAUER,
                CONF_REGEN_BEOBACHTET: DEFAULT_REGEN_BEOBACHTET,
                CONF_REGEN_FORECAST: DEFAULT_REGEN_FORECAST,
                CONF_STRAHLUNG_SCHWELLE: DEFAULT_STRAHLUNG_SCHWELLE,
                CONF_NOTAUS_MIN: DEFAULT_NOTAUS_MIN,
                CONF_TARIF: DEFAULT_TARIF,
                CONF_WAEHRUNG: DEFAULT_WAEHRUNG,
                "score": dict(SCORE_DEFAULTS),
                "topf": dict(TOPF_DEFAULTS),
                CONF_KREISE: [],
            }
            return self.async_create_entry(
                title="Garten-Bewässerung", data={}, options=options
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_WETTER): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="weather")
                    )
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "GartenOptionsFlow":
        return GartenOptionsFlow(config_entry)


class GartenOptionsFlow(OptionsFlowWithReload):
    """Options-Menü: Globales · Benachrichtigungen · Tuning · Kreis-CRUD.

    OptionsFlowWithReload statt update_listener: der Core reloaded den Entry
    selbst nach dem Speichern — kein Race zwischen Flow-Finish und der
    Listener-Registrierung im Setup (im E2E-Test real aufgetreten).
    """

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._neu: dict[str, Any] = {}  # Zwischenspeicher beim Kreis-Anlegen/-Bearbeiten
        self._edit_id: str | None = None

    # ---------- Helpers ----------

    @property
    def _opt(self) -> dict[str, Any]:
        return dict(self._entry.options)

    def _kreise(self) -> list[dict[str, Any]]:
        return [dict(k) for k in self._entry.options.get(CONF_KREISE, [])]

    def _speichern(self, aenderungen: dict[str, Any]) -> ConfigFlowResult:
        neu = self._opt
        neu.update(aenderungen)
        return self.async_create_entry(title="", data=neu)

    # ---------- Menü ----------

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        optionen = ["globale_einstellungen", "benachrichtigungen", "tuning", "kreis_hinzufuegen"]
        if self._kreise():
            optionen += ["kreis_bearbeiten", "kreis_entfernen"]
        return self.async_show_menu(step_id="init", menu_options=optionen)

    # ---------- Globale Einstellungen ----------

    async def async_step_globale_einstellungen(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        o = self._opt
        if user_input is not None:
            user_input[CONF_REGEN_SENSOR] = user_input.get(CONF_REGEN_SENSOR) or ""
            user_input[CONF_STRAHLUNG_SENSOR] = user_input.get(CONF_STRAHLUNG_SENSOR) or ""
            return self._speichern(user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_WETTER, default=o[CONF_WETTER]): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
                vol.Optional(
                    CONF_REGEN_SENSOR,
                    description={"suggested_value": o.get(CONF_REGEN_SENSOR, "")},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    CONF_STRAHLUNG_SENSOR,
                    description={"suggested_value": o.get(CONF_STRAHLUNG_SENSOR, "")},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_ZEIT, default=o.get(CONF_ZEIT, DEFAULT_ZEIT)): selector.TimeSelector(),
                vol.Required(
                    CONF_VORLAUF, default=o.get(CONF_VORLAUF, DEFAULT_VORLAUF)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=120, step=5, unit_of_measurement="min")
                ),
                vol.Required(
                    CONF_STANDARD_DAUER, default=o.get(CONF_STANDARD_DAUER, DEFAULT_STANDARD_DAUER)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=1, max=60, step=1, unit_of_measurement="min")
                ),
                vol.Required(
                    CONF_NOTAUS_MIN, default=o.get(CONF_NOTAUS_MIN, DEFAULT_NOTAUS_MIN)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=5, max=240, step=5, unit_of_measurement="min")
                ),
            }
        )
        return self.async_show_form(step_id="globale_einstellungen", data_schema=schema)

    # ---------- Benachrichtigungen ----------

    async def async_step_benachrichtigungen(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        o = self._opt
        if user_input is not None:
            return self._speichern(
                {
                    CONF_NOTIFY: _notify_liste(user_input.get("notify_text", "")),
                    CONF_PUSH_KRITISCH: user_input[CONF_PUSH_KRITISCH],
                    CONF_DASHBOARD_PFAD: user_input.get(CONF_DASHBOARD_PFAD, "").strip(),
                }
            )
        schema = vol.Schema(
            {
                vol.Optional(
                    "notify_text",
                    description={"suggested_value": ", ".join(o.get(CONF_NOTIFY, []))},
                ): selector.TextSelector(),
                vol.Required(
                    CONF_PUSH_KRITISCH, default=o.get(CONF_PUSH_KRITISCH, True)
                ): selector.BooleanSelector(),
                vol.Optional(
                    CONF_DASHBOARD_PFAD,
                    description={"suggested_value": o.get(CONF_DASHBOARD_PFAD, "")},
                ): selector.TextSelector(),
            }
        )
        return self.async_show_form(step_id="benachrichtigungen", data_schema=schema)

    # ---------- Tuning (Score + Regen/Strahlung + Topf + Kosten) ----------

    async def async_step_tuning(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        o = self._opt
        score = {**SCORE_DEFAULTS, **o.get("score", {})}
        topf = {**TOPF_DEFAULTS, **o.get("topf", {})}
        if user_input is not None:
            # section()-Gruppen liefern verschachtelte Dicts -> flach klopfen
            flach: dict[str, Any] = {}
            for wert in user_input.values():
                if isinstance(wert, dict):
                    flach.update(wert)
            neu_score = {
                k: flach[f"score_{k}"]
                for k in SCORE_DEFAULTS
                if f"score_{k}" in flach
            }
            neu_topf = {k: flach[f"topf_{k}"] for k in TOPF_DEFAULTS}
            return self._speichern(
                {
                    "score": {**score, **neu_score},
                    "topf": {**topf, **neu_topf},
                    CONF_REGEN_BEOBACHTET: flach[CONF_REGEN_BEOBACHTET],
                    CONF_REGEN_FORECAST: flach[CONF_REGEN_FORECAST],
                    CONF_STRAHLUNG_SCHWELLE: flach[CONF_STRAHLUNG_SCHWELLE],
                    CONF_TARIF: flach[CONF_TARIF],
                    CONF_WAEHRUNG: flach[CONF_WAEHRUNG],
                }
            )

        def _num(mini: float, maxi: float, step: float, einheit: str | None = None):
            cfg = selector.NumberSelectorConfig(
                min=mini, max=maxi, step=step, mode=selector.NumberSelectorMode.BOX
            )
            if einheit:
                cfg["unit_of_measurement"] = einheit
            return selector.NumberSelector(cfg)

        schema = vol.Schema(
            {
                vol.Required("gewichte"): section(
                    vol.Schema(
                        {
                            vol.Required("score_gewicht_boden", default=score["gewicht_boden"]): _num(0, 100, 1),
                            vol.Required("score_gewicht_temp", default=score["gewicht_temp"]): _num(0, 100, 1),
                            vol.Required("score_gewicht_tage", default=score["gewicht_tage"]): _num(0, 100, 1),
                            vol.Required("score_skip_schwelle", default=score["skip_schwelle"]): _num(1, 100, 1),
                            vol.Required("score_tage_saettigung", default=score["tage_saettigung"]): _num(1, 30, 1, "d"),
                        }
                    ),
                    {"collapsed": False},
                ),
                vol.Required("temperatur"): section(
                    vol.Schema(
                        {
                            vol.Required("score_temp_quelle", default=score["temp_quelle"]): selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=["tmax", "et0"], translation_key="temp_quelle"
                                )
                            ),
                            vol.Required("score_temp_anker", default=score["temp_anker"]): _num(-10, 30, 0.5, "°C"),
                            vol.Required("score_temp_spanne", default=score["temp_spanne"]): _num(1, 30, 0.5, "°C"),
                            vol.Required("score_et0_anker", default=score["et0_anker"]): _num(0, 5, 0.1, "mm"),
                            vol.Required("score_et0_spanne", default=score["et0_spanne"]): _num(0.5, 10, 0.1, "mm"),
                            vol.Required("score_forecast_typ", default=score["forecast_typ"]): selector.SelectSelector(
                                selector.SelectSelectorConfig(options=["daily", "hourly"])
                            ),
                        }
                    ),
                    {"collapsed": True},
                ),
                vol.Required("regen_sonne"): section(
                    vol.Schema(
                        {
                            vol.Required(CONF_REGEN_BEOBACHTET, default=o.get(CONF_REGEN_BEOBACHTET)): _num(0, 20, 0.5, "mm"),
                            vol.Required(CONF_REGEN_FORECAST, default=o.get(CONF_REGEN_FORECAST)): _num(0, 20, 0.5, "mm"),
                            vol.Required(CONF_STRAHLUNG_SCHWELLE, default=o.get(CONF_STRAHLUNG_SCHWELLE)): _num(0, 200000, 1),
                        }
                    ),
                    {"collapsed": True},
                ),
                vol.Required("toepfe"): section(
                    vol.Schema(
                        {
                            vol.Required("topf_max_dosen", default=topf["max_dosen"]): _num(1, 20, 1),
                            vol.Required("topf_dosis_max_min", default=topf["dosis_max_min"]): _num(1, 30, 1, "min"),
                            vol.Required("topf_min_intervall_min", default=topf["min_intervall_min"]): _num(10, 360, 5, "min"),
                            vol.Required("topf_glitch_grenze", default=topf["glitch_grenze"]): _num(0, 30, 1, "%"),
                        }
                    ),
                    {"collapsed": True},
                ),
                vol.Required("kosten"): section(
                    vol.Schema(
                        {
                            vol.Required(CONF_TARIF, default=o.get(CONF_TARIF)): _num(0, 20, 0.01),
                            vol.Required(CONF_WAEHRUNG, default=o.get(CONF_WAEHRUNG, DEFAULT_WAEHRUNG)): selector.TextSelector(),
                        }
                    ),
                    {"collapsed": True},
                ),
            }
        )
        return self.async_show_form(
            step_id="tuning",
            data_schema=schema,
            description_placeholders={
                "rechner_url": "https://philipp-builder.github.io/ha-garten-bewaesserung-integration/#playground",
                "rechner_url_de": "https://philipp-builder.github.io/ha-garten-bewaesserung-integration/de/#playground",
            },
        )

    # ---------- Kreis anlegen ----------

    async def async_step_kreis_hinzufuegen(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            typ = user_input[CONF_KREIS_TYP]
            defaults = KREIS_TYP_DEFAULTS[typ]
            self._neu = {
                CONF_KREIS_ID: _eindeutige_id(user_input[CONF_KREIS_NAME], self._kreise()),
                CONF_KREIS_NAME: user_input[CONF_KREIS_NAME].strip(),
                CONF_KREIS_TYP: typ,
                CONF_VENTILE: user_input[CONF_VENTILE],
                CONF_BODENSENSOREN: user_input.get(CONF_BODENSENSOREN, []),
                CONF_PARALLEL: user_input["ausfuehrung"] != "sequenziell",
                CONF_START_MIT_GRUPPE: user_input["ausfuehrung"] == "parallel_gruppe",
                CONF_GRUPPE: int(user_input[CONF_GRUPPE]),
                **defaults,
            }
            self._edit_id = None
            return await self.async_step_kreis_details()

        naechste_nr = (
            max((k.get(CONF_GRUPPE, 1) for k in self._kreise()), default=0) + 1
        )
        schema = vol.Schema(
            {
                vol.Required(CONF_KREIS_NAME): selector.TextSelector(),
                vol.Required(CONF_KREIS_TYP, default="rasen"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["rasen", "topf"], translation_key="kreis_typ"
                    )
                ),
                vol.Required(CONF_VENTILE): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch", multiple=True)
                ),
                vol.Optional(CONF_BODENSENSOREN, default=[]): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", multiple=True)
                ),
                vol.Required("ausfuehrung", default="parallel_start"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["sequenziell", "parallel_start", "parallel_gruppe"],
                        translation_key="ausfuehrung",
                    )
                ),
                vol.Required(CONF_GRUPPE, default=naechste_nr): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=20, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(step_id="kreis_hinzufuegen", data_schema=schema)

    async def async_step_kreis_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Schritt 2: Dauer-/Schwellen-Defaults + optionale Sensorik."""
        k = self._neu
        ist_topf = k[CONF_KREIS_TYP] == "topf"
        if user_input is not None:
            k[CONF_VETO] = user_input[CONF_VETO]
            k[CONF_MIN_DAUER] = user_input[CONF_MIN_DAUER]
            k[CONF_MAX_DAUER] = user_input[CONF_MAX_DAUER]
            k["temp_quelle"] = user_input["temp_quelle"]
            if ist_topf:
                k[CONF_ZIEL_UNTEN] = user_input[CONF_ZIEL_UNTEN]
                k[CONF_ZIEL_OBEN] = user_input[CONF_ZIEL_OBEN]
                k[CONF_K_FAKTOR] = user_input[CONF_K_FAKTOR]
            k[CONF_FLOW_SENSOR] = user_input.get(CONF_FLOW_SENSOR) or ""
            k[CONF_LECK] = user_input.get(CONF_LECK, [])
            k[CONF_VERSORGUNG] = user_input.get(CONF_VERSORGUNG) or ""
            k[CONF_BATTERIE] = user_input.get(CONF_BATTERIE, [])

            kreise = self._kreise()
            if self._edit_id:
                kreise = [
                    k if alt[CONF_KREIS_ID] == self._edit_id else alt for alt in kreise
                ]
            else:
                kreise.append(k)
            return self._speichern({CONF_KREISE: kreise})

        felder: dict[Any, Any] = {
            vol.Required(CONF_VETO, default=k.get(CONF_VETO)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%")
            ),
            vol.Required(CONF_MIN_DAUER, default=k.get(CONF_MIN_DAUER)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=60, step=1, unit_of_measurement="min")
            ),
            vol.Required(CONF_MAX_DAUER, default=k.get(CONF_MAX_DAUER)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=90, step=1, unit_of_measurement="min")
            ),
            vol.Required(
                "temp_quelle", default=k.get("temp_quelle", "global")
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["global", "tmax", "et0"],
                    translation_key="temp_quelle_kreis",
                )
            ),
        }
        if ist_topf:
            felder.update(
                {
                    vol.Required(
                        CONF_ZIEL_UNTEN, default=k.get(CONF_ZIEL_UNTEN)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%")
                    ),
                    vol.Required(
                        CONF_ZIEL_OBEN, default=k.get(CONF_ZIEL_OBEN)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%")
                    ),
                    vol.Required(
                        CONF_K_FAKTOR, default=k.get(CONF_K_FAKTOR, 2.0)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.2, max=10, step=0.1, mode=selector.NumberSelectorMode.BOX
                        )
                    ),
                }
            )
        felder.update(
            {
                vol.Optional(
                    CONF_FLOW_SENSOR,
                    description={"suggested_value": k.get(CONF_FLOW_SENSOR, "")},
                ): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
                vol.Optional(CONF_LECK, default=k.get(CONF_LECK, [])): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor", multiple=True)
                ),
                vol.Optional(
                    CONF_VERSORGUNG,
                    description={"suggested_value": k.get(CONF_VERSORGUNG, "")},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                vol.Optional(
                    CONF_BATTERIE, default=k.get(CONF_BATTERIE, [])
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", multiple=True)
                ),
            }
        )
        return self.async_show_form(step_id="kreis_details", data_schema=vol.Schema(felder))

    # ---------- Kreis bearbeiten / entfernen ----------

    def _kreis_auswahl_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("kreis"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=k[CONF_KREIS_ID], label=k[CONF_KREIS_NAME]
                            )
                            for k in self._kreise()
                        ]
                    )
                )
            }
        )

    async def async_step_kreis_bearbeiten(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            kid = user_input["kreis"]
            self._neu = next(k for k in self._kreise() if k[CONF_KREIS_ID] == kid)
            self._edit_id = kid
            return await self.async_step_kreis_basis_bearbeiten()
        return self.async_show_form(
            step_id="kreis_bearbeiten", data_schema=self._kreis_auswahl_schema()
        )

    async def async_step_kreis_basis_bearbeiten(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        k = self._neu
        if user_input is not None:
            k[CONF_KREIS_NAME] = user_input[CONF_KREIS_NAME].strip()
            neuer_typ = user_input[CONF_KREIS_TYP]
            if neuer_typ != k.get(CONF_KREIS_TYP):
                # Typwechsel: fehlende typ-spezifische Felder mit Defaults
                # seeden, konfigurierte Werte (Veto/Dauern) unangetastet lassen.
                # Alt-Felder bleiben im Dict (harmlos; bei Rückwechsel wieder
                # aktiv) — die Entities räumt _registry_aufraeumen beim Reload.
                k[CONF_KREIS_TYP] = neuer_typ
                for feld, wert in KREIS_TYP_DEFAULTS[neuer_typ].items():
                    k.setdefault(feld, wert)
            k[CONF_VENTILE] = user_input[CONF_VENTILE]
            k[CONF_BODENSENSOREN] = user_input.get(CONF_BODENSENSOREN, [])
            k[CONF_PARALLEL] = user_input["ausfuehrung"] != "sequenziell"
            k[CONF_START_MIT_GRUPPE] = user_input["ausfuehrung"] == "parallel_gruppe"
            k[CONF_GRUPPE] = int(user_input[CONF_GRUPPE])
            return await self.async_step_kreis_details()
        schema = vol.Schema(
            {
                vol.Required(CONF_KREIS_NAME, default=k[CONF_KREIS_NAME]): selector.TextSelector(),
                vol.Required(CONF_KREIS_TYP, default=k[CONF_KREIS_TYP]): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["rasen", "topf"], translation_key="kreis_typ"
                    )
                ),
                vol.Required(CONF_VENTILE, default=k[CONF_VENTILE]): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch", multiple=True)
                ),
                vol.Optional(
                    CONF_BODENSENSOREN, default=k.get(CONF_BODENSENSOREN, [])
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", multiple=True)
                ),
                vol.Required(
                    "ausfuehrung",
                    default=(
                        "sequenziell"
                        if not k.get(CONF_PARALLEL, True)
                        else "parallel_gruppe"
                        if k.get(CONF_START_MIT_GRUPPE)
                        else "parallel_start"
                    ),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=["sequenziell", "parallel_start", "parallel_gruppe"],
                        translation_key="ausfuehrung",
                    )
                ),
                vol.Required(CONF_GRUPPE, default=k.get(CONF_GRUPPE, 1)): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1, max=20, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                ),
            }
        )
        return self.async_show_form(step_id="kreis_basis_bearbeiten", data_schema=schema)

    async def async_step_kreis_entfernen(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            kreise = [
                k for k in self._kreise() if k[CONF_KREIS_ID] != user_input["kreis"]
            ]
            return self._speichern({CONF_KREISE: kreise})
        return self.async_show_form(
            step_id="kreis_entfernen", data_schema=self._kreis_auswahl_schema()
        )
