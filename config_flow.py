"""Config flow pour TigerTag — avec gestion des lieux de stockage."""
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    TigerTagApiClient,
    TigerTagApiClientAuthenticationError,
    TigerTagApiClientCommunicationError,
)
from .const import CONF_API_KEY, CONF_EMAIL, CONF_LOCATIONS, DEFAULT_LOCATIONS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema({
    vol.Required(CONF_EMAIL):   str,
    vol.Required(CONF_API_KEY): str,
})


async def _validate_credentials(hass, data: dict[str, Any]) -> str:
    session = async_get_clientsession(hass)
    client  = TigerTagApiClient(
        email=data[CONF_EMAIL], api_key=data[CONF_API_KEY], session=session,
    )
    if not await client.ping():
        raise TigerTagApiClientAuthenticationError
    return f"TigerTag ({data[CONF_EMAIL]})"


class TigerTagConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flux de configuration en 2 étapes : identifiants → lieux de stockage."""

    VERSION = 1

    def __init__(self):
        self._data: dict[str, Any] = {}
        self._title: str = ""

    # ── Étape 1 : identifiants ──────────────────────────────────────────────
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._title = await _validate_credentials(self.hass, user_input)
            except TigerTagApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except TigerTagApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Erreur inattendue lors de la validation TigerTag")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL])
                self._abort_if_unique_id_configured()
                self._data.update(user_input)
                return await self.async_step_locations()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors,
        )

    # ── Étape 2 : lieux de stockage ─────────────────────────────────────────
    async def async_step_locations(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """
        L'utilisateur saisit ses lieux de stockage séparés par des virgules.
        Ex : "Garage, Salon, Bureau, Cave"
        """
        errors: dict[str, str] = {}
        default_str = ", ".join(DEFAULT_LOCATIONS)

        if user_input is not None:
            raw = user_input.get("locations_raw", default_str)
            locations = [loc.strip() for loc in raw.split(",") if loc.strip()]
            if not locations:
                errors["base"] = "no_locations"
            else:
                self._data[CONF_LOCATIONS] = locations
                return self.async_create_entry(title=self._title, data=self._data)

        schema = vol.Schema({
            vol.Required("locations_raw", default=default_str): str,
        })
        return self.async_show_form(
            step_id="locations",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "example": "Garage, Salon, Bureau, Cave"
            },
        )

    # ── Options flow : modification des lieux après installation ────────────
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TigerTagOptionsFlow(config_entry)


class TigerTagOptionsFlow(config_entries.OptionsFlow):
    """
    Permet de modifier les lieux de stockage depuis
    Paramètres → Intégrations → TigerTag → Configurer.
    """

    def __init__(self, config_entry):
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        current = self._entry.data.get(CONF_LOCATIONS, DEFAULT_LOCATIONS)
        current_str = ", ".join(current)

        if user_input is not None:
            raw = user_input.get("locations_raw", current_str)
            locations = [loc.strip() for loc in raw.split(",") if loc.strip()]
            if not locations:
                errors["base"] = "no_locations"
            else:
                # On met à jour entry.data avec les nouveaux lieux
                new_data = dict(self._entry.data)
                new_data[CONF_LOCATIONS] = locations
                self.hass.config_entries.async_update_entry(
                    self._entry, data=new_data
                )
                return self.async_create_entry(title="", data={})

        schema = vol.Schema({
            vol.Required("locations_raw", default=current_str): str,
        })
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={"example": "Garage, Salon, Bureau, Cave"},
        )
