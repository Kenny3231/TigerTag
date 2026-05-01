"""Entités Number (poids modifiable) pour TigerTag."""
import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TigerTagDataUpdateCoordinator
from .helpers import resolve_reference, resolve_spool, spool_display_name

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """
    Configure les entités Number avec détection dynamique des nouvelles bobines.
    Une nouvelle bobine dans l'inventaire crée automatiquement une entité,
    sans redémarrage de Home Assistant.
    """
    coordinator: TigerTagDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_uids: set[str] = set()

    @callback
    def _async_add_new_spools() -> None:
        data = coordinator.data
        if not data or not isinstance(data.get("inventory"), dict):
            return

        new_entities: list[TigerTagSpoolNumber] = []
        for key, spool in data["inventory"].items():
            uid = str(spool.get("uid", key))
            if uid and uid not in known_uids:
                known_uids.add(uid)
                new_entities.append(TigerTagSpoolNumber(coordinator, entry, uid))

        if new_entities:
            _LOGGER.debug("%d nouvelle(s) bobine(s) ajoutée(s).", len(new_entities))
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_spools))
    _async_add_new_spools()


class TigerTagSpoolNumber(CoordinatorEntity[TigerTagDataUpdateCoordinator], NumberEntity):
    """
    Entité Number représentant le poids modifiable d'une bobine de filament.

    Volontairement minimaliste : cette entité ne fait qu'une chose — permettre
    de modifier le poids. Toutes les métadonnées riches (couleur, températures,
    matériau, emplacement…) sont sur l'entité Sensor correspondante.
    """

    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_icon                     = "mdi:weight-gram"
    _attr_native_min_value         = 0
    _attr_native_max_value         = 10_000
    _attr_native_step              = 1

    def __init__(
        self,
        coordinator: TigerTagDataUpdateCoordinator,
        entry: ConfigEntry,
        uid: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._uid   = uid
        self._attr_unique_id = f"tigertag_number_{uid}"
        # entity_id fixe avec préfixe tigertag_ — indépendant du nom du device
        self.entity_id = f"number.tigertag_{uid}"

    # ------------------------------------------------------------------
    # Suppression automatique si la bobine disparaît de l'inventaire
    # ------------------------------------------------------------------

    @callback
    def _handle_coordinator_update(self) -> None:
        data         = self.coordinator.data or {}
        inventory    = data.get("inventory", {})
        current_uids = {str(v.get("uid", k)) for k, v in inventory.items()}

        if self._uid not in current_uids:
            _LOGGER.debug("Bobine %s absente de l'inventaire — suppression du number.", self._uid)
            entity_registry = er.async_get(self.hass)
            if entity_registry.async_get(self.entity_id):
                entity_registry.async_remove(self.entity_id)
            else:
                self.hass.async_create_task(self.async_remove(force_remove=True))
            return

        super()._handle_coordinator_update()

    # ------------------------------------------------------------------
    # Device — rattache toutes les bobines au même appareil TigerTag
    # ------------------------------------------------------------------

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="TigerTag Studio",
            manufacturer="TigerTag Project",
            model="Inventory Manager",
            sw_version="1.1",
        )

    # ------------------------------------------------------------------
    # Propriétés
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Nom complet : [Marque] [Série] [Couleur] [5 derniers chars UID] — Poids"""
        spool = resolve_spool(self.coordinator, self._uid) or {}
        brand = resolve_reference(self.coordinator, "brand", spool.get("id_brand"))
        return spool_display_name(spool, brand, self._uid)

    @property
    def native_value(self) -> float | None:
        spool = resolve_spool(self.coordinator, self._uid)
        if not spool:
            return None
        raw = spool.get("weight_available") or spool.get("weight") or spool.get("measure_gr")
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Appelé quand l'utilisateur modifie le poids depuis l'interface HA."""
        spool            = resolve_spool(self.coordinator, self._uid) or {}
        container_weight = int(spool.get("container_weight") or 0)
        twin_uid         = spool.get("twin_tag_uid") or None

        await self.coordinator.client.set_weight_with_twin(
            uid=self._uid,
            weight=int(value),
            container_weight=container_weight,
            twin_uid=twin_uid,
        )
        await self.coordinator.async_request_refresh()
