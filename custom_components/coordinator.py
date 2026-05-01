"""DataUpdateCoordinator pour TigerTag."""
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import TigerTagApiClient, TigerTagApiClientError
from .const import CONF_LOCATIONS, DEFAULT_LOCATIONS, DOMAIN, UPDATE_INTERVAL
from .storage import TigerTagStorage

_LOGGER = logging.getLogger(__name__)


class TigerTagDataUpdateCoordinator(DataUpdateCoordinator):
    """
    Coordinator central — expose coordinator.data à toutes les entités :
    {
        "inventory":  { uid: spool_dict },
        "references": { "brand": [...], ... },
        "locations":  { uid: "sensor.p2s_ams_1_emplacement_1" },
        "rooms":      { uid: "Garage" },
        "tares":      { uid: 250 },
        "config_locations": ["Garage","Salon","Bureau"],  # lieux configurés
    }
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client: TigerTagApiClient,
        entry,
    ) -> None:
        self.client  = client
        self.storage = TigerTagStorage(hass)
        self._entry  = entry

        super().__init__(
            hass, _LOGGER, name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    # ── Init avant premier refresh ──────────────────────────────────────────
    async def async_setup(self) -> None:
        await self.storage.async_load()

    # ── Raccourcis storage ──────────────────────────────────────────────────
    def get_location(self, uid: str) -> str | None:
        return self.storage.get_location(uid)

    async def async_set_location(self, uid: str, entity_id: str | None) -> None:
        await self.storage.async_set_location(uid, entity_id)

    def get_room(self, uid: str) -> str | None:
        return self.storage.get_room(uid)

    async def async_set_room(self, uid: str, room: str | None) -> None:
        await self.storage.async_set_room(uid, room)

    def get_tare(self, uid: str) -> int | None:
        return self.storage.get_tare(uid)

    async def async_set_tare(self, uid: str, tare_g: int | None) -> None:
        await self.storage.async_set_tare(uid, tare_g)

    def get_config_locations(self) -> list[str]:
        return self._entry.data.get(CONF_LOCATIONS, DEFAULT_LOCATIONS)

    # ── Boucle principale ───────────────────────────────────────────────────
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            await self._refresh_references_if_needed()
            inventory = await self.client.get_inventory()
            return {
                "inventory":        inventory,
                "references":       self.storage.references,
                "locations":        self.storage.locations,
                "rooms":            self.storage.rooms,
                "tares":            self.storage.tares,
                "config_locations": self.get_config_locations(),
            }
        except TigerTagApiClientError as exc:
            raise UpdateFailed(f"Mise à jour TigerTag échouée : {exc}") from exc

    async def _refresh_references_if_needed(self) -> None:
        if not self.storage.references_are_stale():
            return
        try:
            refs = await self.client.get_references()
            await self.storage.async_save_references(refs)
        except Exception as err:
            _LOGGER.warning("Références non mises à jour (cache conservé) : %s", err)
