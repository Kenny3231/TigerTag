"""Constantes pour l'intégration TigerTag."""

DOMAIN = "tigertag"

# Config flow
CONF_EMAIL     = "email"
CONF_API_KEY   = "api_key"
CONF_LOCATIONS = "locations"   # lieux de stockage définis par l'utilisateur

# Intervalles
UPDATE_INTERVAL            = 300    # inventaire : 5 minutes
REFERENCES_UPDATE_INTERVAL = 86400  # références  : 24 heures

# Services HA
SERVICE_UPDATE_WEIGHT = "update_spool_weight"
SERVICE_BAMBU_AMS     = "set_bambu_ams_filament"
SERVICE_SET_ROOM      = "set_spool_room"
SERVICE_REFRESH       = "refresh"

# Bambu Lab — sécurité
BAMBU_VALID_TRAY_TYPES = frozenset({
    "PLA","PETG","ABS","ASA","TPU","PA","PC","PVA","HIPS",
})
BAMBU_TRAY_INFO_IDX: dict[str, str] = {
    "PLA":"GFA00","PETG":"GFG00","ABS":"GFB00","ASA":"GFB01",
    "TPU":"GFU00","PA":"GFN00","PC":"GFC00","PVA":"GFS00","HIPS":"GFB02",
}

DEFAULT_NOZZLE_TEMP_MIN = 190
DEFAULT_NOZZLE_TEMP_MAX = 240
DEFAULT_LOCATIONS       = ["Garage","Salon","Bureau"]
