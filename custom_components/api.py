"""Client HTTP asynchrone pour l'API TigerTag."""
import asyncio
import logging
import socket
from typing import Any, Optional

import aiohttp
import async_timeout

_LOGGER = logging.getLogger(__name__)

BASE_URL            = "https://cdn.tigertag.io"
REFERENCES_BASE_URL = "https://api.tigertag.io/api:tigertag"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TigerTagApiClientError(Exception):
    """Exception générique pour l'API TigerTag."""


class TigerTagApiClientCommunicationError(TigerTagApiClientError):
    """Erreur réseau ou timeout."""


class TigerTagApiClientAuthenticationError(TigerTagApiClientError):
    """Clé API ou e-mail invalide."""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class TigerTagApiClient:
    """Client asynchrone pour l'API TigerTag."""

    def __init__(self, email: str, api_key: str, session: aiohttp.ClientSession) -> None:
        self._email   = email
        self._api_key = api_key
        self._session = session

    async def _api_wrapper(self, method: str, url: str) -> Any:
        """
        Exécute une requête HTTP et normalise toutes les exceptions.
        La clé API est masquée dans les logs (remplacée par ***).
        """
        safe_url = url.replace(self._api_key, "***") if self._api_key else url
        _LOGGER.debug("→ %s %s", method, safe_url)

        try:
            async with async_timeout.timeout(10):
                response = await self._session.request(method=method, url=url)

            # Erreurs d'authentification interceptées avant raise_for_status
            if response.status in (401, 403):
                raise TigerTagApiClientAuthenticationError(
                    "Authentification refusée — vérifiez votre clé API et votre e-mail."
                )

            response.raise_for_status()

            # content_type=None pour éviter les crashs sur réponses mal typées
            try:
                return await response.json(content_type=None)
            except (aiohttp.ContentTypeError, ValueError):
                return await response.text()

        except TigerTagApiClientError:
            raise
        except asyncio.TimeoutError as exc:
            raise TigerTagApiClientCommunicationError(
                "Délai d'attente dépassé lors de la connexion à l'API TigerTag."
            ) from exc
        except (aiohttp.ClientError, socket.gaierror) as exc:
            raise TigerTagApiClientCommunicationError(f"Erreur réseau : {exc}") from exc
        except Exception as exc:
            raise TigerTagApiClientError(f"Erreur inattendue : {exc}") from exc

    # ------------------------------------------------------------------
    # Endpoints
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        """Vérifie la validité de la clé API. Retourne True/False sans lever d'exception."""
        try:
            await self._api_wrapper("GET", f"{BASE_URL}/pingbyapikey?ApiKey={self._api_key}")
            return True
        except TigerTagApiClientAuthenticationError:
            return False
        except TigerTagApiClientError as err:
            _LOGGER.error("Ping TigerTag échoué : %s", err)
            return False

    async def get_inventory(self) -> dict[str, Any]:
        """
        Récupère l'inventaire des bobines.
        - Normalise en dict {uid: spool_data}
        - Filtre les bobines supprimées (deleted == True)
          Une bobine supprimée a "deleted": true dans le JSON.
          "deleted": null = active, "deleted": true = supprimée.
          On filtre aussi les bobines avec deleted_at mais sans deleted=true
          (cas edge comme la bobine Test dans ton inventaire).
        """
        url    = f"{BASE_URL}/exportInventory?ApiKey={self._api_key}&email={self._email}"
        result = await self._api_wrapper("GET", url)

        if isinstance(result, list):
            raw = {str(item.get("uid", i)): item for i, item in enumerate(result)}
        elif isinstance(result, dict):
            raw = result
        else:
            _LOGGER.warning("Format d'inventaire inattendu : %s", type(result))
            return {}

        # Nettoyage des Firestore Timestamps (dicts non-sérialisables par HA)
        # {"_seconds": int, "_nanoseconds": int} → int (epoch seconds)
        def _clean(obj):
            if isinstance(obj, dict):
                if "_seconds" in obj and "_nanoseconds" in obj:
                    return obj["_seconds"]
                return {k: _clean(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_clean(i) for i in obj]
            return obj

        raw = {key: _clean(spool) for key, spool in raw.items()}

        # Filtrage des bobines supprimées (deleted: true uniquement)
        active = {
            key: spool
            for key, spool in raw.items()
            if spool.get("deleted") is not True
        }

        _LOGGER.debug(
            "%d bobine(s) active(s) sur %d dans l'inventaire (%d supprimée(s) ignorée(s))",
            len(active), len(raw), len(raw) - len(active),
        )
        return active

    async def set_weight(
        self,
        uid: str,
        weight: int,
        container_weight: Optional[int] = None,
    ) -> Any:
        """
        Met à jour le poids d'une bobine.
        Valide les paramètres localement avant d'appeler l'API.
        """
        if not uid or not isinstance(uid, str) or len(uid) > 64:
            raise ValueError(f"UID invalide : {uid!r}")
        if not isinstance(weight, (int, float)) or not (0 <= weight <= 99_999):
            raise ValueError(f"Poids invalide : {weight!r}")

        url = (
            f"{BASE_URL}/setSpoolWeightByRfid"
            f"?ApiKey={self._api_key}&uid={uid}&weight={int(weight)}"
        )

        if container_weight is not None:
            if not isinstance(container_weight, (int, float)) or container_weight < 0:
                raise ValueError(f"Poids conteneur invalide : {container_weight!r}")
            url += f"&container_weight={int(container_weight)}"

        return await self._api_wrapper("GET", url)

    async def set_weight_with_twin(
        self,
        uid: str,
        weight: int,
        container_weight: int = 0,
        twin_uid: str | None = None,
    ) -> None:
        """
        Met à jour le poids d'une bobine et, si elle a un twin_tag_uid,
        met à jour les deux bobines avec le même poids.
        C'est le comportement officiel de l'app TigerTag Studio Manager.
        """
        await self.set_weight(uid=uid, weight=weight, container_weight=container_weight)

        if twin_uid:
            _LOGGER.debug("Twin Tag détecté — mise à jour simultanée de %s", twin_uid)
            try:
                await self.set_weight(uid=twin_uid, weight=weight, container_weight=container_weight)
            except Exception as err:
                _LOGGER.warning("Mise à jour du twin %s échouée : %s", twin_uid, err)

    async def get_references(self) -> dict[str, Any]:
        """
        Récupère toutes les tables de correspondance (marques, matériaux, aspects…).
        Les endpoints en erreur retournent None sans faire échouer l'ensemble.
        """
        endpoints = {
            "version":      f"{REFERENCES_BASE_URL}/version/get/all",
            "material":     f"{REFERENCES_BASE_URL}/material/get/all",
            "aspect":       f"{REFERENCES_BASE_URL}/aspect/get/all",
            "type":         f"{REFERENCES_BASE_URL}/type/get/all",
            "diameter":     f"{REFERENCES_BASE_URL}/diameter/filament/get/all",
            "brand":        f"{REFERENCES_BASE_URL}/brand/get/all",
            "measure_unit": f"{REFERENCES_BASE_URL}/measure_unit/get/all",
        }

        references: dict[str, Any] = {}
        for key, url in endpoints.items():
            try:
                references[key] = await self._api_wrapper("GET", url)
            except Exception as err:
                _LOGGER.warning("Référence '%s' non récupérée : %s", key, err)
                references[key] = None

        return references
