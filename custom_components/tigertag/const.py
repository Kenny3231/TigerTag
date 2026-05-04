"""Constantes pour l'intégration TigerTag."""

DOMAIN = "tigertag"

# Config flow
CONF_EMAIL        = "email"
CONF_PASSWORD     = "password"
CONF_FIREBASE_UID = "firebase_uid"

# Intervalles
UPDATE_INTERVAL            = 300    # inventaire : 5 minutes
REFERENCES_UPDATE_INTERVAL = 86400  # références  : 24 heures
TOKEN_REFRESH_INTERVAL     = 3300   # token Firebase : 55 minutes

# Firebase
FIREBASE_CONFIG_URL   = "https://tigertag-cdn.web.app/__/firebase/init.json"
FIREBASE_AUTH_URL     = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
FIREBASE_REFRESH_URL  = "https://securetoken.googleapis.com/v1/token"
FIRESTORE_BASE_URL    = "https://firestore.googleapis.com/v1"
REFERENCES_BASE_URL   = "https://api.tigertag.io/api:tigertag"

# Services HA
SERVICE_UPDATE_WEIGHT = "update_spool_weight"
SERVICE_BAMBU_AMS     = "set_bambu_ams_filament"
SERVICE_SET_RACK      = "set_spool_rack"
SERVICE_SET_TARE      = "set_spool_tare"
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
