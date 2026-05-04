"""Persistance locale pour TigerTag : références, emplacements AMS, tares, profils, tokens."""
import logging
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, REFERENCES_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)
_STORE_VERSION = 1


class TigerTagStorage:
    """
    Gère toute la persistance locale :
    - Références (brand, material…) avec cache 24h
    - Emplacements AMS  {uid: "sensor.p2s_ams_1_emplacement_1"}
    - Tares custom      {uid: 250}
    - Profils filament  {uid: "GFL96"}
    - Tokens Firebase   {refresh_token, id_token}
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._ref_store     = Store(hass, _STORE_VERSION, f"{DOMAIN}_references.json")
        self._loc_store     = Store(hass, _STORE_VERSION, f"{DOMAIN}_locations.json")
        self._tare_store    = Store(hass, _STORE_VERSION, f"{DOMAIN}_tares.json")
        self._profile_store = Store(hass, _STORE_VERSION, f"{DOMAIN}_spool_profiles.json")
        self._token_store   = Store(hass, _STORE_VERSION, f"{DOMAIN}_firebase_tokens.json")

        self._references:     dict[str, Any] = {}
        self._locations:      dict[str, str] = {}   # uid → entity_id tray Bambu
        self._tares:          dict[str, int] = {}   # uid → tare en grammes
        self._spool_profiles: dict[str, str] = {}   # uid → tray_info_idx
        self._firebase_tokens: dict[str, str] = {}  # refresh_token, id_token
        self._references_fetched_at: datetime | None = None

    async def async_load(self) -> None:
        await self._load_refs()
        await self._load_locations()
        await self._load_tares()
        await self._load_spool_profiles()
        await self._load_firebase_tokens()

    async def _load_refs(self) -> None:
        d = await self._ref_store.async_load()
        if isinstance(d, dict):
            self._references = d.get("data") or {}
            ts = d.get("updated_at")
            if ts:
                try:
                    self._references_fetched_at = datetime.fromisoformat(ts)
                except ValueError:
                    pass

    async def _load_locations(self) -> None:
        d = await self._loc_store.async_load()
        if isinstance(d, dict):
            self._locations = d

    async def _load_tares(self) -> None:
        d = await self._tare_store.async_load()
        if isinstance(d, dict):
            self._tares = d

    async def _load_spool_profiles(self) -> None:
        d = await self._profile_store.async_load()
        if isinstance(d, dict):
            self._spool_profiles = d

    async def _load_firebase_tokens(self) -> None:
        d = await self._token_store.async_load()
        if isinstance(d, dict):
            self._firebase_tokens = d

    # ── Références ──────────────────────────────────────────────────────────
    @property
    def references(self) -> dict[str, Any]:
        return self._references

    def references_are_stale(self) -> bool:
        if not self._references or self._references_fetched_at is None:
            return True
        return (datetime.now() - self._references_fetched_at).total_seconds() > REFERENCES_UPDATE_INTERVAL

    async def async_save_references(self, refs: dict[str, Any]) -> None:
        self._references            = refs
        self._references_fetched_at = datetime.now()
        await self._ref_store.async_save({
            "data": refs, "updated_at": self._references_fetched_at.isoformat()
        })

    # ── Emplacements AMS ─────────────────────────────────────────────────────
    @property
    def locations(self) -> dict[str, str]:
        return self._locations

    def get_location(self, uid: str) -> str | None:
        return self._locations.get(uid)

    async def async_set_location(self, uid: str, entity_id: str | None) -> None:
        if entity_id is None:
            self._locations.pop(uid, None)
        else:
            self._locations[uid] = entity_id
        await self._loc_store.async_save(self._locations)

    # ── Tares custom ─────────────────────────────────────────────────────────
    @property
    def tares(self) -> dict[str, int]:
        return self._tares

    def get_tare(self, uid: str) -> int | None:
        return self._tares.get(uid)

    async def async_set_tare(self, uid: str, tare_g: int | None) -> None:
        if tare_g is None:
            self._tares.pop(uid, None)
        else:
            self._tares[uid] = tare_g
        await self._tare_store.async_save(self._tares)

    # ── Profils filament ──────────────────────────────────────────────────────
    def get_spool_profile(self, uid: str) -> str | None:
        return self._spool_profiles.get(uid)

    async def async_set_spool_profile(self, uid: str, tray_info_idx: str | None) -> None:
        if tray_info_idx is None:
            self._spool_profiles.pop(uid, None)
        else:
            self._spool_profiles[uid] = tray_info_idx
        await self._profile_store.async_save(self._spool_profiles)

    # ── Firebase tokens ───────────────────────────────────────────────────────
    def get_refresh_token(self) -> str:
        return self._firebase_tokens.get("refresh_token", "")

    def get_id_token(self) -> str:
        return self._firebase_tokens.get("id_token", "")

    async def async_save_tokens(self, refresh_token: str, id_token: str = "") -> None:
        self._firebase_tokens = {"refresh_token": refresh_token, "id_token": id_token}
        await self._token_store.async_save(self._firebase_tokens)
