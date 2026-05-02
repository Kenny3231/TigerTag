"""Entités Sensor TigerTag — avec room, ams_location, tare custom."""
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfMass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TigerTagDataUpdateCoordinator
from .helpers import clean_value, resolve_reference, resolve_spool, spool_color_hex, spool_display_name

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: TigerTagDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    known_uids: set[str] = set()

    # Sensor de statistiques globales (unique par entrée)
    async_add_entities([TigerTagStatsSensor(coordinator, entry)])

    @callback
    def _add_new() -> None:
        data = coordinator.data
        if not data or not isinstance(data.get("inventory"), dict):
            return
        new = []
        for key, spool in data["inventory"].items():
            uid = str(spool.get("uid", key))
            if uid and uid not in known_uids:
                known_uids.add(uid)
                new.append(TigerTagSpoolSensor(coordinator, entry, uid))
        if new:
            async_add_entities(new)

    entry.async_on_unload(coordinator.async_add_listener(_add_new))
    _add_new()


class TigerTagSpoolSensor(CoordinatorEntity[TigerTagDataUpdateCoordinator], SensorEntity):
    # has_entity_name=False : l'entity_id est basé sur unique_id uniquement
    # indépendant du nom du device → stable même si l'utilisateur renomme l'appareil
    _attr_has_entity_name            = False
    _attr_state_class                = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_icon                       = "mdi:printer-3d-nozzle"

    def __init__(self, coordinator, entry, uid):
        super().__init__(coordinator)
        self._entry = entry
        self._uid   = uid
        self._attr_unique_id         = f"tigertag_sensor_{uid}"
        # Forcer l'entity_id à toujours commencer par "tigertag_"
        # indépendamment du nom donné à l'appareil dans HA
        self.entity_id = f"sensor.tigertag_{uid}"

    @callback
    def _handle_coordinator_update(self) -> None:
        data      = self.coordinator.data or {}
        inventory = data.get("inventory", {})
        current   = {str(v.get("uid", k)) for k, v in inventory.items()}
        if self._uid not in current:
            _LOGGER.debug("Bobine %s absente de l'inventaire — suppression du sensor.", self._uid)
            # Supprimer du registre ET de l'état courant
            entity_registry = er.async_get(self.hass)
            if entity_registry.async_get(self.entity_id):
                entity_registry.async_remove(self.entity_id)
            else:
                self.hass.async_create_task(self.async_remove(force_remove=True))
            return
        super()._handle_coordinator_update()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="TigerTag Studio", manufacturer="TigerTag Project",
            model="Inventory Manager", sw_version="2.0",
            configuration_url="https://app.tigertag.io",
        )

    @property
    def _spool(self) -> dict[str, Any]:
        return resolve_spool(self.coordinator, self._uid) or {}

    def _ref(self, ref_type: str, item_id: Any) -> str:
        return resolve_reference(self.coordinator, ref_type, item_id)

    @property
    def name(self) -> str:
        brand = self._ref("brand", self._spool.get("id_brand"))
        return spool_display_name(self._spool, brand, self._uid)

    @property
    def native_value(self) -> float | None:
        d   = self._spool
        raw = d.get("weight_available") or d.get("weight") or d.get("measure_gr")
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def entity_picture(self) -> str | None:
        """
        - TigerTag+ : URL de l'image produit officielle
        - TigerTag classique : SVG inline coloré généré depuis les composantes RGB
        """
        d       = self._spool
        img_url = d.get("url_img")

        # Image officielle disponible → on l'utilise
        if img_url and img_url not in ("", "--"):
            return img_url

        # Pas d'image → SVG bobine coloré (style Spoolman)
        # On utilise une data URL SVG directe (pas de base64 nécessaire pour SVG)
        try:
            r = int(d.get("color_r", 0))
            g = int(d.get("color_g", 0))
            b = int(d.get("color_b", 0))
        except (TypeError, ValueError):
            r = g = b = 128

        c = f"#{r:02x}{g:02x}{b:02x}"

        # SVG inline avec la couleur injectée — encodage URL simple
        # SVG carré (viewBox 500x500) avec la bobine centrée et avec marges
        # On ajoute un fond transparent et on centre la bobine originale
        # en la scalant pour qu'elle tienne dans un carré avec padding
        # viewBox rogné sur la bobine + preserveAspectRatio pour centrer dans le carré
        cc = c.replace("#", "%23")
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-140 -60 515 620" preserveAspectRatio="xMidYMid meet">'
            f'<path fill="%23343434" d="M0-63C35-63 63-35 63 0 63 35 35 63 0 63-35 63-63 35-63 0-63-35-35-63 0-63z" transform="matrix(.588,0,0,3.948,197,250)"/>'
            f'<path fill="{cc}" d="M0-63C35-63 63-35 63 0 63 35 35 63 0 63-35 63-63 35-63 0-63-35-35-63 0-63z" transform="matrix(.382,0,0,3.462,197,250)"/>'
            f'<path fill="{cc}" d="M-38-65H38V65H-38z" transform="matrix(2.074,0,0,3.358,117,250)"/>'
            f'<path fill="%23343434" d="M0-63C35-63 63-35 63 0 63 35 35 63 0 63-35 63-63 35-63 0-63-35-35-63 0-63z" transform="matrix(.588,0,0,3.948,37,250)"/>'
            f'<path fill="%23111111" d="M0-63C35-63 63-35 63 0 63 35 35 63 0 63-35 63-63 35-63 0-63-35-35-63 0-63z" transform="matrix(.244,0,0,1.636,37,250)"/>'
            f'</svg>'
        )

        return f"data:image/svg+xml,{svg}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._spool
        coord = self.coordinator

        # Tare : custom override > valeur officielle TigerTag
        tare_custom   = coord.get_tare(self._uid)
        tare_official = d.get("container_weight")
        tare_effective = tare_custom if tare_custom is not None else tare_official

        try:
            r, g, b = int(d.get("color_r",0)), int(d.get("color_g",0)), int(d.get("color_b",0))
        except (TypeError, ValueError):
            r = g = b = 0

        attrs: dict[str, Any] = {
            "uid":           self._uid,
            "brand":         self._ref("brand",    d.get("id_brand")),
            "material":      self._ref("material", d.get("id_material")),
            "type":          self._ref("type",     d.get("id_type")),
            "tag_type":      self._ref("version",  d.get("id_tigertag") or d.get("id_version")),
            "is_plus":       bool(d.get("url_img") and d.get("url_img") not in ("","--")),
            "has_twin":      bool(d.get("twin_tag_uid")),
            "twin_uid":      d.get("twin_tag_uid"),
            # Apparence
            "series":        clean_value(d.get("series")),
            "product_name":  clean_value(d.get("name") or d.get("color_name")),
            "color_name":    clean_value(d.get("color_name") or d.get("name") or d.get("message")),
            "color_hex":     f"#{r:02x}{g:02x}{b:02x}",
            # Couleurs secondaires (bicolor, tricolor) depuis les champs RFID
            "color_hex2":    f"#{int(d.get('color_r2',0)):02x}{int(d.get('color_g2',0)):02x}{int(d.get('color_b2',0)):02x}" if d.get("color_r2") else None,
            "color_hex3":    f"#{int(d.get('color_r3',0)):02x}{int(d.get('color_g3',0)):02x}{int(d.get('color_b3',0)):02x}" if d.get("color_r3") else None,
            "aspect1":       self._ref("aspect", d.get("id_aspect1") or d.get("id_aspect")),
            "aspect2":       self._ref("aspect", d.get("id_aspect2")),
            # Spécifications
            "diameter":      self._ref("diameter", d.get("data1")),
            "capacity_gr":   d.get("measure_gr") or d.get("measure"),
            "container_weight":         tare_official,
            "container_weight_custom":  tare_custom,
            "container_weight_effective": tare_effective,
            "container_id":  clean_value(d.get("container_id")),
            # Impression
            "nozzle_temp_min": d.get("data2"),
            "nozzle_temp_max": d.get("data3"),
            "dry_temp":        d.get("data4"),
            "dry_time_hours":  d.get("data5"),
            "bed_temp_min":    d.get("data6"),
            "bed_temp_max":    d.get("data7"),
            # Flags
            "is_refill":   bool(d.get("info1")),
            "is_recycled": bool(d.get("info2")),
            "is_filled":   bool(d.get("info3")),
            # Produit
            "sku":      clean_value(d.get("sku")),
            "barcode":  clean_value(d.get("barcode")),
            # img_url : image officielle si TigerTag+, sinon SVG coloré généré
            "img_url":  self.entity_picture,
            "twin_uid": clean_value(d.get("twin_tag_uid")),
            # Liens
            "link_youtube": clean_value(d.get("LinkYoutube")),
            "link_msds":    clean_value(d.get("LinkMSDS")),
            "link_tds":     clean_value(d.get("LinkTDS")),
            "link_rohs":    clean_value(d.get("LinkROHS")),
            "link_reach":   clean_value(d.get("LinkREACH")),
            "link_food":    clean_value(d.get("LinkFOOD")),
            # Couleurs étendues
            "online_color_list": d.get("online_color_list") or [],
            # Profil filament Bambu sauvegardé (tray_info_idx)
            "bambu_profile_idx": coord.get_spool_profile(self._uid),
            "online_color_type": d.get("online_color_type"),
            # Dates (epoch seconds après nettoyage Firestore dans api.py)
            "updated_at":  d.get("updated_at"),   # dernière modif (epoch s)
            "last_update": d.get("last_update"),   # dernière sync  (epoch ms → on divise)
            # Emplacements
            "ams_location":    coord.get_location(self._uid),
            "room_location":   coord.get_room(self._uid),
            # Lieux configurés (utilisés par la carte JS pour les filtres)
            "config_locations": (coord.data or {}).get("config_locations", []),
        }
        # Filtre : exclure None ET les dicts non sérialisables par HA
        # (ex: champs Firestore deleted_at/updated_at = {"_seconds":...})
        return {
            k: v for k, v in attrs.items()
            if v is not None and not isinstance(v, (dict, list))
            or isinstance(v, list) and all(not isinstance(i, dict) for i in v)
        }


class TigerTagStatsSensor(CoordinatorEntity[TigerTagDataUpdateCoordinator], SensorEntity):
    """
    Sensor de statistiques globales TigerTag.

    Expose en valeur principale : le nombre de bobines uniques (twin dédupliqués).
    Expose en attributs : toutes les métriques utiles pour les dashboards.

    entity_id : sensor.tigertag_stats
    """

    _attr_has_entity_name = False
    _attr_icon            = "mdi:printer-3d-nozzle"
    _attr_state_class     = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"tigertag_stats_{entry.entry_id}"
        self.entity_id = "sensor.tigertag_statistiques"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="TigerTag Studio",
            manufacturer="TigerTag Project",
            model="Inventory Manager",
            sw_version="2.0",
            configuration_url="https://app.tigertag.io",
        )

    @property
    def name(self) -> str:
        return "Statistiques"

    def _compute_stats(self) -> dict:
        """
        Calcule les statistiques en une passe.
        Déduplication twin : on garde le premier de chaque paire rencontré
        et on marque son twin comme déjà vu — simple et fiable.
        """
        data      = self.coordinator.data or {}
        inventory = data.get("inventory", {})
        thr       = 250  # seuil stock faible en grammes

        seen:         set[str] = set()
        count_unique  = 0
        count_ams     = 0
        count_no_loc  = 0
        count_low     = 0
        count_refill  = 0
        twin_pairs    = 0
        total_weight  = 0.0

        for key, spool in inventory.items():
            uid      = str(spool.get("uid", key))
            twin_uid = str(spool["twin_tag_uid"]) if spool.get("twin_tag_uid") else None

            # Déjà compté comme twin d'une bobine précédente → on saute
            if uid in seen:
                continue

            count_unique += 1
            seen.add(uid)

            if twin_uid:
                seen.add(twin_uid)  # empêche le twin d'être compté à son tour
                twin_pairs += 1

            w = float(spool.get("weight_available") or spool.get("weight") or 0)
            total_weight += w

            if self.coordinator.get_location(uid):
                count_ams += 1
            elif not self.coordinator.get_room(uid):
                count_no_loc += 1

            if 0 < w < thr:  # 0 exclu : non renseigné ≠ vide
                count_low += 1

            if spool.get("info1"):
                count_refill += 1

        return {
            "count_unique":      count_unique,
            "count_total_tags":  len(inventory),
            "count_twin_pairs":  twin_pairs,
            "count_in_ams":      count_ams,
            "count_no_location": count_no_loc,
            "count_low_stock":   count_low,
            "count_refill":      count_refill,
            "total_weight_g":    round(total_weight, 1),
            "total_weight_kg":   round(total_weight / 1000, 3),
        }

    @property
    def native_value(self) -> int:
        """Valeur principale = nombre de bobines uniques (twins dédupliqués)."""
        return self._compute_stats()["count_unique"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        stats = self._compute_stats()
        # Ajouter les profils Bambu mis en cache (pour la carte JS)
        bambu_profiles = (self.coordinator.data or {}).get("bambu_profiles", {})
        if bambu_profiles:
            stats["bambu_profiles"] = bambu_profiles
        return stats
