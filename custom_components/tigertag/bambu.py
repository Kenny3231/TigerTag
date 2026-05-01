"""
Logique de traduction TigerTag → protocole AMS Bambu Lab.

Ce fichier est volontairement isolé du reste de l'intégration pour deux raisons :
1. La logique est complexe et mérite d'être testable indépendamment.
2. Si Bambu Lab change son protocole MQTT, on sait exactement où toucher.

Point d'entrée principal : build_ams_payload()
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from .const import (
    BAMBU_TRAY_INFO_IDX,
    BAMBU_VALID_TRAY_TYPES,
    DEFAULT_NOZZLE_TEMP_MAX,
    DEFAULT_NOZZLE_TEMP_MIN,
)
from .helpers import resolve_reference, spool_color_bambu

if TYPE_CHECKING:
    from .coordinator import TigerTagDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def resolve_tray_type(
    coordinator: "TigerTagDataUpdateCoordinator",
    spool_data: dict[str, Any],
) -> str:
    """
    Détermine le type de filament Bambu Lab (tray_type) à partir des données TigerTag.

    - Résout l'ID matériau via les tables de référence.
    - Vérifie que le résultat est dans la whitelist Bambu Lab.
    - Retourne "PLA" par défaut si le matériau est inconnu ou hors whitelist.

    Sécurité : sans whitelist, une valeur arbitraire de l'API externe
    serait injectée dans la commande MQTT envoyée à l'imprimante.
    """
    raw = resolve_reference(coordinator, "material", spool_data.get("id_material"))
    tray_type = raw.upper() if raw else "PLA"

    if tray_type not in BAMBU_VALID_TRAY_TYPES:
        _LOGGER.warning(
            "Matériau '%s' non reconnu par Bambu Lab, utilisation de PLA par défaut.",
            tray_type,
        )
        return "PLA"

    return tray_type


def build_ams_payload(
    coordinator: "TigerTagDataUpdateCoordinator",
    spool_data: dict[str, Any],
    ams_id: int,
    tray_id: int,
) -> dict[str, Any]:
    """
    Construit le payload JSON complet pour la commande MQTT Bambu Lab.

    Protocole : ams_filament_setting
    Documentation : https://github.com/bambulab/BambuStudio/wiki/MQTT-API

    Args:
        coordinator : coordinator TigerTag (pour les tables de référence)
        spool_data  : données brutes de la bobine depuis l'inventaire TigerTag
        ams_id      : numéro de l'AMS cible (0 = premier AMS)
        tray_id     : numéro de l'emplacement dans l'AMS (0 à 3)

    Returns:
        dict prêt à être sérialisé en JSON et envoyé via MQTT.
    """
    # 1. Type de filament (avec whitelist de sécurité)
    tray_type = resolve_tray_type(coordinator, spool_data)

    # 2. Code générique Bambu Lab (ex: GFA00 pour PLA générique)
    tray_info_idx = BAMBU_TRAY_INFO_IDX.get(tray_type, "GFA00")

    # 3. Couleur au format Bambu Lab : RRGGBBFF
    tray_color = spool_color_bambu(spool_data)

    # 4. Températures de buse
    #    data2 = temp min, data3 = temp max dans le schéma TigerTag
    try:
        nozzle_min = int(spool_data.get("data2") or DEFAULT_NOZZLE_TEMP_MIN)
    except (TypeError, ValueError):
        nozzle_min = DEFAULT_NOZZLE_TEMP_MIN

    try:
        nozzle_max = int(spool_data.get("data3") or DEFAULT_NOZZLE_TEMP_MAX)
    except (TypeError, ValueError):
        nozzle_max = DEFAULT_NOZZLE_TEMP_MAX

    # Cohérence min/max
    if nozzle_min > nozzle_max:
        _LOGGER.warning(
            "Températures incohérentes (min=%d > max=%d), inversion automatique.",
            nozzle_min, nozzle_max,
        )
        nozzle_min, nozzle_max = nozzle_max, nozzle_min

    # 5. Construction du payload final
    payload = {
        "print": {
            "sequence_id":     "0",
            "command":         "ams_filament_setting",
            "ams_id":          ams_id,
            "tray_id":         tray_id,
            "tray_info_idx":   tray_info_idx,
            "tray_color":      tray_color,
            "nozzle_temp_min": nozzle_min,
            "nozzle_temp_max": nozzle_max,
            "tray_type":       tray_type,
            "setting_id":      "",
        }
    }

    _LOGGER.debug(
        "Payload AMS construit — AMS %d / Tray %d : %s %s %d–%d°C",
        ams_id, tray_id, tray_type, tray_color, nozzle_min, nozzle_max,
    )

    return payload
