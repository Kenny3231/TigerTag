"""Config flow pour TigerTag — Email/Password ou Google OAuth (refresh token)."""
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
from .const import (
    CONF_EMAIL, CONF_PASSWORD, CONF_FIREBASE_UID, DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

# Schémas des deux modes d'auth
STEP_AUTH_MODE_SCHEMA = vol.Schema({
    vol.Required("auth_mode", default="password"): vol.In(["password", "token"]),
})

STEP_PASSWORD_SCHEMA = vol.Schema({
    vol.Required(CONF_EMAIL):    str,
    vol.Required(CONF_PASSWORD): str,
})

STEP_TOKEN_SCHEMA = vol.Schema({
    vol.Required(CONF_EMAIL):         str,
    vol.Required("refresh_token"):    str,
})


async def _validate_password(hass, data: dict[str, Any]) -> tuple[str, str, str]:
    """Valide email/password. Retourne (title, firebase_uid, refresh_token)."""
    session = async_get_clientsession(hass)
    client  = TigerTagApiClient(
        email=data[CONF_EMAIL],
        password=data[CONF_PASSWORD],
        session=session,
    )
    await client.authenticate()
    return f"TigerTag ({data[CONF_EMAIL]})", client.firebase_uid, client.refresh_token


async def _validate_token(hass, data: dict[str, Any]) -> tuple[str, str, str]:
    """
    Valide un refresh token Firebase (ex: obtenu depuis Google OAuth).
    Retourne (title, firebase_uid, refresh_token).
    """
    session = async_get_clientsession(hass)
    client  = TigerTagApiClient(
        email=data[CONF_EMAIL],
        password="",
        session=session,
        refresh_token=data["refresh_token"],
    )
    # Utilise le refresh token pour obtenir un id_token valide
    await client.refresh_id_token()
    return f"TigerTag ({data[CONF_EMAIL]})", client.firebase_uid, client.refresh_token


class TigerTagConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Flux de configuration : authentification Email / Mot de passe TigerTag.
    """

    VERSION = 2

    def __init__(self):
        self._data:  dict[str, Any] = {}
        self._title: str = ""

    # ── Étape unique : Email + Password ─────────────────────────────────────
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Redirige directement vers le formulaire email/password."""
        return await self.async_step_password(user_input)

    # ── Étape 2a : Email + Password ─────────────────────────────────────────
    async def async_step_password(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._title, firebase_uid, refresh_token = await _validate_password(
                    self.hass, user_input,
                )
            except TigerTagApiClientAuthenticationError:
                errors["base"] = "invalid_auth"
            except TigerTagApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Erreur validation TigerTag email/password")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL])
                self._abort_if_unique_id_configured()
                self._data.update(user_input)
                self._data[CONF_FIREBASE_UID]  = firebase_uid
                self._data["_refresh_token"]   = refresh_token
                self._data["_auth_mode"]       = "password"
                return self.async_create_entry(title=self._title, data=self._data)

        return self.async_show_form(
            step_id="password",
            data_schema=STEP_PASSWORD_SCHEMA,
            errors=errors,
        )

    # ── Étape 2b : Refresh Token Google ─────────────────────────────────────
    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self._title, firebase_uid, refresh_token = await _validate_token(
                    self.hass, user_input,
                )
            except TigerTagApiClientAuthenticationError:
                errors["base"] = "invalid_token"
            except TigerTagApiClientCommunicationError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Erreur validation TigerTag refresh token")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL])
                self._abort_if_unique_id_configured()
                self._data[CONF_EMAIL]         = user_input[CONF_EMAIL]
                self._data[CONF_FIREBASE_UID]  = firebase_uid
                self._data["_refresh_token"]   = refresh_token
                self._data["_auth_mode"]       = "token"
                return self.async_create_entry(title=self._title, data=self._data)

        return self.async_show_form(
            step_id="token",
            data_schema=STEP_TOKEN_SCHEMA,
            errors=errors,
            description_placeholders={
                "help": (
                    "Ouvre l'app TigerTag Studio Manager → F12 → Application → "
                    "IndexedDB → firebaseLocalStorageDb → firebaseLocalStorage → "
                    "copie la valeur 'refreshToken'."
                )
            },
        )

    # ── Options flow ────────────────────────────────────────────────────────
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return TigerTagOptionsFlow(config_entry)


class TigerTagOptionsFlow(config_entries.OptionsFlow):
    """Modification des lieux de stockage après installation."""

    def __init__(self, config_entry):
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return self.async_create_entry(title="", data={})
