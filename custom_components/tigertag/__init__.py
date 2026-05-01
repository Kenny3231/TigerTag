"""Initialisation de l'intégration TigerTag."""
import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import entity_registry as er
from homeassistant.components.http import StaticPathConfig

from .api import TigerTagApiClient
from .bambu import build_ams_payload
from .const import (
    CONF_API_KEY, CONF_EMAIL, DOMAIN,
    SERVICE_BAMBU_AMS, SERVICE_REFRESH, SERVICE_SET_ROOM, SERVICE_UPDATE_WEIGHT,
)
from .coordinator import TigerTagDataUpdateCoordinator
from .helpers import resolve_spool

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.NUMBER, Platform.SENSOR]

# URL sous laquelle la carte Lovelace est servie par HA
# Le fichier tigertag-card.js est dans custom_components/tigertag/
_CARD_URL  = "/local/tigertag-card.js"
_CARD_PATH = "tigertag-card.js"  # nom du fichier dans le dossier de l'intégration

# ── Schémas de validation ────────────────────────────────────────────────────

_UPDATE_WEIGHT_SCHEMA = vol.Schema({
    vol.Required("uid"):    cv.string,
    vol.Required("weight"): vol.All(vol.Coerce(int), vol.Range(min=0, max=99_999)),
    vol.Optional("container_weight", default=0): vol.All(vol.Coerce(int), vol.Range(min=0)),
})

_SET_ROOM_SCHEMA = vol.Schema({
    vol.Required("uid"):  cv.string,
    vol.Required("room"): vol.Any(cv.string, None),
})

_SET_TARE_SCHEMA = vol.Schema({
    vol.Required("uid"):  cv.string,
    vol.Required("tare"): vol.All(vol.Coerce(int), vol.Range(min=0, max=9999)),
})

_BAMBU_AMS_SCHEMA = vol.Schema({
    vol.Required("uid"):            cv.string,
    vol.Required("tray_entity_id"): cv.string,
})

# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_coordinator(hass: HomeAssistant, entry_id: str) -> TigerTagDataUpdateCoordinator | None:
    return hass.data.get(DOMAIN, {}).get(entry_id)

# ── Handlers de services ─────────────────────────────────────────────────────

def _make_update_weight_handler(hass: HomeAssistant, entry_id: str):
    async def handle(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, entry_id)
        if not coordinator:
            return
        uid              = call.data["uid"]
        weight           = call.data["weight"]
        container_weight = call.data.get("container_weight", 0)
        spool    = resolve_spool(coordinator, uid)
        twin_uid = spool.get("twin_tag_uid") if spool else None
        try:
            await coordinator.client.set_weight_with_twin(
                uid=uid, weight=weight,
                container_weight=container_weight,
                twin_uid=twin_uid,
            )
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Erreur mise à jour poids bobine %s : %s", uid, err)
    return handle


def _make_set_room_handler(hass: HomeAssistant, entry_id: str):
    async def handle(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, entry_id)
        if not coordinator:
            return
        uid  = call.data["uid"]
        room = call.data.get("room") or None
        await coordinator.async_set_room(uid, room)
        coordinator.async_set_updated_data({
            **(coordinator.data or {}),
            "rooms": coordinator.storage.rooms,
        })
    return handle


def _make_set_tare_handler(hass: HomeAssistant, entry_id: str):
    async def handle(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, entry_id)
        if not coordinator:
            _LOGGER.error("Coordinator TigerTag introuvable pour set_spool_tare")
            return
        uid    = call.data["uid"]
        tare_g = call.data["tare"]
        _LOGGER.debug("Tare custom bobine %s → %d g", uid, tare_g)
        await coordinator.async_set_tare(uid, tare_g)
        # Mise à jour immédiate des entités sans attendre le prochain cycle
        coordinator.async_set_updated_data({
            **(coordinator.data or {}),
            "tares": coordinator.storage.tares,
        })
    return handle


def _make_bambu_ams_handler(hass: HomeAssistant, entry_id: str):
    async def handle(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, entry_id)
        if not coordinator:
            return
        uid            = call.data["uid"]
        tray_entity_id = call.data["tray_entity_id"]
        spool = resolve_spool(coordinator, uid)
        if not spool:
            _LOGGER.error("Bobine UID '%s' introuvable dans l'inventaire.", uid)
            return
        payload = build_ams_payload(
            coordinator=coordinator, spool_data=spool, ams_id=0, tray_id=0,
        )
        p = payload["print"]
        _LOGGER.info(
            "Envoi filament → %s : %s %s %d–%d°C",
            tray_entity_id, p["tray_type"], p["tray_color"],
            p["nozzle_temp_min"], p["nozzle_temp_max"],
        )
        try:
            await hass.services.async_call(
                "bambu_lab", "set_filament",
                {
                    "tray_info_idx":   p["tray_info_idx"],
                    "tray_color":      p["tray_color"],
                    "tray_type":       p["tray_type"],
                    "nozzle_temp_min": p["nozzle_temp_min"],
                    "nozzle_temp_max": p["nozzle_temp_max"],
                },
                target={"entity_id": tray_entity_id},
            )
        except Exception as err:
            _LOGGER.error("Erreur envoi Bambu Lab : %s", err)
            return
        await coordinator.async_set_location(uid, tray_entity_id)
    return handle


def _make_refresh_handler(hass: HomeAssistant, entry_id: str):
    async def handle(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, entry_id)
        if coordinator:
            await coordinator.async_request_refresh()
    return handle

# ── Enregistrement de la carte Lovelace ────────────────────────────────────────

async def _async_register_card(hass: HomeAssistant) -> None:
    """
    Enregistre tigertag-card.js comme ressource statique et Lovelace.
    Le fichier est servi depuis custom_components/tigertag/tigertag-card.js
    → accessible à l'URL /tigertag-card/tigertag-card.js
    Idempotent : appelé à chaque démarrage, ne re-crée pas si déjà présent.
    """
    import os
    card_file = os.path.join(
        hass.config.path("custom_components", DOMAIN), _CARD_PATH
    )

    if not os.path.isfile(card_file):
        _LOGGER.warning(
            "Fichier carte TigerTag introuvable : %s — la carte ne sera pas enregistrée.",
            card_file,
        )
        return

    # Enregistrement du chemin statique (sert le fichier JS)
    try:
        await hass.http.async_register_static_paths([
            StaticPathConfig(_CARD_URL, card_file, False)
        ])
        _LOGGER.debug("Chemin statique enregistré : %s → %s", _CARD_URL, card_file)
    except Exception as err:
        _LOGGER.debug("Chemin statique déjà enregistré ou erreur : %s", err)

    # Enregistrement automatique comme ressource Lovelace (module JS)
    # Uniquement possible en mode UI (storage mode).
    # En mode YAML, ResourceYAMLCollection ne supporte pas async_create_item —
    # l'utilisateur doit ajouter la ressource manuellement dans configuration.yaml.
    if "lovelace" not in hass.data:
        _LOGGER.info(
            "TigerTag Card disponible à : %s — "
            "ajouter dans configuration.yaml : "
            "lovelace: resources: - url: %s type: module",
            _CARD_URL, _CARD_URL,
        )
        return

    try:
        resources = hass.data["lovelace"].resources
        # Mode YAML : ResourceYAMLCollection ne supporte pas async_create_item
        if not hasattr(resources, "async_create_item"):
            _LOGGER.info(
                "Lovelace en mode YAML — ajouter dans configuration.yaml : "
                "lovelace: resources: - url: %s type: module",
                _CARD_URL,
            )
            return

        if not any(res.get("url") == _CARD_URL for res in resources.async_items()):
            await resources.async_create_item({"res_type": "module", "url": _CARD_URL})
            _LOGGER.info("Ressource Lovelace TigerTag Card enregistrée : %s", _CARD_URL)
        else:
            _LOGGER.debug("Ressource Lovelace déjà enregistrée : %s", _CARD_URL)

    except Exception as err:
        _LOGGER.info(
            "Auto-enregistrement Lovelace impossible (%s) — "
            "ajouter dans configuration.yaml : "
            "lovelace: resources: - url: %s type: module",
            err, _CARD_URL,
        )


# ── Nettoyage du registre des entités orphelines ────────────────────────────

async def _async_cleanup_orphan_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: TigerTagDataUpdateCoordinator,
) -> None:
    """
    Supprime du registre HA les entités TigerTag dont la bobine
    n'existe plus dans l'inventaire TigerTag.
    Appelé après le premier refresh, avant le chargement des plateformes.
    """
    inventory = (coordinator.data or {}).get("inventory", {})
    current_uids = {str(v.get("uid", k)) for k, v in inventory.items()}

    entity_registry = er.async_get(hass)
    entries_to_remove = [
        e for e in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if e.domain in ("sensor", "number")
        and e.unique_id.split("_", 2)[-1] not in current_uids
    ]

    for orphan in entries_to_remove:
        _LOGGER.info(
            "Suppression entité orpheline : %s (bobine absente de l'inventaire)",
            orphan.entity_id,
        )
        entity_registry.async_remove(orphan.entity_id)


# ── Setup / Unload ────────────────────────────────────────────────────────────

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    # Enregistrement de la carte Lovelace (une seule fois pour toutes les entrées)
    if not hass.data[DOMAIN].get("_card_registered"):
        await _async_register_card(hass)
        hass.data[DOMAIN]["_card_registered"] = True

    session = async_get_clientsession(hass)
    client  = TigerTagApiClient(
        email=entry.data[CONF_EMAIL],
        api_key=entry.data[CONF_API_KEY],
        session=session,
    )

    coordinator = TigerTagDataUpdateCoordinator(hass, client, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Nettoyage des entités orphelines avant le chargement des plateformes
    await _async_cleanup_orphan_entities(hass, entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    eid = entry.entry_id

    # Enregistrement de tous les services
    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_WEIGHT,
        _make_update_weight_handler(hass, eid),
        schema=_UPDATE_WEIGHT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_ROOM,
        _make_set_room_handler(hass, eid),
        schema=_SET_ROOM_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, "set_spool_tare",
        _make_set_tare_handler(hass, eid),
        schema=_SET_TARE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_BAMBU_AMS,
        _make_bambu_ams_handler(hass, eid),
        schema=_BAMBU_AMS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH,
        _make_refresh_handler(hass, eid),
    )

    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))
    return True


async def _async_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Rechargement si la config change (lieux modifiés via options flow)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            for svc in (
                SERVICE_UPDATE_WEIGHT, SERVICE_SET_ROOM,
                SERVICE_BAMBU_AMS, SERVICE_REFRESH, "set_spool_tare",
            ):
                hass.services.async_remove(DOMAIN, svc)
    return unload_ok
