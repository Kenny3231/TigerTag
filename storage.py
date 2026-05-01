"""Persistance locale pour TigerTag : références, emplacements AMS, lieux, tares custom."""
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
    - Lieux de stockage {uid: "Garage"}
    - Tares custom      {uid: 250}  (override du container_weight officiel)
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._ref_store  = Store(hass, _STORE_VERSION, f"{DOMAIN}_references.json")
        self._loc_store  = Store(hass, _STORE_VERSION, f"{DOMAIN}_locations.json")
        self._room_store = Store(hass, _STORE_VERSION, f"{DOMAIN}_rooms.json")
        self._tare_store = Store(hass, _STORE_VERSION, f"{DOMAIN}_tares.json")

        self._references: dict[str, Any] = {}
        self._locations:  dict[str, str] = {}   # uid → entity_id tray Bambu
        self._rooms:      dict[str, str] = {}   # uid → lieu de stockage
        self._tares:      dict[str, int] = {}   # uid → tare en grammes
        self._references_fetched_at: datetime | None = None

    # ── Chargement initial ──────────────────────────────────────────────────
    async def async_load(self) -> None:
        await self._load_refs()
        await self._load_locations()
        await self._load_rooms()
        await self._load_tares()

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

    async def _load_rooms(self) -> None:
        d = await self._room_store.async_load()
        if isinstance(d, dict):
            self._rooms = d

    async def _load_tares(self) -> None:
        d = await self._tare_store.async_load()
        if isinstance(d, dict):
            self._tares = d

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

    # ── Emplacements AMS (entity_id tray Bambu) ─────────────────────────────
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

    # ── Lieux de stockage (pièce) ────────────────────────────────────────────
    @property
    def rooms(self) -> dict[str, str]:
        return self._rooms

    def get_room(self, uid: str) -> str | None:
        return self._rooms.get(uid)

    async def async_set_room(self, uid: str, room: str | None) -> None:
        if room is None:
            self._rooms.pop(uid, None)
        else:
            self._rooms[uid] = room
        await self._room_store.async_save(self._rooms)

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
