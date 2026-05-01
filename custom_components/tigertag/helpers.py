"""
Fonctions utilitaires partagées par toute l'intégration TigerTag.

Centralisées ici pour éviter la duplication entre number.py, sensor.py,
bambu.py, et __init__.py.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .coordinator import TigerTagDataUpdateCoordinator


def resolve_reference(
    coordinator: "TigerTagDataUpdateCoordinator",
    ref_type: str,
    item_id: Any,
) -> str:
    """
    Traduit un ID numérique en libellé lisible via les tables de référence TigerTag.

    L'API TigerTag utilise tantôt 'label', tantôt 'name' selon l'endpoint —
    on cherche les deux pour couvrir tous les cas.

    Exemples :
        resolve_reference(coordinator, "brand",    42)  → "Bambu Lab"
        resolve_reference(coordinator, "material",  3)  → "PETG"
        resolve_reference(coordinator, "aspect",    1)  → "Matte"
    """
    if not item_id:
        return ""

    refs = (coordinator.data or {}).get("references", {}).get(ref_type)
    if not refs:
        return str(item_id)

    target = str(item_id)

    if isinstance(refs, list):
        for item in refs:
            if str(item.get("id", "")) == target:
                return item.get("label") or item.get("name") or target

    elif isinstance(refs, dict):
        val = refs.get(target)
        if isinstance(val, dict):
            return val.get("label") or val.get("name") or target
        if isinstance(val, str):
            return val

    return target


def resolve_spool(
    coordinator: "TigerTagDataUpdateCoordinator",
    uid: str,
) -> dict[str, Any] | None:
    """
    Cherche et retourne les données d'une bobine par son UID.
    Retourne None si introuvable.
    """
    inventory = (coordinator.data or {}).get("inventory", {})
    for key, value in inventory.items():
        if str(value.get("uid", key)) == uid:
            return value
    return None


def clean_value(val: Any) -> Any:
    """
    Normalise les valeurs "vides" renvoyées par l'API TigerTag.
    L'API utilise "--" comme valeur sentinelle pour les champs non renseignés.
    Retourne None si la valeur est vide, None, ou "--".
    """
    if val is None:
        return None
    if isinstance(val, str) and (val.strip() == "" or val.strip() == "--"):
        return None
    return val


def spool_display_name(spool_data: dict[str, Any], brand: str, uid: str) -> str:
    """
    Construit le nom d'affichage d'une bobine pour l'interface HA.
    Format : [Marque] [Série] [Nom/Couleur] [5 derniers chars UID]

    Les parties vides sont ignorées proprement.
    """
    series    = spool_data.get("series", "")
    color     = spool_data.get("color_name") or spool_data.get("name") or ""
    uid_tail  = uid[-5:] if len(uid) >= 5 else uid

    parts = [str(p).strip() for p in (brand, series, color, uid_tail) if p]
    return " ".join(parts) or f"Spool {uid}"


def spool_color_hex(spool_data: dict[str, Any]) -> str:
    """
    Convertit les composantes RGB de la bobine en couleur hexadécimale CSS (#rrggbb).
    """
    try:
        r = int(spool_data.get("color_r", 0))
        g = int(spool_data.get("color_g", 0))
        b = int(spool_data.get("color_b", 0))
    except (TypeError, ValueError):
        r = g = b = 0
    return f"#{r:02x}{g:02x}{b:02x}"


def spool_color_bambu(spool_data: dict[str, Any]) -> str:
    """
    Convertit les composantes RGB en format Bambu Lab : RRGGBBFF
    (FF = opacité 100%, toujours fixe pour Bambu Lab).
    """
    try:
        r = int(spool_data.get("color_r", 0))
        g = int(spool_data.get("color_g", 0))
        b = int(spool_data.get("color_b", 0))
    except (TypeError, ValueError):
        r = g = b = 0
    return f"{r:02X}{g:02X}{b:02X}FF"
