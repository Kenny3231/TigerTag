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
    vol.Required("uid"):                   cv.string,
    vol.Required("tray_entity_id"):        cv.string,
    vol.Optional("tray_info_idx"):         cv.string,   # override du profil filament
    vol.Optional("profile_name"):          cv.string,   # pour le log uniquement
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

        # Si la bobine était dans un AMS et qu'on la replace ailleurs
        # → libérer le tray AMS et sauvegarder le nouveau lieu comme "précédent"
        current_ams = coordinator.get_location(uid)
        if current_ams and room != coordinator.get_room(uid):
            # On efface l'ams_location car la bobine quitte physiquement le tray
            await coordinator.async_set_location(uid, None)

        await coordinator.async_set_room(uid, room)
        coordinator.async_set_updated_data({
            **(coordinator.data or {}),
            "locations": coordinator.storage.locations,
            "rooms":     coordinator.storage.rooms,
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


def _extract_printer_name(entity_id: str) -> str:
    """Extrait le nom de l'imprimante depuis un entity_id Bambu Lab.
    Ex: 'sensor.p2s_ams_1_emplacement_1' → 'P2S'
    """
    import re
    m = re.match(r"^sensor\.([^_]+(?:_[^_]+)*?)(?:_ams_|_external)", entity_id, re.IGNORECASE)
    if m:
        return m.group(1).replace("_", " ").upper()
    return entity_id.split(".")[1].split("_")[0].upper()


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

        # ── 1. Chercher si ce tray a déjà une bobine TigerTag ──────────────
        inventory = (coordinator.data or {}).get("inventory", {})
        old_uid_in_tray = None
        for key, sp in inventory.items():
            sp_uid = str(sp.get("uid", key))
            if coordinator.get_location(sp_uid) == tray_entity_id and sp_uid != uid:
                old_uid_in_tray = sp_uid
                break

        # ── 2. Remettre l'ancienne bobine à son lieu précédent ─────────────
        if old_uid_in_tray:
            prev = coordinator.get_prev_room(old_uid_in_tray)
            _LOGGER.info("Ancienne bobine %s dans ce tray → retour lieu '%s'", old_uid_in_tray, prev)
            await coordinator.async_set_location(old_uid_in_tray, None)
            await coordinator.async_set_room(old_uid_in_tray, prev)
            await coordinator.async_set_prev_room(old_uid_in_tray, None)

        # ── 3. Sauvegarder le lieu actuel de la nouvelle bobine ────────────
        current_room = coordinator.get_room(uid)
        printer_name = _extract_printer_name(tray_entity_id)
        # On sauvegarde le lieu précédent seulement si ce n'est pas déjà un nom d'imprimante
        if current_room and current_room != printer_name:
            await coordinator.async_set_prev_room(uid, current_room)

        # ── 4. Envoi vers Bambu Lab ─────────────────────────────────────────
        payload = build_ams_payload(
            coordinator=coordinator, spool_data=spool, ams_id=0, tray_id=0,
        )
        p = payload["print"]
        # Override du profil si fourni par la carte JS
        if call.data.get("tray_info_idx"):
            p["tray_info_idx"] = call.data["tray_info_idx"]
            _LOGGER.info("Profil override : %s (%s)", call.data["tray_info_idx"], call.data.get("profile_name", ""))
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

        # ── 5. Persister : lieu AMS + nom imprimante comme lieu de stockage ─
        await coordinator.async_set_location(uid, tray_entity_id)
        await coordinator.async_set_room(uid, printer_name)

        # ── 6. Sauvegarder le profil filament choisi ──────────────────────────
        tray_info_idx = call.data.get("tray_info_idx")
        if tray_info_idx:
            await coordinator.async_set_spool_profile(uid, tray_info_idx)
            _LOGGER.info("Profil filament sauvegardé pour bobine %s : %s", uid, tray_info_idx)

        # Mise à jour immédiate des entités
        coordinator.async_set_updated_data({
            **(coordinator.data or {}),
            "locations": coordinator.storage.locations,
            "rooms":     coordinator.storage.rooms,
        })
        _LOGGER.info("Bobine %s → tray %s, lieu '%s'", uid, tray_entity_id, printer_name)

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
        DOMAIN, "fetch_bambu_profiles",
        _make_fetch_profiles_handler(hass, eid),
        schema=_FETCH_PROFILES_SCHEMA,
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
                SERVICE_BAMBU_AMS, SERVICE_REFRESH,
                "set_spool_tare", "fetch_bambu_profiles",
            ):
                hass.services.async_remove(DOMAIN, svc)
    return unload_ok


# ── Schéma fetch_bambu_profiles ──────────────────────────────────────────────
_FETCH_PROFILES_SCHEMA = vol.Schema({
    vol.Required("device_id"): cv.string,
    vol.Required("uid"):       cv.string,
})

def _score_profile(profile: dict, material: str, series: str, brand: str = "", bambu_id: str = "") -> int:
    """
    Score un profil Bambu par rapport à la bobine TigerTag.
    - Retourne -9999 si le type ne correspond pas à la bobine courante
    - Générique en tête si la marque TigerTag n'est pas dans Bambu
    - Bonus si la série correspond (ex: Silk, Galaxy...)
    """
    name   = (profile.get("name","") or "").lower()
    ptype  = (profile.get("type","") or profile.get("filament_type","") or "").lower()
    vendor = (profile.get("vendor","") or profile.get("filament_vendor","") or "").lower()
    mat    = (material or "").lower()
    ser    = (series or "").lower()
    br     = (brand or "").lower()

    # Filtre par type — on extrait le type de base du matériau TigerTag
    # car TigerTag peut retourner "PLA Silk", "PLA Galaxy" au lieu de "PLA"
    # On prend le premier mot comme type de base (ex: "PLA Silk" → "PLA")
    mat_base = mat.strip().lower().split()[0] if mat.strip() else ""
    ptype_clean = ptype.strip().lower()
    if mat_base and ptype_clean and ptype_clean != mat_base:
        return -9999

    score = 0

    # Match type de base
    if mat and ptype == mat:
        score += 100

    # Vendors reconnus dans la base Bambu (liste extensible)
    KNOWN_VENDORS = {"esun", "polymake"}

    # Logique vendor — ordre de priorité :
    # 1. Même marque que TigerTag → meilleur match possible
    # 2. Generic → meilleur fallback universel pour filaments tiers
    # 3. Bambu Lab → profil spécifique mais pas idéal pour filaments tiers
    # 4. Vendor reconnu (eSun, Polymake) → bon profil mais marque différente
    # 5. Autre → pénalité
    if vendor:
        vendor_clean = vendor.strip().lower()
        br_clean     = br.strip().lower()
        if br_clean and (br_clean in vendor_clean or vendor_clean in br_clean):
            score += 80   # même marque = meilleur match
        elif "generic" in vendor_clean:
            score += 40   # générique = priorité sur Bambu pour filaments tiers
        elif "bambu" in vendor_clean:
            score += 20   # Bambu spécifique = ok mais après générique
        elif any(k in vendor_clean for k in KNOWN_VENDORS):
            score += 15   # autre vendor reconnu
        else:
            score -= 10   # vendor inconnu

    # Match série — bonus réduit si le vendor ne correspond pas à la marque TigerTag
    # Évite que "Bambu PLA Galaxy" passe devant "Generic PLA" pour du Rosa3D Galaxy
    if ser:
        vendor_matches = bool(br and vendor and (br in vendor or vendor in br))
        serie_bonus = 40 if vendor_matches else 15
        import re
        for word in re.split(r'[\s\-_]+', ser.lower()):
            if len(word) > 3 and word in name:
                score += serie_bonus

    # GXX99 = profil générique universel Bambu (ex: GFL99 = PLA générique de base)
    # C'est le meilleur fallback pour les filaments tiers non répertoriés
    # On lui donne un bonus modéré pour qu'il passe devant les profils spécifiques
    # quand il n'y a pas de meilleur match
    idx = (profile.get("tray_info_idx","") or "").upper()
    if idx.endswith("99"):
        score += 5  # léger bonus : fallback universel préféré aux profils spécifiques non pertinents

    return score




def _make_fetch_profiles_handler(hass: HomeAssistant, entry_id: str):
    """Score et stocke les profils filament Bambu pour une bobine TigerTag."""
    async def handle(call) -> None:
        import json as _json
        coordinator = _get_coordinator(hass, entry_id)
        if not coordinator:
            return
        device_id = call.data["device_id"]
        uid       = call.data["uid"]
        spool    = resolve_spool(coordinator, uid)
        material = ""
        series   = ""
        if spool:
            from .helpers import resolve_reference
            material = resolve_reference(coordinator, "material", spool.get("id_material", ""))
            series   = spool.get("series", "") or ""
        # Récupérer les profils via get_filament_data
        profiles = []
        try:
            resp = await hass.services.async_call(
                "bambu_lab", "get_filament_data",
                {"device_id": device_id},
                return_response=True, blocking=True,
            )
            if resp:
                raw = resp if isinstance(resp, (list, dict)) else _json.loads(str(resp))
                if isinstance(raw, dict) and raw:
                    profiles = [
                        {
                            "tray_info_idx":  idx,
                            "name":           p.get("name", idx),
                            "type":           p.get("filament_type", ""),
                            "nozzle_temp_min": str(p.get("nozzle_temperature_range_low", "")),
                            "nozzle_temp_max": str(p.get("nozzle_temperature_range_high", "")),
                            "bed_temp":        str(p.get("bed_temperature", "")),
                            "drying_temp":     str(p.get("drying_temp", "")),
                            "drying_time":     str(p.get("drying_time", "")),
                            "vendor":          p.get("filament_vendor", ""),
                        }
                        for idx, p in raw.items()
                    ]
                elif isinstance(raw, list) and raw:
                    profiles = raw
                _LOGGER.info("get_filament_data : %d profils chargés", len(profiles))
        except Exception as err:
            _LOGGER.error("get_filament_data échoué : %s", err)

        if not profiles:
            _LOGGER.warning("Aucun profil filament disponible pour device_id=%s", device_id)
            return
        # Récupérer la marque et le bambuID de la bobine
        brand    = ""
        bambu_id = ""
        if spool:
            from .helpers import resolve_reference
            brand = resolve_reference(coordinator, "brand", spool.get("id_brand", ""))
            # bambuID depuis les métadonnées du matériau TigerTag
            id_material = spool.get("id_material", "")
            if id_material:
                refs = (coordinator.data or {}).get("references", {}).get("material") or []
                if isinstance(refs, list):
                    mat_entry = next(
                        (m for m in refs if str(m.get("id","")) == str(id_material)),
                        None
                    )
                    if mat_entry:
                        bambu_id = (mat_entry.get("metadata") or {}).get("bambuID", "") or ""
                        if bambu_id:
                            _LOGGER.info("BambuID TigerTag pour %s : %s", material, bambu_id)

        # Scorer
        raw_scored = [
            {**p, "_score": _score_profile(p, material, series, brand, bambu_id)}
            for p in profiles
        ]

        # Filtrer les mauvais types (score == -9999)
        filtered = [p for p in raw_scored if p["_score"] > -9999]

        # Dédupliquer par tray_info_idx — garder le meilleur score
        seen_idx: dict = {}
        for p in filtered:
            idx = p.get("tray_info_idx", "")
            if idx not in seen_idx or p["_score"] > seen_idx[idx]["_score"]:
                seen_idx[idx] = p
        deduped = sorted(seen_idx.values(), key=lambda x: -x["_score"])

        _LOGGER.info(
            "Profils %s/%s (brand=%s) : %d après filtre/dédup, top 3 : %s",
            material, series, brand, len(deduped),
            [p.get("name") for p in deduped[:3]],
        )

        current = dict(coordinator.data or {})
        bp = dict(current.get("bambu_profiles", {}))
        bp[device_id] = {"uid": uid, "profiles": deduped}
        current["bambu_profiles"] = bp
        coordinator.async_set_updated_data(current)
    return handle
